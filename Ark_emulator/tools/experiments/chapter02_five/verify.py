import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m44_chapter02_integrated_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_module
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(test_module.__file__),ROOT/'tools/build_chapter02_09_enemy_module.py',ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json',ROOT/'packages/campaign/chapter02_sources/native.reference.json',ROOT/'tools/campaign_content_composition.py',ROOT/'tools/experiments/defdrn_status/test_model.py',ROOT/'tools/experiments/m41_peer/test_peer.py']
start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='81d12ea08787d4edeed139ab55dc73e424644a1b4b8f48360fb9b114b25203da';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_module.__file__)),str(paths[-2]),str(paths[-1])],plugins=[Results()]);end={str(p):sha(p) for p in paths};last=implementation_digest()
fixtures=list(test_module.INPUTS)
for name in ['test_model','test_peer']:
 if name in sys.modules:fixtures+=sys.modules[name].INPUTS
out=ROOT/'validation/campaign/chapter02_five/m44_final.json';out.parent.mkdir(parents=True,exist_ok=True);report={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixtures':fixtures,'scope':'five actual module stats/motion/steering birth plus source-backed silence and independent contact fixtures under merged M44; no stage run','formal_approved':False};out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
