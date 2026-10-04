import sys,json,hashlib,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m81_strict_event_reference_candidate';sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import pytest,test_storage as t
import test_reference
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();files=[Path(__file__),Path(t.__file__),ROOT/'tools/campaign_ordered_checkpoint.py',t.HELPER,ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v12.py',ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v13.py',ROOT/'tools/candidates/m77_event_storage/prepare_candidate.py',ROOT/'tools/candidates/m81_strict_event_reference/prepare_candidate.py',Path(test_reference.__file__),RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in files};assert sha(t.HELPER)=='2029677af14d702ef917522be3dd2d348b906366759905af41e6562399df29e9';core=implementation_digest();assert core=='9f0d15e6f84bcff2eb5f08f3a04f7753a5f3f952f904798f24808427e7f51b9e';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'passed':call.excinfo is None})
out=ROOT/'validation/campaign/m81_strict_event_reference';out.mkdir(parents=True,exist_ok=True);run=out/('casefiles-'+uuid.uuid4().hex)
code=pytest.main(['-q',str(Path(t.__file__)),str(Path(test_reference.__file__)),'--basetemp',str(run)],plugins=[Results()]);end={str(p):sha(p) for p in files};last=implementation_digest();r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'actual_inputs':t.INPUTS,'fixtures':t.CAPTURES,'reference_cases':test_reference.CASES,'case_files_root':str(run),'file_sha256':{str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file()},'scope':'author revision verification, no self-approval/campaign receipt'};(out/'final.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'core':core,'stable':core==last and start==end,'sha256':sha(out/'final.json')}));raise SystemExit(0 if r['passed'] else 1)
