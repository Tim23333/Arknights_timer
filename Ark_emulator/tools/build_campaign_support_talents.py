"""Source-backed support talent and sustained healing models, with explicit gaps."""
from __future__ import annotations
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_support_skill_recipes import raw_character
from tools.build_kalts_skill_recipe import decode_bson_document, BUFF_SOURCE
from tools.extract_campaign_animation_bindings import unity_payload

IDS = ('char_202_demkni', 'char_128_plosis', 'char_003_kalts', 'char_358_lisa', 'char_179_cgbird', 'char_400_weedy')
OUTPUT = ROOT / 'packages/campaign/talents.support.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    normalized_path = ROOT / 'packages/campaign/operators.normalized.json'
    normalized = json.loads(normalized_path.read_bytes())
    frozen = json.loads((ROOT / 'packages/campaign/roster.reference.json').read_bytes())['frozen']
    raw = unity_payload(BUFF_SOURCE.read_bytes())
    templates, spans = decode_bson_document(raw)
    keys = ('demkni_t_1', 'demkni_t_2', 'lisa_t_2', 'evade_magic', 'charge_token[born]', 'damage_scale[input]',
        'evade_physical', 'periodic_damage_by_hp_ratio[skip_modifier_fix]')
    subset = {}
    for key in keys:
        lo, hi = spans[(key,)]
        subset[key] = {'parsed': templates[key], 'offset': lo, 'raw_bson_base64': base64.b64encode(raw[lo:hi]).decode(),
            'sha256': hashlib.sha256(raw[lo:hi]).hexdigest()}
    result = {'normalized_sha256': sha(normalized_path), 'buff_template_source_sha256': sha(BUFF_SOURCE),
        'bounded_bson_decoder_sha256': sha(ROOT / 'tools/build_kalts_skill_recipe.py'),
        'extractor_sha256': sha(Path(__file__)), 'templates': subset, 'operators': {}}
    # Offline FlatBuffers research reader only. Preserve exact bytes and slots;
    # packed booleans/enums are NOT guessed from its generic integer decoder.
    sys.path.insert(0, str(ROOT.parent / 'ark_parser/enemy'))
    from extract_enemy_data import FB
    db_path = ROOT.parent / 'data/anon_textassets/buff_table352282.dat'
    db = FB(str(db_path))
    pointer = db.table_fields(db.root)[0]
    selected = {}
    for key, slot in db.read_dict(pointer + db.i32(pointer)):
        if key in ('spRecover', 'weak[inf]', 'sluggish[inf]'):
            pos = slot + db.i32(slot)
            selected[key] = {'table_offset': pos, 'field_offsets': db.table_fields(pos),
                'generic_indexed_research_decode': db.parse_table(pos)}
    if set(selected) != {'spRecover', 'weak[inf]', 'sluggish[inf]'}:
        raise ValueError('required native buff DB dependencies missing')
    result['buff_database'] = {'source_sha256': sha(db_path), 'raw_base64': base64.b64encode(db_path.read_bytes()).decode(),
        'reader_sha256': sha(ROOT.parent / 'ark_parser/enemy/extract_enemy_data.py'), 'selected': selected,
        'status': 'indexed_research_decode_packed_flags_not_normalized',
        'spRecover_priority_key_evidence': selected['spRecover']['generic_indexed_research_decode'][34],
        'dump_layout_version_gap': 'native indexed table lacks current dump remainingTimeKey; full typed layout pending'}
    for cid in IDS:
        row = next(x for x in normalized['operators'] if x['character_id'] == cid)
        path, components = raw_character(cid)
        prefab = frozen['prefab_catalog'][row['selected_skill']['level']['prefabId']]
        result['operators'][cid] = {'selected_talents': [t['selected_candidate'] for t in row['talents']],
            'profession': row['raw_character']['profession'],
            'config': row['config'], 'stats': row['stats']['model_stats'], 'selected_skill': row['selected_skill'],
            'charpack_sha256': sha(path), 'charpack_components': components, 'skill_prefab': prefab}
    return json.loads(json.dumps(result))  # indexed research keys have canonical JSON string identity.


def bb(talent):
    values = talent['blackboard']
    return {v['key']: v['value'] for v in values} if isinstance(values, list) else values


