"""Copy the reviewed M12 bytes into the primary runtime and retain old identities."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OLD = 'c0b92545a714e763f3e43d4e13d25f0be99ecda912cb8479536982ac38f8216e'
NEW = 'bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    sys.path.insert(0, str(ROOT))
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest() == OLD, 'Primary changed before promotion'
    source = ROOT.parent / 'unpack_work/campaign_m12_projection_candidate/ark_sim'
    target = ROOT / 'ark_sim'
    backup = ROOT.parent / 'unpack_work/campaign_primary_history' / OLD
    files = sorted(source.rglob('*.py')) + [source/'rules/contracts.json', source/'content/presets/ark_standard.json']
    payloads = [(p.relative_to(source), p.read_bytes()) for p in files]
    existing = {p.relative_to(target) for p in target.rglob('*.py')}
    assert existing == {rel for rel, _ in payloads if rel.suffix == '.py'}
    history = {}
    for rel, data in payloads:
        old = (target/rel).read_bytes()
        saved = backup/rel
        if saved.exists():
            assert saved.read_bytes() == old, f'Backup mismatch: {rel}'
        else:
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(old)
        history[rel.as_posix()] = {'old_sha256': sha(old), 'new_sha256': sha(data)}
    test = ROOT/'tests_v2/test_activation_control_review.py'
    saved = backup/'tests_v2/test_activation_control_review.py'
    saved.parent.mkdir(parents=True, exist_ok=True)
    if saved.exists():
        assert saved.read_bytes() == test.read_bytes()
    else:
        saved.write_bytes(test.read_bytes())
    reviewed_test = (ROOT/'tools/experiments/m12_integrated/test_activation_control_review.py').read_bytes()
    assert reviewed_test.count(b'parents[3]') == 1
    revised_test = reviewed_test.replace(b'parents[3]', b'parents[1]')
    for rel, data in payloads:
        (target/rel).write_bytes(data)
    test.write_bytes(revised_test)
    assert implementation_digest() == NEW, 'Copied runtime does not match reviewed candidate'
    record = {'schema': 'ark-sim/primary-promotion-record/v1',
        'old_implementation': OLD, 'new_implementation': NEW,
        'source_candidate': str(source), 'backup': str(backup), 'files': history,
        'test_fixture': {'path': str(test), 'old_sha256': sha(saved.read_bytes()),
            'new_sha256': sha(revised_test), 'reason': 'Separate single-blocker release from legitimate second-blocker transfer'},
        'candidate_full_suite': '1261 passed, 1 stale two-blocker fixture failed',
        'corrected_fixture_suite': '16 passed',
        'independent_reviews': ['m11_block_sync_independent_review.json', 'm12_projection_independent_review.json',
            'm12_block_transfer_fixture_independent_review.json'],
        'runtime_reverification_pending': True, 'formal_stage_approved': False}
    output = ROOT/'validation/campaign/m12_primary_promotion_20261002.json'
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'implementation': NEW, 'files_copied': len(files), 'record': str(output)}))


if __name__ == '__main__':
    main()
