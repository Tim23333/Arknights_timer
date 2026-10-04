import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_units
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();model=ROOT/'packages/campaign/chapter03_visibility/three_hidden_sensor.model.json';p=json.loads(model.read_bytes());paths=[Path(__file__),Path(test_units.__file__),ROOT/'tools/build_chapter03_hidden_ranged.py',model,ROOT/'packages/campaign/chapter03_sources/native.reference.json',ROOT/'packages/campaign/chapter03_visibility/lurker_sensor.model.json',ROOT/'tools/campaign_ordered_checkpoint.py',RUNTIME/'ark_sim/rules/contracts.json']
for name,pin in p['manifest']['metadata']['source_locks'].items():
 f=ROOT.parent/name;assert sha(f)==pin;paths.append(f)
start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='e6d05494938ef71a20091b287475fc3e297b9831366a030b349b319a7df515a4';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_units.__file__))],plugins=[Results()]);end={str(p):sha(p) for p in paths};last=implementation_digest();report={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':test_units.INPUTS,'scope':'two actual ranged hidden source producers reuse frozen M49 controller with source disableWhenAttack0, their own normal/combat/projectile/stats; ordered disk and command replay','stage_executed':False,'client_verified':False,'formal_approved':False};out=ROOT/'validation/campaign/chapter03_hidden/final.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
