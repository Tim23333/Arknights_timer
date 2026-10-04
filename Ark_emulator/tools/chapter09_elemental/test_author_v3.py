"""Public-trigger author tests for the isolated elemental candidate."""
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
CANDIDATE=ROOT.parent/'unpack_work/campaign_elemental_v3_candidate'
sys.path.insert(0,str(CANDIDATE))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.elemental import validate,validate_effect
from ark_sim.tools.replay import replay
from ark_sim.adapters.api import implementation_digest

def rule(name,expression,parameters=None):
    return {'id':'rule/ep/'+name,'kind':'calculation_rule','contract':'elemental.'+name,
            'version':'1.0.0','implementation':{'type':'expression','expression':expression},'parameters':parameters or {}}

def package(capacity=7.5,resistance=0,rate=0,duration=1,callbacks=None,neutral=False,effects=None):
    rules=[rule('capacity','inputs.parameters.capacity'),
           rule('loss','max(0, inputs.request.raw_amount * (1-inputs.parameters.resistance*0.01))'),
           rule('recovery','min(inputs.capacity, max(0, inputs.current+inputs.parameters.recovery_rate*inputs.delta_seconds))'),
           rule('break_duration','inputs.parameters.break_duration_seconds'),
           rule('eligibility',"'neutral' not in inputs.target.tags"),
           rule('packet','inputs.source_attributes.atk * inputs.request.parameters.ep_ratio')]
    profile={'capacity':capacity,'resistance':resistance,'recovery_rate':rate,'break_duration_seconds':duration,
             'rules':{'elemental.'+key:'rule/ep/'+key for key in ('capacity','loss','recovery','break_duration')},
             'on_break':callbacks or [{'op':'emit','event':'ep.callback.start','target':'selected'}],
             'on_end':[{'op':'emit','event':'ep.callback.end','target':'selected'}]}
    if effects is None:effects=[{'op':'elemental_damage','element':'fire','amount':capacity}]
    abilities=[{'id':'ability/ep/cast','kind':'ability','activation':{'mode':'manual'},'selector':'selector/ep/target',
                'duration_seconds':0,'timeline':[{'at':0,'effects':effects}]},
               {'id':'ability/ep/retire','kind':'ability','activation':{'mode':'manual'},'selector':'selector/ep/target',
                'duration_seconds':0,'timeline':[{'at':0,'effect':{'op':'retire','parameters':{'reason':'withdrawn'}}}]},
               {'id':'ability/ep/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/ep/target',
                'duration_seconds':0,'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':40}}]}]
    return {'schemaVersion':2,'rules':rules,'abilities':abilities,
        'entities':[{'id':'unit/ep/source','kind':'entity','tags':['player'],'components':{
            'attributes':{'base':{'atk':60,'attack_interval':2,'attack_speed_ratio':1}},
            'resources':{'hp':{'role':'health','capacity':1000,'initial':1000}},'spatial':{},
            'abilities':[a['id'] for a in abilities]}},
            {'id':'unit/ep/target','kind':'entity','tags':['enemy']+(['neutral'] if neutral else []),'components':{
             'attributes':{'base':{'max_hp':1000,'def':0,'magic_resistance':0}},
             'resources':{'hp':{'role':'health','capacity':1000,'initial':1000}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},
             'elemental':{'elements':{'fire':copy.deepcopy(profile),'water':copy.deepcopy(profile)},'eligibility_rule':'rule/ep/eligibility'}}}],
        'selectors':[{'id':'selector/ep/target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}],
        'scenarioDraft':{'id':'scenario/ep','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},
            'initialEntities':[{'definition':'unit/ep/source','instanceAlias':'source','position':{'row':0,'col':0}},
                              {'definition':'unit/ep/target','instanceAlias':'target','position':{'row':0,'col':1}}]}}

def create(**kwargs):return Engine.create(Compiler().compile(package(**kwargs)),seed=29)
def cast(sim,at=2,ability='ability/ep/cast'):
    sim.submit({'action':'skill','source':'source','ability':ability},at=at)
def state(sim):return sim.ctx.get('target',('runtime','elemental'))
def events(sim,kind):return [thaw(x) for x in sim.session.events if x['type']==kind]

def test_public_low_capacity_real_break_all_lock_end():
    sim=create();cast(sim);sim.session.advance(3)
    s=state(sim);assert s['remaining']=={'fire':0,'water':7.5} and s['break']['due']==32
    assert s['break']['provenance']['source']==sim.session.world.resolve('source')
    assert s['break']['provenance']['element']=='fire'
    cast(sim,5);sim.session.advance(29)
    assert len(events(sim,'elemental.break.started'))==1 and state(sim)['remaining']['fire']==0
    sim.session.advance(1)
    assert state(sim)['remaining']=={'fire':7.5,'water':7.5} and state(sim)['break'] is None
    assert len(events(sim,'ep.callback.start'))==len(events(sim,'ep.callback.end'))==1

def test_two_same_tick_packets_first_crossing_wins():
    sim=create(effects=[{'op':'elemental_damage','element':'water','amount':7.5},
                        {'op':'elemental_damage','element':'fire','amount':100}])
    cast(sim);sim.session.advance(3)
    assert state(sim)['break']['element']=='water' and state(sim)['remaining']=={'fire':7.5,'water':0}
    assert len(events(sim,'elemental.loss.accepted'))==1

def test_separate_resources_resistance_and_recovery():
    sim=create(resistance=50,rate=3,effects=[{'op':'elemental_damage','element':'fire','amount':6}]);cast(sim)
    sim.session.advance(3);assert state(sim)['remaining']['fire']==4.5
    sim.session.advance(15);assert state(sim)['remaining']['fire']==pytest.approx(6.)
    assert state(sim)['remaining']['water']==7.5 and state(sim)['break'] is None

def test_zero_direct_loss_no_world_rng_event_or_scheduler_write():
    sim=create();before=sim.session.checkpoint()
    result=sim.ctx.elemental.apply(sim.session.world.resolve('source'),sim.session.world.resolve('target'),
        {'op':'elemental_damage','element':'fire','amount':0})
    assert result=={'accepted':True,'loss':0,'break':False} and sim.session.checkpoint()==before

def test_neutral_qualification_real_public_rejection():
    sim=create(neutral=True);cast(sim);sim.session.advance(3)
    assert state(sim)['remaining']=={'fire':7.5,'water':7.5} and not events(sim,'elemental.loss.accepted')

def test_health_then_independent_source_packet_public_atomic():
    sim=create(capacity=100,effects=[{'op':'elemental_attack',
        'health_effect':{'op':'damage','damage_type':'true','scale':.5},
        'element_effect':{'op':'elemental_damage','element':'fire','amount_rule':'rule/ep/packet','parameters':{'ep_ratio':.2}}}])
    cast(sim);sim.session.advance(3)
    assert sim.ctx.resources.current('target','hp')==970
    assert state(sim)['remaining']['fire']==88 # 60*.2; health30 must not be used.
    rows=[x['type'] for x in sim.session.events if x['type'] in ('damage.accepted','elemental.loss.accepted')]
    assert rows==['damage.accepted','elemental.loss.accepted']

def test_derived_packet_error_rolls_back_health_events_rng_queue():
    data=package(capacity=100,effects=[{'op':'elemental_attack',
        'health_effect':{'op':'damage','damage_type':'true','scale':.5},
        'element_effect':{'op':'elemental_damage','element':'fire','amount_rule':'rule/ep/packet','parameters':{'ep_ratio':.2}}}])
    next(x for x in data['rules'] if x['contract']=='elemental.packet')['implementation']['expression']='-1'
    sim=Engine.create(Compiler().compile(data));before=sim.session.checkpoint()
    with pytest.raises(ValueError):sim.ctx.effects.execute(sim.session.world.resolve('source'),[sim.session.world.resolve('target')],data['abilities'][0]['timeline'][0]['effects'][0])
    assert sim.session.checkpoint()==before

@pytest.mark.parametrize('ability,reason',[('ability/ep/retire','withdrawn'),('ability/ep/kill','dead')])
def test_public_lifecycle_cancels_break_expiry(ability,reason):
    sim=create();cast(sim);cast(sim,5,ability);sim.session.advance(40)
    assert sim.ctx.get('target',('runtime','state'))==reason and state(sim)['break'] is None
    assert not events(sim,'ep.callback.end') and not any(t['kind']=='domain.elemental.expire' for t in sim.session.scheduler.pending)

def test_on_break_retire_aborts_later_owned_callback():
    sim=create(callbacks=[{'op':'retire','parameters':{'reason':'withdrawn'}},{'op':'emit','event':'ep.invalid.after_retire'}])
    cast(sim);sim.session.advance(4)
    assert not events(sim,'ep.invalid.after_retire') and state(sim)['break'] is None

def test_late_unowned_expiry_cannot_finish_current_lease():
    sim=create();cast(sim);sim.session.advance(3);before=sim.session.checkpoint()
    sim.ctx.elemental.expire(sim.session,{'target':sim.session.world.resolve('target'),'generation':1})
    assert sim.session.checkpoint()==before

def test_locked_loss_is_full_noop_and_original_source_retire_does_not_reassign_provenance():
    sim=create(callbacks=[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}])
    cast(sim);sim.session.advance(3)
    assert sim.ctx.get('source',('runtime','state'))=='withdrawn'
    before=sim.session.checkpoint()
    result=sim.ctx.elemental.apply(3,3,{'op':'elemental_damage','element':'water','amount':100})
    assert result['reason']=='break_locked' and sim.session.checkpoint()==before
    assert state(sim)['break']['provenance']['source_stamp']['state']=='alive'
    sim.session.advance(30)
    assert len(events(sim,'ep.callback.end'))==1 and state(sim)['remaining']=={'fire':7.5,'water':7.5}

def test_on_end_new_generation_aborts_remaining_old_callback():
    data=package()
    profile=data['entities'][1]['components']['elemental']['elements']['fire']
    profile['on_end']=[{'op':'elemental_damage','element':'fire','amount':7.5},
                       {'op':'emit','event':'ep.invalid.old_end'}]
    sim=Engine.create(Compiler().compile(data));cast(sim);sim.session.advance(33)
    assert state(sim)['break']['generation']==2 and state(sim)['break']['due']==62
    assert len(events(sim,'elemental.break.started'))==2 and not events(sim,'ep.invalid.old_end')

def test_on_break_callback_fault_rolls_back_complete_request():
    sim=create(callbacks=[{'op':'emit','event':'ep.before_fault'},
                          {'op':'modify_resource','resource':'missing','delta':1}])
    before=sim.session.checkpoint()
    with pytest.raises(ValueError):sim.ctx.effects.execute(2,[3],{'op':'elemental_damage','element':'fire','amount':7.5})
    assert sim.session.checkpoint()==before

def test_real_end_callback_fault_not_swallowed_and_lease_state_rolls_back():
    data=package();data['entities'][1]['components']['elemental']['elements']['fire']['on_end']=[
        {'op':'emit','event':'ep.end_before_fault'},{'op':'modify_resource','resource':'missing','delta':1}]
    sim=Engine.create(Compiler().compile(data));cast(sim);sim.session.advance(32)
    before=state(sim)
    with pytest.raises(ValueError):sim.session.advance(1)
    after=state(sim)
    # Phase0 resource tick legitimately precedes the failing owned expiry.
    assert {k:v for k,v in after.items() if k!='last_time'}=={k:v for k,v in before.items() if k!='last_time'}
    assert after['last_time']==32 and not events(sim,'ep.end_before_fault') and not events(sim,'elemental.break.ended')
    assert sim.session.checkpoint()['failure']['exception']=='ValueError'

@pytest.mark.parametrize('kind', ['capacity','loss','recovery','break_duration'])
def test_invalid_pure_outputs_never_partially_commit(kind):
    data=package();next(x for x in data['rules'] if x['contract']=='elemental.'+kind)['implementation']['expression']='-1'
    if kind=='capacity':
        with pytest.raises(ValueError):Engine.create(Compiler().compile(data))
        return
    sim=Engine.create(Compiler().compile(data));before=sim.session.checkpoint()
    if kind=='recovery':
        with pytest.raises(ValueError):sim.session.advance(2)
        assert state(sim)['remaining']=={'fire':7.5,'water':7.5}
    else:
        with pytest.raises(ValueError):sim.ctx.effects.execute(2,[3],{'op':'elemental_damage','element':'fire','amount':7.5})
        assert sim.session.checkpoint()==before

def test_target_lifecycle_generation_change_invalidates_stale_expiry_without_refill():
    data=package()
    data['entities'][1]['components']['lifecycle']['parameters']={'revive':True,'revive_value':1000}
    sim=Engine.create(Compiler().compile(data));cast(sim);cast(sim,5,'ability/ep/kill');sim.session.advance(7)
    assert state(sim)['break'] is None and not any(t['kind']=='domain.elemental.expire' for t in sim.session.scheduler.pending)
    sim.session.advance(26)
    assert sim.ctx.get('target',('runtime','lifecycle_generation'))==1 and sim.ctx.resources.current('target','hp')==1000
    assert state(sim)['break'] is None and state(sim)['remaining']['fire']==0
    assert not events(sim,'ep.callback.end')

def test_true_cp_and_from_start_replay_same_events_world_rng_queue(tmp_path):
    sim=create();cast(sim);cast(sim,8);sim.session.advance(13)
    checkpoint=sim.checkpoint();path=tmp_path/'checkpoint.json';path.write_text(json.dumps(checkpoint),encoding='utf-8')
    restored=Engine.restore(sim.program,json.loads(path.read_text()))
    sim.session.advance(28);restored.session.advance(28)
    assert sim.checkpoint()==restored.checkpoint()
    head=replay(sim.program,sim.export_replay())
    assert head.checkpoint()==sim.checkpoint()

@pytest.mark.parametrize('value',[True,math.nan,math.inf,-1])
def test_amount_strict_boundary_validation(value):
    with pytest.raises(ValueError):validate_effect({'op':'elemental_damage','element':'fire','amount':value})

def test_bad_eligibility_output_rolls_back_rule_trace():
    data=package();next(x for x in data['rules'] if x['contract']=='elemental.eligibility')['implementation']['expression']='1'
    sim=Engine.create(Compiler().compile(data));before=sim.session.checkpoint()
    with pytest.raises(ValueError):sim.ctx.elemental.apply(2,3,{'op':'elemental_damage','element':'fire','amount':1})
    assert sim.session.checkpoint()==before

def test_contract_original_99_and_full_new_6_schema():
    parent=json.loads((ROOT/'ark_sim/rules/contracts.json').read_bytes())
    current=json.loads((CANDIDATE/'ark_sim/rules/contracts.json').read_bytes())
    assert len(parent['contracts'])==99 and current['contracts'][:99]==parent['contracts']
    assert current['types']==parent['types'] and len(current['contracts'])==105
    new=current['contracts'][99:]
    assert {x['id'] for x in new}=={'elemental.'+k for k in ('capacity','loss','recovery','break_duration','eligibility','packet')}
    for row in new:
        assert row['pureEvaluation'] is True and row['writesStateDirectly'] is False and row['contractVersion']==1
        assert row['implementations']==['expression','graph','provider']
        assert all(set(x)=={'name','type','required'} and x['required'] is True for x in row['inputs'])

def test_scenario_override_only_profile_has_real_owned_expiry_handler():
    data=package()
    profile=data['entities'][1]['components'].pop('elemental')
    data['scenarioDraft']['initialEntities'][1]['components']={'elemental':profile}
    sim=Engine.create(Compiler().compile(data));cast(sim);sim.session.advance(33)
    assert len(events(sim,'elemental.break.ended'))==1 and state(sim)['remaining']['fire']==7.5

def test_scenario_effective_profile_strict_false_not_integer_before_runtime():
    data=package();data['scenarioDraft']['initialEntities'][1]['components']={'elemental':{'elements':{'fire':{'capacity':True}}}}
    with pytest.raises(ValueError):Compiler().compile(data)

def projectile_package(source_invalid='retain'):
    data=package(capacity=100,effects=[{'op':'elemental_attack',
        'health_effect':{'op':'damage','damage_type':'true','scale':.5,'projectile_definition':'projectile/ep/author'},
        'element_effect':{'op':'elemental_damage','element':'fire','amount_rule':'rule/ep/packet','parameters':{'ep_ratio':.2}}}])
    data['rules'] += [
        {'id':'rule/ep/trajectory','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},
        {'id':'rule/ep/collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}]
    data['projectiles']=[{'id':'projectile/ep/author','kind':'projectile','motion':{'rule':'rule/ep/trajectory','parameters':{'mode':'homing','speed':2}},
        'collision':{'rule':'rule/ep/collision','parameters':{'enabled':False}},'lifetime_seconds':3,
        'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,
        'lifecycle':{'source_invalid':source_invalid,'source_hidden':'retain','target_invalid':'cancel','target_hidden':'cancel',
             'finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':False,'hit_on_expire':False}}]
    data['scenarioDraft']['resources']={'dp':{'initial':10,'capacity':99}}
    return data

def test_real_compound_projectile_pending_then_one_health_and_ep_with_disk_cp(tmp_path):
    sim=Engine.create(Compiler().compile(projectile_package()));cast(sim)
    sim.session.advance(6)
    assert sim.ctx.resources.current('target','hp')==1000 and state(sim)['remaining']['fire']==100
    path=tmp_path/'inflight.json';path.write_text(json.dumps(sim.checkpoint()),encoding='utf-8')
    restored=Engine.restore(sim.program,json.loads(path.read_text()))
    sim.session.advance(25);restored.session.advance(25)
    assert sim.checkpoint()==restored.checkpoint()
    assert sim.ctx.resources.current('target','hp')==970 and state(sim)['remaining']['fire']==88
    assert len(events(sim,'damage.accepted'))==len(events(sim,'elemental.loss.accepted'))==1
    assert events(sim,'damage.accepted')[0]['time']==events(sim,'elemental.loss.accepted')[0]['time']
    assert replay(sim.program,sim.export_replay()).checkpoint()==sim.checkpoint()

@pytest.mark.parametrize('policy,loss',[('retain',12),('cancel',0)])
def test_public_source_withdraw_retained_registry_scope_or_actual_cancel(policy,loss):
    sim=Engine.create(Compiler().compile(projectile_package(policy)));cast(sim)
    sim.submit({'action':'withdraw','source':'source'},at=5);sim.session.advance(31)
    assert sim.ctx.get('source',('runtime','state'))=='withdrawn'
    assert sim.ctx.resources.current('target','hp')==1000-(30 if loss else 0)
    assert state(sim)['remaining']['fire']==100-loss

def test_forged_projectile_cast_has_no_retained_permission():
    sim=Engine.create(Compiler().compile(projectile_package()));sim.submit({'action':'withdraw','source':'source'},at=1)
    sim.session.advance(2);before=sim.session.checkpoint()
    result=sim.ctx.elemental.apply(2,3,{'op':'elemental_damage','element':'fire','amount':12},cast={
        'id':'cast/fake','projectile_impact':True,'source_generation':0,'launch_snapshot':sim.ctx.capture_view(2)})
    assert result['reason']=='source_invalid' and sim.session.checkpoint()==before

def test_dead_target_cancels_whole_compound_payload():
    sim=Engine.create(Compiler().compile(projectile_package()));cast(sim);cast(sim,5,'ability/ep/kill')
    sim.session.advance(31)
    assert not events(sim,'elemental.loss.accepted') and state(sim)['remaining']['fire']==100

def test_actual_stored_old_cast_is_not_call_stack_authority_before_or_after_hit():
    sim=Engine.create(Compiler().compile(projectile_package()));cast(sim)
    sim.submit({'action':'withdraw','source':'source'},at=5);sim.session.advance(6)
    stored=next(iter(sim.ctx.get('system/battle',('projectiles','instances')).values()))['cast']
    for after_hit in (False,True):
        if after_hit:sim.session.advance(25)
        before=sim.session.checkpoint()
        result=sim.ctx.elemental.apply(2,3,{'op':'elemental_damage','element':'fire','amount':1},cast=stored)
        assert result['reason']=='source_invalid' and sim.session.checkpoint()==before
    assert state(sim)['remaining']['fire']==88

def test_same_callback_capacity_loss_clamps_all_resources_and_zero_rate_tick_also_syncs():
    data=package(capacity=13.5,effects=[{'op':'apply_buff','buff':'buff/ep/capacity'},
                                      {'op':'elemental_damage','element':'fire','amount':1.5}])
    data['entities'][1]['components']['attributes']['base']['ep_capacity']=13.5
    next(x for x in data['rules'] if x['contract']=='elemental.capacity')['implementation']['expression']='inputs.attributes.target.ep_capacity'
    data['buffs']=[{'id':'buff/ep/capacity','kind':'buff','modifiers':[{'attribute':'ep_capacity','layer':'flat','value':-6}]}]
    sim=Engine.create(Compiler().compile(data));cast(sim);sim.session.advance(3)
    assert state(sim)['remaining']=={'fire':6,'water':7.5}
    assert len(events(sim,'elemental.capacity.synced'))==2
    data['abilities'][0]['timeline'][0]['effects']=[{'op':'apply_buff','buff':'buff/ep/capacity'}]
    sim=Engine.create(Compiler().compile(data));cast(sim);sim.session.advance(4)
    assert state(sim)['remaining']=={'fire':7.5,'water':7.5}

if __name__=='__main__':
    run=Path('E:/ArkSimLogs/runs/chapter09_elemental_author_v3');run.mkdir(parents=True,exist_ok=True)
    code=pytest.main([str(Path(__file__)),'-q','--basetemp',str(run/'temp'),'-o','cache_dir='+str(run/'pytest_cache')])
    print('candidate_core',implementation_digest())
    raise SystemExit(code)
