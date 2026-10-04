"""New full-suite identity: correct explicit inputs and exact catalog-count clone."""
import ast,hashlib,json,os,sys,time,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json');os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
import ark_sim
from ark_sim.adapters.api import implementation_digest
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 import pytest
 assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
 original=ROOT/'tests_v2/test_rules.py';text=original.read_text(encoding='utf8');needle='assert len(DEFAULT_CATALOG["contracts"]) == 92';assert text.count(needle)==1;changed=text.replace(needle,'assert len(DEFAULT_CATALOG["contracts"]) == 96',1)
 # Independently prove the sole AST change, retaining every other assertion.
 a=ast.parse(text);b=ast.parse(changed);constants=[n for n in ast.walk(a) if isinstance(n,ast.Constant) and n.value==92];assert len(constants)==1;constants[0].value=96;assert ast.dump(a)==ast.dump(b)
 clone=OUT/'test_rules_catalog96_source.py'
 if clone.exists():raise ValueError('Preserve cloned source')
 clone.write_text(changed,encoding='utf8',newline='')
 # pytest still collects the original file/node IDs. __file__ keeps the exact
 # original path so docs/v2_examples/custom_guard.json is not relocated.
 module=types.ModuleType('test_rules');module.__file__=str(original);exec(compile(changed,str(original),'exec'),module.__dict__);sys.modules['test_rules']=module
 paths=[p for folder in (RUNTIME/'ark_sim',ROOT/'tests_v2',ROOT/'tools') for p in folder.rglob('*') if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts]+[clone,Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']),ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json'];before={str(p):sha(p) for p in paths};cases=[];started=time.monotonic()
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':
    cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
    if report.failed:print(json.dumps({'immediate_failure':report.nodeid,'failure':str(report.longrepr)}),flush=True)
 code=int(pytest.main([str(ROOT/'tests_v2'),'-q','--tb=short'],plugins=[Results()]));after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==PIN
 report={'core':PIN,'exitcode':code,'elapsed_seconds':time.monotonic()-started,'cases':cases,'explicit_environment':{k:os.environ[k] for k in ('CAMPAIGN_SUMMON_PACKAGE','ARKSIM_M10_REVIEW_ROOT')},'catalog_clone':{'original_path':str(original),'original_sha':sha(original),'clone_path':str(clone),'clone_sha':sha(clone),'only_change':'Expected catalog count92 ->96; other AST identical','fixture_file_path':str(original),'custom_guard_path':str(ROOT/'docs/v2_examples/custom_guard.json')},'guards_before':before,'guards_after':after,'previous_twofail_identity_preserved':True,'whole_4_9_executed':False,'client_verified':False}
 dest=OUT/'full_v2_verification.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exitcode':code,'passed':sum(c['outcome']=='passed' for c in cases),'report_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
