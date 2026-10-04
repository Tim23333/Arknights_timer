import sys,json,hashlib
from pathlib import Path
runtime,input_path,out=map(Path,sys.argv[1:]);raw=input_path.read_bytes();sys.path.insert(0,str(runtime))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
s=Engine.create(Compiler().compile(json.loads(raw)),seed=700020)
for t,a in [(0,'immune'),(1,'mixed'),(2,'silence')]:s.submit({'action':'skill','source':'subject','ability':'ability/'+a},at=t)
s.advance(15);out.write_text(json.dumps({'core':implementation_digest(),'module':sys.modules['ark_sim'].__file__,'input_sha256':hashlib.sha256(raw).hexdigest(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},indent=2)+'\n',encoding='utf8')
