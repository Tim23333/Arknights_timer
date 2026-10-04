"""Full suite on source-combined ray/branch/status and fresh selection gates."""
import hashlib,json,os,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/campaign/chapter05_complete_v1'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json');os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
PIN='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    fixture=RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json';source=ROOT/'ark_emulator/levels/packs/level_main_00-01.json'
    if not fixture.exists():fixture.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,fixture)
    assert sha(fixture)==sha(source)
    paths=[p for folder in (RUNTIME/'ark_sim',ROOT/'tests_v2') for p in folder.rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts]
    paths.extend([fixture,Path(__file__),ROOT/'tools/campaign_runthrough_progress_v3.py',Path(os.environ['CAMPAIGN_SUMMON_PACKAGE'])]);before={str(p):sha(p) for p in paths};cases=[];start=time.monotonic()
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':
                cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
                if report.failed:print(json.dumps({'failure':report.nodeid,'details':str(report.longrepr)}),flush=True)
    code=int(pytest.main([str(ROOT/'tests_v2'),'-q','--tb=short'],plugins=[Capture()]));after={str(p):sha(p) for p in paths}
    assert before==after and implementation_digest()==PIN
    actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)}
    assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
    out=OUT/'full_v3.json'
    with out.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'elapsed_seconds':time.monotonic()-start,'cases':cases,
        'guards_start':before,'guards_end':after,'actual_modules':actual,'client_verified':False,'full_stage_executed':False},f,indent=2)
    print(json.dumps({'exitcode':code,'passed':sum(c['outcome']=='passed' for c in cases),'sha':sha(out)}));raise SystemExit(code)
if __name__=='__main__':main()
