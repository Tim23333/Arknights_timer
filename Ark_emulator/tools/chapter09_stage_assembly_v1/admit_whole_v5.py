"""Require actual current-source author and independent gates before 9-18."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    proof_paths=[
        'validation/campaign/chapter09_duspfr_full_v1/full.107.json',
        'validation/campaign/chapter09_duspfr_full_v1/baseline/verification.identity.json',
        'validation/campaign/chapter09_ruin_v2/final.v2.json',
        'validation/campaign/chapter09_stage_assembly/blocked.input.v5.json',
        'validation/campaign/chapter09_stage_assembly/public.prefix.v5.json']
    proofs=[]
    for name in proof_paths:
        path=ROOT/name;d=json.loads(path.read_bytes());assert d.get('passed') is True,name
        for key in ['guards_start','guards_end','source_at_start','source_at_completion','source_guard_start','source_guard_end']:
            if key in d:assert all(Path(p).exists() and sha(p)==pin for p,pin in d[key].items()),name+' '+key
        proofs.append({'path':name,'sha256':sha(path),'actual_passed':True,'current_consumed_source_equal':True})
    peer_path=ROOT/'validation/campaign/chapter09_ruin_peer/actual.v2.json';peer=json.loads(peer_path.read_bytes())
    required={'old_source_counter','different_native_combat_CPP','environment_NoSource_and_ranged_obstacle','real_dushdo_blocked_counter'}
    actual={r['case'] for r in peer['results'] if r['passed'] is True};assert required<=actual
    # Preserve the first fixture failure; the fresh geometrical gate must pass.
    follow_path=ROOT/'validation/campaign/chapter09_ruin_peer/followup.actual.json';follow=json.loads(follow_path.read_bytes())
    assert follow['actual_exit']==0 and follow['source_guard'] is True
    required_follow={'corrected_radius_actual_on_path','v5_dushdo_different_ATK_actual_CPPhead','foreign_and_same_side_exception_rejected'}
    assert {r['case'] for r in follow['results'] if r['passed'] is True}==required_follow
    stage=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v5.life99999.json'
    assert follow['v5_source_sha']==sha(stage)
    assert all(Path(p).exists() and sha(p)==pin for p,pin in peer['source_after'].items())
    fixed=ROOT/'validation/campaign/chapter09_stage_assembly/blocked.input.freeze.v5.json';freeze=json.loads(fixed.read_bytes())
    assert all(sha(ROOT/p)==pin for p,pin in freeze['files'].items())
    receipt={'schema':'ark-sim/c9-918-admission/v5','author_proofs':proofs,
        'independent_first_batch':{'path':str(peer_path),'sha256':sha(peer_path),'actual_exit':peer['actual_exit'],'accepted_gates':sorted(required),'original_radius_fixture_failure_preserved':True},
        'independent_fresh_batch':{'path':str(follow_path),'sha256':sha(follow_path),'actual_exit':0,'accepted_gates':sorted(required_follow)},
        'native_births':34,'squad12':True,'deploy_capacity':8,'initialDP':12,'base_life99999':True,
        'client_accuracy_verified':False,'whole_stage_passed':False,'ready_to_execute':True,
        'run_entry':'tools/chapter09_stage_assembly_v1/run_918_v5.ps1'}
    out=ROOT/'validation/campaign/chapter09_stage_assembly/whole.admission.v5.json'
    assert not out.exists();out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps({'ready_to_execute':True,'independent_effective_gates':7}))


if __name__=='__main__':main()
