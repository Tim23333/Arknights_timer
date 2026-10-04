"""Independent owned-controller checks, preserving known old-source failure scope."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m91_complete_c4_candidate';OUT=ROOT/'validation/campaign/m91_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import ark_sim
from ark_sim.adapters.api import implementation_digest
TEST=ROOT/'tools/experiments/m78_independent_controller_peer/test_peer.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 paths=[TEST,Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter04_dmage/source.reference.json',ROOT/'packages/campaign/chapter04_dmage/module.reference.json']
 paths += [p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
 return {str(p):sha(p) for p in paths}
def main():
 import pytest
 assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
 before=guard();cases=[]
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
 code=int(pytest.main([str(TEST),'-q','--tb=short','-k','not normal_source2_actual_blocker_hard_eligibility'],plugins=[Results()]))
 after=guard();assert before==after
 report={'core':implementation_digest(),'exitcode':code,'cases':cases,'guard_before':before,'guard_after':after,'excluded_known_failure':'Old module finite blocked priority SourceCombat; root M92 wrapper pending. Existing independent failure remains unaltered.','whole_stage_executed':False}
 p=OUT/'independent_attachment_peer.json';p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exitcode':code,'passed':sum(c['outcome']=='passed' for c in cases),'report_sha256':sha(p)}));raise SystemExit(code)
if __name__=='__main__':main()
