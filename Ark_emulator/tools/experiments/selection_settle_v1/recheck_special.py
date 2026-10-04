import ast,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_selection_settle_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));import pytest
from ark_sim.adapters.api import implementation_digest
PIN='30e4cdfadc5a98eb59da20d89591f5f5d3d6acc8f2d9a997df5e761d759fb49d';assert implementation_digest()==PIN
source=ROOT/'tools/experiments/chapter05_special_ranged_guard_independent_recheck/test_peer.py'
text=source.read_text(encoding='utf8');replacements={
    'model.ranged_guard.reference.json':'model.selection_settle.reference.json',
    'a491491f577f5842660ddbcff3a6eda0cfab1fff9f4994c1cb04f107bc6463dc':'fa314fcf5e46ddcef792ced3f1f7f86cc1586d7f74e5915af305f270dff55b8d'}
changed=text
for old,new in replacements.items():assert changed.count(old)==1;changed=changed.replace(old,new,1)
a=ast.parse(text);b=ast.parse(changed)
for node in ast.walk(a):
    if isinstance(node,ast.Constant) and isinstance(node.value,str):
        for old,new in replacements.items():node.value=node.value.replace(old,new)
assert ast.dump(a)==ast.dump(b)
clone=Path(__file__).with_name('test_original_special_assertions.py')
with clone.open('x',encoding='utf8') as f:f.write(changed)
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(clone),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
assert implementation_digest()==PIN;out=ROOT/'validation/campaign/selection_settle_v1/special_recheck.json'
with out.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'original_sha':hashlib.sha256(source.read_bytes()).hexdigest(),
    'only_changes':replacements,'all_assertions_ast_preserved':True,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}));raise SystemExit(code)
