import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_input_target_peer import test_source_correct as peer
from tools.experiments.chapter06_source_peer.audit_sources import audit
OUT=ROOT/'validation/campaign/chapter06_input_target_independent_peer';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(peer.__file__),ROOT/'tools/experiments/chapter06_input_target_peer/test_hostile.py',ROOT/'tools/experiments/chapter06_input_target_peer/test_bow_counter.py',ROOT/'tools/experiments/chapter06_input_target_peer/test_sp_flags.py']
source_paths=[ROOT/'packages/campaign/chapter06_sources/native.reference.json',ROOT/'packages/campaign/chapter06_cold/model.json',ROOT/'packages/campaign/chapter06_cold/source.decoded.json',ROOT/'packages/campaign/chapter06_plans/source.plan.json']+[ROOT/'packages/campaign/chapter06_units'/n/'model.json' for n in ['melee_v2','snmage_v3','snslime','frozen_melee','snbow_v2']]
files=tests+source_paths+[Path(__file__),ROOT/'tools/experiments/chapter06_source_peer/audit_sources.py',ROOT/'tools/chapter06/cold/policies.py',ROOT/'tools/campaign_content_composition.py',ROOT/'tools/campaign_ordered_checkpoint.py']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a';sourceaudit=audit()
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
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q','--import-mode=importlib'],plugins=[plugin])
modules=[m for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).resolve()==Path(peer.__file__).resolve()];inputs=[];captures=[];seen=set()
for m in modules:
 if id(m) not in seen:seen.add(id(m));inputs.extend(m.INPUTS);captures.extend(m.CAPTURES)
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'source_audit':sourceaudit,'scope':'Independent publicdeploy source consumers with freshDEF31/MRES17, actualauthoredframes/stat/BSON/raw source comparisons. CPbeforehit/sourceDeath/ordered savedbytes andpublichead fullcheckpoint/events verified. RealSource2 blocker counter fororiginalsnmage andsnbow preserved; noactorname mechanic. Partial module gates, noC6whole/client claim.','SP_source_boundary':'Attack-typeSP source has no attacks whenFrozen andtherefore noattack.accepted/charge. This does notprove universal Frozen timeSP stop; optional frozen_recovery timeSPbinding remainsreferencepolicy pendingnative source timing proof.'}
for name,value in [('inputs.json',inputs),('captures.json',captures),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'exit':int(code),'guards_equal':before==after}))
