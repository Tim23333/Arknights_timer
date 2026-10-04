import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate';sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import pytest,test_profiles as t
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();src=ROOT/'packages/campaign/chapter04_sources/native.reference.json';source=json.loads(src.read_bytes());files=[Path(__file__),Path(t.__file__),ROOT/'tools/build_chapter04_demon_profiles.py',src,ROOT/'tools/campaign_ordered_checkpoint.py',*[t.OUT/(policy+'.model.json') for policy in ['with_pre_only','no_pre_only']],ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs'];files += [ROOT.parent/p for p in source['source_locks']]
start={str(p):sha(p) for p in files};assert all(sha(ROOT.parent/p)==h for p,h in source['source_locks'].items());core=implementation_digest();assert core=='1ef9635ee70a8159e0523156aeeb177329d19d12a26185b98b9d9fa55ea3c3d5';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'passed':call.excinfo is None})
code=pytest.main(['-q',str(Path(t.__file__))],plugins=[Results()]);end={str(p):sha(p) for p in files};last=implementation_digest();out=ROOT/'validation/campaign/chapter04_demon_profiles';out.mkdir(parents=True,exist_ok=True);r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixtures':t.CAPTURES,'scope':'two explicit branch profiles only; native dispatch unknown and client feedback retained; no stage receipt'};(out/'final.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'report_sha256':sha(out/'final.json')}));raise SystemExit(0 if r['passed'] else 1)
