import sys,json,hashlib,subprocess,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m61_rebirth_candidate';BASE=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m61_rebirth'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(thaw(v),indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')];source_before={str(p.relative_to(RUNTIME)):sha(p) for p in paths};cases=[];inputs=[];original=Compiler.compile
 def captured(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):02d}.json';write(path,p);inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_rebirth.py')),str(Path(__file__).with_name('test_frostnova.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
 from tools.experiments.m61_rebirth.test_frostnova import fixture
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=6121);commands=[{'action':'skill','source':'boss','ability':'ability/synthetic_phase_probe','at':1},{'action':'skill','source':'director','ability':'ability/knockdown','at':2},{'action':'skill','source':'boss','ability':'ability/synthetic_phase_probe','at':152},{'action':'skill','source':'director','ability':'ability/knockdown','at':153}]
 for cmd in commands:s.submit({k:v for k,v in cmd.items() if k!='at'},at=cmd['at'])
 s.advance(90);cp=OUT/'frost.checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(65);r.advance(65);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
 for name,v in [('frost.input.json',p),('frost.commands.json',commands),('frost.replay.json',s.export_replay()),('frost.final.json',s.snapshot())]:write(OUT/name,v)
 from tools.experiments.m61_rebirth.test_rebirth import fixture as generic
 p=generic();p['entities'][0]['components'].pop('rebirth');p['rules']=[];p['abilities']=[a for a in p['abilities'] if a['id'] in {'ability/hit','ability/withdraw'}];p['entities'][1]['components']['abilities']=['ability/hit','ability/withdraw'];write(OUT/'noopt.input.json',p)
 for label,runtime in [('parent',BASE),('candidate',RUNTIME)]:
  run=subprocess.run([sys.executable,str(Path(__file__).with_name('capture_noopt.py')),str(runtime),str(OUT/'noopt.input.json'),str(OUT/f'noopt.{label}.json')],capture_output=True,text=True);assert run.returncode==0,run.stderr
 a=json.loads((OUT/'noopt.parent.json').read_bytes());b=json.loads((OUT/'noopt.candidate.json').read_bytes());allowed={'snapshot/program_fingerprint','snapshot/runtime_fingerprint','checkpoint/program_fingerprint','checkpoint/runtime_fingerprint'};differences=[]
 def trace_paths(trace,path):
  if 'runtime_fingerprint' not in trace:return
  assert {'calculation_id','rule_id','contract_version','rule_fingerprint','stages'}<=set(trace);allowed.add(path+'/runtime_fingerprint')
  for i,stage in enumerate(trace['stages']):
   if 'trace' in stage:trace_paths(stage['trace'],path+f'/stages/{i}/trace')
 for prefix,events in [('snapshot/events',a['snapshot']['events']),('checkpoint/kernel/events/records',a['checkpoint']['kernel']['events']['records'])]:
  for i,event in enumerate(events):
   if event['type']=='calculation':trace_paths(event['payload']['trace'],f'{prefix}/{i}/payload/trace')
 def compare(x,y,path):
  assert type(x)==type(y),path
  if path in allowed:
   if x!=y:differences.append({'path':path,'parent':x,'candidate':y})
   return
  if isinstance(x,dict):
   assert set(x)==set(y),path
   for k in x:compare(x[k],y[k],path+'/'+k)
  elif isinstance(x,list):
   assert len(x)==len(y),path
   for i,(xx,yy) in enumerate(zip(x,y)):compare(xx,yy,path+'/'+str(i))
  else:assert x==y,(path,x,y)
 compare(a['snapshot'],b['snapshot'],'snapshot');compare(a['checkpoint'],b['checkpoint'],'checkpoint')
 changed={};patch=[]
 for path in paths:
  old=BASE/'ark_sim'/path.relative_to(RUNTIME/'ark_sim')
  if not old.exists() or old.read_bytes()!=path.read_bytes():
   name=str(path.relative_to(RUNTIME)).replace('\\','/');changed[name]=sha(path);patch+=list(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],path.read_text(encoding='utf8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8')
 check=subprocess.run([sys.executable,'tools/build_frostnova_rebirth_model.py','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert check.returncode==0,check.stderr
 source_after={str(p.relative_to(RUNTIME)):sha(p) for p in paths};assert source_before==source_after and before==implementation_digest()
 names=['tools/build_frostnova_rebirth_model.py','packages/campaign/chapter04_boss/m61/rebirth.reference_model.json','packages/campaign/chapter04_boss_plan/source.reference.json','validation/campaign/m61_rebirth/compat_final.log','tools/candidates/m61_rebirth/prepare.py']+[str(p.relative_to(ROOT)) for p in Path(__file__).parent.glob('*.py')]
 report={'schema':'ark-sim/rebirth-candidate-review/v1','status':'passed_bounded_declared_profile','core_before':before,'core_after':implementation_digest(),'actual_module':sys.modules['ark_sim'].__file__,'source_before':source_before,'source_after':source_after,'changed_source_files':changed,'source_locks':{n:sha(ROOT/n) for n in names},'cases':cases,'actual_inputs':inputs,'public_frost_checkpoint_resume_equal':True,'public_frost_command_replay_equal':True,'public_files':{str(p.relative_to(ROOT)):sha(p) for p in [cp,OUT/'frost.input.json',OUT/'frost.commands.json',OUT/'frost.replay.json',OUT/'frost.final.json']},'noopt_all_values_equal_except_exact_identity_paths':True,'noopt_identity_differences':differences,'noopt_events':len(b['snapshot']['events']),'noopt_raw_bytes_equal':False,'constructor_check':check.stdout,'source_frost_scope':{'exact_variant':'enemy_1505_frstar@0/9d1e3d01ef79ae3e','HP':25000,'ATK_before':420,'ATK_after':630,'down_seconds':5,'selected_restore_ratio':1,'serialized_restore_ratio':.5,'one_actor_one_final_kill':True,'synthetic_ATK_probe_not_native_attack':True},'remaining_gaps':['FrostNova normal/ArcticBlast/IceShield/tile RNG/blackice not authored by phase-only module','status immunity actual control/application consumer assigned M70','native timing/callback/body comparison and source/reference HP ratio conflict retained'],'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'candidate_final.json',report);print(json.dumps({'core':before,'cases':len(cases),'report_sha256':sha(OUT/'candidate_final.json'),'changed':list(changed),'noopt_events':len(b['snapshot']['events'])}))
if __name__=='__main__':main()
