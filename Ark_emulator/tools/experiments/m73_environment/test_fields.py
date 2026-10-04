import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]


def fixture(initial=None,two=False):
    profile={'type':'periodic_effect_field','expected_blackboard':{'low':1.0,'high':1.0},'origin':{'kind':'environment'},'effects':[],
      'trigger':{'rule':'rule/clock','stream':'field','sample_count':1,'parameters':{},'initial':initial or {'mode':'sampled'}},
      'membership':{'rule':'rule/members','parameters':{}}}
    return {'manifest':{'requires':['preset/ark_standard']},'rules':[
        {'id':'rule/clock','kind':'rule','contract':'field.trigger','parameters':{'minimum_key':'low','maximum_key':'high'},'implementation':{'type':'provider','provider':'model.field.uniform_trigger'}},
        {'id':'rule/members','kind':'rule','contract':'field.members','implementation':{'type':'expression','expression':'[]'}}],
      'scenarioDraft':{'id':'scene/fieldclock','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':1,'cols':2 if two else 1,'tiles':[{'tileKey':'custom_field','passableMask':3,'buildableType':1,'blackboard':{'low':1.0,'high':1.0}} for _ in range(2 if two else 1)],'tile_mechanics':{'custom_field':profile}}}}


def make(p):
    INPUTS.append(p);return Engine.create(Compiler().compile(p),seed=62053)


def test_actual_first_sample_and_periodic_tasks_single_field_orderedCP_replay(tmp_path):
    s=make(fixture());assert s.ctx.periodic_fields.current('field/1')['due']==30
    s.advance(17);cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(75);r.advance(75)
    events=[e for e in s.session.events if e['type']=='field.triggered'];assert [e['time'] for e in events]==[30,60,90]
    assert [e['payload']['sequence'] for e in events]==[0,1,2]
    assert s.ctx.periodic_fields.current('field/1')['sequence']==3
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_two_cells_have_independent_state_and_stable_row_major_order(tmp_path):
    s=make(fixture(two=True));s.advance(5);cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(57);r.advance(57)
    events=[e for e in s.session.events if e['type']=='field.triggered']
    assert [(e['time'],e['payload']['field_uid']) for e in events]==[(30,'field/1'),(30,'field/2'),(60,'field/1'),(60,'field/2')]
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_fixed_initial_zero_does_not_draw_before_first_packet():
    s=make(fixture({'mode':'fixed','seconds':0}));assert not [e for e in s.session.events if e['type'].startswith('random.')]
    s.advance(1);assert [e['time'] for e in s.session.events if e['type']=='field.triggered']==[0]
    assert s.ctx.periodic_fields.current('field/1')['due']==30


def test_remove_cancels_generation_and_no_more_draws():
    s=make(fixture());s.advance(10);s.ctx.periodic_fields.remove('field/1');before=s.session.random.snapshot();s.advance(100)
    assert not [e for e in s.session.events if e['type']=='field.triggered'] and s.session.random.snapshot()==before
    assert not s.ctx.periodic_fields.current('field/1')['active']


def test_terminal_cancels_tasks_without_future_samples():
    s=make(fixture(two=True));before=s.session.random.snapshot();s.ctx.state_update(finished=True);s.advance(60)
    assert not [e for e in s.session.events if e['type']=='field.triggered'] and s.session.random.snapshot()==before
    assert all(not f['active'] for f in s.ctx.periodic_fields.state()['fields'].values())


def test_explicit_custom_clock_changes_delay_and_disabled_stops_after_one():
    p=fixture({'mode':'fixed','seconds':0});p['rules'][0]['implementation']={'type':'expression','expression':"{'enabled':False,'next_delay_seconds':None}"};p['scenarioDraft']['map']['tile_mechanics']['custom_field']['trigger']['sample_count']=0
    s=make(p);s.advance(100);assert [e['time'] for e in s.session.events if e['type']=='field.triggered']==[0]
    assert not s.ctx.periodic_fields.current('field/1')['active']


@pytest.mark.parametrize('patch',[lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_field']['trigger'].update(sample_count=True),
    lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_field']['origin'].update(field_uid='forged'),
    lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_field']['trigger'].update(initial={'mode':'guess'}),
    lambda p:p['scenarioDraft']['map']['tiles'][0]['blackboard'].update(high=2.0),
    lambda p:p['rules'][0].update(contract='field.members')])
def test_invalid_schema_board_or_wrong_contract_compile_rejected(patch):
    p=fixture();patch(p)
    with pytest.raises(ValueError):Compiler().compile(p)


@pytest.mark.parametrize('expr',["{'enabled':True,'next_delay_seconds':0}","{'enabled':1,'next_delay_seconds':1}","{'enabled':True,'next_delay_seconds':1/0}","{'enabled':False,'next_delay_seconds':0}"])
def test_true_trigger_failure_restores_samples_tasks_log_counter_and_world(expr):
    p=fixture({'mode':'fixed','seconds':0});p['rules'][0]['implementation']={'type':'expression','expression':expr};s=make(p)
    before=s.checkpoint();payload={'uid':'field/1','generation':1}
    with pytest.raises(Exception):s.ctx.periodic_fields.pulse(s.session,payload)
    assert s.checkpoint()==before


