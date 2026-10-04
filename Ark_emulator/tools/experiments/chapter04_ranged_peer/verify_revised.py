import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==ROOT/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));import pytest,test_revised as t
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();files=[Path(__file__),Path(t.__file__),t.SOURCE,ROOT/'packages/campaign/chapter04_units/ranged/table.reference_model.json',ROOT/'packages/campaign/chapter04_units/ranged/source_circle.reference_model.json',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'ark_sim/rules/contracts.json'];files +=[ROOT.parent/p for p in t.SRC['source_locks']];start={str(p):sha(p) for p in files};assert all(sha(ROOT.parent/p)==h for p,h in t.SRC['source_locks'].items());core=implementation_digest();assert core=='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'passed':call.excinfo is None})
code=pytest.main(['-q',str(Path(t.__file__))],plugins=[Results()]);end={str(p):sha(p) for p in files};last=implementation_digest();out=ROOT/'validation/campaign/chapter04_ranged_peer';out.mkdir(parents=True,exist_ok=True);r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'actual_inputs':t.INPUTS,'fixtures':t.CAPTURES,'scope':'independent ranged source/packets/branches, no stage receipt'};(out/'revised_review.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'core':core,'stable':core==last and start==end,'sha256':sha(out/'revised_review.json')}));raise SystemExit(0 if r['passed'] else 1)
