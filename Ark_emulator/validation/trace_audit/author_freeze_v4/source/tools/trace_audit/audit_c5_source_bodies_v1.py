"""Separate source-body layer on sealed5-9; static base-write candidates stay pending."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.body_binding_v1 import audit
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 original=Path('E:/ArkSimEvidence/campaign/05_09_8fa4e36752e92f7d/public_v1.original.json');r=json.loads(original.read_bytes());assert r['process_complete'];journal=Path(r['journal']['path']);package=ROOT/'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-09.life99999.json';helper=ROOT/'tools/trace_audit/body_binding_v1.py';p=json.loads(package.read_bytes());before={str(x):sha(x) for x in (original,journal,package,helper,Path(__file__))};assert before[str(journal)]==r['journal']['sha256'] and before[str(package)]==r['package_sha256'];ops=Counter();candidates=[]
 def walk(v,path):
  if isinstance(v,dict):
   if 'op' in v:ops[v['op']]+=1
   if v.get('op') in ('set','set_component','modify_attribute','set_attribute') or (isinstance(v.get('path'),list) and 'base' in v['path']):candidates.append({'path':path,'data':v})
   for k,item in v.items():walk(item,path+'/'+k)
  elif isinstance(v,list):
   for i,item in enumerate(v):walk(item,path+'/'+str(i))
 walk(p,'');assert not candidates,'Review explicit mutable base operations before asserting static source equality'
 result=audit(journal,p);after={str(x):sha(x) for x in (original,journal,package,helper,Path(__file__))};assert before==after;result.update({'source_original_report':str(original),'journal':r['journal'],'source_at_start':before,'source_at_end':after,'source_identity_stable':True,'static_content_effect_operations':dict(ops),'explicit_base_write_candidates':candidates,'static_scan_scope':'Explicit content effect ops/paths only. Dynamic implementation/context base edits outside this layer remain pending, never auto-approved.','complete_actual_trace_read':True,'client_verified':False});out=ROOT/'validation/trace_audit/05-09.sealed_original.body_binding_v1.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'passed':result['passed'],'counts':result['counts'],'pending':result['pending_fields'],'failures':result['failures'][:5]}));raise SystemExit(0 if result['passed'] else 1)
if __name__=='__main__':main()
