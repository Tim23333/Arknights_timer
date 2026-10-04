"""Declared source BuffTile base-force contribution, cell membership and removal."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/environment.native.v1.json'


def eligibility(inputs, parameters, context):
    from ark_sim.domains.spatial import project_cell
    state = inputs['selection_states']['candidate']
    same = project_cell(inputs['source']['components']['spatial']['position']) == project_cell(inputs['candidate']['components']['spatial']['position'])
    accepted = (same and state['side'] == 0 and bool(state['category'] & 1) and bool(state['motion'] & 3)
                and not state['target_free'] and not state['camouflage'] and not state.get('invisible', False))
    return {'accepted': accepted, 'reason': 'native_cell_player_character' if accepted else 'outside_native_field_qualification'}


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.ch9.bigforce_cell': {'callable': eligibility, 'version': '1'}}


def build():
    from ark_sim.domains.selection import DEFAULT_STATE, SWITCHES
    native = json.loads(SOURCE.read_bytes())
    source = next(c['raw'] for c in native['prefabs']['tile_bigforce']['components'].values() if c['native_class'] == 'BuffTile')
    raw = source['_buffs'][0]
    assert source['_clearBuffsWhenLeft'] == 1 and raw['attributes']['attributeModifiers'][0]['attributeType'] == 24
    operands = [t for values in native['stage_tile_operands'].values() for t in values if t['tileKey'] == 'tile_bigforce']
    boards = [{r['key']: r['value'] for r in t['blackboard']} for t in operands]
    assert boards and all(b == {'base_force_level': 1.0} for b in boards)
    config = {k: 0 for k in SWITCHES}; config.update(_targetSide=1, _targetMotion=3, _targetCategory=1)
    parent = 'buff/ch9/bigforce/parent'; child = 'buff/ch9/bigforce/base_force'
    owner = 'unit/ch9/bigforce/field'; selector = 'selector/ch9/bigforce/cell'; rule = 'rule/ch9/bigforce/eligibility'
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ch9/bigforce/v1', 'metadata': {
        'source_locks': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE, Path(__file__)]},
        'native_BuffTile': source, 'reference_policy': 'Static field owner selects player characters by explicit native targetSide1 projection and current model cell; leaves remove actual owned child.',
        'whole_stage_verified': False}}, 'entities': [{'id': owner, 'kind': 'entity', 'tags': ['tile_field_owner'],
        'components': {'selection_state': {'side': 0, 'motion': 1, 'category': 2, 'unit_type': 4},
                       'spatial': {}, 'buffs': {'initial': [parent]}}}],
        'rules': [{'id': rule, 'kind': 'rule', 'contract': 'targeting.eligibility',
                   'implementation': {'type': 'provider', 'provider': 'reference.ch9.bigforce_cell'}}],
        'selectors': [{'id': selector, 'kind': 'selector', 'region': {'type': 'all'}, 'limit': None,
            'eligibility': {'rule': rule, 'parameters': {'source_configuration': config, 'side_policy': 'relative_ally_enemy',
                'neutral_policy': 'reject', 'defaults': DEFAULT_STATE}}}],
        'buffs': [{'id': parent, 'kind': 'buff', 'aura': {'selector': selector, 'buff': child,
                    'lease_policy': {'mode': 'shared', 'identity': ['definition', 'target'],
                                     'source_binding': 'oldest_live_lease', 'external_child_collision': 'reject'}}},
                  {'id': child, 'kind': 'buff', 'stacking': {'mode': 'refresh', 'identity': ['definition', 'target'], 'max_stacks': 1},
                   'modifiers': [{'attribute': 'base_force_level', 'layer': 'flat', 'value': 1.0}], 'metadata': {'native_inline': raw}}]}


def profile():
    return {'type': 'occupancy_buff_field', 'definition': 'unit/ch9/bigforce/field', 'expected_blackboard': {'base_force_level': 1.0}}
