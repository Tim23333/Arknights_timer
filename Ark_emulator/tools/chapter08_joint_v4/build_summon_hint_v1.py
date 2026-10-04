"""Native branch advancement and explicit seven-group visual hint data."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v4_candidate'
SOURCE = ROOT / 'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json'
LOOP = ROOT / 'packages/campaign/chapter08_consumers/flame/loop.profile.v3.json'
OUT = SOURCE.with_name('summon_hint.module.v1.json')
HINT = 'ability/ch8/bsnake/hint'
COUNTDOWN = 'ability/ch8/bsnake/hint_countdown'
SUMMON = 'ability/ch8/bsnake/summon_flame'
TIMER = 'buff/ch8/source/bsnake_t[hint]'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    data = json.loads(SOURCE.read_bytes())
    loop = json.loads(LOOP.read_bytes())
    groups = data['hint_alias_sets7x5']
    assert len(groups) == 7 and all(len(group) == 5 for group in groups)
    actions = loop['native_summon_actions']
    assert actions[0]['_isLoop'] and [node.get('_abilityName') for node in actions[1:]] == ['Hint', 'HintCountdown']
    bb = data['consumer_merged_BB12']
    assert bb['hint.interval']['value'] == 27
    start = [{'op': 'emit', 'event': 'source.bsnake.hint.clear'}]
    for index, keys in enumerate(groups):
        start.append({'op': 'emit', 'event': 'source.bsnake.hint.show',
                      'payload': {'phase_index': index, 'registration_keys': keys,
                                  'effect_key': 'map_fire_crystal_birth_01_buff'},
                      'condition': 'inputs.source.components.resources.hint_phase.current == ' + str(index)})
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ch8/bsnake/summon_hint_v1',
            'requires': ['preset/ark_standard'], 'metadata': {
                'source_locks': {str(path): sha(path) for path in (SOURCE, LOOP, Path(__file__))},
                'required_runtime': '20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30',
                'resources_required': {'mode': {'initial': 0, 'capacity': 3}, 'hint_phase': {'initial': 0, 'capacity': 6}},
                'owned_abilities': [HINT, COUNTDOWN, SUMMON], 'native_actions': actions,
                'reference_policy': 'Hint selects next native phase (not current completed phase); resource phase advances modulo7 after branch request. Countdown fires once at27s and clears itself. Visual effects explicit events carry actual native aliases, no fabricated combat actor.',
                'whole_stage_executed': False, 'full_boss_complete': False, 'client_verified': False}},
            'abilities': [
                {'id': HINT, 'kind': 'ability', 'activation': {'mode': 'manual', 'parameters': {'auto_only': True},
                    'on_start': start}, 'timeline': []},
                {'id': COUNTDOWN, 'kind': 'ability', 'activation': {'mode': 'manual', 'parameters': {'auto_only': True},
                    'on_start': [{'op': 'apply_buff', 'target': 'source', 'buff': TIMER}]}, 'timeline': []},
                {'id': SUMMON, 'kind': 'ability', 'cooldown_seconds': 50, 'initial_cooldown_seconds': 75,
                 'activation': {'mode': 'manual', 'parameters': {'auto_only': True},
                     'condition': "inputs.resources.mode.current == 1 and inputs.branches.bsnake_flame.available == True"},
                 'duration_seconds': 70 / 30, 'timeline': [{'at': 27, 'effects': [
                     {'op': 'advance_branch', 'parameters': {'branch': 'bsnake_flame'}},
                     {'op': 'modify_resource', 'target': 'source', 'resource': 'hint_phase', 'delta': 1,
                      'condition': 'inputs.source.components.resources.hint_phase.current < 6'},
                     {'op': 'modify_resource', 'target': 'source', 'resource': 'hint_phase', 'value': 0,
                      'condition': 'inputs.source.components.resources.hint_phase.current == 6'},
                     {'op': 'trigger_ability', 'target': 'source', 'ability': HINT},
                     {'op': 'trigger_ability', 'target': 'source', 'ability': COUNTDOWN},
                 ]}]},
            ], 'buffs': [{'id': TIMER, 'kind': 'buff', 'duration_seconds': 27,
                         'on_remove': [{'op': 'trigger_ability', 'target': 'source', 'ability': HINT}]}]}


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler
    p = build()
    scene = deepcopy(p)
    loop = json.loads(LOOP.read_bytes())
    scene['entities'] = [{'id': 'unit/summon/source', 'kind': 'entity', 'components': {
        'spatial': {}, 'resources': p['manifest']['metadata']['resources_required'],
        'abilities': p['manifest']['metadata']['owned_abilities']}}]
    # Structural compilation uses source keys but declared primitive definitions.
    keys = {item['definition'] for item in loop['initial_entities']}
    scene['entities'] += [{'id': key, 'kind': 'entity', 'components': {'spatial': {}}} for key in keys]
    scene['scenarioDraft'] = {'id': 'scene/summon/compile', 'ruleset': 'ruleset/ark_standard',
                              'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'],
                              'initialEntities': loop['initial_entities'] + [{'definition': 'unit/summon/source',
                                  'instanceAlias': 'source', 'position': {'row': 0, 'col': 0}}]}
    Compiler().compile(scene)
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'actual_compile': True}))
