"""Small real native-only run for the new worker's unchanged CP/head semantics."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return BUILTIN_PROVIDERS


def package():
    def entity(name, hp, tags, abilities=()):
        return {'id': 'unit/ledger21/' + name, 'kind': 'entity', 'tags': tags, 'components': {
            'attributes': {'base': {'max_hp': hp, 'atk': 10931, 'def': 0, 'mres': 0}},
            'resources': {'hp': {'initial': hp, 'capacity': hp, 'role': 'health'}}, 'spatial': {},
            'abilities': list(abilities), 'lifecycle': {'policy': 'policy/ark_lifecycle'}}}
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ledger21/static', 'metadata': {'pending_model_gaps': []}},
        'entities': [entity('native', 4317, ['enemy']), entity('operator', 7193, ['player'], ['ability/ledger21/kill'])],
        'selectors': [{'id': 'selector/ledger21/native', 'kind': 'selector', 'region': {'type': 'all'},
                       'filters': [{'tag': 'enemy'}, {'state': 'alive'}], 'limit': 1}],
        'abilities': [{'id': 'ability/ledger21/kill', 'kind': 'ability', 'activation': {'mode': 'manual'},
                       'selector': 'selector/ledger21/native', 'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': 'true', 'scale': 1}}]}],
        'scenarioDraft': {'id': 'scene/ledger21/static', 'ruleset': 'ruleset/ark_standard', 'seed': 1107,
            'map': {'rows': 2, 'cols': 3}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
            'objectives': {'type': 'waves', 'life_resource': 'life'},
            'metadata': {'runthrough_profile': {'base_life_resource': 'life', 'scope': 'Bounded runner mechanism gate, not a campaign stage'}},
            'initialEntities': [{'definition': 'unit/ledger21/operator', 'instanceAlias': 'operator', 'position': {'row': 1, 'col': 1}}],
            'timeline': {'policy': 'managed_clear', 'negative_timeout_policy': 'wait_for_clear', 'waves': [
                {'fragments': [{'actions': [{'kind': 'spawn', 'spawn': {'definition': 'unit/ledger21/native',
                    'instanceAlias': 'native', 'position': {'row': 0, 'col': 1}}, 'count': 1, 'managed': True, 'blocks_wave': True}]}]}]}}}


if __name__ == '__main__':
    output = ROOT / 'scenarios/campaign/chapter10/ledger_native_gate'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'package.json').write_text(json.dumps(package(), indent=2) + '\n', encoding='utf8')
    (output / 'commands.json').write_text(json.dumps([{'at': 7, 'action': 'skill', 'source': 'operator', 'ability': 'ability/ledger21/kill'}], indent=2) + '\n', encoding='utf8')
