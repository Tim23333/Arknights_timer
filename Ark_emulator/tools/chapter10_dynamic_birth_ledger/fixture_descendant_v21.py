"""Independent native death descendant scenario for the bounded V21 worker."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def providers():
    from tools.chapter10_bloodline_v1.build import providers as bloodline
    return bloodline()


def package():
    from tools.chapter10_bloodline_v1.build import build_all, entity_id
    p = build_all()
    p['entities'].append({'id': 'unit/independent/ledger/operator', 'kind': 'entity', 'tags': ['player'],
        'components': {'attributes': {'base': {'max_hp': 7139, 'atk': 10391, 'def': 0, 'mres': 0, 'block_count': 0}},
            'resources': {'hp': {'role': 'health', 'initial': 7139, 'capacity': 7139}},
            'selection_state': {'side': 0, 'category': 1, 'motion': 1, 'unit_type': 1},
            'spatial': {}, 'abilities': ['ability/independent/ledger/parent', 'ability/independent/ledger/child'],
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    parent, child = entity_id('enemy_1222_dpvt_2'), entity_id('enemy_1220_dzoms_2')
    for name, definition in [('parent', parent), ('child', child)]:
        selector = 'selector/independent/ledger/' + name
        p['selectors'].append({'id': selector, 'kind': 'selector', 'region': {'type': 'all'},
            'filters': [{'state': 'alive'}, {'field': {'path': ['definition_id'], 'equals': definition}}], 'limit': 1})
        p['abilities'].append({'id': 'ability/independent/ledger/' + name, 'kind': 'ability',
            'activation': {'mode': 'manual'}, 'selector': selector,
            'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': 'true', 'scale': 1}}]})
    p['scenarioDraft'] = {'id': 'scene/independent/ledger/death_source', 'ruleset': 'ruleset/ark_standard',
        'seed': 19937, 'map': {'rows': 3, 'cols': 7}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
        'objectives': {'type': 'waves', 'life_resource': 'life'},
        'metadata': {'runthrough_profile': {'base_life_resource': 'life', 'scope': 'Bounded source death ledger, not a campaign stage'}},
        'initialEntities': [{'definition': 'unit/independent/ledger/operator', 'instanceAlias': 'operator', 'position': {'row': 2, 'col': 0}}],
        'timeline': {'policy': 'managed_clear', 'negative_timeout_policy': 'wait_for_clear', 'waves': [
            {'fragments': [{'actions': [{'kind': 'spawn', 'spawn': {'definition': parent, 'instanceAlias': 'parent',
                'position': {'row': 1, 'col': 1}, 'route': {'motionMode': 'WALK', 'startPosition': {'row': 1, 'col': 1},
                    'endPosition': {'row': 1, 'col': 6}, 'checkpoints': [{'type': 'WAIT_FOR_SECONDS', 'time': 3, 'position': {'row': 1, 'col': 1}}]}},
                'count': 1, 'managed': True, 'blocks_wave': True}]}]}, {'fragments': []}]}}
    return p


if __name__ == '__main__':
    output = ROOT / 'scenarios/campaign/chapter10/ledger_descendant_gate'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'package.json').write_text(json.dumps(package(), indent=2) + '\n', encoding='utf8')
    (output / 'commands.json').write_text(json.dumps([
        {'at': 7, 'action': 'skill', 'source': 'operator', 'ability': 'ability/independent/ledger/parent'},
        {'at': 50, 'action': 'skill', 'source': 'operator', 'ability': 'ability/independent/ledger/child'}], indent=2) + '\n', encoding='utf8')
