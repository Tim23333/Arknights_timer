"""Source-owned waiting Immo, with true zero HP and typed membership gates."""
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter07_boss.test_mechanism_v5 import package as original,deploy,kill,ev
from tools.chapter07_boss.build_mechanism_v1 import OUT
from tools.chapter07_boss.build_waiting_v1 import IMMO
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def package():
 q=original();p=json.loads((OUT/'waiting.mechanism.v2.json').read_bytes());p['entities']+=q['entities'][1:]
 for bucket in ['abilities','selectors']:
  for d in q[bucket]:
   if d['id'].startswith(('ability/test/','selector/test/')):p[bucket].append(d)
 p['scenarioDraft']=q['scenarioDraft'];return p
def make(p=None):return Engine.create(Compiler().compile(p or package()),seed=7187)
def start(p=None):s=make(p);deploy(s);kill(s,5);return s
def test_actual_hp0_owned_timer29_immo_typed_sourcearea_current_atk():
 s=start();s.session.advance(31)
 assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
 assert [e['time'] for e in ev(s,'ability.started') if e['payload']['ability']==IMMO]==[29]
 areas=ev(s,'area.resolved');assert len(areas)==1 and len(areas[0]['payload']['members'])==1
 ps=[e for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')];assert len(ps)==1 and ps[0]['time']==29 and ps[0]['payload']['amount']==pytest.approx(1920*.0521)
@pytest.mark.parametrize('field,value',[('motion',2),('camouflage',True),('target_free',True)])
def test_actual_ground_camo_targetfree_native_gate_still_zero_member_cast(field,value):
 p=package();p['entities'][1]['components']['selection_state'][field]=value;s=start(p);s.session.advance(31)
 assert [e['time'] for e in ev(s,'ability.started') if e['payload']['ability']==IMMO]==[29]
 assert len(ev(s,'area.resolved'))==1 and not ev(s,'area.resolved')[0]['payload']['members']
@pytest.mark.parametrize('tick',[6,30])
def test_actual_owned_waiting_publiccp_head_and_no_reanimation(tick,tmp_path):
 s=start();s.session.advance(tick);p=tmp_path/'waiting.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h));s.session.advance(55-tick);r.session.advance(55-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
 assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss')
def test_publicmanual_source_cannot_use_waiting_action_privilege():
 s=start();s.submit({'action':'skill','source':'boss','ability':IMMO},at=6);s.session.advance(8)
 assert not [e for e in ev(s,'ability.started') if e['payload']['ability']==IMMO]
