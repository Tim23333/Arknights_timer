"""Exact same category-slice input under an explicitly chosen runtime."""
import argparse
import sys
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
a=argparse.ArgumentParser();a.add_argument('--runtime-root',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
sys.path.insert(0,str(args.runtime_root.resolve()))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim'
sys.path.append(str(ROOT))
from tools.experiments.m15_peer import verify as h
from ark_sim.contracts import thaw,digest
from ark_sim.adapters.api import implementation_digest
h.PACKAGE=ROOT/'packages/campaign/chapter01_devices/emp.category.json'
s=h.make(h.scene(sp=5));h.command(s,'device','ability/chapter01_emp/burst',0);s.advance(47)
events=[thaw(e) for e in s.session.events]
# Fingerprint differences are expected and retained separately. No numeric,
# input, target, cause, ordering, or domain event field is excluded.
IDENTITY={'runtime_fingerprint','rule_fingerprint'}
def normalized(x):
    if isinstance(x,dict):return {k:normalized(v) for k,v in x.items() if k not in IDENTITY}
    if isinstance(x,list):return [normalized(v) for v in x]
    return x
value={'implementation':implementation_digest(),'runtime':s.runtime_fingerprint,'program':s.program.fingerprint,
       'terrain_loaded':getattr(s.ctx,'terrain',None) is not None,'event_count':len(events),
       'normalized_event_sha256':digest(normalized(events)),'events':events,'snapshot':s.snapshot(),
       'ignored_identity_field_names':sorted(IDENTITY)}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in value.items() if k not in ('events','snapshot')}))
