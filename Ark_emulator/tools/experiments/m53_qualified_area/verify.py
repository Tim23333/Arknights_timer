import sys,json,hashlib,subprocess,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m53_qualified_area_candidate';BASE=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m53_qualified_area';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();cases=[];inputs=[];original=Compiler.compile
 def capture(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):02d}.json';write(path,thaw(p));inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=capture;code=pytest.main([str(Path(__file__).with_name('test_area.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
 from tools.experiments.m53_qualified_area.test_area import fixture,fire
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=5310);fire(s,3);s.advance(2);cp=OUT/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(5);r.advance(5);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
 write(OUT/'public_input.json',p);write(OUT/'public_replay.json',s.export_replay());write(OUT/'public_final.json',s.snapshot())
 for name,runtime in [('parent',BASE),('candidate',RUNTIME)]:
  run=subprocess.run([sys.executable,str(Path(__file__).with_name('capture_noopt.py')),str(runtime),str(OUT/f'noopt_{name}.json')],capture_output=True,text=True);assert run.returncode==0,run.stderr
 a=json.loads((OUT/'noopt_parent.json').read_bytes());b=json.loads((OUT/'noopt_candidate.json').read_bytes());differences=[]
 def compare(x,y,path=''):
  if path.endswith('runtime_fingerprint'):
   if x!=y:differences.append(path)
   return
  if isinstance(x,dict):
   assert set(x)==set(y),(path,set(x)^set(y))
   for k in x:compare(x[k],y[k],path+'/'+k)
  elif isinstance(x,list):
   assert len(x)==len(y),path
   for i,(xx,yy) in enumerate(zip(x,y)):compare(xx,yy,path+'/'+str(i))
  else:assert type(x)==type(y) and x==y,(path,x,y)
 compare(a['snapshot'],b['snapshot']);compare(a['checkpoint'],b['checkpoint'])
 changed={};patch=[]
 for path in sorted((RUNTIME/'ark_sim').rglob('*.py')):
  old=BASE/'ark_sim'/path.relative_to(RUNTIME/'ark_sim')
  if not old.exists() or old.read_bytes()!=path.read_bytes():
   name=str(path.relative_to(RUNTIME)).replace('\\','/');changed[name]=sha(path);patch += list(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],path.read_text(encoding='utf8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8');after=implementation_digest();assert before==after
 locks={str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')}
 report={'schema':'ark-sim/qualified-area-review/v1','status':'passed_declared_model','actual_module':sys.modules['ark_sim'].__file__,'core_before':before,'core_after':after,'changed_source_files':changed,'source_locks':locks,'cases':cases,'actual_inputs':inputs,'public_checkpoint_equal':True,'public_command_replay_equal':True,'noopt_all_values_equal_except_runtime_fingerprint':True,'excluded_exact_paths':differences,'noopt_events':len(b['snapshot']['kernel']['events']) if 'kernel' in b['snapshot'] else None,'client_verified':False,'formal_approved':False}
 write(OUT/'candidate_final.json',report);print(json.dumps({'core':before,'cases':len(cases),'report_sha256':sha(OUT/'candidate_final.json'),'changed':changed}))
if __name__=='__main__':main()
