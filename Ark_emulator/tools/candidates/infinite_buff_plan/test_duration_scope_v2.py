"""Actual scoped duration, atomic calculation rollback and callback input changes."""
import sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
def fixture(scope,seconds,operations=None):
 def provider(inputs,params,context):return {'accepted':True,'operations':operations or [{'kind':'apply','buff':'buff/permanent','duration_seconds':None}]}
 reg={**BUILTIN_PROVIDERS,'author/none2':{'callable':provider,'version':'2'}}
 p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'rules':[{'id':'rule/none2','kind':'rule','contract':'buff.application','implementation':{'type':'provider','provider':'author/none2'}},{'id':'rule/duration2','kind':'rule','contract':'buff.duration','implementation':{'type':'expression','expression':str(seconds)}}],'buffs':[{'id':'buff/permanent','kind':'buff'}],'entities':[{'id':'unit/source','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'atk':100}},'spatial':{}}},{'id':'unit/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'atk':50}},'spatial':{}}}],'scenarioDraft':{'id':'scene/infinity2/'+scope,'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},'objectives':{},'initialEntities':[{'definition':'unit/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':1}}],'dependencies':['rule/none2','buff/permanent','rule/duration2']}}
 if scope=='buff':p['buffs'][0]['rules']={'buff.duration':'rule/duration2'}
 if scope=='source':p['entities'][0]['rules']={'buff.duration':'rule/duration2'}
 if scope=='target':p['entities'][1]['rules']={'buff.duration':'rule/duration2'}
 if scope=='scenario':p['scenarioDraft']['rules']={'buff.duration':'rule/duration2'}
 return p,reg
def apply(s,target='target'):s.ctx.effects.execute('source',[s.session.world.resolve(target)],{'op':'buff_application','application_rule':'rule/none2','allowed':['buff/permanent']})
@pytest.mark.parametrize('scope',['buff','source','target','scenario','runtime_source','runtime_target'])
@pytest.mark.parametrize('seconds',[0,3])
def test_actual_zero_only_all_binding_scopes_and_failure_no_calculation_cache_leak(scope,seconds):
 p,reg=fixture(scope,seconds);s=Engine.create(Compiler(providers=reg).compile(p),providers=reg)
 if scope.startswith('runtime_'):s.ctx.set(scope.split('_')[1],('runtime','rule_bindings'),{'buff.duration':'rule/duration2'})
 before=s.checkpoint()
 if seconds:
  with pytest.raises(ValueError,match='actual resolved zero'):apply(s)
  assert s.checkpoint()==before
  # Rollback invalidates caches; subsequent reads must not reference a rolled
  # back calculation event. Actual Session cache epoch handles invalidation.
  s.ctx.attributes.value('source','atk');ids={e['id'] for e in s.session.events};assert all(e['payload']['source_event_id'] in ids for e in s.session.events if e['type']=='calculation.cached')
 else:
  apply(s);instances=s.ctx.entity('target')['components']['buffs']['instances'];assert len(instances)==1 and instances[0]['expires_at'] is None
@pytest.mark.parametrize('mode',['first_modifier','first_on_apply_callback'])
def test_all_none_prechecked_then_actual_input_recheck_after_prior_effect(mode):
 ops=[{'kind':'apply','buff':'buff/change','duration_seconds':1},{'kind':'apply','buff':'buff/permanent','duration_seconds':None}];p,reg=fixture('buff',0,ops);p['rules'][1]['implementation']['expression']='inputs.attributes.atk - 100';change={'id':'buff/change','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]}
 if mode=='first_on_apply_callback':
  change.pop('modifiers');change['effects']=[{'op':'apply_buff','buff':'buff/callback_change'}];p['buffs'].append({'id':'buff/callback_change','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]})
 p['buffs'].append(change);p['scenarioDraft']['dependencies'].append('buff/change');s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);before=s.checkpoint()
 with pytest.raises(ValueError,match='actual resolved zero'):s.ctx.effects.execute('source',[s.session.world.resolve('source')],{'op':'buff_application','application_rule':'rule/none2','allowed':['buff/change','buff/permanent']})
 assert s.checkpoint()==before
def test_callback_removes_permanent_handle_no_forced_reinsert():
 p,reg=fixture('buff',0);p['buffs'][0]['effects']=[{'op':'remove_buff','buff':'buff/permanent'}];s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);apply(s);assert not s.ctx.entity('target')['components']['buffs']['instances']
def test_callback_retires_owner_respects_actual_identity():
 p,reg=fixture('buff',0);p['buffs'][0]['effects']=[{'op':'retire'}];s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);apply(s);assert not s.ctx.alive('target')
