"""Three durable public proofs using immutable event references for comparisons."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_special.test_author_v3 import package,make,ability,fixed_damage,packets
from tools.chapter08_special.policies_v2 import providers
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'packages/campaign/chapter08_consumers/special'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def state(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'random':s.session.random.snapshot(),'time':s.session.time}
def main():
 guarded=[OUT/n for n in ['source.closure.v1.json','emppnt.module.v3.json','empace.module.v3.json']]+[Path(__file__),Path(__file__).with_name('policies_v2.py')];before={str(p):sha(p) for p in guarded};rows=[];core=implementation_digest();assert core=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
 for name,case,split,end in [('emppnt','retained_source',12,105),('empace','half_threshold',6,160),('empace','flight',32,40)]:
  p=package(name,name=='empace' and case=='half_threshold');s=make(p)
  if case=='retained_source':
   a=ability(p,'retire',{'op':'retire','parameters':{'reason':'controlled_source_retire'}});s=make(p);s.submit({'action':'skill','source':'near','ability':a},at=11)
  elif case=='half_threshold':
   a=fixed_damage(p,6000);s=make(p);s.submit({'action':'skill','source':'near','ability':a},at=5)
  folder=OUT/('durable_'+case+'_v1');folder.mkdir(exist_ok=True);s.session.advance(split);cp=folder/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=providers());s.session.advance(end-split);r.session.advance(end-split);h=replay(s.program,s.export_replay(),providers=providers())
  assert state(s)==state(r)==state(h);assert tuple(s.session.events)==tuple(r.session.events)==tuple(h.session.events)
  (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
  stream=folder/'events.jsonl'
  with stream.open('wb') as f:
   for event in s.session.events:f.write((json.dumps(thaw(event),ensure_ascii=False,separators=(',',':'))+'\n').encode())
  rows.append({'name':name,'case':case,'split':split,'end':end,'cp_equal':True,'head_equal':True,'state_domains':['World','scheduler','RNG','time'],'full_events_equal':True,'events':len(s.session.events),'packets':[(e['time'],e['payload'].get('target'),e['payload']['amount']) for e in packets(s)],'files':{str(q):sha(q) for q in folder.iterdir() if q.is_file()}})
 after={str(p):sha(p) for p in guarded};assert before==after and implementation_digest()==core;result={'status':'passed','runtime_sha256':core,'guards_before':before,'guards_after':after,'guards_equal':True,'cases':rows,'event_comparison':'Tuple of original immutable event objects; only one record at a time thawed to JSONL. No three full event snapshot copies.','whole_stage_executed':False,'independent_reviewed':False,'client_verified':False};out=OUT/'durable.proofs.v1.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'cases':len(rows)}))
if __name__=='__main__':main()
