import sys,json
from pathlib import Path
runtime=Path(sys.argv[1]).resolve();sys.path.insert(0,str(runtime))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
raw=Path(sys.argv[2]).read_bytes();p=json.loads(raw);commands=json.loads(Path(sys.argv[3]).read_bytes())
before=implementation_digest();s=Engine.create(Compiler().compile(p),seed=4506)
for command in commands:s.submit({k:v for k,v in command.items() if k!='at'},at=command['at'])
s.advance(8);after=implementation_digest();assert before==after
Path(sys.argv[4]).write_text(json.dumps({'module':sys.modules['ark_sim'].__file__,'core':before,'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
