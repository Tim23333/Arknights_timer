import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_scenario_cards_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter07_consumers_peer import test_capacity as peer,common
OUT=ROOT/'validation/campaign/chapter07_scenario_cards_actual_capacity';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[Path(__file__),Path(peer.__file__),Path(common.__file__),common.MINE,peer.NATIVE,ROOT/'tools/chapter07_predefines/policies_v1.py',ROOT/'tools/chapter07_strength_melee/policies_v1.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter07_predefines/source.v4.reference.json']+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='478db2509508490f920fb08d24b3656cc995230d87eec31ab35a5ef19cd6d5c9'
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
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([str(Path(peer.__file__)),'-q','--import-mode=importlib'],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Fresh actualOre3 on4f16. 14 recipient states; diamond/current half-cell geometry; mode/listener and finite external immune at hit; source retirement cancellation; publicCP18/head. Controlled source initialSP7 and recipient eventSPbinding declared. Native finishedBuff timing remains explicit19frame reference, not recovered body.'}
for name,value in [('inputs.json',common.INPUTS),('captures.json',common.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
