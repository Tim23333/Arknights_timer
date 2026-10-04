"""Generic-key portal source profiles, actual movement, CP and commands."""
from pathlib import Path
import sys
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];CANDIDATE=ROOT.parent/'unpack_work/campaign_m18_portal_candidate'
sys.path.insert(0,str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim'
sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
LAST=None
POLICY={'rule':'rule/portal_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}}
def scene(wait=.1):
    tiles=[{'tileKey':'tile_floor','buildableType':1,'passableMask':1} for _ in range(6)]
    tiles[0]={'tileKey':'custom_hatch','buildableType':0,'passableMask':3,'heightType':'LOWLAND','blackboard':None,'effects':None}
    tiles[3]={'tileKey':'custom_emerge','buildableType':0,'passableMask':3,'heightType':'LOWLAND','blackboard':None,'effects':None}
    return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/walker','kind':'entity','tags':['enemy','ground'],'dependencies':['buff/ledger_observer'],
        'components':{'attributes':{'base':{'move_speed':3,'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},
          'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/remove','ability/rng']}}],
        'abilities':[{'id':'ability/remove','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'retire','target':'source','parameters':{'reason':'removed'}}}]},
          {'id':'ability/rng','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'random','target':'source','stream':'imp','probability':.5,'on_success':[{'op':'emit','event':'probe'}]}}]}],
        'buffs':[{'id':'buff/ledger_observer','kind':'buff','interval_seconds':1,'movement_damage':{'effect':{'op':'damage','scale':0,'damage_type':'true'}}}],
        'rules':[{'id':'rule/portal_transition','kind':'calculation_rule','contract':'movement.transition','implementation':{'type':'provider','provider':'ark.movement.living_transition'}}],
        'scenarioDraft':{'id':'scenario/portal','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':6,'tiles':tiles,
          'tile_mechanics':{'custom_hatch':{'type':'route_checkpoint_portal','role':'entry'},'custom_emerge':{'type':'route_checkpoint_portal','role':'exit'}}},
          'initialEntities':[{'definition':'unit/walker','instanceAlias':'walker','position':{'row':0,'col':0},'route':{
            'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':5},'transition_policy':deepcopy(POLICY),
            'checkpoints':[{'type':5},{'type':1,'time':wait},{'type':6,'position':{'row':0,'col':3}}]}}],
          'waves':[],'objectives':{}}}
def make(p):
    global LAST
    LAST=Engine.create(Compiler().compile(p),seed=1803);return LAST
def roundtrip(s):
    r=Engine.restore(s.program,s.checkpoint());s.advance(3);r.advance(3)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_actual_hide_wait_capture_appear_distance_and_cp_replay():
    s=make(scene());s.advance(1);assert s.ctx.route_hidden('walker') and s.ctx.get('walker',('spatial','portal_capture','captured_at'))==0
    assert s.ctx.get('walker',('spatial','position'))=={'row':0,'col':0}
    cp=s.checkpoint();s.advance(2);assert s.ctx.route_hidden('walker');s.advance(1)
    assert not s.ctx.route_hidden('walker') and s.ctx.get('walker',('spatial','position'))['col']==3.1
    assert abs(s.ctx.get('walker',('spatial','distance_travelled'))-.1)<1e-9
    e=[e for e in s.session.events if e['type']=='movement.visibility_changed'];assert [e['time'] for e in e]==[0,3]
    assert all(e['payload']['distance_recorded']==0 and e['payload']['tile_transition']['capture']['entry']['tile_key']=='custom_hatch' for e in e)
    assert s.ctx.get('walker',('spatial','portal_capture')) is None
    r=Engine.restore(s.program,cp);r.advance(3);assert r.snapshot()==s.snapshot();roundtrip(s)
def test_no_automatic_tile_entry_teleport():
    p=scene();route=p['scenarioDraft']['initialEntities'][0]['route'];route['checkpoints']=[]
    s=make(p);s.advance(4);assert s.ctx.get('walker',('spatial','position'))['col']==.4
    assert not s.ctx.route_hidden('walker') and not [e for e in s.session.events if e['type']=='movement.visibility_changed'];roundtrip(s)
def test_pure_tile_profile_reads_no_log_rng_world_changes():
    from ark_sim.domains.tile_mechanics import descriptor
    s=make(scene());before=s.checkpoint()
    for _ in range(4):assert descriptor(s.ctx.spatial.grid,{'row':0,'col':.5})['profile'] is None
    assert before==s.checkpoint()
def test_capture_survives_terrain_invalidation_and_restore():
    p=scene(.2);p['entities'][0]['components']['terrain_overlays']=[{'key':'surface','priority':0,'values':{'buildableType':0}}]
    p['abilities'].append({'id':'ability/change_surface','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_terrain_overlay','target':'source',
       'parameters':{'key':'surface','priority':0,'values':{'buildableType':1}}}]},'timeline':[]})
    p['entities'][0]['components']['abilities'].append('ability/change_surface')
    s=make(p);s.advance(1);cap=s.ctx.get('walker',('spatial','portal_capture'))
    # Public API-only overlay change exercises revision invalidation; no command replay claim for this branch.
    s.ctx.terrain.apply('walker',{'key':'surface','priority':1,'values':{'buildableType':2}})
    assert s.ctx.get('walker',('spatial','portal_capture'))==cap
    r=Engine.restore(s.program,s.checkpoint());s.advance(6);r.advance(6);assert s.snapshot()==r.snapshot() and not s.ctx.route_hidden('walker')