def test_uniform_interval_consumes_supplied_value_and_exact_source_bounds():
    from ark_sim.domains.periodic_fields import uniform_trigger
    result=uniform_trigger({'blackboard':{'minimum':13.0,'maximum':19.0},'samples':[{'value':.25}],'parameters':{}},
        {'minimum_key':'minimum','maximum_key':'maximum'},{})
    assert result=={'enabled':True,'next_delay_seconds':14.5}


def test_membership_own_cell_and_declared_extra_combat_policies_are_distinct():
    from ark_sim.domains.periodic_fields import cell_combat_members
    from ark_sim.domains.selection import DEFAULT_STATE
    actors=[{'id':i,'components':{'spatial':{'position':pos}}} for i,pos in [(1,{'row':2,'col':2}),(2,{'row':2,'col':3}),(3,{'row':2,'col':3}),(4,{'row':2,'col':3}),(5,{'row':2,'col':2})]]
    states={str(i):dict(DEFAULT_STATE) for i in range(1,6)}
    for state in states.values():state.update(side=0,motion=1,category=1)
    for i in (2,3,4):states[str(i)]['side']=1
    states['5']['motion']=2
    combat={'1':{'blocked_by':None,'attacking':False},'2':{'blocked_by':91,'attacking':False},'3':{'blocked_by':None,'attacking':True},'4':{'blocked_by':None,'attacking':False},'5':{'blocked_by':None,'attacking':False}}
    inputs={'field':{'cell':{'row':2,'col':2}},'candidates':actors,'selection_states':states,'combat_states':combat,'parameters':{}}
    options={'side_mask':3,'motion_mask':1,'category_mask':1,'extra_offsets':[[0,1]],'combat_policy':'blocked','exclude_flags':[9,17],'respect_target_free':True}
    assert cell_combat_members(inputs,options,{})==[1,2]
    options['combat_policy']='attacking';assert cell_combat_members(inputs,options,{})==[1,3]
    options['combat_policy']='blocked_or_attacking';assert cell_combat_members(inputs,options,{})==[1,2,3]
    states['2']['target_free']=True;states['3']['abnormal_flags']=[9]
    assert cell_combat_members(inputs,options,{})==[1]


def damaging_fixture(hp=2000):
    p=fixture({'mode':'fixed','seconds':.1})
    p['rules'][1]={'id':'rule/members','kind':'rule','contract':'field.members',
       'parameters':{'side_mask':3,'motion_mask':1,'category_mask':1,'extra_offsets':[[0,1]],'combat_policy':'blocked_or_attacking','exclude_flags':[9,17],'respect_target_free':True},
       'implementation':{'type':'provider','provider':'model.field.cell_combat_members'}}
    p['rules'].append({'id':'rule/fixed','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph',
        'nodes':[{'id':'settle','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],
        'output':'nodes.settle'}})
    p['entities']=[{'id':'unit/victim','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},
        'attributes':{'base':{'max_hp':hp,'atk':0,'def':999,'mres':90}},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/victim','instanceAlias':'victim','position':{'row':0,'col':0}}]
    profile=p['scenarioDraft']['map']['tile_mechanics']['custom_field']
    profile['effects']=[{'op':'no_source_damage','fixed_amount':700.0,'damage_type':'true','attack_type':'NONE','damage_without_modify':False,
        'ignore_for_sp':False,'node_is_env_damage':False,'env_blackboard_injected':True,'environmental':True,'origin':{'kind':'CastTile'},'rules':{'damage.pipeline':'rule/fixed'}}]
    return p


def test_actual_source_free_700_ignores_def_res_and_preserves_origin_saved_replay(tmp_path):
    s=make(damaging_fixture());s.advance(2);cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(34);r.advance(34)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in hits]==[(3,700.0),(33,700.0)]
    assert s.ctx.resources.current('victim','hp')==600
    assert all(e['payload']['source'] is None and e['payload']['origin']['field_uid']=='field/1' for e in hits)
    assert [e['payload']['origin']['trigger_sequence'] for e in hits]==[0,1]
    assert not [e for e in s.session.events if e['type']=='attack.accepted']
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_lethal_pipeline700_actual100_and_no_virtual_source_actor():
    s=make(damaging_fixture(100));s.advance(5);hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(hits)==1 and hits[0]['payload']['pipeline_amount']==700.0 and hits[0]['payload']['amount']==100
    assert not s.ctx.alive('victim')
    assert len(s.session.world.entities())==2
    deaths=[e for e in s.session.events if e['type']=='entity.died'];assert len(deaths)==1 and deaths[0]['payload']['source'] is None


def test_field_origin_opaque_rule_condition_strings_are_data_not_code():
    p=damaging_fixture();p['scenarioDraft']['map']['tile_mechanics']['custom_field']['origin']={'condition':'not valid expression [','provider':'absent raw marker','rule':'not_a_dependency'}
    s=make(p);s.advance(5);hit=next(e for e in s.session.events if e['type']=='damage.accepted')
    assert hit['payload']['origin']['condition']=='not valid expression ['


def test_bad_request_and_source_attribute_pipeline_are_compile_rejected():
    p=damaging_fixture();p['scenarioDraft']['map']['tile_mechanics']['custom_field']['effects'][0]['fixed_amount']=True
    with pytest.raises(ValueError):Compiler().compile(p)
    p=damaging_fixture();p['rules'][2]['metadata']={'input_bindings':{'attack':{'entity':'source','attribute':'atk'}}}
    with pytest.raises(ValueError):Compiler().compile(p)
