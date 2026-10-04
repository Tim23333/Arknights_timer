from pathlib import Path
import sys,json,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m78_owned_attachment_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest,ark_sim
spec=importlib.util.spec_from_file_location('author_guard',ROOT/'tools/experiments/m78_attachments/verify.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
OUT=ROOT/'validation/campaign/m78_independent_peer';OUT.mkdir(parents=True,exist_ok=True)
before=a.guard();before['peer']={str(p):a.sha(p) for p in Path(__file__).parent.glob('*.py')};pin=implementation_digest();assert pin=='27d8ba218d90e6880a4f8704418871a517e5a6f30f034a79db8b04ca46a0cf74'
cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'longrepr':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short'],plugins=[Capture()]))
m=next(m for n,m in sys.modules.items() if n.endswith('test_peer'));after=a.guard();after['peer']={str(p):a.sha(p) for p in Path(__file__).parent.glob('*.py')};assert before==after and implementation_digest()==pin
report={'core_start':pin,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'module_sha256':a.sha(ROOT/'packages/campaign/chapter04_dmage/module.reference.json'),'source_sha256':a.sha(ROOT/'packages/campaign/chapter04_dmage/source.reference.json'),'scope':'Independent small actual-source DMAGE and owned attachment cases only; no whole stage, 36-stage or client acceptance','actual_modules':{n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)}}
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed']}));sys.exit(code)
