"""Same finite fixture/provider source in two explicit runtime processes."""
import sys,json,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);args=ap.parse_args();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim'
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
sys.path.insert(0,str(Path(__file__).parent));import test_unlimited as tests
def strip(v):
 if isinstance(v,dict):return {k:strip(x) for k,x in v.items() if k not in ('runtime_fingerprint','rule_fingerprint')}
 if isinstance(v,list):return [strip(x) for x in v]
 return v
core=implementation_digest();p=tests.fixture(1);s=tests.make(p);tests.fire(s);s.advance(4);tests.exact(s);events=strip(thaw(s.session.events));snapshot=strip(s.snapshot());report={'core':core,'module':ark_sim.__file__,'input_sha256':tests.INPUTS[0]['sha256'],'event_count':len(events),'events':events,'events_sha256':digest(events),'snapshot':snapshot,'snapshot_sha256':digest(snapshot),'checkpoint_replay_equal':True};assert implementation_digest()==core
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({k:report[k] for k in ('core','event_count','events_sha256','snapshot_sha256')}))
