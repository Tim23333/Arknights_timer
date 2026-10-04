import sys,json
from pathlib import Path
runtime,input_path,out=map(Path,sys.argv[1:]);raw=input_path.read_bytes();sys.path.insert(0,str(runtime))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
s=Engine.create(Compiler().compile(json.loads(raw)),seed=760070);s.submit({'action':'skill','source':'hero','ability':'ability/peer/kill'},at=1);s.advance(35)
out.write_text(json.dumps({'core':implementation_digest(),'module':sys.modules['ark_sim'].__file__,'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},indent=2)+'\n',encoding='utf8')
