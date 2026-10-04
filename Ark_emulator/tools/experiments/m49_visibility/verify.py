import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate';BASE=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_toggle,test_sources
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();out=ROOT/'validation/campaign/m49_visibility';out.mkdir(parents=True,exist_ok=True)
source=ROOT/'packages/campaign/chapter03_visibility/source.reference.json';model=ROOT/'packages/campaign/chapter03_visibility/lurker_sensor.model.json';d=json.loads(source.read_bytes());paths=[Path(__file__),Path(test_toggle.__file__),Path(test_sources.__file__),Path(__file__).with_name('capture_noopt.py'),ROOT/'tools/candidates/m49_visibility/prepare_candidate.py',ROOT/'tools/candidates/m49_visibility/toggles.py',ROOT/'tools/audit_chapter03_visibility.py',ROOT/'tools/build_chapter03_visibility_model.py',ROOT/'tools/campaign_ordered_checkpoint.py',source,model,RUNTIME/'ark_sim/rules/contracts.json']
for name,pin in d['source_locks'].items():
 path=ROOT.parent/name;assert sha(path)==pin;paths.append(path)
start={str(p):sha(p) for p in paths};core=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_toggle.__file__)),str(Path(test_sources.__file__))],plugins=[Results()])
captures=[]
for root,label in [(BASE,'parent'),(RUNTIME,'candidate')]:
 path=out/('noopt.'+label+'.json');subprocess.run([sys.executable,str(Path(__file__).with_name('capture_noopt.py')),str(root),str(path)],check=True);captures.append(json.loads(path.read_bytes()))
def normalized(v):
 if isinstance(v,dict):return {k:normalized(x) for k,x in v.items() if k not in {'program_fingerprint','runtime_fingerprint'}}
 if isinstance(v,list):return [normalized(x) for x in v]
 return v
equal=all(normalized(captures[0][k])==normalized(captures[1][k]) for k in ['snapshot','checkpoint']);end={str(p):sha(p) for p in paths};last=implementation_digest();report={'passed':code==0 and equal and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'generic_inputs':test_toggle.INPUTS,'source_inputs':test_sources.INPUTS,'noopt_equal':equal,'noopt_events':len(captures[1]['snapshot']['events']),'excluded_identity_fields':['program_fingerprint','runtime_fingerprint'],'scope':'generic conditional passive/status immunity/availability plus source-backed lurker/sensor short fixtures, no source-stage execution','client_verified':False,'formal_approved':False};path=out/'final.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'core':core,'sha256':sha(path)}));raise SystemExit(0 if report['passed'] else 1)
