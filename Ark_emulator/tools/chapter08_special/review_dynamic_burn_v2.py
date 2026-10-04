"""New-core independent source-clock proof, without reusing old-core green identity."""
import hashlib,json,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_lifetime_v3_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.dragon_fire_policies_v3 import providers as fire
from tools.chapter08_buff_lifetime.policies_v1 import providers as life
from tools.campaign_content_composition_v2 import compose_modules
CORE='da6ba0da3a469768b254ad89585b969f8ed761cb62f0c3eddfce840b854ff19c';MODULE=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v7.dynamic.json';OUT=ROOT/'packages/campaign/chapter08_consumers/special/dynamic_burn_independent_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def registry():return {**fire(),**life()}
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def package(multiplier=1):
 p=json.loads(MODULE.read_bytes());timer,child=[b['id'] for b in p['buffs']];apply=next(r['id'] for r in p['rules'] if r['contract']=='buff.application');aid='ability/peer/dynamic/fire';sid='selector/peer/dynamic/player';source='unit/peer/dynamic/source';target='unit/peer/dynamic/target'
 p['entities']=[{'id':source,'kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':50000,'atk':1500}},'resources':{'hp':{'initial':50000,'capacity':50000,'role':'health'}},'spatial':{},'abilities':[aid],'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':target,'kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':20000,'atk':0,'def':1234,'mres':91,'one_minus_status_resistance':multiplier}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
 p['selectors']=[{'id':sid,'kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}]}];p['abilities']=[{'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'manual','on_start':[{'op':'buff_application','application_rule':apply,'allowed':[timer,child]}]},'timeline':[]}]
 p['buffs'].append({'id':'buff/peer/dynamic/resistance','kind':'buff','modifiers':[{'attribute':'one_minus_status_resistance','layer':'final_ratio','value':-.5}]});p['entities'][0]['components']['abilities'] += ['ability/peer/dynamic/add','ability/peer/dynamic/remove']
 for name,op in [('add','apply_buff'),('remove','remove_buff')]:p['abilities'].append({'id':'ability/peer/dynamic/'+name,'kind':'ability','selector':sid,'activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':op,'buff':'buff/peer/dynamic/resistance'}}]})
 p['scenarioDraft']={'id':'scene/peer/dynamic/source','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':3},'objectives':{},'initialEntities':[{'definition':source,'instanceAlias':'source','position':{'row':0,'col':0}},{'definition':target,'instanceAlias':'target','position':{'row':2,'col':2}}]};return p,timer,child,aid
def run(label,multiplier,commands,split,end,expected_remove,expected_hits,initial_half=False):
 p,timer,child,aid=package(multiplier);
 if initial_half:p['entities'][1]['components']['buffs']={'initial':['buff/peer/dynamic/resistance']}
 reg=registry();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=8026)
 for name,tick in commands:s.submit({'action':'skill','source':'source','ability':aid if name=='fire' else 'ability/peer/dynamic/'+name},at=tick)
 folder=OUT/label;folder.mkdir(parents=True,exist_ok=True);s.session.advance(split);cp=folder/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg);s.session.advance(end-split);r.session.advance(end-split);h=replay(s.program,s.export_replay(),providers=reg);assert domain(s)==domain(r)==domain(h) and tuple(s.session.events)==tuple(r.session.events)==tuple(h.session.events)
 removed=[e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==timer];hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted'];assert removed==expected_remove and hits==expected_hits,(label,removed,hits)
 (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
 with (folder/'events.jsonl').open('wb') as f:
  for event in s.session.events:f.write((json.dumps(thaw(event),ensure_ascii=False,separators=(',',':'))+'\n').encode())
 return {'label':label,'split':split,'end':end,'timer_removed':removed,'hits':hits,'target_hp':s.ctx.resources.current('target','hp'),'CP':True,'head':True,'all_events':True,'files':{str(p):sha(p) for p in folder.iterdir() if p.is_file()}}
def main():
 assert implementation_digest()==CORE;before=sha(MODULE);OUT.mkdir(exist_ok=True);rows=[]
 rows.append(run('midlife300_to608',1,[('fire',0),('add',300)],301,620,[608],[(30*n,50+6*n) for n in range(1,21)]))
 rows.append(run('restore_at150_to765',1,[('fire',0),('remove',150)],151,780,[765],[(30*n,50+6*n) for n in range(1,26)],initial_half=True))
 rows.append(run('refresh_native_duration',1,[('fire',0),('add',300),('fire',400)],401,875,[858],[(30*n,50+6*n) for n in range(1,29)]))
 rows.append(run('gap_reset_same_child',1,[('fire',0),('fire',930)],920,1030, [915],[(30*n,50+6*n) for n in range(1,31)]+[(960,56),(990,62),(1020,68)]))
 rows.append(run('minimum0_clamp',0,[('fire',0)],1,35,[1],[]))
 assert before==sha(MODULE) and implementation_digest()==CORE;result={'status':'passed','core':CORE,'module_sha256':before,'source_after':sha(MODULE),'cases':rows,'first_packet_and_refresh_model_phase':'Reference policy checked; native subframe/body unverified','new_identity_execution':True,'old3992_counters_preserved':True,'whole_stage_executed':False,'client_verified':False};out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'cases':len(rows)}))
if __name__=='__main__':main()
