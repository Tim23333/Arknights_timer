import sys,json,hashlib,importlib.util,tempfile,contextlib,io,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_combat_v5_candidate';OUT=ROOT/'validation/campaign/frost_combat_v6';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='df98feb41687d1b560d27d24bcbc7aad8bbb2f7ace48aaa67aca5816fe95e86b'
selected=['tools/experiments/m78_attachments/test_attachment.py','tools/experiments/m93_world_cast_leases/test_leases.py','tools/experiments/m93_world_cast_leases/test_author_boundary.py','tools/experiments/m96_immunity_independent_peer/test_cross.py','tools/experiments/m94_independent_boundary_peer_v2/test_boundary.py','tools/experiments/m75_packet_order/test_packets.py','tools/experiments/m72_no_source_damage/test_no_source.py','tools/experiments/m84_catalog_peer/test_peer.py','tests_v2/test_abilities.py','tests_v2/test_auras.py','tests_v2/test_event_resources.py','tests_v2/test_damage_hooks_random.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'parent':(ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate/ark_sim','*.py'),'tools':(ROOT/'tools/candidates/frost_combat_v1','*'),'experiments':(ROOT/'tools/experiments/frost_combat_v6','*.py'),'compat_helper':(Path(__file__).parent,'*.py'),'models':(ROOT/'packages/campaign/chapter04_boss/frost_combat_v6','*.json')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
 paths=[ROOT/p for p in selected+['packages/campaign/chapter04_boss/frost_combat_v1/source.audit.json','packages/campaign/chapter04_boss_plan/source.reference.json','packages/campaign/chapter04_sources/native.reference.json','packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json','packages/campaign/chapter04_dmage/module.immunity_guard.reference.json','tools/campaign_ordered_checkpoint.py','tests_v2/test_campaign_acceptance.py']];g['selected_and_consumed']={str(p):sha(p) for p in paths};return g
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main(selected+['--import-mode=importlib','-q','--tb=short'],plugins=[Capture()]))
spec=importlib.util.spec_from_file_location('frost_builder',ROOT/'tools/candidates/frost_combat_v1/build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory(prefix='frost_rebuild_',dir=RUNTIME.parent) as temp:
 b.OUT=Path(temp)/'candidate';b.ROOT=Path(temp)/'evidence'
 with contextlib.redirect_stdout(io.StringIO()):b.main()
 assert b.core(b.OUT)==PIN
for script in ['audit.py','module_v6.py']:subprocess.run([sys.executable,str(ROOT/'tools/candidates/frost_combat_v1'/script),'--check'],check=True,capture_output=True,text=True)
after=guard();assert before==after and implementation_digest()==PIN
actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
target=OUT/'compatibility.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Frost combat author compatibility and frozen-byte rebuilding','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'fresh_rebuild_equal':True,'source_and_module_byte_checks':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_modules':actual,'passed':code==0,'limits':'Selected compatibility only; not independent acceptance, full suite or 4-10'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'sha256':sha(target),'failed':[c['case'] for c in cases if c['outcome']=='failed']}));sys.exit(code)
