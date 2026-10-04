"""Source/conflict/content guards, separate from generic core evidence."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m28_unlimited_projectile_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest
import test_skulsr as tests
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=ROOT/'packages/campaign/chapter02_behavior/skulsr.conflict.reference.json';audit=json.loads(source.read_bytes());paths=[Path(__file__),Path(tests.__file__),ROOT/'tools/build_skulsr_partial.py',ROOT/'tools/audit_skulsr_native_sources.py',ROOT/'tools/probe_skulsr_managed_bodies.ps1',source,ROOT/'packages/campaign/chapter02_behavior/projectiles.partial.json',*[tests.OUT/f'skulsr.{p}.partial.json' for p in ('serialized','DB')]]
for path,pin in audit['source_locks'].items():assert sha(path)==pin;paths.append(Path(path))
for row in audit['hot_lua_inventory']:assert sha(row['path'])==row['sha256'];paths.append(Path(row['path']))
start={str(p):sha(p) for p in paths};core=implementation_digest();cases=[]
assert core=='cb0e7a97a2621aaf4b14dc942181686906733acbcc61f6a5a23ebae9448e997b'
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main([str(Path(tests.__file__)),'-q'],plugins=[Results()]);end={str(p):sha(p) for p in paths};core_end=implementation_digest()
report={'schema_version':1,'scope':'explicit unresolved HP policy/manual dualmode attack/combat interface only; not native or complete stage','passed':code==0 and start==end and core==core_end,'core_start':core,'core_end':core_end,'module_path':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':tests.INPUTS,'source_conflict':'HP serialized .4000000059604645 vsDB.5 remains unresolved','native_body_recovered':False,'actual_game_correct':False,'formal_approved':False}
out=ROOT/'validation/campaign/m28_unlimited/skulsr_final.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'fixtures':len(tests.INPUTS),'source_locks':len(start),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
