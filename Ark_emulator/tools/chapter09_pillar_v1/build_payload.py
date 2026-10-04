"""Source-bound pillar collapse payload using existing owned-cast APIs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/predefines.native.v3.json'
RUIN_SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/duruin.transitive.source.v1.json'
PREFIX = 'ch9/pillar/'
TRAIT = 'buff/' + PREFIX + 'trait'


def members(inputs, parameters, context):
    from ark_sim.domains.spatial import project_cell
    parameters = {**parameters, **inputs['parameters']}
    source = context['source']; center = project_cell(inputs['center_position'])
    offsets = parameters['offsets']; cells = {(center[0] + x[0], center[1] + x[1]) for x in offsets}
    states = context['area_selection_states']['candidates']; result = []
    for actor in inputs['candidates']:
        if actor['id'] == source['id'] or project_cell(actor['components']['spatial']['position']) not in cells:
            continue
        state = states[str(actor['id'])]
        if state['side'] != parameters['side'] or not state['category'] & parameters['category_mask'] or not state['motion'] & parameters['motion_mask']:
            continue
        if state['target_free'] and not parameters['ignore_target_free']:
            continue
        if state.get('invisible', False) and not parameters['can_select_invisible']:
            continue
        if state['camouflage'] and not parameters['can_select_camouflage']:
            continue
        result.append(actor['id'])
    return result


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.ch9.pillar_members': {'callable': members, 'version': 'source-masks-cell-offsets-v1'}}


def build():
    from ark_sim.domains.selection import DEFAULT_STATE
    source = json.loads(SOURCE.read_bytes()); ruin = json.loads(RUIN_SOURCE.read_bytes())
    native = source['stages']['level_main_09-16']['instances'][0]['raw_character']['phases'][0]['attributesKeyFrames'][0]['data']
    assert (native['maxHp'], native['atk']) == (5000, 12000)
    skills = source['skill_prefabs']['sktok_dupilr']['components']
    attacks = [c for c in skills.values() if c['native_class'] == 'MeleeAttack']
    damage = next(c for c in attacks if c['gameobject_name'] == 'AttackEnemy')
    assert damage['raw']['_preDelay'] == 1.5 and damage['raw']['_damageType'] == 3
    child = next(c for c in source['prefabs']['trap_043_dupilr']['components'].values()
                 if c['native_class'] == 'PassiveBuffAbility' and any(b['buffKey'] == 'dupilr_trait' for b in c['raw']['_buffs']))
    raw_trait = next(b for b in child['raw']['_buffs'] if b['buffKey'] == 'dupilr_trait')
    mode = next(c['raw'] for c in ruin['native_prefab']['components'].values() if c['native_class'] == 'TrapMode')
    assert mode['_keepCurrentPassableMask'] == 1
    p = {'schemaVersion': 2, 'manifest': {'id': 'package/' + PREFIX + 'collapse_payload_v1', 'metadata': {
        'scope': 'Collapse gameplay payload only; automatic modifier and depleted damaged state still require owned source consumers',
        'source_locks': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (SOURCE, RUIN_SOURCE, Path(__file__))},
        'native_trait': raw_trait, 'native_damage': damage, 'whole_pillar_complete': False}},
        'rules': [{'id': 'rule/' + PREFIX + 'members', 'kind': 'rule', 'contract': 'area.members',
                   'implementation': {'type': 'provider', 'provider': 'reference.ch9.pillar_members'}}],
        'buffs': [{'id': TRAIT, 'kind': 'buff', 'metadata': {'native_inline': raw_trait,
                  'source_marker_role': 'Actual pillar damage provenance for gargoyle skip consumer; modifier callbacks separately pending'}},
                  {'id': 'buff/' + PREFIX + 'stun10', 'kind': 'buff', 'duration_seconds': 10,
                   'selection_flags': {'abnormal_flags': [0]}, 'control': {'move': False, 'attack': False, 'abilities': False, 'interrupt': True}},
                  {'id': 'buff/' + PREFIX + 'deadlike', 'kind': 'buff',
                   'selection_flags': {'abnormal_flags': [5, 6, 2, 15, 3], 'abnormal_immunes': [0, 16, 19], 'abnormal_combo_immunes': [0]}}],
        'abilities': [], 'entities': []}
    directions = {'right': [(0, 0), (0, 1), (0, 2)], 'left': [(0, 0), (0, -1), (0, -2)],
                  'up': [(0, 0), (-1, 0), (-2, 0)], 'down': [(0, 0), (1, 0), (2, 0)]}
    for direction, offsets in directions.items():
        def area(side, category, free, effects):
            return {'op': 'area', 'target': 'source', 'center': 'source', 'membership_rule': 'rule/' + PREFIX + 'members',
                'selection_projection': {'defaults': DEFAULT_STATE},
                'parameters': {'offsets': offsets, 'side': side, 'category_mask': category, 'motion_mask': 3,
                    'ignore_target_free': free, 'can_select_invisible': False, 'can_select_camouflage': False}, 'effects': effects}
        dr, dc = offsets[1]
        eligibility = ('inputs.cell.row - inputs.source.components.spatial.position.row in params.rows and '
                       'inputs.cell.col - inputs.source.components.spatial.position.col in params.cols and '
                       'inputs.tile.buildableType != 0 and not inputs.deployment_blocked')
        rows = [dr, dr * 2] if dr else [0]; cols = [dc, dc * 2] if dc else [0]
        effects = [area(1, 1, False, [{'op': 'damage', 'damage_type': 'true', 'scale': 1},
                                      {'op': 'apply_buff', 'buff': 'buff/' + PREFIX + 'stun10'}]),
                   area(0, 1, True, [{'op': 'retire', 'parameters': {'reason': 'withdrawn'}}]),
                   area(0, 2, True, [{'op': 'instant_kill', 'parameters': {'cause': 'pillar_collapse', 'skip_rebirth': False}}]),
                   {'op': 'spawn_on_tiles', 'definition': 'unit/' + PREFIX + 'ruin', 'parameters': {
                       'cells': 'captured', 'recheck': True, 'occupant_expression': 'False', 'occupant_parameters': {},
                       'instant_kill': {'cause': 'pillar_spawn', 'skip_rebirth': False}, 'on_owner_retire': 'retain'}},
                   {'op': 'retire', 'target': 'source', 'parameters': {'reason': 'dead'}}]
        p['abilities'].append({'id': 'ability/' + PREFIX + 'collapse_' + direction, 'kind': 'ability',
            'activation': {'mode': 'manual', 'costs': [{'resource': 'sp', 'amount': 10}],
                'condition': 'inputs.resources.sp.current >= 10',
                'on_start': [{'op': 'apply_buff', 'target': 'source', 'buff': 'buff/' + PREFIX + 'deadlike', 'bind_to_cast': True}]},
            'tile_selector': {'eligibility_expression': eligibility, 'parameters': {'rows': rows, 'cols': cols},
                              'limit': 2, 'selection': 'row_major', 'stream': None},
            'timeline': [{'at_seconds': 1.5, 'effects': effects}], 'duration_seconds': 1.5})
    p['entities'] = [{'id': 'unit/' + PREFIX + 'body', 'kind': 'entity', 'tags': ['pillar', 'dupilr'], 'components': {
        'attributes': {'base': {'max_hp': 5000, 'atk': 12000, 'def': 0, 'mres': 0}},
        'resources': {'hp': {'role': 'health', 'capacity': 5000, 'initial': 5000}, 'sp': {'capacity': 10, 'initial': 10}},
        'spatial': {}, 'selection_state': {'side': 2, 'motion': 1, 'category': 1, 'unit_type': 4},
        'buffs': {'initial': [TRAIT]}, 'abilities': [a['id'] for a in p['abilities']], 'lifecycle': {'policy': 'policy/ark_lifecycle'}}},
        {'id': 'unit/' + PREFIX + 'ruin', 'kind': 'entity', 'tags': ['enemy', 'ruin'], 'components': {
            'attributes': {'base': {'max_hp': 100, 'atk': 0, 'def': 0, 'mres': 0, 'block_count': 3}},
            'resources': {'hp': {'role': 'health', 'capacity': 100, 'initial': 100}},
            'spatial': {}, 'selection_state': {'side': 1, 'motion': 1, 'category': 4, 'unit_type': 4},
            'tile_occupancy': {'blocks_deployment': True, 'exclusive': False, 'targetable': True, 'withdrawable': True},
            'terrain_overlays': [{'key': 'ruin', 'priority': 0, 'values': {'buildableType': 0,
                'physicalHeight': mode['_rewriteHeight'], 'obstacleLikeMoveCost': True}, 'preserve': ['passableMask', 'heightType']}],
            'deployable': {'base_cost': 5, 'terrain': 'ground', 'capacity': 0, 'cooldown_seconds': 5,
                          'refund_ratio': 0, 'parameters': {'max_instances': 100}},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}}]
    return p


if __name__ == '__main__':
    output = ROOT / 'packages/campaign/chapter09_consumers/pillars/collapse.payload.v1.json'
    if output.exists(): raise FileExistsError(output)
    output.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(hashlib.sha256(output.read_bytes()).hexdigest())
