"""Read-only publish audit of completed candidate proofs, never promotion."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/publication_snapshot_audit_v1';OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def pins(mapping):
    assert all(sha(k)==h for k,h in mapping.items())
def main():
    parent=read(ROOT/'validation/campaign/campaign_owned_channel_phase_full_v2/full.da218.v1.json');reference={c['case'] for c in parent['cases']};assert len(reference)==1219;rows=[]
    configs=[('phase_da','campaign_owned_channel_phase_v2/freeze.functional.v2.json','campaign_owned_channel_phase_full_v2','da218','channel_phase_da'),
      ('lookup12','campaign_death_event_lookup_v1/candidate.v1.json','campaign_death_event_lookup_full_v1','12e1','death_lookup12'),
      ('callbacks737','campaign_owned_interrupt_callbacks_v1/freeze.functional.v1.json','campaign_owned_interrupt_callbacks_full_v1','737e','interrupt_callback737')]
    for name,manifest,folder,tag,run_prefix in configs:
        mp=ROOT/'validation/campaign'/manifest;m=read(mp);candidate=Path(m['candidate']);inventory=m['inventory'];pins({str(candidate/k):h for k,h in inventory.items()});proofs={};actual_core=None
        for kind in ('full','baseline'):
            path=ROOT/'validation/campaign'/folder/(kind+'.'+tag+'.v1.json');r=read(path);assert r['passed'] is True and r['identity_stable'] is True;actual_core=r['core']
            if kind=='full':
                assert r['exitcode']==0 and len(r['cases'])==1219 and len({c['case'] for c in r['cases']})==1219 and {c['case'] for c in r['cases']}==reference and all(c['outcome']=='passed' for c in r['cases']) and r['collection_skips']==[]
                assert r['guards_start']==r['guards_end'];pins(r['guards_end'])
            else:
                assert r['actual_exit']==0 and r['source_before']==r['source_after'] and r['core_at_completion']==r['core'];pins(r['source_after'])
            assert all(Path(p).resolve().is_relative_to(candidate.resolve()) for p in r['actual_modules'].values());assert all(sha(p)==inventory[Path(p).relative_to(candidate).as_posix()] for p in r['actual_modules'].values())
            run=run_prefix+('_full1219_20261007_v1' if kind=='full' else '_baseline_20261007_v1');receipt=Path('E:/ArkSimLogs/receipts')/run/'completion.json';done=read(receipt)
            assert done['worker_exit']==done['cleanup_exit']==0 and done['raw_logs_removed_after_validation'] and done['cleanup_result']['fully_cleaned'] and done['cleanup_result']['remaining_files']==0
            saved=OUT/'receipts'/(run+'.completion.json');saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(receipt.read_bytes());proofs[kind]={'path':str(path),'sha256':sha(path),'receipt_sha256':sha(saved),'actual_worker_exit':0,'cleanup_exit':0,'raw_removed':True,'actual_modules':len(r['actual_modules'])}
        snapshots={}
        if name=='callbacks737':
            for delta in m['delta']:
                p=ROOT/'tools/campaign_owned_interrupt_callbacks_v1/source_delta'/delta['path'];assert sha(p)==delta['current_sha256']==inventory[delta['path']];snapshots[str(p)]=sha(p)
            assert actual_core==m['core']
        rows.append({'candidate':name,'core':actual_core,'inventory_count':len(inventory),'inventory_current_equal':True,'manifest_sha256':sha(mp),'proofs':proofs,'tracked_delta_snapshots':snapshots,'full_unique1219_parent_case_set_equal_no_skips':True,'promoted':False,'whole_stage':False})
    dmech=read(ROOT/'validation/campaign/chapter10_dmech_source_v1/freeze.source.v1.json');pins(dmech['locks']);assert sha(dmech['module'])==dmech['module_sha256'] and sha(dmech['report'])==dmech['report_sha256'] and dmech['actual_exit']==0
    peer=read(ROOT/'validation/campaign/campaign_owned_dead_callback_peer_v1/final.freeze.v1.json');pins(peer['files']);assert peer['actual_exit']==0 and peer['all_current_source_guards_equal'] is True and sha(peer['actual_report'])==peer['actual_report_sha256']
    lookup=read(ROOT/'validation/campaign/campaign_death_event_lookup_root_peer_v1/freeze.root.v1.json')
    for ref in lookup['proofs'].values():assert sha(ref['path'])==ref['sha256']
    result={'schema':'ark-sim/completed-publish-snapshot-audit/v1','passed':True,'candidates':rows,'dmech_current_frozen_source_and_actual_report_equal':True,'callbacks_independent_peer_current_equal':True,'lookup_root_independent_and_native_birth_current_equal':True,'reviewer_sha256':sha(Path(__file__)),'primary_modified':False,'promotion_authorized_or_performed':False,'whole_stage_or_live_run_result_claim':False}
    path=OUT/'completed.review.v1.json';path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'report_sha256':sha(path),'737_actual_full_now_complete':True}))
if __name__=='__main__':main()
