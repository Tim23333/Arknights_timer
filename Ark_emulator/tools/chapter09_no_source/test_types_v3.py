"""Actual None-source ARTS/PHYSICAL formulas, NORMAL SP and atomic failures."""
import json
from pathlib import Path
from copy import deepcopy

import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def effect(kind='arts',ignore=False,bypass=False):
    return {'op':'no_source_damage','target':2,'fixed_amount':1200,'damage_type':kind,'attack_type':'NORMAL',
            'damage_without_modify':bypass,'ignore_for_sp':ignore,'node_is_env_damage':False,
            'env_blackboard_injected':False,'environmental':False,'origin':{'reference':'C9/FIRE/break'},
            'rules':{'damage.pipeline':'rule/test/none/'+kind}}


def package(kind='arts',ignore=False,bypass=False):
    expression="{'accepted':True,'amount':inputs.effect.fixed_amount*(1-min(100,max(0,inputs.effect.resistance))/100),'allocations':[],'events':[]}"
    if kind=='physical':expression="{'accepted':True,'amount':max(inputs.effect.fixed_amount-inputs.effect.defense,inputs.effect.fixed_amount*.05),'allocations':[],'events':[]}"
    bindings={'resistance':{'entity':'target','attribute':'mres'}} if kind=='arts' else {'defense':{'entity':'target','attribute':'def'}}
    return {'schemaVersion':2,'manifest':{'id':'package/test/no_source_types','requires':['preset/ark_standard']},
       'rules':[{'id':'rule/test/none/'+kind,'kind':'rule','contract':'damage.pipeline',
                 'implementation':{'type':'graph','nodes':[{'id':'result','expression':expression}],'output':'nodes.result'},'metadata':{'input_bindings':bindings}},
                {'id':'rule/test/sp','kind':'rule','contract':'resource.recovery',
                 'implementation':{'type':'expression','expression':'inputs.current+inputs.parameters.amount'}}],
       'buffs':[{'id':'buff/test/res_minus20','kind':'buff','duration_seconds':10,
                 'modifiers':[{'attribute':'mres','layer':'flat','value':-20}]}],
       'entities':[{'id':'unit/test/victim','kind':'entity','tags':['player'],
          'components':{'attributes':{'base':{'max_hp':4000,'atk':0,'def':700,'mres':30}},
             'resources':{'hp':{'initial':4000,'capacity':4000,'role':'health'},
                          'sp':{'initial':0,'capacity':20,'recovery_rule':'rule/test/sp',
                                'recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},
             'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},
             'spatial':{},'buffs':{'initial':['buff/test/res_minus20']},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],
       'scenarioDraft':{'id':'scene/test/no_source_types','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},
          'initialEntities':[{'definition':'unit/test/victim','instanceAlias':'victim','position':{'row':0,'col':0}}],
          'scheduledEffects':[{'at':3,'effect':effect(kind,ignore,bypass)}]}}


@pytest.mark.parametrize('kind,ignore,bypass,damage,sp',[
    ('arts',False,False,1080,1),('arts',True,False,1080,0),
    ('arts',False,True,1200,1),('physical',False,False,500,1)])
def test_actual_none_source_current_RES10_or_DEF700_damage_and_SP_CP_head(kind,ignore,bypass,damage,sp,tmp_path):
    program=Compiler().compile(package(kind,ignore,bypass));sim=Engine.create(program,seed=931)
    sim.session.advance(2);path=tmp_path/'before_packet.checkpoint.json';pin=write_ordered(path,sim.checkpoint())
    restored=Engine.restore(program,load_bound(path,pin));sim.session.advance(8);restored.session.advance(8)
    head=replay(program,sim.export_replay());assert sim.checkpoint()==restored.checkpoint()==head.checkpoint()
    hit=next(event['payload'] for event in sim.session.events if event['type']=='damage.accepted')
    assert hit['source'] is None and hit['source_policy']=='none' and hit['attack_type']=='NORMAL'
    assert hit['amount']==damage and sim.ctx.resources.current('victim','hp')==4000-damage
    assert sim.ctx.resources.current('victim','sp')==sp
    assert not [event for event in sim.session.events if event['type']=='attack.accepted']
    assert hit['origin']['reference']=='C9/FIRE/break'


def test_custom_formula_entirely_replaceable_and_target_hook_failure_rolls_back():
    p=package();p['scenarioDraft']['scheduledEffects'][0]['at']=9999
    p['rules'][0]['implementation']['nodes'][0]['expression']="{'accepted':True,'amount':inputs.effect.fixed_amount*.125,'allocations':[],'events':[]}"
    s=Engine.create(Compiler().compile(p));s.ctx.effects.execute(None,['victim'],effect());assert s.ctx.resources.current('victim','hp')==3850
    bad=deepcopy(p);bad['rules'][0]['implementation']['nodes'][0]['expression']="{'accepted':True,'amount':100,'allocations':[{'resource':'hp','amount':10},{'resource':'missing','amount':20}],'events':[]}"
    s=Engine.create(Compiler().compile(bad));before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.effects.execute(None,['victim'],effect())
    assert s.checkpoint()==before


@pytest.mark.parametrize('change',[{'damage_type':True},{'damage_type':'unknown'},{'attack_type':False},{'attack_type':'SKILL'}])
def test_unsupported_or_untyped_request_is_rejected_before_any_write(change):
    p=package();p['scenarioDraft']['scheduledEffects'][0]['at']=9999;s=Engine.create(Compiler().compile(p));before=s.checkpoint();request=effect();request.update(change)
    with pytest.raises(ValueError):s.ctx.effects.execute(None,['victim'],request)
    assert s.checkpoint()==before
