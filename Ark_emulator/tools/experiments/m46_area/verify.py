import json,sys,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m46_area_members_candidate';BASE=ROOT.parent/'unpack_work/campaign_m44_chapter02_integrated_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_generic,test_boss
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();OUT=ROOT/'validation/campaign/m46_area';OUT.mkdir(parents=True,exist_ok=True)
package=ROOT/'packages/campaign/chapter02_behavior/reference50/skulsr.model.json';payload=json.loads(package.read_bytes());paths=[Path(__file__),Path(test_generic.__file__),Path(test_boss.__file__),Path(__file__).with_name('capture_noopt.py'),ROOT/'tools/candidates/m46_area_members/prepare_candidate.py',ROOT/'tools/build_skulsr_reference50.py',ROOT/'tools/campaign_ordered_checkpoint.py',package,RUNTIME/'ark_sim/rules/contracts.json']
for name,pin in payload['manifest']['metadata']['source_locks'].items():
 p=Path(name);p=p if p.is_absolute() else ROOT/p
 assert sha(p)==pin;paths.append(p)
start={str(p):sha(p) for p in paths};core=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_generic.__file__)),str(Path(test_boss.__file__))],plugins=[Results()])
p=test_generic.fixture();p['rules']=[];e=p['abilities'][0]['timeline'][0]['effect'];e.pop('membership_rule');e.pop('parameters');e['radius']=1.5;input_path=OUT/'noopt.input.json';input_path.write_text(json.dumps(p,indent=2)+'\n',encoding='utf8')
captures=[]
for root,name in [(BASE,'parent'),(RUNTIME,'candidate')]:
 out=OUT/('noopt.'+name+'.json');subprocess.run([sys.executable,str(Path(__file__).with_name('capture_noopt.py')),str(root),str(input_path),str(out)],check=True);captures.append(json.loads(out.read_bytes()))
def normalized(x):
 if isinstance(x,dict):return {k:normalized(v) for k,v in x.items() if k not in {'program_fingerprint','runtime_fingerprint'}}
 if isinstance(x,list):return [normalized(v) for v in x]
 return x
equal=all(normalized(captures[0][k])==normalized(captures[1][k]) for k in ['snapshot','checkpoint']);end={str(p):sha(p) for p in paths};last=implementation_digest()
report={'passed':code==0 and equal and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'generic_inputs':test_generic.INPUTS,'boss_inputs':test_boss.INPUTS,'noopt':{'equal':equal,'excluded_identity_fields':['program_fingerprint','runtime_fingerprint'],'parent_core':captures[0]['core'],'events':len(captures[1]['snapshot']['events']),'input_sha256':sha(input_path),'parent_artifact_sha256':sha(OUT/'noopt.parent.json'),'candidate_artifact_sha256':sha(OUT/'noopt.candidate.json')},'scope':'pure opt-in membership/Boss declared table-reference short models; no stage receipt','client_verified':False,'formal_approved':False};out=OUT/'final.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'core':core,'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
