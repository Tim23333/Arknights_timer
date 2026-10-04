"""Record independently completed 4-10 without changing a live guarded registry."""
import hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    original=ROOT/'validation/campaign/runthrough/progress_after_03_07_and_04_09_20261004.json'
    prior=json.loads(original.read_bytes());assert prior['registry_sha256']==sha(ROOT/'validation/campaign/runthrough/registry.json')
    receipt=ROOT/'validation/campaign/chapter04_10_full_v1/root_completed_inspect.json';check=json.loads(receipt.read_bytes())
    result=check['inspection'];assert result['process_status']=='complete' and result['determinism_status']=='verified' and result['durable_checkpoint_status']=='verified'
    report=Path(result['report']);assert sha(report)==result['report_sha256']=='e612713e349c7f71974701619398c15a438e4323168685350388bbaee2ee53fc'
    current=deepcopy(prior);row=next(r for r in current['cases'] if r['native_id']=='main_04-10');assert row['process_status']=='not_run'
    row.update(result,official_registration_pending=True)
    current.update(schema='ark-sim/campaign-completed-pending-registration/v1',
        prior_progress_sha=sha(original),completed_receipt_sha=sha(receipt),registered_complete=4,
        registration_policy='Actual 5 complete receipts; registry remains byte-identical during legacy V20 guards')
    current['counts'].update(process_complete=sum(r['process_status']=='complete' for r in current['cases']),
        determinism_verified=sum(r['process_status']=='complete' and r['determinism_status']=='verified' for r in current['cases']),
        durable_checkpoint_verified=sum(r['process_status']=='complete' and r['durable_checkpoint_status']=='verified' for r in current['cases']))
    assert current['counts']['process_complete']==5
    out=ROOT/'validation/campaign/runthrough/progress_with_completed_pending_04_10_20261004.json'
    with out.open('x',encoding='utf8') as f:json.dump(current,f,ensure_ascii=False,indent=2)
    print(json.dumps({'counts':current['counts'],'registry_unchanged':True,'sha':sha(out)}))
if __name__=='__main__':main()
