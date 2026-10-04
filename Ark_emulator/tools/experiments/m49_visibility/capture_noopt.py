import sys,json
from pathlib import Path
root,out=map(Path,sys.argv[1:]);sys.path.insert(0,str(root));from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
sys.path.append(str(Path(__file__).resolve().parents[3]));sys.path.append(str(Path(__file__).parent))
import test_toggle
p=test_toggle.fixture();p['entities'][0]['components']['buffs']['initial']=[];p['entities'][0]['rules']={};p['rules']=[];p['buffs']=[]
s=Engine.create(Compiler().compile(p),seed=4901);s.submit({'action':'skill','source':'hero','ability':'ability/probe'},at=1);s.advance(5);out.write_text(json.dumps({'core':implementation_digest(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},indent=2)+'\n',encoding='utf8')
