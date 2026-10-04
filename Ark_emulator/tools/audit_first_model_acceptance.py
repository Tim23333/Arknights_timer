"""Read-only typed first-stage scope inventory; never creates approval receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    current = ROOT/'packages/campaign/mainline_models/level_main_00-10.m7.json'
    plan_path = ROOT/'packages/campaign/mainline_dependencies/level_main_00-10.json'
    normalized_path = ROOT/'packages/campaign/operators.normalized.json'
    stage, plan, normalized = load(current), load(plan_path), load(normalized_path)
    from ark_sim import Compiler
    program = Compiler().compile(stage)
    actors = {x['metadata']['native_id']: x for x in stage['entities'] if x.get('metadata', {}).get('native_id', '').startswith('char_')}
    definitions = {x['id']: x for kind in ('entities', 'abilities', 'buffs', 'selectors', 'rules', 'behaviors') for x in stage.get(kind, [])}
    integrations = stage['manifest']['metadata']['squad_model']['integration']
    used_commands = load(ROOT/'validation/campaign/m8_00_10_final_20261002.commands.json')
    deployed = {definitions[x['entity']]['metadata']['native_id'] for x in used_commands if x['action'] == 'deploy'}
    rows = []
    for row in normalized['operators']:
        cid = row['character_id'];actor = actors[cid]
        binding = next(x for x in integrations if x['native_id'] == cid)
        ability = definitions[binding['selected_skill_ability']]
        expected = row['stats']['model_stats'];actual = actor['components']['attributes']['base']
        comparisons = {k: actual[v] == expected[k] for k, v in [('maxHp','max_hp'),('atk','atk'),('def','def'),('magicResistance','mres')]}
        rows.append({'native_id': cid, 'unit_id': actor['id'], 'fixed_config_equal': actor['metadata']['config'] == row['config'],
            'base_stat_checks': comparisons, 'selected_skill_native_id': row['selected_skill']['skill_id'],
            'selected_ability_id': ability['id'], 'ability_owned': ability['id'] in actor['components']['abilities'],
            'gate_native_skill_metadata': ability.get('metadata', {}).get('native_skill_id'),
            'deployment_in_current_stage_script': cid in deployed,
            'actual_abilities': actor['components']['abilities'], 'actual_initial_buffs': actor['components'].get('buffs', {}).get('initial', []),
            'historical_pending_labels': binding['pending'], 'mechanic_acceptance_status': 'independent_final_integration_evidence_required',
            'does_not_promote_from_stage_victory': True})
    routes = [{'native_route_id': key, 'motion_mode': value['motionMode'], 'spawn_random_range': value['spawnRandomRange'],
        'allow_diagonal': value['allowDiagonalMove']} for key, value in plan['used_routes'].items()]
    reports = []
    for path in (ROOT/'validation/campaign').glob('*00_10*.json'):
        if '.package.' in path.name or '.commands.' in path.name:
            continue
        value = load(path)
        reports.append({'path': path.relative_to(ROOT).as_posix(), 'passed': value.get('passed'),
            'formal_stage_accepted': value.get('formal_stage_accepted'), 'package_sha256': value.get('package_sha256'),
            'runtime_fingerprint': value.get('runtime_fingerprint'), 'checkpoint_equal': value.get('checkpoint_equal'),
            'replay_equal': value.get('replay_equal'), 'state': {k: value.get('state', {}).get(k) for k in ('kills','leaks','result','finished','pending_waves')}})
    roster_cases = {'model_source_and_config': 'implemented_current_definitions', 'selected_skills_and_talents': 'math_profiles_present_fresh_binding_witnesses_required',
        'summons': 'three_exact_definitions_present_undeployed_in_stage_need_independent_closed_cases',
        'spawn_diagonal_steering': 'implemented_M7_explicit_math_profile_client_native_alignment_pending',
        'waves_and_controls': 'source_counts_preserved_headless_policy_need_final_consumption_and_conservation_ranges',
        'three_way_final_identity': 'live_not_promoted_before_completed_artifact',
        'campaign_execution_gate': 'typed_gap_audit_and_external_review_contract_not_yet_present'}
    return {'schema': 'ark-sim/first-model-acceptance-scope-audit/v1', 'formal_approval': False, 'scope_targets': 36,
        'fixed_roster_count': 12, 'current_stage': 'level_main_00-10.m7', 'program_fingerprint': program.fingerprint,
        'input_hashes': {p.relative_to(ROOT).as_posix(): sha(p) for p in (current, plan_path, normalized_path,
            ROOT/'tools/build_m7_mainline_model.py', ROOT/'tools/campaign_progress.py')}, 'typed_summary': roster_cases,
        'roster_inventory': rows, 'compiled_roster_count': len(program.scenario['roster']), 'spawn_count': len(program.scenario['waves']),
        'native_spawn_count': plan['spawn_count'], 'native_control_counts': plan['control_counts'], 'native_route_inventory': routes,
        'native_difficulty': plan['difficulty'], 'applicable_runes': len(plan['applicable_runes']), 'inactive_runes': len(plan['inactive_runes']),
        'stage_current_profiles': stage['manifest']['metadata']['model_profiles'],
        'required_mechanics_source_list': plan['required_mechanics'], 'historical_reports_not_automatically_current': reports,
        'missing_native_skill_metadata_for_gate': [x['native_id'] for x in rows if x['gate_native_skill_metadata'] != x['selected_skill_native_id']],
        'undeployed_fixed_roster': sorted(set(actors)-deployed), 'receipt_issued': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'validation/campaign/first_model_acceptance_scope_audit.json')
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'roster': result['fixed_roster_count'], 'spawns': result['spawn_count'],
        'undeployed': result['undeployed_fixed_roster'], 'gate_metadata_missing': result['missing_native_skill_metadata_for_gate'],
        'receipt_issued': False, 'output': str(args.output)}))
