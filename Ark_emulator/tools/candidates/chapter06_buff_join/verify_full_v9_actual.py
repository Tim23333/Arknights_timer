"""Run repository tests at their real paths; adapt only the new catalog count."""
import ast,hashlib,json,os,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v9_candidate'
OUT=ROOT/'validation/campaign/chapter06_buff_join_v9'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
PIN='84ccd1edcb7978d37f41be86e0c3d4bf0e877ec30624ef34264bb1998ecea7f4'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    source=ROOT/'tests_v2/test_rules.py';tree=ast.parse(source.read_text(encoding='utf8'))
    name='test_catalog_has_96_contracts_and_is_immutable'
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    changed=0
    class NewCount(ast.NodeTransformer):
        def visit_Compare(self,node):
            nonlocal changed
            if (isinstance(node.left,ast.Call) and isinstance(node.left.func,ast.Name) and node.left.func.id=='len'
                    and len(node.comparators)==1 and isinstance(node.comparators[0],ast.Constant) and node.comparators[0].value==96):
                node.comparators[0]=ast.Constant(97);changed+=1
            return self.generic_visit(node)
    NewCount().visit(function);assert changed==1
    ast.fix_missing_locations(function)
    fixture=RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json'
    fixture.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'ark_emulator/levels/packs/level_main_00-01.json',fixture)
    assert sha(fixture)==sha(ROOT/'ark_emulator/levels/packs/level_main_00-01.json')
    paths=[p for folder in (RUNTIME/'ark_sim',ROOT/'tests_v2') for p in folder.rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts]
    paths.extend([fixture,Path(__file__),ROOT/'tools/campaign_runthrough_progress_v3.py',Path(os.environ['CAMPAIGN_SUMMON_PACKAGE'])])
    before={str(p):sha(p) for p in paths};cases=[];patches=[];start=time.monotonic()
    class Capture:
        def pytest_collection_modifyitems(self,items):
            for item in items:
                if Path(item.path)==source and item.name==name:
                    namespace=item.module.__dict__.copy()
                    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
                    item.obj=namespace[name];patches.append(item.nodeid)
            assert len(patches)==1
        def pytest_runtest_logreport(self,report):
            if report.when=='call':
                cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
                if report.failed:print(json.dumps({'failure':report.nodeid,'details':str(report.longrepr)}),flush=True)
    code=int(pytest.main([str(ROOT/'tests_v2'),'-q','--tb=short'],plugins=[Capture()]))
    assert before=={str(p):sha(p) for p in paths} and implementation_digest()==PIN
    actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)}
    assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
    target=OUT/'full_v9_actual.json'
    with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'elapsed_seconds':time.monotonic()-start,
        'cases':cases,'guards_start':before,'guards_end':{str(p):sha(p) for p in paths},'actual_modules':actual,
        'test_adjustment':{'original_sha':sha(source),'function':name,'ast_only_literal_change':'catalog count96 ->97','collected_once':patches},
        'client_verified':False,'full_stage_executed':False},f,indent=2)
    print(json.dumps({'exit':code,'cases':len(cases),'sha':sha(target)}));raise SystemExit(code)


if __name__=='__main__':main()
