import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate'));sys.path.insert(1,str(ROOT))
from tools.experiments.chapter06_boss_peer.test_peer_fullbusy import fixture,make,skill,providers
from ark_sim import Engine
from tools.campaign_ordered_checkpoint import load_bound
from ark_sim.contracts import thaw
import hashlib
OUT=ROOT/'validation/campaign/chapter06_boss_checkpoint_query_identity';OUT.mkdir(exist_ok=False)
path=next((ROOT/'validation/campaign/chapter06_boss_mechanisms_independent/actual_ordered_cps').glob('test_hp_zero*/boss_ordered.json'));pin=hashlib.sha256(path.read_bytes()).hexdigest()
s=make(fixture());skill(s,'hit',5);skill(s,'small',904);skill(s,'small',905);skill(s,'hit',906);s.advance(6);s.advance(300);assert s.ctx.attributes.values('boss')['atk']==660;r=Engine.restore(s.program,load_bound(path,pin),providers=providers())
def diff(a,b,path='$'):
 if type(a)!=type(b):return {'path':path,'forward_type':str(type(a)),'restore_type':str(type(b)),'forward':a,'restored':b}
 if isinstance(a,dict):
  if set(a)!=set(b):return {'path':path,'forward_keys':list(a),'restore_keys':list(b)}
  for k in a:
   d=diff(a[k],b[k],path+'.'+str(k))
   if d:return d
 elif isinstance(a,list):
  if len(a)!=len(b):return {'path':path,'forward_len':len(a),'restored_len':len(b)}
  for i,(x,y) in enumerate(zip(a,b)):
   d=diff(x,y,path+'['+str(i)+']')
   if d:return d
 elif a!=b:return {'path':path,'forward':a,'restored':b}
 return None
rows=[]
from ark_sim.tools.replay import replay
head=replay(s.program,s.export_replay(),providers=providers())
initial={'with_same_query_CPrestore_diff':diff(s.checkpoint(),r.checkpoint()),'head_without_private_query_diff':diff(s.checkpoint(),head.checkpoint())}
print(json.dumps(initial))
with (OUT/'query_identity.json').open('x',encoding='utf8') as f:json.dump(initial,f,indent=2)
for step in range(25):
 d=diff(s.checkpoint(),r.checkpoint());rows.append({'clock':s.session.time,'diff':d})
 if d:break
 s.advance(1);r.advance(1)
print(json.dumps(rows,ensure_ascii=False))
for name,obj in [('diff.json',rows),('forward.events.json',thaw(tuple(s.session.events))),('restored.events.json',thaw(tuple(r.session.events))),('forward.checkpoint.json',s.checkpoint()),('restored.checkpoint.json',r.checkpoint())]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
