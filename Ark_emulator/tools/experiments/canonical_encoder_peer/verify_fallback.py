import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'))
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/canonical_encoder_peer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    import pytest
    names=['tools/campaign_canonical_encoder.py','tools/campaign_streaming_evidence_v2.py','tools/campaign_streaming_evidence.py','tools/run_campaign_streaming_runthrough_v10.py',
        'tools/experiments/canonical_encoder_peer/test_fallback.py',str(Path(__file__).relative_to(ROOT))]
    before={name:sha(ROOT/name) for name in names};core=implementation_digest();cases=[]
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    result=pytest.main([str(Path(__file__).with_name('test_fallback.py')),'-q'],plugins=[Results()]);assert result==0
    assert core==implementation_digest() and before=={name:sha(ROOT/name) for name in names}
    report={'schema':'ark-sim/experimental-encoder-correctness-review/v1','status':'passed_bounded_correctness_fallback','helper_source_locks':before,'actual_core':core,'cases':cases,
        'scope':'Original generic streaming chunks; one-record detached owned snapshot for records; no trust of public malformed wrapper identity across calls/yields.',
        'old_failures':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [OUT/'malformed_frozen_original_failure.json',OUT/'mutable_backing_deep_revision_failure.json']],
        'limitations':['No current speedup claim. Earlier identity-cache timing is historical and not transferred.','Generic chunks retain old streaming mutation/exception semantics rather than promising a detached whole journal.','Only records take an owned snapshot per event; this avoids whole-history duplication but retains per-record peak cost.','v10 remains experimental/not promoted; existing live v9 inputs/helpers not modified.'],
        'actual_engine_journal_used':True,'formal_approved':False,'whole_stage_executed':False,'client_verified':False}
    path=OUT/'fallback_final_review.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':len(cases),'sha256':sha(path)}))
if __name__=='__main__':main()
