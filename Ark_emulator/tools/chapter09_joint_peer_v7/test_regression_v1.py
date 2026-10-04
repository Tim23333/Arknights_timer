"""Real v6 regression: inactive Buff flags must not authorize attachment cancellation."""
from tools.chapter09_joint_peer_v7.test_v1 import fixture,rule,create,events,receipt,guard,START,digest
from ark_sim.domains.selection import DEFAULT_STATE

def test_inactive_source_flag_is_not_an_attachment_cancel_flag():
 p=fixture();p['rules'].append(rule('rule/peer/inactive','buff.applicability','False'));p['buffs'].append({'id':'buff/peer/inactive_stun','kind':'buff','selection_flags':{'abnormal_flags':[0]},'active_rule':'rule/peer/inactive'});p['entities'][0]['components']['buffs']={'initial':['buff/peer/inactive_stun']}
 s=create(p);assert s.ctx.spatial.selection_state('source',DEFAULT_STATE)['abnormal_flags']==[];assert s.ctx.get('source',('buffs','instances'))[0]['applicability']=={'active':False,'control':False};s.advance(45)
 observed={'health_packets':[t for t,_ in events(s,'damage.accepted')],'EP_packets':[t for t,_ in events(s,'elemental.loss.accepted')],'attachment_finished':events(s,'attachment.finished'),'expected_packets':[2,14,26],'source_rule_is_inactive':True,'source_guard':guard()==START,'input_digest':digest(p)};receipt('actual_inactive_flag_regression',observed)
 assert observed['health_packets']==observed['EP_packets']==[2,14,26]

def test_inactive_immunity_cannot_hide_actual_source_cancel_flag():
 p=fixture();p['rules'].append(rule('rule/peer/inactive','buff.applicability','False'));p['buffs'].append({'id':'buff/peer/inactive_immunity','kind':'buff','selection_flags':{'abnormal_immunes':[0]},'active_rule':'rule/peer/inactive'});p['entities'][0]['components']['buffs']={'initial':['buff/peer/inactive_immunity']};p['scenarioDraft']['commands'].append({'at':1,'action':'skill','source':'controller','ability':'ability/peer/foreign_stun'})
 s=create(p);s.advance(2);assert s.ctx.spatial.selection_state('source',DEFAULT_STATE)['abnormal_flags']==[0];s.advance(43)
 observed={'health_packets':[t for t,_ in events(s,'damage.accepted')],'EP_packets':[t for t,_ in events(s,'elemental.loss.accepted')],'attachment_finished':events(s,'attachment.finished'),'expected_packets':[],'actual_projected_stun_flag':[0],'inactive_immunity':True,'source_guard':guard()==START,'input_digest':digest(p)};receipt('actual_inactive_immunity_regression',observed)
 assert observed['health_packets']==observed['EP_packets']==[]

def test_active_flag_with_control_disabled_still_contributes_cancel_status():
 p=fixture();p['rules'].append(rule('rule/peer/no_control','buff.applicability','False'));p['buffs'].append({'id':'buff/peer/active_flag_no_control','kind':'buff','selection_flags':{'abnormal_flags':[0]},'control':{'abilities':False},'control_rule':'rule/peer/no_control'});p['entities'][0]['components']['buffs']={'initial':['buff/peer/active_flag_no_control']}
 s=create(p);assert s.ctx.get('source',('buffs','instances'))[0]['applicability']=={'active':True,'control':False};assert s.ctx.spatial.selection_state('source',DEFAULT_STATE)['abnormal_flags']==[0];s.advance(45)
 assert not events(s,'command.rejected');assert events(s,'damage.accepted')==events(s,'elemental.loss.accepted')==[];assert events(s,'attachment.finished')[0][1]['reason']=='source_flags';receipt('active_control_disabled_guard',{'passes':True,'active_status_contribution_distinct_from_control':True,'source_guard':guard()==START})

def test_source_base_cancel_flag_survives_buff_applicability_filter():
 p=fixture();p['entities'][0]['components']['selection_state']['abnormal_flags']=[12];s=create(p);assert s.ctx.spatial.selection_state('source',DEFAULT_STATE)['abnormal_flags']==[12];s.advance(45)
 assert not events(s,'command.rejected');assert events(s,'damage.accepted')==events(s,'elemental.loss.accepted')==[];assert events(s,'attachment.finished')[0][1]['reason']=='source_flags';receipt('source_base_flag_guard',{'passes':True,'base_status_contribution_survives_filter':True,'source_guard':guard()==START})
