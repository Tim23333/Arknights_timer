from tools.chapter08_bsnake.test_firecommon_v2 import ROOT,package,make,OUT
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim import Engine
from ark_sim.tools.replay import replay

def test_invalid_target_never_consumes_native_quota_far_actor_hit():
 for flag,value in [('target_free',True),('camouflage',True),('side',1),('category',4)]:
  p=package();# Separate row2 near instance definition; row1/3 unaffected.
  q=dict(p['entities'][-1]);import copy;q=copy.deepcopy(q);q['id']='unit/firecommon/near';q['components']['selection_state'][flag]=value;p['entities'].append(q);p['scenarioDraft']['initialEntities'][2]['definition']=q['id'];_,s,_=make(p);s.advance(100);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert sorted(e['payload']['target'] for e in hits)==[3,5,6];assert s.ctx.resources.current('row2','hp')==10000

def test_live_ASPD_doesnotchange_ABSOLUTE_screen_motion_and_currentATK_plus100_RES():
 p=package();p['buffs']=[{'id':'buff/fire/boost','kind':'buff','duration_seconds':10,'modifiers':[{'attribute':'atk','layer':'flat','value':100},{'attribute':'attack_speed_ratio','layer':'flat','value':1}]}];p.setdefault('selectors',[]).append({'id':'selector/fire/source','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':2}}]});p['scenarioDraft']['scheduledEffects']=[{'at':5,'effect':{'op':'apply_buff','buff':'buff/fire/boost','selector':'selector/fire/source'}}];pr,s,reg=make(p);s.advance(6);f=OUT/'boost6.cp.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h),providers=reg);s.advance(90);r.advance(90);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[522,522,522];assert s.ctx.entity('boss')['components']['attributes']['base']['atk']==770

def test_source_after_launch_real_retirement_retained_projectiles():
 p=package();p.setdefault('selectors',[]).append({'id':'selector/fire/source','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':2}}]});p['abilities'].append({'id':'ability/fire/retire','kind':'ability','selector':'selector/fire/source','activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':{'op':'retire','parameters':{'reason':'withdrawn'}}}]});p['entities'][-1]['components']['abilities']=['ability/fire/retire'];pr,s,reg=make(p);s.submit({'action':'skill','source':'row1','ability':'ability/fire/retire'},at=5);s.advance(100);assert not s.ctx.active('boss');assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[462,462,462]
