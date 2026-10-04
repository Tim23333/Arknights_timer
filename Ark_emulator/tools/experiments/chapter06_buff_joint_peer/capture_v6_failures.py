import sys,json,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v6_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.contracts import thaw
from tools.experiments.chapter06_buff_joint_peer.test_peer import fixture,make
OUT=ROOT/'validation/campaign/chapter06_buff_joint_peer_v6'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
captures=[]
for mode in ['unhashable_handle','zero_immediate']:
 if mode=='unhashable_handle':p,e=fixture("{'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/a','instance':[],'generation':1}]}")
 else:
  p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0}]}",permanent=True);p['buffs'][1]['control']={'attack':False};p['buffs'][1]['effects']=[{'op':'modify_resource','resource':'hp','delta':-25}]
 s=make(p);before=s.checkpoint();error=None
 try:
  s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1)
 except Exception:error=traceback.format_exc()
 captures.append({'case':mode,'input':p,'before':before,'after':s.checkpoint(),'commands':s.export_replay(),'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'error':error,'world_equal':before['session']['world']==s.checkpoint()['session']['world'] if 'session' in before else None})
with (OUT/'fresh_failure_capture.json').open('x',encoding='utf8') as f:json.dump(captures,f,ensure_ascii=False,indent=2)
print(sha(OUT/'fresh_failure_capture.json'))
