import sys,json,argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,str(a.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.build_chapter01_w_combat import fixture
p=Compiler().compile(fixture(json.loads((ROOT/'packages/campaign/chapter01_models/w_combat/model.json').read_bytes())));s=Engine.create(p,seed=17);s.advance(40)
assert getattr(s.ctx,'projectiles',None) is None and s.ctx.get('system/battle',('projectiles',)) is None
result={'program_fingerprint':p.fingerprint,'implementation_sha256':implementation_digest(),'rule_fingerprint':s.ctx.rules.fingerprint,'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'random':s.session.random.snapshot(),'events':thaw(s.session.events),'runtime_module':sys.modules['ark_sim'].__file__}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'program':p.fingerprint,'core':result['implementation_sha256'],'events':len(result['events'])}))
