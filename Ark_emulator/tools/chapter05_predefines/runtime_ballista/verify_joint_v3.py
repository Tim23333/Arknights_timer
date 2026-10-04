"""Actual newest combined8fa joint ray/settle/branch source boundaries."""
import hashlib,json,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/campaign/chapter05_ballista_joint_v3';PIN='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.append(str(Path(__file__).parent));sys.path.append(str(ROOT/'tests_v2'))
import ark_sim
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
TESTS=['tools/chapter05_predefines/runtime_ballista/test_consumer_v2.py','tools/chapter05_predefines/runtime_ballista/test_advanced.py','tools/chapter05_predefines/runtime_ballista/test_source_chain_v3.py','tools/experiments/selection_settle_independent_peer_v2/test_peer.py','tools/experiments/selection_settle_independent_peer_v2/test_boundary.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]+[ROOT/t for t in TESTS]+[Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-10.life99999.json',ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/module.v2.reference.json',ROOT/'packages/campaign/chapter05_predefines/source.reference.json',ROOT/'packages/campaign/chapter05_units/special/model.selection_settle.reference.json',ROOT/'packages/campaign/chapter05_sources/native.reference.json'];return {str(p):sha(p) for p in paths}
def main():
 import pytest
 assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';OUT.mkdir(parents=True,exist_ok=True);before=guard();cases=[];inputs=[];original=Compiler.compile
 def capture(self,p,*a,**kw):inputs.append(deepcopy(p));return original(self,p,*a,**kw)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
 Compiler.compile=capture
 try:code=int(pytest.main([*[str(ROOT/t) for t in TESTS],'-q','--tb=short','--import-mode=importlib'],plugins=[Results()]))
 finally:Compiler.compile=original
 after=guard();assert before==after and implementation_digest()==PIN;paths=[]
 for i,p in enumerate(inputs):
  file=OUT/f'actual_input_{i:03d}.json'
  try:text=json.dumps(p,ensure_ascii=False,indent=2)
  except TypeError:text=json.dumps({'repr':repr(p)},indent=2)
  file.write_text(text+'\n',encoding='utf8',newline='');paths.append({'file':str(file),'sha':sha(file)})
 captures=[]
 for name,module in list(sys.modules.items()):
  if name.endswith('test_source_chain_v3'):captures.extend(module.CAPTURES)
 report={'role':'Author joint newest combined8fa boundaries; source-specific independent acceptance still separate','core':PIN,'actual_import':ark_sim.__file__,'exitcode':code,'cases':cases,'actual_inputs':paths,'actual_source_chain_captures':captures,'guard_before':before,'guard_after':after,'all_original_behavioral_assertions_unchanged':True,'old146_source_chain_not_relabelled':True,'whole_stage_executed':False,'client_verified':False};dest=OUT/'verification.json'
 if dest.exists():raise ValueError('Preserve joint report')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exitcode':code,'passed':sum(c['outcome']=='passed' for c in cases),'report_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
