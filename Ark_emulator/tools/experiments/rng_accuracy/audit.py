"""Offline RNG source/implementation audit. No reader/service/device is opened."""
import ast,json,hashlib,re,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];LIVE=ROOT.parent/'tools/ak_live_rng';sys.path.insert(0,str(LIVE));sys.path.insert(1,str(ROOT))
from rng_engines import DotNetRandom,MBIG,recover_advanced
from tracker import EngineTracker
from ark_sim.kernel.random import RandomStreams
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def record(path):return {'path':str(path.resolve()),'sha256':sha(path)}
def source_extract(path,needle):
 text=path.read_text(encoding='utf8');i=text.index(needle);start=text.rfind('// Namespace:',0,i);end=text.find('// Namespace:',i);return {'source':record(path),'line':text[:i].count('\n')+1,'text':text[start:end if end!=-1 else len(text)]}
def independent_step(seeds,i,p):
 seeds=list(seeds);i=i+1 if i<55 else 1;p=p+1 if p<55 else 1;raw=seeds[i]-seeds[p]
 if raw==2147483647:raw-=1
 if raw<0:raw+=2147483647
 seeds[i]=raw;return seeds,i,p,raw
class FakeReader:
 def __init__(self,state):self.state=state
 def read(self,addr,size):return struct.pack('<56i',*self.state.seeds) if addr==100 else struct.pack('<ii',self.state.inext,self.state.inextp)
 def read_many(self,requests):return [self.read(a,s) for a,s in requests]
def main():
 files=[ROOT/'ark_sim/kernel/random.py',ROOT/'ark_sim/kernel/session.py',ROOT/'ark_sim/adapters/api.py',ROOT/'ark_sim/tools/replay.py',LIVE/'rng_engines.py',LIVE/'tracker.py',LIVE/'rng_service.py',LIVE/'memscan.py',LIVE/'README.md',ROOT.parent/'Ark_data/dump.cs',ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs'];start_locks={str(p):sha(p) for p in files};excerpts=[]
 for dump in files[-2:]:
  text=dump.read_text(encoding='utf8')
  for needle in ['public class LegacyRandom :','public interface IBattleRandom','public class BattleRandomWrapper','public static class BattleRandomFactory','public static class RandomFactory','private static IBattleRandom s_randomImp']:
   if needle in text:excerpts.append(source_extract(dump,needle))
 v2=RandomStreams(0);mt_values=[v2.sample('imp') for _ in range(3)];standard=DotNetRandom(0);knuth_raw=[standard.next_int() for _ in range(3)];assert knuth_raw==[1559595546,1755192844,1649316166];assert mt_values!=[x/MBIG for x in knuth_raw]
 # Explicit synthetic captured-state recurrence; no native constructor claim.
 synthetic=[0]+[(i*123457)%MBIG for i in range(1,56)];state=DotNetRandom(seeds=synthetic,inext=0,inextp=31);a=synthetic;i=0;p=31;values=[]
 for _ in range(120):
  a,i,p,raw=independent_step(a,i,p);assert raw==state.next_int() and a==state.seeds and (i,p)==(state.inext,state.inextp);values.append(raw)
 prior=DotNetRandom(0);expected=prior.clone();raw=expected.next_int();different=DotNetRandom(seeds=expected.seeds,inext=expected.inext,inextp=32);recovered=recover_advanced(prior,EngineTracker._observed_key(different),max_steps=1);assert recovered==(1,[raw]) and not EngineTracker._same_state(expected,different)
 reader=FakeReader(prior);tracker=EngineTracker(reader,{'kind':'knuth','array':100,'cursor_addr':200});assert tracker.poll()==[];reader.state=different;accepted=tracker.poll();assert len(accepted)==1 and tracker.state.inextp==32 and tracker.status=='ok'
 calls=[]
 for path in [ROOT/'ark_sim/domains/lifecycle.py',ROOT/'ark_sim/domains/movement.py',ROOT/'ark_sim/domains/effects.py']:
  tree=ast.parse(path.read_text(encoding='utf8'))
  for node in ast.walk(tree):
   if isinstance(node,ast.Call) and ast.unparse(node.func).endswith('random.sample'):calls.append({'source':record(path),'line':node.lineno,'actual_call':ast.unparse(node)})
 consumers=[]
 paths=[ROOT/'packages/campaign/talents.attack.json',ROOT/'packages/campaign/talents.support.json',ROOT/'packages/campaign/mainline_models/level_main_00-10.m14_timeline.json']
 def scan(value,path,pointer=''):
  if isinstance(value,dict):
   for key,v in value.items():
    if key in ('stream','random_stream') and isinstance(v,str):consumers.append({'source':record(path),'pointer':pointer+'/'+key,'configured_model_stream':v,'native_stream_mapping':'unproven; name alone is not call-site evidence'})
    scan(v,path,pointer+'/'+key)
  elif isinstance(value,list):
   for i,v in enumerate(value):scan(v,path,pointer+'/'+str(i))
 for path in paths:scan(json.loads(path.read_bytes()),path)
 report={'schema':'ark-sim/rng-accuracy-source-audit/v1','status':'source_audit_with_accuracy_blockers','offline_assertions_passed':True,'client_accuracy_verified':False,'device_access_performed':False,'primary_implementation':implementation_digest(),'source_locks':start_locks,'source_declarations':excerpts,'v2_actual_sample_calls':calls,'content_model_stream_consumers':consumers,'algorithm_divergence_synthetic_seed0':{'v2_profile':v2.algorithm,'v2_imp_values':mt_values,'dotnet_compatibility_ctor21_raw':knuth_raw,'dotnet_compatibility_ctor21_values':[x/MBIG for x in knuth_raw],'scope':'different algorithm/profile; neither this seed constructor nor seed0 claimed as actual-game initialization'},'snapshot31_recurrence_synthetic':{'initial_seeds':synthetic,'initial_cursors':[0,31],'steps':120,'first_raw_values':values[:8],'final_state':{'seeds':state.seeds,'inext':state.inext,'inextp':state.inextp},'independent_recurrence_equal':True,'native_snapshot':False},'tracker_missing_second_cursor_counterexample':{'prior_state':{'seeds':prior.seeds,'inext':0,'inextp':21},'predicted_endpoint':{'seeds':expected.seeds,'inext':1,'inextp':22},'different_observation':{'seeds':different.seeds,'inext':1,'inextp':32},'accepted_recovery':recovered,'fake_tracker_poll_output':accepted,'tracker_status':tracker.status,'full_endpoint_equal':False,'synthetic_memory_only':True},'raw_snapshot_export_gap':'tracker/service snapshot exposes cursors and rounded history/predictions, not complete seed array/backend state; these UI snapshots cannot initialize a validated RNG backend','accuracy_blockers':['actual native seed constructor/factory bodies unknown','native RNG operation to raw draw budget/float conversion unknown','imp/trivial mapping for each spawn/targeting/talent/packet call unproven','31 cursor observation currently source-comment claim, no raw historical live snapshot fixture supplied in this audit','full backend state and version-bound episode origin required; tracker endpoint omits second cursor','physical stream aliasing cannot be modeled as independent SHA-derived streams'],'formal_approval':False}
 assert {str(p):sha(p) for p in files}==start_locks
 out=ROOT/'validation/campaign/rng_accuracy/source_audit.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'offline_assertions_passed':True,'device_access':False,'actual_sample_calls':len(calls),'content_stream_refs':len(consumers),'tracker_counterexample_reproduced':True,'report_sha256':sha(out)}))
if __name__=='__main__':main()
