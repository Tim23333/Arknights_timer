"""Exact selected chapter0 constant-mode melee and nonattacking flyer models."""
import hashlib
import json
from pathlib import Path
from copy import deepcopy
import sys

ROOT = Path(__file__).resolve().parents[2];sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'packages/campaign/chapter0_source_prepare/enemies.native.v1.json'
SOURCE_SHA = 'ad8a610ad5b3fbebe16a000f5098084accab4a346492dd686e937f22925fe360'


def build():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError('Native chapter0 source changed')
    source = json.loads(SOURCE.read_bytes())
    entities, abilities, selectors, bindings = [], [], [], {}
    for variant in source['variants'].values():
        native = variant['native_enemy']['resolved'];key = variant['prefab_key']
        root = source['prefabs'][key]['components'][str(variant['root_path_id'])]['raw']
        modes = variant['modes']
        assert len(modes) == 1 and not root['_commonAbilities'] and not modes[0]['raw']['_generalAbilities']
        assert root['_delayToBorn'] == 0 and not variant['passive_and_skill_components']
        attrs = native['attributes'];motion = {'WALK': 1, 'FLY': 2}[native['motion']]
        entity = 'unit/ch0/' + key;attack = 'ability/ch0/' + key + '/combat'
        owned = []
        node = modes[0]['nodes']['_combat'];raw = node['raw']
        if node['native_class'] == 'MeleeAttack':
            assert motion == 1 and raw['_selectTargetSource'] == 2 and raw['_damageType'] == 1
            assert raw['_waitForAttackEvent'] == 1 and raw['_preDelay'] == 0
            binding = node['animation_binding']
            hits = [e for e in binding['events'] if e['name'] == 'OnAttack']
            assert len(hits) == 1 and hits[0]['exact_authored_frame']
            selector = 'selector/ch0/' + key + '/actual_blocker'
            selectors.append({'id': selector, 'kind': 'selector', 'region': {'type': 'all', 'blocked_only': True},
                              'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': 1})
            abilities.append({'id': attack, 'kind': 'ability',
                              'activation': {'mode': 'automatic_attack', 'interval_seconds': attrs['baseAttackTime']},
                              'selector': selector, 'duration_seconds': binding['duration']['seconds'],
                              'timeline': [{'at_seconds': hits[0]['seconds'], 'effect':
                                            {'op': 'damage', 'damage_type': 'physical', 'scale': raw['_atkScale']}}],
                              'metadata': {'native_owned_node': deepcopy(node),
                                           'source_reference': 'Only actual blocker; exact authored OnAttack and full animation duration, source base interval'}})
            owned.append(attack)
        else:
            assert node['native_class'] == 'EmptyAnimatedAbility' and motion == 2 and attrs['atk'] == 0
            assert modes[0]['nodes']['_attack']['status'] == 'native_null'
            assert modes[0]['nodes']['_attackTrigger']['status'] == 'native_null'
        base = {'max_hp': attrs['maxHp'], 'atk': attrs['atk'], 'def': attrs['def'], 'mres': attrs['magicResistance'],
                'move_speed': attrs['moveSpeed'], 'attack_speed_ratio': attrs['attackSpeed'] / 100,
                'attack_interval': attrs['baseAttackTime'], 'mass_level': attrs['massLevel'],
                'block_cost': root['_blockVolume']}
        entities.append({'id': entity, 'kind': 'entity', 'tags': ['enemy', key, 'air' if motion == 2 else 'ground'],
                         'components': {'attributes': {'base': base},
                                        'resources': {'hp': {'role': 'health', 'initial': attrs['maxHp'], 'capacity': attrs['maxHp']}},
                                        'selection_state': {'side': root['_sideTypeIndex'], 'motion': motion, 'category': 1, 'unit_type': 2,
                                                            'abnormal_immunes': [0] if attrs['stunImmune'] else []},
                                        'spatial': {'motion_mode': 1 if motion == 2 else 0, 'route_motion_mode': 1 if motion == 2 else 0},
                                        'abilities': owned, 'lifecycle': {'policy': 'policy/ark_lifecycle', 'leak_loss': native['lifePointReduce']}},
                         'metadata': {'native_variant': deepcopy(variant), 'root_component': deepcopy(root),
                                      'empty_combat_policy': 'Actual empty animated flyer has no damage or independent attack trigger; raw node retained' if not owned else None}})
        bindings[native['name']] = entity
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ch0/source_enemies_v1', 'metadata': {
                'source_sha256': SOURCE_SHA, 'variants': 8, 'constant_native_modes': True,
                'source_conversion_only': True, 'model_approved': False, 'whole_stage': False, 'client_verified': False}},
            'entities': entities, 'abilities': abilities, 'selectors': selectors}


if __name__ == '__main__':
    p = build();output = ROOT / 'packages/campaign/chapter0_consumers/enemies.module.v1.json'
    if output.exists():raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'entities': len(p['entities']), 'real_combat_abilities': len(p['abilities']),
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'model_approved': False}))
