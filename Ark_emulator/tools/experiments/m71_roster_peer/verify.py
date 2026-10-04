import sys,json,hashlib,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m71_event_storage_candidate';sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import pytest,test_disk as t
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();files=[Path(__file__),Path(t.__file__),ROOT/'tools/campaign_ordered_checkpoint.py',t.HELPER,t.HELPER.with_name('campaign_streaming_evidence_v12.py'),RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in files};assert sha(t.HELPER)=='7d5c0ef3f02c48274cd128b8cce91e4bc50683ff75fb2d6c8be6be0e97e1f353';core=implementation_digest();assert core=='15517b90969c61b15340929687092401b4a807b6a3f66d0d2135e780568c04aa';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'passed':call.excinfo is None})
out=ROOT/'validation/campaign/m71_roster_peer';out.mkdir(parents=True,exist_ok=True);run=out/('casefiles-'+uuid.uuid4().hex)
code=pytest.main(['-q',str(Path(t.__file__)),'--basetemp',str(run)],plugins=[Results()]);end={str(p):sha(p) for p in files};last=implementation_digest();r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'actual_inputs':t.INPUTS,'fixtures':t.CAPTURES,'case_files_root':str(run),'file_sha256':{str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file()},'scope':'independent disk/ordering/rollback/observation review, no campaign receipt'};(out/'initial_review.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'core':core,'stable':core==last and start==end,'sha256':sha(out/'initial_review.json')}));raise SystemExit(0 if r['passed'] else 1)
