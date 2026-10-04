import sys,json,hashlib,subprocess,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m59_area_primary_candidate';BASE=ROOT.parent/'unpack_work/campaign_m54_qualified_visibility_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m59_area_primary'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(thaw(v),indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();assert before=='84b4146bd574dda5dfd833314bee46c4370e583bcc8ef900075911fdafadbd9a';cases=[];inputs=[];original=Compiler.compile
 def captured(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):02d}.json';write(path,p);inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_primary.py')),str(Path(__file__).with_name('test_mortar.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
 from tools.experiments.m59_area_primary.test_primary import fixture,fire
 p=fixture(projectile=True);program=Compiler().compile(p);s=Engine.create(program,seed=5918);fire(s);s.advance(2);cp=OUT/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(5);r.advance(5);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
 for name,v in [('public_input.json',p),('public_replay.json',s.export_replay()),('public_final.json',s.snapshot())]:write(OUT/name,v)
 p=fixture(include=None);write(OUT/'noopt_input.json',p)
 for name,runtime in [('parent',BASE),('candidate',RUNTIME)]:
  run=subprocess.run([sys.executable,str(Path(__file__).with_name('capture_noopt.py')),str(runtime),str(OUT/'noopt_input.json'),str(OUT/f'noopt_{name}.json')],capture_output=True,text=True);assert run.returncode==0,run.stderr
 a=json.loads((OUT/'noopt_parent.json').read_bytes());b=json.loads((OUT/'noopt_candidate.json').read_bytes());allowed={'snapshot/program_fingerprint','checkpoint/program_fingerprint','snapshot/runtime_fingerprint','checkpoint/runtime_fingerprint'};differences=[]
 def trace_paths(trace,path):
  if 'runtime_fingerprint' not in trace:return
  assert {'calculation_id','rule_id','contract_version','rule_fingerprint','runtime_fingerprint','stages'}<=set(trace);allowed.add(path+'/runtime_fingerprint')
  if trace.get('provider',{}).get('name')=='ark.area.qualified_cell_offsets':
   allowed.add(path+'/rule_fingerprint');allowed.add(path+'/provider/source_sha256')
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
 for path in sorted((RUNTIME/'ark_sim').rglob('*.py')):
  old=BASE/'ark_sim'/path.relative_to(RUNTIME/'ark_sim')
  if not old.exists() or old.read_bytes()!=path.read_bytes():
   name=str(path.relative_to(RUNTIME)).replace('\\','/');changed[name]=sha(path);patch += list(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],path.read_text(encoding='utf8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 assert set(changed)=={'ark_sim/domains/qualified_areas.py'};(OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8')
 check=subprocess.run([sys.executable,'tools/build_chapter03_mortar_primary.py','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert check.returncode==0
 assert implementation_digest()==before
 names=['tools/build_chapter03_mortar_primary.py','packages/campaign/chapter03_models/mortar.primary.reference.json','packages/campaign/chapter03_models/mortar.targeting.reference.json','packages/campaign/chapter03_sources/native.reference.json']+[str(p.relative_to(ROOT)) for p in Path(__file__).parent.glob('*.py')]
 report={'schema':'ark-sim/qualified-primary-candidate/v1','status':'passed_declared_reference_scope','actual_module':sys.modules['ark_sim'].__file__,'core_before':before,'core_after':implementation_digest(),'changed_source_files':changed,'source_locks':{n:sha(ROOT/n) for n in names},'cases':cases,'actual_inputs':inputs,'public_checkpoint_resume_equal':True,'public_command_replay_equal':True,'noopt_all_values_equal_except_exact_identity_paths':True,'noopt_identity_differences':differences,'noopt_events':len(b['snapshot']['events']),'builder_check':check.stdout,'scope':['generic optional include_primary; strict bool/missing primary snapshot failfast','same live/visible/availability and child source eligibility guards, no hardcoded actor/flag/side','outside-grid primary plus grid union once','bound9 and immunity9 half-open; targetfree/motion/category/side/retired/route-hidden deny','expiry/reached/capture ordinary projectile quota preserve','actual Mortarf16/current homing/sourceATKat_hit450; stress expiry outside grid350; dead/free no hit','old no-opt World/random/tasks/events values compared in independent parent/candidate processes'],'remaining_integration':['M59 from M54 has no M55/M57 route_obstacle schema; separate Root merge and actual source crate replay required','native method/callback ordering client feedback; no client-verified or formal stage claim'],'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'candidate_final.json',report);print(json.dumps({'cases':len(cases),'core':before,'report_sha256':sha(OUT/'candidate_final.json'),'changed':changed,'module_sha256':sha(ROOT/names[1])}))
if __name__=='__main__':main()
