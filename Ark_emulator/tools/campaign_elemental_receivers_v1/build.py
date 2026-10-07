"""Reference-first ally FIRE/DARK receivers, using existing V2 contracts only."""
from copy import deepcopy
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/common_elemental_receivers/source.bson.v2.json'
TABLE = ROOT / 'ark_emulator/data_buff_table.json'
P = 'campaign/elemental_receivers/'
DARK = 'buff/' + P + 'dark'
FIRE = 'buff/' + P + 'fire'


def eligible(inputs, parameters, context):
    # World access stays at the domain boundary: these are immutable inputs.
    actor = inputs['target']
    base = actor['components'].get('selection_state', {})
    if base.get('side', 0) != 0:
        return False
    flags = set(base.get('abnormal_flags', []))
    immunes = set(base.get('abnormal_immunes', []))
    for buff in actor['components'].get('buffs', {}).get('instances', []):
        if buff.get('expires_at') is not None and context['time'] >= buff['expires_at']:
            continue
        if not buff.get('applicability', {}).get('active', True):
            continue
        definition = parameters['buff_flags'].get(buff['definition'])
        if definition is None:
            raise ValueError('Elemental receiver missing actual Buff status declaration: ' + buff['definition'])
        flags.update(definition['flags'])
        immunes.update(definition['immunes'])
    return not bool((flags - immunes) & {5, 21})  # INVINCIBLE / ELEMENT_FREE_ALL.


def frozen_recovery(inputs, parameters, context):
    now = inputs['time']
    buffs = inputs['owner']['components'].get('buffs', {}).get('instances', [])
    active = any(buff['definition'] == parameters['buff'] and
                 (buff.get('expires_at') is None or now < buff['expires_at']) and
                 buff.get('applicability', {}).get('active', True) for buff in buffs)
    if active or inputs['configured_frozen']:
        return True
    if parameters.get('base_rule'):
        return context.calculate('resource.recovery_freeze', inputs, rule_id=parameters['base_rule']).value
    return False


def no_source_pipeline(inputs, parameters, context):
    request = inputs['effect']
    value = request['fixed_amount']
    if request['damage_type'] == 'physical':
        value = max(value - request['defense'], value * .05)
    elif request['damage_type'] == 'arts':
        value *= 1 - min(100, max(0, request['resistance'])) / 100
    return {'accepted': True, 'amount': value, 'allocations': [], 'events': []}


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,
        'reference.campaign.elemental.eligible': {'callable': eligible, 'version': 'ally-explicit-live-flags-v1'},
        'reference.campaign.elemental.freeze': {'callable': frozen_recovery, 'version': 'owned-dark-sp-freeze-compose-prior-v1'},
        'reference.campaign.elemental.no_source': {'callable': no_source_pipeline, 'version': 'source-fixed-amount-target-defense-resistance-v1'}}


def no_source(amount, kind, attack_type='BUFF', ignore_sp=True):
    return {'op': 'no_source_damage', 'target': 'selected', 'fixed_amount': amount, 'damage_type': kind,
        'attack_type': attack_type, 'damage_without_modify': False, 'ignore_for_sp': ignore_sp,
        'node_is_env_damage': False, 'env_blackboard_injected': False, 'environmental': False,
        'origin': {'source': 'native-elemental-break-reference'},
        'rules': {'damage.pipeline': 'rule/' + P + 'no_source'}}


def source_values():
    table = json.loads(TABLE.read_bytes())
    answer = {}
    for name in ('ep_break_fire_char', 'ep_break_dark_char'):
        answer[name] = {key: struct.unpack('<f', struct.pack('<I', bits & 0xffffffff))[0]
                        for key, bits in table[name]['36']}
    assert answer['ep_break_fire_char'] == {'magic_resistance': -20, 'ep_fire_damage': 1200}
    assert answer['ep_break_dark_char'] == {'damage': 100, 'interval': 1, 'sp': -1}
    return answer


