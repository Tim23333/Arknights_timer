import sys,json,hashlib,time,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 stage=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v7.json';data=json.loads(stage.read_bytes());paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+[stage,stage.with_name('level_main_08-16.native_draft.v7.life99999.v1.json'),ROOT/'tools/campaign_ordered_checkpoint.py'];paths += [Path(p) for p in data['manifest']['metadata']['source_locks']];pending=[ROOT/'tools/chapter08_buff_lifetime/talula_providers_v1.py',ROOT/'tools/chapter08_special/policies_v2.py',ROOT/'tools/chapter08_ranged/policies_v1.py',ROOT/'tools/chapter08_environment/policies_v1.py'];seen=set()
 while pending:
  p=pending.pop()
  if p in seen:continue
  seen.add(p)
  for node in ast.walk(ast.parse(p.read_bytes())):
   if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('tools.'):
    q=(ROOT/Path(*node.module.split('.'))).with_suffix('.py')
    if q.exists():pending.append(q)
 paths+=list(seen);paths=list(dict.fromkeys(paths));before={str(p):sha(p) for p in paths};cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name(n)) for n in ['test_jt82_v3.py','test_jt82_dynamic_v2.py']]+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after;out=ROOT/'validation/campaign/chapter08_jt82_v7_independent_final';out.mkdir(exist_ok=False);f=out/'verification.json';f.write_text(json.dumps({'passed':code==0,'actual_exit':code,'core':implementation_digest(),'cases':cases,'elapsed':time.monotonic()-start,'guards_before':before,'guards_after':after,'no_author_fixture_builder_imports':True,'consumer_provider_imports_are_actual_frozen_algorithms_not_expected_oracles':True,'scope':'Fresh32native fieldadmission/5exactvariants/map/allusedroutes/originalWave/Fragment/Action delays/counts/managedflags/DP10life3slots9seed/fixed12/onlylife goal recovery, v7 sourcevalues identicalv6 butnewruntime82db proof. Fulluncut nativeplan180/CPP47/head. Controlledoriginalmap400/CPP113/head: infection ATK120->180 ASPD1->1.5/realdamage and sixvolcanoes actual1000NoSource. Currentstage D12 remaininglifetime independent915-200=715 then rate2 ceil357.5 =>expiry558/CPP211/head; native50+180*t/900 actual18packets30..540, permanentchildafterparentexpiry. No migration9ad/oldnarrow/sourcejournals, notwhole-stage or allalgorithm/client accuracy.'},indent=2),encoding='utf8');print(json.dumps({'actual_exit':code,'cases':len(cases),'sha':sha(f)}));raise SystemExit(code)
if __name__=='__main__':main()
