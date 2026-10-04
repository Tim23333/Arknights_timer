"""Source-bound IceShield content for the independently reviewed tile runtime.

This is a replaceable reference policy, not a recovered native TileSelector body.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'packages/campaign/chapter04_boss_plan/source.reference.json'
PIN = '7ad2fb46b3e281711b6faf8b7a3bacfb9df6bc11ff32212a8439d8925d6893ec'
OUT = ROOT / 'packages/campaign/chapter04_boss/ice_shield_v3'


def build():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == PIN
    source = json.loads(SOURCE.read_bytes())
    plan = source['declared_plan']['ice_shield']
    assert (plan['initial_cd'], plan['cd'], plan['priority'], plan['source_tile_count'],
            plan['source_spawn_frame'], plan['instant_kill_skip_reborn_raw']) == (30, 30, 2, 2, 55, False)
    token_id = 'unit/ch4/frost/sealed_floor'
    token = {'id': token_id, 'kind': 'entity', 'version': 'ice-shield-reference-v1',
        'tags': ['sealed_floor'], 'components': {
            'attributes': {'base': {'max_hp': 100, 'atk': 0, 'def': 0, 'res': 0}},
            'resources': {'hp': {'role': 'health', 'initial': 100, 'capacity_attribute': 'max_hp'}},
            'lifecycle': {'policy': 'policy/ark_lifecycle'},
            'tile_occupancy': {'blocks_deployment': True, 'exclusive': True, 'targetable': False, 'withdrawable': False}},
        'metadata': {'native_key': 'trap_004_iceblock', 'no_terrain_rewrite': True,
            'native_token_asset_sha': source['sealed_floor_native']['source']['sha256'],
            'character_table_entry_present': False, 'stats_origin': 'PRTS reference HP100; no source-table entry',
            'player_withdraw_supported': False}}
    skill = {'id': 'ability/ch4/frost/ice_shield', 'kind': 'ability', 'version': 'ice-shield-reference-v1',
        'initial_cooldown_seconds': plan['initial_cd'], 'cooldown_seconds': plan['cd'],
        'activation': {'mode': 'manual', 'parameters': {'requires_targets': True,
            'auto_when_ready': True, 'auto_only': True, 'priority': plan['priority']}},
        'tile_selector': {
            'eligibility_expression': '(inputs.cell.row-inputs.source.components.spatial.position.row)**2 + '
                '(inputs.cell.col-inputs.source.components.spatial.position.col)**2 <= params.radius**2 '
                'and inputs.tile.buildableType in params.buildable_types and not inputs.deployment_blocked',
            'parameters': {'radius': 2, 'buildable_types': [1, 2, 3]}, 'limit': plan['source_tile_count'],
            'selection': 'uniform_without_replacement', 'stream': 'ch4/frost/ice_shield/reference_uniform'},
        'timeline': [{'at': plan['source_spawn_frame'], 'effect': {
            'op': 'spawn_on_tiles', 'definition': token_id, 'parameters': {
                'cells': 'captured', 'recheck': False,
                'occupant_expression': "'player' in inputs.candidate.tags",
                'occupant_parameters': {}, 'instant_kill': {'cause': 'ice_shield', 'skip_rebirth': False},
                'on_owner_retire': 'retain'}}}],
        'metadata': {'source_plan_sha': PIN, 'native_filter_enum': 'EXCEPT_CHARACTER',
            'selection_policy': 'deployment-eligible cell centers in radius2, exclude current deployment occupancy; '
                'uniform sample without replacement at accepted activation, root-cell occupants at frame55',
            'source_conflict': 'Native TileSelector filter/body and radius/cell boundary remain unverified; '
                'this explicit reference policy must not be called native equivalence',
            'cooldown_policy': '30 seconds from cast finish, initial30; replaceable pending loader-body evidence',
            'kill_policy': 'Current player-tag root-cell occupants at execution; true InstantKill allows rebirth'}}
    return {'manifest': {'id': 'package/ch4/frost/ice_shield_v1', 'version': '1',
        'metadata': {'status': 'source_bound_reference_module_pending_peer_and_full_stage',
            'source_locks': {str(SOURCE.relative_to(ROOT)): PIN},
            'source_references': source['reference_sources'], 'client_verified': False,
            'requires': ['tile_selector', 'tile_occupancy', 'spawn_on_tiles', 'ability.initial_cooldown_seconds']}},
        'definitions': [token, skill]}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    data = json.dumps(build(), ensure_ascii=False, indent=2).encode('utf8') + b'\n'
    path = OUT / 'module.reference.json'
    if args.check:
        assert path.read_bytes() == data
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(data)
    print(json.dumps({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
        'checked': args.check, 'full_stage_executed': False}))


if __name__ == '__main__':
    main()
