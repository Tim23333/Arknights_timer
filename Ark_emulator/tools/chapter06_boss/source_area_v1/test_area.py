"""Three alive targets, two cast gates and real outer entrant: one source AoE."""
from pathlib import Path
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.source_area_v1.build_modules import ROOT,BASES
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
COLD=ROOT/'packages/campaign/chapter06_cold/model.json'
CASES={'ordinary0':('ordinary',0,315,28,330),'ordinary1':('ordinary',1,620,87,495),'story':('story',0,480,87,900)}
def package(case):
 which,phase,start,frame,damage=CASES[case];p=json.loads((ROOT/'packages/campaign/chapter06_boss'/BASES[which][2]/'model.json').read_bytes());boss=p['entities'][0];burst=next(a['id'] for a in p['abilities'] if a['id'].endswith('/burst'+str(phase)) or (which=='story' and a['id'].endswith('/burst')))
 for e in boss['components']['ability_arbitration']['entries']:
  if e['ability']!=burst:e['condition']='False'
 p['manifest']['metadata']['probe_scope']='Only unrelatedarbitration disabled; retained source Burst initial/reset/frame/fullclock and exactstats. Ordinaryphase1 enters by publictrueHP0/rebirth, not manualphase.'
 move='ability/test/area/enter';freeze='ability/test/area/freeze';kill='ability/test/area/kill'
 p['rules'].append({'id':'rule/test/area/sp','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
 for alias in ['a','b','outer']:
  p['entities'].append({'id':'unit/test/area/'+alias,'kind':'entity','tags':['player','cold_receiver'], 'components':{'attributes':{'base':{'max_hp':1000000,'atk':0,'def':100,'mres':25,'block_count':0}},'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'},'sp':{'initial':0,'capacity':99,'recovery_rule':'rule/test/area/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[move]}})
 p['abilities'].append({'id':move,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':2,'col':5 if phase==1 or which=='story' else 4}}}]})
 p['entities'].append({'id':'unit/test/area/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':100000}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':[freeze,kill]}})
 p['selectors'].append({'id':'selector/test/area/players','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'},{'state':'alive'}],'limit':None})
 p['selectors'].append({'id':'selector/test/area/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'},{'state':'alive'}],'limit':1})
 p['abilities'].append({'id':freeze,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/area/players','timeline':[{'at':0,'effect':{'op':'buff_application','application_rule':'rule/ch6/cold/application','allowed':['buff/ch6/cold/e2c_cold','buff/ch6/cold/e2c_freeze'],'parameters':{'duration_seconds':10}}}]})
 p['abilities'].append({'id':kill,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/area/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
 p['scenarioDraft']={'id':'scene/source_area/'+case,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':9},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':boss['id'],'instanceAlias':'boss','position':{'row':2,'col':2}},*({'definition':'unit/test/area/'+alias,'instanceAlias':alias,'position':pos} for alias,pos in [('a',{'row':2,'col':3}),('b',{'row':3,'col':2}),('outer',{'row':2,'col':6})]),{'definition':'unit/test/area/controller','instanceAlias':'controller','position':{'row':4,'col':8}}]}
 if which=='ordinary':p['scenarioDraft']['branches']={'frstar_frosts':{'loop':False,'phases':[{'pre_delay_seconds':0,'actions':[]}]}}
 return p,burst,start,frame,damage
def create(case,frozen=False):
 p,burst,start,frame,damage=package(case);s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),providers=providers(),seed=6219)
 if case=='ordinary1':s.submit({'action':'skill','source':'controller','ability':'ability/test/area/kill'},at=5)
 s.submit({'action':'skill','source':'outer','ability':'ability/test/area/enter'},at=start+1)
 if frozen:
  for at in [start+3,start+4]:s.submit({'action':'skill','source':'controller','ability':'ability/test/area/freeze'},at=at)
 return s,burst,start,frame,damage
def ev(s,name):return [e for e in s.session.events if e['type']==name]
def check(s,burst,start,frame,damage,frozen=False):
 cast=next(e for e in ev(s,'ability.started') if e['payload']['ability']==burst);assert cast['time']==start and len(cast['payload']['targets'])==2
 areas=ev(s,'area.resolved');assert len(areas)==1 and areas[0]['time']==start+frame and len(areas[0]['payload']['members'])==3
 ps=[e for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')];assert len(ps)==3 and all(e['time']==start+frame and e['payload']['amount']==damage*(2 if frozen else 1) for e in ps)
 for alias in ['a','b','outer']:
  flags=s.ctx.spatial.selection_state(alias,DEFAULT_STATE)['abnormal_flags'];assert (16 in flags) if frozen else (23 in flags and 16 not in flags)
  assert s.ctx.resources.current(alias,'hp')==1000000-damage*(2 if frozen else 1) and s.ctx.resources.current(alias,'sp')==1
@pytest.mark.parametrize('case',CASES)
@pytest.mark.parametrize('frozen',[False,True])
def test_actual_once_area_three_packets_cold_or_pre_frozen_owned_multiplier(case,frozen):
 s,b,t,f,d=create(case,frozen);s.session.advance(t+f+1);check(s,b,t,f,d,frozen)
@pytest.mark.parametrize('case',CASES)
def test_actual_multigate_midcast_disk_cp_and_public_head(case,tmp_path):
 s,b,t,f,d=create(case);tick=t+10;s.session.advance(tick);p=tmp_path/'area.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h),providers=providers());s.session.advance(t+f+1-tick);r.session.advance(t+f+1-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot();check(s,b,t,f,d)
def test_actual_three_gate_targets_still_one_source_area():
 p,b,t,f,d=package('story');p['scenarioDraft']['initialEntities'][3]['position']={'row':2,'col':5}
 s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),providers=providers(),seed=6219);s.session.advance(t+f+1)
 cast=next(e for e in ev(s,'ability.started') if e['payload']['ability']==b);assert len(cast['payload']['targets'])==3 and len(ev(s,'area.resolved'))==1
 assert len([e for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')])==3
def test_source_target_override_does_not_bypass_original_requires_targets_gate():
 p,b,t,f,d=package('story')
 for u in p['entities']:
  if 'player' in u.get('tags',[]):u['components']['selection_state']['category']=2
 s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),providers=providers(),seed=6219);s.session.advance(t+f+1)
 assert not [e for e in ev(s,'ability.started') if e['payload']['ability']==b] and not ev(s,'area.resolved')
