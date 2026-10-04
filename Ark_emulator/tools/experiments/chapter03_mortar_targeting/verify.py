import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m56_chapter03_integrated_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter03_mortar_targeting'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(thaw(v),indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 before=implementation_digest();assert before=='9fd0e2e11e19ad3573b9f85b49cff52ae6503cc031e44124d452c5972294f011';cases=[];inputs=[];original=Compiler.compile
 def captured(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):02d}.json';write(path,p);inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_targeting.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
 from tools.experiments.chapter03_mortar_targeting.test_targeting import fixture_obstacle,submit_obstacle
 p=fixture_obstacle();program=Compiler().compile(p);s=Engine.create(program,seed=5360);submit_obstacle(s);s.advance(35);cp=OUT/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(170);r.advance(170);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
 for name,v in [('public_input.json',p),('public_replay.json',s.export_replay()),('public_final.json',s.snapshot())]:write(OUT/name,v)
 check=subprocess.run([sys.executable,'tools/build_chapter03_mortar_targeting.py','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert check.returncode==0,check.stderr
 package=ROOT/'packages/campaign/chapter03_models/mortar.targeting.reference.json';native=json.loads(package.read_bytes())['manifest']['metadata'];assert native['native_variant']=='enemy_1024_mortar@0/6408b1bf3f6a0758' and native['raw_source']['mode']['_attack']==native['raw_source']['mode']['_combat'] and native['raw_source']['attack']['_selectTargetSource']==1 and native['raw_source']['hit']['_targetOptions']['targetCategory']==1
 assert implementation_digest()==before
 paths=[package,ROOT/'tools/build_chapter03_mortar_targeting.py',ROOT/'packages/campaign/chapter03_models/mortar.reference.json',ROOT/'packages/campaign/chapter03_sources/native.reference.json',ROOT/'packages/campaign/chapter03_traps/crate.partial.reference_model.json',Path(__file__),Path(__file__).with_name('test_targeting.py')]
 report={'schema':'ark-sim/mortar-reference-targeting-review/v1','status':'passed_bounded_declared_profile','core_before':before,'core_after':implementation_digest(),'actual_module':sys.modules['ark_sim'].__file__,'source_locks':{str(p.relative_to(ROOT)):sha(p) for p in paths},'cases':cases,'actual_inputs':inputs,'constructor_check':check.stdout,'source_bindings':{'native_variant':native['native_variant'],'mode_pointer':3737424909807747982,'attack_and_combat_pointer':2458650350520140686,'selectTargetSource':1,'raw_primary_category':1,'raw_hit_category':1,'source_frame':16,'special_obstacle':'only captured primary category4; default-category1 splash unchanged'},'public_checkpoint_resume_equal':True,'public_command_replay_equal':True,'actual_damage_packets':[e['payload'] for e in s.session.events if e['type']=='damage.accepted'],'actual_damage_pipeline_values':[e['payload']['value'] for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='damage.pipeline'],'final_counts':{'kills':s.ctx.state()['kills'],'leaks':s.ctx.state()['leaks'],'life':s.ctx.resources.current('system/battle','life')},'public_files':{str(p.relative_to(ROOT)):sha(p) for p in [cp,OUT/'public_input.json',OUT/'public_replay.json',OUT/'public_final.json']},'reference':native['reference_targeting'],'required_gaps':['alwaysHitTraceTargetInEnd1 outside current impact grid is not yet guaranteed: separate M59 generic include_primary revision required','known M56 stale route-obstacle callback defect exists; no callbacks in this source crate scenario; no formal core obstacle approval'],'feedback_pending':['PRTS obstacle exception versus raw category1/native IBuil­dable handler body','planar homing/current-point and callback ordering replaceable','integer-base-taunt score profile versus fractional/live-modified taunt requires replacement'],'client_verified':False,'whole_stage_executed':False,'formal_approved':False}
 write(OUT/'final_review.json',report);print(json.dumps({'cases':len(cases),'core':before,'report_sha256':sha(OUT/'final_review.json'),'package_sha256':sha(package)}))
if __name__=='__main__':main()