def module():
    values = source_values()
    source = json.loads(SOURCE.read_bytes())
    sp = source['templates']['sp_loss']['parsed']['eventToActions']['ON_BUFF_START'][0]['_buff']['attributes']['abnormalFlags']
    assert sp == ['SKILL_NOT_ACTIVATABLE', 'SP_RECOVER_STOPPED']
    fire = source['templates']['ep_break_fire_char']['parsed']['eventToActions']['ON_BUFF_START'][1]
    assert fire['_damageWithoutModify'] is False and fire['_damageType'] == 'MAGICAL'
    dark = source['templates']['periodic_magic_damage']['parsed']['eventToActions']['ON_BUFF_TRIGGER'][0]
    assert dark['_damageWithoutModify'] is False and dark['_ignoreForSp'] is True
    rules = []
    def expression(name, contract, code):
        rid = 'rule/' + P + name
        rules.append({'id': rid, 'kind': 'rule', 'contract': contract,
                      'implementation': {'type': 'expression', 'expression': code}})
        return rid
    elemental_rules = {
        'elemental.capacity': expression('capacity', 'elemental.capacity', 'inputs.parameters.capacity'),
        'elemental.loss': expression('loss', 'elemental.loss', 'inputs.request.raw_amount * (1 - inputs.parameters.resistance / 100)'),
        'elemental.recovery': expression('recovery', 'elemental.recovery', 'min(inputs.capacity, inputs.current + inputs.parameters.recovery_rate * inputs.delta_seconds)'),
        'elemental.break_duration': expression('duration', 'elemental.break_duration', 'inputs.parameters.break_duration_seconds')}
    rules += [{'id': 'rule/' + P + 'eligible', 'kind': 'rule', 'contract': 'elemental.eligibility',
               'parameters': {'buff_flags': {}}, 'implementation': {'type': 'provider', 'provider': 'reference.campaign.elemental.eligible'}},
              {'id': 'rule/' + P + 'no_source', 'kind': 'rule', 'contract': 'damage.pipeline',
               'implementation': {'type': 'provider', 'provider': 'reference.campaign.elemental.no_source'},
               'metadata': {'input_bindings': {'defense': {'entity': 'target', 'attribute': 'def'},
                                             'resistance': {'entity': 'target', 'attribute': 'mres'}}}}]
    pulse = [no_source(values['ep_break_dark_char']['damage'], 'arts'),
             {'op': 'modify_resource', 'target': 'target', 'resource': 'sp', 'delta': values['ep_break_dark_char']['sp'],
              'parameters': {'if_resource_present': True}}]
    buffs = [{'id': FIRE, 'kind': 'buff', 'duration_seconds': 10,
              'modifiers': [{'attribute': 'mres', 'layer': 'flat', 'value': values['ep_break_fire_char']['magic_resistance']}]},
             {'id': DARK, 'kind': 'buff', 'duration_seconds': 15, 'interval_seconds': 1,
              'selection_flags': {'abnormal_flags': [1, 24]}, 'effects': pulse}]
    profiles = {}
    for key, duration, buff in [('FIRE', 10, FIRE), ('DARK', 15, DARK)]:
        start = [{'op': 'apply_buff', 'target': 'target', 'buff': buff}]
        if key == 'FIRE':
            start.append(no_source(values['ep_break_fire_char']['ep_fire_damage'], 'arts', 'NORMAL', False))
        else:
            # The elemental owner callback supplies no actor source to the
            # immediate damage packet; normal Buff event callbacks cannot.
            start.extend(deepcopy(pulse))
        profiles[key] = {'capacity': 1000, 'resistance': 0, 'recovery_rate': 0,
                         'break_duration_seconds': duration, 'rules': deepcopy(elemental_rules),
                         'on_break': start, 'on_end': [{'op': 'remove_buff', 'target': 'target', 'buff': buff}]}
    return {'schemaVersion': 2, 'manifest': {'id': 'package/' + P + 'ally_v1', 'metadata': {
        'source_locks': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (SOURCE, TABLE, Path(__file__))},
        'decoded_offline_buff_values': values,
        'reference': 'https://prts.wiki/index.php?title=元素&oldid=430495',
        'reference_policy': 'Default independent EP1000/resistance0/recovery0; shared break lock and all-bar reset. Ally character/token/trap FIRE/DARK only. Native source declarations plus fixed-reference defaults; not recovered method bodies.',
        'DARK_first_trigger': 'Native waitFirstTriggerInterval=false/firstTriggerInterval0: immediate pulse then every30ticks,15s expiry.',
        'game_version_policy': 'Pinned source bytes and October2026 PRTS reference separated; post-April2026 enemy-side routing change does not alter selected ally receivers.',
        'pending': ['Independent modifier-layer and game flags/skill-proc/SP attribution review', 'Stage9/10 assembly and actual whole run'],
        'client_verified': False}}, 'rules': rules, 'buffs': buffs,
        'receiver_template': {'eligibility_rule': 'rule/' + P + 'eligible', 'elements': profiles}}


