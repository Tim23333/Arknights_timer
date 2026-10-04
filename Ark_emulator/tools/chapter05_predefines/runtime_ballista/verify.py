"""Actual consumer/source/catalog/helper guards and scoped V2 compatibility evidence."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate';OUT=ROOT/'validation/campaign/chapter05_ballista_v1';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.append(str(ROOT/'tests_v2'));sys.path.append(str(Path(__file__).parent))
import ark_sim
from ark_sim.adapters.api import implementation_digest
from ark_sim import Compiler
PIN='49af646affbd800b2d65a25634700deb1444fcbc3e0d886516ad9509edab217b'
TESTS=['tools/chapter05_predefines/runtime_ballista/test_consumer_v2.py','tools/chapter05_predefines/runtime_ballista/test_advanced.py','tools/experiments/m37_projectile_refs/test_refs.py','tools/experiments/m37_projectile_refs/test_quota_compat_copy.py','tests_v2/test_kernel.py','tests_v2/test_abilities.py','tests_v2/test_replay.py','tests_v2/test_buff_mode_lifecycle.py','tests_v2/test_chapter03_sensor_terrain.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]+list(Path(__file__).parent.glob('*.py'))+[ROOT/t for t in TESTS]+[ROOT/'packages/campaign/chapter05_predefines/source.reference.json',ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/source.policy.json',ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/module.v2.reference.json',ROOT/'packages/campaign/chapter05_plans/source.plan.json',ROOT/'tools/campaign_ordered_checkpoint.py']
 return {str(p):sha(p) for p in paths}
def main():
 import pytest
 assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';before=guard();cases=[];inputs=[];original=Compiler.compile
 def capture(self,p,*a,**kw):
  try:inputs.append({'source_input':p,'description':'Actual supplied Compiler input'})
  except TypeError:inputs.append({'description':'Nonserializable compiler argument', 'repr':repr(p)})
  return original(self,p,*a,**kw)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
 Compiler.compile=capture
 try:code=int(pytest.main([*[str(ROOT/t) for t in TESTS],'-q','--tb=short','--import-mode=importlib'],plugins=[Results()]))
 finally:Compiler.compile=original
 after=guard();assert before==after and implementation_digest()==PIN
 serial=[]
 for i,p in enumerate(inputs):
  try:text=json.dumps(p,ensure_ascii=False,indent=2)
  except TypeError:text=json.dumps({'repr':repr(p)},indent=2)
  path=OUT/f'actual_input_{i:03d}.json';path.write_text(text+'\n',encoding='utf8',newline='');serial.append({'path':str(path),'sha':sha(path)})
 report={'core':PIN,'actual_import':ark_sim.__file__,'exitcode':code,'cases':cases,'actual_inputs':serial,'guard_before':before,'guard_after':after,'source_catalog_helpers_stable':True,'scope':'16 actual ballista checks plus V2 projectile quota/refs, kernel/ability/Buff/terrain/replay compatibility; no wholeC5 stage acceptance or client claim','remaining_source_policies':['Replaceable mapbound reference extent for native FarthestPointMovement _withinAbilityRange; source fields retained, client comparison pending','C5stage_branch converter integration / Root latest settle parent exact threeway merge / independent review separate'],'formal_independent_acceptance':False,'whole_stage_executed':False,'client_verified':False};dest=OUT/'verification_final.json'
 if dest.exists():raise ValueError('Preserve earlier evidence')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exitcode':code,'passed':sum(x['outcome']=='passed' for x in cases),'report_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
