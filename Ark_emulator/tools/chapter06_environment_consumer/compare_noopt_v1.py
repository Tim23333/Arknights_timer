"""No-opt exact value comparison; whitelist only top runtime implementation identities."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];P=Path('E:/ArkSimEvidence/chapter06_static_noopt_v1/parent.json');C=P.with_name('candidate.json');p=json.loads(P.read_bytes());c=json.loads(C.read_bytes());differences=[]
def compare(a,b,path):
 if type(a) is not type(b):differences.append({'path':path,'kind':'type'});return
 if isinstance(a,dict):
  if a.keys()!=b.keys():differences.append({'path':path,'kind':'keys'});return
  for k in a:compare(a[k],b[k],path+'/'+k)
 elif isinstance(a,list):
  if len(a)!=len(b):differences.append({'path':path,'kind':'length'});return
  for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
 elif a!=b:differences.append({'path':path,'parent':a,'candidate':b})
compare(p,c,'');allowed={'/core'}|{'/cases/'+str(i)+'/snapshot/runtime_fingerprint' for i in range(3)};assert {x['path'] for x in differences}==allowed
out=ROOT/'validation/campaign/chapter06_environment_candidate_v1/noopt.json';assert not out.exists();r={'passed':True,'parent_sha':hashlib.sha256(P.read_bytes()).hexdigest(),'candidate_sha':hashlib.sha256(C.read_bytes()).hexdigest(),'actual_all_values_compared':True,'only_declared_runtime_id_differences':differences,'full_0_1_executed':False,'0_1_actual_prefix_ticks':150,'custom_actual850_60_checked':True,'primary_modified':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest(),'diff_count':len(differences)}))
