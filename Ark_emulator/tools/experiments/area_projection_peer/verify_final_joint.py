import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter07_consumers_peer import test_cards_warmed as cards,test_capacity as cap,common
from tools.experiments.wave_finish_peer import test_wave_bound as wave,test_cross as cross
from tools.experiments.chapter07_joint_peer import test_checkpoint_zero as zero
OUT=ROOT/'validation/campaign/chapter07_final3992_joint_independent';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(m.__file__) for m in [cards,cap,wave,cross,zero]]
files=[Path(__file__),*tests,Path(common.__file__),ROOT/'tools/chapter07_predefines/policies_v1.py',ROOT/'tools/chapter07_strength_melee/policies_v1.py',ROOT/'tools/chapter07_boss/policies_v1.py',ROOT/'tools/chapter07_boss/policies_v2.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter07_predefines_consumer/mine.module.v2.json',ROOT/'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v1.json',ROOT/'packages/campaign/chapter07_boss/patrt/combined.mechanism.v2.json',ROOT/'packages/campaign/chapter07_boss/patrt/source.closure.json',ROOT/'validation/campaign/chapter07_joint_independent_complete/inputs.json']+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
names=['test_native_card_public_deploy_keeps_actual_twelve_and_cp_restore_head','test_late_card_creation_buff_failure_rolls_back_payment_stock_allocation_tasks_rng','test_cards_preserve_real_scenario_zero_capacity_gate','test_public_finish_preserves_pending_birth_post_pre_and_cp_head','test_real_hpzero_rebirth_onbegin_releases_enemy_gate_not_future_birth','test_unchanged_actual_boss_in_managed_wave_source_cp6_head','test_actual_source_initial_public_checkpoint_zero_has_same_future_trace']
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
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(p) for p in tests),'-q','--import-mode=importlib','-k',' or '.join(names)],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Final3992 actual selected original7 crossing assertions/inputs unchanged: actualfixed12 nativecard CP2/head and lateatomic/true0capacity; futurebirth waveCP2/head; HP0waiting finishwaveCP2/head; unchanged actualPatriot managedwave CP6/head and initialCP0/head. No previous identity migrated; no whole/nativebody claim.'}
for name,value in [('inputs.json',common.INPUTS+wave.INPUTS+zero.INPUTS),('captures.json',common.CAPTURES+wave.CAPTURES+zero.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
