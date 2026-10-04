"""Assertion-identical M30 copy + frozen M28 and V2 ability compatibility."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=[Path(__file__).with_name('test_quota_compat_copy.py'),ROOT/'tools/experiments/m28_unlimited/test_unlimited.py',ROOT/'tests_v2/test_abilities.py'];original=ROOT/'tools/experiments/m30_quota/test_quota.py';raw=files[0].read_bytes();assert raw.replace(b'campaign_m37_projectile_refs_candidate',b'campaign_m30_projectile_quota_candidate').replace(b'c77ce7a46101cf903fd9c6c56dcabddf5775008d091365cd7486ddeb47b8d740',b'517290e56f59bdf5f57862dbadb8929b37cf6fbe0468116dcb39669df6357b51')==original.read_bytes()
core=implementation_digest();start={str(p):sha(p) for p in [Path(__file__),original,*files]};cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',*[str(p) for p in files]],plugins=[Results()]);end={str(p):sha(p) for p in [Path(__file__),original,*files]}
report={'passed':code==0 and start==end and core==implementation_digest(),'core':core,'module':ark_sim.__file__,'test_start':start,'test_end':end,'cases':cases,'source_copy_changes':'only explicit candidate path/core literals, original assertions byte-identical after reverse replacement','scope':'compatibility, not independent peer or stage','formal_approved':False};out=ROOT/'validation/campaign/m37_projectile_refs/compatibility_final.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
