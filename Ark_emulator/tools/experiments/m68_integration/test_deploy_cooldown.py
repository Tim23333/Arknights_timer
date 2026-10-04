import json,hashlib
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.domains.deployment import prepare,record
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
CAPTURES=[];INPUTS=[]
def fixture(start='deploy',owned=False):
 d={'base_cost':5,'capacity':0,'cooldown_seconds':5,'refund_ratio':.5,'terrain':'ground','parameters':{'max_instances':10},'stock':{'resource':'cards','amount':1},'rules':{'deploy.cost':'rule/constant_cost'}}
 if start is not None:d['cooldown_start']=start
 token={'id':'unit/marker','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'def':0,'block_count':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'deployable':d,'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 p={'manifest':{'requires':['preset/ark_standard']},'entities':[token],'rules':[{'id':'rule/constant_cost','kind':'rule','contract':'deploy.cost','implementation':{'type':'expression','expression':'inputs.base_cost'}}], 'scenarioDraft':{'id':'scene/cooldown','ruleset':'ruleset/ark_standard','roster':['unit/marker'],'map':{'rows':2,'cols':6},'parameters':{'deploy_capacity':2},'resources':{'dp':{'initial':100,'capacity':100},'cards':{'initial':5,'capacity':5},'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'}}}
 if owned:
  host={'id':'unit/host','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/spawn']}}
  p['entities'].append(host);p['abilities']=[{'id':'ability/spawn','kind':'ability','activation':{'mode':'manual','costs':[{'owner':'battle','resource':'dp','amount':5}],'on_start':[{'op':'spawn','definition':'unit/marker','owner':'source','lifetime_seconds':2,'parameters':{'position_from_payload':True,'deployment_payment_amount':5,'max_owned':10}}]},'timeline':[]}]
  p['scenarioDraft']['roster']=['unit/host'];p['scenarioDraft']['initialEntities']=[{'definition':'unit/host','instanceAlias':'host','position':{'row':1,'col':0}},{'definition':'unit/host','instanceAlias':'host2','position':{'row':1,'col':1}}]
 return p

