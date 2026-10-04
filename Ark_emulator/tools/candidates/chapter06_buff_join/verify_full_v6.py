"""All current tests on the exact joint core; only catalog count follows new contract."""
import ast,hashlib,json,os,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v6_candidate'
OUT=ROOT/'validation/campaign/chapter06_buff_join_v6'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
PIN='01f88963d0720245edfdbb7c3ca19dce2c307202795bba74ceb933f028d08a15'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    # Private test checkout preserves every existing assertion except the explicit count.
    tests=RUNTIME/'tests_v2'
    assert not tests.exists()
    shutil.copytree(ROOT/'tests_v2',tests,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    original=ROOT/'tests_v2/test_rules.py';selected=tests/'test_rules.py'
    before=original.read_text(encoding='utf8')
    anchor='assert len(DEFAULT_CATALOG["contracts"]) == 96'
    assert before.count(anchor)==1
    after=before.replace(anchor,'assert len(DEFAULT_CATALOG["contracts"]) == 97')
    selected.write_text(after,encoding='utf8',newline='')
    # Assert the cloned file differs by that one literal only.
    assert ast.dump(ast.parse(after.replace('== 97','== 96',1)))==ast.dump(ast.parse(before))
    for p in tests.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p!=selected:
            assert p.read_bytes()==(ROOT/'tests_v2'/p.relative_to(tests)).read_bytes()
    source_fixture=ROOT/'ark_emulator/levels/packs/level_main_00-01.json'
    fixture=RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json'
    fixture.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source_fixture,fixture)
    assert sha(fixture)==sha(source_fixture)
    paths=[p for folder in (RUNTIME/'ark_sim',ROOT/'tests_v2',tests) for p in folder.rglob('*')
           if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts]
    paths.extend([fixture,Path(__file__),ROOT/'tools/campaign_runthrough_progress_v3.py',Path(os.environ['CAMPAIGN_SUMMON_PACKAGE'])])
    guards={str(p):sha(p) for p in paths};cases=[];start=time.monotonic()
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':
                cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
                if report.failed:print(json.dumps({'failure':report.nodeid,'details':str(report.longrepr)}),flush=True)
    code=int(pytest.main([str(tests),'-q','--tb=short'],plugins=[Capture()]))
    assert guards=={str(p):sha(p) for p in paths} and implementation_digest()==PIN
    actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)}
    assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
    report={'core':PIN,'exitcode':code,'elapsed_seconds':time.monotonic()-start,'cases':cases,
            'guards_start':guards,'guards_end':{str(p):sha(p) for p in paths},'actual_modules':actual,
            'test_adjustment':{'original_sha':sha(original),'selected_sha':sha(selected),'only_change':anchor+' -> count97 (new buff.application)'},
            'client_verified':False,'full_stage_executed':False}
    target=OUT/'full_v6.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'exit':code,'cases':len(cases),'sha':sha(target)}));raise SystemExit(code)


if __name__=='__main__':main()
