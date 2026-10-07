"""Freeze only completed independent v2 clock reports, retaining v1 identity."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OUT=ROOT/'validation/campaign/chapter0_source_numeric_peer_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    report=OUT/'clock.actual.v2.json';r=json.loads(report.read_bytes());assert r['passed'] and r['source_unchanged'] and len(r['cases'])==17 and len(r['full_disk_CP_head'])==16
    assert all(p['four_observations_equal'] and p['full_checkpoint_equal'] for p in r['full_disk_CP_head'])
    assert all(sha(k)==h for k,h in r['source_guards'].items())
    old=json.loads((OUT/'freeze.peer.v1.json').read_bytes())
    assert all(sha(ROOT/k)==h for group in ('reports','tools') for k,h in old[group].items())
    done=Path('E:/ArkSimLogs/receipts/chapter0_capped_clock_peer_20261007_v3/completion.json');completion=json.loads(done.read_bytes());assert completion['worker_exit']==completion['cleanup_exit']==0 and completion['raw_logs_removed_after_validation'] and completion['cleanup_result']['fully_cleaned'];(OUT/'clock.completion.v2.json').write_bytes(done.read_bytes())
    names=['clock.actual.v2.json','clock.completion.v2.json','clock.launcher.failure.v2.json','clock.source.review.v1.json','selection.source.review.v1.json'];record={'schema':'ark-sim/chapter0-capped-clock-independent-freeze/v2','core':r['core'],'consumer_scope_passed':True,'cases':17,'complete_disk_CP_head':16,
      'source_guards':r['source_guards'],'reports':{str((OUT/n).relative_to(ROOT)):sha(OUT/n) for n in names},'tools':{str((HERE/n).relative_to(ROOT)):sha(HERE/n) for n in ['verify_clock_v2.py','freeze_clock_v2.py','review_clock.py']},
      'v1_bounded_freeze_sha256':sha(OUT/'freeze.peer.v1.json'),'old_v1_reports_unchanged':True,'native_formula_verified':False,'clock_policy':r['clock_policy'],'whole_stage':False,'client_verified':False,'source_timestamp_versions_alignment_verified':False,'target_cancel_order':'Actual public target/source death behavior measured on current model; native callback method bodies not recovered'}
    out=OUT/'freeze.clock.peer.v2.json';out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha256':sha(out),'cases':17,'full_CP_head':16}))
if __name__=='__main__':main()
