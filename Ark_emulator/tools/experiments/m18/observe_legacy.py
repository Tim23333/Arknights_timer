"""Same no-profile route and commands under an explicit runtime root."""
import argparse
import sys
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
a=argparse.ArgumentParser();a.add_argument('--runtime-root',type=Path,required=True);a.add_argument('--input',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
sys.path.insert(0,str(args.runtime_root.resolve()))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim'
s=Engine.create(Compiler().compile(json.loads(args.input.read_bytes())),seed=1803)
s.submit({'action':'skill','source':'walker','ability':'ability/rng'},at=2);s.advance(30)
def normalized(x):
    if isinstance(x,dict):return {k:normalized(v) for k,v in x.items() if k not in {'runtime_fingerprint','rule_fingerprint'}}
    if isinstance(x,list):return [normalized(v) for v in x]
    return x
events=[thaw(e) for e in s.session.events];v={'implementation':implementation_digest(),'runtime':s.runtime_fingerprint,
 'program':s.program.fingerprint,'event_count':len(events),'normalized_event_sha256':digest(normalized(events)),
 'ignored_fields':['runtime_fingerprint','rule_fingerprint'],'events':events,'snapshot':s.snapshot(),'commands':s.export_replay()}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v[k] for k in ('implementation','event_count','normalized_event_sha256')}))
