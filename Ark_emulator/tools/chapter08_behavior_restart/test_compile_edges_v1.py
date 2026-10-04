"""Actor-known restart closure errors and callback retirement boundaries."""
import pytest
from tools.chapter08_behavior_restart.test_restart_v1 import package,effect
from ark_sim import Compiler,Engine


def test_known_actor_self_restart_state_missing_rejected_compile():
    p=package();p['scenarioDraft']['scheduledEffects']=[];e=effect();e['state']='absent'
    p['behaviors'][0]['states']['normal']['on_exit']=[e]
    with pytest.raises(ValueError,match='state is absent'):Compiler().compile(p)


def test_known_actor_self_foreign_ability_is_not_admitted():
    p=package();p['scenarioDraft']['scheduledEffects']=[]
    p['abilities'].append({'id':'ability/foreign','kind':'ability','activation':{'mode':'manual'},'timeline':[]})
    e=effect();e['parameters']['abilities'].append('ability/foreign');p['abilities'][0]['activation']['on_start']=[e]
    with pytest.raises(ValueError,match='unpossessed'):Compiler().compile(p)


def test_on_enter_retire_stops_next_resource_effect_and_clock_writes():
    p=package();p['scenarioDraft']['scheduledEffects']=[];p['behaviors'][0]['states']['half']['on_enter']=[
        {'op':'retire','target':'self','parameters':{'reason':'withdrawn'}},
        {'op':'modify_resource','target':'self','resource':'mode','value':1}]
    s=Engine.create(Compiler().compile(p));s.ctx.effects.execute('boss',['boss'],effect())
    assert not s.ctx.active('boss') and s.ctx.resources.current('boss','mode')==0
    assert s.ctx.get('boss',('runtime','cooldowns'),{}).get('ability/new') is None
    assert not s.ctx.behavior._restart_busy


def test_reset_flag_false_keeps_actor_shared_clock_while_replacing_only_declared_clocks():
    p=package();p['scenarioDraft']['scheduledEffects']=[];s=Engine.create(Compiler().compile(p))
    s.ctx.set('boss',('runtime','next_attack'),87);s.ctx.set('boss',('runtime','cooldowns'),{'ability/old':99})
    e=effect();e['parameters']['reset_attack_clock']=False;s.ctx.effects.execute('boss',['boss'],e)
    assert s.ctx.get('boss',('runtime','next_attack'))==87
    assert s.ctx.get('boss',('runtime','cooldowns'))=={'ability/old':99,'ability/new':30}


def test_ability_can_restart_its_own_cast_without_dependency_cycle():
    p=package();p['scenarioDraft']['scheduledEffects']=[];p['abilities'][0]['activation']['on_start']=[effect()]
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'boss','ability':'ability/old'},at=0);s.advance(25)
    assert not s.ctx.get('boss',('runtime','casts'))
    assert not [e for e in s.session.events if e['type']=='damage.accepted']
    assert s.ctx.get('boss',('behavior','state'))=='half'
    assert [e['time'] for e in s.session.events if e['type']=='behavior.restarted']==[0]
