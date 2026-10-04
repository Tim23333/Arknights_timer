import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_wave_track_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_stage_controls_review.audit_fields_v3 import audit
import pytest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+list((ROOT/'packages/campaign/chapter08_stage_controls').rglob('*'));paths=[p for p in paths if p.is_file()];paths += [ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json',ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v2.json',ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v2.life99999.v1.json',ROOT/'packages/campaign/chapter08_consumers/bsnake/four_modes.wave_source.v4.json',ROOT/'tools/campaign_ordered_checkpoint.py'];before={str(p):sha(p) for p in paths};fields=audit();cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name(x)) for x in ['test_controls_v2.py','test_fields_v1.py']]+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after;out=ROOT/'validation/campaign/chapter08_stage_controls_independent_final_v1';out.mkdir(exist_ok=False);f=out/'verification.json';f.write_text(json.dumps({'passed':code==0,'actual_exit':code,'core':implementation_digest(),'fields':fields,'cases':cases,'elapsed':time.monotonic()-start,'source_before':before,'source_after':after,'independent_of_author_helpers_fixtures':True,'scope':'Rawfixed story bytes+decoded Opera SerializedState originalparams21pins ->control steps; fresh irregularACK actual8/fade9/CP39/head, concurrentAV shifted4/10 exact0/6/9/90 noHP/SP/attributes/Buff/terrain/battleRNG sideeffects. Full44source draft allactions/routes/times/counts and onlylife recovery typeexact, 7 otheredit negative gates. Header is_skippable metadata notimplemented user skip; nativeglobalLock/render/nativeclockfeedback referencepolicy. FirstHPfullcapacitychosencontent vsoldliteral.5 sourcepolicy notclientvalidated; no oldproof value migration.','whole_stage_executed':False,'client_verified':False,'primary_modified':False},indent=2),encoding='utf8');print(json.dumps({'sha':sha(f),'actual_exit':code,'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
