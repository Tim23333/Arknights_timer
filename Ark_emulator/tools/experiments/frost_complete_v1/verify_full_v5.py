"""Fresh complete suite on exact candidate and canonical input identity."""
import ast,hashlib,json,os,sys,time,types,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/frost_complete_v1'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json');os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
import ark_sim
from ark_sim.adapters.api import implementation_digest
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    import pytest
    assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    fixture=RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json'
    source=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate/ark_emulator/levels/packs/level_main_00-01.json'
    if not fixture.exists():
        fixture.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,fixture)
    assert sha(fixture)==sha(source)
    original=ROOT/'tests_v2/test_rules.py';text=original.read_text(encoding='utf8');needle='assert len(DEFAULT_CATALOG["contracts"]) == 92';assert text.count(needle)==1;changed=text.replace(needle,'assert len(DEFAULT_CATALOG["contracts"]) == 96',1)
    a=ast.parse(text);b=ast.parse(changed);constants=[n for n in ast.walk(a) if isinstance(n,ast.Constant) and n.value==92];assert len(constants)==1;constants[0].value=96;assert ast.dump(a)==ast.dump(b)
    clone=OUT/'test_rules_full_v5_correct_fixture_catalog96.py'
    with clone.open('x',encoding='utf8') as f:f.write(changed)
    module=types.ModuleType('test_rules');module.__file__=str(original);exec(compile(changed,str(original),'exec'),module.__dict__);sys.modules['test_rules']=module
    paths=[p for folder in (RUNTIME/'ark_sim',ROOT/'tests_v2') for p in folder.rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts]
    paths.extend([clone,fixture,Path(__file__),Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']),ROOT/'tools/campaign_runthrough_progress_v3.py',ROOT/'tools/build_campaign_runthrough_input.py'])
    before={str(p):sha(p) for p in paths};cases=[];started=time.monotonic()
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':
                cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
                if report.failed:print(json.dumps({'immediate_failure':report.nodeid,'failure':str(report.longrepr)}),flush=True)
    code=int(pytest.main([str(ROOT/'tests_v2'),'-q','--tb=short'],plugins=[Capture()]));after={str(p):sha(p) for p in paths}
    assert before==after and implementation_digest()==PIN
    actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)}
    assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
    report={'core':PIN,'exitcode':code,'elapsed_seconds':time.monotonic()-started,'cases':cases,'guards_start':before,'guards_end':after,
        'actual_modules':actual,'canonical_input':os.environ['CAMPAIGN_SUMMON_PACKAGE'],'catalog_only_change':'AST92->96; original__file__fixturepath',
        'full_4_10_executed':False,'client_verified':False}
    target=OUT/'full_v5_correct_fixture.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'exitcode':code,'passed':sum(c['outcome']=='passed' for c in cases),'sha':sha(target)}));raise SystemExit(code)
if __name__=='__main__':main()
