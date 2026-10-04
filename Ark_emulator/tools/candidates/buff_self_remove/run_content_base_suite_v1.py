"""Run unchanged repository tests with captured current joint runtime identities."""
import hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
import ast
CORE='d81334d340034732a1840f16612073f7ae56e41a9727584ea38c74c61943439e'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def test_sources():
    pending=list((ROOT/'tests_v2').glob('*.py'));found=set()
    while pending:
        path=pending.pop()
        if path in found:continue
        found.add(path)
        for n in ast.walk(ast.parse(path.read_bytes())):
            modules=[]
            if isinstance(n,ast.Import):modules=[a.name for a in n.names]
            if isinstance(n,ast.ImportFrom) and n.module:
                modules=[n.module]
                if n.module=='tools':modules += ['tools.'+a.name for a in n.names]
            for module in modules:
                if module.startswith('tools.'):
                    child=(ROOT/Path(*module.split('.'))).with_suffix('.py')
                    if child.is_file():pending.append(child)
    return found


def main():
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    paths=list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
    paths += list(test_sources())
    paths += [Path(__file__),ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json',
        RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json']
    paths=sorted(set(p for p in paths if '__pycache__' not in p.parts))
    before={str(p):sha(p) for p in paths};cases=[];skips=[];out=ROOT/'validation/campaign/content_base_v1/full_suite_v1'
    out.mkdir(exist_ok=False);(out/'start.json').write_text(json.dumps({'guards':before,'core':CORE},indent=2)+'\n',encoding='utf8')
    class Capture:
        def pytest_collectreport(self,report):
            if report.skipped:skips.append({'nodeid':report.nodeid,'reason':str(report.longrepr)})
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
    start=time.monotonic();code=int(pytest.main(['tests_v2','-q','--tb=short'],plugins=[Capture()]))
    after={str(p):sha(p) for p in paths}
    actual={name:str(Path(m.__file__).resolve()) for name,m in sys.modules.items() if name.startswith('ark_sim') and getattr(m,'__file__',None)}
    stable=before==after and implementation_digest()==CORE and all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
    result={'core':CORE,'exitcode':code,'elapsed_seconds':time.monotonic()-start,'cases':cases,
        'guards_start':before,'guards_end':after,'actual_modules':actual,'identity_stable':stable,'collection_skips':skips,
        'original_expectations_changed':False,'full_stage_executed':False,'client_verified':False}
    target=out/'verification.json';target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'exit':code,'cases':len(cases),'stable':stable,'sha':sha(target)}),flush=True)
    raise SystemExit(0 if code==0 and stable and len(cases)==1219 and not skips else 1)


if __name__=='__main__':main()
