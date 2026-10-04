"""Historical rate sample context and attribute time-dependent source rules."""
from tools.chapter08_buff_lifetime_review.test_joint_peer_v2 import package,make,command,equality,removed,packets

def test_attributeclock_read_same_sampletime_as_rate_expression(tmp_path):
    p=package();p['entities'][0]['rules']={'attributes.effective':'rule/peer/temporal_attr'}
    p['rules'].append({'id':'rule/peer/temporal_attr','kind':'rule','contract':'attributes.effective',
        'implementation':{'type':'expression','expression':'(1 if context.time < 3 else 2) if context.attribute == "clock_rate" else inputs.base'}})
    s=make(p);command(s,'install',0);equality(s,tmp_path,2,8)
    assert removed(s)==[5] and packets(s)==[2,4]

def test_rate_nestedcontextseconds_and_clocktimestamp_agree(tmp_path):
    p=package();p['rules'][0]['implementation']['expression']='1 if inputs.clock.time == context.time and context.seconds == context.time * context.quantum else -1'
    s=make(p);command(s,'install',0);equality(s,tmp_path,2,9)
    assert removed(s)==[6] and packets(s)==[2,4]
