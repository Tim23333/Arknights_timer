"""Export actual draft-audit tests; this evidence is not a conversion receipt."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import build_first_model_conversion as b
from ark_sim.adapters.api import implementation_digest


def main():
    test=Path(__file__).with_name('test_contract.py')
    files=[test,ROOT/'tools/build_first_model_conversion.py',ROOT/'tools/validate_first_model_conversion.py',b.SCHEMA,b.CONTENT,b.COMMAND_OUTPUT,b.AUDIT]
    before={b.relative(p):b.sha(p) for p in files};core=implementation_digest()
    require=b.require;require(core==b.CORE,'wrong execution implementation')
    code="from pathlib import Path;import sys;import ark_sim;assert Path(ark_sim.__file__).resolve().is_relative_to(Path(sys.argv[1]));import pytest;raise SystemExit(pytest.main(sys.argv[2:]))"
    run=subprocess.run([sys.executable,'-c',code,str(ROOT),str(test),'-q','--tb=short'],cwd=ROOT,capture_output=True,text=True)
    after={b.relative(p):b.sha(p) for p in files};stable=before==after and core==implementation_digest()
    result={'schema':'ark-sim/campaign-test-evidence/v1','passed':run.returncode==0 and stable,'implementation_sha256':core,
        'input_package_sha256':b.sha(b.CONTENT),'native_model_input_sha256':b.INPUT_SHA,'commands_sha256':b.sha(b.COMMAND_OUTPUT),
        'exit_code':run.returncode,'pytest_output':run.stdout+run.stderr,'identity_at_start':before,'identity_at_completion':after,
        'identity_stable':stable,'tests':[{'path':b.relative(test),'source_sha256':b.sha(test),'result':'passed' if run.returncode==0 else 'failed'}],
        'scope':'source/contract/schema/negative input guards; no combat-stage execution or independent receipt',
        'formal_approval':False,'review_receipt':False}
    output=ROOT/'validation/campaign/first_model_conversion_tests_20261002.json';b.write(output,result)
    print(run.stdout+run.stderr);print(json.dumps({'passed':result['passed'],'output':str(output)}))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
