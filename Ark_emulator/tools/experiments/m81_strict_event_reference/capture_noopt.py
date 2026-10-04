import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=Path(sys.argv[1]).resolve();sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT));import test_storage as t
s=t.create(Path('.'),False);s.advance(30);Path(sys.argv[2]).write_text(json.dumps({'input':t.INPUTS,'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'commands':s.export_replay()},indent=2)+'\n',encoding='utf8')
