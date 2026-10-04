from tools.experiments.retained_buff_payload_peer.test_peer import fixture,make,capture
def test_source_withdrawn_in_first_packet_payload_blocks_later_sibling_prechange_payload_plan():
 p,second=fixture();p['buffs'][0]['effects']=[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]
 p['abilities'][0]['activation']['on_start'][0]['on_success'].append(second)
 s=make(p);s.submit({'action':'skill','source':'source','ability':'ability/peer/shot'},at=0)
 try:s.advance(10)
 finally:capture(s,'sibling_after_source_withdraw')
 assert not s.ctx.active('source') and [b['definition'] for b in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
