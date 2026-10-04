from tools.experiments.retained_buff_payload_peer.test_peer import fixture,make,capture,fire
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim import Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
def test_real_hp_zero_death_before_impact_keeps_true_launched_payload_and_public_disk_head(tmp_path):
 p,_=fixture();p['abilities'][1]['activation']['on_start']=[{'op':'modify_resource','target':2,'resource':'hp','value':0}]
 s=make(p);fire(s);s.advance(4);assert s.ctx.resources.current('source','hp')==0 and not s.ctx.active('source') and s.ctx.get('source',('runtime','death_generation'))==1
 cp=tmp_path/'dead_prehit.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.advance(6);r.advance(6);rep=replay(s.program,s.export_replay());capture(s,'hpzero_source_entry')
 assert s.checkpoint()==r.checkpoint()==rep.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(rep.session.events))
 assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[60]
 assert [b['definition'] for b in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
 assert not s.ctx.projectiles._impact_payload_scopes and not s.ctx.projectiles._inflight_hits
