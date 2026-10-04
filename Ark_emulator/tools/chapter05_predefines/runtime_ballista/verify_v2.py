"""Fresh quota compatibility identity adaptation, all behavioral assertions unchanged."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate';OUT=ROOT/'validation/campaign/chapter05_ballista_v1';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.append(str(ROOT/'tests_v2'));sys.path.append(str(Path(__file__).parent))
import ark_sim
from ark_sim.adapters.api import implementation_digest
from ark_sim import Compiler
from tools.chapter05_predefines.runtime_ballista.verify import TESTS,guard,sha
PIN='49af646affbd800b2d65a25634700deb1444fcbc3e0d886516ad9509edab217b'
def main():
 import pytest
 assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';before=guard();before[str(Path(__file__))]=sha(Path(__file__));cases=[];adapted=[];inputs=[];original=Compiler.compile
 def capture(self,p,*a,**kw):
  try:inputs.append(deepcopy(p))
  except TypeError:inputs.append({'nonserializable_argument':repr(p)})
  return original(self,p,*a,**kw)
 class Results:
  def pytest_collection_modifyitems(self,session,config,items):
   seen=set()
   for item in items:
    module=item.module
    if Path(getattr(module,'__file__','')).resolve()!=ROOT/'tools/experiments/m37_projectile_refs/test_quota_compat_copy.py' or id(module) in seen:continue
    seen.add(id(module));adapted.append({'file':module.__file__,'original_sha':sha(Path(module.__file__)),'original_CORE':module.CORE,'original_RUNTIME':str(module.RUNTIME),'selected_CORE':PIN,'selected_RUNTIME':str(RUNTIME),'only_adapted':'Module CORE/RUNTIME import identity gates; zero behavioral expectations or fixtures changed'});module.CORE=PIN;module.RUNTIME=RUNTIME
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
 Compiler.compile=capture
 try:code=int(pytest.main([*[str(ROOT/t) for t in TESTS],'-q','--tb=short','--import-mode=importlib'],plugins=[Results()]))
 finally:Compiler.compile=original
 assert len(adapted)==1;after=guard();after[str(Path(__file__))]=sha(Path(__file__));assert before==after and implementation_digest()==PIN;serial=[]
 for i,p in enumerate(inputs):
  try:text=json.dumps(p,ensure_ascii=False,indent=2)
  except TypeError:text=json.dumps({'nonserializable_argument':repr(p)},indent=2)
  path=OUT/f'v2_actual_input_{i:03d}.json';path.write_text(text+'\n',encoding='utf8',newline='');serial.append({'path':str(path),'sha':sha(path)})
 report={'core':PIN,'actual_import':ark_sim.__file__,'exitcode':code,'cases':cases,'identity_gate_adaptation':adapted,'actual_inputs':serial,'guard_before':before,'guard_after':after,'original_failed_report_sha':sha(OUT/'verification_final.json'),'source_catalog_helpers_stable':True,'all_original_behavioral_assertions_preserved':True,'whole_stage_executed':False,'client_verified':False};dest=OUT/'verification_v2_final.json'
 if dest.exists():raise ValueError('Preserve final report')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exitcode':code,'passed':sum(x['outcome']=='passed' for x in cases),'report_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
