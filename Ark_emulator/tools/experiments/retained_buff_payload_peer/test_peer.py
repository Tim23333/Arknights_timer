import json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def fixture(nested=False):
 application={'op':'buff_application','application_rule':'rule/peer/cold','allowed':['buff/peer/launched'],'target':3}
 forged={'op':'buff_application','application_rule':'rule/peer/unlaunched','allowed':['buff/peer/unlaunched'],'target':3}
 buffs=[{'id':'buff/peer/launched','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_flags':[23]}},{'id':'buff/peer/unlaunched','kind':'buff','duration_seconds':1,'modifiers':[{'attribute':'atk','layer':'flat','value':99}]}]
 if nested:buffs[0]['effects']=[forged]
 def rule(name,buff):return {'id':'rule/peer/'+name,'kind':'rule','contract':'buff.application','implementation':{'type':'expression','expression':repr({'accepted':True,'operations':[{'kind':'apply','buff':buff,'duration_seconds':1}]})}}
 def ability(name,effect):return {'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]}
 shot=ability('shot',{'op':'damage','target':3,'damage_type':'physical','scale':1,'projectile_definition':'projectile/peer/retained','on_success':[application]});forged_ability=ability('forged',forged)
 retire=ability('retire_source',{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}});kill=ability('kill_target',{'op':'retire','target':3,'parameters':{'reason':'dead'}})
 def ent(name,abilities,atk=0):return {'id':'unit/peer/'+name,'kind':'entity','components':{'attributes':{'base':{'max_hp':1000,'atk':atk,'def':20,'mres':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'abilities':abilities,'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 projectile={'id':'projectile/peer/retained','kind':'projectile','motion':{'rule':'rule/peer/motion','parameters':{'mode':'homing','speed':10}},'collision':{'rule':'rule/peer/contact','parameters':{'radius':0}},'lifetime_seconds':2,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':True,'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':True,'hit_on_reach':False,'force_reach_on_expire':False,'hit_on_expire':False}}
 p={'schemaVersion':2,'manifest':{'id':'package/peer/retained_buff_payload','requires':['preset/ark_standard']},'entities':[ent('source',[shot['id'],forged_ability['id']],80),ent('target',[]),ent('controller',[retire['id'],kill['id']])],'abilities':[shot,retire,kill,forged_ability],'buffs':buffs,'rules':[rule('cold','buff/peer/launched'),rule('unlaunched','buff/peer/unlaunched'),{'id':'rule/peer/motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},{'id':'rule/peer/contact','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}],'definitions':[projectile],'scenarioDraft':{'id':'scene/peer/retained_payload','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':4},'objectives':{},'resources':{},'initialEntities':[{'definition':'unit/peer/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/peer/target','instanceAlias':'target','position':{'row':0,'col':2}},{'definition':'unit/peer/controller','instanceAlias':'controller','position':{'row':1,'col':0}}]}}
 return p,forged
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=62011)
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'scopes':deepcopy(s.ctx.projectiles._impact_payload_scopes),'reservations':deepcopy(s.ctx.projectiles._inflight_hits)})
def fire(s,targetdead=False):
 s.submit({'action':'skill','source':'source','ability':'ability/peer/shot'},at=0);s.submit({'action':'skill','source':'controller','ability':'ability/peer/retire_source'},at=2)
 if targetdead:s.submit({'action':'skill','source':'controller','ability':'ability/peer/kill_target'},at=3)
def test_true_launched_payload_after_source_retirement_has_one_damage_one_cold_and_public_cp_head(tmp_path):
 p,_=fixture();s=make(p);fire(s);s.advance(4);cp=tmp_path/'prehit.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h))
 try:s.advance(6);r.advance(6)
 finally:capture(s,'true_retained')
 rep=replay(s.program,s.export_replay());assert s.checkpoint()==r.checkpoint()==rep.checkpoint();assert thaw(tuple(s.session.events))==thaw(tuple(rep.session.events))
 assert [x['payload']['amount'] for x in s.session.events if x['type']=='damage.accepted']==[60]
 assert [x['definition'] for x in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
 assert not s.ctx.projectiles._impact_payload_scopes and not s.ctx.projectiles._inflight_hits
def test_forged_dead_source_cast_marker_has_no_buff_or_projectile_authority():
 p,e=fixture();s=make(p);s.ctx.lifecycle.retire('source','withdrawn');before=s.checkpoint();s.ctx.effects.execute('source',['target'],e,cast={'projectile_impact':True,'id':'cast/2/999'});capture(s,'forged_flag');assert before==s.checkpoint()
def test_target_dead_before_contact_rejects_both_damage_and_payload():
 p,_=fixture();s=make(p);fire(s,True)
 try:s.advance(12)
 finally:capture(s,'dead_target')
 assert not [e for e in s.session.events if e['type'] in ['damage.accepted','buff.applied']]
def test_immediate_buff_callback_cannot_borrow_impact_scope_for_new_unlaunched_buff():
 p,_=fixture(True);s=make(p);fire(s)
 try:s.advance(10)
 finally:capture(s,'nested_unlaunched')
 assert [x['definition'] for x in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
