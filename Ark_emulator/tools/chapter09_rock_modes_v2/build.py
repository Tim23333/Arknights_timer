"""Source-owned recovery/start occupancy and explicit hover route policy."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/enemies.native.v1.json'


def decision(inputs, params, context):
    normal = inputs['parameters']['normal']
    recovering = bool(inputs['cast_groups'].get('mode_action'))
    if recovering: return {'move': False, 'attack': False}
    busy = bool(inputs['cast_groups'].get('normal'))
    selected = bool(inputs['eligible_ids'].get('normal'))
    return {'move': normal and inputs['blocked_by'] is None and not selected and not busy,
            'attack': normal and selected and not busy}


def providers():
    from tools.chapter09_rock_gargoyle.build_v1 import providers as base
    return {**base(), 'reference.ch9.mode_decision': {'callable': decision, 'version': 'source-mode-action-occupancy-v2'}}


def build(key, *, pillar_trait_buff=None, dependency_definitions=(), profile='prts_reference'):
    from tools.chapter09_rock_gargoyle.build_v1 import build as prior
    if profile not in ('native_literal', 'prts_reference'): raise ValueError('Explicit source/reference profile required')
    p = prior(key, pillar_trait_buff=pillar_trait_buff, dependency_definitions=dependency_definitions,
              restore_profile='native_reference' if profile == 'native_literal' else 'prts_reference')
    source = json.loads(SOURCE.read_bytes()); short = key.split('_', 2)[2]
    body = p['entities'][0]['components']; ap = 'ability/ch9/' + short + '/'; bp = 'buff/ch9/' + short + '/'
    metadata = p['manifest']['metadata']; metadata['source_locks'][str(Path(__file__))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    metadata['reference_policy']['profile'] = profile
    metadata['reference_policy']['native_motion_fields'] = 'Native motion WALK is recorded; reference aerial selection is separated from explicitly ground route'
    metadata['reference_policy']['route_and_target_modes'] = {'route': 0, 'target': 1 if profile == 'prts_reference' else 0}
    metadata['reference_policy']['animation_mode_action'] = 'Owned finite ability occupancy; source frames preserved. Stun delays legal Recover start; max once and blocked gate explicit.'
    metadata['required_runtime'] = 'New independent route motion protocol; own and peer gates required'
    p['manifest']['id'] = 'package/ch9/' + short + '/source_modes_v2/' + profile
    for ability in p['abilities']:
        ability['activation']['parameters']['blocks_attacks'] = True
    behavior = p['behaviors'][0]
    if short == 'durokt':
        body['spatial']['motion_mode'] = 1 if profile == 'prts_reference' else 0
        body['spatial']['route_motion_mode'] = 0
        body['selection_state']['motion'] = 2 if profile == 'prts_reference' else 1
        body['resources']['recover_used'] = {'initial': 0, 'capacity': 1}
        parsed = source['animations'][key]['parsed']['animations']['Change']; assert parsed['duration']['frame'] == 28
        recover = ap + 'recover'
        p['abilities'].append({'id': recover, 'kind': 'ability',
            'activation': {'mode': 'manual', 'condition': 'inputs.resources.mode.current == 1 and inputs.resources.recover_used.current == 0 and inputs.source.components.runtime.blocked_by == None',
                'parameters': {'auto_only': True, 'auto_when_ready': True},
                'on_start': [{'op': 'modify_resource', 'target': 'source', 'resource': 'recover_used', 'value': 1}]},
            'duration_seconds': parsed['duration']['seconds'], 'timeline': [],
            'metadata': {'native_key': 'RecoverAnim', 'native_animation': parsed, 'ignore_silence': True, 'maxTriggerTime': 1}})
        body['abilities'].append(recover)
        for prof in behavior['decision']['profiles']:prof.setdefault('cast_groups', []).append({'key': 'mode_action', 'abilities': [recover]})
        for effect in behavior['transitions'][0]['effects']:
            if effect['op'] == 'set_motion_mode': effect['parameters'] = {'route_motion_mode': 0}
        behavior['transitions'][0]['effects'].insert(0, {'op': 'restart_behavior', 'target': 'source', 'state': 'ground',
            'parameters': {'abilities': list(body['abilities']), 'reset_attack_clock': True,
                           'initial_cooldowns': {}, 'reason': 'native_flight_disabled'}})
        entries = []
        for aid in body['abilities']:
            is_recover = aid == recover
            entries.append({'ability': aid, 'priority': 1 if is_recover else 0,
                'attack_clock': True, 'require_attack_control': True,
                'condition': "inputs.source.components.resources.mode.current == 1 and inputs.source.components.resources.recover_used.current == 0 and inputs.runtime.blocked_by == None" if is_recover else 'True',
                'parameters': {}})
        body['ability_arbitration'] = {'priority_order': 'higher_first', 'busy': 'blocking_casts', 'entries': entries}
    else:
        start = ap + 'start_flight'
        parsed = source['animations'][key]['parsed']['animations']['Start']; assert parsed['duration']['frame'] == 20
        assert parsed['events'][0]['name'] == 'OnStart' and parsed['events'][0]['frame'] == 20
        stone = next(buff for buff in p['buffs'] if buff['id'] == bp + 'stone')
        stone['on_remove'] = [{'op': 'trigger_ability', 'ability': start,
                              'condition': 'inputs.source.components.runtime.alive'}]
        fly_mode = 1 if profile == 'prts_reference' else 0
        p['abilities'].append({'id': start, 'kind': 'ability', 'activation': {'mode': 'manual',
            'parameters': {'auto_only': True}, 'on_start': [
                {'op': 'modify_resource', 'target': 'source', 'resource': 'mode', 'value': 2},
                {'op': 'set_motion_mode', 'target': 'source', 'value': fly_mode, 'parameters': {'route_motion_mode': 0}},
                {'op': 'apply_buff', 'target': 'source', 'buff': bp + 'unbalance_immune'}]},
            'duration_seconds': parsed['duration']['seconds'], 'timeline': [{'at_seconds': parsed['duration']['seconds'],
                'effect': {'op': 'apply_buff', 'target': 'source', 'buff': bp + 'reborn_complete'}}],
            'metadata': {'native_key': 'Born2Fly', 'native_Start': parsed, 'native_actions': 'Empty actions; OnStart adds dugago_reborn empty-template marker'}})
        p['buffs'].append({'id': bp + 'reborn_complete', 'kind': 'buff', 'metadata': {'native_buffKey': 'dugago_reborn', 'native_template': 'empty', 'health_effect': None}})
        body['abilities'].append(start)
        for prof in behavior['decision']['profiles']:prof.setdefault('cast_groups', []).append({'key': 'mode_action', 'abilities': [start]})
        body['spatial']['route_motion_mode'] = 0
        body['spatial']['motion_mode'] = 0
        metadata['reference_policy']['stone_heal'] = 'enemy_dugago_stone_heal is empty template plus visual; no invented recovery'
    metadata['pending'] = ['Fresh source/reference author and independent gates', 'Client Collider/harpoon/animation interruption correspondence', 'One-second pillar-break mark reference versus fixed same-source native check remains separate profile']
    return p
