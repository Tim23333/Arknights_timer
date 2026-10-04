import sys,json,hashlib
from pathlib import Path
runtime,input_path,out_path=map(Path,sys.argv[1:]);sys.path.insert(0,str(runtime))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim'
raw=input_path.read_bytes();p=json.loads(raw);s=Engine.create(Compiler().compile(p),seed=4601);s.submit({'action':'skill','source':'src','ability':'ability/packet'},at=1);s.advance(5)
out_path.write_text(json.dumps({'input_sha256':hashlib.sha256(raw).hexdigest(),'core':implementation_digest(),'actual_module':ark_sim.__file__,'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},indent=2)+'\n',encoding='utf8')
