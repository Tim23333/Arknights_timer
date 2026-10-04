"""Fixed a705 source content six author cases; source/candidate/helper guards."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';OUT=ROOT/'validation/campaign/chapter07_sotisd_guarded_final_v6';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
CORE='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE
 module=ROOT/'packages/campaign/chapter07_ordinary_remaining/sotisd.module.v3.reference.json';m=json.loads(module.read_bytes());paths=list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))+list((ROOT/'tools/chapter07_ordinary_remaining').glob('*.py'))+list((ROOT/'packages/campaign/chapter07_ordinary_remaining').glob('*.json'))+[ROOT/'tools/campaign_ordered_checkpoint.py']+[Path(p) for p in m['manifest']['metadata']['source_locks']]
 before={str(p):sha(p) for p in paths};start=time.monotonic();code=pytest.main([str(ROOT/'tools/chapter07_ordinary_remaining/test_sotisd_guarded_v6.py'),'-q']);after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 OUT.mkdir(parents=True,exist_ok=True);out=OUT/'verification.json';assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'source_before':before,'source_after':after,'module':str(module),'module_sha':sha(module),'author_cases':6,'elapsed':time.monotonic()-start,'scope':'sotisd exact15000/700/1300/RES60/0.7/3.8/28nativeframes/114cycle/sourceSILENCED12/noSP/actualDP7/true600damage/sourceBuff flat+1/basegetter0/reference live integer taunt ordering/two public casts700/actualremove→0/CPdiskload/head equality','native_getter_and_comparator_client_verified':False,'captured_midcast_TargetFree_pending':True,'new_core_changed':False,'primary_modified':False,'wholeC7_executed':False,'independent_reviewed':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'actual_exit':code,'sha':sha(out),'elapsed':r['elapsed']}));raise SystemExit(code)
if __name__=='__main__':main()