def add_sustained_healing(p, evidence, name, range_data):
    cid = 'char_128_plosis' if name == 'plosis' else 'char_179_cgbird'
    row = evidence['operators'][cid]
    level = row['selected_skill']['level']
    values = {x['key']: x['value'] for x in level['blackboard']}
    components = row['charpack_components']
    root = next(x['fields'] for x in components.values() if '_modes' in x['fields'])
    ptr = root['_modes'][1]
    if ptr['m_FileID'] != 0:
        raise ValueError('native heal mode external reference')
    mode = components[str(ptr['m_PathID'])]['fields']
    attack = components[str(mode['_attack']['m_PathID'])]['fields']
    selector = components[str(attack['_selector']['m_PathID'])]['fields']
    if selector['_maxNum'] != 3 or selector['_postFilter'] != 3 or selector['_excludeOwner'] != 0:
        raise ValueError('native sustained heal selector changed')
    actor = next(x for x in p['entities'] if x['id'] == 'unit/support_' + name)
    resources = actor['components']['resources']
    resources['mode'] = {'initial': 0, 'capacity': 1}
    resources['sp'].update(initial=level['spData']['initSp'], capacity=level['spData']['spCost'])
    sid, aid, bid = ('selector/support_' + name + '_sustained', 'ability/support_' + name + '_skill', 'buff/support_' + name + '_skill')
    p['selectors'].append({'id': sid, 'kind': 'selector', 'region': {'type': 'grid_offsets',
        'offsets': [[g['row'], g['col']] for g in range_data[level['rangeId']]['grids']], 'rotate_with_facing': True},
        'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': 3})
    modifiers = ([{'attribute': 'attack_interval', 'layer': 'flat', 'value': values['base_attack_time']}]
                 if name == 'plosis' else [{'attribute': 'atk', 'layer': 'direct_ratio', 'value': values['atk']}])
    buff = {'id': bid, 'kind': 'buff', 'duration_seconds': level['duration'], 'modifiers': modifiers,
        'on_remove': [{'op': 'modify_resource', 'target': 'source', 'resource': 'mode', 'value': 0}]}
    if name == 'cgbird':
        buff['aura'] = {'selector': sid + '_res', 'buff': bid + '_res'}
        res_selector = json.loads(json.dumps(p['selectors'][-1]))
        res_selector.update(id=sid + '_res', filters=[{'tag': 'player'}, {'state': 'alive'}], limit=None)
        p['selectors'].append(res_selector)
        p['buffs'].append({'id': bid + '_res', 'kind': 'buff', 'stacking': {'mode': 'independent'},
            'modifiers': [{'attribute': 'mres', 'layer': 'direct_ratio', 'value': values['magic_resistance']}],
            'damage_hooks': [{'phase': 'after', 'condition': "inputs.effect.damage_type == 'arts'",
                'samples': {'stream': 'imp', 'count': 1}, 'rule': 'rule/support_night_dodge'}]})
        p['rules'].append({'id': 'rule/support_night_dodge', 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
            'parameters': {'probability': values['prob']}, 'implementation': {'type': 'graph', 'nodes': [{'id': 'result', 'expression':
                "{'accepted': False, 'amount': 0, 'allocations': [], 'events': []} if inputs.samples[0].value < params.probability else inputs.effect.settlement"}], 'output': 'nodes.result'}})
    p['buffs'].append(buff)
    predelay = attack['_preDelay'] if name == 'plosis' else .9
    if name == 'cgbird':
        from tools.extract_campaign_animation_bindings import build as binding_build
        bindings = binding_build()['operators'][cid]
        modes = [x for x in bindings['modes'] if x['resolved_animation_key'] == 'Attack_C']
        if len(modes) != 1:
            raise ValueError('exact Attack_C source binding missing')
        front, back = modes[0]['bindings_by_face']['front'], modes[0]['bindings_by_face']['back']
        if front['events'] != back['events']:
            raise ValueError('direction adapter required for Night heal timing')
        predelay = next(x['seconds'] for x in front['events'] if x['name'] == 'OnAttack')
        evidence['night_skill_animation_binding'] = modes[0]
    p['abilities'] += [{'id': aid, 'kind': 'ability', 'metadata': {'native_skill_id': row['selected_skill']['skill_id'],
        'pending_native_FSM_alignment': True}, 'activation': {'mode': 'manual',
            'costs': [{'resource': 'sp', 'amount': level['spData']['spCost']}], 'on_start': [
                {'op': 'modify_resource', 'target': 'source', 'resource': 'mode', 'value': 1},
                {'op': 'apply_buff', 'target': 'source', 'buff': bid}]},
        'parameters': {'blocks_attacks': False}, 'duration_seconds': level['duration'], 'timeline': []},
        {'id': aid + '_heal', 'kind': 'ability', 'parameters': {'healing': True},
         'activation': {'mode': 'automatic_attack', 'interval_rule': 'rule/ark_attack_interval',
            'condition': 'inputs.resources.mode.current == 1'}, 'selector': sid, 'target_capture': 'each_hit',
         'timeline': [{'at_seconds': predelay, 'condition': 'inputs.resources.mode.current == 1',
            'effect': {'op': 'heal', 'scale': 1}}]}]
    actor['components']['abilities'] += [aid, aid + '_heal']
    evidence[name + '_sustained_profile'] = {'native_mode_attack': attack, 'native_selector': selector,
        'model_packet_predelay': predelay, 'mode_end_cancels_model_heal': True,
        'flat_interval_modifier': values.get('base_attack_time'), 'no_native_ramp_field_found': name == 'plosis',
        'pending': ['native_FSM_first_attack_clock_restart', 'animation_speed_scaling_at_modified_interval']}


