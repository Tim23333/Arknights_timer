"""Read-only M7 roster gap witnesses and explicit replacement profiles."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler, Engine

OUTPUT = ROOT / 'packages/campaign/roster.profiles.json'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration(text, title):
    start = text.index(title)
    opened = text.index('{', start)
    depth = 1
    end = opened + 1
    while depth:
        if text[end] == '{':
            depth += 1
        elif text[end] == '}':
            depth -= 1
        end += 1
    return text[start:end]


def kalts_witness(profile_rule=None):
    data = load(ROOT / 'packages/campaign/squad.integrated.json')
    units = {x['id']: x for x in data['entities']}
    caster = 'unit/char_003_kalts'
    owned = 'unit/kalts_mon3tr_model'
    if profile_rule:
        data['rules'].append(deepcopy(profile_rule))
        units[caster].setdefault('rules', {})['targeting.score'] = profile_rule['id']
    def actor(identifier, alias, row, col, ratio, owner=None):
        hp = units[identifier]['components']['attributes']['base']['max_hp']
        components = {'resources': {'hp': {'initial': hp * ratio}}}
        if owner:
            components['ownership'] = {'owner': owner, 'on_owner_retire': 'retain'}
        return {'definition': identifier, 'instanceAlias': alias, 'position': {'row': row, 'col': col}, 'components': components}
    ability = next(x for x in data['abilities'] if x['id'] == 'ability/char_003_kalts/normal_attack')
    output = []
    for own_ratio, self_ratio in ((.8, .6), (.8, 1), (1, 1)):
        current = deepcopy(data)
        current['scenarioDraft'] = {'id': 'scenario/m7_kalts_priority', 'ruleset': 'ruleset/ark_standard',
            'map': {'rows': 9, 'cols': 9}, 'resources': {'dp': {'initial': 20, 'capacity': 99}}, 'initialEntities': [
                actor(caster, 'kalts', 4, 4, self_ratio), actor(owned, 'owned', 4, 5, own_ratio, 'kalts'),
                actor('unit/char_151_myrtle', 'stranger', 4, 6, .1),
                actor('unit/char_179_cgbird', 'foreign_host', 3, 4, 1), actor(owned, 'foreign', 3, 5, .05, 'foreign_host')]}
        sim = Engine.create(Compiler().compile(current))
        chosen = sim.ctx.spatial.select('kalts', ability['selector'], ability=ability)
        aliases = {sim.session.world.resolve(alias): alias for alias in ('kalts', 'owned', 'stranger', 'foreign_host', 'foreign')}
        output.append({'self_hp_ratio': self_ratio, 'owned_hp_ratio': own_ratio,
            'unrelated_hp_ratio': .1, 'foreign_owned_mon_hp_ratio': .05, 'selected': [aliases[x] for x in chosen],
            'selector_id': ability['selector']})
    return output


def exu_witness():
    data = load(ROOT / 'packages/campaign/talents.attack.json')
    data['entities'].append({'id': 'unit/m7_buddy', 'kind': 'entity', 'tags': ['player'], 'components': {
        'attributes': {'base': {'max_hp': 1000, 'atk': 100, 'def': 0, 'mres': 0}}, 'spatial': {},
        'resources': {'hp': {'initial': 1000, 'capacity_attribute': 'max_hp', 'role': 'health'}}}})
    data['scenarioDraft'].update(initialEntities=[{'definition': 'unit/char_103_angel', 'instanceAlias': 'angel', 'position': {'row': 3, 'col': 3}},
        {'definition': 'unit/m7_buddy', 'instanceAlias': 'buddy', 'position': {'row': 3, 'col': 4}}],
        dependencies=['buff/talent_angel_friend'])
    sim = Engine.create(Compiler().compile(data))
    def hp(alias):
        return {'current': sim.ctx.resources.current(alias, 'hp'), 'capacity': sim.ctx.resources.capacity(alias, 'hp')}
    result = {'self_after_birth_initial_buffs': hp('angel'), 'buddy_before_buff': hp('buddy')}
    sim.ctx.buffs.apply('angel', 'buddy', 'buff/talent_angel_friend')
    result['buddy_after_buff'] = hp('buddy')
    sim.ctx.resources.adjust('buddy', 'hp', value=1050)
    sim.ctx.buffs.remove('buddy', 'buff/talent_angel_friend')
    result['buddy_after_buff_removal'] = hp('buddy')
    sim.ctx.effects.execute('angel', ['buddy'], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 1})
    result['after_true_one_packet'] = hp('buddy')
    result['damage_accepted_amount'] = [e['payload']['amount'] for e in sim.session.events if e['type'] == 'damage.accepted'][-1]
    return result


def direction_witness():
    base = load(ROOT / 'packages/campaign/squad.integrated.json')
    selector_id = next(x['selector'] for x in base['abilities'] if x['id'] == 'ability/campaign_angel_normal')
    selector = next(x for x in base['selectors'] if x['id'] == selector_id)
    extent = max(x[1] for x in selector['region']['offsets'])
    output = []
    for rotate in (False, True):
        for facing in ('left', 'right'):
            data = deepcopy(base)
            selected = next(x for x in data['selectors'] if x['id'] == selector['id'])
            selected['region']['rotate_with_facing'] = rotate
            selected['limit'] = None  # Witness the whole geometric candidate set.
            data['entities'].append({'id': 'unit/m7_direction_enemy', 'kind': 'entity', 'tags': ['enemy', 'ground'],
                'components': {'attributes': {'base': {'max_hp': 1000, 'def': 0, 'mres': 0}}, 'spatial': {},
                    'resources': {'hp': {'initial': 1000, 'capacity': 1000, 'role': 'health'}}}})
            entries = [{'definition': 'unit/char_103_angel', 'instanceAlias': 'angel', 'position': {'row': 3, 'col': extent + 1}, 'facing': facing}]
            for side, sign in [('left', -1), ('right', 1)]:
                entries += [{'definition': 'unit/m7_direction_enemy', 'instanceAlias': side + str(distance),
                    'position': {'row': 3, 'col': extent + 1 + sign * distance}} for distance in (1, extent, extent + 1)]
            data['scenarioDraft'] = {'id': 'scenario/m7_direction_witness', 'ruleset': 'ruleset/ark_standard',
                'map': {'rows': 7, 'cols': 2 * extent + 3}, 'resources': {'dp': {'initial': 20, 'capacity': 99}}, 'initialEntities': entries}
            sim = Engine.create(Compiler().compile(data))
            ids = sim.ctx.spatial.select('angel', selector['id'])
            aliases = {sim.session.world.resolve(x['instanceAlias']): x['instanceAlias'] for x in entries}
            chosen = [aliases[x] for x in ids]
            if rotate:
                expected = {facing + str(1), facing + str(extent)}
                if set(chosen) != expected:
                    raise ValueError('rotated native grid model fails independent near/edge/outside geometry')
            output.append({'rotate_with_facing': rotate, 'facing': facing, 'range_column_extent': extent, 'selected': chosen,
                'candidate_distances': [1, extent, extent + 1]})
    return output


def build():
    dump_path = ROOT.parent / 'Ark_data/dump.cs'
    dump = dump_path.read_text(encoding='utf8')
    support = load(ROOT / 'packages/campaign/talents.support.json')['manifest']['metadata']['source_evidence']
    attacks = load(ROOT / 'packages/campaign/attacks.reference.json')
    native_kalts = next(x for x in attacks['operators'] if x['character_id'] == 'char_003_kalts')
    filters = [x['fields'] for x in native_kalts['components'].values() if '_postFilter' in x['fields']]
    if len(filters) != 1 or filters[0]['_postFilter'] != 64:
        raise ValueError('native Kalts selector identity changed')
    rule = {'id': 'rule/m7_kalts_noequip_own_or_self', 'kind': 'calculation_rule', 'contract': 'targeting.score',
        'parameters': {'preferred_token_definition': 'unit/kalts_mon3tr_model', 'fallback_group_offset': 2},
        'implementation': {'type': 'expression', 'expression':
            "context.health_ratio + (0 if inputs.candidate.id == inputs.source.id or (inputs.candidate.definition_id == params.preferred_token_definition and 'ownership' in inputs.candidate.components and inputs.candidate.components.ownership.owner == inputs.source.id) else params.fallback_group_offset) if context.healing else inputs.distance"},
        'metadata': {'status': 'explicit_noequip_semantic_model_profile', 'native_enum_64_method_verified': False,
            'does_not_remap_64_to_36': True, 'client_calibrated': False}}
    before, after = kalts_witness(), kalts_witness(rule)
    if [x['selected'] for x in after] != [['kalts'], ['owned'], ['foreign']]:
        raise ValueError('new explicit healing profile does not satisfy independent categorical expectations')
    tokens = load(ROOT / 'packages/campaign/support_tokens.reference.json')
    bird = tokens['tokens']['token_10003_cgbird_bird']
    declarations = declaration(dump, 'public enum FilterUtil.FilterType')
    methods = [line.strip() for line in dump.splitlines() if '_Filter_KALSIT_M3_SELECTOR(Entity ' in line]
    evidence = {'input_hashes': {name: sha(ROOT / name) for name in (
        'packages/campaign/squad.integrated.json', 'packages/campaign/talents.attack.json', 'packages/campaign/talents.support.json',
        'packages/campaign/support_tokens.reference.json', 'packages/campaign/attacks.reference.json')},
        'dump_sha256': sha(dump_path), 'extractor_sha256': sha(Path(__file__)),
        'direction_grid_witness': direction_witness(),
        'runtime_files_sha256': {name: sha(ROOT / name) for name in (
            'ark_sim/domains/buffs.py', 'ark_sim/domains/resources.py', 'ark_sim/domains/lifecycle.py', 'ark_sim/domains/movement.py')},
        'kalts': {'native_selector': filters[0], 'enum_declaration': declarations, 'method_declarations': methods,
            'native_methods_are_empty_stubs': all(line.endswith('{ }') for line in methods), 'frozen_model_witness': before,
            'explicit_profile_witness': after},
        'bird': {'native_root_class': bird['linked_native_components'][str(bird['entity_fields']['m_Script']['m_PathID'])]['fields'],
            'native_entity_fields': bird['entity_fields'], 'no_fixed_expiry_field_in_inspected_prefab': not any('lifeTime' in k for k in bird['entity_fields']),
            'HP_decay_template': support['templates']['periodic_damage_by_hp_ratio[skip_modifier_fix]'],
            'recharge_template': support['templates']['charge_token[born]'],
            'recharge_method_declaration': declaration(dump, 'public class Nodes.RechargeToken : ActionNode'),
            'fixed_expiry_native_method_verified': False, 'recharge_formula_native_method_verified': False},
        'exu': {'current_runtime_witness_from_frozen_content': exu_witness(),
            'historical_observation_before_M7_capacity_clamp': {'status': 'observed_in_readonly_command_before_root_fix_not_current_replay',
                'buff_removal': {'current': 1050, 'capacity': 1000}, 'following_true_one_damage_accepted': 50,
                'native_current_HP_formula_inferred': False}, 'native_blessing_components':
            load(ROOT / 'packages/campaign/talents.attack.json')['manifest']['metadata']['source']['operators']['char_103_angel']['components'],
            'current_HP_rescaling_native_method_verified': False}}
    return {'schemaVersion': 2, 'manifest': {'id': 'package/m7_roster_profiles', 'version': '1', 'metadata': {
        'status': 'explicit_model_profiles_not_native_approval', 'formal_mainline_approved': False, 'complete_operator_count': 0,
        'source_and_witness_evidence': evidence, 'unit_patches': {'unit/char_003_kalts': {'rules': {'targeting.score': rule['id']}}},
        'capacity_change_profiles': {'minimum_model_invariant': 'current <= effective_capacity immediately after mutation',
            'preserve_absolute_clamped': 'min(old_current,new_capacity)',
            'preserve_ratio': 'old_current*new_capacity/old_capacity',
            'preserve_missing_hp': 'max(0,new_capacity-(old_capacity-old_current))',
            'initialize_full_on_birth': 'new_capacity only for an explicit full-health birth policy',
            'recommended_initial_profile': 'preserve_absolute_clamped; birth behavior independently declared',
            'native_formula_verified': False},
        'bird_card_profile': {'model_birth_charge': 2, 'source_recharge_on_owner_born': True,
            'minimum_guarantee': 'death or withdraw cannot fabricate recharge without a declared profile',
            'native_add_vs_reset_vs_clamp': 'pending method body/client evidence'}}}, 'rules': [rule]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    value = build()
    if args.check:
        if load(OUTPUT) != value:
            raise ValueError('M7 profile input identity or model witness changed')
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'output': str(OUTPUT), 'status': 'explicit_model_profiles_not_native_approval'}))


if __name__ == '__main__':
    main()
