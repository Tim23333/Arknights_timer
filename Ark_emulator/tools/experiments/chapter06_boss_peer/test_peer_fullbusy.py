import json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_content_composition_v2 import compose_modules
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter06_review.runner_providers_v1 import providers
ROOT=Path(__file__).resolve().parents[3];BOSS='unit/ch6/frstar2/3681c71c12a71fb0';PREFIX='ability/'+BOSS+'/';INPUTS=[];CAPTURES=[]
def fixture(state=None,tag='ground',initial=None,branch=False):
 m=json.loads((ROOT/'packages/campaign/chapter06_boss/frstar2/model.json').read_bytes());c=json.loads((ROOT/'packages/campaign/chapter06_cold/model.json').read_bytes());trap=json.loads((ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json').read_bytes());defs,_=compose_modules([('finalBoss',m),('actualCold',c),('actualTrap',trap)]);
 for key,block,taunt in [('tank',3,0),('other',0,1000000000)]:
  defs['unit/peer/'+key]={'id':'unit/peer/'+key,'kind':'entity','tags':['player',tag],'components':{'attributes':{'base':{'max_hp':90000,'atk':0,'def':31,'mres':17,'block_count':block,'taunt_level':taunt}},'resources':{'hp':{'initial':90000,'capacity':90000,'role':'health'},'sp':{'initial':0,'capacity':50,'recovery_rule':'rule/peer/received','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},'selection_state':{'side':0,'motion':2 if tag=='flying' else 1,'category':1,'unit_type':1,**(state or {})},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'spatial':{'radius':0},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 defs['rule/peer/received']={'id':'rule/peer/received','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current+inputs.parameters.amount'}}
 controller={'id':'unit/peer/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':50000}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'abilities':['ability/peer/'+x for x in ['hit','small','freeze','coldboss','sleepboss']],'spatial':{}}};defs[controller['id']]=controller
 effects={'hit':{'op':'damage','target':2,'damage_type':'true','scale':1},'small':{'op':'damage','target':2,'damage_type':'true','scale':.002},'freeze':{'op':'apply_buff','target':6,'buff':'buff/ch6/cold/e2c_freeze'},'coldboss':{'op':'buff_application','target':2,'application_rule':'rule/ch6/cold/application','allowed':['buff/ch6/cold/e2c_cold','buff/ch6/cold/e2c_freeze'],'parameters':{'duration_seconds':10}},'sleepboss':{'op':'apply_buff','target':2,'buff':'buff/peer/sleep'}}
 for key,e in effects.items():defs['ability/peer/'+key]={'id':'ability/peer/'+key,'kind':'ability','activation':{'mode':'manual','on_start':[e]},'timeline':[]}
 defs['buff/peer/sleep']={'id':'buff/peer/sleep','kind':'buff','selection_flags':{'abnormal_combos':[0]},'control':{'attack':False,'abilities':False,'move':False}}
 boss={'definition':BOSS,'instanceAlias':'boss','position':{'row':2,'col':2}}
 if initial:boss['components']=deepcopy(initial)
 p={'schemaVersion':2,'manifest':{'id':'package/independent/ch6/boss','requires':['preset/ark_standard']},'definitions':list(defs.values()),'scenarioDraft':{'id':'scene/independent/ch6/boss','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':10},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':30,'capacity':99}},'parameters':{'deploy_capacity':4},'roster':['unit/peer/tank','unit/peer/other'],'objectives':{},'initialEntities':[boss,{'definition':controller['id'],'instanceAlias':'controller','position':{'row':7,'col':9}}]}}
 p['scenarioDraft']['branches']=deepcopy(trap['manifest']['metadata']['native_branch_programs']['level_main_06-14']);p['scenarioDraft']['initialEntities']+=deepcopy(trap['manifest']['metadata']['native_predefined_profiles']['level_main_06-14']['initial_entities'])
 return p
def make(p):INPUTS.append(deepcopy(p));r=providers();return Engine.create(Compiler(providers=r).compile(p),providers=r,seed=6191)
def deploy(s,key='tank',row=2,col=3,at=0):s.submit({'action':'deploy','definition':'unit/peer/'+key,'alias':key,'position':{'row':row,'col':col},'facing':'left'},at=at)
def skill(s,key,at):s.submit({'action':'skill','source':'controller','ability':'ability/peer/'+key},at=at)
def ev(s,key):return [e for e in s.session.events if e['type']==key]
def capture(s,name):CAPTURES.append({'case':name,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def exact(s,tmp,n):
 path=tmp/'boss_ordered.json';pin=write_ordered(path,s.checkpoint());r=providers();rest=Engine.restore(s.program,load_bound(path,pin),providers=r);s.advance(n);rest.advance(n);head=replay(s.program,s.export_replay(),providers=r);assert s.checkpoint()==rest.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
def test_full_declared_normal_cast_busy_duration_scales_with_actual_pointseven_ASPD():
 initial={'buffs':{'initial':['buff/'+BOSS+'/sleepimmune','buff/ch6/cold/e2c_cold']},'ability_timing':{'initial_cooldowns':{PREFIX+'burst0':1.5}}};s=make(fixture(initial=initial));deploy(s);s.advance(72);capture(s,'normal_pointseven_fullbusy')
 normal=[e for e in ev(s,'ability.started') if e['payload']['ability']==PREFIX+'normal0'];burst=[e for e in ev(s,'ability.started') if e['payload']['ability']==PREFIX+'burst0'];assert normal and normal[0]['time']==0
 assert burst and burst[0]['time']>=69
