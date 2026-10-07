"""Freeze bounded actual O1 proof and a tracked byte snapshot; no promotion."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
DEST=ROOT/'validation/campaign/campaign_death_event_lookup_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    candidate=json.loads((DEST/'candidate.v1.json').read_bytes());result=json.loads((DEST/'actual.v2.json').read_bytes())
    path=Path(candidate['candidate']);assert result['passed'] and result['source_unchanged']
    assert len(result['cases'])==9 and all(row['passed'] for row in result['cases'])
    assert len(result['actual_CP_head_proofs'])==3
    assert all(p['disk_CP_equal'] and p['head_equal'] and p['full_checkpoint_equal'] for p in result['actual_CP_head_proofs'])
    assert all(sha(path/k)==h for k,h in candidate['inventory'].items())
    snapshot=HERE/'source_delta.v1'/candidate['delta']['file'];snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes((path/candidate['delta']['file']).read_bytes())
    assert sha(snapshot)==candidate['delta']['current']
    receipt=Path('E:/ArkSimLogs/receipts/death_event_lookup_perf_gates_20261007_v2/completion.json')
    completion=json.loads(receipt.read_bytes());assert completion['worker_exit']==completion['cleanup_exit']==0 and completion['raw_logs_removed_after_validation']
    (DEST/'completion.v2.json').write_bytes(receipt.read_bytes())
    record={'schema':'ark-sim/death-event-indexed-functional-freeze/v1','core':result['core'],'parent_core':result['parent_core'],
      'candidate':candidate['candidate'],'parent_freeze_sha256':candidate['parent_freeze_sha256'],'inventory':candidate['inventory'],
      'source_delta':candidate['delta'],'tracked_source_snapshot':{'path':str(snapshot.relative_to(ROOT)),'sha256':sha(snapshot)},
      'harness':{str(p.relative_to(ROOT)):sha(p) for p in HERE.glob('*.py')},
      'actual_report':{'path':str((DEST/'actual.v2.json').relative_to(ROOT)),'sha256':sha(DEST/'actual.v2.json'),'cases':9,'full_disk_CP_head':3},
      'historical_fixture_failure':{'path':str((DEST/'actual.v1.json').relative_to(ROOT)),'sha256':sha(DEST/'actual.v1.json'),'retained':True},
      'cleanup_receipt_sha256':sha(DEST/'completion.v2.json'),'passed':True,'promoted':False,'full_suite_pending':True,
      'parent_phase_acceptance_not_substituted':True,'whole_stage_claim':False,'primary_or_live_modified':False}
    out=DEST/'freeze.functional.v1.json';out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'freeze':str(out),'sha256':sha(out),'core':result['core']}))
if __name__=='__main__':main()
