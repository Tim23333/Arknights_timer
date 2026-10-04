"""Pinned M94 full regression / fresh complete baseline evidence launch."""
import argparse,hashlib,json,runpy,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import ark_sim
from ark_sim.adapters.api import implementation_digest
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['full','baseline']);args=ap.parse_args();assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
 paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]+list((ROOT/'tests_v2').rglob('*.py'))+[Path(__file__),ROOT/'tools/verify_v2_baseline.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/ark_content/level_main_00_01.json',ROOT/'packages/custom/custom_guard.json',ROOT/'scenarios/level_main_00_01/commands.json'];before={str(p):sha(p) for p in paths}
 started=time.monotonic();cases=[];code=0
 if args.mode=='full':
  import pytest
  class Results:
   def pytest_runtest_logreport(self,report):
    if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
  code=int(pytest.main([str(ROOT/'tests_v2'),'-q','--tb=short'],plugins=[Results()]))
 else:
  sys.argv=[str(ROOT/'tools/verify_v2_baseline.py'),'--output',str(OUT/'baseline')]
  try:runpy.run_path(str(ROOT/'tools/verify_v2_baseline.py'),run_name='__main__')
  except SystemExit as e:code=int(e.code or 0)
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==PIN
 report={'mode':args.mode,'core':PIN,'actual_import':ark_sim.__file__,'exitcode':code,'elapsed_seconds':time.monotonic()-started,'cases':cases,'guards_before':before,'guards_after':after,'whole_4_9_executed':False,'client_verified':False}
 dest=OUT/(args.mode+'_verification.json');
 if dest.exists():raise ValueError('Preserve previous evidence')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'mode':args.mode,'exitcode':code,'passed':sum(c['outcome']=='passed' for c in cases),'report_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
