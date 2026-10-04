from copy import deepcopy
from tools.chapter08_buff_lifetime_review.test_joint_peer_v2 import package,make,command,capture,packets,removed,equality,INPUTS,CAPTURES,REGISTRY
def test_time_expression_changes_at3_not_during_previous_interval_expected_expiry5(tmp_path):
 p=package();p['rules'][0]['implementation']['expression']='1 if inputs.clock.time < 3 else 2';s=make(p);command(s,'install',0);equality(s,tmp_path,2,8);capture(s,'time_expression');assert removed(s)==[5] and packets(s)==[2,4]
def test_finite_rate_marker_expiry3_keeps_last_2_to3_interval_then_timer_expires3(tmp_path):
 p=package();p['buffs'][1]['duration_seconds']=3/30;p['entities'][0]['components']['buffs']={'initial':['buff/peer/fast']};s=make(p);command(s,'install',0);equality(s,tmp_path,2,7);capture(s,'marker_expiry');assert removed(s)==[3] and packets(s)==[2]
