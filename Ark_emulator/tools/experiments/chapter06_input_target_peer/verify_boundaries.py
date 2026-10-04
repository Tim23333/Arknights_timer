import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_input_target_peer import test_source_correct as peer
OUT=ROOT/'validation/campaign/chapter06_input_target_boundaries';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
test=ROOT/'tools/experiments/chapter06_input_target_peer/test_boundaries_fixed.py';files=[test,Path(peer.__file__),Path(__file__),ROOT/'tools/campaign_content_composition.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/chapter06/cold/policies.py',ROOT/'packages/campaign/chapter06_units/snmage_v3/model.json',ROOT/'packages/campaign/chapter06_units/snbow_v2/model.json',ROOT/'packages/campaign/chapter06_units/input_target_evidence/delivery.pins.json',ROOT/'packages/campaign/chapter06_cold/model.json']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_teardown(self,item,nextitem):
  tmp=item.funcargs.get('tmp_path')
  if tmp:
   folder=OUT/'actual_ordered_cps'/item.name;folder.mkdir(parents=True,exist_ok=True)
   for p in tmp.glob('*.json'):(folder/p.name).write_bytes(p.read_bytes())
 def pytest_runtest_logreport(self,report):
  if report.when=='call':self.rows.append({'nodeid':report.nodeid,'outcome':report.outcome,'duration':report.duration,'failure':str(report.longrepr) if report.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([str(test),'-q','--import-mode=importlib'],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Sixfresh public normal+Cold hardblocker, camouflage nofallback/release, nativeground1 preserved free-mode qualification. PublicorderedCP/head allcheckpoint/events equality on charged andrelease scenarios;sourcewrapperonly,notwhole/client proof.'}
for name,v in [('inputs.json',peer.INPUTS),('captures.json',peer.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'exit':int(code),'guards_equal':before==after}))
