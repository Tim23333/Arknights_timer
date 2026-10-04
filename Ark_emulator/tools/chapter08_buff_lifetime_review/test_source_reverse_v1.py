from copy import deepcopy
from tools.chapter08_buff_lifetime_review.test_source_peer_v4 import package,proof,INPUTS,CAPTURES,REG,MODULE,PARENT,CHILD
from ark_sim import Compiler,Engine
def test_source_initial_half_resistance_removed150_integrates300_plus615_nominalticks_expiry765(tmp_path):
 p=package();p['entities'][1]['components']['buffs']={'initial':['buff/peer/resistance']};p['entities'][1]['components']['abilities'].append('ability/peer/unresist');p['abilities'].append({'id':'ability/peer/unresist','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':'self','buff':'buff/peer/resistance'}]},'timeline':[]});INPUTS.append(deepcopy(p));program=Compiler(providers=REG).compile(p,packages=[str(MODULE)]);s=Engine.create(program,providers=REG,seed=8819311)
 s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=0);s.submit({'action':'skill','source':'firetarget','ability':'ability/peer/unresist'},at=150);proof(s,tmp_path,149,780)
 assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==PARENT]==[765]
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==list(range(30,751,30)) and [e['payload']['amount'] for e in hits]==[50+6*n for n in range(1,26)]
