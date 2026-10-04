import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v10_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.retained_buff_payload_peer import test_peer
OUT=ROOT/'validation/campaign/retained_buff_payload_peer_v10';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(test_peer.__file__),ROOT/'tools/experiments/retained_buff_payload_peer/test_callback_lineage.py']
files=tests+[Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='38de0b0570ed01c73abff5187b6ac1a99dcb31bd8aadd1ee43de10297c4f60f4'
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call':self.rows.append({'nodeid':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q'],plugins=[plugin])
after=guard();r={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Independent generic trueprojectile/public retire/targetdead/forgedcast and onapply/onremove callbacklineage tests. NoCold authorunit or authorfixture dependency. Successful path assertsorderedCPprehit and publichead equivalence; failures kept actual source.'}
for name,v in [('inputs.json',test_peer.INPUTS),('captures.json',test_peer.CAPTURES),('verification.json',r)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
