import sys,json,hashlib,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m63_deploy_cooldown_candidate';BASE=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate';sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import pytest,test_cooldown as t
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();files=[Path(__file__),Path(t.__file__),ROOT/'tools/candidates/m63_deploy_cooldown/prepare_candidate.py',ROOT/'tools/campaign_ordered_checkpoint.py',RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in files};core=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'passed':call.excinfo is None})
code=pytest.main(['-q',str(Path(t.__file__))],plugins=[Results()]);end={str(p):sha(p) for p in files};last=implementation_digest();out=ROOT/'validation/campaign/m63_deploy_cooldown';out.mkdir(parents=True,exist_ok=True);diffs=[];patch=''
for p in sorted((RUNTIME/'ark_sim').rglob('*.py')):
 old=BASE/p.relative_to(RUNTIME)
 if p.read_bytes()!=old.read_bytes():
  name=str(p.relative_to(RUNTIME/'ark_sim'));diffs.append(name);patch+=''.join(difflib.unified_diff(old.read_text().splitlines(True),p.read_text().splitlines(True),fromfile='m58/'+name,tofile='m63/'+name))
(out/'candidate.patch').write_text(patch,encoding='utf8');r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'changed_files':diffs,'cases':cases,'fixtures':t.CAPTURES,'actual_fixture_inputs':t.INPUTS,'scope':'generic deploy/retire timing only; constant cost is test content; no stage/promotion receipt'};(out/'final.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'core':core,'report_sha256':sha(out/'final.json'),'patch_sha256':sha(out/'candidate.patch')}));raise SystemExit(0 if r['passed'] else 1)
