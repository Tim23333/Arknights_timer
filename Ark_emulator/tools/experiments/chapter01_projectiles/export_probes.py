import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m17_projectile_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.experiments.chapter01_projectiles.test_lifecycle import base,events
before=implementation_digest();cases=[]
for name,attach in [('normal','fixed'),('C4_fixed','fixed'),('C4_follow','follow')]:
 p=base(attach,normal=name=='normal',targets=((3,4),(3,5)));sim=Engine.create(Compiler().compile(p),seed=1701)
 if name!='normal':sim.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);sim.submit({'action':'skill','source':'target0','ability':'ability/target_move'},at=50)
 sim.advance(31 if name=='normal' else 113);saved=sim.checkpoint();restored=Engine.restore(sim.program,saved);sim.advance(2);restored.advance(2);assert sim.snapshot()==restored.snapshot();assert sim.snapshot()==replay(sim.program,sim.export_replay()).snapshot()
 cases.append({'case':name,'program_fingerprint':sim.program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,'fixture':p,'commands':sim.export_replay(),'checkpoint_equal':True,'replay_equal':True,'observed_events':thaw([e for e in sim.session.events if e['type'] in {'projectile.launched','projectile.reached','projectile.hit','projectile.invalid','damage.accepted','area.resolved','ability.finished','command.accepted'}]),'projectile_state':sim.ctx.get('system/battle',('projectiles',))})
assert implementation_digest()==before
result={'schema':'ark-sim/projectile-model-probes/v1','passed':True,'implementation_sha256':before,'runtime_module':sys.modules['ark_sim'].__file__,'cases':cases,'formal_approval':False,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed'}]}
(ROOT/'validation/campaign/m17_projectiles/probes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'cases':len(cases),'core':before}))