def mon3tr_attack_overrides(reference=None):
    from tools.extract_campaign_support_token_sources import build as rebuild_token_sources
    reference = rebuild_token_sources() if reference is None else reference
    frozen = json.loads((ROOT / 'packages/campaign/support_tokens.reference.json').read_bytes())
    if frozen != reference:
        raise ValueError('exact external token source mapping identity changed')
    historical = json.loads((ROOT / 'packages/campaign/skills.kalts.json').read_bytes())
    token = deepcopy(next(x for x in historical['entities'] if x['id'] == 'unit/kalts_mon3tr_model'))
    token['components']['spatial']['blocking'] = True
    native = reference['tokens']['token_10002_kalts_mon3tr']
    raw_character = reference['token_character_table']['tokens']['token_10002_kalts_mon3tr']
    from tools.build_kalts_skill_recipe import token_stats
    stats = token_stats(raw_character)
    for source_key, model_key in [('atk', 'atk'), ('def', 'def'), ('maxHp', 'max_hp'), ('baseAttackTime', 'attack_interval'), ('blockCnt', 'block_count')]:
        if token['components']['attributes']['base'][model_key] != stats['model'][source_key]:
            raise ValueError('historical token model differs from fixed native E270 stats')
    ranges = json.loads((ROOT / 'ark_emulator/data_range_table.json').read_bytes())
    native_range = raw_character['phases'][2]['rangeId']
    selector = deepcopy(next(x for x in historical['selectors'] if x['id'] == 'selector/token_melee'))
    selector['region']['offsets'] = [[g['row'], g['col']] for g in ranges[native_range]['grids']]
    overrides = []
    for ability_id, mode_index, damage_type in [('ability/mon3tr_normal_probe', 0, 'physical'), ('ability/mon3tr_true_probe', 2, 'true')]:
        ability = deepcopy(next(x for x in historical['abilities'] if x['id'] == ability_id))
        mode = native['modes'][mode_index]
        fields = mode['attack_fields']
        if fields['_waitForAttackEvent'] != 1 or fields['_timeMode'] != 0 or fields['_selectTargetSource'] != 2 or fields['_atkScale'] != 1:
            raise ValueError('Mon3tr native attack contract changed')
        events = mode['exact_bindings']['single']['events']
        hits = [x for x in events if x['name'] == 'OnAttack']
        if len(hits) != 1:
            raise ValueError('Mon3tr one-packet attack event changed')
        ability['activation'].update(mode='automatic_attack', interval_rule='rule/ark_attack_interval')
        ability['activation']['parameters'] = {'auto_only': True}
        ability['timeline'] = [{'at_seconds': hits[0]['seconds'], 'condition': ability['activation']['condition'],
            'effect': {'op': 'damage', 'damage_type': damage_type, 'read_mode': {'source_attributes': 'at_hit'}}}]
        ability['metadata'] = {'status': 'external2025_model_profile', 'native_token_id': 'token_10002_kalts_mon3tr',
            'native_mode_index': mode_index, 'native_attack_binding': mode, 'source_version_matches_local': False,
            'pending_native_FSM_callback_and_modified_attack_speed_scaling': True,
            'historical_ability_id_retained_for_definition_override': True}
        overrides.append(ability)
    death = next(x for x in raw_character['talents'][1]['candidates'] if x['unlockCondition']['phase'] == 'PHASE_2' and x['requiredPotentialRank'] == 0)
    death_values = {x['key']: x['value'] for x in death['blackboard']}
    if death_values != {'stun': 3, 'value': 1200}:
        raise ValueError('fixed potential Mon3tr death talent changed')
    token['components'].setdefault('buffs', {}).setdefault('initial', []).append('buff/support_mon3tr_death')
    death_buff = {'id': 'buff/support_mon3tr_death', 'kind': 'buff', 'removal': {'on_target_death': 'retain', 'on_source_death': 'retain'},
        'metadata': {'native_template': 'kalts_token_death_rattle_projectile', 'projectile_callback_timing_pending': True},
        'events': [{'event': 'entity.died', 'condition': 'inputs.payload.target == context.owner.id',
            'effects': [{'op': 'damage', 'selector': 'selector/support_mon3tr_death', 'damage_type': 'true', 'scale': 0, 'additions': death_values['value']},
                        {'op': 'apply_buff', 'selector': 'selector/support_mon3tr_death', 'buff': 'buff/support_mon3tr_death_stun'}]}]}
    stun = {'id': 'buff/support_mon3tr_death_stun', 'kind': 'buff', 'duration_seconds': death_values['stun'],
        'control': {'move': False, 'attack': False, 'abilities': False, 'block': False, 'interrupt': True},
        'metadata': {'status_resistance_and_native_buff_DB_immunity_pending': True}}
    death_selector = {'id': 'selector/support_mon3tr_death', 'kind': 'selector', 'region': {'type': 'grid_offsets',
        'offsets': [[g['row'], g['col']] for g in ranges[death['rangeId']]['grids']], 'rotate_with_facing': False},
        'filters': [{'tag': 'enemy'}, {'state': 'alive'}], 'limit': None}
    return {'status': 'external2025_model_profile', 'source_version_matches_local': False,
        'historical_package_sha256': sha(ROOT / 'packages/campaign/skills.kalts.json'),
        'token_entity': token, 'ability_overrides': overrides,
        'selector': selector, 'additional_buffs': [death_buff, stun], 'additional_selectors': [death_selector],
        'fixed_native_stats': stats, 'native_death_talent': death,
        'native_source': reference}


def mon3tr_model_fixture():
    package = json.loads((ROOT / 'packages/campaign/skills.kalts.json').read_bytes())
    override = mon3tr_attack_overrides()
    package['entities'] = [override['token_entity'] if x['id'] == override['token_entity']['id'] else x for x in package['entities']]
    mapping = {x['id']: x for x in override['ability_overrides']}
    package['abilities'] = [mapping.get(x['id'], x) for x in package['abilities']]
    package['buffs'] += override['additional_buffs']
    package['selectors'] = [override['selector'] if x['id'] == override['selector']['id'] else x for x in package['selectors']]
    package['selectors'] += override['additional_selectors']
    package['manifest']['metadata']['external_attack_override'] = override
    package['manifest']['metadata']['source_version_matches_local'] = False
    package['scenarioDraft']['metadata']['external2025_model_profile'] = True
    return package


