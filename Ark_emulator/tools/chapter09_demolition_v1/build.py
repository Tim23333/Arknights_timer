"""Fixed demolition content; geometry/timing/force policies are explicit rules."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/predefines.native.v3.json'
PREFIX = 'ch9/demolition/'
BODY = 'unit/' + PREFIX + 'body'
BLAST = 'ability/' + PREFIX + 'blast'
BOOT = 'ability/' + PREFIX + 'deploy'
STOCK = 'stock_ch9_demolition'


def members(inputs, parameters, context):
    from ark_sim.domains.spatial import project_cell
    params = {**parameters, **inputs['parameters']}
    source = context['source']
    facing = source['components']['spatial'].get('facing', 'right')
    dr, dc = {'right': (0, 1), 'left': (0, -1), 'up': (-1, 0), 'down': (1, 0)}[facing]
    row, col = project_cell(inputs['center_position'])
    selected = []
    for actor in inputs['candidates']:
        if actor['id'] == source['id']:
            continue
        if project_cell(actor['components']['spatial']['position']) != (row + dr, col + dc):
            continue
        state = context['area_selection_states']['candidates'][str(actor['id'])]
        if params['branch'] == 'pillar':
            if params['pillar_tag'] in actor['tags'] and state['motion'] & 1:
                selected.append(actor['id'])
            continue
        if state['side'] != params['enemy_side'] or not state['category'] & 1 or not state['motion'] & 1:
            continue
        if state['camouflage'] or state.get('invisible', False):
            continue
        # Native _ignoreTargetFree=1. Membership uses the source selector mask.
        selected.append(actor['id'])
    return selected


def push_plan(inputs, parameters, context):
    flags = set(context['target']['components'].get('selection_state', {}).get('abnormal_flags', []))
    if 8 in flags:
        return {'distance': 0, 'duration': 0}
    delta = inputs['force'] + inputs['displacement_parameters']['source_force_bonus'] - inputs['mass']
    index = max(0, min(6, int(delta // 1) + 3))
    distance = parameters['distances'][index]
    speed = parameters['speeds'][index]
    return {'distance': distance, 'duration': 2 * distance / speed if speed else 0}


def environment_immunity(inputs, parameters, context):
    from ark_sim.contracts import thaw
    effect = inputs['effect']
    if effect.get('node_is_env_damage') or effect.get('environmental'):
        result = thaw(effect['settlement'])
        result['amount'] = 0
        for row in result.get('allocations', []):
            if row.get('resource', 'hp') == 'hp':
                if 'delta' in row: row['delta'] = 0
                if 'amount' in row: row['amount'] = 0
        return result
    return thaw(effect['settlement'])


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,
        'reference.ch9.demolition_members': {'callable': members, 'version': 'front-cell-live-source-masks-v1'},
        'reference.ch9.demolition_push': {'callable': push_plan, 'version': 'explicit-force-table-v1'},
        'reference.ch9.demolition_environment': {'callable': environment_immunity, 'version': 'native-shared-env-flag-zero-v1'}}


def build(stage='level_main_09-16', *, pillar_abilities=None):
    from ark_sim.domains.selection import DEFAULT_STATE
    from tools.build_weedy_skill_recipe import literal_push_profile
    native = json.loads(SOURCE.read_bytes())
    row = next(x for x in native['stages'][stage]['instances']
               if x['raw_native']['inst']['characterKey'] == 'trap_045_dublst')
    assert row['bucket'] == 'tokenCards' and row['raw_native']['initialCnt'] == {'level_main_09-16': 2, 'level_main_09-17': 1}[stage]
    attrs = row['raw_character']['phases'][0]['attributesKeyFrames'][0]['data']
    assert (attrs['maxHp'], attrs['atk'], attrs['cost'], attrs['respawnTime']) == (100, 2000, 5, 5)
    skill = row['skill_selection']['level']; assert skill['spData']['spType'] == 8
    components = native['prefabs']['trap_045_dublst']['components']
    attack = next(c['raw'] for c in components.values() if c['native_class'] == 'MeleeAttack')
    assert attack['_damageType'] == 3 and not attack['_waitForAttackEvent']
    immunities = next(c['raw']['_buffs'][0] for c in components.values() if c['native_class'] == 'PassiveBuffAbility')
    trigger = next(c['raw']['_buffs'][0] for c in native['skill_prefabs']['sktok_dublst']['components'].values()
                   if c['native_class'] == 'PassiveBuffAbility')
    assert trigger['triggerInterval'] == .5 and trigger['triggerCnt'] == 1
    force = row['raw_character']['talents'][0]['candidates'][0]['blackboard'][0]['value']; assert force == 1
    profile_path = ROOT / 'ark_emulator/consts.py'
    physics = literal_push_profile(profile_path)  # AST values only; no V1 runtime import.
    p = {'schemaVersion': 2, 'manifest': {'id': 'package/' + PREFIX + stage,
        'metadata': {'source_locks': {str(q): hashlib.sha256(q.read_bytes()).hexdigest()
                     for q in (SOURCE, Path(__file__), profile_path)},
            'native_card': row['raw_native'], 'native_skill': row['skill_selection'],
            'native_attack': attack, 'native_trigger': trigger,
            'reference_policy': {'range': 'Current source has no rangeId; front one model cell from fixed PRTS reference, hit-time sampling',
                'timing': 'Passive skill starts on deployment; native Buff first interval .5 then raw attack predelay through time.quantize; default30Hz gives15+20 ticks',
                'sp': 'Source SPtype8 is passive: preserve initial0/cap25/recovery1 but no25SP payment gate',
                'pillar': 'Fixed reference directly activates supplied possessed directional collapse at blast, independent of ordinary2000 damage',
                'physics': physics},
            'reference_url': 'https://prts.wiki/w/爆破装置',
            'whole_stage': False, 'client_verified': False}},
        'rules': [
            {'id': 'rule/' + PREFIX + 'cost', 'kind': 'rule', 'contract': 'deploy.cost',
             'implementation': {'type': 'expression', 'expression': 'inputs.base_cost'}},
            {'id': 'rule/' + PREFIX + 'environment', 'kind': 'rule', 'contract': 'damage.pipeline',
             'implementation': {'type': 'provider', 'provider': 'reference.ch9.demolition_environment'}},
            {'id': 'rule/' + PREFIX + 'members', 'kind': 'rule', 'contract': 'area.members',
             'implementation': {'type': 'provider', 'provider': 'reference.ch9.demolition_members'}},
            {'id': 'rule/' + PREFIX + 'push', 'kind': 'rule', 'contract': 'movement.displacement',
             'parameters': {'distances': physics['effect_distances'], 'speeds': physics['initial_speeds']},
             'implementation': {'type': 'provider', 'provider': 'reference.ch9.demolition_push'}}],
        'buffs': [{'id': 'buff/' + PREFIX + 'immunity', 'kind': 'buff',
                   'selection_flags': {'abnormal_flags': immunities['attributes']['abnormalFlags'],
                        'abnormal_immunes': immunities['attributes']['abnormalImmunes'],
                        'abnormal_combo_immunes': immunities['attributes']['abnormalComboImmunes']},
                   'damage_hooks': [{'phase': 'after', 'rule': 'rule/' + PREFIX + 'environment'}],
                   'metadata': {'native_inline': immunities}}],
        'abilities': [], 'entities': []}
    def area(branch, effects):
        return {'op': 'area', 'target': 'source', 'center': 'source',
            'membership_rule': 'rule/' + PREFIX + 'members',
            'selection_projection': {'defaults': deepcopy(DEFAULT_STATE)},
            'parameters': {'branch': branch, 'enemy_side': 1, 'pillar_tag': 'dupilr'}, 'effects': effects}
    effects = [area('enemy', [{'op': 'damage', 'damage_type': 'true', 'scale': 1,
        'on_success': [{'op': 'push', 'force': force, 'distance': 0, 'direction': 'source_facing',
            'rules': {'movement.displacement': 'rule/' + PREFIX + 'push'},
            'parameters': {'mass_attribute': 'mass_level', 'force_bonus_attribute': 'base_force_level'}}]}])]
    if pillar_abilities:
        assert set(pillar_abilities) == {'right', 'left', 'up', 'down'}
        for facing, ability in pillar_abilities.items():
            effects.append(area('pillar', [{'op': 'trigger_ability', 'ability': ability,
                'condition': "inputs.source.components.spatial.facing == params.facing",
                'parameters': {'facing': facing}}]))
    else:
        p['manifest']['metadata']['pending'] = ['Supply exact compiled pillar collapse ability dependency for direct pillar branch']
    effects.append({'op': 'retire', 'target': 'source', 'parameters': {'reason': 'dead'}})
    p['abilities'] = [
        {'id': BOOT, 'kind': 'ability', 'activation': {'mode': 'on_deploy'},
         'timeline': [{'at_seconds': .5, 'effect': {'op': 'trigger_ability', 'target': 'source', 'ability': BLAST}}],
         'duration_seconds': .5},
        {'id': BLAST, 'kind': 'ability', 'activation': {'mode': 'manual', 'parameters': {'auto_only': True}},
         'timeline': [{'at_seconds': attack['_preDelay'], 'effects': effects}], 'duration_seconds': attack['_preDelay']}]
    # The trigger task shares BOOT's last tick, before its finish task. Allow the
    # actual source-owned blast overlap without granting public manual use.
    p['abilities'][1]['activation']['parameters']['blocks_attacks'] = False
    p['entities'] = [{'id': BODY, 'kind': 'entity', 'tags': ['demolition', 'mechanism'], 'components': {
        'attributes': {'base': {'max_hp': 100, 'atk': 2000, 'def': 0, 'mres': 0,
                              'block_count': 0, 'mass_level': 0, 'base_force_level': 0}},
        'resources': {'hp': {'initial': 100, 'capacity': 100, 'role': 'health'},
                      'sp': {'initial': 0, 'capacity': 25, 'recovery_rate': 1}},
        'spatial': {'motion_mode': 0, 'blocking': False},
        'selection_state': {'side': 0, 'motion': 1, 'category': 2, 'unit_type': 4},
        'buffs': {'initial': ['buff/' + PREFIX + 'immunity']}, 'abilities': [BOOT, BLAST],
        'deployable': {'base_cost': 5, 'terrain': 'both', 'capacity': 0, 'cooldown_seconds': 5,
            'cooldown_start': 'deploy', 'refund_ratio': 0,
            'parameters': {'max_instances': 1, 'advanced_build_mask': 1},
            'stock': {'resource': STOCK, 'amount': 1},
            'rules': {'deploy.cost': 'rule/' + PREFIX + 'cost'}}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}}]
    return p
