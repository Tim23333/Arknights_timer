"""Current canonical input inventory; verified witnesses never imply approval."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json')
    parser.add_argument('--output', type=Path, default=ROOT/'validation/campaign/current_campaign_input_audit_20261002.json')
    args = parser.parse_args()
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    data = json.loads(args.package.read_bytes()); program = Compiler().compile(data)
    normalized = json.loads((ROOT/'packages/campaign/operators.normalized.json').read_bytes())
    operators = {row['character_id']: row for row in normalized['operators']}
    rows = []
    for ref in program.scenario['roster']:
        unit = program.definitions[ref]; meta = unit['metadata']; native = operators[meta['native_id']]
        ability_id = meta['selected_skill_ability']; ability = program.definitions[ability_id]
        rows.append({'native_id': meta['native_id'], 'config_equal': dict(meta['config']) == native['config'],
            'skill_id_equal': ability['metadata'].get('native_skill_id') == native['selected_skill']['skill_id'],
            'ability_owned': ability_id in unit['components']['abilities'], 'selected_ability': ability_id})
    witnesses = []
    for name in ('canonical_trio_witness.m8_roster.json', 'canonical_lisk_defense.m8_roster.json'):
        path = ROOT/'validation/campaign'/name
        if path.exists():
            value = json.loads(path.read_bytes())
            tests = value.get('tests', [])
            current = value.get('implementation_sha256') == implementation_digest() and all(
                (ROOT/test['path']).is_file() and sha(ROOT/test['path']) == test['source_sha256'] for test in tests)
            witnesses.append({'path': path.relative_to(ROOT).as_posix(), 'artifact_sha256': sha(path),
                'passed': value.get('passed'), 'source_and_implementation_current': current,
                'input_package_matches_current': value.get('input_package_sha256') == sha(args.package),
                'execution_identity_stable': value.get('identity_stable'),
                'test_source_count': len(tests), 'scope_is_mechanisms_only': True})
    result = {'schema': 'ark-sim/current-canonical-input-audit/v1', 'package': str(args.package),
        'package_sha256': sha(args.package), 'program_fingerprint': program.fingerprint,
        'implementation_sha256': implementation_digest(), 'roster': rows,
        'config_skill_ownership_passed': len(rows) == 12 and all(r['config_equal'] and r['skill_id_equal'] and r['ability_owned'] for r in rows),
        'mechanism_witness_artifacts': witnesses,
        'remaining_execution_gaps': ['Chen selected ability recovery policy', 'Kalts resource-gate interrupt scope',
            'Kalts/Night/Weedy canonical lifecycle closure', 'new input full stage checkpoint/replay and independent review'],
        'formal_stage_approved': False, 'review_receipt_issued': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'fixed_roster_count': len(rows), 'config_skill_ownership_passed': result['config_skill_ownership_passed'],
        'mechanism_witness_artifacts': len(witnesses), 'formal_stage_approved': False}))


if __name__ == '__main__':
    main()
