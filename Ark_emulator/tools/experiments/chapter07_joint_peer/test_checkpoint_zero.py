import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter07_boss.policies_v2 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3]
INPUTS=[];CAPTURES=[]
def test_actual_source_initial_public_checkpoint_zero_has_same_future_trace(tmp_path):
 # This is our independent prior input, not an author fixture/oracle.
 values=json.loads((ROOT/'validation/campaign/chapter07_joint_independent_complete/inputs.json').read_text())
 p=next(p for p in values if p['scenarioDraft']['id']=='scene/j/actual_source');INPUTS.append(p);reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=7013)
 s.submit({'action':'skill','source':'director','ability':'ability/j/sourcekill'},at=5)
 pin=write_ordered(tmp_path/'source0.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'source0.json',pin),providers=reg)
 s.advance(36);r.advance(36);h=replay(s.program,s.export_replay(),providers=reg)
 CAPTURES.append({'case':'source_initial_cp0','forward':s.checkpoint(),'restore':r.checkpoint(),'head':h.checkpoint(),'forward_events':thaw(tuple(s.session.events)),'restore_events':thaw(tuple(r.session.events)),'head_events':thaw(tuple(h.session.events))})
 assert s.checkpoint()==r.checkpoint()==h.checkpoint()
