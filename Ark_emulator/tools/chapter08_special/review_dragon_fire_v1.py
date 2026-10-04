"""Fresh independent source-policy counters and corrected-rule public CP/head gate."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.dragon_fire_policies_v2 import providers as old_registry
from tools.chapter08_boss.dragon_fire_policies_v3 import providers as new_registry
BASE=ROOT/'packages/campaign/chapter08_consumers/boss';OUT=ROOT/'packages/campaign/chapter08_consumers/special/dragon_fire_independent_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def package(version,multiplier=1):
 path=BASE/f'dragon_fire.module.v{version}.json';p=json.loads(path.read_bytes());timer,child=[b['id'] for b in p['buffs']];application=next(r['id'] for r in p['rules'] if r['contract']=='buff.application')
 p['manifest']['metadata']['independent_fixture']='Fresh two/three actor source-controlled scene; no author fixture/expected imported; source1500 and target20000/DEF1234/MRES94.'
 source='unit/peer/ch8/fire/source';target='unit/peer/ch8/fire/target';aid='ability/peer/ch8/fire/apply';sid='selector/peer/ch8/fire/target'
 p['entities']=[{'id':source,'kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':50000,'atk':1500}},'resources':{'hp':{'initial':50000,'capacity':50000,'role':'health'}},'spatial':{},'abilities':[aid],'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':target,'kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':20000,'atk':0,'def':1234,'mres':94,'one_minus_status_resistance':multiplier}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
 p['selectors']=[{'id':sid,'kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}],'limit':1}];p['abilities']=[{'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'manual','on_start':[{'op':'buff_application','application_rule':application,'allowed':[timer,child]}]},'timeline':[]}]
 p['scenarioDraft']={'id':'scene/peer/ch8/fire/v'+str(version),'ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':2},'objectives':{},'initialEntities':[{'definition':source,'instanceAlias':'source','position':{'row':0,'col':0}},{'definition':target,'instanceAlias':'target','position':{'row':0,'col':1}}]};return p,timer,child,aid
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def run(case,version,commands,split,end,multiplier=1,second=False):
 p,timer,child,aid=package(version,multiplier);reg=old_registry() if version==2 else new_registry()
 if second:p['scenarioDraft']['initialEntities'].append({'definition':p['entities'][0]['id'],'instanceAlias':'second','position':{'row':1,'col':0}})
 s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=8019)
 for source,tick in commands:s.submit({'action':'skill','source':source,'ability':aid},at=tick)
 folder=OUT/case;folder.mkdir(parents=True,exist_ok=True);s.session.advance(split);cp=folder/'checkpoint.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h),providers=reg);s.session.advance(end-split);r.session.advance(end-split);head=replay(s.program,s.export_replay(),providers=reg)
 assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];instances=s.ctx.get('target',('buffs','instances'),[])
 result={'version':version,'runtime':implementation_digest(),'split':split,'end':end,'cp_equal':True,'head_equal':True,'full_events_equal':True,'hits':[(e['time'],e['payload']['amount']) for e in hits],'target_hp':s.ctx.resources.current('target','hp'),'buffs':thaw(instances),'timer_applied':[(e['time'],e['payload']['instance']) for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==timer],'child_applied':[(e['time'],e['payload']['instance']) for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==child]}
 (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
 with (folder/'events.jsonl').open('wb') as f:
  for event in s.session.events:f.write((json.dumps(thaw(event),ensure_ascii=False,separators=(',',':'))+'\n').encode())
 result['pins']={str(q):sha(q) for q in folder.iterdir() if q.is_file()};return result
def main():
 paths=[BASE/f'dragon_fire.module.v{i}.json' for i in (1,2,3)]+[ROOT/'tools/chapter08_boss'/f'dragon_fire_policies_v{i}.py' for i in (1,2,3)];before={str(p):sha(p) for p in paths};OUT.mkdir(exist_ok=True);rows={}
 rows['old_repeat']=run('old_repeat',2,[('source',0),('source',100)],90,1020);assert rows['old_repeat']['hits'][-1]==(900,230) and len(rows['old_repeat']['timer_applied'])==1
 rows['old_gap']=run('old_gap',2,[('source',0),('source',930)],900,1030);assert rows['old_gap']['hits'][-3:]==[(930,230),(960,230),(990,230)]
 rows['new_repeat']=run('new_repeat',3,[('source',0),('source',100)],90,1020);assert rows['new_repeat']['hits']==[(n*30,50+6*n) for n in range(1,31)]+[(930,230),(960,230),(990,230)]
 rows['new_gap']=run('new_gap',3,[('source',0),('source',930)],920,1030);assert rows['new_gap']['hits'][-3:]==[(960,56),(990,62),(1020,68)] and rows['new_gap']['child_applied'][0][1]==rows['new_gap']['child_applied'][1][1]
 rows['new_half_resistance']=run('new_half_resistance',3,[('source',0),('source',100)],90,580,.5);assert len(rows['new_half_resistance']['hits'])==18 and rows['new_half_resistance']['hits'][-1]==(540,158)
 rows['new_second_source']=run('new_second_source',3,[('source',0),('second',100)],120,300,second=True);assert len(rows['new_second_source']['buffs'])==2 and len(rows['new_second_source']['child_applied'])==1
 assert before=={str(p):sha(p) for p in paths};result={'status':'passed_corrected_source_policy_gate','runtime':implementation_digest(),'module_v3_sha256':sha(BASE/'dragon_fire.module.v3.json'),'source_guards_before':before,'source_guards_after':before,'cases':rows,'independent_fixture':True,'old_actual_required_policy_conflicts_retained':True,'no_fullboss_or_stage_gate':True,'first_packet_phase':'56 is tested declared reference, native body still unverified','child_phase_reset':'Same retained child identity refresh/restart after timer gap is tested reference translation; original BsonIfNot does not create it again. Native reset/phase body remains explicit','dynamic_remaining_duration':'Not proved; initial Attribute26 only','whole_stage_executed':False,'client_verified':False};out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(out),'path':str(out),'cases':len(rows)}))
if __name__=='__main__':main()
