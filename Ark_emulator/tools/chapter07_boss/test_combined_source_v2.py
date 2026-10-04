"""Joint source Aura/current Immo/typed targets/true lifecycle CP boundaries."""
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter07_boss.test_spear_v2 import package as original,deploy,kill,ev
from tools.chapter07_boss.build_mechanism_v1 import OUT,UID,MARKER
from tools.chapter07_boss.build_waiting_v1 import IMMO
from tools.chapter07_boss.policies_v2 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def package():
 q=original();p=json.loads((OUT/'combined.mechanism.v2.json').read_bytes());p['entities']+=q['entities'][1:]
 for k in ['abilities','selectors']:p[k]+=[d for d in q[k] if d['id'].startswith(('ability/test/','selector/test/'))]
 p['scenarioDraft']=q['scenarioDraft'];return p
def make(p=None):return Engine.create(Compiler(providers=providers()).compile(p or package()),providers=providers(),seed=7187)
def start(p=None):s=make(p);deploy(s);kill(s,5);return s
def test_actual_same_boss_hp0_self_and_ally_aura_current_atk_immo_once():
 s=start();s.session.advance(55);atk=s.ctx.attributes.value('boss','atk');assert atk==2240
 assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
 assert s.ctx.attributes.value('ally','atk')==120 and s.ctx.attributes.value('ally','def')==250
 assert any(b['definition']==MARKER for b in s.ctx.get('boss',('buffs','instances'),[]))
 ps=[(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')];assert [t for t,d in ps]==[29,53] and all(d==pytest.approx(atk*.0521) for t,d in ps)
 assert len(ev(s,'area.resolved'))==2
@pytest.mark.parametrize('field,value',[('motion',2),('camouflage',True),('target_free',True)])
def test_joint_source_typed_ground_camo_targetfree_not_bypassed_by_lifecycle_lease(field,value):
 p=package();p['entities'][1]['components']['selection_state'][field]=value;s=start(p);s.session.advance(31)
 assert [e['time'] for e in ev(s,'ability.started') if e['payload']['ability']==IMMO]==[29]
 assert not ev(s,'area.resolved')[0]['payload']['members']
@pytest.mark.parametrize('tick',[6,30])
def test_joint_source_true_waiting_diskcp_and_public_head(tick,tmp_path):
 s=start();s.session.advance(tick);p=tmp_path/'joint.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h),providers=providers());s.session.advance(55-tick);r.session.advance(55-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
def test_joint_actual_owner_retire_cancels_waiting_actions_and_all_child_leases():
 p=package();aid='ability/test/patrt/retire';p['entities'][1]['components']['abilities'].append(aid);p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'retire','target':2,'parameters':{'reason':'controlled_joint_retire'}}}]});s=start(p);s.submit({'action':'skill','source':'hero','ability':aid},at=31);s.session.advance(60)
 assert [e['time'] for e in ev(s,'ability.started') if e['payload']['ability']==IMMO]==[29]
 assert s.ctx.attributes.value('ally','atk')==100 and s.ctx.attributes.value('ally','def')==50
 assert not any(b['definition']==MARKER for b in s.ctx.get('ally',('buffs','instances'),[]))