@pytest.mark.parametrize('mutate',[lambda p:p['scenarioDraft']['map'].pop('tile_mechanics'),
 lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_hatch'].update(type='guess'),
 lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_hatch'].update(extra=True),
 lambda p:p['scenarioDraft']['map']['tiles'][0].update(blackboard=[{'key':'unknown','value':1}]),
 lambda p:p['scenarioDraft']['map']['tiles'][3].update(effects=['unknown']),
 lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_hatch'].update(role='exit'),
 lambda p:p['scenarioDraft']['initialEntities'][0]['route']['checkpoints'][2].update(position={'row':0,'col':2}),
 lambda p:p['scenarioDraft']['initialEntities'][0]['route']['checkpoints'].pop(2)])
def test_source_pair_profile_blackboard_and_effects_negative(mutate):
    p=scene();mutate(p)
    with pytest.raises(ValueError):Compiler().compile(p)
def test_entry_exit_conflicting_rule_rejected_and_single_explicit_loaded():
    p=scene();p['rules']+=[{'id':'rule/pair_a','kind':'calculation_rule','extends':'rule/portal_transition'},
                        {'id':'rule/pair_b','kind':'calculation_rule','extends':'rule/portal_transition'}]
    p['scenarioDraft']['map']['tile_mechanics']['custom_hatch']['rule']='rule/pair_a'
    p['scenarioDraft']['map']['tile_mechanics']['custom_emerge']['rule']='rule/pair_b'
    with pytest.raises(ValueError,match='conflicting'):Compiler().compile(p)
    p['scenarioDraft']['map']['tile_mechanics']['custom_emerge'].pop('rule');s=make(p);s.advance(4)
    trace=[e for e in s.session.events if e['type']=='calculation' and e['payload'].get('calculation_id')=='movement.transition']
    assert len(trace)==2 and all(e['payload']['rule_id']=='rule/pair_a' for e in trace);roundtrip(s)
def test_wrong_runtime_origin_and_rule_failure_atomic():
    p=scene();s=make(p);ref=s.session.world.resolve('walker');sp=s.ctx.get(ref,('spatial',));sp['position']={'row':0,'col':1}
    s.ctx.set(ref,('spatial',),sp);before=s.checkpoint();sp=s.ctx.get(ref,('spatial',));state={'checkpoint':0,'path_index':0}
    with pytest.raises(ValueError):s.ctx.movement.transition_checkpoint(ref,sp['route']['checkpoints'][0],sp['route'],sp,state)
    assert s.checkpoint()==before
    p=scene();p['rules']+=[{'id':'rule/wrong_portal','kind':'calculation_rule','contract':'movement.transition',
       'implementation':{'type':'expression','expression':"{'hidden':True,'relocate':False,'position':{'row':0,'col':1}}"}}]
    p['scenarioDraft']['map']['tile_mechanics']['custom_hatch']['rule']='rule/wrong_portal'
    s=make(p);before=s.checkpoint();sp=s.ctx.get('walker',('spatial',));state={'checkpoint':0,'path_index':0}
    with pytest.raises(ValueError,match='authored'):s.ctx.movement.transition_checkpoint('walker',sp['route']['checkpoints'][0],sp['route'],sp,state)
    assert s.checkpoint()==before and s.ctx.get('walker',('spatial','portal_capture')) is None
