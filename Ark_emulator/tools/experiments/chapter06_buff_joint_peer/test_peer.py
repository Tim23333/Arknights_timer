from pathlib import Path
from copy import deepcopy
import json,math,pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def fixture(plan,permanent=False,callback=None):
 buffs=[{'id':'buff/peer/a','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':7}]},{'id':'buff/peer/b','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':13}]}]
 if not permanent:
  for b in buffs:b['duration_seconds']=20
 if callback:buffs[0]['on_remove']=[{'op':'retire','target':callback,'parameters':{'reason':'withdrawn'}}]
 rule={'id':'rule/peer/application','kind':'rule','contract':'buff.application','implementation':{'type':'expression','expression':plan}}
 effect={'op':'buff_application','target':3,'application_rule':rule['id'],'allowed':['buff/peer/a','buff/peer/b']}
 ability={'id':'ability/peer/application','kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]}
 def entity(name,abilities=[]):return {'id':'unit/peer/'+name,'kind':'entity','components':{'attributes':{'base':{'max_hp':1000,'atk':80}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{},'abilities':abilities,'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 p={'schemaVersion':2,'manifest':{'id':'package/peer/generic_application','requires':['preset/ark_standard']},'entities':[entity('source',[ability['id']]),entity('victim'),entity('other')],'buffs':buffs,'rules':[rule],'abilities':[ability],'scenarioDraft':{'id':'scene/peer/generic_application','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},'objectives':{},'resources':{},'initialEntities':[{'definition':'unit/peer/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/peer/victim','instanceAlias':'victim','position':{'row':0,'col':1}},{'definition':'unit/peer/other','instanceAlias':'other','position':{'row':1,'col':1}}]}}
 return p,effect
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=6171)
def buffs(s,who='victim'):return thaw(s.ctx.get(who,('buffs','instances'),[]))
def capture(s,name):CAPTURES.append({'case':name,'commands':s.export_replay(),'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def exact(s,tmp,n):
 cp=tmp/'ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.advance(n);r.advance(n);rep=replay(s.program,s.export_replay());assert s.checkpoint()==r.checkpoint()==rep.checkpoint();assert thaw(tuple(s.session.events))==thaw(tuple(rep.session.events))
@pytest.mark.parametrize('accepted',[True,False])
def test_plan_noop_has_exact_full_checkpoint_rng_event_task_identity(accepted):
 p,e=fixture(repr({'accepted':accepted,'operations':[]}));s=make(p);before=s.checkpoint();s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'});assert before==s.checkpoint();capture(s,'noop_'+str(accepted))
def test_all_allowed_unselected_buffs_are_real_compiled_closure():
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/a','duration_seconds':0.2}]} ");s=make(p)
 assert all(x in s.program.definitions for x in ['buff/peer/a','buff/peer/b','rule/peer/application'])
 s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1);assert [b['definition'] for b in buffs(s)]==['buff/peer/a'];capture(s,'closure')
@pytest.mark.parametrize('missing_kind',['missing','entity','wrong_contract'])
def test_noop_still_rejects_bad_allowed_or_application_contract(missing_kind):
 p,e=fixture("{'accepted':False,'operations':[]}")
 if missing_kind=='missing':p['buffs'].pop()
 elif missing_kind=='entity':p['buffs'].pop();p['entities'].append({'id':'buff/peer/b','kind':'entity','components':{}})
 else:p['rules'][0]['contract']='buff.duration';p['rules'][0]['implementation']['expression']='0'
 INPUTS.append(deepcopy(p))
 with pytest.raises(Exception):Compiler().compile(p)
@pytest.mark.parametrize('duration',['True','-1',"float('nan')","float('inf')"])
def test_bad_plan_durations_reject_atomically(duration):
 # Request expression uses finite literals for boolean/negative; nonfinite
 # is provider-independent direct plan validation below, not an expression builtin.
 if duration.startswith('float'):
  from ark_sim.domains.buff_application import validate_plan
  with pytest.raises(ValueError):validate_plan({'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/a','duration_seconds':math.nan if 'nan' in duration else math.inf}]},['buff/peer/a'],3,[])
  return
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/a','duration_seconds':"+duration+"}]}");s=make(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'})
 assert before==s.checkpoint();capture(s,'bad_duration_'+duration)
@pytest.mark.parametrize('generation',['True','2'])
def test_wrong_generation_cannot_remove_live_target_handle(generation):
 p,e=fixture("{'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/a','instance':'buff/3/1','generation':"+generation+"}]}");s=make(p);s.ctx.buffs.apply('source','victim','buff/peer/a');before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'})
 assert before==s.checkpoint();capture(s,'generation_'+generation)
def test_foreign_target_handle_and_definition_mismatch_cannot_be_removed():
 for uid,bid in [('buff/4/1','buff/peer/a'),('buff/3/1','buff/peer/b')]:
  p,e=fixture(repr({'accepted':True,'operations':[{'kind':'remove','buff':bid,'instance':uid,'generation':1}]}));s=make(p);s.ctx.buffs.apply('source','victim','buff/peer/a');s.ctx.buffs.apply('source','other','buff/peer/a');before=s.checkpoint()
  with pytest.raises(ValueError):s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'})
  assert before==s.checkpoint();capture(s,'foreign_'+uid+bid)
@pytest.mark.parametrize('retire',[2,3])
def test_remove_callback_retires_source_or_target_and_stops_old_remaining_plan(retire):
 plan="{'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/a','instance':'buff/3/1','generation':1},{'kind':'apply','buff':'buff/peer/b','duration_seconds':1}]}"
 p,e=fixture(plan,callback=retire);s=make(p);s.ctx.buffs.apply('source','victim','buff/peer/a');s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'})
 assert not s.ctx.active(retire) and not any(b['definition']=='buff/peer/b' for b in buffs(s));capture(s,'callback_'+str(retire))
def test_positive_override_on_permanent_definition_has_exact_finite_expiry_public_disk_replay(tmp_path):
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0.2}]}",permanent=True);s=make(p);s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1);assert buffs(s)[0]['expires_at']==6;exact(s,tmp_path,7);assert not buffs(s);capture(s,'finite_override')
def test_explicit_zero_override_does_not_turn_into_permanent_buff():
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0}]}",permanent=True);s=make(p);s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'});capture(s,'zero_override')
 assert buffs(s)[0]['expires_at']==s.session.time
