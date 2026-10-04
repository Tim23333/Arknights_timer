import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_waiting_actions_v2_candidate';PARENT=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.waiting_actions_peer import test_peer_rebind as peer
from tools.experiments.waiting_actions_peer import test_fresh_v2_bound as fresh
from tools.experiments.waiting_actions_peer import test_peer_targeted as shared
OUT=ROOT/'validation/campaign/waiting_actions_v2_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(peer.__file__),Path(fresh.__file__)];files=tests+[Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/waiting_actions_v2/freeze.json',ROOT/'tools/experiments/waiting_actions_peer/test_peer_targeted.py']+[p for r in [RUNTIME,PARENT] for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='c997d5aa71b8607ca1dc2ca8b03701fafce2d9b54a85682a44031ae3bea7da37'
changes=[p.relative_to(RUNTIME/'ark_sim').as_posix() for p in (RUNTIME/'ark_sim').rglob('*.py') if not (PARENT/'ark_sim'/p.relative_to(RUNTIME/'ark_sim')).exists() or sha(p)!=sha(PARENT/'ark_sim'/p.relative_to(RUNTIME/'ark_sim'))]
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
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q','--import-mode=importlib','-k','not refresh_same_definition'],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'changed_files':changes,'scope':'FrozenWaitingc997 original5 forgery assertions unchanged +new ownedcast foreigndispatch/actualBuff.refresh gen/removeforeign rebind/finishcancel/foreign-source rejection/realfinish job/due/faultatomic. HP0inactive waiting true ownedtimer29 CP28/head. One earlier public31 apply attempt rejected before actual mutation, preserved old invalid refresh expectation separately and not counted as kernel failure.'}
for name,value in [('inputs.json',peer.INPUTS+shared.INPUTS),('captures.json',peer.CAPTURES+shared.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
primitive=[r for r in plugin.rows if '/test_self_remove.py' in r['nodeid']];assert len(plugin.rows)==13
with (OUT/'primitive_verification.json').open('x',encoding='utf8') as f:json.dump({'core':report['core'],'cases':primitive,'guards_equal':before==after,'report_sha':sha(OUT/'verification.json'),'changed_files':changes,'no_other_primitive_exemption':True},f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'primitive_sha':sha(OUT/'primitive_verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
