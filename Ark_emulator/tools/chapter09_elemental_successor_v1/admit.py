"""Exact evidence-bound chapter9 successor admission, without launching runs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = '94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def current(values):
    return bool(values) and all(Path(path).exists() and sha(path) == value for path, value in values.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    guards = {}
    def read(relative, pin=None):
        path = ROOT / relative
        actual = sha(path)
        if pin is not None and actual != pin:
            raise ValueError('Pinned evidence drift: ' + relative)
        guards[str(path)] = actual
        return json.loads(path.read_bytes())
    kernel = read('validation/campaign/chapter10_stage_assembly_v2/whole.admission94d2.v1.json',
                  '53e57d7f06c193526da0c65221ff06e0a6282a3d072b347de99eefee8c564ac7')
    assert kernel['admitted'] and kernel['core'] == CORE
    for proof in kernel['reports'].values():
        assert sha(proof['path']) == proof['sha256']
    review = read('validation/campaign/chapter09_elemental_successor_peer_v1/source.review.v1.json',
                  '3a9672927162d6e8888e38f0e0a3acee5ce308770e0c28af4a4607643502b114')
    assert review['source_input_approved'] and review['source_equal'] and current(review['source_after'])
    fire = read('validation/campaign/chapter09_elemental_successor_peer_v1/native.fire.freeze.v1.json',
                'dccb35a05ac4f81b7d01aef6d10fde8ae74e020eba26236273c9a7395567369c')
    assert fire['core'] == CORE and current(fire['current_source_guards'])
    actual = read('validation/campaign/chapter09_elemental_successor_peer_v1/native.fire.actual.v2.json',
                  'f2befe02283ba4ae432f22a191b7df4ec1942d34fc9b9f87abaf017eac04aeab')
    assert actual['actual_exit'] == 0 and actual['core'] == CORE and actual['source_equal']
    assert len(actual['results']) == 3 and all(r['passed'] for r in actual['results'])
    rows = []
    for stage, key, pin, original in [
        ('09-16', '918', '999c9ab461c0fc86d121eaa3a3e4dc29a69dc0631656b81d75523b00d2eebb93',
         'validation/campaign/chapter09_stage_assembly/whole.admission.v6.json'),
        ('09-17', '919', '05963200ef9667b451c8629bcc850bf4a5e1bf406e37dc41abbd3d6c015da99b',
         'validation/campaign/chapter09_stage919_assembly/admission.source.v4.json')]:
        package_path = f'packages/campaign/chapter09_stage_models/level_main_{stage}.elemental_successor.v1.life99999.finite_run_v1.json'
        package = read(package_path, pin)
        metadata = package['manifest']['metadata'];binding = metadata['elemental_successor_binding']
        assert metadata['required_runtime'] == CORE and current(metadata['source_locks']) and current(binding['source_locks'])
        prefix = read(f'validation/campaign/chapter09_elemental_successor_v1/public.prefix{key}.v1.json')
        assert prefix['passed'] and prefix['actual_exit'] == 0 and prefix['core'] == CORE
        assert prefix['complete_CP_head_equal'] and prefix['identity_stable'] and current(prefix['source_after'])
        assert prefix['source_before'][str(ROOT / package_path)] == pin
        parent_evidence = read(original)
        # Historical author/peer gates keep their declared runtime identities.
        # New source bytes and new runtime execution are separately proved.
        profile = package['scenarioDraft']['metadata']['runthrough_profile']
        assert profile['base_life'] == 99999 and len(profile['fixed12']) == 12
        rows.append({'native_stage': stage, 'source_package_sha256': pin,
                     'new_prefix_current': True, 'prior_source_mechanism_admission': original,
                     'prior_mechanism_receipt_sha256': guards[str(ROOT / original)],
                     'prior_mechanism_runtime_identity_not_relabelled': True,
                     'native_births': profile['source_births'], 'slots': profile['deploy_capacity'],
                     'FIRE_business_scope': 'Actual nativeFlame/fixedLiskam3 gates' if stage == '09-16'
                     else 'Original package declares no native EP attack; receiver readiness only',
                     'ready_for_new_run': True, 'whole_stage_passed': False})
    result = {'schema': 'ark-sim/chapter9-elemental-successor-admission/v1', 'core': CORE,
              'ready_cases': rows, 'consumed_receipts': guards,
              'launch_policy': 'Queue until existing long-run raw logs are reclaimed; do not start duplicate runs',
              'new_whole_runs_started': False, 'whole_stages_passed': False, 'client_verified': False,
              'scope': 'Trusted local source-reference input and bounded execution admission, not whole completion'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'ready': 2, 'whole_started': False, 'native_births': [r['native_births'] for r in rows]}))


if __name__ == '__main__':
    main()