def cannon_attack_overrides(reference):
    historical = json.loads((ROOT / 'packages/campaign/skills.weedy.json').read_bytes())
    token = deepcopy(next(x for x in historical['entities'] if x['id'] == 'unit/campaign_weedy_cannon'))
    native = reference['tokens']['token_10009_weedy_cannon']
    mode = native['modes'][0]
    if mode['attack_fields']['_animKey'] != 'Attack_Loop' or mode['attack_fields']['_projectileKey'] != 'projectile_weedy_cannon':
        raise ValueError('native cannon attack binding changed')
    events = [x for x in mode['exact_bindings']['front']['events'] if x['name'] == 'OnAttack']
    if len(events) != 1:
        raise ValueError('cannon attack packet count changed')
    raw = reference['token_character_table']['tokens']['token_10009_weedy_cannon']
    raw_speed = raw['phases'][2]['attributesKeyFrames'][0]['data']['attackSpeed']
    token['components']['attributes']['base'].setdefault('attack_speed_ratio', raw_speed / 100)
    ranges = json.loads((ROOT / 'ark_emulator/data_range_table.json').read_bytes())
    selector = {'id': 'selector/support_cannon_normal', 'kind': 'selector', 'region': {'type': 'grid_offsets',
        'offsets': [[g['row'], g['col']] for g in ranges[raw['phases'][2]['rangeId']]['grids']], 'rotate_with_facing': True},
        'filters': [{'tag': 'enemy'}, {'state': 'alive'}], 'limit': 1}
    ability = {'id': 'ability/support_cannon_normal', 'kind': 'ability', 'selector': selector['id'],
        'activation': {'mode': 'automatic_attack', 'parameters': {'auto_only': True}, 'interval_rule': 'rule/ark_attack_interval'},
        'parameters': {'projectile_speed': 10}, 'timeline': [{'at_seconds': events[0]['seconds'], 'effect': {
            'op': 'damage', 'damage_type': 'physical', 'read_mode': {'source_attributes': 'at_launch'},
            'on_success': [{'op': 'push', 'force': 0, 'direction': 'source_facing',
                'rules': {'movement.displacement': 'rule/campaign_weedy_push_model'}, 'parameters': {'force_bonus_attribute': 'force_bonus'}}]}}],
        'metadata': {'status': 'external2025_model_profile', 'native_mode': mode, 'source_version_matches_local': False,
            'model_loop_signal_without_begin_handoff': True, 'native_begin_loop_and_projectile_damage_sampling_pending': True}}
    # The projectile key must have an exact source mover; no speed/name guess.
    import UnityPy
    paths = [x for x in (ROOT.parent / 'data/battle/prefabs').glob('*projectiles.ab_unpacked/CAB-*') if not x.name.endswith('.resS')]
    if len(paths) != 1:
        raise ValueError('projectile CAB missing/ambiguous')
    objects = {x.path_id: x for x in UnityPy.load(str(paths[0])).objects}
    names = {uid: x.read_typetree()['m_Name'] for uid, x in objects.items() if x.type.name == 'GameObject'}
    projectile = {str(uid): x.read_typetree() for uid, x in objects.items() if x.type.name == 'MonoBehaviour'
        and names.get(x.read_typetree()['m_GameObject']['m_PathID']) == 'projectile_weedy_cannon'}
    movers = [x['_speed'] for x in projectile.values() if '_speed' in x]
    if movers != [10.0]:
        raise ValueError('native cannon projectile speed changed')
    token['components']['abilities'].append(ability['id'])
    token['components']['deployable'] = {'capacity': native['entity_fields']['_occupiedRemainingCharacterCnt'],
        'base_cost': 5, 'cooldown_seconds': raw['phases'][2]['attributesKeyFrames'][0]['data']['respawnTime'],
        'terrain': 'both', 'parameters': {'max_instances': 1}}
    return {'token_entity': token, 'additional_abilities': [ability], 'additional_selectors': [selector],
        'historical_package_sha256': sha(ROOT / 'packages/campaign/skills.weedy.json'),
        'projectile_source_sha256': sha(paths[0]), 'projectile_native_components': projectile,
        'status': 'external2025_model_profile', 'source_version_matches_local': False}


def cannon_model_fixture():
    from tools.extract_campaign_support_token_sources import build as token_source
    p = json.loads((ROOT / 'packages/campaign/skills.weedy.json').read_bytes())
    override = cannon_attack_overrides(token_source())
    p['entities'] = [override['token_entity'] if x['id'] == override['token_entity']['id'] else x for x in p['entities']]
    p['abilities'] += override['additional_abilities']
    p['selectors'] += override['additional_selectors']
    p['manifest']['metadata']['external_normal_override'] = override
    return p


