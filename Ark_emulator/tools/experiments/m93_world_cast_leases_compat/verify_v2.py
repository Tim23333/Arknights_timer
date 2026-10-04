from pathlib import Path
import sys,json,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m93_world_cast_leases_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
sys.path.insert(2,str(ROOT/'tests_v2'))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
spec=importlib.util.spec_from_file_location('m78_guard_compat',ROOT/'tools/experiments/m78_attachments/verify.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
selected=['tools/experiments/m78_attachments/test_attachment.py','tests_v2/test_abilities.py','tests_v2/test_auras.py','tests_v2/test_event_resources.py','tests_v2/test_damage_hooks_random.py']
def guard():
 g=a.guard()
 for name,folder,pattern in [('m93_source',RUNTIME/'ark_sim','*.py'),('m93_catalog',RUNTIME/'ark_sim','*.json'),('m93_tools',ROOT/'tools/candidates/m93_world_cast_leases','*.py'),('m93_experiments',ROOT/'tools/experiments/m93_world_cast_leases','*.py'),('compat_helper',Path(__file__).parent,'*.py')]:g[name]={str(p.relative_to(folder)):a.sha(p) for p in sorted(folder.rglob(pattern)) if '__pycache__' not in p.parts}
 paths=[ROOT/x for x in selected]+[ROOT/x for x in ['tools/experiments/m78_independent_controller_peer_v3/test_peer.py','tools/experiments/m78_independent_packet_peer/test_peer.py','tools/experiments/m78_independent_lifecycle_peer_v3/test_peer.py','tests_v2/test_campaign_acceptance.py']]
 g['selected_tests']={str(p):a.sha(p) for p in paths};return g
before=guard();pin=implementation_digest();assert pin=='4e5b8d8433dd860efa57ee031e07d42e99d8799b39d78499715ba71fb12d7020'
cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'longrepr':str(report.longrepr) if report.failed else None})
code=int(pytest.main(selected+['--import-mode=importlib','-q','--tb=short'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==pin
paths={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in paths.values())
report={'role':'M93 author compatibility and selected test SHA guard','passed':code==0,'core_start':pin,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_modules':paths,'actual_inputs':[p for n,m in sys.modules.items() if n.endswith('test_attachment') for p in getattr(m,'INPUTS',[])],'limits':'Selected compatibility only, not all V2 regression, independent acceptance, whole stage or client accuracy'}
OUT=ROOT/'validation/campaign/m93_world_cast_leases'
with (OUT/'compatibility_v2.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed']}));sys.exit(code)