def test_retired_hidden_actor_does_not_appear():
    p=scene();p['entities'].append({'id':'unit/controller','kind':'entity','tags':['ally'],'components':{'spatial':{},'abilities':['ability/external_remove']}})
    p['abilities'].append({'id':'ability/external_remove','kind':'ability','activation':{'mode':'manual'},
        'timeline':[{'at':0,'effect':{'op':'retire','target':2,'parameters':{'reason':'removed'}}}]})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/controller','instanceAlias':'controller','position':{'row':0,'col':5}})
    s=make(p);assert s.session.world.resolve('walker')==2
    s.submit({'action':'skill','source':'controller','ability':'ability/external_remove'},at=1)
    s.advance(5);assert not s.ctx.alive('walker') and s.ctx.get('walker',('spatial','position'))=={'row':0,'col':0}
    assert len([e for e in s.session.events if e['type']=='movement.visibility_changed'])==1;roundtrip(s)

@pytest.mark.parametrize('offset,valid',[(.49,True),(.5,False)])
def test_half_up_effective_origin_and_static_offset_match(offset,valid):
    p=scene();route=p['scenarioDraft']['initialEntities'][0]['route']
    route['checkpoints'].insert(0,{'type':0,'position':{'row':0,'col':0},'reachOffset':{'x':offset,'y':0}})
    route['reach_offset_policy']={'rule':'rule/offset','parameters':{'axis_signs':{'row':1,'col':1}}}
    p['rules'].append({'id':'rule/offset','kind':'calculation_rule','contract':'movement.checkpoint_position',
       'implementation':{'type':'provider','provider':'ark.movement.checkpoint_cartesian'}})
    if not valid:
        with pytest.raises(ValueError):Compiler().compile(p)
        return
    s=make(p);s.advance(10)
    event=next(e for e in s.session.events if e['type']=='movement.visibility_changed')
    assert event['payload']['tile_transition']['capture']['entry']['cell']=={'row':0,'col':0};roundtrip(s)

@pytest.mark.parametrize('wait',[3,35,40])
def test_native_source_wait_and_portal_tiles_real_model_fixture(wait):
    import json
    package=json.loads((ROOT/'packages/campaign/chapter01_stage_models/m18/level_main_01-12.portal.partial.json').read_bytes())
    audit=json.loads((ROOT/'validation/campaign/chapter01_portal_source_audit.json').read_bytes())
    assoc=next(x for x in audit['route_associations'] if x['hidden_wait_seconds']==[wait])
    rows=package['scenarioDraft']['map']['rows']
    origin={'row':rows-1-assoc['entry_nominal_position']['row'],'col':assoc['entry_nominal_position']['col']}
    exit={'row':rows-1-assoc['exit_position']['row'],'col':assoc['exit_position']['col']}
    p=scene(wait);p['scenarioDraft']['map']=deepcopy(package['scenarioDraft']['map'])
    actor=p['scenarioDraft']['initialEntities'][0];actor['position']=origin;route=actor['route'];route['startPosition']=origin
    # End is the excerpt's exit, not a manufactured ground return across disconnected islands.
    # This fixture proves the source transition excerpt, not a complete native route.
    route['endPosition']=exit;route['checkpoints'][2]['position']=exit
    p['entities'][0]['components']['attributes']['base']['move_speed']=0
    s=make(p);s.advance(1);cp=s.checkpoint();s.advance(wait*30-1);assert s.ctx.route_hidden('walker')
    s.advance(1);assert not s.ctx.route_hidden('walker') and s.ctx.get('walker',('spatial','position'))==exit
    events=[e for e in s.session.events if e['type']=='movement.visibility_changed'];assert [e['time'] for e in events]==[0,wait*30]
    assert s.ctx.get('walker',('spatial','distance_travelled'),0)==0
    r=Engine.restore(s.program,cp);r.advance(wait*30);assert r.snapshot()==s.snapshot();roundtrip(s)