def add_night_bird(p, evidence, reference):
    from tools.normalize_campaign_operators import interpolate, half_away_integer
    cid = 'token_10003_cgbird_bird'
    raw = reference['token_character_table']['tokens'][cid]
    base, frames = interpolate(raw['phases'][2]['attributesKeyFrames'], 70)
    # Native phantom has no favor frames; do not invent player trust bonuses.
    if raw.get('favorKeyFrames'):
        raise ValueError('phantom favor policy changed')
    hp = half_away_integer(base['maxHp'])
    candidate = next(x for x in raw['talents'][1]['candidates'] if x['requiredPotentialRank'] == 0)
    values = bb(candidate)
    card_count = int(values['max_deploy_count'])
    if card_count != values['max_deploy_count'] or card_count != 2:
        raise ValueError('native bird card count changed')
    native = reference['tokens'][cid]
    if not all(x.get('native_attack_absent') for x in native['modes']) or native['entity_fields']['_occupiedRemainingCharacterCnt'] != 0:
        raise ValueError('phantom native no-attack/capacity contract changed')
    actor = next(x for x in p['entities'] if x['id'] == 'unit/support_cgbird')
    actor['components']['resources']['bird_cards'] = {'initial': values['max_deploy_count'], 'capacity': values['max_deploy_count']}
    actor['components']['abilities'].append('ability/support_night_bird')
    bird = {'id': 'unit/support_night_bird', 'kind': 'entity', 'tags': ['player', 'token', 'night_bird', 'native_heal_free'],
        'metadata': {'native_token_id': cid, 'status': 'external2025_model_profile', 'no_native_attack': True,
            'source_version_matches_local': False},
        'components': {'spatial': {'blocking': False}, 'lifecycle': {'policy': 'policy/ark_lifecycle'},
            'deployable': {'capacity': 0, 'base_cost': float(base['cost']),
            'cooldown_seconds': float(base['respawnTime']), 'terrain': 'both', 'parameters': {'max_instances': card_count}},
            'attributes': {'base': {'max_hp': hp, 'atk': 0, 'def': 0, 'mres': float(base['magicResistance']),
                'taunt_level': float(base['tauntLevel']), 'block_count': 0, 'move_speed': float(base['moveSpeed'])}},
            'resources': {'hp': {'initial': hp, 'capacity_attribute': 'max_hp', 'role': 'health', 'parameters': {'healing_allowed': False}}},
            'buffs': {'initial': ['buff/support_bird_dodge', 'buff/support_bird_drop']}, 'abilities': []}}
    p['entities'].append(bird)
    p['abilities'].append({'id': 'ability/support_night_bird', 'kind': 'ability',
        'activation': {'mode': 'manual', 'costs': [{'owner': 'source', 'resource': 'bird_cards', 'amount': 1},
            {'owner': 'battle', 'resource': 'dp', 'amount': float(base['cost'])}],
            'on_start': [{'op': 'spawn', 'definition': bird['id'], 'owner': 'source',
                'position': {'row': 7, 'col': 8}, 'parameters': {'max_owned': card_count, 'on_owner_retire': 'remove'}}]},
        'timeline': [], 'metadata': {'fixture_spawn_position_only': True, 'squad_must_parameterize_payload_position': True}})
    p['rules'] += [{'id': 'rule/support_bird_drop', 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
        'metadata': {'input_bindings': {'max_hp': {'entity': 'source', 'attribute': 'max_hp'}}},
        'parameters': {'ratio': values['hp_ratio']}, 'implementation': {'type': 'graph', 'nodes': [{'id': 'result',
            'expression': "{'accepted':True,'amount':inputs.effect.max_hp*params.ratio,'allocations':[],'events':[]}"}], 'output': 'nodes.result'}},
        {'id': 'rule/support_bird_dodge', 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
            'parameters': {'probability': values['prob']}, 'implementation': {'type': 'graph', 'nodes': [{'id': 'result', 'expression':
                "{'accepted':False,'amount':0,'allocations':[],'events':[]} if inputs.samples[0].value < params.probability else inputs.effect.settlement"}], 'output': 'nodes.result'}},
        {'id': 'rule/support_taunt_score', 'kind': 'calculation_rule', 'contract': 'targeting.score',
            'parameters': {'taunt_weight': 100000, 'blocked_weight': 1000000}, 'implementation': {'type': 'expression', 'expression':
                "context.health_ratio if context.healing else inputs.distance - (inputs.candidate.components.attributes.base.taunt_level*params.taunt_weight if 'taunt_level' in inputs.candidate.components.attributes.base else 0) - (params.blocked_weight if inputs.candidate.components.runtime.blocked_by == inputs.source.id else 0)"}}]
    p['buffs'] += [{'id': 'buff/support_bird_drop', 'kind': 'buff', 'interval_seconds': 1,
        'effects': [{'op': 'damage', 'damage_type': 'true', 'rules': {'damage.pipeline': 'rule/support_bird_drop'},
            'metadata': {'native_skip_modifier_event': True, 'source_HP_drop_profile': True}}]},
        {'id': 'buff/support_bird_dodge', 'kind': 'buff', 'damage_hooks': [{'phase': 'after', 'rule': 'rule/support_bird_dodge',
            'condition': "inputs.effect.damage_type == 'physical'", 'samples': {'stream': 'imp', 'count': 1}}]}]
    p['scenarioDraft']['resources'] = {'dp': {'initial': 20, 'capacity': 20}}
    evidence['night_bird_model'] = {'native_source': native, 'canonical_raw_character': raw, 'E270_interpolation_frames': frames,
        'max_hp_model': hp, 'native_HP_drop': evidence['templates']['periodic_damage_by_hp_ratio[skip_modifier_fix]'],
        'native_physical_dodge': evidence['templates']['evade_physical'],
        'pending': ['external2025_vs_local2026_match', 'born_recharge_card_refresh_native_clock',
            'native_taunt_priority_vs_declared_score_weights', 'skip_modifier_damage_callback_and_true_selfdamage_SP_alignment']}


def add_integration_interface(p, evidence):
    meta = p['manifest']['metadata']
    meta['unit_patches'] = {}
    for cid in IDS:
        name = cid.split('_')[-1]
        actor = next(x for x in p['entities'] if x['id'] == 'unit/support_' + name)
        components = actor['components']
        extra_resources = {k: deepcopy(v) for k, v in components['resources'].items() if k not in ('hp', 'sp')}
        meta['unit_patches']['unit/' + cid] = {'tags': actor['tags'], 'buffs': deepcopy(components.get('buffs', {'initial': []})),
            'attributes': {'sp_recovery_rate': components['attributes']['base']['sp_recovery_rate']},
            'attributes_merge_policy': 'setdefault', 'attribute_layers_append': ['sp_recovery'],
            'rules': {'attributes.effective': 'rule/support_temporal'}, 'resources': extra_resources,
            'time_resource_patch': {'resource': 'sp', 'recovery_rule': 'rule/support_time_sp', 'preserve_selector_and_freeze': True},
            'talent_abilities': [x for x in components.get('abilities', []) if x.endswith('_heal') or x == 'ability/support_night_bird'],
            'deck': {}, 'deployable': {}}
    # Replace selected definitions without changing canonical selected IDs.
    selected = {'ability/support_plosis_skill': 'ability/plosis_s2_first_packet',
        'ability/support_cgbird_skill': 'ability/cgbird_s3', 'ability/support_lisa_s3': 'ability/lisa_s3'}
    meta['skill_definition_overrides'] = {}
    for source_id, canonical_id in selected.items():
        ability = deepcopy(next(x for x in p['abilities'] if x['id'] == source_id))
        ability['id'] = canonical_id
        meta['skill_definition_overrides'][canonical_id] = ability
    base = json.loads((ROOT / 'packages/campaign/units.base.json').read_bytes())
    evidence['base_unit_artifact_sha256'] = sha(ROOT / 'packages/campaign/units.base.json')
    for cid in ('char_128_plosis', 'char_179_cgbird'):
        ability = deepcopy(next(x for x in base['abilities'] if x['id'] == 'ability/' + cid + '/normal_attack'))
        ability['activation']['condition'] = 'inputs.resources.mode.current == 0'
        meta['skill_definition_overrides'][ability['id']] = ability
    mon = evidence['mon3tr_external_attack_overrides']
    cannon = cannon_attack_overrides(mon['native_source'])
    evidence['weedy_cannon_external_attack_overrides'] = cannon
    meta['token_definition_overrides'] = {x['id']: deepcopy(x) for x in [mon['token_entity'], cannon['token_entity'],
        next(x for x in p['entities'] if x['id'] == 'unit/support_night_bird')]}
    meta['skill_definition_overrides'].update({x['id']: deepcopy(x) for x in mon['ability_overrides']})
    # Additional roots are real definitions, not metadata pretending to execute.
    p['buffs'] += deepcopy(mon['additional_buffs'])
    p['selectors'] += deepcopy(mon['additional_selectors']) + [deepcopy(mon['selector'])] + deepcopy(cannon['additional_selectors'])
    p['abilities'] += deepcopy(cannon['additional_abilities'])
    meta['integration_contract'] = {'canonical_unit_ids': True, 'attributes_setdefault_only': True,
        'preserve_existing_health_and_fixed_native_stats': True, 'preserve_owned_recovery_gate': True,
        'additional_target_rules': {'rule/support_taunt_score': 'native taunt model weights, client pending'},
        'external_token_version_match_pending': True, 'spawn_position_requires_deploy_payload': True,
        'fixture_fixed_position_spawn_does_not_prove_deploy_eligibility': True}


