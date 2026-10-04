from ark_sim import Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.chapter07_consumers_peer.common import *
from tools.experiments.chapter07_consumers_peer.test_ore import ore
def test_real_initial_spzero_strict_cost_seven_float_clock_and_freeze_disk_head(tmp_path):
 p=package('ore_natural');ore(p,0);recipient(p,'a',(3,4));s=create(p,[ORE]);s.advance(208);assert s.ctx.resources.current('ore','sp')<7 and not events(s,'ability.started')
 pin=write_ordered(tmp_path/'ore208.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'ore208.json',pin),providers=registry());s.advance(23);r.advance(23);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'ore_natural');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 starts=events(s,'ability.started');hits=events(s,'damage.accepted');assert len(starts)==1 and starts[0]['time']==210 and len(hits)==1 and hits[0]['time']==229 and s.ctx.resources.current('ore','sp')==0 and s.ctx.resources.current('a','hp')==8500
