from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def request(modify=True):return {'op':'no_source_damage','damage_type':'true','attack_type':'BUFF','fixed_amount':30,'damage_without_modify':modify,'ignore_for_sp':True,'node_is_env_damage':False,'env_blackboard_injected':False,'environmental':False,'origin':{'independent':'new_timer_fixture'},'rules':{'damage.pipeline':'rule/peer/half'}}
def package(modify=True,hook=False,bounds=False):
 p={'schemaVersion':2,'manifest':{'id':'package/peer/actorfree','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/half','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount / 2,'allocations':[],'events':[]}"}],'output':'nodes.result'}},{'id':'rule/peer/reject','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.result'}},{'id':'rule/peer/sp','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current+1'}},{'id':'rule/peer/floor','kind':'rule','contract':'resource.bounds','implementation':{'type':'expression','expression':"{'accepted':True,'value':max(5,min(inputs.candidate,inputs.capacity))}"}}],'buffs':[{'id':'buff/peer/blood','kind':'buff','interval_seconds':.1,'effects':[request(modify)]},{'id':'buff/peer/no_damage','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/peer/reject'}]}],'abilities':[{'id':'ability/peer/remove','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':2,'buff':'buff/peer/blood'}]},'timeline':[]},{'id':'ability/peer/refresh','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':'buff/peer/blood'}]},'timeline':[]}],'entities':[{'id':'unit/peer/owner','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':71,'atk':999,'def':999,'mres':100}},'resources':{'hp':{'initial':71,'capacity':71,'role':'health'},'sp':{'initial':0,'capacity':10,'recovery_rule':'rule/peer/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},'buffs':{'initial':['buff/peer/blood']+(['buff/peer/no_damage'] if hook else [])},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/peer/controller','kind':'entity','components':{'abilities':['ability/peer/remove','ability/peer/refresh'],'spatial':{}}}],'scenarioDraft':{'id':'scene/peer/actorfree','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},'objectives':{},'initialEntities':[{'definition':'unit/peer/owner','instanceAlias':'owner','position':{'row':0,'col':0}},{'definition':'unit/peer/controller','instanceAlias':'controller','position':{'row':0,'col':1}}]}}
 if bounds:p['entities'][0]['components']['resources']['hp']['bounds_rule']='rule/peer/floor'
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=6053)
def capture(s,k):CAPTURES.append({'case':k,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def events(s,t):return [e for e in s.session.events if e['type']==t]
@pytest.mark.parametrize('mode',[True,False])
def test_actual_actorfree_buff_timer_damage_flags_no_cast_SP_and_disk(mode,tmp_path):
 s=make(package(mode));s.advance(2);path=tmp_path/'blood_before.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,h));s.advance(8);r.advance(8);head=replay(s.program,s.export_replay());capture(s,'blood_'+str(mode));assert s.checkpoint()==r.checkpoint()==head.checkpoint()
 hits=events(s,'damage.accepted');assert [e['time'] for e in hits]==[3,6,9] and [e['payload']['amount'] for e in hits]==([30,30,11] if mode else [15,15,15])
 assert all(e['payload']['source'] is None and e['payload']['ability'] is None and e['payload']['attack_type']=='BUFF' for e in hits)
 assert all(e['payload']['origin']['buff_timer']['owner']==2 for e in hits) and s.ctx.resources.current('owner','sp')==0 and not events(s,'ability.started') and not events(s,'attack.accepted')
 if mode:assert not s.ctx.alive('owner') and not s.ctx.get('owner',('buffs','instances'),[])
@pytest.mark.parametrize('mode',[True,False])
def test_true_bypasses_targethook_false_preserves_hook(mode):
 s=make(package(mode,hook=True));s.advance(4);capture(s,'hook_'+str(mode));assert s.ctx.resources.current('owner','hp')==(41 if mode else 71)
 assert bool(events(s,'damage.accepted'))==mode and bool(events(s,'damage.rejected'))!=mode

def test_true_still_obeys_actual_health_bounds_instead_of_bypassing_them():
 s=make(package(True,bounds=True));s.advance(13);capture(s,'real_bounds');assert s.ctx.resources.current('owner','hp')==5 and s.ctx.alive('owner') and [e['payload']['amount'] for e in events(s,'damage.accepted')]==[30,30,6,0]

def test_refresh_actual_handle_generation_replaces_old_schedule_without_duplicate_damage():
 s=make(package(False));s.submit({'action':'skill','source':'controller','ability':'ability/peer/refresh'},at=2);s.submit({'action':'skill','source':'controller','ability':'ability/peer/remove'},at=9);s.advance(14);capture(s,'refresh_remove');assert [e['time'] for e in events(s,'damage.accepted')]==[5,8] and not s.ctx.get('owner',('buffs','instances'),[])
