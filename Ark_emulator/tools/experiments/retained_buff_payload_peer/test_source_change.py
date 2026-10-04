from tools.experiments.retained_buff_payload_peer.test_peer import fixture,make,capture
def test_source_withdrawn_by_first_application_callback_stops_remaining_prechange_plan():
 p,_=fixture();p['buffs'][0]['effects']=[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]
 p['abilities'][0]['activation']['on_start'][0]['on_success'][0]['allowed'].append('buff/peer/unlaunched')
 p['rules'][0]['implementation']['expression']="{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/launched','duration_seconds':1},{'kind':'apply','buff':'buff/peer/unlaunched','duration_seconds':1}]}"
 s=make(p);s.submit({'action':'skill','source':'source','ability':'ability/peer/shot'},at=0)
 try:s.advance(10)
 finally:capture(s,'source_withdraw_callback')
 assert not s.ctx.active('source') and [b['definition'] for b in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
