import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=Path(sys.argv[1]).resolve();sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT));import test_cooldown as t
from ark_sim.contracts import thaw
s,inputs=t.create(t.fixture(None));t.deploy(s,0,'a',0);s.submit({'action':'withdraw','source':'a'},at=10);t.deploy(s,159,'early',1);t.deploy(s,160,'b',1);s.advance(200);Path(sys.argv[2]).write_text(json.dumps({'input':inputs,'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'commands':s.export_replay(),'events':thaw(tuple(s.session.events))},indent=2)+'\n',encoding='utf8')
