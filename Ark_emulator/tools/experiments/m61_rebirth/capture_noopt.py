import sys,json
from pathlib import Path
runtime,input_path,out=map(Path,sys.argv[1:]);sys.path.insert(0,str(runtime))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
p=json.loads(input_path.read_bytes());s=Engine.create(Compiler().compile(p),seed=6120);s.submit({'action':'skill','source':'director','ability':'ability/hit'},at=2);s.advance(8)
out.write_text(json.dumps({'core':implementation_digest(),'actual_module':sys.modules['ark_sim'].__file__,'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},indent=2)+'\n',encoding='utf8')
