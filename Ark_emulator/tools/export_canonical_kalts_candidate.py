"""Replay frozen Kal'tsit cases against an explicitly selected isolated runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def child(candidate,script,*args,env=None):
    bootstrap="import sys;sys.path.insert(0,sys.argv[1]);import ark_sim;import ark_sim.adapters.api as api;assert api.__file__.startswith(sys.argv[1]);sys.path.insert(0,sys.argv[2]);exec(sys.argv[3])"
    return subprocess.run([sys.executable,'-c',bootstrap,str(candidate),str(ROOT),script,*args],cwd=candidate,env=env,capture_output=True,text=True)


def digest(candidate):
    result=child(candidate,'from ark_sim.adapters.api import implementation_digest;print(implementation_digest())')
    if result.returncode:raise RuntimeError(result.stderr)
    return result.stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root',type=Path,default=ROOT.parent/'unpack_work/campaign_m10_cast_freeze_candidate')
    parser.add_argument('--expected-digest',default='f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e')
    parser.add_argument('--package',type=Path,default=ROOT/'packages/campaign/mainline_models/level_main_00-10.m10.json')
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/canonical_kalts_witness.m10_f6bb.json')
    args=parser.parse_args();candidate=args.candidate_root.resolve();package=args.package.resolve()
    test=ROOT/'tests_v2/test_canonical_kalts.py'
    helpers=[ROOT/'tools/witness_canonical_kalts.py',ROOT/'tools/canonical_summon_witness_support.py',ROOT/'tools/witness_canonical_roster_trio.py',Path(__file__)]
    sources=[ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.kalts.json',ROOT/'packages/campaign/talents.support.json',ROOT/'packages/campaign/roster.profiles.json']
    files=[package,test,*helpers,*sources]
    before={'implementation_sha256':digest(candidate),'files':{str(p.resolve()):sha(p) for p in files}}
    if before['implementation_sha256']!=args.expected_digest:raise RuntimeError('candidate runtime identity mismatch before execution')
    with tempfile.TemporaryDirectory(prefix='ark_kalts_candidate_') as directory:
        record=Path(directory)/'cases.jsonl'
        env=dict(os.environ,CAMPAIGN_SUMMON_PACKAGE=str(package),CAMPAIGN_SUMMON_CASE_RESULTS=str(record))
        code="import pytest;raise SystemExit(pytest.main([sys.argv[4],'-q','--tb=short']))"
        run=child(candidate,code,str(test),env=env)
        cases=[json.loads(line) for line in record.read_text(encoding='utf8').splitlines()] if record.exists() else []
    after={'implementation_sha256':digest(candidate),'files':{str(p.resolve()):sha(p) for p in files}}
    stable=before==after
    passed=stable and run.returncode==0 and len(cases)==15 and all(c['result']=='passed' for c in cases)
    rows=json.loads(sources[0].read_bytes())['operators']
    config=next(r['config'] for r in rows if r['character_id']=='char_003_kalts')
    result={'schema':'ark-sim/campaign-mechanism-test-evidence/v1','passed':passed,
        'implementation_sha256':before['implementation_sha256'],'runtime_module_root':str(candidate),
        'identity_stable':stable,'identity_at_start':before,'identity_at_completion':after,
        'input_package':str(package),'input_package_sha256':sha(package),
        'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(p),'result':'passed' if passed else 'failed'} for p in [test,*helpers]],
        'source_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sources},'config':config,
        'cases':cases,'pytest_exit_code':run.returncode,'pytest_output':run.stdout+run.stderr,
        'scope':'frozen fifteen canonical Kalts/Mon3tr mechanism cases; no complete native or stage approval',
        'untested_boundaries':['other_unit_kill_marker','outside_host_healing_range_DEF_zero'],
        'primary_runtime_modified':False,'client_pending_preserved':True,'review_receipt':False,'formal_approval':False}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'identity_stable':stable,'count':len(cases),'failed':[c['case'] for c in cases if c['result']!='passed'],'output':str(args.output)}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
