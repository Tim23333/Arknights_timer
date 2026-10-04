from copy import deepcopy
from tools.chapter08_environment.test_infection_probe_v3 import package,MODULE,INPUTS,CAPTURES
from tools.chapter08_environment.policies_v1 import providers
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
def test_original_300seconds_first_expiry_not_refreshed_offcell_and_full_hp_conservation():
 p=package();INPUTS.append(deepcopy(p));reg=providers();s=Engine.create(Compiler(providers=reg).compile(p,packages=[str(MODULE)]),providers=reg,seed=816180);s.submit({'action':'skill','source':'director','ability':'ability/peer/leave'},at=31);s.advance(9001)
 CAPTURES.append({'case':'full300_infection','checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()})
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==299 and hits[0]['time']==30 and hits[-1]['time']==8970 and s.ctx.resources.current('actor','hp')==100000-299*180
 assert not any(b['definition']=='buff/ch8/environment/tile_infection' for b in s.ctx.get('actor',('buffs','instances'))) and s.ctx.attributes.value('actor','atk')==200 and s.ctx.attributes.value('actor','attack_speed_ratio')==1
