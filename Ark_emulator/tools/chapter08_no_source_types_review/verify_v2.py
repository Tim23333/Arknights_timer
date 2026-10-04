import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_no_source_types_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+[ROOT/'tools/campaign_ordered_checkpoint.py'];before={str(p):sha(p) for p in paths};cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name(n)) for n in ['test_peer_v2.py','test_edges_v2.py','test_aura_v2.py']]+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after;out=ROOT/'validation/campaign/chapter08_no_source_types_independent_final';out.mkdir(exist_ok=False);f=out/'verification.json';f.write_text(json.dumps({'passed':code==0,'actual_exit':code,'core':implementation_digest(),'cases':cases,'elapsed':time.monotonic()-start,'source_before':before,'source_after':after,'author_fixture_imported':False,'scope':'Different1600 actorNone arts/currentRES45=880, physical/currentDEF913=687, PURE1600; targetquarterhook220 vsbypass1600. PublicRESchange8 currentRES35 at13->1040. Realownedradius1.1 Aura afterhookquarter withsourceNone, parent publicwithdraw9 removeschild->880. NonlethalSPFalse1, True0; ignoredlethalbounded8000/deadoneNonekill. Typedprotocols/sourceorcast(includinginactive) cannotborrow; inactiveTarget packet skip; multipleallocationbadresource rollback allstores; content5%floor5 notgenericfakeATK. AllCPP11/SHAload/head exact and ElogsCP immediatelyclean. Extraoriginal lethalSP1 assertion unexpectedmodelpolicy0 is excluded pendingRootsource interpretation; Resource.notify explicitlyskips retiredinactive, not silentlyfixedcandidate. ExtraexpressiondamagePipelinefixture invalidschema excluded; providerpipeline isvalid. NotnativeSourceFIREconsumer/gameclient/whole proof.'},indent=2),encoding='utf8');print(json.dumps({'sha':sha(f),'actual_exit':code,'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
