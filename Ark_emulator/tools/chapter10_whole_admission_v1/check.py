"""Fail-closed admission for new 10-16 whole runs; never grants completion."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = '94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63'
FREEZE_SHA = 'ac5bfd93be310a597d0aa71cde58a6e5acd3e270f9705f8a325ce51e439137a9'
PACKAGE_SHA = '4bafdfe7e903d42b1253c1b05b878c3938d567231db254714a99f9372a86d8b5'
COMMANDS_SHA = '48f13bd69454edd38496227d2b421f568bce1395f99ee80fd445d1f3a2192a91'
SOURCE_REVIEW_SHA = '3e8c1ed0c650718c99b7b861ac79a9cbb3704bb64c5059addad45ad378600fca'
PARENT_FULL_SHA = '13dbdfbb16f875851dc3ceded43b1fd05d1898db62fa4fb4b34a77bf5a61b74c'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guards(values):
    return bool(values) and all(Path(p).is_file() and sha(p) == expected for p, expected in values.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve prior admission identities')
    runtime = args.runtime_root.resolve()
    sys.path.insert(0, str(runtime));sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim'
    assert implementation_digest() == CORE
    names = {
        'freeze': 'campaign_elemental_lease_v4/freeze.functional.v4.json',
        'peer': 'campaign_elemental_lease_peer_v4/result.v1.json',
        'source': 'chapter10_stage_assembly_peer_v2/source.review.v1.json',
        'full': 'chapter10_stage_assembly_v2/full.94d2.v1.json',
        'baseline': 'chapter10_stage_assembly_v2/baseline.94d2.v2.json',
        'prefix': 'chapter10_stage_assembly_v2/public.prefix601.94d2.v3.json',
    }
    checks, pins, data = {}, {}, {}
    for name, relative in names.items():
        path = ROOT / 'validation/campaign' / relative
        if not path.exists():
            checks[name] = {'passed': False, 'reason': 'Completed report not available'}
            continue
        data[name] = json.loads(path.read_bytes())
        pins[name] = {'path': str(path), 'sha256': sha(path)}
    if 'freeze' in data:
        d = data['freeze']
        checks['freeze'] = {'passed': pins['freeze']['sha256'] == FREEZE_SHA and d['core'] == CORE
                             and guards({str(runtime / p): value for p, value in d['source_inventory'].items()})}
    if 'peer' in data:
        d = data['peer']
        checks['peer'] = {'passed': d['passed'] and d['core'] == CORE and d['freeze_sha256'] == FREEZE_SHA
                           and d['source_unchanged'] and guards(d['source_guards'])
                           and len(d['cases']) == 7 and all(c['passed'] for c in d['cases'])
                           and len(d['facts']['hostile']) == 28
                           and all(c['actual_rejected'] for c in d['facts']['hostile'])}
    if 'source' in data:
        d = data['source']
        reviewed_package = str(ROOT / 'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v3.life99999.json')
        checks['source'] = {'passed': pins['source']['sha256'] == SOURCE_REVIEW_SHA
                             and d['source_input_approved'] and d['actual_compile']
                             and d['actual_core'] == CORE and d['source_equal']
                             and d['source_before'].get(reviewed_package) == 'afe76e816d71cfeb8fad44dc31ad5168705c0f67940608051758e4991ef346e9'
                             and d['source_before'] == d['source_after'] and guards(d['source_before'])}
    if 'full' in data:
        d = data['full']
        parent_path = ROOT / 'validation/campaign/chapter10_joint_v1/full.108.v1.json'
        assert sha(parent_path) == PARENT_FULL_SHA
        parent = json.loads(parent_path.read_bytes())
        expected_cases = {c['case'] for c in parent['cases']}
        modules = d['actual_modules']
        inventory = data.get('freeze', {}).get('source_inventory', {})
        checks['full'] = {'passed': d['passed'] and d['core'] == CORE and d['exitcode'] == 0
                           and d['identity_stable'] and len(d['cases']) == 1219 and not d['collection_skips']
                           and len(expected_cases) == 1219 and {c['case'] for c in d['cases']} == expected_cases
                           and all(c['outcome'] == 'passed' for c in d['cases'])
                           and d['guards_start'] == d['guards_end'] and guards(d['guards_end'])
                           and bool(modules) and Path(modules.get('ark_sim', '')).resolve() == runtime / 'ark_sim/__init__.py'
                           and all(Path(p).is_relative_to(runtime / 'ark_sim')
                                   and Path(p).relative_to(runtime).as_posix() in inventory for p in modules.values())}
    if 'baseline' in data:
        d = data['baseline'];level = d.get('level_00_01', {})
        checks['baseline'] = {'passed': d['passed'] and d['actual_exit'] == 0 and d['core'] == CORE
                               and d['identity_stable'] and guards(d['source_after'])
                               and level.get('checkpoint_resume_equal') and level.get('replay_equal')
                               and {k: r['damage'] for k, r in d['custom_rulesets'].items()}
                               == {'ruleset/ark_standard': 850, 'ruleset/custom_balance': 60}}
    if 'prefix' in data:
        d = data['prefix']
        checks['prefix'] = {'passed': d['passed'] and d['actual_exit'] == 0 and d['core'] == CORE
                             and d['full_CP_head_equal'] and d['source_guard_equal']
                             and d['actual_module_paths_equal'] and guards(d['source_after'])
                             and d['package_sha256'] == 'afe76e816d71cfeb8fad44dc31ad5168705c0f67940608051758e4991ef346e9'
                             and d['commands_sha256'] == COMMANDS_SHA}
    package = ROOT / 'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v3.life99999.finite_v1.json'
    commands = ROOT / 'scenarios/campaign/chapter10/level_main_10-14/public_plan_v1_finite/commands.json'
    p = json.loads(package.read_bytes())
    original = json.loads((ROOT / 'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v3.life99999.json').read_bytes())
    projected = json.loads(package.read_bytes())
    del projected['scenarioDraft']['metadata']['runthrough_profile']
    # Canonical JSON equality retains scalar type distinctions such as1/1.0.
    exact_overlay = json.dumps(projected, sort_keys=True, allow_nan=False) == json.dumps(original, sort_keys=True, allow_nan=False)
    checks['whole_inputs'] = {'passed': sha(package) == PACKAGE_SHA and sha(commands) == COMMANDS_SHA
                               and exact_overlay
                               and p['manifest']['metadata']['required_runtime'] == CORE
                               and guards(p['manifest']['metadata']['source_locks'])}
    record = {'schema': 'ark-sim/chapter10-whole-admission/v1', 'core': CORE,
              'admitted': all(v['passed'] for v in checks.values()), 'checks': checks, 'reports': pins,
              'package': str(package), 'package_sha256': sha(package),
              'commands': str(commands), 'commands_sha256': sha(commands),
              'scope': 'New source-reference whole run permitted only after completed gates',
              'evidence_boundary': 'Trusted local execution receipts; hashes bind their saved identities, not arbitrary self-declared JSON or client accuracy',
              'whole_run_started': False, 'whole_stage_passed': False, 'client_verified': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps({'admitted': record['admitted'], 'checks': checks}))
    return 0 if record['admitted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
