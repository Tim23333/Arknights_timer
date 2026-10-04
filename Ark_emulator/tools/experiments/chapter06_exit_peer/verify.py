import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_exit_accounting_v4_candidate';PARENT=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v15_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_exit_peer import test_peer_correct as peer
OUT=ROOT/'validation/campaign/chapter06_exit_independent_peer';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(peer.__file__),ROOT/'tools/experiments/chapter06_exit_peer/test_boundaries.py'];policy=ROOT/'packages/campaign/chapter06_exit_accounting/reference_policy.json';plan=ROOT/'packages/campaign/chapter06_plans/source.plan.json'
files=tests+[Path(__file__),policy,plan,ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/candidates/chapter06_exit_accounting/rebase_v4.py',ROOT/'validation/campaign/exit_accounting_v4/composition.json']+[p for d in [RUNTIME,PARENT] for p in (d/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='a41a501b58fd242dd67069f9b45ec8948af914026401cae6ce580de220445e81'
changes=[]
for p in (RUNTIME/'ark_sim').rglob('*'):
 if p.is_file() and p.suffix in ['.py','.json']:
  rel=p.relative_to(RUNTIME/'ark_sim');old=PARENT/'ark_sim'/rel
  if not old.exists() or sha(old)!=sha(p):changes.append(rel.as_posix())
assert set(changes)=={'content/capabilities.py','content/compiler.py','content/schemas.py','domains/lifecycle.py','domains/exit_accounting.py','rules/contracts.json'}
old=json.loads((PARENT/'ark_sim/rules/contracts.json').read_bytes());new=json.loads((RUNTIME/'ark_sim/rules/contracts.json').read_bytes());assert new['contracts'][:-1]==old['contracts'] and new['contracts'][-1]['id']=='lifecycle.exit';assert len(new['contracts'])==98
reference=json.loads(policy.read_bytes());assert list(reference['manifest']['metadata']['source_locks'].values())==[sha(plan)];profile=reference['actionLifecycleProfile'];native=json.loads(plan.read_bytes())['stages'][profile['native_id']]['native_document'];assert profile['native_action']==native['waves'][0]['fragments'][0]['actions'][0] and profile['native_action']['isUnharmfulAndAlwaysCountAsKilled'] is True
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
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q'],plugins=[plugin])
modules=[m for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).resolve()==Path(peer.__file__).resolve()];seen=set();inputs=[];captures=[]
for m in modules:
 if id(m) not in seen:seen.add(id(m));inputs.extend(m.INPUTS);captures.extend(m.CAPTURES)
after=guard();report={'core':implementation_digest(),'catalog_sha':sha(RUNTIME/'ark_sim/rules/contracts.json'),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'changes':changes,'unrelated_v15_bytes_preserved':True,'catalog_append_only_lifecycle_exit':True,'source_policy_raw_flag_verified':True,'native_semantics_verified':False,'reference_policy_scope':reference['manifest']['metadata']['reference_policy'],'scope':'Independent configurable actual routeexit/HP95000/noopt/death/duplicates/typedplans/dependency/fullrollback and queuedresource reaction/onremovecapacity callback. ActualorderedCP andpublichead/fullcheckpoint/events equal. NoC6story/actor sourcecombat/whole/clientclaim.','fixture_corrections':'Initialresourcebounds expression unsupported andbuffevent inputnamespace wrong; originalfixture/testfile kept. Correctedprovider/context inputs uses same atomic andcredit expectations, not corefix.'}
for name,value in [('inputs.json',inputs),('captures.json',captures),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after,'source_policy_sha':sha(policy)}))