def build(*, require_complete=False):
    evidence = sources()
    gaps = ['native_modifier_event_SP_output_vs_accepted_heal_alignment_pending',
        'native_derived_fragile_callback_vs_packet_eligible_hook_alignment_pending', 'Nightingale_native_rng_draw_order_pending',
        'Nightingale_bird_native_card_refresh_and_target_priority_calibration_pending', 'Mon3tr_external2025_vs_local2026_version_match_pending',
        'Mon3tr_death_projectile_clock_and_status_immunity_pending', 'Ptilopsis_native_FSM_cooldown_restart_alignment_pending',
        'Weedy_cannon_default_source_recovered_normal_runtime_conversion_pending']
    if require_complete:
        raise ValueError('complete support talents unsupported: ' + '; '.join(gaps))
    p = {'schemaVersion': 2, 'status': 'partially_implemented', 'manifest': {'id': 'package/support_talents', 'version': '1',
        'metadata': {'official_unit_complete': False, 'client_validated': False, 'formal_mainline_approved': False,
            'source_evidence': evidence, 'pending_mechanics': gaps, 'model_profile': 'source_values_with_explicit_scheduler_alignment'}},
        'entities': [], 'abilities': [], 'buffs': [], 'selectors': [], 'rules': []}
    rows = evidence['operators']
    saria = bb(rows['char_202_demkni']['selected_talents'][0])
    if (saria['interval'], saria['max_stack_cnt'], saria['atk'], saria['def']) != (20, 5, .05, .04):
        raise ValueError('native Saria applicable talent changed')
    stack = evidence['templates']['demkni_t_1']['parsed']['eventToActions']['ON_BUFF_TRIGGER'][0]['_buff']
    if stack['overrideType'] != 'STACK' or stack['maxStackCnt'] != 5 or stack['lifeTimeType'] != 'INFINITY':
        raise ValueError('Saria stack semantics changed')
    p['rules'].append({'id': 'rule/support_temporal', 'kind': 'calculation_rule', 'extends': 'rule/ark_attribute_layers',
        'parameters': {'operations': {'sp_recovery': 'max_add', 'fragility': 'max_ratio', 'sluggish': 'min_ratio'}},
        'implementation': {'type': 'provider', 'provider': 'ark.attributes.time_layers'}})
    p['rules'].append({'id': 'rule/support_time_sp', 'kind': 'calculation_rule', 'contract': 'resource.recovery',
        'implementation': {'type': 'expression', 'expression': 'inputs.current + inputs.attributes.sp_recovery_rate * inputs.delta_seconds'}})
    p['buffs'].append({'id': 'buff/support_saria_stacks', 'kind': 'buff', 'stacking': {'mode': 'refresh'},
        'metadata': {'source_template': 'demkni_t_1', 'blackboard_interval_override_model': True},
        'modifiers': [{'attribute': k, 'layer': 'direct_ratio', 'value': saria[k],
            'parameters': {'time_curve': {'type': 'staircase', 'step_seconds': saria['interval'], 'max_steps': saria['max_stack_cnt']}}}
            for k in ('atk', 'def')]})
    ranges = json.loads((ROOT / 'ark_emulator/data_range_table.json').read_bytes())
    for cid in IDS:
        name = cid.split('_')[-1]
        stats = rows[cid]['stats']
        p['entities'].append({'id': 'unit/support_' + name, 'kind': 'entity', 'tags': ['player', name, 'time_sp', 'profession_' + str(rows[cid]['profession'])],
            'metadata': {'native_id': cid, 'config': rows[cid]['config'], 'complete_operator': False},
            'rules': {'attributes.effective': 'rule/support_temporal'}, 'components': {'spatial': {},
                'attributes': {'layers': ['flat', 'direct_ratio', 'final_ratio', 'sp_recovery'], 'base': {'atk': stats['atk'], 'def': stats['def'], 'mres': stats['magicResistance'],
                    'max_hp': stats['maxHp'], 'attack_interval': stats['baseAttackTime'], 'attack_speed_ratio': 1,
                    'sp_recovery_rate': stats['spRecoveryPerSec']}},
                'resources': {'hp': {'initial': stats['maxHp'], 'capacity_attribute': 'max_hp', 'role': 'health'},
                    'sp': {'initial': 0, 'capacity': 200, 'recovery_rate': 1, 'recovery_rule': 'rule/support_time_sp',
                        'parameters': {'freeze_while_cast': True, 'freeze_cast_modes': ['manual']}}},
                'abilities': []}})
    actor = lambda n: next(x for x in p['entities'] if x['id'] == 'unit/support_' + n)
    p['buffs'].append({'id': 'buff/support_saria_heal_sp', 'kind': 'buff', 'events': [
        {'event': 'healing.accepted', 'target': 'event_target', 'condition': 'inputs.payload.source == context.owner.id',
            'effects': [{'op': 'modify_resource', 'resource': 'sp', 'delta': bb(rows['char_202_demkni']['selected_talents'][1])['sp'],
                'parameters': {'if_resource_present': True, 'respect_recovery_freeze': True}}]}]})
    actor('demkni')['components']['buffs'] = {'initial': ['buff/support_saria_stacks', 'buff/support_saria_heal_sp']}
    for name, cid in [('plosis', 'char_128_plosis'), ('lisa', 'char_358_lisa')]:
        rate = bb(rows[cid]['selected_talents'][0])['sp_recovery_per_sec']
        member, emitter, sid = ('buff/support_' + name + '_sp', 'buff/support_' + name + '_sp_emitter', 'selector/support_' + name + '_sp')
        filters = [{'tag': 'player'}, {'state': 'alive'}, {'tag': 'time_sp'}]
        if name == 'lisa':
            filters.append({'tag': 'profession_' + str(rows[cid]['profession'])})
        p['selectors'].append({'id': sid, 'kind': 'selector', 'region': {'type': 'all'}, 'filters': filters, 'limit': None})
        p['buffs'] += [{'id': member, 'kind': 'buff', 'stacking': {'mode': 'independent'},
            'modifiers': [{'attribute': 'sp_recovery_rate', 'layer': 'sp_recovery', 'value': rate}]},
            {'id': emitter, 'kind': 'buff', 'aura': {'selector': sid, 'buff': member}}]
        actor(name)['components']['buffs'] = {'initial': [emitter]}
    night_talent = bb(rows['char_179_cgbird']['selected_talents'][0])
    if night_talent['magic_resistance'] != 15:
        raise ValueError('Nightingale talent changed')
    night_char = rows['char_179_cgbird']['charpack_components']
    native_aura = [r['fields'] for r in night_char.values() if r['fields'].get('_removeBuffWhenTargetLeave') == 1
        and any(b['buffKey'] == 'cgbird_t_1' for b in r['fields'].get('_buffs', []))]
    if not native_aura or any(x['_buffs'][0]['independentCharacterSource'] != 1 for x in native_aura):
        raise ValueError('Nightingale independent-source aura changed')
    p['buffs'] += [{'id': 'buff/support_night_res', 'kind': 'buff', 'stacking': {'mode': 'independent'},
        'modifiers': [{'attribute': 'mres', 'layer': 'flat', 'value': night_talent['magic_resistance']}]},
        {'id': 'buff/support_night_res_emitter', 'kind': 'buff',
         'aura': {'selector': 'selector/support_night_base_range', 'buff': 'buff/support_night_res'}}]
    actor('cgbird')['components']['buffs'] = {'initial': ['buff/support_night_res_emitter']}
    # The table's normal range, distinct from S3 expanded range.
    normalized = json.loads((ROOT / 'packages/campaign/operators.normalized.json').read_bytes())
    night = next(r for r in normalized['operators'] if r['character_id'] == 'char_179_cgbird')
    range_id = night['stats'].get('range_id')
    if range_id is None:
        # Exact normal range is recovered from the fixed raw E2 phase, never skill range fallback.
        char = json.loads((ROOT.parent / 'ark_parser/character/data/characters.json').read_bytes())['char_179_cgbird']
        range_id = char['phases'][2]['rangeId']
    p['selectors'].append({'id': 'selector/support_night_base_range', 'kind': 'selector',
        'region': {'type': 'grid_offsets', 'offsets': [[g['row'], g['col']] for g in ranges[range_id]['grids']], 'rotate_with_facing': True},
        'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': None})
    p['manifest']['metadata']['source_evidence']['night_base_range_id'] = range_id
    for name in ('plosis', 'cgbird'):
        add_sustained_healing(p, evidence, name, ranges)
    # Explicit nonstackable hook group avoids repeated multiplication when
    # independent source aura members overlap. Highest-ratio is a pure layer.
    lisa = rows['char_358_lisa']
    weak_ratio = bb(lisa['selected_talents'][1])['damage_scale'] - 1
    slow = evidence['buff_database']['selected']['sluggish[inf]']['generic_indexed_research_decode']['0']['5'][0]
    import struct
    slow_ratio = struct.unpack('<f', struct.pack('<i', slow['2']))[0]
    if (slow['0'], slow['1']) != (6, 3) or abs(slow_ratio + .8) > 1e-6:
        raise ValueError('native sluggish move-speed scalar changed')
    p['buffs'].append({'id': 'buff/support_sluggish', 'kind': 'buff', 'duration_seconds': 2,
        'metadata': {'native_buff_key': 'sluggish', 'model_status_id': True},
        'modifiers': [{'attribute': 'move_speed', 'layer': 'sluggish', 'value': slow_ratio}]})
    normal_range = json.loads((ROOT.parent / 'ark_parser/character/data/characters.json').read_bytes())['char_358_lisa']['phases'][2]['rangeId']
    delta_scale = {x['key']: x['value'] for x in lisa['selected_skill']['level']['blackboard']}['scale_delta_to_one']
    for variant, range_key, ratio in [('passive', normal_range, weak_ratio), ('s3', lisa['selected_skill']['level']['rangeId'], weak_ratio * delta_scale)]:
        sid, member, emitter = ('selector/support_lisa_' + variant, 'buff/support_lisa_' + variant + '_member', 'buff/support_lisa_' + variant + '_emitter')
        p['selectors'].append({'id': sid, 'kind': 'selector', 'region': {'type': 'grid_offsets',
            'offsets': [[g['row'], g['col']] for g in ranges[range_key]['grids']], 'rotate_with_facing': True},
            'filters': [{'tag': 'enemy'}, {'state': 'alive'}], 'limit': None})
        p['buffs'].append({'id': member, 'kind': 'buff', 'stacking': {'mode': 'independent'},
            'dependencies': ['buff/support_sluggish'], 'damage_hooks': [
                {'phase': 'after', 'rule': 'rule/support_fragility_' + variant, 'group': 'fragility', 'priority': ratio,
                 'condition': "'buff/support_sluggish' in context.target_buff_ids or 'buff/support_lisa_s3_member' in context.target_buff_ids"}],
            'modifiers': [{'attribute': 'fragile_factor', 'layer': 'fragility', 'value': ratio}] +
                ([{'attribute': 'move_speed', 'layer': 'sluggish', 'value': slow_ratio}] if variant == 's3' else [])})
        p['buffs'].append({'id': emitter, 'kind': 'buff', 'aura': {'selector': sid, 'buff': member},
            **({'duration_seconds': lisa['selected_skill']['level']['duration'], 'control': {'attack': False}} if variant == 's3' else {})})
        if variant == 'passive':
            actor('lisa')['components']['buffs']['initial'].append(emitter)
        p['rules'].append({'id': 'rule/support_fragility_' + variant, 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
            'parameters': {'source_bound_multiplier': 1 + ratio}, 'implementation': {'type': 'graph', 'nodes': [
                {'id': 'scaled', 'rule': 'rule/support_fragility_scale', 'inputs': {'source': 'inputs.source', 'target': 'inputs.target',
                    'effect': "{'settlement':inputs.effect.settlement,'multiplier':params.source_bound_multiplier,'resource':inputs.effect.resource} if 'resource' in inputs.effect else {'settlement':inputs.effect.settlement,'multiplier':params.source_bound_multiplier}",
                    'states': 'inputs.states', 'samples': 'inputs.samples'}}], 'output': 'nodes.scaled'}})
    p['rules'].append({'id': 'rule/support_fragility_scale', 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
        'implementation': {'type': 'provider', 'provider': 'ark.damage.settlement_scale'}})
    p['entities'].append({'id': 'unit/support_enemy', 'kind': 'entity', 'tags': ['enemy'],
        'rules': {'attributes.effective': 'rule/support_temporal'},
        'components': {'spatial': {}, 'attributes': {'layers': ['flat', 'direct_ratio', 'final_ratio', 'sluggish', 'fragility'],
            'base': {'max_hp': 100000, 'atk': 10, 'def': 0, 'mres': 0, 'move_speed': 1, 'fragile_factor': 1}},
            'resources': {'hp': {'initial': 100000, 'capacity': 100000, 'role': 'health'}}}})
    skill = lisa['selected_skill']['level']
    regen_scale = {x['key']: x['value'] for x in skill['blackboard']}['attack@atk_to_hp_recovery_ratio']
    friend_selector = json.loads(json.dumps(next(x for x in p['selectors'] if x['id'] == 'selector/support_lisa_s3')))
    friend_selector.update(id='selector/support_lisa_s3_regeneration', filters=[{'tag': 'player'}, {'state': 'alive'}])
    p['selectors'].append(friend_selector)
    lisa_emitter = next(x for x in p['buffs'] if x['id'] == 'buff/support_lisa_s3_emitter')
    lisa_emitter.update(interval_seconds=1, effects=[{'op': 'regenerate', 'selector': friend_selector['id'], 'scale': regen_scale}])
    evidence['lisa_regeneration_clock_profile'] = {'interval_seconds': 1, 'scale': regen_scale,
        'source': 'native charpack atk_to_hp_recovery triggerInterval1; healing accepted is not emitted',
        'half_open_terminal_pulse_pending_client': True}
    evidence['mon3tr_external_attack_overrides'] = mon3tr_attack_overrides()
    p['abilities'].append({'id': 'ability/support_lisa_s3', 'kind': 'ability',
        'activation': {'mode': 'manual', 'costs': [{'resource': 'sp', 'amount': skill['spData']['spCost']}],
            'on_start': [{'op': 'apply_buff', 'target': 'source', 'buff': 'buff/support_lisa_s3_emitter'}]},
        'duration_seconds': skill['duration'], 'timeline': []})
    actor('lisa')['components']['abilities'].append('ability/support_lisa_s3')
    actor('lisa')['components']['resources']['sp'].update(initial=skill['spData']['initSp'], capacity=skill['spData']['spCost'])
    evidence['fragility_model_installation_contract'] = {'native_scan_seconds': .029999999329447746,
        'native_nonstackable': evidence['templates']['damage_scale[input]']['parsed'],
        'hook_group': 'fragility', 'eligible_hook_priority_and_source_bound_factor': True,
        'aura_members_modify_max_ratio_and_share_nonstackable_group': True, 'sluggish_marker': 'buff/support_sluggish',
        'model_condition_evaluated_at_damage_packet_not_native_scan': True}
    # Explicit infinite injured fixtures allow cadence/selection tests without fake production stats.
    p['entities'].append({'id': 'unit/support_injured', 'kind': 'entity', 'tags': ['player', 'injured_fixture'],
        'components': {'spatial': {}, 'attributes': {'base': {'max_hp': 100000, 'mres': 10, 'def': 0}},
            'resources': {'hp': {'initial': 100, 'capacity': 100000, 'role': 'health'}}}})
    p['scenarioDraft'] = {'id': 'scenario/support_talent_fixture', 'ruleset': 'ruleset/ark_standard',
        'metadata': {'not_formal_mainline': True, 'status': 'partially_implemented'}, 'map': {'rows': 15, 'cols': 15},
        'initialEntities': [{'definition': x['id'], 'instanceAlias': x['id'].split('_')[-1],
            'position': {'row': 7, 'col': 7}, 'facing': 'right'} for x in p['entities'] if x['id'] != 'unit/support_injured']}
    add_night_bird(p, evidence, evidence['mon3tr_external_attack_overrides']['native_source'])
    add_integration_interface(p, evidence)
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    value = build()
    if args.check:
        if json.loads(OUTPUT.read_bytes()) != value:
            raise ValueError('support talent source or model identity changed')
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf8')
    print(json.dumps({'output': str(OUTPUT), 'status': 'partially_implemented', 'talent_operator_count': 6}))


if __name__ == '__main__':
    main()
