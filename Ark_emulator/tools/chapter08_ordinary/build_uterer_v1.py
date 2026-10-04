"""Source-bound chapter8 melee consumer; no game-ID runtime branches."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest

CORE = '3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
VID = 'enemy_1108_uterer@0/dfc143b32f205b76'
UNIT = 'unit/ch8/uterer/dfc143b32f205b76'
ABILITY = 'ability/ch8/uterer/combat'
SELECTOR = 'selector/ch8/uterer/blocked'
BEHAVIOR = 'behavior/ch8/uterer'
SOURCE = ROOT/'packages/campaign/chapter08_source_prepare/integration'
OUT = ROOT/'packages/campaign/chapter08_consumers/uterer/module.v1.reference.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assert implementation_digest() == CORE
    paths = [SOURCE/'source.plan.v1.json', SOURCE/'enemies.native.v1.json', Path(__file__)]
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    assert before['packages/campaign/chapter08_source_prepare/integration/enemies.native.v1.json'] == '9b2a5b1b0d2dfe623421596181a3fc6462ccd4f9cf660cba6f4e75120600941e'
    plan = json.loads(paths[0].read_bytes())
    source = json.loads(paths[1].read_bytes())
    variant = plan['variants'][VID]
    resolved = variant['native_enemy']['resolved']
    prefab = source['prefabs'][resolved['prefabKey']]
    components = prefab['components']
    root = next(c for c in components.values() if c['native_class'] == 'Enemy')
    mover = next(c for c in components.values() if c['native_class'] == 'MoveController')
    modes = root['raw']['_modes']
    assert len(modes) == 1 and modes[0]['m_FileID'] == 0
    mode = components[str(modes[0]['m_PathID'])]
    assert mode['native_class'] == 'UnitMode'
    assert not root['raw']['_commonAbilities'] and not mode['raw']['_generalAbilities']
    assert mode['raw']['_attack']['m_PathID'] == mode['raw']['_attackTrigger']['m_PathID'] == 0
    combat_ref = mode['raw']['_combat']
    assert combat_ref == {'m_FileID': 0, 'm_PathID': 7292172302963525355}
    combat = components[str(combat_ref['m_PathID'])]
    raw = combat['raw']
    assert combat['native_class'] == 'MeleeAttack' and not raw['_activeBuffs']
    assert not resolved.get('skills') and not resolved.get('talentBlackboard')
    assert (raw['_damageType'], raw['_attackType'], raw['_timeMode'], raw['_affectedBySlowDown']) == (1, 1, 0, 1)
    assert raw['_selector']['m_PathID'] == 0 and raw['_waitForAttackEvent'] == 1
    animation = source['animations'][resolved['prefabKey']]
    mapping = next(r for r in animation['animator']['fields']['_animations'] if r['animKey'] == raw['_animKey'])
    binding = animation['parsed']['animations'][mapping['animName']]
    events = [e for e in binding['events'] if e['name'] == 'OnAttack']
    assert len(events) == 1 and events[0]['exact_authored_frame'] is True
    assert (mapping['speed'], events[0]['frame'], events[0]['seconds']) == (1.0, 12, .4)
    attrs = resolved['attributes']
    assert (attrs['maxHp'], attrs['atk'], attrs['def'], attrs['magicResistance'], attrs['baseAttackTime']) == (3500, 380, 100, 20, 1.5)
    immunity_defaults = {k: False for k in ('silenceImmune', 'stunImmune', 'sleepImmune', 'frozenImmune') if k not in attrs}
    policy = {
        'native_method_bodies_verified': False,
        'capture': 'Current blocker captured at cast; target retirement cancels damage through normal lifecycle checks.',
        'damage_reads': 'Current source ATK and target DEF at hit, explicit replaceable read_mode.',
        'clock': 'TimeMode0 OnAttack .4s divided by current attack_speed_ratio; cooldown uses baseAttackTime1.5s.',
        'movement': 'Source steering8/maxforce10, V2 centre/grid collision and arrival radius .05 reference rule.',
        'undefined_DB_immunity_defaults': immunity_defaults,
        'undefined_DB_defaults_are_not_defined_source_values': True,
        'render_only': ['UberEffectEmitter', 'ShadowController', 'FaceSwitcher', 'SkeletonAnimation', 'SingleSpineAnimator'],
        'client_verified': False,
    }
    p = {
        'schemaVersion': 2,
        'manifest': {'id': 'package/ch8/uterer/source_v1', 'requires': ['preset/ark_standard'], 'metadata': {
            'source_locks': before, 'required_runtime': CORE, 'reference_policy': policy,
            'variant_bindings': [{'variant_id': VID, 'unit_definition': UNIT, 'native_reference': variant['native_reference'],
                'native_resolved': resolved, 'native_raw_rows': variant['native_enemy']['raw_rows'],
                'root_source': root, 'mode_source': mode, 'combat_source': combat, 'mover_source': mover,
                'animation_mapping': mapping, 'animation_binding': binding}],
            'whole_stage_executed': False, 'independent_reviewed': False,
        }},
        'entities': [{'id': UNIT, 'kind': 'entity', 'tags': ['enemy', 'ground'], 'components': {
            'attributes': {'base': {'max_hp': attrs['maxHp'], 'atk': attrs['atk'], 'def': attrs['def'],
                'mres': attrs['magicResistance'], 'move_speed': attrs['moveSpeed'], 'attack_interval': attrs['baseAttackTime'],
                'attack_speed_ratio': attrs['attackSpeed']/100, 'mass_level': attrs['massLevel'], 'block_cost': root['raw']['_blockVolume']}},
            'resources': {'hp': {'initial': attrs['maxHp'], 'capacity_attribute': 'max_hp', 'role': 'health'}},
            'selection_state': {'side': 1, 'motion': 1, 'category': 1, 'unit_type': 2, 'abnormal_immunes': []},
            'spatial': {'motion_mode': 0, 'steering': {'rule': 'rule/ch8/uterer/steering', 'parameters': {
                'response_factor': mover['raw']['_steeringFactor'], 'max_acceleration': mover['raw']['_maxSteeringForce'], 'arrival_radius': .05}}},
            'lifecycle': {'policy': 'policy/ark_lifecycle', 'leak_loss': resolved['lifePointReduce']},
            'abilities': [ABILITY], 'behavior': {'machine': BEHAVIOR},
        }, 'metadata': {'native_variant': VID, 'native_reference': variant['native_reference']}}],
        'abilities': [{'id': ABILITY, 'kind': 'ability', 'selector': SELECTOR,
            'activation': {'mode': 'automatic_attack', 'parameters': {'auto_only': True}}, 'target_capture': 'at_cast',
            'timeline': [{'at_seconds': events[0]['seconds'], 'effect': {'op': 'damage', 'damage_type': 'physical', 'scale': raw['_atkScale'],
                'read_mode': {'source_attributes': 'at_hit', 'target_attributes': 'at_hit'},
                'damage_flags': {'source_attack_type': 'NORMAL', 'ignore_for_sp': False}}}],
            'rules': {'ability.windup': 'rule/ch8/uterer/windup'},
            'metadata': {'source_component_path_id': combat_ref['m_PathID'], 'native_OnAttack_frame': 12}}],
        'selectors': [{'id': SELECTOR, 'kind': 'selector', 'region': {'type': 'all', 'blocked_only': True},
            'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': 1}],
        'behaviors': [{'id': BEHAVIOR, 'kind': 'behavior', 'initial': 'active', 'states': {'active': {}}, 'transitions': [],
            'decision': {'rule': 'rule/ark_behavior_decision', 'default_mode': 0, 'profiles': [{'mode': 0,
                'selectors': [{'key': 'normal', 'selector': SELECTOR}], 'cast_groups': [{'key': 'normal', 'abilities': [ABILITY]}],
                'parameters': {'target_key': 'normal', 'blocked_target': True, 'stop_on_target': False, 'stop_cast_groups': ['normal']}}]}}],
        'rules': [
            {'id': 'rule/ch8/uterer/steering', 'kind': 'rule', 'contract': 'movement.steering',
                'implementation': {'type': 'provider', 'provider': 'ark.movement.steering_velocity'}},
            {'id': 'rule/ch8/uterer/windup', 'kind': 'calculation_rule', 'contract': 'ability.windup',
                'parameters': {'minimum_speed': .01, 'native_max_anim_scale': raw['_maxAnimScale']},
                'implementation': {'type': 'expression', 'expression': 'inputs.timing_parameters.seconds / max(inputs.attributes.attack_speed_ratio, params.minimum_speed)'},
                'metadata': {'source_timing_fields': {k: raw[k] for k in ('_affectedBySlowDown','_timeMode','_waitForAttackEvent','_maxAnimScale','_preDelay','_animKey')},
                    'native_body_verified': False, 'reference_replaceable': True}},
        ],
    }
    fixture = dict(p)
    fixture['scenarioDraft'] = {'id': 'scene/ch8/uterer/compile', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 1, 'cols': 3},
        'initialEntities': [{'definition': UNIT, 'instanceAlias': 'source', 'position': {'row': 0, 'col': 0}}]}
    Compiler().compile(fixture)
    assert before == {x.relative_to(ROOT).as_posix(): sha(x) for x in paths}
    return p


if __name__ == '__main__':
    p = build()
    assert not OUT.exists(), 'Frozen consumer already exists; create a new version instead.'
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='')
    print(json.dumps({'module_sha': sha(OUT), 'variant': VID, 'actual_compile': True, 'whole_stage_executed': False}))
