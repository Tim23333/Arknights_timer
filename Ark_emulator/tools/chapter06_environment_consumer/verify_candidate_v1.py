"""Actual new static-mask assertions plus existing spatial compatibility, immutable source guard."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_declared_static_tile_v1_candidate';OUT=ROOT/'validation/campaign/chapter06_environment_candidate_v1';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
CORE='8c58a6b704da11c42540357f37331ef604ac737056c1baf40ca7b14e44578924'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE;files=list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))+[ROOT/'tools/chapter06_environment_consumer/test_declared_static_tile_v2.py',ROOT/'packages/campaign/chapter06_environment_consumer/module.v2.reference.json',Path(__file__)];before={str(p):sha(p) for p in files};args=['tools/chapter06_environment_consumer/test_declared_static_tile_v2.py','tests_v2/test_spatial.py','tests_v2/test_m7_spatial_review.py','tests_v2/test_run_diagnostics_actual_route.py','-q'];started=time.monotonic();code=pytest.main(args);after={str(p):sha(p) for p in files};assert before==after and implementation_digest()==CORE;r={'actual_exit':code,'passed':code==0,'core':CORE,'selection':args,'elapsed':time.monotonic()-started,'source_before':before,'source_after':after,'primary_modified':False};out=OUT/'verification.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'passed':code==0,'sha':sha(out)}));raise SystemExit(code)
if __name__=='__main__':main()
