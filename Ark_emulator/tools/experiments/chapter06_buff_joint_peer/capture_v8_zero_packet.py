import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v8_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_buff_joint_peer.test_peer import fixture,make
OUT=ROOT/'validation/campaign/chapter06_buff_joint_peer_v8_zero';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[Path(__file__),ROOT/'tools/experiments/chapter06_buff_joint_peer/test_peer.py']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'));before={str(p):sha(p) for p in files}
p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0}]}",permanent=True)
p['buffs'][1]['modifiers']=[{'attribute':'def','layer':'flat','value':13}]
for ent in p['entities']:ent['components']['attributes']['base'].update({'def':0,'mres':0})
p['abilities'][0]['activation']['on_start'].append({'op':'damage','target':3,'damage_type':'physical','scale':1})
s=make(p);s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1)
damage=[thaw(ev) for ev in s.session.events if ev['type']=='damage.accepted'];passed=len(damage)==1 and damage[0]['payload']['amount']==80
report={'core':implementation_digest(),'passed':passed,'expected_physical_damage':80,'actual_damage':damage,'input':p,'commands':s.export_replay(),'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'guards_before':before,'guards_after':{str(p):sha(p) for p in files},'scope':'Fresh public onecast explicitzeroDEF Buff immediately followed by normal physicalpacket; baseDEF0/ATK80. Nozero-time advance or privateattribute read used to cause counter.'}
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'passed':passed,'damage':damage,'sha':sha(OUT/'verification.json')}))
