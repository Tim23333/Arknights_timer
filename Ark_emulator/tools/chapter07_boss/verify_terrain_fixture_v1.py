"""Real public deployment rejection at the author's erroneous ore-occupied cell."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_scenario_cards_v1_candidate'))
sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.chapter07_boss.policies_v2 import providers as boss
from tools.chapter07_predefines.policies_v1 import providers as ore
folder=ROOT/'packages/campaign/chapter07_boss/patrt/ore_mine_joint_v3'
p=json.loads((folder/'input.json').read_bytes());registry={**ore(),**boss()}
s=Engine.create(Compiler(providers=registry).compile(p),providers=registry,seed=7189)
s.submit({'action':'deploy','entity':'unit/ch7/predefined/mine/level1','row':3,'col':3,'alias':'mine'},at=0)
s.session.advance(2)
rows=[thaw(e) for e in s.session.events if e['type'].startswith('command.')]
assert len(rows)==1 and rows[0]['type']=='command.rejected'
assert s.ctx.spatial.grid.tile(3,3)['buildableType']==0
result={'status':'actual_fixture_rejection_confirmed','runtime_sha256':implementation_digest(),'input_sha256':hashlib.sha256((folder/'input.json').read_bytes()).hexdigest(),'terrain':thaw(s.ctx.spatial.grid.tile(3,3)),'public_command_events':rows,'stock':s.ctx.resources.current('system/battle','stock_ch7_mine'),'dp':s.ctx.resources.current('system/battle','dp'),'correction':'Relocate source Ore to adjacent cell3,4; retain Boss/mine cell3,3 and all native numerical/timing fields. This is author scene geometry, not a source/kernel fix.'}
path=folder/'terrain.fixture.failure.json';path.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
