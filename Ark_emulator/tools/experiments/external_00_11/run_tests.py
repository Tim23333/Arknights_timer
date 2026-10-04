"""Record actual external draft/source tests without approving0-11."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import prepare_external_00_11 as b
from ark_sim.adapters.api import implementation_digest


def main():
    test=Path(__file__).with_name('test_source_contract.py')
    files=[test,Path(__file__),Path(b.__file__),ROOT/'tools/propose_witness_scope_00_11.py',b.CONTENT,b.COMMANDS,b.CONTRACT,b.AUDIT,
        ROOT/'packages/campaign/conversion_drafts/main_00-11.witness_scope.proposal.json',ROOT/'tools/campaign_model_acceptance.py']
    start={b.common.relative(p):b.sha(p) for p in files};core=implementation_digest();assert core==b.CORE
    run=subprocess.run([sys.executable,'-m','pytest',str(test),'-q','--tb=short'],cwd=ROOT,capture_output=True,text=True)
    end={b.common.relative(p):b.sha(p) for p in files};stable=start==end and core==implementation_digest()
    result={'schema':'ark-sim/campaign-test-evidence/v1','passed':run.returncode==0 and stable,'implementation_sha256':core,
        'input_package_sha256':b.PIN,'commands_sha256':b.sha(b.COMMANDS),'contract_sha256':b.sha(b.CONTRACT),
        'pytest_output':run.stdout+run.stderr,'exit_code':run.returncode,'source_at_start':start,'source_at_completion':end,'identity_stable':stable,
        'tests':[{'path':b.common.relative(test),'source_sha256':b.sha(test),'result':'passed' if run.returncode==0 else 'failed'}],
        'scope':'0-11source/consumer/contract/proposal tests only; no complete stage or target mechanism battle execution',
        'formal_approval':False,'review_receipt':False}
    output=ROOT/'validation/campaign/external_00_11_draft_tests_20261002.json';b.write(output,result)
    print(run.stdout+run.stderr);print(json.dumps({'passed':result['passed'],'output':str(output)}));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
