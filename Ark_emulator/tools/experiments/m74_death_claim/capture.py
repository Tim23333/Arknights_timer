import sys,json
from pathlib import Path
runtime,out=map(Path,sys.argv[1:]);ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(runtime))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
p=json.loads((ROOT/'validation/campaign/m61_roster_peer/initial_review.json').read_bytes())['fixtures'][-1]['input']['fixture'];s=Engine.create(Compiler().compile(p),seed=610031);s.submit({'action':'skill','source':'hero','ability':'ability/damage'},at=1);s.advance(17)
out.write_text(json.dumps({'actual_module':sys.modules['ark_sim'].__file__,'core':implementation_digest(),'input':p,'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'replay':s.export_replay(),'actual_kills':[dict(e['payload']) for e in s.session.events if e['type']=='combat.kill']},indent=2)+'\n',encoding='utf8')
