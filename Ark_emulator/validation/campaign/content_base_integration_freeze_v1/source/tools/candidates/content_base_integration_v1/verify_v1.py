"""Unchanged final Infinity/source assertions on explicit joint import identity."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
CORE='d81334d340034732a1840f16612073f7ae56e41a9727584ea38c74c61943439e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().is_relative_to(RUNTIME.resolve());tests=[Path(__file__).with_name(x) for x in ('test_infinity_contract.py','test_infinity_scopes.py','test_strength_source.py')];paths=tests+[Path(__file__),ROOT/'tools/chapter07_strength_melee/policies_v2.py',ROOT/'tools/campaign_ordered_checkpoint.py']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'));modules=list((ROOT/'packages/campaign/chapter07_strength_melee').glob('*.v5.json'))
 for p in modules:
  paths.append(p);m=json.loads(p.read_bytes());assert m['manifest']['metadata']['required_runtime']=='aa919c9cbd380cf74544d22b4cdebaa9d333c97eed8b21de5b8d8e5186c77d2d'
  for f,h in m['manifest']['metadata']['source_locks'].items():assert sha(Path(f))==h;paths.append(Path(f))
 before={str(p):sha(p) for p in paths};start=time.monotonic();code=pytest.main([str(p) for p in tests]+['-q']);after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE;out=ROOT/'validation/campaign/content_base_integration_v1/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'source_before':before,'source_after':after,'modules_same_old_aa919_metadata':{str(p):sha(p) for p in modules},'actual_new_joint_proof_not_migrated':True,'assertions_unchanged_except_import_and_new_output':True,'author34_and_source9':True,'elapsed':time.monotonic()-start,'full_suite_passed':False,'independent_reviewed':False,'primary_modified':False,'wholeC7_executed':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'actual_exit':code,'sha':sha(out),'elapsed':r['elapsed']}));raise SystemExit(code)
if __name__=='__main__':main()
