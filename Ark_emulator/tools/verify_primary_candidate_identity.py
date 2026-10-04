"""Reconstruct program/runtime identities through both actual import locations."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def reconstruct(runtime,packages):
    code = """
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
before=implementation_digest()
rows=[]
for path in sys.argv[2:]:
    program=Compiler().compile(path);sim=Engine.create(program,seed=123)
    rows.append({'package':path,'program_fingerprint':program.fingerprint,
        'runtime_fingerprint':sim.runtime_fingerprint,'reconstruction_ticks':sim.session.time})
assert before==implementation_digest()
print(json.dumps({'implementation_sha256':before,'actual_module':ark_sim.__file__,'programs':rows}))
"""
    return json.loads(subprocess.check_output([sys.executable,'-c',code,str(runtime),*[str(p) for p in packages]],
        cwd=runtime,text=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root',type=Path,default=ROOT.parent/'unpack_work/campaign_m12_projection_candidate')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    packages = [ROOT/'packages/ark_content/level_main_00_01.json',
        ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json',
        ROOT/'packages/campaign/mainline_models/level_main_00-11.m12_projection.json']
    primary = reconstruct(ROOT,packages)
    candidate = reconstruct(args.candidate_root.resolve(),packages)
    assert primary['implementation_sha256'] == candidate['implementation_sha256']
    assert primary['programs'] == candidate['programs']
    report = {'schema':'ark-sim/primary-candidate-identity/v1','passed':True,
        'primary':primary,'candidate':candidate,'scope':'Zero-tick identity reconstruction; combat evidence stays in separate reports',
        'formal_approval':False}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'programs':len(packages),'implementation_sha256':primary['implementation_sha256']}))


if __name__ == '__main__':
    main()
