"""Independent no-source damage boundaries against actual M72 candidate."""
from pathlib import Path
from copy import deepcopy
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m79_rebirth_environment_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def request(**changes):
    return {'op':'no_source_damage','fixed_amount':700,'damage_type':'true',
        'origin':{'kind':'periodic_field','field_uid':'field/test','cell':{'row':1,'col':1},'trigger_sequence':1},
        'ignore_for_sp':False,'attack_type':'NONE','damage_without_modify':False,
        'node_is_env_damage':False,'env_blackboard_injected':True,'environmental':True,
        'rules':{'damage.pipeline':'rule/model_no_source_fixed_pipeline'},**changes}


def rule(ident, expression, contract='damage.pipeline'):
    return {'id':ident,'kind':'calculation_rule','contract':contract,
        'implementation':{'type':'graph','nodes':[{'id':'result','expression':expression}],'output':'nodes.result'}}


def fixture(hp=1000, buffs=(), resources=None, health='hp'):
    entity={'id':'unit/victim','kind':'entity','tags':['enemy','ground'],
        'components':{'attributes':{'base':{'max_hp':hp,'def':99999,'res':99,'atk':0}},
        'resources':{health:{'initial':hp,'capacity':hp,'role':'health'}, **(resources or {})},
        'lifecycle':{'policy':'policy/ark_lifecycle','parameters':{'health_resource':health}},
        'spatial':{},'abilities':[],'buffs':{'initial':list(buffs)}}}
    return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},
        'rules':[json.loads((ROOT/'tools/candidates/m72_no_source_damage/pipeline.rule.json').read_text())],
        'entities':[entity], 'scenarioDraft':{'id':'scene/no_source','ruleset':'ruleset/ark_standard',
        'map':{'rows':3,'cols':3},'initialEntities':[{'definition':'unit/victim','instanceAlias':'victim','position':{'row':1,'col':1}}],
        'scheduledEffects':[{'at':999999,'effect':request(target=2)}]}}


def make(package=None): return Engine.create(Compiler().compile(package or fixture()),seed=17)
def values(sim): return sim.checkpoint()
def events(sim,event): return [thaw(e) for e in sim.session.events if e['type']==event]
def damage(sim,targets=('victim',),**changes): return sim.ctx.effects.execute(None,targets,request(**changes))


def test_fixed_pure700_not_def_res_actual100_health_counter_origin_and_death():
    sim=make(fixture(hp=100))
    result=damage(sim)
    event=events(sim,'damage.accepted')[-1]['payload']
    assert result['actual_health_loss']==100
    assert event['amount']==event['actual_health_loss']==100 and event['pipeline_amount']==700
    assert sim.ctx.resources.current('victim','hp')==0
    assert sim.ctx.state()['damage_dealt']==100 and sim.ctx.state()['kills']==1
    for kind in ['resource.changed','damage.accepted','entity.died','combat.kill']:
        payload=events(sim,kind)[-1]['payload']
        assert payload['source'] is None and payload['origin']['field_uid']=='field/test'
        assert payload['node_is_env_damage'] is False and payload['env_blackboard_injected'] is True
    assert not events(sim,'attack.accepted')
    assert sim.session.random.samples==()


def test_actual_decoded_environment_source_request_fields_consumed():
    import hashlib
    path=ROOT/'packages/campaign/chapter04_environment/source.reference.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest()=='148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8'
    source=json.loads(path.read_text(encoding='utf8'))
    component=next(c for c in source['prefabs']['tile_volcano']['components'].values() if '_actions' in c['raw'])
    raw=component['raw'];node=json.loads(raw['_actions']['SerializedState'])[0]
    bb={row['key']:row['value'] for row in source['stage_tile_operands']['level_main_04-09'][0]['blackboard']}
    assert node['_damageType']=='PURE' and type(raw['_injectEnvDmgFlagToBlackboard']) is int
    sim=make(fixture(hp=100))
    damage(sim,fixed_amount=bb[node['_damageKey']],ignore_for_sp=node['_ignoreForSp'],
        attack_type=node['_attackType'],damage_without_modify=node['_damageWithoutModify'],
        node_is_env_damage=node['_isEnvDamage'],env_blackboard_injected=bool(raw['_injectEnvDmgFlagToBlackboard']))
    event=events(sim,'damage.accepted')[-1]['payload']
    assert type(event['pipeline_amount']) is float and event['pipeline_amount']==700.0
    assert event['amount']==100 and event['source'] is None
    assert event['ignore_for_sp'] is False and event['damage_without_modify'] is False
    assert event['node_is_env_damage'] is False and event['env_blackboard_injected'] is True


