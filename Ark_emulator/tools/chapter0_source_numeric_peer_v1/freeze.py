import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OUT=ROOT/'validation/campaign/chapter0_source_numeric_peer_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    first=json.loads((OUT/'actual.v1.json').read_bytes());second=json.loads((OUT/'actual.v2.json').read_bytes());review=json.loads((OUT/'source.inputs.review.v1.json').read_bytes())
    assert first['source_unchanged'] and len(first['cases'])==18 and sum(c['passed'] for c in first['cases'])==10
    assert second['passed'] and second['source_unchanged'] and len(second['cases'])==8 and review['passed']
    assert first['core']==second['core']=='08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'
    assert all(p['four_observations_equal'] and p['full_checkpoint_equal'] for r in (first,second) for p in r['full_disk_CP_head'])
    for v in (1,2):
        pin=Path(f'E:/ArkSimLogs/receipts/chapter0_numeric_peer_20261007_v{v}/completion.json');record=json.loads(pin.read_bytes())
        assert record['cleanup_exit']==0 and record['raw_logs_removed_after_validation'] and record['cleanup_result']['fully_cleaned']
        assert record['worker_exit']==(1 if v==1 else 0);(OUT/f'completion.v{v}.json').write_bytes(pin.read_bytes())
    frozen={'schema':'ark-sim/chapter0-independent-bounded-peer-freeze/v1','core':second['core'],'consumer_scope_passed':True,'native_cases_passed':10,'reference_clock_and_public_target_cases_passed':8,'complete_CP_head_groups':26,
      'history_failure_preserved':True,'animation_speed_native_body_gap':second['animation_speed_source_gap'],'native_broad_immunity_or_selector_timing_claim':False,'whole_stage':False,'client_verified':False,
      'reports':{str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('*.json')},'tools':{str(p.relative_to(ROOT)):sha(p) for p in HERE.glob('*') if p.is_file()},'source_guards':second['source_guards']}
    out=OUT/'freeze.peer.v1.json';out.write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'freeze':str(out),'sha256':sha(out)}))
if __name__=='__main__':main()
