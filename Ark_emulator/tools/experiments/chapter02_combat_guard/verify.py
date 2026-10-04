import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_guard
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();pkg=ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.combat_guard.reference_module.json';p=json.loads(pkg.read_bytes());paths=[Path(__file__),Path(test_guard.__file__),ROOT/'tools/experiments/chapter02_twelve/test_module.py',ROOT/'tools/build_chapter02_10_combat_guard.py',ROOT/'tools/campaign_content_composition.py',ROOT/'tools/campaign_ordered_checkpoint.py',pkg,RUNTIME/'ark_sim/rules/contracts.json']
for name,pin in p['manifest']['metadata']['source_locks'].items():
 f=Path(name);f=f if f.is_absolute() else ROOT/f
 assert sha(f)==pin;paths.append(f)
start={str(x):sha(x) for x in paths};core=implementation_digest();assert core=='a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_guard.__file__))],plugins=[Results()]);end={str(x):sha(x) for x in paths};last=implementation_digest();out=ROOT/'validation/campaign/chapter02_combat_guard/final.json';out.parent.mkdir(parents=True,exist_ok=True);r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':test_guard.INPUTS,'scope':'content-only exact three INPUT_TARGET2 source consumers; arbitrary taunt cannot override blocked identity; recorded deployment/ordered CP/replay; no stage receipt','stage_executed':False,'client_verified':False,'formal_approved':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if r['passed'] else 1)