def test_pipeline_replacement_target_context_source_empty():
    p=fixture()
    p['rules'][0]=rule('rule/model_no_source_fixed_pipeline',
        "{'accepted': inputs.source == {} and context.source == {}, 'amount': inputs.effect.fixed_amount / 2, 'allocations': [], 'events': []}")
    sim=make(p);damage(sim)
    assert sim.ctx.resources.current('victim','hp')==650


def test_custom_pipeline_target_attribute_binding_consumed_at_hit():
    p=fixture()
    p['rules'][0]=rule('rule/model_no_source_fixed_pipeline',
        "{'accepted': True, 'amount': inputs.effect.maximum / 10, 'allocations': [], 'events': []}")
    p['rules'][0]['metadata']={'input_bindings':{'maximum':{'entity':'target','attribute_role':'max_hp'}}}
    sim=make(p);damage(sim)
    assert sim.ctx.resources.current('victim','hp')==900


@pytest.mark.parametrize('amount',[-1,float('nan'),True])
def test_invalid_fixed_amount_compile_and_runtime_atomic(amount):
    p=fixture();p['scenarioDraft']['scheduledEffects'][0]['effect']['fixed_amount']=amount
    with pytest.raises(ValueError):Compiler().compile(p)
    sim=make();before=values(sim)
    with pytest.raises(ValueError):damage(sim,fixed_amount=amount)
    assert values(sim)==before


def test_ordinary_none_and_actor_on_no_source_rejected_without_state_changes():
    sim=make();before=values(sim)
    with pytest.raises(ValueError):sim.ctx.effects.execute(None,['victim'],{'op':'damage'})
    with pytest.raises(ValueError):sim.ctx.effects.execute('victim',['victim'],request())
    assert values(sim)==before


def test_source_attribute_pipeline_binding_rejected_at_compile_and_new_fields_scoped():
    p=fixture();p['rules'][0]['metadata']={'input_bindings':{'attack':{'entity':'source','attribute_role':'attack'}}}
    with pytest.raises(ValueError,match='source'):Compiler().compile(p)
    p=fixture();p['scenarioDraft']['scheduledEffects'][0]['effect']={'op':'damage','fixed_amount':700}
    with pytest.raises(ValueError,match='explicit no_source'):Compiler().compile(p)


@pytest.mark.parametrize('change',[{'ignore_for_sp':0},{'attack_type':'NORMAL'},
    {'damage_without_modify':True},{'environmental':None},{'origin':{}},{'unknown':1},{'parameters':{'fixed_amount':700}}])
def test_unknown_or_unconsumed_source_flags_rejected(change):
    p=fixture();p['scenarioDraft']['scheduledEffects'][0]['effect'].update(change)
    with pytest.raises(ValueError):Compiler().compile(p)


def test_origin_is_opaque_json_not_rule_provider_or_expression_references():
    p=fixture();origin={'field_uid':'field/test','definition':'rule/model_no_source_fixed_pipeline',
        'condition':'native text not an expression','provider':'not/a/runtime/provider','rule':'unloaded/raw/rule'}
    p['scenarioDraft']['scheduledEffects'][0]['effect']['origin']=origin
    sim=make(p);damage(sim,origin=origin)
    assert events(sim,'damage.accepted')[-1]['payload']['origin']==origin


def hook_package(expression,hp=1000,resources=None):
    p=fixture(hp=hp,buffs=['buff/after'],resources=resources)
    p['rules'].append(rule('rule/after',expression))
    p['buffs']=[{'id':'buff/after','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/after'}]}]
    return p