def mount(package, entities=None):
    """Bind actual receiver entities; preserve owned skills and original SP freeze."""
    data = module()
    rows = package.get('definitions')
    if rows is None:
        rows = []
        for kind in ('entities', 'buffs', 'rules', 'abilities', 'selectors', 'projectiles'):
            rows.extend(package.get(kind, []))
    selected = set(entities) if entities is not None else None
    rules = data['rules']
    for entity in rows:
        if entity.get('kind') != 'entity' or (selected is not None and entity['id'] not in selected):
            continue
        if entity['components'].get('selection_state', {}).get('side', 0) != 0:
            continue
        if 'elemental' in entity['components']:
            raise ValueError('Receiver already declared; explicit merge needed: ' + entity['id'])
        entity['components']['elemental'] = deepcopy(data['receiver_template'])
        resources = entity['components'].get('resources', {})
        if 'sp' in resources:
            spec = resources['sp']
            old = spec.get('recovery_freeze_rule') or spec.get('rules', {}).get('resource.recovery_freeze')
            rid = 'rule/' + P + 'freeze/' + entity['id'].replace('/', '_')
            rules.append({'id': rid, 'kind': 'rule', 'contract': 'resource.recovery_freeze',
                          'parameters': {'buff': DARK, **({'base_rule': old} if old else {})},
                          'dependencies': [old] if old else [],
                          'metadata': {'recovery_freeze_authority': 'final_override'},
                          'implementation': {'type': 'provider', 'provider': 'reference.campaign.elemental.freeze'}})
            spec['recovery_freeze_rule'] = rid
    # Skill-not-activatable leaves normal attacks intact, including fallback
    # attacks when an attack-replacing skill such as Chen S1 is forbidden.
    for definition in rows:
        if definition.get('kind') == 'ability':
            activation = definition.get('activation', {})
            parameters = activation.get('parameters', {})
            if activation.get('mode') == 'manual' or parameters.get('replace_attack'):
                activation['forbidden_source_flags'] = list(dict.fromkeys([*activation.get('forbidden_source_flags', []), 24]))
    if 'definitions' in package:
        package['definitions'].extend([*rules, *data['buffs']])
    else:
        package.setdefault('rules', []).extend(rules)
        package.setdefault('buffs', []).extend(data['buffs'])
    final = package.get('definitions', package.get('buffs', []))
    flags = {d['id']: {'flags': deepcopy(d.get('selection_flags', {}).get('abnormal_flags', [])),
                       'immunes': deepcopy(d.get('selection_flags', {}).get('abnormal_immunes', []))}
             for d in final if d.get('kind') == 'buff'}
    rule = next(r for r in rules if r['id'] == 'rule/' + P + 'eligible')
    rule['parameters']['buff_flags'] = flags
    return package
