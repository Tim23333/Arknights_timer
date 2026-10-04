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
