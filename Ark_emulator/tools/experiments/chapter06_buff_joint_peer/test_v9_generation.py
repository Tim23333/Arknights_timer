from tools.experiments.chapter06_buff_joint_peer.test_peer import fixture,make,buffs,capture,exact
def test_public_remove_callback_refreshes_later_handle_and_old_generation_is_not_removed(tmp_path):
 p,e=fixture("{'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/a','instance':'buff/3/1','generation':1},{'kind':'remove','buff':'buff/peer/b','instance':'buff/3/2','generation':1}]}")
 p['buffs'][0]['on_remove']=[{'op':'apply_buff','target':3,'buff':'buff/peer/b'}];p['entities'][1]['components']['buffs']={'initial':['buff/peer/a','buff/peer/b']}
 s=make(p);assert [(b['id'],b['generation']) for b in buffs(s)]==[('buff/3/1',1),('buff/3/2',1)]
 s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1);exact(s,tmp_path,7);capture(s,'refreshed_handle_generation')
 assert [(b['definition'],b['id'],b['generation']) for b in buffs(s)]==[('buff/peer/b','buff/3/2',2)]
 assert [e['payload']['buff'] for e in s.session.events if e['type']=='buff.removed']==['buff/peer/a']