def create(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':6301});s=Engine.create(Compiler().compile(json.loads(raw)),seed=6301);return s,{'fixture_sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':6301}
def deploy(s,at,alias,col):s.submit({'action':'deploy','entity':'unit/marker','alias':alias,'position':{'row':0,'col':col}},at=at)
def exact(s,inputs,tmp,expected):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(60);r.advance(60);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();CAPTURES.append({'input':inputs,'expected':expected,'snapshot':s.snapshot(),'commands':s.export_replay(),'events':thaw(tuple(s.session.events)),'checkpoint_sha256':h,'checkpoint_equal':True,'commands_replay_equal':True})
def history(s,key='unit/marker'):return s.ctx.state()['deployments'][key]

def test_deploy_cooldown_halfopen_and_retire_does_not_extend_new_ready(tmp_path):
 s,inputs=create(fixture());deploy(s,0,'a',0);deploy(s,149,'too_early',1);deploy(s,150,'b',1);s.submit({'action':'withdraw','source':'a'},at=200);s.advance(201)
 assert history(s)=={'count':2,'ready_at':300};assert s.ctx.resources.current('system/battle','cards')==3 and s.ctx.resources.current('system/battle','dp')==92.5
 assert not any(e.get('alias')=='too_early' for e in s.snapshot()['entities']);assert s.ctx.active('b') and not s.ctx.active('a')
 exact(s,inputs,tmp_path,{'first_ready':150,'second_ready':300,'retire200_does_not_extend':300,'successful_deploys':2,'constant_fee_each':5})

@pytest.mark.parametrize('start',[None,'retire'])
def test_default_retire_cooldown_remains_from_retirement(start,tmp_path):
 s,inputs=create(fixture(start));deploy(s,0,'a',0);s.submit({'action':'withdraw','source':'a'},at=200);deploy(s,349,'early',1);deploy(s,350,'b',1);s.advance(351);assert history(s)['ready_at']==350 and history(s)['count']==2
 exact(s,inputs,tmp_path,{'default_retire_ready':350,'successful_second':350})


def test_owned_deploy_history_scoped_by_owner_and_lifetime_does_not_extend(tmp_path):
 s,inputs=create(fixture(owned=True))
 for source,col in [('host',0),('host2',1)]:s.submit({'action':'skill','source':source,'ability':'ability/spawn','payload':{'position':{'row':0,'col':col}}},at=0)
 s.submit({'action':'skill','source':'host','ability':'ability/spawn','payload':{'position':{'row':0,'col':2}}},at=149);s.submit({'action':'skill','source':'host','ability':'ability/spawn','payload':{'position':{'row':0,'col':2}}},at=150);s.advance(151)
 k='unit/marker|owner:'+str(s.session.world.resolve('host'));k2='unit/marker|owner:'+str(s.session.world.resolve('host2'));assert history(s,k)=={'count':2,'ready_at':300} and history(s,k2)=={'count':1,'ready_at':150}
 assert s.ctx.resources.current('system/battle','dp')==85 and s.ctx.resources.current('system/battle','cards')==2
 exact(s,inputs,tmp_path,{'owner1_second_ready':300,'owner2_ready':150,'lifetime60_not_extension':True,'DP15':'actual three successful payments'})


def test_cooldown_pure_rule_reason_and_actual_attributes_consumed(tmp_path):
 p=fixture();p['entities'][0]['components']['deployable']['rules']['deploy.cooldown']='rule/custom_cd';p['rules'].append({'id':'rule/custom_cd','kind':'rule','contract':'deploy.cooldown','implementation':{'type':'expression','expression':'inputs.attributes.max_hp / 100 if inputs.reason.type == "deployed" else 9'}})
 s,inputs=create(p);deploy(s,0,'a',0);deploy(s,29,'early',1);deploy(s,30,'b',1);s.advance(31);assert history(s)=={'count':2,'ready_at':60}
 exact(s,inputs,tmp_path,{'custom_deploy_delay_seconds':1,'second_deploy_at':30});assert all(e['payload']['value']==1 for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='deploy.cooldown')


def test_duplicate_record_fails_before_any_second_stock_or_calculation():
 s,inputs=create(fixture());plan=prepare(s.ctx,'unit/marker',{'row':0,'col':0});ref=s.ctx.lifecycle.create('unit/marker',{'row':0,'col':0},deployed=True);record(s.ctx,ref,plan);before=s.checkpoint()
 with pytest.raises(ValueError,match='already recorded'):record(s.ctx,ref,plan)
 assert s.checkpoint()==before


def test_duplicate_record_from_cooldown_calc_callback_rejected_and_atomic():
 s,inputs=create(fixture());plan=prepare(s.ctx,'unit/marker',{'row':0,'col':0});ref=s.ctx.lifecycle.create('unit/marker',{'row':0,'col':0},deployed=True);before=s.checkpoint();old=s.ctx.calc
 def callback(name,*a,**kw):
  if name=='deploy.cooldown':record(s.ctx,ref,plan)
  return old(name,*a,**kw)
 s.ctx.calc=callback
 with pytest.raises(ValueError,match='already recorded'):record(s.ctx,ref,plan)
 assert s.checkpoint()==before


@pytest.mark.parametrize('failure',['rule','stock','birth'])
def test_public_deploy_failure_all_payments_random_tasks_marker_rollback(failure):
 p=fixture();p['buffs']=[{'id':'buff/random_birth','kind':'buff','effects':[{'op':'random','stream':'imp','probability':1,'effects':[{'op':'emit','event':'probe.birth'}]}]}];p['entities'][0]['components']['buffs']={'initial':['buff/random_birth']}
 if failure=='rule':
  p['entities'][0]['components']['deployable']['rules']['deploy.cooldown']='rule/bad_cd';p['rules'].append({'id':'rule/bad_cd','kind':'rule','contract':'deploy.cooldown','implementation':{'type':'expression','expression':'1 / 0'}})
 elif failure=='stock':p['scenarioDraft']['resources']['cards']['initial']=0
 else:p['buffs'][0]['effects'].append({'op':'modify_resource','resource':'missing','delta':1})
 s,inputs=create(p);before=s.checkpoint()
 with pytest.raises(Exception):
  with s.session.atomic():s._execute_command({'action':'deploy','entity':'unit/marker','alias':'bad','position':{'row':0,'col':0}})
 assert s.checkpoint()==before
 CAPTURES.append({'input':inputs,'expected':'All resources, actor creation, record marker, tasks/log/RNG restored','failure':failure,'scope':'public API atomic instrumentation; no command replay claim','checkpoint':s.checkpoint()})

@pytest.mark.parametrize('bad',[None,True,0,'start','deployment',{},[]])
def test_invalid_start_compile_failfast(bad):
 p=fixture();p['entities'][0]['components']['deployable']['cooldown_start']=bad
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'negative':True})
 with pytest.raises(Exception,match='cooldown_start'):Compiler().compile(json.loads(raw))


