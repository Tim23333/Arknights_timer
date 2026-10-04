from tools.experiments.chapter06_buff_joint_peer.test_peer import fixture,make,capture,exact
def test_same_public_cast_zero_def_buff_cannot_reduce_following_damage_packet(tmp_path):
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0}]}",permanent=True);p['buffs'][1]['modifiers']=[{'attribute':'def','layer':'flat','value':13}]
 for ent in p['entities']:ent['components']['attributes']['base'].update({'def':0,'mres':0})
 p['abilities'][0]['activation']['on_start'].append({'op':'damage','target':3,'damage_type':'physical','scale':1})
 s=make(p);s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1);exact(s,tmp_path,2);capture(s,'public_zero_def_packet')
 assert [x['payload']['amount'] for x in s.session.events if x['type']=='damage.accepted']==[80]
def test_scheduled_public_zero_control_cannot_interrupt_existing_manual_cast(tmp_path):
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0}]}",permanent=True)
 p['buffs'][1]['control']={'attack':False,'abilities':False,'interrupt':True}
 p['abilities'].append({'id':'ability/peer/hold','kind':'ability','activation':{'mode':'manual'},'duration_seconds':1,'timeline':[]});p['entities'][1]['components']['abilities']=['ability/peer/hold']
 s=make(p);s.submit({'action':'skill','source':'victim','ability':'ability/peer/hold'},at=0);s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=1);s.advance(1);exact(s,tmp_path,34);capture(s,'public_zero_control_hold')
 assert not [x for x in s.session.events if x['type']=='ability.interrupted']
 assert len([x for x in s.session.events if x['type']=='ability.finished' and x['payload']['source']==3])==1
