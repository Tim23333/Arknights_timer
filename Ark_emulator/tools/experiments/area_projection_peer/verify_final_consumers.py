import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter07_consumers_peer import common,test_ore as ore,test_mine_bound as mine,test_strength_current as strength,test_strength_extra as packet,test_story_fields as story
OUT=ROOT/'validation/campaign/chapter07_final3992_consumers_independent';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(m.__file__) for m in [ore,mine,strength,packet,story]]
files=[Path(__file__),*tests,Path(common.__file__),common.ORE,common.MINE,common.STORY,*common.STRENGTH,ROOT/'tools/chapter07_predefines/policies_v1.py',ROOT/'tools/chapter07_strength_melee/policies_v1.py',ROOT/'tools/chapter07_strength_melee/policies_v2.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/campaign_content_composition_v2.py',ROOT/'tools/control_driver/public_ack_v2.py',ROOT/'packages/campaign/chapter07_sources/native.reference.json',ROOT/'packages/campaign/chapter07_predefines/source.v4.reference.json']+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
selected=['test_midcast_immune_expiry_and_listener_checked_at_actual_payload_disk_head','test_natural_source_mode20s_separate_from_sp25_and_disk_prehit','test_variant2_marker_remove_never_cleans_variant1_or_variant3_disk_head','test_real_public_blocker_three_source_melee_packets_use_their_own_strength','test_story_v2_source_utf8_five_actual_acks_protect_fade_sidecar_disk_head']
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
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(p) for p in tests),'-q','--import-mode=importlib','-k',' or '.join(selected)],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Final3992 selected source crossings; original asserted input/code files unchanged. Ore lateimmune/listener CP18/head; mine actualnaturalclock/SP25 hit749 CP601/head; strengthownvariant markerremoval CP7/head; true publicblocker source3melee509/743/269; storyV2 UTF8/raw7/actual5publicacks/protect15/fade9/CP3driver/head. No sourcebody/client/whole claim; earlier broader4f16/478 results preserve their identities.'}
for name,value in [('inputs.json',common.INPUTS),('captures.json',common.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
