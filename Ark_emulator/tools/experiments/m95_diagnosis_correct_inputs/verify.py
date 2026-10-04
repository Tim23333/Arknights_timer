"""Diagnose input selection with the unchanged canonical regression assertion."""
import os,sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m95_diagnosis_correct_inputs'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json');os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
import ark_sim,pytest
from tools import canonical_summon_witness_support as h
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7';assert implementation_digest()==PIN
inputs=[];original=h.make
def make(data,seed=11):inputs.append({'data':data,'seed':seed});return original(data,seed=seed)
h.make=make
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
 paths+=[Path(__file__),ROOT/'tests_v2/test_canonical_kalts.py',ROOT/'tools/witness_canonical_kalts.py',ROOT/'tools/canonical_summon_witness_support.py',ROOT/'tools/witness_canonical_roster_trio.py',Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']),ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json',ROOT/'tools/experiments/m10/build_wrapper.py']
 return {str(p):sha(p) for p in paths}
before=guard();cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main(['tests_v2/test_canonical_kalts.py::test_canonical_mechanism[no_owned_token_must_not_interrupt_ordinary_heal]','-q','--tb=short'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;s=h.LAST_SIM
driver=next(e for e in inputs[0]['data']['entities'] if e['id']=='unit/char_003_kalts')['components']['resources']['sp']['recovery'];assert driver['interrupt_abilities']==['ability/kalts_host_s3']
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'core_start':PIN,'core_end':implementation_digest(),'passed':code==0,'explicit_inputs':{k:os.environ[k] for k in ['CAMPAIGN_SUMMON_PACKAGE','ARKSIM_M10_REVIEW_ROOT']},'start_manifest':before,'end_manifest':after,'guards_equal':True,'cases':cases,'actual_inputs':inputs,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'conclusion':'Correct M12 filtered recovery input passes unchanged canonical assertion; legacy M8 broad interrupt is a known content policy, not M93/M94 regression. No M95 runtime candidate created.'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'report_sha256':sha(target),'cases':len(cases)}));sys.exit(code)