@pytest.mark.parametrize('container',['initial','wave','runtime'])
def test_invalid_effective_instance_start_cannot_bypass_definition_guard(container):
 p=fixture();override={'deployable':{'cooldown_start':True}}
 if container=='initial':p['scenarioDraft']['initialEntities']=[{'definition':'unit/marker','instanceAlias':'wrong','components':override,'position':{'row':0,'col':0}}]
 elif container=='wave':p['scenarioDraft']['waves']=[{'at':0,'definition':'unit/marker','instanceAlias':'wrong','components':override,'position':{'row':0,'col':0}}]
 if container=='runtime':
  sim,_=create(p);before=sim.checkpoint()
  with pytest.raises(ValueError,match='cooldown_start'):sim.ctx.lifecycle.create('unit/marker',{'row':0,'col':0},component_overrides=override)
  assert sim.checkpoint()==before
 else:
  with pytest.raises(Exception,match='cooldown_start'):Compiler().compile(p)

@pytest.mark.parametrize('expression',['-1','True','1 / 0'])
def test_bad_cooldown_output_public_payment_and_marker_rolls_back(expression):
 p=fixture();p['entities'][0]['components']['deployable']['rules']['deploy.cooldown']='rule/bad_output';p['rules'].append({'id':'rule/bad_output','kind':'rule','contract':'deploy.cooldown','implementation':{'type':'expression','expression':expression}})
 s,inputs=create(p);before=s.checkpoint()
 with pytest.raises(Exception):
  with s.session.atomic():s._execute_command({'action':'deploy','entity':'unit/marker','position':{'row':0,'col':0}})
 assert s.checkpoint()==before



def test_actual_health_death_does_not_restart_deploy_cooldown(tmp_path):
 p=fixture();p['entities'].append({'id':'unit/probe_enemy','kind':'entity','tags':['enemy'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':100}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'abilities':['ability/kill_marker'],'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['selectors']=[{'id':'selector/marker','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}],'limit':1}];p['abilities']=[{'id':'ability/kill_marker','kind':'ability','selector':'selector/marker','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}];p['scenarioDraft']['initialEntities']=[{'definition':'unit/probe_enemy','instanceAlias':'enemy','position':{'row':1,'col':5}}]
 s,inputs=create(p);deploy(s,0,'a',0);s.submit({'action':'skill','source':'enemy','ability':'ability/kill_marker'},at=10);deploy(s,149,'early',1);deploy(s,150,'b',1);s.advance(151);assert not s.ctx.alive('a') and s.ctx.resources.current('a','hp')==0 and history(s)=={'count':2,'ready_at':300}
 exact(s,inputs,tmp_path,{'health_death':10,'first_ready_stays':150,'second_ready':300})


def test_stock_shared_with_dp_checks_combined_before_payment():
 p=fixture();p['entities'][0]['components']['deployable']['stock']['resource']='dp';p['scenarioDraft']['resources']['dp']['initial']=5;s,inputs=create(p);before=s.checkpoint()
 with pytest.raises(ValueError,match='stock'):
  with s.session.atomic():s._execute_command({'action':'deploy','entity':'unit/marker','position':{'row':0,'col':0}})
 assert s.checkpoint()==before


def test_explicit_zero_cooldown_allows_distinct_cells_same_frame(tmp_path):
 p=fixture();p['entities'][0]['components']['deployable']['cooldown_seconds']=0;s,inputs=create(p);deploy(s,0,'a',0);deploy(s,0,'b',1);s.advance(1);assert history(s)=={'count':2,'ready_at':0} and s.ctx.resources.current('system/battle','cards')==3
 exact(s,inputs,tmp_path,{'zero_cooldown':0,'sameframe_successes':2})
