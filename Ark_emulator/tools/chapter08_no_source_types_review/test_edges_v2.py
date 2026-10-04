from copy import deepcopy
import pytest
from tools.chapter08_no_source_types_review.test_peer_v2 import package,make,proof,request,REG
def test_liveRES_public_buff8_is_read_at_NoneSource_packet13_not_cached_initial():
 p=package();p['entities'][0]['components']['abilities']=['ability/peer/reschange'];p['buffs'].append({'id':'buff/peer/reschange','kind':'buff','modifiers':[{'attribute':'mres','layer':'flat','value':-10}]});p['abilities']=[{'id':'ability/peer/reschange','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/peer/reschange'}]},'timeline':[]}];pr,s=make(p);s.submit({'action':'skill','source':'target','ability':'ability/peer/reschange'},at=8);proof(p,pr,s,'liveRES35',11,20);assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[1040];assert s.ctx.attributes.values(2)['mres']==35
def test_target_inactive_after_public_withdraw9_doesnot_receive_sourceNone13():
 p=package();p['entities'][0]['components']['abilities']=['ability/peer/withdraw'];p['abilities']=[{'id':'ability/peer/withdraw','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}]},'timeline':[]}];pr,s=make(p);s.submit({'action':'skill','source':'target','ability':'ability/peer/withdraw'},at=9);proof(p,pr,s,'inactive_target',7,20);assert not [e for e in s.session.events if e['type']=='damage.accepted'] and s.ctx.resources.current('target','hp')==8000
def test_multiple_allocations_late_bad_resource_rollback_every_earlier_plan():
 p=package();p['scenarioDraft']['scheduledEffects']=[]
 def bad(inputs,params,context):return {'accepted':True,'amount':300,'allocations':[{'target':2,'resource':'hp','amount':123},{'target':2,'resource':'absent','amount':177}],'events':[]}
 from ark_sim import Compiler,Engine
 reg={**REG,'peer.bad.alloc':{'callable':bad,'version':'1'}};p['rules'][1]['implementation']={'type':'provider','provider':'peer.bad.alloc'};pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg);before=s.checkpoint()
 with pytest.raises((ValueError,KeyError)):s.ctx.effects.execute(None,[2],dict(request(),target=2))
 assert s.checkpoint()==before
def test_minimum5percent_kept_by_source_unaffiliated_custom_pipeline_not_generic_fakeATK():
 p=package('physical',amount=100);pr,s=make(p);proof(p,pr,s,'minfloor',11,20);assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[5]
