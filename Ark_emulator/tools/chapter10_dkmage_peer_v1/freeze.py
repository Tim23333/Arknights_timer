"""Freeze executed independent consumer evidence; no production promotion."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter10_dkmage_peer_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    path=OUT/'result.v1.json';r=json.loads(path.read_bytes())
    assert r['passed'] and r['source_unchanged'] and len(r['cases'])==6
    assert all(row['passed'] for row in r['cases'])
    assert len(r['actual_CP_head_proofs'])==9 and all(p['disk_CP_equal'] and p['head_equal'] and p['full_checkpoint_equal'] for p in r['actual_CP_head_proofs'])
    assert all(sha(p)==h for p,h in r['source_guards'].items())
    receipt=Path('E:/ArkSimLogs/receipts/chapter10_dkmage_peer_20261007_c/completion.json');exit=json.loads(receipt.read_bytes())
    assert exit['worker_exit']==exit['cleanup_exit']==0 and exit['raw_logs_removed_after_validation']
    data={'schema':'ark-sim/dkmage-source-independent-freeze/v1','bounded_selected_source_consumer_passed':True,'core':r['core'],
      'source_freeze_sha256':r['freeze_sha256'],'report':{'path':str(path),'sha256':sha(path)},
      'cases':6,'actual_new_disk_CP_head_full_checkpoint_proofs':9,'cleanup_receipt':{'path':str(receipt),'sha256':sha(receipt)},
      'peer_tools':{str(p):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
      'native_owned_empty_data':'Original DB skills/spData null; same _combat/_attack RangedAttack path; native EmptyAbility has no selector/clock/SP. Owned lifecycle data is actually consumed by EP packet and missing/mismatched source is rejected. The name is not a proof of an empty skill.',
      'selector_boundary':'All native fields preserved; current reference eligibility covers side, air/category masks and statuses. postFilter4/priority/client/native method bodies are not proved equivalent.',
      'scope':'Selected source body and bounded cast/finite chain/death descendant only; stage composerV2 and new elemental lease core require subsequent independent integration.',
      'CoreRestoreGap_on_parent_not_promoted':True,'whole_stage_approval':False,'formal_approval':False,'client_verified':False,
      'primary_modified':False,'candidate_modified':False,'raw_checkpoint_reusable':False}
    (OUT/'freeze.peer.v1.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'groups':6,'new_disk_full_proofs':9,'freeze_sha256':sha(OUT/'freeze.peer.v1.json')}))
if __name__=='__main__':main()