def test_source_wrapper_compiles_without_erasing_other_model_gaps():
    from tools.build_chapter01_portal_model import build,OUTPUT
    import json
    p=build();assert json.loads(OUTPUT.read_bytes())==p
    program=Compiler().compile(p);assert len(program.definitions)>200
    gaps=p['manifest']['metadata']['pending_model_gaps']
    assert 'W_persistent_projectile_attachment_lifecycle' in gaps and 'full_stage_commands_and_checkpoint_replay_not_executed' in gaps
    assert not p['manifest']['metadata']['formal_stage_approved']

def test_captured_origin_mismatch_fails_atomic_before_appear():
    s=make(scene());s.advance(1);sp=s.ctx.get('walker',('spatial',));sp['position']={'row':0,'col':1}
    s.ctx.set('walker',('spatial',),sp);cp=s.checkpoint();sp=s.ctx.get('walker',('spatial',));state=sp['movement'];state['checkpoint']=2
    with pytest.raises(ValueError,match='origin'):
        s.ctx.movement.transition_checkpoint('walker',sp['route']['checkpoints'][2],sp['route'],sp,state)
    assert s.checkpoint()==cp and s.ctx.route_hidden('walker')

def test_rule_receives_actual_tile_parameters_and_capture_clock():
    p=scene();p['scenarioDraft']['map']['tile_mechanics']['custom_hatch'].update(rule='rule/inspect_portal',parameters={'source_marker':17})
    p['rules'].append({'id':'rule/inspect_portal','kind':'calculation_rule','contract':'movement.transition',
      'implementation':{'type':'expression','expression':"{'hidden':inputs.kind == 5,'relocate':inputs.kind == 6,'position':inputs.checkpoint.position if inputs.kind == 6 else inputs.position} if inputs.tile_transition.capture.entry.profile.parameters.source_marker == 17 and inputs.tile_transition.capture.captured_at == 0 else {'invalid':True}"}})
    s=make(p);s.advance(4);assert not s.ctx.route_hidden('walker');roundtrip(s)

def test_failure_after_real_cast_task_cancellation_rolls_back_all():
    p=scene();c=p['entities'][0]['components'];c['buffs']={'initial':['buff/fail_on_interrupt']}
    c['resources']['hp']['recovery_freeze_rule']='rule/failing_freeze'
    p['rules'].append({'id':'rule/failing_freeze','kind':'calculation_rule','contract':'resource.recovery_freeze',
      'metadata':{'recovery_freeze_authority':'final_override'},'implementation':{'type':'expression','expression':'1/0'}})
    p['buffs'].append({'id':'buff/fail_on_interrupt','kind':'buff','events':[{'event':'ability.interrupted',
      'effects':[{'op':'modify_resource','resource':'hp','delta':1,'parameters':{'respect_recovery_freeze':True}}]}]})
    p['abilities'].append({'id':'ability/long','kind':'ability','activation':{'mode':'manual'},'duration_seconds':2,
      'timeline':[{'at_seconds':1,'effect':{'op':'emit','event':'future'}}]})
    c['abilities'].append('ability/long');s=make(p);s.ctx.abilities.start('walker','ability/long')
    before=s.checkpoint();assert any(t['kind']=='domain.ability.effect' for t in s.session.scheduler.pending)
    sp=s.ctx.get('walker',('spatial',));state={'checkpoint':0,'path_index':0}
    with pytest.raises(ValueError):s.ctx.movement.transition_checkpoint('walker',sp['route']['checkpoints'][0],sp['route'],sp,state)
    assert s.checkpoint()==before and s.ctx.get('walker',('runtime','casts')) and not s.ctx.route_hidden('walker')
