"""Independent bounded M13 lifecycle witnesses; no promotion/receipt authority."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m13_control_lifecycle_candidate'
DIGEST='419b3c706820597d6d5b9f012e5a4caa33ea0adfd9ca1a62dbf2151566895df2'
RESULTS=[]


def pulse(name):return {'op':'emit','target':'battle','event':'peer.'+name}
def input_lock(on):return {'op':'input_lock','target':'battle','parameters':{'key':'shared','enabled':on}}
def payment(delta):return {'op':'modify_resource','target':'battle','resource':'credit','delta':delta}
def action(alias='notice',delay=0,fragment=True,wave=True):return {'kind':'control','definition':'control/peer','instanceAlias':alias,'delay_seconds':delay,'managed':True,'blocks_fragment':fragment,'blocks_wave':wave}


def scene(steps=None,actions=None,ack='external'):
    return {'schemaVersion':2,'manifest':{'id':'package/m13_peer','version':'1','requires':['preset/ark_standard']},
        'controls':[{'id':'control/peer','kind':'control','clock_policy':'logical','ack_policy':ack,
            'on_start':[input_lock(True),pulse('start')],'on_complete':[payment(2),pulse('done')],
            'steps':steps if steps is not None else [{'kind':'ack','key':'confirm'}]}],
        'entities':[{'id':'unit/peer_enemy','kind':'entity','tags':['enemy','ground'],'components':{
            'attributes':{'base':{'max_hp':10,'atk':0,'def':0,'mres':0}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},
            'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],
        'scenarioDraft':{'id':'scenario/m13_peer','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':4},
            'resources':{'credit':{'initial':10,'capacity':100},'life':{'initial':5,'capacity':5}},'objectives':{'type':'waves','life_resource':'life'},
            'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[
                {'actions':actions or [action()]},
                {'actions':[{'kind':'spawn','spawn':{'definition':'unit/peer_enemy','instanceAlias':'arriving','position':{'row':1,'col':1}},'managed':False,'blocks_wave':False}]}]},
                {'fragments':[{'actions':[{'kind':'effects','effects':[pulse('wave2')]}]}]}]}}}


def make(data):
    from ark_sim import Compiler,Engine
    return Engine.create(Compiler().compile(data),seed=1318)


def observed(sim,expected,roundtrip=True):
    from ark_sim import Engine
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    if roundtrip:
        saved=sim.checkpoint();other=Engine.restore(sim.program,saved);sim.advance(2);other.advance(2)
        assert sim.snapshot()==other.snapshot()
        assert sim.snapshot()==replay(sim.program,sim.export_replay()).snapshot()
    return {'expected':expected,'program_fingerprint':sim.program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
        'state':sim.ctx.state(),'events':[thaw(e) for e in sim.session.events if not e['type'].startswith('calculation.')],
        'commands':sim.export_replay(),'fixture_initial_state':thaw(sim.program.scenario),
        'checkpoint_equal':True if roundtrip else 'API-only boundary; not command replayed','replay_equal':True if roundtrip else 'API-only boundary; not command replayed'}


def case_external_fragment_wave_and_registration():
    s=make(scene());s.advance(4)
    state=s.ctx.state()['timeline'];assert state['fragment_index']==0 and state['remaining_actions']==0
    assert 'control/1' in state['control_members'] and s.ctx.state()['pending_waves']==1
    assert not any('enemy' in e['tags'] for e in s.session.world.entities())
    s.submit({'action':'control_ack','control':'notice','step':0},at=4);s.advance(3)
    assert s.ctx.controls.instance('notice')['status']=='completed' and s.ctx.resources.current('system/battle','credit')==12
    assert not s.ctx.state()['input_locks'] and s.ctx.state()['pending_waves']==0
    assert len([e for e in s.session.events if e['type']=='peer.wave2'])==1
    return observed(s,{'pending_spawn_before_ack':1,'fragment_and_wave_released_after_actual_ack':True,'credit':12})


def case_overlap_global_same_key():
    p=scene(actions=[action('a',fragment=False),action('b',fragment=False)]);p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':input_lock(True)}]
    s=make(p);s.advance(3);assert set(s.ctx.state()['input_locks'])=={'shared','control/1:shared','control/2:shared'}
    s.submit({'action':'control_ack','control':'a','step':0},at=3);s.advance(1)
    assert set(s.ctx.state()['input_locks'])=={'shared','control/2:shared'}
    assert s.ctx.state()['timeline']['phase']=='wave_gate'
    s.submit({'action':'control_ack','control':'b','step':0},at=4);s.advance(3)
    assert s.ctx.state()['input_locks']==['shared']
    return observed(s,{'each_instance_lock_is_owned':True,'global_lock_remains':True})


def case_wrong_ack_direct_atomic():
    s=make(scene());s.advance(3)
    for ref,step in [('notice',True),('notice',9),('absent',0)]:
        before=s.checkpoint()
        try:s.ctx.controls.acknowledge(ref,step)
        except ValueError:pass
        else:raise AssertionError('invalid ack accepted')
        assert before==s.checkpoint()
    return observed(s,{'bad_reference_or_bool_or_wrong_step_preserves_entire_checkpoint':True},False)


def case_pending_continue_and_terminal():
    s=make(scene(actions=[action(delay=1)]));s.advance(2);assert s.ctx.controls.instance('notice')['status']=='pending'
    s.ctx.controls.cancel('notice','peer_request',policy='continue');s.advance(35)
    assert s.ctx.controls.instance('notice')['status']=='cancelled' and s.ctx.state()['pending_waves']==0
    assert len([e for e in s.session.world.entities() if 'enemy' in e['tags']])==1
    assert not [e for e in s.session.events if e['type']=='control.completed']
    continued=observed(s,{'cancel_pending_releases_fragment_and_preserves_one_real_birth':True},False)
    p=scene(actions=[action(delay=1)]);p['scenarioDraft']['scheduledEffects']=[{'at':2,'effect':{'op':'modify_resource','target':'battle','resource':'life','value':0}}]
    s=make(p);s.advance(5)
    assert s.ctx.state()['finished'] and s.ctx.state()['result']=='defeat' and s.ctx.state()['pending_waves']==1
    assert not any('enemy' in e['tags'] for e in s.session.world.entities())
    assert s.ctx.controls.instance('notice')['status']=='cancelled'
    assert not [t for t in s.session.scheduler.pending if t['kind'].startswith(('domain.control','domain.timeline'))]
    return {'continue_API':continued,'terminal_commands_replay':observed(s,{'unborn_population_kept_pending1_not_counted_kill':True})}


def case_complete_cancel_start_rollback():
    from ark_sim.rules.errors import RuleError
    snapshots=[]
    for phase in ('on_start','on_complete','on_cancel'):
        p=scene(actions=[action(delay=1 if phase=='on_start' else 0)])
        p['rules']=[{'id':'rule/peer_fail','kind':'calculation_rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}}]
        p['controls'][0][phase]=[input_lock(True),{'op':'random','stream':'imp','probability':1,'on_success':[payment(-3)]},
            {'op':'modify_resource','target':'battle','resource':'credit','amount_rule':'rule/peer_fail'}]
        s=make(p);s.advance(2);before=s.checkpoint()
        try:
            if phase=='on_start':s.ctx.controls.begin('notice')
            elif phase=='on_complete':s.ctx.controls.acknowledge('notice',0)
            else:s.ctx.controls.cancel('notice','peer',policy='continue')
        except RuleError:pass
        else:raise AssertionError('expected arithmetic failure')
        assert before==s.checkpoint();snapshots.append({'phase':phase,'full_checkpoint_equal':True})
    return {'expected':{'world_events_resources_tasks_RNG_and_membership_atomic':True},'actual':snapshots,'API_only':True}


def case_null_actor_alias_and_bad_diagnostic():
    s=make(scene());s.advance(2)
    ref=s.ctx.lifecycle.create('unit/peer_enemy',position={'row':0,'col':0},alias=None)
    assert s.ctx.alive(ref)
    bad=[]
    for alias in (7,True,{},[]):
        before=s.checkpoint()
        try:s.ctx.lifecycle.create('unit/peer_enemy',position={'row':0,'col':0},alias=alias)
        except ValueError as error:bad.append({'alias':alias,'error':str(error)})
        except Exception as error:
            RESULTS.append({'case':'null_actor_alias_and_bad_diagnostic','result':'failed','expected':'ValueError with actor alias diagnostic and no side effects','actual_type':type(error).__name__,'error':str(error),'input_alias':alias,'checkpoint_equal':before==s.checkpoint()})
            raise
        else:raise AssertionError('illegal alias created')
        assert s.checkpoint()==before
    return {'expected':{'null_legal_nonstring_ValueError_without_mutation':True},'actual':bad,'API_only':True}


def case_terminal_inside_start_effect():
    p=scene(steps=[{'kind':'effects','effects':[pulse('after_fatal')]}],ack='immediate')
    p['controls'][0]['on_start']=[input_lock(True),{'op':'modify_resource','target':'battle','resource':'life','value':0}]
    s=make(p);s.advance(3)
    # A real lifecycle terminal is detected within this same logical tick;
    # keep the exact events as a provisional terminal-order counterexample.
    data=observed(s,{'fatal_control_must_not_emit_followup_or_completed':True})
    if any(e['type'] in ('peer.after_fatal','control.completed') for e in s.session.events):
        RESULTS.append({'case':'terminal_inside_start_effect','result':'failed','actual':data});raise AssertionError('control followed fatal life mutation with continuation/completion before same-tick terminal')
    return data


def case_source_three_stories_logical_clock():
    sys.path.insert(1,str(ROOT))
    from tools.experiments.m13.build_chapter01_control_profiles import build
    raw=json.loads((ROOT/'packages/campaign/chapter01_controls/native.reference.json').read_bytes())
    values=[]
    for policy in ('immediate','external'):
        source,package=build(policy)
        for key in ('obt/tutorial/level/main_01-11_a','obt/tutorial/level/main_01-11_b','obt/tutorial/level/main_01-12'):
            item=next(x for x in source['action_templates'] if x['native_action']['key']==key)
            template=deepcopy(item['template']);template['delay_seconds']=0
            # Fixture removes only source-level start offset to inspect the story
            # clock itself, and records this explicit change in its initial state.
            p=scene(actions=[template]);p['controls']=deepcopy(package['controls'])
            s=make(p);s.advance(1);alias=template['instanceAlias']
            rows=raw['stories'][key]['classified_rows']
            delay_seconds=sum(r['decoded_parameters']['time'] for r in rows if r['command']=='Delay')
            assert delay_seconds==(18 if key.endswith('01-11_b') else 0)
            definition=next(c for c in p['controls'] if c['id']==template['definition'])
            assert definition['clock_policy']=='logical' and definition['ack_policy']==policy
            assert definition['metadata']['native_flags_and_rows']==rows
            assert template['blocks_fragment']==item['native_action']['blockFragment']
            assert template['blocks_wave']==(not item['native_action']['dontBlockWave'])
            if policy=='external':
                assert s.ctx.controls.instance(alias)['phase']=='awaiting_ack'
                assert s.ctx.state()['input_locks']
                for _ in range(600):
                    instance=s.ctx.controls.instance(alias)
                    if instance['status']=='completed':break
                    if instance['phase']=='awaiting_ack':s.submit({'action':'control_ack','control':alias,'step':instance['waiting_step']})
                    s.advance(1)
                else:raise AssertionError('external source story failed finite completion')
            else:s.advance(541)
            assert s.ctx.controls.instance(alias)['status']=='completed' and not s.ctx.state()['input_locks']
            if policy=='immediate':assert s.ctx.controls.instance(alias)['completed_at']==30*delay_seconds
            ev=[e for e in s.session.events if e['type']=='chapter01.control.source_row_observed']
            actual=[e['payload']['native_row'] for e in ev]
            expected=[r for r in rows if r['classification']!='blank']
            assert actual==expected
            if policy=='immediate' and key.endswith('01-11_b'):
                assert [e['time'] for e in ev if e['payload']['native_row']['command']=='PopupDialog']==[0,120,240,360,480]
            values.append({'story':key,'policy':policy,'result':observed(s,{'source_rows_and_gate_flags_preserved':True,'wall_clock_not_claimed':True,'logical_delay_seconds':delay_seconds})})
    return values


def case_no_control_scene_remains_without_control_state():
    p=scene();p.pop('controls');p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions']=[{'kind':'effects','effects':[payment(1)]}]
    s=make(p);s.advance(3)
    assert getattr(s.ctx,'controls',None) is None and 'controls' not in s.ctx.state()
    assert s.ctx.resources.current('system/battle','credit')==11 and s.ctx.state()['pending_waves']==0
    return observed(s,{'no_controls_component_or_state_introduced':True,'legacy_effect_and_spawn_math_preserved':True})


CASES={k[5:]:v for k,v in list(globals().items()) if k.startswith('case_')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,default=CANDIDATE)
    parser.add_argument('--digest',default=DIGEST);parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m13_control_peer_initial.json')
    parser.add_argument('--case',action='append');args=parser.parse_args();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim'
    before=implementation_digest();assert before==args.digest
    files=[Path(__file__),ROOT/'tools/experiments/m13/build_chapter01_control_profiles.py',ROOT/'packages/campaign/chapter01_controls/native.reference.json']
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    for name in args.case or list(CASES):
        try:RESULTS.append({'case':name,'result':'passed','actual':CASES[name]()})
        except Exception as error:
            if not any(r['case']==name and r['result']=='failed' for r in RESULTS):RESULTS.append({'case':name,'result':'failed','error':repr(error)})
    stable=before==implementation_digest() and hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    result={'schema':'ark-sim/bounded-control-peer-review/v1','passed':stable and all(r['result']=='passed' for r in RESULTS),
        'implementation_sha256':before,'runtime_module':ark_sim.__file__,'cases':RESULTS,'identity_stable':stable,
        'source_at_start':hashes,'source_at_completion':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed' if all(r['result']=='passed' for r in RESULTS) else 'failed'}],
        'formal_approval':False,'promotion_receipt':False,'scope':'bounded generic control lifecycle cases; no native UI or stage approval'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':result['passed'],'cases':[(r['case'],r['result']) for r in RESULTS],'output':str(args.output)}))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
