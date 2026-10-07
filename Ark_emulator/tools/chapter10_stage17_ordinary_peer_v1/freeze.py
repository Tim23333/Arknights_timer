"""Freeze separate parent9a and successor94 source3 peer evidence."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter10_stage17_ordinary_peer_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    paths=[OUT/name for name in ('result.9a.v1.json','result.94.v1.json','death.94.v1.json')]
    reports=[json.loads(p.read_bytes()) for p in paths]
    assert reports[0]['core']=='9a7d4a01b7fe0a8d77a39e4b280b330e65670349b6fb2716c1319dabcc491ed9'
    assert reports[1]['core']==reports[2]['core']=='94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63'
    assert all(r['passed'] and r['source_unchanged'] for r in reports)
    assert all(all(sha(p)==h for p,h in r['source_guards'].items()) for r in reports)
    proofs=[p for r in reports for p in r['actual_CP_head_proofs']];assert len(proofs)==27
    assert all(p['disk_CP_equal'] and p['head_equal'] and p['full_checkpoint_equal'] for p in proofs)
    runs=['ordinary_source3_peer_9a_20261007_b','ordinary_source3_peer_94_20261007_a','ordinary_source3_peer_death94_20261007_a'];receipts={}
    for name in runs:
        base=Path('E:/ArkSimLogs/receipts')/name
        for filename in ('completion.json','cleanup.result.json'):
            p=base/filename;local=OUT/(name+'.'+filename);local.write_bytes(p.read_bytes());receipts[local.relative_to(ROOT).as_posix()]=sha(local)
        r=json.loads((base/'completion.json').read_bytes());assert r['worker_exit']==r['cleanup_exit']==0 and r['raw_logs_removed_after_validation']
    r={'schema':'ark-sim/source3-independent-peer-freeze/v1','bounded_source3_passed':True,
      'source_freeze_sha256':reports[0]['source_freeze_sha256'],'source_old_identity_not_migrated':True,
      'separate_parent9a_cases':5,'separate_successor94_cases':5,'successor94_base_lord_death_case':1,'actual_new_full_CP_head_proofs':27,
      'reports':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},'cleanup_receipts':receipts,
      'peer_tools':{p.relative_to(ROOT).as_posix():sha(p) for p in Path(__file__).parent.glob('*.py')},
      'scope':'Selected darmy/slime/base lord source reference consumers only. Vampire actual-primary-health output reference is explicit; barrier/flag5 zero-reception projection does not recover native invulnerability or output-event methods. No dmech channel body or target-stage completion claimed.',
      'dmech_runtime_approved':False,'whole_stage_complete':False,'client_verified':False,'primary_modified_by_peer':False}
    path=OUT/'freeze.peer.v1.json';path.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'proofs':27,'freeze_sha256':sha(path)}))
if __name__=='__main__':main()
