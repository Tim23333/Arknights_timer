import sys,json
from pathlib import Path
runtime,out=map(Path,sys.argv[1:]);ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(runtime));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
p=json.loads((ROOT/'validation/campaign/m53_qualified_area/public_input.json').read_bytes());p['rules']=[];effect=p['abilities'][0]['activation']['on_start'][0];effect.pop('membership_rule');effect['radius']=1.5
s=Engine.create(Compiler().compile(p),seed=5309);s.submit({'action':'skill','source':'source','ability':'ability/area'},at=1);s.advance(8)
out.write_text(json.dumps({'core':implementation_digest(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},indent=2)+'\n',encoding='utf8')
