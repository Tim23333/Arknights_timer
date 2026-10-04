"""Bounded <=300tick actual content retention census; no live process touched."""
import sys,json,hashlib,time,gc,os,argparse,struct
from pathlib import Path
from collections import Counter
from collections.abc import Mapping
import psutil
ROOT=Path(__file__).resolve().parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def measure(root):
 seen=set();sizes=0;types=Counter();string_bytes=0;string_ids=set();string_values=set();memo={};structural=set();serialized_occurrences=0
 def add(v):
  nonlocal sizes,string_bytes
  ident=id(v)
  if ident in seen:return
  seen.add(ident);sizes+=sys.getsizeof(v);types[type(v).__name__]+=1
  if isinstance(v,str):string_bytes+=sys.getsizeof(v);string_ids.add(ident);string_values.add(v)
 def walk(v):
  add(v)
  if not isinstance(v,(Mapping,list,tuple)):
   raw=json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8');kind=type(v).__name__.encode();return len(raw),hashlib.sha256(kind+b':'+raw).digest(),0
  ident=id(v)
  if ident in memo:return memo[ident]
  if isinstance(v,Mapping):
   proxy=getattr(v,'_data',None)
   if proxy is not None:
    add(proxy)
    for internal in gc.get_referents(proxy):
     if isinstance(internal,dict):add(internal)
   digest=hashlib.sha256(b'map');length=2;occurrences=1
   for index,key in enumerate(v):
    add(key);key_raw=json.dumps(key,ensure_ascii=False,allow_nan=False).encode('utf8');child_length,child_hash,child_occ=walk(v[key]);length+=len(key_raw)+1+child_length+(1 if index else 0);occurrences+=child_occ;digest.update(struct.pack('>Q',len(key_raw)));digest.update(key_raw);digest.update(child_hash)
  else:
   digest=hashlib.sha256(b'array');length=2;occurrences=1
   for index,item in enumerate(v):
    n,h,c=walk(item);length+=n+(1 if index else 0);occurrences+=c;digest.update(h)
  fingerprint=digest.digest();structural.add(fingerprint);memo[ident]=(length,fingerprint,occurrences);return memo[ident]
 length,digest,occurrences=walk(root)
 return {'unique_retained_objects':len(seen),'unique_json_container_identities':len(memo),'unique_structural_containers_ordered_typed':len(structural),'serialized_container_occurrences':occurrences,'serialized_compact_utf8_bytes':length,'estimated_retained_shallow_bytes_including_mapping_backings':sizes,'object_types':dict(types),'unique_string_objects':len(string_ids),'unique_string_values':len(string_values),'retained_string_shallow_bytes':string_bytes,'ordered_typed_payload_structure_hash':digest.hex(),'scope':'event journal object graph only; shallow retained estimate, not allocator/RSS or World/program; repeated serialized subtrees fully counted'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--commands',type=Path,required=True);ap.add_argument('--expected-core',required=True);ap.add_argument('--max-ticks',type=int,default=300);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert 0<a.max_ticks<=300;runtime=a.runtime.resolve();sys.path.insert(0,str(runtime))
 import ark_sim
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim' and implementation_digest()==a.expected_core
 guarded=[a.package,a.commands,Path(__file__),runtime/'ark_sim/rules/contracts.json',runtime/'ark_sim/content/presets/ark_standard.json'];locks={str(p.resolve()):sha(p) for p in guarded};p=json.loads(a.package.read_bytes());commands=json.loads(a.commands.read_bytes());scene=p['scenarioDraft'];process=psutil.Process();start=time.time();s=Engine.create(Compiler().compile(p),seed=scene.get('seed',0));
 for command in commands:
  c=dict(command);tick=c.pop('at');s.submit(c,at=tick)
 points=[]
 for tick in sorted(set([0,min(100,a.max_ticks),min(200,a.max_ticks),a.max_ticks])):
  begun=time.time();s.advance(tick-s.session.time);gc.collect();rss=process.memory_info().rss;private=getattr(process.memory_info(),'private',None);counts=Counter(e['type'] for e in s.session.events);measured=measure(s.session._events._records);gc.collect();point={'tick':tick,'simulation_seconds':time.time()-begun,'rss_before_census':rss,'private_before_census':private,'rss_after_census':process.memory_info().rss,'event_count':len(s.session.events),'event_types':dict(counts),'journal_census':measured};points.append(point);print(json.dumps({'tick':tick,'events':point['event_count'],'rss':rss,'retained_estimate':measured['estimated_retained_shallow_bytes_including_mapping_backings'],'unique_containers':measured['unique_json_container_identities'],'structural_containers':measured['unique_structural_containers_ordered_typed']}),flush=True)
 assert {str(p.resolve()):sha(p) for p in guarded}==locks and implementation_digest()==a.expected_core
 report={'schema':'ark-sim/m27-storage-retention-census/v1','passed':True,'scope':'bounded actual package/commands; no fullstage/accuracy/CP proof','actual_module':ark_sim.__file__,'core_start':a.expected_core,'core_end':implementation_digest(),'package_sha256':sha(a.package),'commands_sha256':sha(a.commands),'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'points':points,'source_locks':locks,'elapsed_seconds':time.time()-start,'events_dropped':False,'trace_sampling_changed':False,'live_process_touched':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha256':sha(a.output)}),flush=True)
if __name__=='__main__':main()
