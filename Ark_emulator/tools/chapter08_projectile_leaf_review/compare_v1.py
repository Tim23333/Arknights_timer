import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter08_projectile_leaf_independent_comparison_v1';OUT.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pdir=ROOT/'validation/campaign/chapter08_projectile_leaf_parent_peer_v3';cdir=ROOT/'validation/campaign/chapter08_projectile_leaf_candidate_peer_v3';a=json.loads((pdir/'captures.json').read_bytes());b=json.loads((cdir/'captures.json').read_bytes());rowsa={x['case']:x for x in a};rowsb={x['case']:x for x in b};parent_runtime=rowsa['retired_flight']['checkpoint']['runtime_fingerprint'];candidate_runtime=rowsb['retired_flight']['checkpoint']['runtime_fingerprint'];allowed=[];rejected=[];keys_checked=0
allowed_paths={'/checkpoint/runtime_fingerprint','/replay/runtime_fingerprint'}
def compare(x,y,path):
 global keys_checked
 keys_checked+=1
 if type(x)!=type(y):rejected.append(path);return
 if isinstance(x,dict):
  if list(x)!=list(y):rejected.append(path+'/dict_order');return
  for k in x:compare(x[k],y[k],path+'/'+k)
 elif isinstance(x,list):
  if len(x)!=len(y):rejected.append(path+'/length');return
  for i,(u,v) in enumerate(zip(x,y)):compare(u,v,path+'/'+str(i))
 elif x!=y:
  suffix=path.split(':',1)[1]
  if suffix in allowed_paths and x==parent_runtime and y==candidate_runtime:allowed.append(path)
  else:rejected.append(path)
for case in rowsa:compare(rowsa[case],rowsb[case],case+':')
assert not rejected,rejected[:30]
reports=[json.loads((folder/'verification.json').read_bytes()) for folder in (pdir,cdir)];assert all(r['guards_equal'] and all(c['outcome']=='passed' for c in r['cases']) for r in reports)
paths=[Path(__file__),pdir/'captures.json',cdir/'captures.json',pdir/'inputs.json',cdir/'inputs.json',pdir/'verification.json',cdir/'verification.json'];before={str(p):sha(p) for p in paths};after={str(p):sha(p) for p in paths};assert before==after
r={'passed':True,'parent_core':reports[0]['core'],'candidate_core':reports[1]['core'],'paired_common_cases':list(rowsa),'candidate_only_case':'component_view API deepimmutability/default/mappingpath/unknownentity/oldcachedview, absentAPI parent has no correspondingexecution and isnotfakecomparison','checked_nodes':keys_checked,'all_values_and_dict_insertion_orders_compared':True,'only_allowed_exact_identity_paths':allowed,'rejected_differences':rejected,'numeric_comparison':'Exact allfields includingeventcontext/value, amounts324.1700000000001 andcurrentATK stored unchanged, no rounding/tolerance in pairedcomparison. Source_math assertion separately usesabs1e-9 for mathematically324.17 acrossbothversions; oldv1/v2 exactbinaryfloatassert failures retained.','guard_reports':[{'path':str(folder/'verification.json'),'sha':sha(folder/'verification.json'),'guards_equal':True} for folder in (pdir,cdir)],'guards_start':before,'guards_end':after,'guards_equal':True,'scope':'Our ownnewdifferentlife9000/ATK421+initial200Buff/targetDEF137RES23/2.3speed/sourcewithdraw4/twoflight hits40,41,CP20/head60. Threecommonactualcaptures includefullsnapshot/checkpoint/events/replay; leafput version+1/order z,a,m/new andlatefaultRNG/jobs/events completeCP equality. No timing claim,no native7Rootcapture reuse, no whole/client/sourcebody allapproval.'};(OUT/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'sha':sha(OUT/'verification.json'),'checked_nodes':keys_checked,'allowed':allowed}))
