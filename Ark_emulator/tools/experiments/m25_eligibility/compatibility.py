import sys,json,argparse,hashlib
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--runtime',required=True);ap.add_argument('--output',required=True);args=ap.parse_args();runtime=Path(args.runtime).resolve();sys.path.insert(0,str(runtime))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
import test_eligibility as h
p=h.shot_fixture();del p['selectors'][0]['eligibility'];p['rules']=[]
for e in p['entities']:e['components'].pop('selection_state')
for b in p['buffs']:b.pop('selection_flags')
s=Engine.create(Compiler().compile(p),seed=2501);s.submit({'action':'skill','source':'target','ability':'ability/free'},at=0);s.submit({'action':'skill','source':'source','ability':'ability/shot'},at=2);s.advance(35)
def clean(v):
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k not in ('runtime_fingerprint','program_fingerprint','rule_fingerprint')}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 return v
result={'core':implementation_digest(),'actual_module':sys.modules['ark_sim'].__file__,'fixture':p,'world':thaw(s.session.world.snapshot()),'random':s.session.random.snapshot(),'scheduler':s.session.scheduler.snapshot(),'events_raw_sha256':hashlib.sha256(json.dumps(thaw(s.session.events),sort_keys=True).encode()).hexdigest(),'events_without_identity':clean(thaw(s.session.events)),'identity_normalization':'only runtime/program/rule fingerprint keys removed; no state/eventtype/values removed'}
assert Path(sys.modules['ark_sim'].__file__).resolve().parent==runtime/'ark_sim';Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
