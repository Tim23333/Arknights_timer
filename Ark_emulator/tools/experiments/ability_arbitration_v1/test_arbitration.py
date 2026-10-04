from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay


def fixture(order='higher_first'):
    abilities=[]
    for name in ('low','high','fallback'):
        abilities.append({'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual'},
            'cooldown_seconds':1,'timeline':[{'at':3,'effect':{'op':'emit','event':'probe.'+name}}]})
    ids=[a['id'] for a in abilities]
    spec={'priority_order':order,'busy':'all_casts','entries':[
        {'ability':aid,'priority':priority,'attack_clock':True,'require_attack_control':True,
         'condition':'True','parameters':{}} for aid,priority in zip(ids,[0,2,1])]}
    unit={'id':'unit/source','kind':'entity','components':{
        'abilities':ids,'ability_arbitration':spec,
        'attributes':{'base':{'max_hp':100,'attack_interval':1,'attack_speed_ratio':1}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}}}}
    return {'definitions':[unit,*abilities],'scenarioDraft':{'id':'scene/arbitrate',
        'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':1},
        'initialEntities':[{'definition':'unit/source','instanceAlias':'source'}]}}


def create(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=884)
def starts(s):return [(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started']


@pytest.mark.parametrize('order,first',[('higher_first','ability/high'),('lower_first','ability/low')])
def test_priority_is_explicit_and_not_ability_array_order(order,first):
    s=create(fixture(order));s.advance(1)
    assert starts(s)==[(0,first)]
    assert s.ctx.get('source',('runtime','next_attack'))==30
    assert len([e for e in s.session.events if e['type']=='ability.arbitrated'])==1


def test_unaffordable_high_skill_rolls_back_then_fallback_is_actual_cast():
    p=fixture();p['definitions'][2]['activation']['costs']=[{'resource':'hp','amount':101}]
    s=create(p);s.advance(4)
    assert starts(s)==[(0,'ability/fallback')]
    assert s.ctx.resources.current('source','hp')==100
    assert [e['type'] for e in s.session.events if e['type'].startswith('probe.')]==['probe.fallback']


def test_attack_clock_busy_gate_cp_and_replay_use_real_state():
    s=create();s.advance(2);r=Engine.restore(s.program,s.checkpoint())
    s.advance(99);r.advance(99)
    assert s.checkpoint()==r.checkpoint()
    assert starts(s)==[(0,'ability/high'),(30,'ability/fallback'),(60,'ability/high'),(90,'ability/fallback')]
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_non_attack_skill_has_independent_clock_and_attack_clock_not_changed():
    p=fixture();p['definitions'][0]['components']['ability_arbitration']['entries'][1]['attack_clock']=False
    p['definitions'][0]['components']['ability_arbitration']['entries'][1]['require_attack_control']=False
    s=create(p);s.ctx.set('source',('runtime','next_attack'),1000);s.advance(4)
    assert starts(s)==[(0,'ability/high')]
    assert s.ctx.get('source',('runtime','next_attack'))==1000


def test_rejected_or_invalid_post_cast_clock_rolls_back_all_domains():
    p=fixture();p['rules']=[{'id':'rule/zero_interval','kind':'rule','contract':'time.interval',
        'implementation':{'type':'expression','expression':'0'}}]
    p['scenarioDraft']['rules']={'time.interval':'rule/zero_interval'}
    s=create(p);before=s.checkpoint()
    from ark_sim.domains.ability_arbitration import tick
    with pytest.raises(ValueError,match='must advance'):tick(s.ctx.abilities,s.session.world.resolve('source'))
    assert s.checkpoint()==before


@pytest.mark.parametrize('bad',[True,-1,'high',None])
def test_strict_priority_type_and_all_possessed_abilities_required(bad):
    p=fixture();p['definitions'][0]['components']['ability_arbitration']['entries'][1]['priority']=bad
    if bad==-1 and type(bad) is int:
        # Negative priorities are valid integers; omission is the negative case.
        p['definitions'][0]['components']['ability_arbitration']['entries'].pop()
    with pytest.raises(ValueError):Compiler().compile(p)


def test_bad_effective_override_rejected_without_partial_creation():
    s=create();before=s.checkpoint();spec=deepcopy(fixture()['definitions'][0]['components']['ability_arbitration'])
    spec['entries'][1]['condition']='1'
    # Invalid runtime output is detected before any successful activation.
    ref=s.ctx.lifecycle.create('unit/source',alias='override',component_overrides={'ability_arbitration':spec})
    from ark_sim.domains.ability_arbitration import tick
    cp=s.checkpoint()
    with pytest.raises(ValueError,match='strict boolean'):tick(s.ctx.abilities,ref)
    assert s.checkpoint()==cp
    bad=deepcopy(spec);bad['entries'][0]['ability']='ability/unowned'
    before=s.checkpoint()
    with pytest.raises(ValueError,match='possessed'):s.ctx.lifecycle.create('unit/source',component_overrides={'ability_arbitration':bad})
    assert s.checkpoint()==before


def test_busy_long_cast_suppresses_new_skills_until_actual_finish():
    p=fixture();p['definitions'][2]['timeline'][0]['at']=60
    s=create(p);s.advance(61)
    assert starts(s)==[(0,'ability/high')]
    assert any(e['type']=='probe.high' and e['time']==60 for e in s.session.events)
    s.advance(1)
    assert starts(s)[-1]==(61,'ability/fallback')


def test_targetless_high_rejection_does_not_starve_valid_lower_skill():
    p=fixture();p['definitions'][2]['selector']='selector/empty';p['definitions'][2]['activation']['parameters']={'requires_targets':True}
    p['definitions'].append({'id':'selector/empty','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'not-present'}],'ordering':[],'limit':1})
    s=create(p);s.advance(1)
    assert starts(s)==[(0,'ability/fallback')]


def test_tied_priorities_use_declared_entry_order_and_false_condition_skips():
    p=fixture();rows=p['definitions'][0]['components']['ability_arbitration']['entries']
    rows[1]['priority']=rows[2]['priority']=3;rows[1]['condition']='False'
    s=create(p);s.advance(1);assert starts(s)==[(0,'ability/fallback')]


def test_public_started_reaction_retire_retains_accepted_clock_and_cancels_tasks():
    p=fixture()
    for ability in p['definitions'][1:]:
        ability['events']=[{'event':'ability.started','condition':'inputs.payload.source == 2',
            'effects':[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]}]
    s=create(p);s.advance(1)
    assert not s.ctx.active('source') and s.ctx.get('source',('runtime','casts'))=={}
    # event_reaction is explicitly scheduled after accepted activation. Its
    # retirement cancels the cast but cannot erase the already committed clock.
    assert s.ctx.get('source',('runtime','next_attack'))==30
    assert len(starts(s))==1
    assert not any(t['kind'].startswith('domain.ability.') for t in s.session.scheduler.pending)
    s.advance(40)
    assert len(starts(s))==1 and not any(e['type']=='probe.high' for e in s.session.events)


def test_invalid_dormant_override_fails_at_create_and_compile():
    bad=deepcopy(fixture()['definitions'][0]['components']['ability_arbitration'])
    bad['entries'][0]['ability']='ability/unowned'
    s=create();before=s.checkpoint()
    with pytest.raises(ValueError,match='possessed'):
        s.ctx.lifecycle.create('unit/source',active=False,registration_key='bad',component_overrides={'ability_arbitration':bad})
    assert s.checkpoint()==before
    p=fixture();p['scenarioDraft']['initialEntities'][0]['components']={'ability_arbitration':bad}
    p['definitions'].append({'id':'ability/unowned','kind':'ability','activation':{'mode':'manual'},'timeline':[]})
    with pytest.raises(ValueError,match='possessed'):Compiler().compile(p)
