"""Same no-opt behavior input against explicitly chosen runtime bytes."""
import sys,json,argparse
from pathlib import Path
a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--input',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
sys.path.insert(0,str(args.root.resolve()))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw,digest
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==args.root.resolve()/'ark_sim'
raw=args.input.read_bytes();s=Engine.create(Compiler().compile(json.loads(raw)),seed=24);s.advance(12)
def normalized(x):
 if isinstance(x,dict):return {k:normalized(v) for k,v in x.items() if k not in {'rule_fingerprint','runtime_fingerprint'}}
 if isinstance(x,list):return [normalized(v) for v in x]
 return x
events=[thaw(e) for e in s.session.events];v={'core':implementation_digest(),'events':events,'count':len(events),'normalized_events_sha256':digest(normalized(events)),'snapshot':s.snapshot()}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes((json.dumps(v,indent=2)+'\n').encode())
print(json.dumps({k:v[k] for k in ('core','count','normalized_events_sha256')}))
