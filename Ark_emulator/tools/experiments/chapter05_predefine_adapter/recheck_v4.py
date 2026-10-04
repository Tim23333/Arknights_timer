"""Execute the unchanged independent v3 assertions on the v4 converter."""
import ast,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));import pytest
source=ROOT/'tools/experiments/hidden_v3_peer/test_adapter.py';text=source.read_text(encoding='utf8')
old='from tools.build_reference_stage_scenario_v3 import compose';new='from tools.build_reference_stage_scenario_v4 import compose'
assert text.count(old)==1;changed=text.replace(old,new,1);a=ast.parse(text);b=ast.parse(changed)
nodes=[n for n in ast.walk(a) if isinstance(n,ast.ImportFrom) and n.module=='tools.build_reference_stage_scenario_v3'];assert len(nodes)==1;nodes[0].module='tools.build_reference_stage_scenario_v4';assert ast.dump(a)==ast.dump(b)
clone=Path(__file__).with_name('test_hidden_v4_original_assertions.py')
with clone.open('x',encoding='utf8') as f:f.write(changed)
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(clone),'-q','--tb=short'],plugins=[Capture()]))
out=ROOT/'validation/campaign/chapter05_predefine_adapter/independent_v4_recheck.json'
with out.open('x',encoding='utf8') as f:json.dump({'exitcode':code,'original_sha':hashlib.sha256(source.read_bytes()).hexdigest(),
    'converter_sha':hashlib.sha256((ROOT/'tools/build_reference_stage_scenario_v4.py').read_bytes()).hexdigest(),
    'only_test_change':'Import selected v4; all expectations AST identical','cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}));raise SystemExit(code)
