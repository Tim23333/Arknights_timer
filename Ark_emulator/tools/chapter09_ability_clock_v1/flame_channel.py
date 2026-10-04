"""Source Flame casting state, six-second cooldown pulse and linked packets."""
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/enemies.native.v1.json'


def package():
    from tools.chapter09_linked_elemental.fixture_v2 import fixture
    p = fixture(capacity=1000, duration=10.6, hp=20000, resistance=20)
    data = json.loads(SOURCE.read_bytes())
    row = next(v for v in data['variants'].values() if v['prefab_key'] == 'enemy_1173_duspfr')
    skill = next(s for s in row['native_enemy']['resolved']['skills'] if s['prefabKey'] == 'Flame')
    bb = {r['key']: r['value'] for r in skill['blackboard']}
    assert (bb['duspfr_flame[cd].duration'], bb['duspfr_flame[cd].cooldown'], bb['duspfr_flame[cd].interval']) == (10.6, 10, 6)
    ability = p['abilities'][0]; aid = ability['id']; state = 'buff/ch9/flame/casting_state'
    ability['duration_seconds'] = 10.6
    ability['activation'] = {'mode': 'manual', 'forbidden_source_flags': [0, 12],
        'parameters': {'auto_only': True, 'auto_when_ready': True, 'requires_targets': True},
        'on_start': [{'op': 'apply_buff', 'target': 'source', 'buff': state, 'bind_to_cast': True},
                     {'op': 'set_ability_cooldown', 'target': 'source', 'ability': aid, 'duration_seconds': 0}]}
    # The source Attack preDelay is .5 seconds. Harpoon travel is independently
    # declared as the current planar speed10 reference, not native method proof.
    ability['timeline'][0] = {'at_seconds': .5, 'effect': ability['timeline'][0]['effect']}
    source = p['entities'][0]; source['components']['buffs'] = {'initial': []}
    p['buffs'].append({'id': state, 'kind': 'buff', 'duration_seconds': 10.6, 'interval_seconds': 6,
        'control': {'move': False, 'attack': False},
        'effects': [{'op': 'set_ability_cooldown', 'ability': aid, 'duration_seconds': 10}],
        'on_remove': [{'op': 'interrupt_ability', 'ability': aid},
                      {'op': 'set_ability_cooldown', 'ability': aid, 'duration_seconds': 10}],
        'events': [{'event': 'attachment.finished',
            'condition': "inputs.payload.source == context.owner.id and inputs.payload.reason in ['source_flags','cast_interrupted','target_invalid']",
            'effects': [{'op': 'interrupt_ability', 'ability': aid},
                        {'op': 'remove_buff', 'buff': state}]}],
        'metadata': {'native_buff_key': 'duspfr_flame[cd]', 'native_template': 'enemy_duspfr_flame[cd]',
                     'source_BB': bb, 'source_BSON': data['bson_templates']['templates']['enemy_duspfr_flame[cd]']}})
    p['scenarioDraft']['commands'] = []
    p['manifest'] = {'id': 'package/ch9/flame_channel/prototype', 'metadata': {
        'source_variant': row['native_reference'], 'source_skill': skill,
        'scope': 'Casting state and continuous payload; target loss source-owned cancellation, normal skill repeat state semantics and DeadBoom still require full consumer review',
        'reference_policy': 'Fixed native10.6/6/10/.5; planar harpoon flight10, first packet at contact, packets each.5. The10.6 cast state deadline cancels remaining link; its duration is not extended by flight.',
        'whole_enemy_complete': False}}
    return p


def providers():
    from tools.chapter09_linked_elemental.fixture_v2 import providers as base
    return base()
