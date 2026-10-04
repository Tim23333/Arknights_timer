import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_waiting_actions_v1_candidate';PARENT=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.waiting_actions_peer import test_peer_forgery as peer
OUT=ROOT/'validation/campaign/waiting_actions_independent_forgery';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(peer.__file__)];files=tests+[Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/waiting_actions_v1/freeze.json']+[p for r in [RUNTIME,PARENT] for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='4dc5c3c7a4c2a2fccc1d6bb8cee63a0a5e86df16fa644e17fc2a91cbdc6c67fa'
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
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q','--import-mode=importlib'],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'changed_files':changes,'scope':'Independent real owned29tick timer HP0inactive waiting CP/head/manual rejection; copiedbuff directtrigger and foreign scheduled ownedpayload may acquire lease before real timer, bool generation equality permits mismatchedtype. Kernel trusted API misuse counter deliberately exercised because task requests forged lease/timer defense; no sourceconsumer/whole claim. Missingretained-removal/targetsource initialfixtures kept.'}
for name,value in [('inputs.json',peer.INPUTS),('captures.json',peer.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
primitive=[r for r in plugin.rows if '/test_self_remove.py' in r['nodeid']];assert len(plugin.rows)==5
with (OUT/'primitive_verification.json').open('x',encoding='utf8') as f:json.dump({'core':report['core'],'cases':primitive,'guards_equal':before==after,'report_sha':sha(OUT/'verification.json'),'changed_files':changes,'no_other_primitive_exemption':True},f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'primitive_sha':sha(OUT/'primitive_verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