def test_target_invulnerability_after_hook_and_custom_cap_remain():
    sim=make(hook_package("{'accepted': False, 'amount': 0, 'allocations': [], 'events': []}"))
    assert damage(sim)['actual_health_loss']==0 and sim.ctx.resources.current('victim','hp')==1000
    assert len(events(sim,'damage.rejected'))==1
    sim=make(hook_package("{'accepted': True, 'amount': min(inputs.effect.settlement.amount, 17), 'allocations': [], 'events': []}"))
    damage(sim);assert sim.ctx.resources.current('victim','hp')==983


def test_environment_projection_flag_and_original_node_flag_are_distinct():
    p=hook_package("{'accepted':inputs.effect.environmental and inputs.effect.env_blackboard_injected and not inputs.effect.node_is_env_damage,'amount':23,'allocations':[],'events':[]}")
    sim=make(p);damage(sim)
    assert sim.ctx.resources.current('victim','hp')==977
    sim=make(p);damage(sim,environmental=False)
    assert sim.ctx.resources.current('victim','hp')==1000
    sim=make(p);damage(sim,node_is_env_damage=True)
    assert sim.ctx.resources.current('victim','hp')==1000


def test_mixed_shield_and_custom_health_allocations_stats_exclude_shield():
    p=hook_package("{'accepted': True, 'amount': 700, 'allocations': [{'target':'target','resource':'shield','delta':-1},{'target':'target','resource':'vital','amount':700}], 'events': []}",hp=100,
        resources={'shield':{'initial':1,'capacity':1}})
    c=p['entities'][0]['components'];c['resources']['vital']=c['resources'].pop('hp')
    p['rules'].append({'id':'rule/vital_death','kind':'calculation_rule','contract':'lifecycle.death',
        'implementation':{'type':'provider','provider':'ark.lifecycle.standard'},'parameters':{'resource':'vital','threshold':0}})
    c['lifecycle']['rules']={'lifecycle.death':'rule/vital_death'}
    sim=make(p);damage(sim)
    assert sim.ctx.resources.current('victim','shield')==0 and sim.ctx.resources.current('victim','vital')==0
    accepted=events(sim,'damage.accepted')[-1]['payload']
    assert accepted['amount']==accepted['total_health_loss']==100
    assert [a['health_loss'] for a in accepted['allocations']]==[0,100]
    assert sim.ctx.state()['damage_dealt']==100 and sim.ctx.state()['kills']==1


def test_source_before_hooks_not_run_or_sampled_target_after_still_samples():
    p=hook_package("{'accepted': inputs.source == {} and context.source == {}, 'amount': 4, 'allocations': [], 'events': []}")
    p['rules'].append(rule('rule/before',"{'accepted':False,'effect':inputs.effect,'effects':[]}",'damage.request'))
    p['buffs'][0]['damage_hooks'].insert(0,{'phase':'before','rule':'rule/before','samples':{'stream':'source_crit','count':1}})
    p['buffs'][0]['damage_hooks'][1]['samples']={'stream':'target_after','count':1}
    sim=make(p);damage(sim)
    assert sim.ctx.resources.current('victim','hp')==996
    assert [s['stream'] for s in sim.session.random.samples]==['target_after']


def test_after_hook_failure_rolls_back_sample_rng_scheduler_world_events():
    p=hook_package("{'accepted':True,'amount':1/0,'allocations':[],'events':[]}")
    p['buffs'][0]['damage_hooks'][0]['samples']={'stream':'target_after','count':1}
    sim=make(p);before=values(sim)
    with pytest.raises(Exception):damage(sim)
    assert values(sim)==before


