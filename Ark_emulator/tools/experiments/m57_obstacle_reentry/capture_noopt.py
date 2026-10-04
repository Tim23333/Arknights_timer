import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];runtime=Path(sys.argv[1]).resolve();sys.path.insert(0,str(runtime));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim'
sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT));import test_independent as t;from ark_sim.contracts import thaw
p=t.fixture();c=p['entities'][0]['components'];c.pop('route_obstacle');c.pop('terrain_overlays');c['attributes']['base']['block_count']=1
s=t.make(p);t.deploy(s);s.advance(30)
Path(sys.argv[2]).write_text(json.dumps({'input':t.INPUTS,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()},indent=2)+'\n',encoding='utf8')


