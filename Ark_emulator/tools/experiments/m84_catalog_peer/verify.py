import sys,json,hashlib,re,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m84_boundary_settle_v2_candidate';CORE='e8fe0c931358f6f09e6e209ff70948dd1d17fb80aeae969afd71d2c8ab1bef3e';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME));sys.path.append(str(Path(__file__).parent))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m84_catalog_peer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 assert implementation_digest()==CORE and Path(sys.modules['ark_sim'].__file__).resolve().parent==RUNTIME/'ark_sim'
 files=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']];start={str(p.relative_to(RUNTIME)):sha(p) for p in files};cases=[];inputs=[];original=Compiler.compile
 def capture(self,p,*a,**k):
  f=OUT/f'input_{len(inputs):02d}.json';write(f,p);inputs.append({'path':str(f.relative_to(ROOT)),'sha256':sha(f)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=capture
 try:code=pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q'],plugins=[Results()])
 finally:Compiler.compile=original
 assert code==0
 from test_peer import fixture
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=840070)
 for time,ability in [(0,'apply'),(3,'damage')]:s.submit({'action':'skill','source':'director','ability':'ability/boundary/'+ability},at=time)
 s.advance(2);h=write_ordered(OUT/'public.ordered.json',s.checkpoint());r=Engine.restore(program,load_bound(OUT/'public.ordered.json',h));s.advance(2);r.advance(1);assert not r.ctx.buffs.controls('subject')['attack'];r.advance(1);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot();write(OUT/'public.final.json',s.snapshot());write(OUT/'public.replay.json',s.export_replay())
 a=json.loads((OUT/'noopt.parent.json').read_bytes());b=json.loads((OUT/'noopt.candidate.json').read_bytes());diff=[]
 def cmp(x,y,p):
  assert type(x)==type(y),p
  if isinstance(x,dict):
   assert x.keys()==y.keys(),p
   for k in x:cmp(x[k],y[k],p+'.'+k)
  elif isinstance(x,list):
   assert len(x)==len(y),p
   for i,(v,w) in enumerate(zip(x,y)):cmp(v,w,f'{p}[{i}]')
  elif (struct.pack('>d',x)!=struct.pack('>d',y)) if isinstance(x,float) else (x!=y):diff.append({'path':p,'parent':x,'candidate':y})
 for key in ['snapshot','checkpoint']:cmp(a[key],b[key],key)
 for row in diff:
  path=row['path'];assert path in ['snapshot.runtime_fingerprint','checkpoint.runtime_fingerprint'] or re.fullmatch(r'(snapshot\.events|checkpoint\.kernel\.events\.records)\[\d+\]\.payload\.trace(\.stages\[\d+\]\.trace)*\.runtime_fingerprint',path),path
 assert a['input_sha256']==b['input_sha256'] and b['core']==CORE and all('boundary' not in row for row in b['checkpoint']['kernel']['systems'])
 assert implementation_digest()==CORE and start=={str(p.relative_to(RUNTIME)):sha(p) for p in files}
 names=['validation/campaign/m70_root_peer/initial_review.json','validation/campaign/m70_applicability_v2/noopt.input.json','validation/campaign/m84_catalog_peer/noopt.parent.json','validation/campaign/m84_catalog_peer/noopt.candidate.json'];locks={n:sha(ROOT/n) for n in names};locks.update({str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')})
 report={'schema':'ark-sim/independent-clock-boundary-review/v1','status':'passed_bounded_model_review','core_start':CORE,'core_end':CORE,'actual_module':sys.modules['ark_sim'].__file__,'source_start':start,'source_end':start,'source_locks':locks,'cases':cases,'actual_inputs':inputs,'public_ordered_checkpoint_resume_equal':True,'public_command_replay_equal':True,'public_files':{str(f.relative_to(ROOT)):sha(f) for f in [OUT/'public.ordered.json',OUT/'public.final.json',OUT/'public.replay.json']},'noopt':{'parent_core':a['core'],'current_core':CORE,'event_count':len(a['snapshot']['events']),'all_values_and_float_bits_equal_except_exact_identity_paths':True,'no_boundary_registration_field':True,'differences':diff},'observed':{'exact_expiry_tick':3,'effective_abnormal_flags':[9],'effective_abnormal_immunes':[16],'effective_sleep_combo':[0],'mixed_atk':33,'attack_permitted':False,'hp_before_command_at3':10000,'hp_after_executing3':9990},'failure_semantics':'Observer transaction writes rollback, private guards clear; advanced clock and failure diagnostic remain, further advance rejected. Budget exhaustion before second observer retains first successfully committed observer; not falsely claimed whole-step rollback.','scope':'Independent synthetic public content with exact rule/window math; API observer registration and callbacks; raw Frost operands validated separately, not whole Boss/native client accuracy.','client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'final_review.json',report);print(json.dumps({'core':CORE,'cases':len(cases),'report_sha256':sha(OUT/'final_review.json'),'noopt_events':len(a['snapshot']['events']),'identity_paths':len(diff)}))
if __name__=='__main__':main()