def test_lethal_policy_revive_is_not_forced_kill_and_origin_death_is_retained():
    p=fixture(hp=100)
    p['rules'].append({'id':'rule/revive','kind':'calculation_rule','contract':'lifecycle.death',
        'implementation':{'type':'provider','provider':'ark.lifecycle.standard'},
        'parameters':{'resource':'hp','threshold':0,'revive':True,'revive_value':25}})
    p['entities'][0]['components']['lifecycle']['rules']={'lifecycle.death':'rule/revive'}
    sim=make(p);damage(sim)
    assert sim.ctx.alive('victim') and sim.ctx.resources.current('victim','hp')==25
    assert sim.ctx.state()['kills']==0 and not events(sim,'combat.kill') and not events(sim,'entity.died')
    assert events(sim,'damage.accepted')[-1]['payload']['actual_health_loss']==100


def test_lifecycle_callback_exception_after_health_commit_rolls_back_all(monkeypatch):
    sim=make(fixture(hp=100));before=values(sim)
    def broken(ref,event):
        assert event['source'] is None and event['origin']['field_uid']=='field/test'
        sim.session.random.sample('death_callback')
        sim.session.schedule('domain.effect',{'source':None,'targets':[2],'effect':request()},99)
        sim.ctx.state_update(kills=17)
        sim.ctx.emit('death.callback_started',event)
        raise RuntimeError('death callback failure')
    monkeypatch.setattr(sim.ctx.lifecycle,'check',broken)
    with pytest.raises(RuntimeError):damage(sim)
    assert values(sim)==before


