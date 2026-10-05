"""Bounded source aura/attack author cases, raw managed E only."""
import os,json,traceback,hashlib
from pathlib import Path
from copy import deepcopy
from tools.chapter10_remaining_v1.build import *
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter10_remaining_v1';OUT.mkdir(parents=True,exist_ok=True);LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();RESULT=[];FACT={};ART=[];CORE=implementation_digest();assert CORE=='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
NATIVE=ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json';native=json.loads(NATIVE.read_bytes());markraw=next(b for c in native['prefabs']['enemy_1220_dzoms']['components'].values() for b in c['raw'].get('_buffs',[]) if b['buffKey']=='enemy_bloodsucker_mark');mark={'id':MARK,'kind':'buff','metadata':{'native_inline':markraw,'native_owner':'enemy_1220_dzoms PassiveBuffAbility'}}
def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=41737)
def fixture(key,*,sources=1,members=0,normal=False):
 p=build(key,bloodsucker_mark=mark);body=p['entities'][0]['id'];p['buffs'].append({'id':'buff/peer/silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}});p['entities'][0]['dependencies']=['buff/peer/silence']
 if not normal:p['abilities'][0]['activation']['condition']='False'
 initial=[{'definition':body,'instanceAlias':'owner'+str(i),'position':{'row':2,'col':2+i}} for i in range(sources)]
 for i in range(members):
  eid='unit/peer/blood'+str(i);p['entities'].append({'id':eid,'kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':41737,'atk':1000,'def':683,'mres':39}},'resources':{'hp':{'role':'health','initial':41737,'capacity':41737}},'selection_state':{'side':1,'category':1,'motion':1,'unit_type':2},'spatial':{},'buffs':{'initial':[MARK]},'lifecycle':{'policy':'policy/ark_lifecycle'}}});initial.append({'definition':eid,'instanceAlias':'blood'+str(i),'position':{'row':7,'col':i}})
 p['scenarioDraft']={'id':'scene/peer/remaining/'+key,'ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':13},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial};bind_recipients(p);return p

def cpp(p,end,pins,label):
 a=create(p);a.advance(end);b=create(p)
 for t in pins:
  b.advance(t-b.session.time);path=LOG/(label+str(t)+'.checkpoint.json');h=write_ordered(path,b.checkpoint());ART.append({'path':str(path),'sha256':h,'bytes':path.stat().st_size});b=Engine.restore(b.program,load_bound(path,h),providers=REG)
 b.advance(end-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);return a

def lord():
 p=fixture('enemy_1226_dklord_2',members=7);s=create(p);s.advance(2);a=s.ctx.attributes.value('owner0','atk');FACT['lord7_probe']=a;assert a==3000
 for i in [0,1,2]:s.ctx.effects.execute('system/battle',[s.session.world.resolve('blood'+str(i))],{'op':'retire','parameters':{'reason':'withdraw'}})
 s.advance(1);a=s.ctx.attributes.value('owner0','atk');FACT['lord4_probe']=a;assert a==2400
 p['scenarioDraft']['scheduledEffects']=[{'at':3,'effect':{'op':'retire','target':3,'parameters':{'reason':'withdraw'}}}];q=cpp(p,7,[2,4],'lord');assert q.ctx.attributes.value('owner0','atk')==3000;FACT['lord_source_reverse_cap6_global_range_CPP']=True

def supply():
 p=fixture('enemy_1224_dsuply_2',sources=6,members=1);s=create(p);s.advance(2);atk=s.ctx.attributes.value('blood0','atk');FACT['supply6_probe']=atk;assert atk==1500
 for i in [0,1]:s.ctx.buffs.apply('system/battle','owner'+str(i),'buff/peer/silence')
 s.advance(1);assert s.ctx.attributes.value('blood0','atk')==1400
 s.ctx.buffs.remove('owner0','buff/peer/silence');s.advance(1);assert s.ctx.attributes.value('blood0','atk')==1500;FACT['supply_cap5_actual_silence_detach_restore']=True

def eligibility():
 p=fixture('enemy_1226_dklord_2',members=4);p['entities'][2]['components']['selection_state']['motion']=2;p['entities'][3]['components']['selection_state']['side']=0;p['entities'][4]['components']['buffs']['initial']=[];s=create(p);s.advance(2);FACT['eligibility_probe']=s.ctx.attributes.value('owner0','atk');assert FACT['eligibility_probe']==1500;FACT['global_aura_ground_ally_actual_mark_only']=True

def normal():
 p=fixture('enemy_1224_dsuply_2',normal=True);p['entities'].append({'id':'unit/peer/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':17771,'atk':0,'def':137,'mres':35}},'resources':{'hp':{'role':'health','initial':17771,'capacity':17771}},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/target','instanceAlias':'target','position':{'row':2,'col':3}});s=cpp(p,38,[12,14],'normal');events=[thaw(x) for x in s.session.events if x['type'] in ['ability.started','projectile.launched','damage.accepted']];FACT['normal_probe']={'events':events,'HP':s.ctx.resources.current('target','hp')};hit=next(e for e in events if e['type']=='damage.accepted');start=next(e for e in events if e['type']=='ability.started');launch=next(e for e in events if e['type']=='projectile.launched');assert launch['time']-start['time']==13;assert hit['payload']['amount']==283 and s.ctx.resources.current('target','hp')==17488;FACT['source_frame13_speed10_physical420_DEF137_CPP']=True

def rejection():
 for key,kwargs,reason in [('enemy_1225_dkmage_2',{},'ChainLightning'),('enemy_1226_dklord_2',{},'bloodsucker mark'),('enemy_1226_dklord_2',{'bloodsucker_mark':mark,'require_complete':True},'deathrattle')]:
  try:build(key,**kwargs)
  except ValueError as e:assert reason in str(e)
  else:raise AssertionError('source dependency silently omitted')
 FACT['missing_chain_mark_deathrattle_refused']=True

def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE,NATIVE,Path(__file__),Path(__file__).with_name('build.py')]}
BEFORE=guard()
for name,fn in [('lord_reverse_attack_cap6_CPP',lord),('supply_stack_cap5_and_silence',supply),('actual_native_aura_masks',eligibility),('native_ranged_hitframe13_CPP',normal),('strict_missing_source_dependencies',rejection)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'whole_stage':False};(OUT/'author.actual.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'results':RESULT,'actual_exit':r['actual_exit']}));raise SystemExit(r['actual_exit'])
