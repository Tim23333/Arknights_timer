import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';PARENT=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_boss_peer import test_npc_tile as peer
from tools.experiments.chapter06_boss_peer import test_peer_fullbusy as records
OUT=ROOT/'validation/campaign/chapter06_boss_npc_tile_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(peer.__file__)];pins=json.loads((ROOT/'packages/campaign/chapter06_boss/frstar2/delivery.pins.json').read_bytes())['pins'];files=tests+[Path(__file__),ROOT/'packages/campaign/chapter06_npcs/huang.v7.model.json',ROOT/'tools/experiments/chapter06_boss_peer/test_peer_fullbusy.py',ROOT/'packages/campaign/chapter06_boss/frstar2/delivery.pins.json',ROOT/'packages/campaign/chapter06_boss/frstar2/model.json',ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json',ROOT/'tools/campaign_content_composition_v2.py',ROOT/'tools/chapter06_review/runner_providers_v1.py',ROOT/'tools/chapter06_npcs/providers_v2.py',ROOT/'tools/chapter06_npcs/huang_v6_policy.py',ROOT/'tools/chapter06_npcs/amiya_policy.py',ROOT/'tools/chapter06_npcs/policies.py',ROOT/'tools/chapter06/cold/policies.py',ROOT/'tools/campaign_ordered_checkpoint.py']+[ROOT/p for p in pins]+[p for r in [RUNTIME,PARENT] for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b'
for p,pin in pins.items():assert sha(ROOT/p)==pin
changes=[]
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
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'only_current_buff_remove_dependency_primitive_changed':True,'scope':'Fresh actual nativeNPC Character/category1/unit_type1 without deployable via publicactivation. SourceEXCEPT_CHARACTER filter2 reference currently excludes deploymentcapability only, wrongly admits existing nativeCharacter tile and InstantKills55. Classification contradiction counter; SourceTileSelector native body exact meaning still requires declared reference policy, not client proof.'}
for name,value in [('inputs.json',records.INPUTS),('captures.json',records.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
primitive=[r for r in plugin.rows if '/test_self_remove.py' in r['nodeid']];assert len(plugin.rows)==1
with (OUT/'primitive_verification.json').open('x',encoding='utf8') as f:json.dump({'core':report['core'],'cases':primitive,'guards_equal':before==after,'report_sha':sha(OUT/'verification.json'),'changed_files':changes,'no_other_primitive_exemption':True},f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'primitive_sha':sha(OUT/'primitive_verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
