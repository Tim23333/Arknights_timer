"""Freeze compact executed business scope while retaining the real restore gap."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/campaign_elemental_receiver_peer_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    paths=[OUT/name for name in ('result.v1.json','extra.v1.json','flags.v1.json')]
    reports=[json.loads(p.read_bytes()) for p in paths]
    rows=[row for r in reports for row in r['cases']]
    assert all(row['passed'] for row in rows)
    assert reports[0]['primary_unchanged'] and reports[0]['source_unchanged'] and reports[1]['primary_unchanged']
    assert all(sha(p)==h for p,h in reports[0]['source_hashes'].items())
    proofs=[proof for r in reports for proof in r['actual_CP_head_proofs']]
    assert all(p['disk_CP_equal'] and p['head_equal'] for p in proofs)
    accepted=[r['field'] for r in reports[0]['facts']['single_field_in_memory_restore'] if not r['rejected']]
    receipts=[Path('E:/ArkSimLogs/receipts')/name/'completion.json' for name in
      ('elemental_receiver_peer_20261007_b','elemental_receiver_peer_20261007_extra_b','elemental_receiver_peer_20261007_flags_a')]
    for p in receipts:
        r=json.loads(p.read_bytes());assert r['worker_exit']==0 and r['cleanup_exit']==0 and r['raw_logs_removed_after_validation']
    data={'schema':'ark-sim/elemental-receiver-peer-business-scope/v1',
      'bounded_content_numbers_passed':True,'case_count':len(rows),'actual_fresh_CP_head_proof_count':len(proofs),
      'source_hashes':reports[0]['source_hashes'],'implementation':reports[0]['implementation'],
      'reports':{str(p):sha(p) for p in paths},'cleanup_receipts':{str(p):sha(p) for p in receipts},
      'CoreRestoreGap':{'retained':bool(accepted),'actual_in_memory_single_field_acceptance':accepted,
        'disk_original_hash_byte_tamper_rejected':reports[0]['facts']['disk_byte_tamper_rejected'],
        'scope':'Actual Engine.restore trusted dictionary gap; disk binding does not establish owned elemental lineage'},
      'whole_stage_approval':False,'formal_approval':False,'client_body_accuracy_verified':False,
      'scope':'Actual fixed roster ally FIRE/DARK numeric content; all15 health/SP/owned ability fields preserved, three summon public requests, live status projection, original skill/SP freeze and actual 70s redeploy. Generic restore hardening must be reverified against a separate frozen candidate.',
      'references':{'fixed_element_defaults':'https://prts.wiki/index.php?title=元素&oldid=430495',
        'formula_live_support':'https://prts.wiki/w/游戏数据基础',
        'raw_formula':'source.bson.v2: FIRE MAGIC_RESISTANCE ADDITION; fixed roster Night S3 mres direct_ratio1.5'},
      'source_policy':'Pinned oldid inaccessible via web during review; live formula support does not claim a method body or substitute for native BSON bytes.',
      'peer_tools':{str(p):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}}
    (OUT/'business.scope.v1.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'bounded_content_numbers_passed':True,'cases':len(rows),'fresh_proofs':len(proofs),'CoreRestoreGap':accepted}))
if __name__=='__main__':main()
