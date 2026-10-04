"""Full actual0-1/custom deep comparison; only named fingerprint paths may differ."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter05_ballista_v1';BASE=Path('E:/ArkSimEvidence/ballista_noopt_v1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 parent=BASE/'parent_v5.full.json';candidate=BASE/'ballista_v1.full.json';a=json.loads(parent.read_bytes());b=json.loads(candidate.read_bytes());assert a['core']=='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90' and b['core']=='49af646affbd800b2d65a25634700deb1444fcbc3e0d886516ad9509edab217b';diffs=[]
 def compare(x,y,path):
  if isinstance(x,dict) and isinstance(y,dict):
   assert x.keys()==y.keys(),path
   for key in x:
    if key in ('runtime_fingerprint','program_fingerprint') and x[key]!=y[key]:diffs.append({'path':path+'/'+key,'old':x[key],'new':y[key]})
    else:compare(x[key],y[key],path+'/'+key)
  elif isinstance(x,list) and isinstance(y,list):
   assert len(x)==len(y),path
   for i,(xx,yy) in enumerate(zip(x,y)):compare(xx,yy,path+'/'+str(i))
  else:assert type(x)==type(y) and x==y,path+': '+repr(x)[:150]+' != '+repr(y)[:150]
 assert len(a['cases'])==len(b['cases'])==3;compare(a['cases'],b['cases'],'cases');assert a['guard_before']==a['guard_after'] and b['guard_before']==b['guard_after'];counts={}
 for d in diffs:counts[d['path'].rsplit('/',1)[-1]]=counts.get(d['path'].rsplit('/',1)[-1],0)+1
 r={'parent_core':a['core'],'candidate_core':b['core'],'cases':[{'case':x['case'],'time':x['snapshot']['time'],'events':len(x['snapshot']['events'])} for x in b['cases']],'all_values_equal_except_named_fingerprint_paths':True,'difference_counts':counts,'difference_paths':diffs,'original_parent_snapshot':{'path':str(parent),'sha':sha(parent)},'actual_candidate_snapshot':{'path':str(candidate),'sha':sha(candidate)},'source_catalog_inputs_start_end_stable':True,'scope':'Full original no-opt 0-1 and custom850/60 snapshots/events/world/scheduler-visible state, no physics/HP/callback changes hidden under fingerprint masking','client_verified':False};dest=OUT/'noopt_comparison.json'
 if dest.exists():raise ValueError('Preserve comparison')
 dest.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'differences':len(diffs),'difference_counts':counts,'all_other_values_equal':True}))
if __name__=='__main__':main()
