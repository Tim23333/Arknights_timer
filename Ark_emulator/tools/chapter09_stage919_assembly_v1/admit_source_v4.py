"""Only actual current-content proofs admit the pinned finale run."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def current_guards(report,key):
    assert all(Path(p).exists() and sha(p)==h for p,h in report[key].items())


def main():
    accepted=[]
    for name in ['chapter09_finale_full_v1/full.108.json','chapter09_finale_full_v1/baseline/verification.identity.json',
                 'chapter09_stage919_assembly/input.source.v3.json','chapter09_stage919_assembly/public.source.v3.json',
                 'chapter09_stage919_assembly/roster.immunity.owned.v3.json']:
        p=ROOT/'validation/campaign'/name;d=json.loads(p.read_bytes());assert d['passed'] is True
        for key in ('guards_end','source_at_completion','source_guard_end'):
            if key in d:current_guards(d,key)
        accepted.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
    content=ROOT/'validation/campaign/chapter09_mandra_v2/freeze.source.v2.json';d=json.loads(content.read_bytes());assert d['runtime_delta_files']==0 and d['source_before']==d['source_after']
    assert all(sha(Path(d['runtime'])/p)==h for p,h in d['source_after'].items())
    assert all(sha(ROOT/r['path'])==r['sha256'] for r in d['modules'])
    peer=ROOT/'validation/campaign/chapter09_mandra_peer_v2/peer.final.v2.json';d=json.loads(peer.read_bytes());assert d['passed']==4 and d['failed']==0 and d['source_before_end_and_current_equal'] is True
    wave=ROOT/'validation/campaign/chapter09_stage919_wave_v4/author.wave.final.v4.json';d=json.loads(wave.read_bytes());assert d['actual_exit']==0 and d['source_equal'];current_guards(d,'source_after')
    independent=ROOT/'validation/campaign/chapter09_wave_peer_v4/actual.correct.v4.json';d=json.loads(independent.read_bytes());assert d['actual_exit']==0 and d['source_guard_equal'];current_guards(d,'source_after')
    patch=ROOT/'validation/campaign/chapter09_stage919_wave_v4/patch.v4.json';d=json.loads(patch.read_bytes());p=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v4.life99999.json';assert sha(p)==d['output_sha256'] and d['only_selected_hook_diff'] is True
    # V3 actual public input proof stays V3; only the source-owned finish hook
    # differs in V4. No old proof is relabelled as a V4 whole run.
    a=json.loads(p.read_bytes());b=json.loads((ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v3.life99999.json').read_bytes());next(x for x in a['definitions'] if x['id']=='unit/ch9/mandra/body')['components']['rebirth']['on_finish'].pop();assert a==b
    out=ROOT/'validation/campaign/chapter09_stage919_assembly/admission.source.v4.json';assert not out.exists();out.write_text(json.dumps({'ready_to_execute':True,'actual_core':'cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18','actual_proofs':accepted,'mandra_source_freeze_sha':sha(content),'mandra_independent_sha':sha(peer),'wave_author_sha':sha(wave),'wave_independent_sha':sha(independent),'source_patch_sha':sha(patch),'only_source_wave_finish_hook_changes_prior_public_input':True,'old_V3_proof_not_relabelled_V4':True,'whole_stage_passed':False,'client_verified':False},indent=2)+'\n',encoding='utf8');print(json.dumps({'ready_to_execute':True}))


if __name__=='__main__':main()
