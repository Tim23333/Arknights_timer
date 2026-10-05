"""Source-native receiving marker creates before zero and clears after modifier."""
from pathlib import Path
import json
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
MARK = 'buff/ch9/dugago/pillar_break_mark'


def receiver(inputs, parameters, context):
    source = inputs['source']; now = context['time']
    owned = any(x['definition'] == parameters['pillar_trait'] and x.get('applicability', {}).get('active', True)
        and (x['expires_at'] is None or now < x['expires_at']) for x in source.get('components', {}).get('buffs', {}).get('instances', []))
    return {'accepted': True, 'effect': dict(inputs['effect']), 'effects':
        [{'op': 'apply_buff', 'buff': parameters['mark']}] if owned else []}


def skip(inputs, parameters, context):
    if inputs['depletion_event'].get('operation') != 'damage': return False
    now = context['time']
    return any(x['definition'] == parameters['mark'] and x.get('applicability', {}).get('active', True)
        and (x['expires_at'] is None or now < x['expires_at'])
        for x in inputs['target']['components'].get('buffs', {}).get('instances', []))


def providers():
    from tools.chapter09_rock_modes_v2.build import providers as base
    return {**base(), 'reference.ch9.receiving_pillar_marker': {'callable': receiver, 'version': 'fixed-native-pre-modifier-marker-v1'},
        'reference.ch9.pillar_marker_skip': {'callable': skip, 'version': 'actual-target-mark-at-zero-v1'}}


def build(*, pillar_trait, dependency_definitions, profile='native_literal'):
    from tools.chapter09_rock_modes_v2.build import build as base
    package = base('enemy_1172_dugago', pillar_trait_buff=pillar_trait, dependency_definitions=dependency_definitions, profile=profile)
    prefix = 'rule/ch9/dugago/'
    package['rules'].append({'id': prefix+'receiving_mark', 'kind': 'rule', 'contract': 'damage.request',
        'dependencies': [pillar_trait, MARK], 'parameters': {'pillar_trait': pillar_trait, 'mark': MARK},
        'implementation': {'type': 'provider', 'provider': 'reference.ch9.receiving_pillar_marker'}})
    rule = next(x for x in package['rules'] if x['id'] == prefix+'pillar_skip')
    rule['parameters'] = {'mark': MARK}; rule['dependencies'] = [MARK]
    rule['implementation']['provider'] = 'reference.ch9.pillar_marker_skip'
    owner = next(x for x in package['buffs'] if x['id'] == 'buff/ch9/dugago/pillar_check')
    owner['damage_hooks'] = [{'phase': 'receiver_request', 'rule': prefix+'receiving_mark',
        'after_effects': [{'op': 'remove_buff', 'buff': MARK}]}]
    package['buffs'].append({'id': MARK, 'kind': 'buff', 'duration_seconds': 1,
        'stacking': {'mode': 'independent', 'identity': ['definition', 'target'], 'max_stacks': 1},
        'metadata': {'native_key': 'dugago_attack_by_dupilr', 'source': 'Create before modifier, clear on applied modifier'}})
    source=json.loads((ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json').read_bytes())
    package['manifest']['metadata']['native_marker_template'] = source['bson_templates']['templates']['enemy_dugago_t[attack_by_dupilr]']['parsed']
    package['manifest']['metadata']['reference_policy']['pillar_mark'] = 'Fixed native same-modifier create/check/clear; PRTS1-second lingering policy is not silently folded in'
    package['manifest']['metadata']['pending'] = ['Fresh generic/source independent gates', 'NoSourceDamage receiving-before behavior not consumed by this actor-source marker', 'PRTS persistent1sec alternate profile separate']
    return package
