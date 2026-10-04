import sys,json,hashlib,io,contextlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/chapter06_base_joint_independent_peer';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
names=['retained_buff_payload_peer/test_peer.py','retained_buff_payload_peer/test_callback_lineage.py','retained_buff_payload_peer/test_scope_boundaries_fixed2.py','retained_buff_payload_peer/test_source_change.py','retained_buff_payload_peer/test_v13_entry.py','retained_buff_payload_peer/test_sibling_after_source_change.py','retained_buff_payload_peer/test_revive_incarnation_fixed.py','retained_buff_payload_peer/test_same_state_revive_final.py','chapter06_exit_peer/test_peer_correct.py','chapter06_exit_peer/test_boundaries.py','retained_area_peer/test_peer_fixed.py','retained_area_peer/test_failure_edges_fixed.py']
tests=[ROOT/'tools/experiments'/name for name in names];files=tests+[Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter06_exit_accounting/reference_policy.json',ROOT/'packages/campaign/chapter06_plans/source.plan.json']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_teardown(self,item,nextitem):
  tmp=item.funcargs.get('tmp_path')
  if tmp:
   name=item.nodeid.replace('\\','_').replace('/','_').replace(':','_').replace('[','_').replace(']','_');folder=OUT/'actual_ordered_cps'/name;folder.mkdir(parents=True,exist_ok=True)
   for p in tmp.glob('*.json'):(folder/p.name).write_bytes(p.read_bytes())
 def pytest_runtest_logreport(self,report):
  if report.when=='call':self.rows.append({'nodeid':report.nodeid,'outcome':report.outcome,'duration':report.duration,'failure':str(report.longrepr) if report.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q','--import-mode=importlib'],plugins=[plugin])
paths={str(p.resolve()) for p in tests};modules=[m for m in list(sys.modules.values()) if getattr(m,'__file__',None) and str(Path(m.__file__).resolve()) in paths];inputs=[];captures=[];seen_lists=set()
for m in modules:
 for attr,dest in [('INPUTS',inputs),('CAPTURES',captures)]:
  value=getattr(m,attr,None)
  if value is not None and id(value) not in seen_lists:seen_lists.add(id(value));dest.extend(value)
after=guard();report={'core':implementation_digest(),'catalog_sha':sha(RUNTIME/'ark_sim/rules/contracts.json'),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Fresh actual joint14single-retained/20exit/10area assertions unchanged, actualorderedCP rawbytes/head exactcheckpoint/events checks retained. 44generic independent checks, notsourceenemymechanism/fullstage/fullsuite/client claim. --import-mode=importlib avoids duplicate test_peer basename collection; actualmodule input/capture lists collected.'}
for name,value in [('inputs.json',inputs),('captures.json',captures),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'exit':int(code),'guards_equal':before==after}))
