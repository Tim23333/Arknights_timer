import pytest
from ark_sim import Compiler,Engine
def p(bufflist):
 return {'schemaVersion':2,'manifest':{'id':'package/peer/selfremove','requires':['preset/ark_standard']},'buffs':bufflist,'entities':[{'id':'unit/peer/owner','kind':'entity','components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'buffs':{'initial':['buff/peer/a']}}}],'scenarioDraft':{'id':'scene/peer/selfremove','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},'initialEntities':[{'definition':'unit/peer/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]}}
def test_own_definition_remove_only_compiles_and_real_timer_removes_once():
 data=p([{'id':'buff/peer/a','kind':'buff','interval_seconds':.1,'effects':[{'op':'remove_buff','buff':'buff/peer/a'}]}]);s=Engine.create(Compiler().compile(data));s.advance(10)
 assert not s.ctx.get('owner',('buffs','instances'),[]) and len([e for e in s.session.events if e['type']=='buff.removed'])==1
@pytest.mark.parametrize('kind',['apply_self','apply_mutual','remove_mutual','explicit_dependency_self'])
def test_other_construct_cycles_still_rejected(kind):
 a={'id':'buff/peer/a','kind':'buff'};b={'id':'buff/peer/b','kind':'buff'}
 if kind=='apply_self':a['effects']=[{'op':'apply_buff','buff':a['id']}]
 elif kind=='explicit_dependency_self':a['dependencies']=[a['id']]
 else:
  op='remove_buff' if kind=='remove_mutual' else 'apply_buff';a['effects']=[{'op':op,'buff':b['id']}];b['effects']=[{'op':op,'buff':a['id']}]
 with pytest.raises(ValueError,match='cycle'):Compiler().compile(p([a,b]))
def test_other_missing_remove_definition_does_not_get_self_exemption():
 data=p([{'id':'buff/peer/a','kind':'buff','effects':[{'op':'remove_buff','buff':'buff/peer/missing'}]}])
 with pytest.raises(ValueError):Compiler().compile(data)
