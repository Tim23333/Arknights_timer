"""Reactivation placement/fault/registry identity and finite actor generations."""
import pytest
from tools.chapter08_predefined_reactivation.test_generic_v1 import package
from ark_sim import Compiler,Engine

def test_newincarnation_callback_failure_rolls_back_registry_budget_world_events():
    p=package();p['entities'][0]['components']['behavior']={'machine':'behavior/device'};p['entities'][0]['components']['resources']['marker']={'initial':0,'capacity':1}
    p['behaviors']=[{'id':'behavior/device','kind':'behavior','initial':'ready','states':{'ready':{'on_enter':[{'op':'modify_resource','target':'self','resource':'marker','value':1}]}},'transitions':[]}]
    s=Engine.create(Compiler().compile(p));old=s.ctx.lifecycle.activate_predefined('device1');s.ctx.lifecycle.retire(old,'withdrawn')
    # Actualcallback uses a source-local resource rule chosen at compilation;
    # mutate capturedstate is not needed for fault: Worldclock drives rule.
    # Separate program below faults only secondactivation when time>=3.
    p['rules']=[{'id':'rule/faultbounds','kind':'rule','contract':'resource.bounds','implementation':{'type':'provider','provider':'test.reuse.bounds'}}]
    p['entities'][0]['components']['resources']['marker']['bounds_rule']='rule/faultbounds'
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    def bound(inputs,params,context):
        if context['time']>=3:raise ValueError('lateboundsfault')
        return {'accepted':True,'value':inputs['candidate'],'overflow':0}
    reg={**BUILTIN_PROVIDERS,'test.reuse.bounds':{'callable':bound,'version':'1'}}
    s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);old=s.ctx.lifecycle.activate_predefined('device1');s.ctx.lifecycle.retire(old,'withdrawn');s.advance(3);before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.lifecycle.activate_predefined('device1')
    assert s.checkpoint()==before

def test_reuse_denied_for_unlisted_retirement_reason():
    s=Engine.create(Compiler().compile(package()));old=s.ctx.lifecycle.activate_predefined('device1');s.ctx.lifecycle.retire(old,'dead');before=s.checkpoint()
    with pytest.raises(ValueError,match='retirement reason'):s.ctx.lifecycle.activate_predefined('device1')
    assert s.checkpoint()==before

def test_instance_alias_not_rebound_for_repeatable_registration():
    p=package();p['scenarioDraft']['initialEntities'][0]['instanceAlias']='device_alias'
    with pytest.raises(ValueError,match='instancealias'):Compiler().compile(p)

def test_foreignregistry_current_mapping_rejects_before_actor_creation():
    s=Engine.create(Compiler().compile(package()));s.ctx.lifecycle.activate_predefined('device1');registry=s.ctx.state()['predefined_registry'];registry['device1']=s.session.world.resolve('director');s.ctx.state_update(predefined_registry=registry);before=s.checkpoint()
    with pytest.raises(ValueError,match='registry differs'):s.ctx.lifecycle.activate_predefined('device1')
    assert s.checkpoint()==before
