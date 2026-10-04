import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m53_qualified_area_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter03_mortar';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(thaw(v),indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();assert before=='5ed2a57028755f6781bccfbc6845ad62fd841f5d96d55f1d49cdc973acace047';cases=[];inputs=[];original=Compiler.compile
 def captured(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):02d}.json';write(path,thaw(p));inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_mortar.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
 from tools.experiments.chapter03_mortar.test_mortar import fixture
 evidence=[]
 for kind in ('moving_live','target_retired','source_retired'):
  p=fixture();commands=[]
  if kind=='moving_live':
   p['scenarioDraft']['initialEntities'][2]['position']={'row':4,'col':5};commands=[{'action':'skill','source':'main','ability':'ability/move','at':30},{'action':'skill','source':'director','ability':'ability/boost','at':30}]
  else:commands=[{'action':'skill','source':'main' if kind=='target_retired' else 'director','ability':'ability/withdraw' if kind=='target_retired' else 'ability/retire_source','at':30}]
  program=Compiler().compile(p);s=Engine.create(program,seed=5321)
  for cmd in commands:s.submit({k:v for k,v in cmd.items() if k!='at'},at=cmd['at'])
  s.advance(25);directory=OUT/kind;directory.mkdir(exist_ok=True);cp=directory/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(40);r.advance(40);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
  for name,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:write(directory/name,value)
  evidence.append({'case':kind,'checkpoint_resume_equal':True,'command_replay_equal':True,'actual_damage_packets':[e['payload'] for e in s.session.events if e['type']=='damage.accepted'],'files':{str(path.relative_to(ROOT)):sha(path) for path in directory.iterdir()}})
 check=subprocess.run([sys.executable,'tools/build_chapter03_mortar.py','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert check.returncode==0,check.stderr
 after=implementation_digest();assert before==after
 names=['tools/build_chapter03_mortar.py','packages/campaign/chapter03_models/mortar.reference.json','packages/campaign/chapter03_sources/native.reference.json','tools/experiments/chapter03_mortar/test_mortar.py',str(Path(__file__).relative_to(ROOT)),'validation/campaign/m53_qualified_area/candidate_final.json','validation/campaign/m53_qualified_area/compat_fresh.log']
 report={'schema':'ark-sim/chapter03-mortar-review/v1','status':'passed_declared_reference_profile','actual_module':sys.modules['ark_sim'].__file__,'core_before':before,'core_after':after,'source_locks':{n:sha(ROOT/n) for n in names},'cases':cases,'actual_inputs':inputs,'public_evidence':evidence,'builder_check':check.stdout,'scope':['exact VID stats3300/400/150/0/range7/interval4.5','exact source OnAttack16, projectile speed4/lifetime10/infinity inactive1','ground primary versus typed ground/fly nine-cell source Hit qualification','actual impact point after public target move; captured actorID remains','source ATK +100 after launch yields450 rather than350','source and target retirement retain packet/last point, only living qualified actors receive physical settlement','route-hidden primary excluded while other qualified members hit','source targetFree/camouflage17 distinct; primary cannot select17, impact explicitly ignores17','reach and expiry each one blast quota, no double dispatch','ordered CP and commands replay for three actual public fixtures'],'feedback_pending':['native method bodies, paracurve3D/collider callback ordering and FROM_OWNER selector dispatch','selected mathematical homing/expiry/retention profile can be replaced by pure rules','INVISIBLE9 is enforced only in subsequent M49+M53 merged candidate, not claimed by this standalone M48-derived core'],'client_verified':False,'whole_stage_executed':False,'formal_approved':False}
 write(OUT/'final_review.json',report);print(json.dumps({'passed':len(cases),'core':before,'report_sha256':sha(OUT/'final_review.json'),'module_sha256':sha(ROOT/names[1])}))
if __name__=='__main__':main()
