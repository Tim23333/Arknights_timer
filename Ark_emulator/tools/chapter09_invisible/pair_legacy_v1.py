"""Compare every raw context/event/key order; exempt only runtime identity."""
import json,subprocess,sys,os,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_invisible_v1_candidate';LOG=Path('E:/ArkSimLogs/runs/chapter09_invisible_legacy_pair')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ordered(value):
 if isinstance(value,dict):return [(k,ordered(v)) for k,v in value.items()]
 if isinstance(value,list):return [ordered(v) for v in value]
 return value
def pair(a,b,path='$',identities=None):
 if identities is None:identities=[]
 if isinstance(a,dict):
  assert isinstance(b,dict) and list(a)==list(b),path+' keys/order differ'
  for k in a:
   if (k in {'program_fingerprint','runtime_fingerprint','rule_fingerprint','rule_runtime_fingerprint'} or path+'.'+k=='$.program_metadata.providers.model.targeting.eligibility.implementation') and a[k]!=b[k]:
    assert isinstance(a[k],str) and isinstance(b[k],str) and len(a[k])==len(b[k])==64
    identities.append({'path':path+'.'+k,'parent':a[k],'candidate':b[k]})
   else:pair(a[k],b[k],path+'.'+k,identities)
 elif isinstance(a,list):
  assert isinstance(b,list) and len(a)==len(b),path+' lengths differ'
  for i,(x,y) in enumerate(zip(a,b)):pair(x,y,path+'['+str(i)+']',identities)
 else:assert type(a)==type(b) and a==b,path+' differs: '+repr(a)[:120]+' / '+repr(b)[:120]
 return identities
def main():
 LOG.mkdir(parents=True,exist_ok=True);paths=[]
 for name,runtime in [('parent',ROOT),('candidate',CAND)]:
  path=LOG/(name+'.checkpoint.json');subprocess.run([sys.executable,str(Path(__file__).with_name('source_snapshot_v1.py')),str(runtime),str(path)],cwd=ROOT,env={**os.environ,'PYTHONHASHSEED':'0'},check=True);paths.append(path)
 parent,candidate=[json.loads(p.read_bytes()) for p in paths];results=[]
 for key,original in parent['cases'].items():
  modified=candidate['cases'][key];identities=pair(original,modified);results.append({'case':key,'all_context_events_checkpoint_values_and_keyorder_equal':True,'definitions_and_scenario_and_metadata_equal_except_identity':True,'identity_differences':len(identities),'allowed_identity_fields':['program_fingerprint','runtime_fingerprint','rule_fingerprint','rule_runtime_fingerprint','program_metadata.providers.model.targeting.eligibility.implementation'],'identity_path_sha':hashlib.sha256(json.dumps(identities).encode()).hexdigest(),'context_excluded':False,'cached_calc_excluded':False})
 receipt={'parent':parent['implementation'],'candidate':candidate['implementation'],'cases':results,'raw_sha':{str(p):sha(p) for p in paths},'cached_calc_excluded':False,'contexts_excluded':False,'source_defaults_updated':False,'CP_deleted_after_verification':True,'passed':True}
 cleanup=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),'--apply','--run-dir',str(LOG),'--minimum-age-minutes','0'],capture_output=True,text=True,check=True);receipt['cleanup']=json.loads(cleanup.stdout)
 out=ROOT/'validation/campaign/chapter09_invisible/legacy.pair.v1.json';out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'cases':len(results),'context_cached_calc_keyorder_equal':True,'cleanup':receipt['cleanup']}))
if __name__=='__main__':main()
