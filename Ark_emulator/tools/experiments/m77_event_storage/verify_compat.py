import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m77_event_storage_candidate';sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.append(str(ROOT));import pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();paths=[ROOT/'tools/experiments/m71_event_storage/test_storage.py',ROOT/'tests_v2/test_kernel.py',ROOT/'tests_v2/test_replay.py'];files=[Path(__file__),*paths,RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in files};core=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'passed':call.excinfo is None})
code=pytest.main(['-q',*[str(p) for p in paths]],plugins=[Results()]);end={str(p):sha(p) for p in files};last=implementation_digest();out=ROOT/'validation/campaign/m77_event_storage/compat.json';r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'core':core,'sha256':sha(out)}));raise SystemExit(0 if r['passed'] else 1)
