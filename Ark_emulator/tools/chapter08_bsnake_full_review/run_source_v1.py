import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_bsnake_combat.policies_v1 import providers as combat
from tools.chapter08_bsnake_skills.policies_v1 import providers as skills
from tools.chapter08_bsnake.screen_policy_v1 import providers as screen
from tools.chapter08_joint_v4.build_summon_hint_v2 import providers as hint
from tools.chapter08_flame_device.policies_v1 import providers as flame
def providers():return {**combat(),**skills(),**screen(),**hint(),**flame()}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
INPUT=ROOT/'validation/campaign/chapter08_bsnake_full_input_v2'
OUT=ROOT/'validation/campaign/chapter08_bsnake_full_actual_v1';OUT.mkdir(exist_ok=False)
core=implementation_digest();assert core=='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
guards={str(p):sha(p) for p in list(RUNTIME.rglob('*.py'))+list(RUNTIME.rglob('*.json'))+[Path(__file__),INPUT/'input.json',INPUT/'commands.json']}
def save(name,value):
 p=OUT/name;p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf8');return sha(p)
save('guards.before.json',guards)
p=json.loads((INPUT/'input.json').read_bytes());program=Compiler(providers=providers()).compile(p)
s=Engine.create(program,providers=providers(),seed=884500)
for c in json.loads((INPUT/'commands.json').read_bytes()):
 s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
start=time.perf_counter()
for end in (58,118,200):
 s.advance(end-s.session.time);print(json.dumps({'clock':s.session.time,'events':len(s.session.events),'boss':s.ctx.get(20,('lifecycle',)),'hp':s.ctx.resources.current(20,'hp')}),flush=True)
assert s.ctx.resources.current(20,'hp')==0
pin=write_ordered(OUT/'waiting200.checkpoint.json',s.checkpoint())
save('waiting200.pin.json',pin)
r=Engine.restore(program,load_bound(OUT/'waiting200.checkpoint.json',pin),providers=providers())
for end in (208,1048,1498,3400,4501,4651,4900,5491,5600):
 s.advance(end-s.session.time);print(json.dumps({'clock':s.session.time,'events':len(s.session.events),'hp':s.ctx.resources.current(20,'hp'),'mode':s.ctx.resources.current(20,'mode')}),flush=True)
 if end==208:assert s.ctx.resources.current(20,'hp')==75000
 if end==4900:
  terminalpin=write_ordered(OUT/'terminal4900.checkpoint.json',s.checkpoint());save('terminal4900.pin.json',terminalpin)
r.advance(5600-r.session.time)
assert s.checkpoint()==r.checkpoint(),'waiting200 continuation differs'
t=Engine.restore(program,load_bound(OUT/'terminal4900.checkpoint.json',terminalpin),providers=providers());t.advance(700)
assert s.checkpoint()==t.checkpoint(),'terminal4900 continuation differs'
h=replay(program,s.export_replay(),providers=providers())
assert s.checkpoint()==h.checkpoint(),'public head differs'
for name,sim in [('forward',s),('restored',r),('head',h)]:
 save(name+'.capture.json',{'checkpoint':sim.checkpoint(),'events':thaw(tuple(sim.session.events)),'replay':sim.export_replay()})
assert guards=={p:sha(Path(p)) for p in guards},'guards changed'
save('verification.json',{'passed':True,'core':core,'scope':'Controlled source 75k four modes; full stage not asserted. Numerical source assertions reviewed separately.','waiting200_and_terminal4900_and_public_head_equal':True,'events':len(s.session.events),'seconds':time.perf_counter()-start,'guards_equal':True})
print('COMPLETE '+sha(OUT/'verification.json'),flush=True)
