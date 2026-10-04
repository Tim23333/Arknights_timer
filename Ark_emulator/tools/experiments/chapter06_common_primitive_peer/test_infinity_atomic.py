from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def plan(inputs,params,context):return {'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/permanent','duration_seconds':None}]}
def package(scope=None):
 p={'schemaVersion':2,'manifest':{'id':'package/peer/permanent','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/plan','kind':'rule','contract':'buff.application','implementation':{'type':'provider','provider':'peer/permanent_plan'}},{'id':'rule/peer/finite_duration','kind':'rule','contract':'buff.duration','implementation':{'type':'expression','expression':'1'}},{'id':'rule/peer/zero_duration','kind':'rule','contract':'buff.duration','implementation':{'type':'expression','expression':'0'}}],'buffs':[{'id':'buff/peer/permanent','kind':'buff','interval_seconds':.1,'effects':[{'op':'modify_resource','resource':'meter','delta':1}]}],'abilities':[{'id':'ability/peer/apply','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'buff_application','application_rule':'rule/peer/plan','allowed':['buff/peer/permanent']}]},'timeline':[]}],'entities':[{'id':'unit/peer/owner','kind':'entity','components':{'attributes':{'base':{'max_hp':123,'atk':37}},'resources':{'hp':{'initial':123,'capacity':123,'role':'health'},'meter':{'initial':0,'capacity':100}},'abilities':['ability/peer/apply'],'spatial':{}}}],'scenarioDraft':{'id':'scene/peer/permanent','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},'initialEntities':[{'definition':'unit/peer/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]}}
 if scope=='scene':p['scenarioDraft']['rules']={'buff.duration':'rule/peer/finite_duration'}
 if scope=='definition':p['buffs'][0]['rules']={'buff.duration':'rule/peer/finite_duration'}
 if scope=='owner':p['entities'][0]['rules']={'buff.duration':'rule/peer/finite_duration'}
 if scope=='zero_scene':p['scenarioDraft']['rules']={'buff.duration':'rule/peer/zero_duration'}
 return p
def registry():return {**BUILTIN_PROVIDERS,'peer/permanent_plan':{'callable':plan,'version':'independent1'}}
def make(p):INPUTS.append(deepcopy(p));r=registry();return Engine.create(Compiler(providers=r).compile(p),providers=r,seed=6063)
def capture(s,name):CAPTURES.append({'case':name,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
@pytest.mark.parametrize('scope',[None,'zero_scene'])
def test_real_permanent_ticks_stay_infinite_and_disk_public_head(scope,tmp_path):
 s=make(package(scope));s.submit({'action':'skill','source':'owner','ability':'ability/peer/apply'},at=1);s.advance(2);uid=s.ctx.get('owner',('buffs','instances'))[0]['id'];path=tmp_path/'permanent.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin),providers=registry());s.advance(13);r.advance(13);head=replay(s.program,s.export_replay(),providers=registry());capture(s,'permanent_'+str(scope));assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 b=s.ctx.get('owner',('buffs','instances'))[0];assert b['id']==uid and b['expires_at'] is None and s.ctx.resources.current('owner','meter')==4
@pytest.mark.parametrize('scope',['scene','definition','owner'])
def test_actual_nonzero_duration_scope_refuses_infinity_without_partial_buff(scope):
 s=make(package(scope));s.submit({'action':'skill','source':'owner','ability':'ability/peer/apply'},at=1);s.advance(3);capture(s,'nonzero_'+scope);assert not s.ctx.get('owner',('buffs','instances'),[]) and any(e['type']=='command.rejected' for e in s.session.events) and s.ctx.resources.current('owner','meter')==0

def two_stage(inputs,params,context):return {'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/boost','duration_seconds':.5},{'kind':'apply','buff':'buff/peer/permanent','duration_seconds':None}]}
def test_earlier_apply_changes_actual_duration_so_late_infinity_reject_rolls_back_entire_plan():
 p=package();p['rules'][0]['implementation']['provider']='peer/two_stage';p['rules'].append({'id':'rule/peer/dynamic_duration','kind':'rule','contract':'buff.duration','implementation':{'type':'expression','expression':'1 if inputs.attributes.atk >= 40 else 0'}});p['scenarioDraft']['rules']={'buff.duration':'rule/peer/dynamic_duration'};p['buffs'].append({'id':'buff/peer/boost','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':10}]});p['abilities'][0]['activation']['on_start'][0]['allowed'].append('buff/peer/boost')
 r={**registry(),'peer/two_stage':{'callable':two_stage,'version':'independent1'}};INPUTS.append(deepcopy(p));s=Engine.create(Compiler(providers=r).compile(p),providers=r);s.submit({'action':'skill','source':'owner','ability':'ability/peer/apply'},at=1);s.advance(3);capture(s,'late_duration_atomic')
 assert not s.ctx.get('owner',('buffs','instances'),[]) and not s.ctx.get('owner',('attributes','modifiers'),[]) and s.ctx.get('owner',('buffs','next_instance_id'),1)==1
 assert not [e for e in s.session.events if e['type'] in ['buff.applied','ability.started']] and any(e['type']=='command.rejected' for e in s.session.events)
