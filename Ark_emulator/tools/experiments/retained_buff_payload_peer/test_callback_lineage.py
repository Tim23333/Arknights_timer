from tools.experiments.retained_buff_payload_peer.test_peer import fixture,make,capture
def test_on_remove_existing_cold_cannot_create_unlaunched_buff_under_impact_authority():
 p,forged=fixture();p['buffs'][0]['on_remove']=[forged]
 p['rules'][0]['implementation']['expression']="{'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/launched','instance':'buff/3/1','generation':1},{'kind':'apply','buff':'buff/peer/launched','duration_seconds':1}]}"
 initial={'id':'ability/peer/initial_cold','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':3,'buff':'buff/peer/launched'}]},'timeline':[]};p['abilities'].append(initial);p['entities'][0]['components']['abilities'].append(initial['id'])
 s=make(p);s.submit({'action':'skill','source':'source','ability':initial['id']},at=0);s.submit({'action':'skill','source':'source','ability':'ability/peer/shot'},at=1);s.submit({'action':'skill','source':'controller','ability':'ability/peer/retire_source'},at=2)
 try:s.advance(10)
 finally:capture(s,'on_remove_unlaunched')
 assert [b['definition'] for b in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
