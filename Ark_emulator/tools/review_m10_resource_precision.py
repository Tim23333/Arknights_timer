"""Read-only isolated candidate review; preloads candidate before primary helpers."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root',type=Path,default=ROOT.parent/'unpack_work/campaign_m10_cast_freeze_candidate')
    parser.add_argument('--package',type=Path,default=ROOT/'packages/campaign/mainline_models/level_main_00-10.m10_resource_precision.json')
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m10_resource_precision_independent_review.json')
    args=parser.parse_args();candidate=args.candidate_root.resolve();package=args.package.resolve()
    test=ROOT/'tests_v2/test_m10_resource_precision_review.py'
    helpers=[ROOT/'tools/canonical_summon_witness_support.py',ROOT/'tools/witness_canonical_kalts.py',ROOT/'tools/witness_canonical_roster_trio.py']
    files=[package,test,Path(__file__),*helpers]
    before={str(p):sha(p) for p in files}
    env=dict(os.environ,ARKSIM_M10_REVIEW_ROOT=str(candidate),CAMPAIGN_SUMMON_PACKAGE=str(package),CAMPAIGN_MECHANISM_PACKAGE=str(package))
    script="import sys;sys.path.insert(0,sys.argv[1]);import ark_sim;import ark_sim.adapters.api as api;assert api.__file__.startswith(sys.argv[1]);sys.path.insert(0,sys.argv[2]);import pytest;raise SystemExit(pytest.main([sys.argv[3],'-q','--tb=short']))"
    process=subprocess.run([sys.executable,'-c',script,str(candidate),str(ROOT),str(test)],cwd=candidate,env=env,capture_output=True,text=True)
    digest_script="import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())"
    digest=subprocess.check_output([sys.executable,'-c',digest_script,str(candidate)],cwd=candidate,text=True).strip()
    after={str(p):sha(p) for p in files};stable=before==after
    passed=stable and digest=='f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e' and process.returncode==0
    result={'schema':'ark-sim/campaign-mechanism-test-evidence/v1','passed':passed,'implementation_sha256':digest,
        'candidate_root':str(candidate),'primary_runtime_modified':False,'identity_stable':stable,'identity_at_start':before,'identity_at_completion':after,
        'input_package':str(package),'input_package_sha256':sha(package),'pytest_output':process.stdout+process.stderr,'pytest_exit_code':process.returncode,
        'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(p),'result':'passed' if passed else 'failed'} for p in [test,Path(__file__),*helpers]],
        'scope':'M10 candidate exact cast recovery and interrupt atomicity; no stage acceptance','review_receipt':False,'formal_approval':False}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'candidate_digest':digest,'output':str(args.output)}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
