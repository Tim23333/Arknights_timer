from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def clocked(inputs,params,context):
 assert context['seconds']==context['time']*context['quantum']
 marker=[i for i in inputs['candidate']['components'].get('buffs',{}).get('instances',[]) if i['definition']=='buff/peer/hidden' and (i['expires_at'] is None or context['time']<i['expires_at'])]
 return not marker
def mutation(inputs,params,context):context['time']=999;return True
def throws(inputs,params,context):raise ValueError('peer pure provider error')
def nested(inputs,params,context):return context.calculate('targeting.availability',inputs,rule_id='rule/peer/clock').value
def registry():return {**BUILTIN_PROVIDERS,'peer.clock':{'callable':clocked,'version':'1'},'peer.mutate':mutation,'peer.throws':throws,'peer.nested':nested}
def package():
 return {'schemaVersion':2,'manifest':{'id':'package/peer/clock','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/clock','kind':'rule','contract':'targeting.availability','implementation':{'type':'provider','provider':'peer.clock'}},{'id':'rule/peer/nested','kind':'rule','contract':'targeting.availability','dependencies':['rule/peer/clock'],'implementation':{'type':'provider','provider':'peer.nested'}}],'buffs':[{'id':'buff/peer/hidden','kind':'buff','duration_seconds':4/30}],'entities':[{'id':'unit/peer/source','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/mark','ability/peer/query']}},{'id':'unit/peer/target','kind':'entity','rules':{'targeting.availability':'rule/peer/nested'},'tags':['target'],'components':{'spatial':{}}}],'selectors':[{'id':'selector/peer/all','kind':'selector','region':{'type':'all'},'filters':[{'tag':'target'}],'limit':None}],'abilities':[{'id':'ability/peer/mark','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':3,'buff':'buff/peer/hidden'}]},'timeline':[]},{'id':'ability/peer/query','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/all','timeline':[{'at':0,'effect':{'op':'emit','event':'peer.clock.targets'}}]}],'scenarioDraft':{'id':'scene/peer/clock','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/peer/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/peer/target','instanceAlias':'target','position':{'row':0,'col':1}}]}}
def make(p=None):p=p or package();INPUTS.append(deepcopy(p));r=registry();return Engine.create(Compiler(providers=r).compile(p),providers=r,seed=26047)
def capture(s,k):CAPTURES.append({'case':k,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()})
def test_exact_expiry_before_cleanup_pure_context_matches_observable_nested_calc(tmp_path):
 s=make();s.submit({'action':'skill','source':'source','ability':'ability/peer/mark'},at=0);s.submit({'action':'skill','source':'source','ability':'ability/peer/query'},at=4);s.advance(3);assert not s.ctx.spatial.available('source',3);before=s.checkpoint();assert not s.ctx.spatial.available('source',3) and s.checkpoint()==before
 pin=write_ordered(tmp_path/'clock3.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'clock3.json',pin),providers=registry());s.advance(3);r.advance(3);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'clock_expiry');assert s.checkpoint()==r.checkpoint()==h.checkpoint();assert s.ctx.spatial.available('source',3)
@pytest.mark.parametrize('provider',['peer.mutate','peer.throws'])
def test_foreign_pure_provider_failure_preserves_world_events_rng_and_scheduled_tasks(provider):
 p=package();p['rules'][0]['implementation']['provider']=provider;s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.spatial.available('source',3)
 capture(s,provider);assert s.checkpoint()==before
def test_missing_target_binding_old_noopt_is_pure_unchanged():
 p=package();p['entities'][1].pop('rules');s=make(p);before=s.checkpoint();assert s.ctx.spatial.available('source',3) and s.checkpoint()==before;capture(s,'noopt')
