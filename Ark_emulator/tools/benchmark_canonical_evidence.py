"""Measure complete canonical journal encoders on an actual source-bound prefix."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--commands',type=Path,required=True);ap.add_argument('--ticks',type=int,default=300);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from tools import campaign_streaming_evidence as old
    from tools.campaign_canonical_encoder import CanonicalEncoder
    if not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()) or implementation_digest()!=args.expected_core:raise ValueError('Wrong runtime')
    guards=[Path(__file__),ROOT/'tools/campaign_canonical_encoder.py',ROOT/'tools/campaign_streaming_evidence.py',args.package,args.commands]
    before={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    package=json.loads(args.package.read_bytes());commands=json.loads(args.commands.read_bytes());sim=Engine.create(Compiler().compile(package),seed=package['scenarioDraft']['seed'])
    for command in commands:
        action=dict(command);tick=action.pop('at');sim.submit(action,at=tick)
    sim.advance(args.ticks);records=sim.session.events
    def measure(iterator):
        tracemalloc.start();started=time.perf_counter();hashvalue=hashlib.sha256();size=0
        for part in iterator:
            if isinstance(part,str):part=part.encode('utf8')
            hashvalue.update(part);size+=len(part)
        elapsed=time.perf_counter()-started;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        return {'sha256':hashvalue.hexdigest(),'bytes':size,'wall_seconds':elapsed,'peak_extra_allocation':peak}
    original=measure(old.chunks(records));encoder=CanonicalEncoder();cached=measure(encoder.chunks(records))
    after={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    report={'schema':'ark-sim/canonical-encoding-benchmark/v1','passed':original['sha256']==cached['sha256'] and original['bytes']==cached['bytes'] and before==after and implementation_digest()==args.expected_core,
        'runtime':args.expected_core,'source_start':before,'source_end':after,'events':len(records),'ticks':args.ticks,
        'original':original,'cached':cached,'cache':encoder.statistics(),'scope':'Actual full prefix journal bytes, bounded export CPU/memory; no event omitted, not fullstage or client proof'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({key:report[key] for key in ('passed','events','ticks','original','cached','cache')},ensure_ascii=False))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
