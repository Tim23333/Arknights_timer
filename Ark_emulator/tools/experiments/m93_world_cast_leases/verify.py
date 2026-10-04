from pathlib import Path
import sys,json,hashlib,importlib.util,tempfile,contextlib,io
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m93_world_cast_leases_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest,ark_sim
spec=importlib.util.spec_from_file_location('m78_guard',ROOT/'tools/experiments/m78_attachments/verify.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
OUT=ROOT/'validation/campaign/m93_world_cast_leases';OUT.mkdir(parents=True,exist_ok=True)
def guard():
 g=a.guard()
 for name,folder,pattern in [('m93_source',RUNTIME/'ark_sim','*.py'),('m93_catalog',RUNTIME/'ark_sim','*.json'),('m93_tools',ROOT/'tools/candidates/m93_world_cast_leases','*.py'),('m93_experiments',Path(__file__).parent,'*.py')]:g[name]={str(p.relative_to(folder)):a.sha(p) for p in sorted(folder.rglob(pattern)) if '__pycache__' not in p.parts}
 return g
before=guard();pin=implementation_digest();assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'longrepr':str(report.longrepr) if report.failed else None})
packet='tools/experiments/m78_independent_packet_peer/test_peer.py';life='tools/experiments/m78_independent_lifecycle_peer_v3/test_peer.py'
selected=['tools/experiments/m78_independent_controller_peer_v3/test_peer.py',packet+'::test_native_priority_charge_and_contact_clock',packet+'::test_packet_600_live_public_atk_change_flags_sp_and_disk_replay',packet+'::test_damage_fault_rng_full_boundary_rollback',life+'::test_public_target_kill_flight_and_held_cleanup',life+'::test_external_source_stun_is_not_ignored_as_own_hold',life+'::test_skill_range3_acquires_outside_normal2_5',str(Path(__file__).with_name('test_leases.py'))]
code=int(pytest.main(selected+['--import-mode=importlib','-k','not normal_source2','-q','--tb=short'],plugins=[Capture()]))
spec=importlib.util.spec_from_file_location('m93_builder',ROOT/'tools/candidates/m93_world_cast_leases/build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
# Rebuild into a new temporary checkout while redirecting the composition path
# through a private ROOT, preserving all frozen reports.
with tempfile.TemporaryDirectory(prefix='m93_reproduce_',dir=RUNTIME.parent) as tmp:
 b.OUT=Path(tmp)/'candidate';b.ROOT=Path(tmp)/'report_root'
 with contextlib.redirect_stdout(io.StringIO()):b.main()
 assert b.core(b.OUT)==pin
after=guard();assert before==after and implementation_digest()==pin
mods=[m for n,m in sys.modules.items() if n.endswith('test_peer') or n.endswith('test_leases')]
report={'role':'M93 author verification; not independent peer acceptance','parent_core':b.PIN,'core_start':pin,'core_end':implementation_digest(),'start_manifest':before,'end_manifest':after,'guards_equal':True,'reproduction_equal':True,'cases':cases,'actual_inputs':[p for m in mods for p in getattr(m,'INPUTS',[])],'full_captures':[c for m in mods for c in getattr(m,'CAPTURES',[])],'actual_modules':{n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)},'scope':'World-wide cast leases and unchanged original M78 controller9/packet3/lifecycle4 assertions; old DMAGE90e source2 bug remains a separate content defect; no stage/client acceptance'}
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'core':pin,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed']}));sys.exit(code)
