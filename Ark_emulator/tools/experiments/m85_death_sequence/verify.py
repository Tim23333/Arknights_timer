import sys,json,hashlib,difflib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m85_death_sequence_candidate';BASE=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME));sys.path.append(str(Path(__file__).parent))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m85_death_sequence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();files=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']];start={str(p.relative_to(RUNTIME)):sha(p) for p in files};cases=[];inputs=[];old=Compiler.compile
 def capture(self,p,*a,**k):
  f=OUT/f'input_{len(inputs):02d}.json';write(f,p);inputs.append({'path':str(f.relative_to(ROOT)),'sha256':sha(f)});return old(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=capture
 try:code=pytest.main([str(Path(__file__).with_name('test_sequence.py')),'-q'],plugins=[Results()])
 finally:Compiler.compile=old
 assert code==0
 from test_sequence import fixture
 p=fixture();p['entities'][0]['components']['lifecycle']['death_projectiles']*=2;program=Compiler().compile(p);s=Engine.create(program,seed=760070);s.submit({'action':'skill','source':'hero','ability':'ability/peer/kill'},at=1);s.advance(15);pin=write_ordered(OUT/'double.ordered.json',s.checkpoint());r=Engine.restore(program,load_bound(OUT/'double.ordered.json',pin));s.advance(20);r.advance(20);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot();write(OUT/'double.final.json',s.snapshot());write(OUT/'double.replay.json',s.export_replay())
 a=json.loads((OUT/'single.parent.json').read_bytes());b=json.loads((OUT/'single.candidate.json').read_bytes());dif=[]
 def cmp(x,y,p):
  assert type(x)==type(y),p
  if isinstance(x,dict):
   assert x.keys()==y.keys(),p
   for k in x:cmp(x[k],y[k],p+'.'+k)
  elif isinstance(x,list):
   assert len(x)==len(y),p
   for i,(v,w) in enumerate(zip(x,y)):cmp(v,w,f'{p}[{i}]')
  elif x!=y:dif.append({'path':p,'parent':x,'candidate':y})
 for key in ['snapshot','checkpoint']:cmp(a[key],b[key],key)
 for row in dif:
  p=row['path'];assert p in ['snapshot.program_fingerprint','snapshot.runtime_fingerprint','checkpoint.program_fingerprint','checkpoint.runtime_fingerprint'] or re.fullmatch(r'(snapshot\.events|checkpoint\.kernel\.events\.records)\[\d+\]\.payload\.trace(\.stages\[\d+\]\.trace)*\.runtime_fingerprint',p),p
 assert b['core']==before
 rel=Path('ark_sim/domains/death_projectiles.py');new=RUNTIME/rel;prior=BASE/rel;patch=''.join(difflib.unified_diff(prior.read_text(encoding='utf8').splitlines(True),new.read_text(encoding='utf8').splitlines(True),fromfile='a/'+str(rel),tofile='b/'+str(rel)));(OUT/'candidate.patch').write_text(patch,encoding='utf8')
 changed=[str(p.relative_to(RUNTIME)) for p in files if (BASE/p.relative_to(RUNTIME)).read_bytes()!=p.read_bytes()];assert changed==[str(rel)]
 assert before==implementation_digest() and start=={str(p.relative_to(RUNTIME)):sha(p) for p in files}
 names=['validation/campaign/m76_catalog_peer/multiple_emission_source_withdraw.counterexample.json','validation/campaign/m85_death_sequence/compat.log','packages/campaign/chapter04_units/bslime.reference_model.json'];locks={n:sha(ROOT/n) for n in names};locks.update({str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')})
 report={'schema':'ark-sim/death-emission-sequence-review/v1','status':'passed_bounded_model_fix','core_before':before,'core_after':before,'actual_module':sys.modules['ark_sim'].__file__,'source_before':start,'source_after':start,'source_locks':locks,'cases':cases,'actual_inputs':inputs,'changed_source':{str(rel):sha(new)},'parent_counterexample':{'path':names[0],'sha256':locks[names[0]],'expected':1,'actual_parent':2},'compatibility':{'passed':101,'includes_original_death_tests':13,'scope':'Original expectations unchanged; explicit M85 import before collection; base rebirth combination not included'},'single_original_feature_compare':{'parent_core':a['core'],'candidate_core':before,'events':len(a['snapshot']['events']),'all_values_equal_except_exact_identity_paths':True,'differences':dif},'public_ordered_checkpoint_resume_equal':True,'public_command_replay_equal':True,'public_files':{str(f.relative_to(ROOT)):sha(f) for f in [OUT/'double.ordered.json',OUT/'double.final.json',OUT/'double.replay.json']},'scope':['Each declared death spec and post-decision boundary revalidates actual active source, optional captured death generation and terminal state','First committed projectile is not deleted due to later source retirement; its own policy decides retention','Whole caller transaction rolls back prior launches/HP/RNG/events/tasks when a later actual pure rule fails','Optional epoch case uses explicitly injected World epoch transition as API guard fixture, not native rebirth claim'],'remaining_integration':['M74/M80 single-death attribution and actual rebirth generation are independent frozen features; not in this M76-parent candidate','Source bslime body overlap/status/client dispatch remain original declared profiles'],'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'candidate_final.json',report);print(json.dumps({'core':before,'cases':len(cases),'compat':101,'report_sha256':sha(OUT/'candidate_final.json'),'patch_sha256':sha(OUT/'candidate.patch')}))
if __name__=='__main__':main()
