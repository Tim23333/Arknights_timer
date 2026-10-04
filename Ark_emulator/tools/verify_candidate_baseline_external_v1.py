"""Run the existing full baseline through a verified frozen candidate import."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(runtime):
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(runtime)],cwd=runtime,text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--expected-digest',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    files = [Path(__file__),ROOT/'tools/verify_v2_baseline_external_v1.py',ROOT/'packages/ark_content/level_main_00_01.json',
        ROOT/'scenarios/level_main_00_01/commands.json']
    before = {str(p):sha(p) for p in files}
    assert digest(runtime) == args.expected_digest
    code = """
import runpy,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import ark_sim
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
assert implementation_digest()==sys.argv[4]
script,output=sys.argv[2:4]
print('Actual baseline runtime: '+ark_sim.__file__,flush=True)
sys.argv=[script,'--output',output]
runpy.run_path(script,run_name='__main__')
"""
    process = subprocess.run([sys.executable,'-c',code,str(runtime),str(ROOT/'tools/verify_v2_baseline_external_v1.py'),
        str(args.output.resolve()),args.expected_digest],cwd=ROOT)
    after = {str(p):sha(p) for p in files}
    stable = before == after and digest(runtime) == args.expected_digest
    report = json.loads(args.output.read_bytes()) if args.output.exists() else {}
    result = {'schema':'ark-sim/candidate-baseline-run/v1','passed':process.returncode == 0 and stable and report.get('passed') is True,
        'runtime_root':str(runtime),'implementation_sha256':args.expected_digest,'source_at_start':before,
        'source_at_completion':after,'identity_stable':stable,'exit_code':process.returncode,
        'baseline':str(args.output),'formal_approval':False}
    identity = args.output.with_suffix('.identity.json')
    identity.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
