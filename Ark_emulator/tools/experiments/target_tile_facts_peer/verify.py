import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_target_tile_facts_v1_candidate';PARENT=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.target_tile_facts_peer import test_peer_pure as peer
OUT=ROOT/'validation/campaign/target_tile_facts_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(peer.__file__)];files=tests+[Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/target_tile_facts_v1/freeze.json']+[p for r in [RUNTIME,PARENT] for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='af16e21678f04bcf6ab2ca64b8829da8511bb82cffea6f5c9906fba9b1bdc0da'
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
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'changed_files':changes,'scope':'CandidateTile af16 explicitoptin pure per-candidate eligibility reads realtile mask2 not ranged/ground labels; five nonBoolflags reject, false has no projectedfield. Public actualterrain overlay changes current tile then selector/orderedpreoverlay CP/head exactly equal. select has legacy ordering traces; pure qualifies has no events/RNG/Worldwrites. No nativewhole claim.'}
for name,value in [('inputs.json',peer.INPUTS),('captures.json',peer.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
primitive=[r for r in plugin.rows if '/test_self_remove.py' in r['nodeid']];assert len(plugin.rows)==8
with (OUT/'primitive_verification.json').open('x',encoding='utf8') as f:json.dump({'core':report['core'],'cases':primitive,'guards_equal':before==after,'report_sha':sha(OUT/'verification.json'),'changed_files':changes,'no_other_primitive_exemption':True},f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'primitive_sha':sha(OUT/'primitive_verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
