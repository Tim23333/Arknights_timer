import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate';PARENT=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_npc_peer import test_huang_v7 as peer
OUT=ROOT/'validation/campaign/chapter06_huang_v7_independent_bound';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[ROOT/'tools/experiments/chapter06_npc_peer/test_self_remove.py',Path(peer.__file__),ROOT/'tools/experiments/chapter06_npc_peer/test_huang_edges_final.py'];files=tests+[Path(__file__),ROOT/'packages/campaign/chapter06_npcs/huang.v7.model.json',ROOT/'packages/campaign/chapter06_npcs/huang_talents.v7.model.json',ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json',ROOT/'packages/campaign/chapter06_predefines/source.reference.json',ROOT/'tools/chapter06_npcs/policies.py',ROOT/'tools/chapter06_npcs/huang_v6_policy.py',ROOT/'validation/campaign/chapter06_npcs_author_v2/freeze.json',ROOT/'tools/campaign_ordered_checkpoint.py']+[p for r in [RUNTIME,PARENT] for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='1cb64a004d15f0b365c0affc02ad900444cd9e5ca263707f7c176c3f3bd1c4fd'
changes=[p.relative_to(RUNTIME/'ark_sim').as_posix() for p in (RUNTIME/'ark_sim').rglob('*.py') if sha(p)!=sha(PARENT/'ark_sim'/p.relative_to(RUNTIME/'ark_sim'))];assert changes==['content/dependencies.py']
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
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'only_current_buff_remove_dependency_primitive_changed':True,'scope':'Independent6 compiler primitives + original3 Huang expectations +5 fresh dynamic effective-maxHP/derived HEALFREE/expiry/multiple-packet/floor/resistance cases. Ordered diskCP and public replay checked. Timing remains explicit deferred reference policy; no native coroutine/client/fullstage claim. Old v5 source failures preserved.'}
for name,value in [('inputs.json',peer.INPUTS),('captures.json',peer.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
primitive=[r for r in plugin.rows if '/test_self_remove.py' in r['nodeid']];assert len(primitive)==6 and all(x['outcome']=='passed' for x in primitive)
with (OUT/'primitive_verification.json').open('x',encoding='utf8') as f:json.dump({'core':report['core'],'cases':primitive,'guards_equal':before==after,'report_sha':sha(OUT/'verification.json'),'changed_files':changes,'no_other_primitive_exemption':True},f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'primitive_sha':sha(OUT/'primitive_verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
