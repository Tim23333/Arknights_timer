"""Export declared intermediate fields using the actual frozen V2 runtime.

The explicit plan maps field names to live JSON component paths, system state,
resources or full random state. It cannot fabricate a native observation.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())


def read_field(sim,spec):
    from ark_sim.contracts import thaw
    if spec['kind']=='entity_component':
        value=sim.ctx.entity(spec['entity'])['components']
        for key in spec['path']:
            if not isinstance(value,Mapping) or key not in value:
                raise ValueError('Required model component path absent: '+str(spec))
            value=value[key]
        return thaw(value)
    if spec['kind']=='battle_state':
        value=sim.ctx.state()
        for key in spec['path']:
            if not isinstance(value,Mapping) or key not in value:
                raise ValueError('Required battle state path absent')
            value=value[key]
        return thaw(value)
    if spec['kind']=='resource':
        return sim.ctx.resources.current(spec['entity'],spec['resource'])
    if spec['kind']=='random_state':
        return thaw(sim.session.random.snapshot())
    raise ValueError('Unknown model observation kind')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root','package','commands','plan','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-core',required=True);args=parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent!=runtime/'ark_sim' or implementation_digest()!=args.expected_core:
        raise ValueError('Wrong explicit trace runtime')
    guarded=[args.package,args.commands,args.plan,Path(__file__),runtime/'ark_sim/rules/contracts.json',runtime/'ark_sim/content/presets/ark_standard.json']
    before={str(p.resolve()):sha(p) for p in guarded}
    package,commands,plan=load(args.package),load(args.commands),load(args.plan)
    if plan.get('schema')!='ark-sim/model-trace-export-plan/v1':raise ValueError('Unknown trace export plan')
    if plan['package_sha256']!=sha(args.package) or plan['commands_sha256']!=sha(args.commands):raise ValueError('Export plan input identity differs')
    frames=plan['model_frames']
    if not frames or any(type(t) is not int or t<0 for t in frames) or frames!=sorted(set(frames)):raise ValueError('Ordered unique nonnegative model frames required')
    if not isinstance(plan['fields'],dict) or not plan['fields']:raise ValueError('Explicit nonempty model field map required')
    program=Compiler().compile(package)
    if plan['comparison_identity'].get('content_identity')!=program.fingerprint:
        raise ValueError('Comparison content identity differs from actual compiled program')
    if 'seed' in package['scenarioDraft'] and plan['seed']!=package['scenarioDraft']['seed']:
        raise ValueError('Export seed differs from explicit scenario seed')
    sim=Engine.create(program,seed=plan['seed'])
    for command in commands:
        action=dict(command);tick=action.pop('at');sim.submit(action,at=tick)
    samples=[]
    for frame in frames:
        sim.advance(frame-sim.session.time)
        values={name:read_field(sim,spec) for name,spec in plan['fields'].items()}
        samples.append({'frame':frame,'frame_before':frame,'frame_after':sim.session.time,'complete':True,'values':values})
    after={str(p.resolve()):sha(p) for p in guarded}
    if before!=after or implementation_digest()!=args.expected_core:raise ValueError('Trace source changed during export')
    result={'schema':'ark-sim/intermediate-trace/v1','origin':'ark_sim','identity':plan['comparison_identity'],
            'model_provenance':{'implementation':args.expected_core,'runtime_module':ark_sim.__file__,'program':program.fingerprint,
                                'runtime':sim.runtime_fingerprint,'seed':plan['seed'],'sources':before,'sources_at_completion':after},
            'samples':samples,'actual_game_accuracy_verified':False,'uncovered_requirements':plan.get('uncovered_requirements',[])}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'frames':len(samples),'fields':len(plan['fields']),'implementation':args.expected_core,'actual_game_accuracy_verified':False}))


if __name__=='__main__':main()
