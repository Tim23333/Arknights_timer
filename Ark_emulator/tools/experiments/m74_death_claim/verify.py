import sys,json,hashlib,subprocess,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m74_death_claim_candidate';BASE=ROOT.parent/'unpack_work/campaign_m61_rebirth_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m74_death_claim'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(thaw(v),indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();files=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'}];start={str(p.relative_to(RUNTIME)):sha(p) for p in files};cases=[];inputs=[];original=Compiler.compile
 def captured(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):02d}.json';write(path,p);inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_claim.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
 for label,runtime in [('original_parent',BASE),('corrected_candidate',RUNTIME)]:
  run=subprocess.run([sys.executable,str(Path(__file__).with_name('capture.py')),str(runtime),str(OUT/(label+'.json'))],capture_output=True,text=True);assert run.returncode==0,run.stderr
 parent=json.loads((OUT/'original_parent.json').read_bytes());new=json.loads((OUT/'corrected_candidate.json').read_bytes());assert len(parent['actual_kills'])==2 and len(new['actual_kills'])==1 and parent['snapshot']['state']['kills']==new['snapshot']['state']['kills']==1 and new['actual_kills'][0]['source']==2
 p=new['input'];program=Compiler().compile(p);s=Engine.create(program,seed=610031);s.submit({'action':'skill','source':'hero','ability':'ability/damage'},at=1);s.advance(1);cp=OUT/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(16);r.advance(16);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
 write(OUT/'public_final.json',s.snapshot());write(OUT/'public_replay.json',s.export_replay())
 changed={};patch=[]
 for path in files:
  old=BASE/'ark_sim'/path.relative_to(RUNTIME/'ark_sim')
  if old.read_bytes()!=path.read_bytes():
   name=str(path.relative_to(RUNTIME)).replace('\\','/');changed[name]=sha(path);patch+=list(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True),path.read_text(encoding='utf8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 assert set(changed)=={'ark_sim/domains/lifecycle.py','ark_sim/domains/effects.py','ark_sim/domains/rebirth.py'};(OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8')
 assert start=={str(p.relative_to(RUNTIME)):sha(p) for p in files} and before==implementation_digest()
 names=[str(p.relative_to(ROOT)) for p in Path(__file__).parent.glob('*.py')]+['validation/campaign/m61_roster_peer/initial_review.json','validation/campaign/m74_death_claim/compat.log']
 report={'schema':'ark-sim/death-claim-review/v1','status':'passed_bounded_model_fix','core_before':before,'core_after':implementation_digest(),'actual_module':sys.modules['ark_sim'].__file__,'source_before':start,'source_after':start,'source_locks':{n:sha(ROOT/n) for n in names},'changed_source_files':changed,'cases':cases,'actual_inputs':inputs,'counterexample':{'old_core':parent['core'],'new_core':new['core'],'old_kill_events':parent['actual_kills'],'new_kill_events':new['actual_kills'],'old_world_kills':1,'new_world_kills':1,'expected_single_actual_executor':2},'public_checkpoint_resume_equal':True,'public_command_replay_equal':True,'program_fingerprint':program.fingerprint,'public_files':{str(p.relative_to(ROOT)):sha(p) for p in [cp,OUT/'public_final.json',OUT/'public_replay.json',OUT/'original_parent.json',OUT/'corrected_candidate.json']},'semantic_changes':['Real new dead transition adds World runtime.death_generation; repeated dead retirement does not','World atomic claim before emit preserves first actual executor, duplicate outer settlement cannot emit second event','explicit expected generation supports stale epoch rejection; direct same-UID API reenable fixture clearly separate from command replay','normal death paths add generation/claim metadata; not claimed raw World equal across versions','optional damage_attribution preserves explicit M72 sourceNone entity.died shape; does not inject None fields on default actor path'],'remaining_integration':['M72 no_source_damage emission loop must use claim_combat_kill with its exact sourceNone/origin payload in a new combined core; not claimed already repaired','Frost complete skills/blackice/control immunity still separate'],'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'candidate_final.json',report);print(json.dumps({'core':before,'cases':len(cases),'report_sha256':sha(OUT/'candidate_final.json'),'changed':changed}))
if __name__=='__main__':main()
