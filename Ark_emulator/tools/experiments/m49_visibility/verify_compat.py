import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();names=['test_auras.py','test_domain_rules.py','test_abilities.py'];paths=[Path(__file__),*[ROOT/'tests_v2'/x for x in names],RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in paths};core=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',*[str(ROOT/'tests_v2'/x) for x in names]],plugins=[Results()]);end={str(p):sha(p) for p in paths};last=implementation_digest();r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'scope':'existing aura/domain/abilities compatibility; not a stage receipt'};out=ROOT/'validation/campaign/m49_visibility/compat.json';out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if r['passed'] else 1)
