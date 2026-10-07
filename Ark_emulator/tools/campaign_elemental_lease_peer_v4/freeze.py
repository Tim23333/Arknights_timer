"""Freeze executed peer gate and byte-preserve three ignored candidate deltas."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/campaign_elemental_lease_peer_v4';HERE=Path(__file__).parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    path=OUT/'result.v1.json';result=json.loads(path.read_bytes());freeze=ROOT/result['freeze_path'];lock=json.loads(freeze.read_bytes())
    assert result['passed'] and result['source_unchanged'] and result['core']==lock['core']
    assert len(result['cases'])==7 and all(r['passed'] for r in result['cases'])
    assert len(result['facts']['hostile'])==28 and all(r['actual_rejected'] for r in result['facts']['hostile'])
    assert len(result['actual_CP_head_proofs'])==5 and all(r['disk_CP_equal'] and r['head_equal'] and r['full_checkpoint_equal'] for r in result['actual_CP_head_proofs'])
    assert all(sha(p)==h for p,h in result['source_guards'].items())
    receipt=Path('E:/ArkSimLogs/receipts/elemental_lease_peer_v4_20261007_b/completion.json');closed=json.loads(receipt.read_bytes())
    assert closed['worker_exit']==closed['cleanup_exit']==0 and closed['raw_logs_removed_after_validation']
    snapshots=[];candidate=Path(lock['candidate'])
    assert len(lock['source_delta'])==3
    for row in lock['source_delta']:
        source=candidate/row['file'];target=HERE/'source_delta.v4'/row['file'];assert sha(source)==row['current']
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==source.read_bytes()
        else:target.write_bytes(source.read_bytes())
        snapshots.append({'runtime_relative_path':row['file'],'snapshot_relative_path':target.relative_to(ROOT).as_posix(),
          'sha256':sha(target),'bytes':target.stat().st_size,'parent_sha256':row['parent']})
    delta={'schema':'ark-sim/elemental-lease-trackable-source-delta/v4','core':result['core'],'parent_core':lock['parent_core'],
      'author_functional_freeze':{'relative_path':freeze.relative_to(ROOT).as_posix(),'sha256':sha(freeze)},
      'actual_source_byte_snapshots':snapshots,'source_inventory':lock['source_inventory'],
      'overlay_policy':'Overlay these exact three files only onto a separately verified parent9a copy. Does not modify production; no claim that the old joint builder alone reconstructs every parent9a correction.',
      'primary_modified':False}
    (OUT/'source.delta.snapshot.v4.json').write_text(json.dumps(delta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    resultfreeze={'schema':'ark-sim/elemental-lease-independent-freeze/v4','core':result['core'],'parent_core':lock['parent_core'],
      'bounded_restore_and_source_business_peer_passed':True,'case_count':7,'hostile_actual_rejections':28,'actual_fresh_full_CP_head_proofs':5,
      'report':{'relative_path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)},
      'author_functional_freeze':{'relative_path':freeze.relative_to(ROOT).as_posix(),'sha256':sha(freeze)},
      'trackable_delta_snapshot':{'relative_path':(OUT/'source.delta.snapshot.v4.json').relative_to(ROOT).as_posix(),'sha256':sha(OUT/'source.delta.snapshot.v4.json')},
      'cleanup_receipt':{'path':str(receipt),'sha256':sha(receipt),'worker_exit':0,'cleanup_exit':0,'raw_remaining':0},
      'peer_tools':{p.relative_to(ROOT).as_posix():sha(p) for p in HERE.glob('*.py')},
      'parent_six_actual_accept_counter_preserved':'validation/campaign/campaign_elemental_receiver_peer_v1/result.v1.json',
      'scope':'Generic arbitrary element state/lease proof and current fixed ally FIRE/DARK consumer on exact core94; legitimate restore is pure, direct data carries no callback authority, and actual owned outer fault rolls five stores back.',
      'full_regression_complete':False,'whole_stage_approval':False,'formal_promotion':False,'client_body_accuracy_verified':False,'primary_modified':False}
    dest=OUT/'freeze.peer.v4.json';dest.write_text(json.dumps(resultfreeze,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'groups':7,'negative_fields':28,'fresh_full_proofs':5,'trackable_delta_count':3,'freeze_sha256':sha(dest)}))
if __name__=='__main__':main()
