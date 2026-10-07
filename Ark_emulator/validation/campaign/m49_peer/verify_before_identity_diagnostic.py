import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate';BASE=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m49_peer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(thaw(v),indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();assert before=='e6d05494938ef71a20091b287475fc3e297b9831366a030b349b319a7df515a4';cases=[];inputs=[];original=Compiler.compile
 def captured(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):02d}.json';write(path,p);inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_visibility.py')),str(Path(__file__).with_name('test_sources.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
 from tools.experiments.m49_peer.test_visibility import fixture
 from tools.experiments.m49_peer.test_sources import source_fixture
 public=[]
 for name in ('generic_deadline','source_sensor'):
  if name=='generic_deadline':
   p=fixture();commands=[{'action':'skill','source':'secret','ability':'ability/pulse','at':2},{'action':'skill','source':'secret','ability':'ability/pulse','at':5},{'action':'skill','source':'observer','ability':'ability/hit','at':10},{'action':'skill','source':'observer','ability':'ability/hit','at':11}];middle=7;final=14
  else:
   p,_=source_fixture('enemy_1019_jshoot',True);commands=[{'action':'skill','source':'sensor','ability':'ability/sensor/reveal','at':2},{'action':'skill','source':'observer','ability':'ability/peer/probe','at':601},{'action':'skill','source':'observer','ability':'ability/peer/probe','at':602}];middle=580;final=604
  program=Compiler().compile(p);s=Engine.create(program,seed=4958)
  for cmd in commands:s.submit({k:v for k,v in cmd.items() if k!='at'},at=cmd['at'])
  directory=OUT/name;directory.mkdir(exist_ok=True);s.advance(middle);path=directory/'checkpoint.ordered.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(final-middle);r.advance(final-middle);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
  for fname,v in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:write(directory/fname,v)
  public.append({'case':name,'checkpoint_resume_equal':True,'command_replay_equal':True,'files':{str(path.relative_to(ROOT)):sha(path) for path in directory.iterdir()}})
 p=fixture();p['entities'][0]['rules']={};p['entities'][0]['components']['buffs']['initial']=[];p['buffs']=[];p['rules']=[];p['entities'][1]['components']['abilities']=['ability/hit'];p['selectors']=[p['selectors'][0]];p['abilities']=[a for a in p['abilities'] if a['id']!='ability/reveal'];write(OUT/'noopt_input.json',p)
 for name,runtime in [('parent',BASE),('candidate',RUNTIME)]:
  run=subprocess.run([sys.executable,str(Path(__file__).with_name('capture_noopt.py')),str(runtime),str(OUT/'noopt_input.json'),str(OUT/f'noopt_{name}.json')],capture_output=True,text=True);assert run.returncode==0,run.stderr
 a=json.loads((OUT/'noopt_parent.json').read_bytes());b=json.loads((OUT/'noopt_candidate.json').read_bytes());differences=[]
 def same(x,y,path):
  if path.endswith('/runtime_fingerprint'):
   if x!=y:differences.append(path)
   return
  assert type(x)==type(y),path
  if isinstance(x,dict):
   assert set(x)==set(y),path
   for k in x:same(x[k],y[k],path+'/'+k)
  elif isinstance(x,list):
   assert len(x)==len(y),path
   for i,(xx,yy) in enumerate(zip(x,y)):same(xx,yy,path+'/'+str(i))
  else:assert x==y,(path,x,y)
 same(a['snapshot'],b['snapshot'],'snapshot');same(a['checkpoint'],b['checkpoint'],'checkpoint')
 after=implementation_digest();assert before==after
 names=['packages/campaign/chapter03_visibility/three_hidden_sensor.model.json','packages/campaign/chapter03_visibility/lurker_sensor.model.json','packages/campaign/chapter03_visibility/source.reference.json','packages/campaign/chapter03_sources/native.reference.json']+[str(p.relative_to(ROOT)) for p in Path(__file__).parent.glob('*.py')]
 native=json.loads((ROOT/names[3]).read_bytes());locks={n:sha(ROOT/n) for n in names}
 for path,pin in native['source_locks'].items():assert sha(ROOT.parent/path)==pin
 report={'schema':'ark-sim/visibility-independent-peer/v1','status':'passed_declared_source_and_model_scope','actual_module':sys.modules['ark_sim'].__file__,'core_before':before,'core_after':after,'source_locks':locks,'original_native_source_locks':native['source_locks'],'cases':cases,'actual_inputs':inputs,'public_evidence':public,'noopt_values_equal':True,'noopt_excluded_exact_identity_paths':differences,'noopt_events_count':len(b['snapshot']['events']),'scope':['arbitrary target-role pulse and resource-held condition','pure eligibility no events/RNG/write','six-tick configurable restore and restart','independent owned child parent IDs','live immunity9 preserves underlying9 and17; half-open expiry','real child on_remove RNG plus failed recovery callback full atomic rollback and guards','fresh original Unity raw PPtr three checkers: Lurker attack1 versus ranged attack0','real source f16/f19 physical180/arts210 and post-attack invisible selection rejection','Lurker actual blocked f13 packet220, pulse13, release14 restores104','Sensor15SP20seconds exact ability freeze and601hit/602rejection; physical/arts/true INVINCIBLE5 rejected','old no-opt all snapshot/World/tasks/random/events values identical except two runtime fingerprints'],'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'final_review.json',report);print(json.dumps({'cases':len(cases),'core':before,'report_sha256':sha(OUT/'final_review.json')}))
if __name__=='__main__':main()
