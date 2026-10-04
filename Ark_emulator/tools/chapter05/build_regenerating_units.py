"""Two exact chapter5 regeneration variants; no plain-unit substitution."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'packages/campaign/chapter05_sources/native.reference.json'
SOURCE_SHA = '323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5'
CORE = 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
OUT = ROOT/'packages/campaign/chapter05_units/regenerating/model.json'
EXPECTED = {'enemy_1044_zomstr': (6000, 500, 130, 200, 26, 3.0),
            'enemy_1043_zomsbr': (2500, 250, 100, 80, 12, 1.8)}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    if sha(SOURCE) != SOURCE_SHA: raise ValueError('Exact chapter5 source drift')
    source = json.loads(SOURCE.read_bytes())
    prefix = 'ch5/regen'
    p = {'schemaVersion': 2, 'manifest': {'id': 'package/chapter05/regenerating_units',
         'requires': ['preset/ark_standard'], 'metadata': {
             'status': 'source_bound_HP_regeneration_and_melee_consumer_author_candidate',
             'required_runtime': CORE, 'builder_sha256': sha(Path(__file__)),
             'source_locks': {SOURCE.relative_to(ROOT).as_posix(): SOURCE_SHA},
             'variant_bindings': [], 'formal_approved': False, 'actual_client_verified': False,
             'whole_stage_executed': False,
             'source_policy': 'Pinned DB/stage variants and local frozen prefab/Spine closures; local asset/client version alignment remains unverified',
             'recovery_profile': 'Continuous HP += effective hp_recovery_per_sec * quantum; clamp by current max_hp; active/alive gate; no SP or skill recovery driver',
             'attack_clock_profile': 'Source OnAttack/30 divided by effective ASPD ratio with minimum .01; interval uses standard time.interval. Native scaling/callback method calibration remains pending',
             'remaining_scope': ['Full stage composition, Mephisto external aura and source/client version comparison',
                                 'Native body separation/selection collider and steering arrival radius .05 calibration',
                                 'Native animation speed clamps, interrupt/status and attack FSM method calibration']}},
         'entities': [], 'abilities': [], 'selectors': [], 'behaviors': [],
         'rules': [
             {'id': 'rule/'+prefix+'/steering', 'kind': 'rule', 'contract': 'movement.steering',
              'implementation': {'type': 'provider', 'provider': 'ark.movement.steering_velocity'}},
             {'id': 'rule/'+prefix+'/hp_recovery', 'kind': 'calculation_rule', 'contract': 'resource.recovery',
              'implementation': {'type': 'expression', 'expression': 'inputs.current + inputs.attributes.hp_recovery_per_sec * inputs.delta_seconds'}},
             {'id': 'rule/'+prefix+'/attack_windup', 'kind': 'calculation_rule', 'contract': 'ability.windup',
              'implementation': {'type': 'expression', 'expression': 'inputs.timing_parameters.seconds / max(inputs.attributes.attack_speed_ratio, params.minimum_speed)'},
              'parameters': {'minimum_speed': .01}},
         ]}
    variants = [v for v in source['variants'].values() if v['native_enemy']['native_id'] in EXPECTED]
    if len(variants) != 2: raise ValueError('Exact regeneration variant scope changed')
    for v in variants:
        native = v['native_enemy']; d = native['resolved']; a = d['attributes']; key = native['native_id']
        if native['native_level'] != 0 or native.get('stage_override') is not None:
            raise ValueError('Unexpected level/override requires separate binding')
        if d.get('skills') or d.get('talentBlackboard') or v['passive_and_skill_components'] or v.get('additional_animation_drivers'):
            raise ValueError('Unconsumed passive/skill/talent is forbidden')
        if d['motion'] != 'WALK' or d['applyWay'] != 'MELEE' or a['spRecoveryPerSec'] != 0 or a['stunImmune'] or a['silenceImmune']:
            raise ValueError('Additional source state requires a separate consumer')
        if len(v['modes']) != 1: raise ValueError('Unconsumed extra mode')
        nodes = v['modes'][0]['nodes']; combat = nodes['_combat']; raw = combat['raw']
        if nodes['_attack'].get('native_class') or nodes['_attackTrigger'].get('native_class') or combat['native_class'] != 'MeleeAttack':
            raise ValueError('Exact single melee slot required')
        if (raw['_selectTargetSource'], raw['_waitForAttackEvent'], raw['_atkScale'], raw['_damageType'], raw['_timeMode'], raw['_preDelay']) != (2, 1, 1, 1, 0, 0):
            raise ValueError('Unconsumed attack selector/timing/damage operands')
        if raw['_activeBuffs'] or raw['_extraDamageType'] or raw['_epDamageRatio'] or raw['_useDynamicAttackType']:
            raise ValueError('Extra attack payload is forbidden')
        events = [e for e in combat['animation_binding']['events'] if e['name'] == 'OnAttack']
        hp, atk, defense, regen, frame, interval = EXPECTED[key]
        if (a['maxHp'], a['atk'], a['def'], a['hpRecoveryPerSec'], a['baseAttackTime']) != (hp, atk, defense, regen, interval):
            raise ValueError('Exact HP/ATK/DEF/recovery/interval changed')
        if len(events) != 1 or events[0]['frame'] != frame or not events[0]['exact_authored_frame']:
            raise ValueError('Exact OnAttack frame changed')
        prefab = source['prefabs'][v['prefab_key']]
        allowed_classes = {'Enemy', 'MoveController', 'UnitMode', 'MeleeAttack', 'UberEffectEmitter',
                           'SingleSpineAnimator', 'SkeletonAnimation', 'ShadowController', 'FaceSwitcher', 'BoneFollower'}
        if {c['native_class'] for c in prefab['components'].values()} - allowed_classes:
            raise ValueError('Unknown component cannot be silently treated as presentation')
        root = next(c['raw'] for c in prefab['components'].values() if c['native_class'] == 'Enemy')
        mover = next(c['raw'] for c in prefab['components'].values() if c['native_class'] == 'MoveController')
        if root['_delayToBorn'] or root['_commonAbilities'] or root['_idleWhenBorn'] or root['_canNotExit']:
            raise ValueError('Unconsumed born/general/exit state')
        if v['modes'][0]['raw']['_generalAbilities'] or root['_specialBlockCondition'] != {'_type': 0, '_buffKeyPairs': [], '_filterTags': []}:
            raise ValueError('Unconsumed mode general ability or special block condition')
        uid = 'unit/'+prefix+'/'+key+'/'+v['variant_id'].split('/')[-1]
        aid, sid, bid = 'ability/'+uid, 'selector/'+uid, 'behavior/'+uid
        p['entities'].append({'id': uid, 'kind': 'entity', 'tags': ['enemy', 'ground', *d.get('enemyTags', [])],
            'metadata': {'native_variant_id': v['variant_id'], 'native_reference': deepcopy(v['native_reference']),
                         'source_hp_recovery_per_sec': regen, 'source_OnAttack_frame': frame},
            'components': {'attributes': {'base': {'max_hp': hp, 'atk': atk, 'def': defense,
                'mres': a['magicResistance'], 'move_speed': a['moveSpeed'], 'attack_interval': interval,
                'attack_speed_ratio': a['attackSpeed']/100, 'mass_level': a['massLevel'],
                'block_cost': root['_blockVolume'], 'hp_recovery_per_sec': regen}},
                'resources': {'hp': {'initial': hp, 'capacity_attribute': 'max_hp', 'role': 'health',
                    'recovery': {'mode': 'continuous'}, 'recovery_rule': 'rule/'+prefix+'/hp_recovery',
                    'parameters': {'pause_at_full': True}}},
                'spatial': {'motion_mode': 0, 'steering': {'rule': 'rule/'+prefix+'/steering',
                    'parameters': {'response_factor': mover['_steeringFactor'], 'max_acceleration': mover['_maxSteeringForce'], 'arrival_radius': .05}}},
                'selection_state': {'side': 1, 'motion': 1, 'category': 1, 'unit_type': 2},
                'lifecycle': {'policy': 'policy/ark_lifecycle', 'leak_loss': d['lifePointReduce']},
                'abilities': [aid], 'behavior': {'machine': bid}}})
        p['selectors'].append({'id': sid, 'kind': 'selector', 'region': {'type': 'all', 'blocked_only': True},
            'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': 1})
        p['abilities'].append({'id': aid, 'kind': 'ability', 'selector': sid,
            'activation': {'mode': 'automatic_attack', 'parameters': {'auto_only': True}},
            'rules': {'ability.windup': 'rule/'+prefix+'/attack_windup'}, 'target_capture': 'at_cast',
            'timeline': [{'at_seconds': events[0]['seconds'], 'effect': {'op': 'damage', 'damage_type': 'physical', 'scale': 1,
                'read_mode': {'source_attributes': 'at_hit', 'target_attributes': 'at_hit'}}}],
            'metadata': {'source_combat_path_id': combat['path_id'], 'source_node': deepcopy(combat)}})
        p['behaviors'].append({'id': bid, 'kind': 'behavior', 'initial': 'active', 'states': {'active': {}}, 'transitions': [],
            'decision': {'rule': 'rule/ark_behavior_decision', 'default_mode': 0, 'profiles': [{'mode': 0,
                'selectors': [{'key': 'normal', 'selector': sid}], 'cast_groups': [{'key': 'normal', 'abilities': [aid]}],
                'parameters': {'target_key': 'normal', 'blocked_target': True, 'stop_on_target': False, 'stop_cast_groups': ['normal']}}]}})
        p['manifest']['metadata']['variant_bindings'].append({'variant_id': v['variant_id'], 'unit_definition': uid,
            'native_reference': deepcopy(v['native_reference']), 'resolved_DB': deepcopy(d),
            'source_enemy_root': deepcopy(root), 'source_mover': deepcopy(mover), 'source_geometry': deepcopy(prefab['geometry_sources']),
            'prefab_source': deepcopy(prefab['source']), 'recovery_rate': regen, 'OnAttack_frame': frame,
            'consumer_map': {'hpRecoveryPerSec': 'effective hp_recovery_per_sec -> resource.recovery -> health bounds/lifecycle',
                             'MeleeAttack': 'blocked selector + physical at-hit packet + source OnAttack/30 + interval/ASPD clock',
                             'native_general_passives_skills': 'asserted absent; never silently skipped'}})
    return p


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); args = ap.parse_args()
    p = build(); raw = (json.dumps(p, ensure_ascii=False, indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes() != raw: raise ValueError('Regenerating module bytes drift')
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_bytes(raw)
    print(json.dumps({'sha256': sha(OUT), 'units': len(p['entities']), 'core_required': CORE, 'formal_approved': False}))