def test_real_death_aura_on_remove_exception_rolls_back_random_and_complete_state():
    p=fixture(hp=100,buffs=['buff/death_failure'])
    p['selectors']=[{'id':'selector/aura','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}]}]
    p['buffs']=[{'id':'buff/child','kind':'buff','stacking':{'mode':'independent'}}, {'id':'buff/death_failure','kind':'buff',
        'aura':{'selector':'selector/aura','buff':'buff/child'}, 'on_remove':[
        {'op':'random','stream':'death_callback','on_success':[
            {'op':'modify_resource','resource':'missing','delta':1}]}]}]
    sim=make(p);before=values(sim)
    with pytest.raises(ValueError):damage(sim)
    assert values(sim)==before


def test_actual_death_subscription_alive_observer_and_no_actor_kill_credit():
    p=fixture(hp=100)
    p['entities'].append({'id':'unit/observer','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'max_hp':100,'atk':0,'def':0}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'},'sp':{'initial':0,'capacity':5,
            'recovery_rule':'rule/sp','recovery':{'mode':'event','event':'combat.kill','owner_role':'source','amount':1}}},
        'spatial':{},'abilities':['ability/death_watch'],'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['rules'].append({'id':'rule/sp','kind':'calculation_rule','contract':'resource.recovery',
        'implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
    p['abilities']=[{'id':'ability/death_watch','kind':'ability','activation':{'mode':'manual'},'timeline':[],
        'events':[{'event':'entity.died','condition':"inputs.payload.source == None and inputs.payload.origin.field_uid == 'field/test'",
        'effects':[{'op':'emit','event':'death.talent_observed'}]}]}]
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/observer','instanceAlias':'observer','position':{'row':2,'col':2}})
    sim=make(p);damage(sim);sim.session.advance(1)
    assert len(events(sim,'death.talent_observed'))==1
    assert sim.ctx.resources.current('observer','sp')==0
    cause=events(sim,'death.talent_observed')[0]['cause']
    assert next(e for e in sim.session.events if e['id']==cause)['type']=='entity.died'


def test_positive_health_allocation_is_not_counted_as_damage():
    p=hook_package("{'accepted':True,'amount':700,'allocations':[{'target':'target','resource':'hp','delta':10}],'events':[]}")
    sim=make(p);sim.ctx.resources.adjust('victim','hp',value=500)
    damage(sim)
    assert sim.ctx.resources.current('victim','hp')==510
    assert sim.ctx.state()['damage_dealt']==0
    assert events(sim,'damage.accepted')[-1]['payload']['actual_health_loss']==0


@pytest.mark.parametrize('allocation',[{'target':'target','amount':-1},{'target':'target','amount':True},
    {'target':'target','delta':1,'amount':2},{'target':'target','delta':-1,'unknown':True}])
def test_bad_allocation_rejected_without_partial_commits(allocation):
    p=hook_package("{'accepted':True,'amount':700,'allocations':"+repr([allocation])+",'events':[]}")
    sim=make(p);before=values(sim)
    with pytest.raises(ValueError):damage(sim)
    assert values(sim)==before


def test_source_allocation_fails_and_mixed_plan_last_invalid_resource_rolls_back():
    for expression in [
        "{'accepted':True,'amount':700,'allocations':[{'target':'source','amount':700}],'events':[]}",
        "{'accepted':True,'amount':700,'allocations':[{'target':'target','resource':'hp','amount':10},{'target':'target','resource':'absent','amount':10}],'events':[]}"]:
        sim=make(hook_package(expression));before=values(sim)
        with pytest.raises(ValueError):damage(sim)
        assert values(sim)==before


def test_typed_flag9_availability_none_source_side2_and_immunity():
    p=fixture()
    p['rules'].append({'id':'rule/available','kind':'calculation_rule','contract':'targeting.availability',
        'implementation':{'type':'expression','expression':"inputs.source == {} and context.source == {} and inputs.selection_states.source.side == 2 and 9 not in inputs.selection_states.candidate.abnormal_flags"}})
    p['entities'][0]['rules']={'targeting.availability':'rule/available'}
    p['entities'][0]['components']['selection_state']={'abnormal_flags':[9]}
    sim=make(p)
    assert sim.ctx.spatial.available(None,2,observable=True) is False
    assert damage(sim)['results']==[] and sim.ctx.resources.current('victim','hp')==1000
    sim.ctx.set(2,('selection_state',),{'abnormal_flags':[9],'abnormal_immunes':[9]})
    assert sim.ctx.spatial.available(None,2,observable=False) is True
    damage(sim);assert sim.ctx.resources.current('victim','hp')==300


@pytest.mark.parametrize('ignore,freeze,expected',[(False,False,1),(True,False,0),(False,True,0)])
def test_target_event_sp_and_emission_time_freeze(ignore,freeze,expected):
    p=fixture(resources={'sp':{'initial':0,'capacity':10,'recovery_rule':'rule/sp',
        'recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1},
        'parameters':{'freeze_while_cast':True}}})
    p['rules'].append({'id':'rule/sp','kind':'calculation_rule','contract':'resource.recovery',
        'implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
    sim=make(p)
    if freeze:sim.ctx.set(2,('runtime','casts'),{'holding':{'activation_mode':'manual'}})
    damage(sim,ignore_for_sp=ignore)
    sim.ctx.set(2,('runtime','casts'),{}) # Unfreeze before queued reaction is consumed.
    sim.session.advance(1)
    assert sim.ctx.resources.current('victim','sp')==expected


def test_finished_by_first_packet_skips_next_target_and_no_additional_samples(monkeypatch):
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/victim','instanceAlias':'second','position':{'row':2,'col':2}})
    sim=make(p)
    original=sim.ctx.lifecycle.check
    def finish(ref,event):
        original(ref,event)
        sim.ctx.state_update(finished=True)
    monkeypatch.setattr(sim.ctx.lifecycle,'check',finish)
    result=damage(sim,targets=('victim','second'))
    assert len(result['results'])==1 and result['finished']
    assert sim.ctx.resources.current('second','hp')==1000


def test_public_scheduled_no_source_checkpoint_file_reload_and_replay(tmp_path):
    p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':3,'effect':request(target=2)}]
    program=Compiler().compile(p);sim=Engine.create(program,seed=17)
    sim.session.advance(2)
    path=tmp_path/'ordered-cp.json';pin=write_ordered(path,sim.checkpoint())
    restored=Engine.restore(program,load_bound(path,pin))
    sim.session.advance(5);restored.session.advance(5)
    assert sim.snapshot()==restored.snapshot() and sim.checkpoint()==restored.checkpoint()
    repeated=replay(program,sim.export_replay())
    assert sim.snapshot()==repeated.snapshot() and sim.checkpoint()==repeated.checkpoint()
    assert events(sim,'damage.accepted')[-1]['payload']['source'] is None
