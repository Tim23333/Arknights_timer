import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_area_projection_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.area_projection_peer import test_projection_controller as peer
fresh=peer
OUT=ROOT/'validation/campaign/chapter07_area_projection_independent_controller';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[Path(__file__),Path(peer.__file__),Path(fresh.__file__),ROOT/'tools/chapter07_boss/policies_v2.py',ROOT/'tools/chapter07_boss/policies_v1.py',ROOT/'packages/campaign/chapter07_boss/patrt/combined.mechanism.v2.json',ROOT/'packages/campaign/chapter07_boss/patrt/source.closure.json',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/chapter07_foundation_v2/composition.json']+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='788f388ec892abca97c8d0cf6ca2329998768f273e66edef21bb000485492c8e'
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_teardown(self,item,nextitem):
  tmp=item.funcargs.get('tmp_path')
  if tmp:
   folder=OUT/'actual_ordered_cps'/item.name;folder.mkdir(parents=True,exist_ok=True)
   for p in tmp.glob('*.json'):(folder/p.name).write_bytes(p.read_bytes())
 def pytest_runtest_logreport(self,report):
  r=report
  if r.when in ('call','setup') and (r.when=='call' or r.failed):self.rows.append({'nodeid':r.nodeid,'outcome':r.outcome,'duration':r.duration,'failure':str(r.longrepr) if r.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([str(Path(peer.__file__)),'-q','--import-mode=importlib'],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Fresh independent synthetic joint Waiting/Aura self and ally+true current high tile input; foreign UID/foreign cast/remove actual parent/public retirement; ordered CP28/full public head. No full stage or native body/timing claim.'}
for name,value in [('inputs.json',peer.INPUTS),('captures.json',peer.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(r['outcome']=='passed' for r in plugin.rows),'guards_equal':before==after}))
