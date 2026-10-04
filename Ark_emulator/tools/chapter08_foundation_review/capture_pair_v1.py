import argparse,sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--core',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,str(a.runtime.resolve()));sys.path.insert(1,str(ROOT))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.contracts import thaw
 from ark_sim.tools.replay import replay
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.chapter08_foundation_review.fixtures_v1 import package,effect
 assert implementation_digest()==a.core;out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);records=[]
 def semantic(v):
  if hasattr(v,'view'):return {'actual_immutable_view':thaw(v.view)}
  if isinstance(v,dict):return {k:semantic(x) for k,x in v.items()}
  if isinstance(v,(list,tuple)):return [semantic(x) for x in v]
  return v
 def capture(s):
  # All memoized results, context/cache traces and dictionary order remain included.
  s.ctx.attributes.value('source','atk');s.ctx.attributes.value('source','atk')
  return {'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'replay':s.export_replay(),'world_cached_views':{str(k):[ver,thaw(view)] for k,(ver,view) in s.session.world._views.items()},'attribute_cache_entries':[[semantic(k),semantic(thaw(v))] for k,v in s.ctx.attributes.cache.items()],'attribute_cache_time':s.ctx.attributes._cache_time,'attribute_cache_epoch':s.ctx.attributes._cache_epoch,'kernel_cache_epoch':s.session._cache_epoch}
 for name,fault,upgrade in [('positive',False,False),('upgrade',False,True),('latefault',True,True)]:
  p=package(fault,upgrade);pr=Compiler().compile(p);s=Engine.create(pr,seed=91947);s.submit({'action':'skill','source':'director','ability':'ability/peer/foundation/kill'},at=6)
  if not fault:s.submit({'action':'skill','source':'director','ability':'ability/peer/foundation/retire'},at=53)
  s.advance(13);cp=s.checkpoint();f=out/(name+'.cp.json');pin=write_ordered(f,cp)
  if fault:
   try:s.advance(10)
   except Exception:pass
   assert s.ctx.state()['timeline']['members']['3']['wave']==1 and s.checkpoint()['kernel']['failure'] is not None;record=capture(s);record['failed_replay_not_executed']=True
  else:
   r=Engine.restore(pr,load_bound(f,pin));s.advance(52);r.advance(52);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay()).checkpoint();record=capture(s);record['disk_head_equal']=True
  record['name']=name;record['input']=p;record['actual_program_fingerprint']=pr.fingerprint;record['actual_runtime_fingerprint']=s.runtime_fingerprint;records.append(record)
 f=out/'capture.json';f.write_text(json.dumps({'core':a.core,'cases':records},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(hashlib.sha256(f.read_bytes()).hexdigest())
if __name__=='__main__':main()
