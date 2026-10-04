"""Independent M14 raw-source and real-kill Timeline witnesses; no receipt."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m12_projection_candidate'
CORE='bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
PACKAGE=ROOT/'packages/campaign/mainline_models/level_main_00-10.m14_timeline.json'
PIN='83bfa1829958f80a4f1da95740466326db3f5a8c7143737d728887b3670116d2'
NATIVE=ROOT/'packages/campaign/native_reference/level_main_00-10.json'
BASE=ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'


def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def pulse(name):return {'op':'emit','target':'battle','event':'peer.'+name}
def birth(alias,block=False):return {'kind':'spawn','managed':True,'blocks_wave':True,'blocks_fragment':block,'spawn':{'definition':'unit/peer_enemy','instanceAlias':alias,'position':{'row':1,'col':1}}}


def audit(native,model):
    scene=model['scenarioDraft'];tl=scene['timeline'];rows=scene['map']['rows']
    baseline=read(BASE)
    for section in ('entities','abilities','buffs','selectors','rules','behaviors'):assert model[section]==baseline[section]
    for key in ('map','roster','resources','rules','parameters','objectives','seed'):assert scene[key]==baseline['scenarioDraft'][key]
    assert tl['policy']=='managed_clear' and tl['negative_timeout_policy']=='wait_for_clear'
    assert len(tl['waves'])==len(native['waves'])
    counts=Counter();routes=set();controls=[]
    allowed={'actionType','managedByScheduler','key','count','preDelay','interval','routeIndex','blockFragment','autoPreviewRoute','autoDisplayEnemyInfo',
        'isUnharmfulAndAlwaysCountAsKilled','hiddenGroup','randomSpawnGroupKey','randomSpawnGroupPackKey','randomType','refreshType','weight','dontBlockWave','forceBlockWaveInBranch'}
    entities={e['metadata']['native_id']:e for e in model['entities'] if 'enemy' in e.get('tags',[])}
    for wi,(nw,w) in enumerate(zip(native['waves'],tl['waves'])):
        assert set(nw)=={'preDelay','postDelay','maxTimeWaitingForNextWave','fragments','advancedWaveTag'} and nw['advancedWaveTag'] is None
        assert (w['pre_delay_seconds'],w['post_delay_seconds'],w['max_wait_seconds'])==(nw['preDelay'],nw['postDelay'],nw['maxTimeWaitingForNextWave'])
        assert len(w['fragments'])==len(nw['fragments'])
        for fi,(nf,f) in enumerate(zip(nw['fragments'],w['fragments'])):
            assert f['pre_delay_seconds']==nf['preDelay'] and len(f['actions'])==len(nf['actions'])
            for ai,(na,a) in enumerate(zip(nf['actions'],f['actions'])):
                assert set(na)==allowed and na['randomType']=='ALWAYS' and na['refreshType']=='ALWAYS'
                assert not na['hiddenGroup'] and not na['randomSpawnGroupKey'] and not na['randomSpawnGroupPackKey']
                assert not na['isUnharmfulAndAlwaysCountAsKilled'] and not na['forceBlockWaveInBranch']
                assert (a['delay_seconds'],a['interval_seconds'],a['count'])==(na['preDelay'],na['interval'],na['count'])
                assert a['metadata']['native_action']==na and a['metadata']['native_wave']==wi and a['metadata']['native_fragment']==fi and a['metadata']['native_action_index']==ai
                if na['actionType']=='SPAWN':
                    assert a['kind']=='spawn' and a['managed']==na['managedByScheduler'] and a['blocks_wave']==(not na['dontBlockWave']) and a['blocks_fragment']==na['blockFragment']
                    counts[a['spawn']['definition']]+=a['count'];routes.add(na['routeIndex']);assert a['spawn']['definition']=='unit/'+na['key']
                    route=deepcopy(native['routes'][na['routeIndex']]);motion='FLY' if 'flying' in entities[na['key']]['tags'] else 'WALK'
                    assert route['motionMode'] in ('E_NUM',motion);route['motionMode']=motion
                    for key in ('startPosition','endPosition'):route[key]['row']=rows-1-route[key]['row']
                    for c in route.get('checkpoints') or []:
                        assert c['type'] in ('MOVE','WAIT_FOR_SECONDS') and not c['randomizeReachOffset'] and c['reachDistance']==0
                        assert not any(c['reachOffset'].values());c['position']['row']=rows-1-c['position']['row']
                    assert route==a['spawn']['route'] and a['spawn']['position']==route['startPosition']
                    p=a['spawn']['placement'];assert p['offset']=={'row':-route['spawnOffset']['y'],'col':route['spawnOffset']['x']}
                    assert p['random_range']=={'row':route['spawnRandomRange']['y'],'col':route['spawnRandomRange']['x']}
                else:
                    assert na['actionType'] in ('STORY','DISPLAY_ENEMY_INFO') and a['kind']=='effects'
                    assert a['metadata']['native_gate_flags']=={k:na[k] for k in ('managedByScheduler','dontBlockWave','blockFragment')}
                    assert a['metadata']['zero_lifetime_member_elision'] is True
                    assert a['effects'][0]['event']=='m14.ui.started' and a['effects'][-1]['event']=='m14.ui.ack_finished'
                    assert a['effects'][-1]['payload']['completion_lifetime_ticks']==0 and not a['effects'][-1]['payload']['native_UI_callback_verified']
                    controls.append((wi,fi,ai,na['actionType']))
    assert sum(counts.values())==35 and len(counts)==5 and len(routes)==17
    return {'population':dict(counts),'route_indices':sorted(routes),'controls':controls,'zero_lifetime_profile_not_native_callback':True}


def scene(block=False,timeout=-1,ui=False):
    effects=[pulse('same_fragment_after_member')]
    actions=[birth('first',block)]
    if ui:
        data=read(PACKAGE);native_ui=data['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]
        actions.insert(0,deepcopy(native_ui))
    return {'schemaVersion':2,'manifest':{'id':'package/m14_peer','version':'1','requires':['preset/ark_standard']},
        'entities':[{'id':'unit/peer_enemy','kind':'entity','tags':['enemy','ground'],'components':{'attributes':{'base':{'max_hp':10,'atk':0,'def':0,'mres':0}},
            'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},
            {'id':'unit/peer_killer','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'atk':1000}},'spatial':{},'abilities':['ability/peer_kill']}}],
        'abilities':[{'id':'ability/peer_kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer_enemy',
            'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true'}}]}],
        'selectors':[{'id':'selector/peer_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}],
        'scenarioDraft':{'id':'scenario/m14_peer','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':4},
            'initialEntities':[{'definition':'unit/peer_killer','instanceAlias':'killer','position':{'row':0,'col':0}}],
            'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[
                {'pre_delay_seconds':.1,'post_delay_seconds':.2,'max_wait_seconds':timeout,'fragments':[{'pre_delay_seconds':.1,'actions':actions},{'actions':[{'kind':'effects','effects':effects}]}]},
                {'pre_delay_seconds':.1,'fragments':[{'pre_delay_seconds':.1,'actions':[dict(birth('second'),delay_seconds=.1)]}]}]}}}


def make(data):
    from ark_sim import Compiler,Engine
    return Engine.create(Compiler().compile(data),seed=1401)


def finish(s,expected):
    from ark_sim import Engine
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    saved=s.checkpoint();r=Engine.restore(s.program,saved);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    return {'expected':expected,'checkpoint_equal':True,'replay_equal':True,'program_fingerprint':s.program.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,
        'commands':s.export_replay(),'fixture_initial_state':thaw(s.program.scenario),'state':s.ctx.state(),
        'events':[thaw(e) for e in s.session.events if e['type'] in ('entity.created','entity.died','combat.kill','damage.accepted','command.accepted','command.rejected','timeline.action','timeline.member_released','timeline.wave_completed','timeline.finished','m14.ui.started','m14.ui.ack_finished','m14.ui.command_observed','input.lock_changed','peer.same_fragment_after_member')]}


def real_kill_managed_gate(block=False,ui=False):
    s=make(scene(block=block,ui=ui));s.advance(12)
    assert s.ctx.state()['pending_waves']==1 and s.ctx.state()['timeline']['phase']==('fragment_wait' if block else 'wave_gate')
    before=[e for e in s.session.events if e['type']=='peer.same_fragment_after_member'];assert bool(before)==(not block)
    s.submit({'action':'skill','source':'killer','ability':'ability/peer_kill'},at=12);s.advance(16)
    assert s.ctx.state()['kills']==1 and s.ctx.state()['leaks']==0 and s.ctx.state()['pending_waves']==1
    s.advance(1);assert s.ctx.state()['pending_waves']==0
    assert Counter(e['definition_id'] for e in s.session.world.entities())=={'system/battle':1,'unit/peer_killer':1,'unit/peer_enemy':2}
    assert s.ctx.get('second',('spatial','timing_origins'))=={'play_start':0,'wave_start':19,'fragment_start':25,'action_start':28}
    assert [e['time'] for e in s.session.events if e['type']=='entity.died']==[12]
    if ui:
        seen=[e for e in s.session.events if e['type'] in ('m14.ui.started','m14.ui.ack_finished')]
        assert [e['type'] for e in seen]==['m14.ui.started','m14.ui.ack_finished'] and {e['time'] for e in seen}=={6}
        assert not s.ctx.state()['input_locks']
    return finish(s,{'real_skill_kills_at12_releases_after_effect_phase13':True,'second_born28':True,'no_shadow_actors':True,'UI_lifetime0':ui})


def late_old_member_timeout():
    p=scene(timeout=.2);w=p['scenarioDraft']['timeline']['waves'];w[0]['pre_delay_seconds']=0;w[0]['post_delay_seconds']=.3;w[0]['fragments'][0]['pre_delay_seconds']=0
    w[1]['pre_delay_seconds']=.3;w[1]['fragments'][0]['pre_delay_seconds']=.4
    s=make(p);s.submit({'action':'skill','source':'killer','ability':'ability/peer_kill'},at=20);s.advance(39)
    assert s.ctx.state()['kills']==1 and s.ctx.state()['pending_waves']==1
    s.advance(1);assert s.ctx.get('second',('spatial','timing_origins'))=={'play_start':0,'wave_start':15,'fragment_start':36,'action_start':39}
    return finish(s,{'finite_timeout6_then_post9_then_pre9_fragment12_action3':True,'old_member_death20_does_not_reset_new_wake':True,'second39':True})


def zero_count():
    p=scene();a=p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0];a['count']=0
    a['spawn']['placement']={'rule':'rule/m7_spawn_rectangle','stream':'spawn','sample_axes':['col','row'],'sample_zero_range':True,'offset':{'row':0,'col':0},'random_range':{'row':.2,'col':.2}}
    p['rules']=[deepcopy(next(r for r in read(PACKAGE)['rules'] if r['id']=='rule/m7_spawn_rectangle'))]
    s=make(p);s.advance(19)
    assert not [e for e in s.session.events if e['type']=='entity.created' and e['payload']['definition']=='unit/peer_enemy']
    assert not s.session.random.samples and s.ctx.state()['pending_waves']==1
    return finish(s,{'zero_count_creates_no_actor_no_RNG_no_pending_population_for_first':True})


def source_negative_cases():
    n,p=read(NATIVE),read(PACKAGE);results=[]
    for name in ('flag','unknown_flag','max_wait','delay','route','motion'):
        native,model=deepcopy(n),deepcopy(p)
        source=native['waves'][0]['fragments'][1]['actions'][0];converted=model['scenarioDraft']['timeline']['waves'][0]['fragments'][1]['actions'][0]
        if name=='flag':converted['blocks_wave']=False
        elif name=='unknown_flag':source['newActiveFlag']=True
        elif name=='max_wait':model['scenarioDraft']['timeline']['waves'][0]['max_wait_seconds']=1
        elif name=='delay':converted['delay_seconds']+=1
        elif name=='route':converted['spawn']['route']['checkpoints'][0]['position']['row']+=1
        else:converted['spawn']['route']['motionMode']='FLY'
        try:audit(native,model)
        except AssertionError:results.append(name)
        else:raise AssertionError('mutant source/consumer accepted: '+name)
    return {'source_mutant_rejections':results,'meaning':'Independent provenance audit, not author builder or core test logic'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m14_timeline_peer_initial.json');args=parser.parse_args()
    sys.path.insert(0,str(CANDIDATE));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim' and implementation_digest()==CORE and sha(PACKAGE)==PIN
    files=[Path(__file__),PACKAGE,NATIVE,BASE,ROOT/'packages/campaign/controls.00_10.reference.json'];before={str(p):sha(p) for p in files}
    cases=[]
    checks={'raw_source_projection':lambda:audit(read(NATIVE),read(PACKAGE)),'real_kill_wave_gate':lambda:real_kill_managed_gate(),
        'real_kill_fragment_gate':lambda:real_kill_managed_gate(block=True),'UI_same_tick_gate_equivalence':lambda:real_kill_managed_gate(block=True,ui=True),
        'finite_timeout_late_member':late_old_member_timeout,'zero_count':zero_count,'source_negative_cases':source_negative_cases}
    for name,fn in checks.items():
        try:cases.append({'case':name,'result':'passed','actual':fn()})
        except Exception as error:cases.append({'case':name,'result':'failed','error':repr(error)})
    stable=before=={str(p):sha(p) for p in files} and implementation_digest()==CORE
    result={'schema':'ark-sim/bounded-timeline-peer-review/v1','passed':stable and all(c['result']=='passed' for c in cases),'implementation_sha256':CORE,
        'input_package_sha256':PIN,'runtime_module':ark_sim.__file__,'source_at_start':before,'source_at_completion':{str(p):sha(p) for p in files},
        'identity_stable':stable,'cases':cases,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(Path(__file__)),'result':'passed' if all(c['result']=='passed' for c in cases) else 'failed'}],
        'scope':'Independent raw35/17/5 and synthetic public-kill Timeline boundaries; not a whole-stage or native UI receipt','formal_approval':False,'review_receipt':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':result['passed'],'cases':[(c['case'],c['result'],c.get('error')) for c in cases]}));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
