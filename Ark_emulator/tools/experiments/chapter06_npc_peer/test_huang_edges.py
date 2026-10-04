from tools.experiments.chapter06_npc_peer.test_huang_v7 import fixture,make,hit,capture,providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim import Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
def positives(s):return [e for e in s.session.events if e['type']=='resource.changed' and e['payload']['target']==2 and e['payload']['resource']=='hp' and e['payload']['delta']>0]
def exact(s,tmp,n):
 path=tmp/'huang_before.json';h=write_ordered(path,s.checkpoint());reg=providers();r=Engine.restore(s.program,load_bound(path,h),providers=reg);s.advance(n);r.advance(n);head=replay(s.program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
def test_abnormal_flag_seven_effective_heal_free_blocks_heal_and_consumes_once():
 s=make(fixture({'id':'buff/peer/flag7','kind':'buff','selection_flags':{'abnormal_flags':[7]}}));hit(s,10);s.advance(12);capture(s,'derived_flag7')
 assert s.ctx.resources.current('native_npc','hp')==1 and not positives(s)
 assert not [b for b in s.ctx.get('native_npc',('buffs','instances'),[]) if b['definition']=='buff/ch6/npc/huang_once']
def test_exact_expired_heal_free_allows_native_one_heal_and_disk_head(tmp_path):
 s=make(fixture({'id':'buff/peer/until10','kind':'buff','duration_seconds':10/30,'selection_flags':{'heal_free':True}}));hit(s,10);s.advance(9);exact(s,tmp_path,4);capture(s,'expired_heal_free')
 assert s.ctx.resources.current('native_npc','hp')==1153.5 and len(positives(s))==1
def test_same_frame_two_true_packets_have_only_one_heal_lock_parent_consumption_and_head(tmp_path):
 s=make(fixture());hit(s,10);hit(s,10);hit(s,191);s.advance(9);exact(s,tmp_path,183);capture(s,'same_frame_two_packets')
 assert not s.ctx.active('native_npc') and len(positives(s))==1 and positives(s)[0]['payload']['delta']==1152.5
 assert len([e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']=='buff/ch6/npc/huang_lock'])==1
def test_fifteen_second_resistance_installs_once_after_exact_first_interval():
 s=make(fixture());s.advance(450);assert not [e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']=='buff/ch6/npc/huang_resistance'];s.advance(451);capture(s,'resistance_15seconds')
 assert len([e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']=='buff/ch6/npc/huang_resistance'])==1
 assert [m['value'] for m in s.ctx.get('native_npc',('attributes','modifiers'),[]) if m['attribute']=='one_minus_status_resistance']==[-.5]
def test_effective_max_hp_change_during_lock_moves_real_half_hp_floor(tmp_path):
 p=fixture();p['buffs'].append({'id':'buff/peer/newmax','kind':'buff','modifiers':[{'attribute':'max_hp','layer':'flat','value':1000}]});p['abilities'].append({'id':'ability/peer/raise_max','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':'buff/peer/newmax'}]},'timeline':[]});p['entities'][-1]['components']['abilities'].append('ability/peer/raise_max')
 s=make(p);hit(s,10);s.submit({'action':'skill','source':'dealer','ability':'ability/peer/raise_max'},at=30);hit(s,40);s.advance(29);exact(s,tmp_path,13);capture(s,'dynamic_live_floor')
 assert s.ctx.resources.capacity('native_npc','hp')==3305 and s.ctx.resources.current('native_npc','hp')==1652.5
