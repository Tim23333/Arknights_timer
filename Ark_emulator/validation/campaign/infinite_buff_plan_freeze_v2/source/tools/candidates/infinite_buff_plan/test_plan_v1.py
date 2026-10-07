"""Explicit infinity contracts, full-plan validation and no partial world writes."""
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.buff_application import validate_plan
from ark_sim.contracts import thaw
def plan(op):return {'accepted':True,'operations':[op]}
@pytest.mark.parametrize('duration',[True,False,-1,float('nan'),float('inf'),'infinite'])
def test_finite_duration_remains_strict(duration):
 with pytest.raises(ValueError):validate_plan(plan({'kind':'apply','buff':'buff/permanent','duration_seconds':duration}),['buff/permanent'],2,[],{'buff/permanent':{'id':'buff/permanent','kind':'buff'}})
@pytest.mark.parametrize('definition',[{'kind':'buff','duration_seconds':0},{'kind':'buff','duration_seconds':3},{'kind':'buff','duration_rule':'rule/x'},{'kind':'buff','parameters':{'duration_seconds':True}},{'kind':'buff','parameters':{'duration_seconds':None}},{'kind':'buff','parameters':{'duration_seconds':1}},{'kind':'entity'}])
def test_explicit_null_requires_truly_permanent_definition(definition):
 with pytest.raises(ValueError):validate_plan(plan({'kind':'apply','buff':'buff/permanent','duration_seconds':None}),['buff/permanent'],2,[],{'buff/permanent':definition})
def test_missing_key_not_permanent_default():
 with pytest.raises(ValueError):validate_plan(plan({'kind':'apply','buff':'buff/permanent'}),['buff/permanent'],2,[],{'buff/permanent':{'kind':'buff'}})
@pytest.mark.parametrize('definition',[{'kind':'buff'},{'kind':'buff','parameters':{'duration_seconds':0}},{'kind':'buff','parameters':{'duration_seconds':0.0}}])
def test_explicit_permanent_variants_accept(definition):validate_plan(plan({'kind':'apply','buff':'buff/permanent','duration_seconds':None}),['buff/permanent'],2,[],{'buff/permanent':definition})
def test_full_plan_late_illegal_infinite_rejects_before_any_apply_events_rng():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 def provider(inputs,params,context):return {'accepted':True,'operations':[{'kind':'apply','buff':'buff/permanent','duration_seconds':None},{'kind':'apply','buff':'buff/finite','duration_seconds':None}]}
 reg={**BUILTIN_PROVIDERS,'author/late_invalid':{'callable':provider,'version':'1'}}
 p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'rules':[{'id':'rule/author/late_invalid','kind':'rule','contract':'buff.application','implementation':{'type':'provider','provider':'author/late_invalid'}}],'buffs':[{'id':'buff/permanent','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':10}]},{'id':'buff/finite','kind':'buff','duration_seconds':1}],'entities':[{'id':'unit/author','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'atk':100}},'spatial':{}}}], 'scenarioDraft':{'id':'scene/author/late_invalid','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},'initialEntities':[{'definition':'unit/author','instanceAlias':'source','position':{'row':0,'col':0}}],'dependencies':['rule/author/late_invalid','buff/permanent','buff/finite']}}
 s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('source',[s.session.world.resolve('source')],{'op':'buff_application','application_rule':'rule/author/late_invalid','allowed':['buff/permanent','buff/finite']})
 assert s.checkpoint()==before
