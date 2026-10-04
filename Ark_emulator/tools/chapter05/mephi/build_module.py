"""Source-bound Mephisto normal Heal and actual owned global HP-rate aura."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'packages/campaign/chapter05_sources/native.reference.json'
SOURCE_SHA = '323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5'
CORE = 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
OUT = ROOT/'packages/campaign/chapter05_boss/mephi'
UID = 'unit/ch5/mephi/6468197a2a582f8b'
AID = 'ability/ch5/mephi/normal_heal'
HS = 'selector/ch5/mephi/heal'
AS = 'selector/ch5/mephi/global_aura'
EMITTER = 'buff/ch5/mephi/global_emitter'
MEMBER = 'buff/ch5/mephi/mephi_t_healaura'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def default_state():
    return {'side': 0, 'motion': 1, 'category': 1, 'profession': 0, 'unit_type': 1,
            'abnormal_flags': [], 'abnormal_combos': [], 'target_free_flags': [], 'target_free_combos': [],
            'target_free': False, 'ally_target_free': False, 'heal_free': False, 'camouflage': False,
            'can_select_camouflage': False}


def build():
    if sha(SOURCE) != SOURCE_SHA: raise ValueError('Exact C5 source changed')
    source = json.loads(SOURCE.read_bytes())
    v = next(v for v in source['variants'].values() if v['native_enemy']['native_id'] == 'enemy_1507_mephi')
    d = v['native_enemy']['resolved']; a = d['attributes']; prefab = source['prefabs'][v['prefab_key']]
    components = prefab['components']
    def one(name):
        matches = [c for c in components.values() if c['native_class'] == name]
        if len(matches) != 1: raise ValueError('Exact native component ambiguity: '+name)
        return matches[0]['raw']
    if v['native_enemy']['native_level'] != 0 or v['native_enemy']['stage_override'] is not None or d.get('skills') or d.get('spData'):
        raise ValueError('No invented level/override/EnemySkill/SP consumers')
    if len(v['modes']) != 1 or v.get('additional_animation_drivers'):
        raise ValueError('Unconsumed modes/animation branches')
    mode = v['modes'][0]; nodes = mode['nodes']; heal = nodes['_attack']; raw = heal['raw']
    if heal['native_class'] != 'Heal' or nodes['_combat']['path_id'] != heal['path_id']:
        raise ValueError('Combat and normal slots must share the same Heal; no duplicate packet')
    if (raw['_selectTargetSource'], raw['_selectTargetTiming'], raw['_waitForAttackEvent'], raw['_preDelay'],
        raw['_isCont'], raw['_isHpRatio'], raw['_ignoreHealFree'], raw['_applyEPHeal']) != (1, 0, 1, 0, 0, 0, 0, 0):
        raise ValueError('Unexpected source heal policy')
    if raw['_activeBuffs'] or mode['raw']['_generalAbilities']: raise ValueError('Extra normal buff/general ability')
    frames = [e for e in heal['animation_binding']['events'] if e['name'] == 'OnAttack']
    if len(frames) != 1 or frames[0]['frame'] != 33 or not frames[0]['exact_authored_frame']:
        raise ValueError('Exact Heal33 required')
    cfg = one('AdvancedSelector'); aura = one('GlobalAuraAbility'); validator = one('TargetValidator')['_targetOptions']
    if (cfg['_targetSide'], cfg['_targetMotion'], cfg['_targetCategory'], cfg['_postFilter'], cfg['_maxNum'], cfg['_excludeOwner']) != (1, 3, 1, 3, 3, 0):
        raise ValueError('Exact ally CHAR, three lowest injured ratios, owner allowed required')
    if nodes['_attackTrigger']['raw']['_minTargetNum'] != 1 or one('CircleRange')['_scaleble'] != 1:
        raise ValueError('Trigger/scaled range source differs')
    root = one('Enemy'); mover = one('MoveController')
    if root['_delayToBorn'] or root['_commonAbilities'] or root['_idleWhenBorn'] or root['_canNotExit']:
        raise ValueError('Unconsumed born/general/exit source')
    if (a['maxHp'], a['atk'], a['def'], a['magicResistance'], a['baseAttackTime'], d['rangeRadius'], a['hpRecoveryPerSec'], a['spRecoveryPerSec']) != (28000, 500, 200, 60, 6, 20, 0, 0):
        raise ValueError('Exact Mephi stats differ')
    if len(aura['_buffs']) != 1 or aura['_passiveBuffs'] or aura['_interval'] != 0 or aura['_removeBuffWhenAbilityDetached'] != 1:
        raise ValueError('Additional or periodically sampled aura source')
    buff = aura['_buffs'][0]; modifiers = buff['attributes']['attributeModifiers']
    if modifiers != [{'attributeType': 13, 'formulaItem': 1, 'value': 0.0, 'loadFromBlackboard': 1, 'fetchBaseValueFromSourceEntity': 0}]:
        raise ValueError('Exact HP_RECOVERY_PER_SEC multiplier from BB required')
    bb = d['talentBlackboard']
    if bb != [{'key': 'healaura.hp_recovery_per_sec', 'value': 1.0, 'valueStr': None}]: raise ValueError('Aura BB source changed')
    if (validator['targetSide'], validator['targetMotion'], validator['targetCategory'], validator['enableAdvancedOptions']) != (1, 3, 1, 0):
        raise ValueError('Exact global ally CHAR validator required')
    circles = [g for g in prefab['geometry_sources'] if g['unity_type'] == 'CircleCollider2D' and g['gameobject_path_id'] == cfg['m_GameObject']['m_PathID']]
    if len(circles) != 1 or circles[0]['raw']['m_Radius'] != 1: raise ValueError('Exact normalized trigger radius1 required')
    # Enum texts preserve the source interpretation, not recovered method bodies.
    dump = ROOT.parent/'Ark_data/dump.cs'; text = dump.read_text(encoding='utf8')
    enums = {}
    for name in ('AttributeType', 'AttributeModifierData.AttributeModifier.FormulaItemType',
                 'FilterUtil.FilterType', 'AbilityStandard.SelectTargetSource', 'AbilityStandard.SelectTargetTiming', 'AuraAbility.SelfOption'):
        m = re.search(r'^public enum '+re.escape(name)+r'[^\n]*\n\{.*?^\}', text, re.M | re.S)
        if not m: raise ValueError('Native enum unavailable: '+name)
        enums[name] = {'line': text[:m.start()].count('\n')+1, 'raw': m.group()}
    aura_cfg = deepcopy(cfg)
    for name in ('targetSide', 'targetMotion', 'targetCategory', 'ignoreTargetFree', 'ignoreAllyTargetFree', 'ignoreHealFree', 'ignoreMotionMode',
                 'onlyIgnoreSomeOfTargetFreeCase', 'abnormalFlag', 'abnormalCombo', 'professionMask', 'checkUnitType', 'unitTypeMask'):
        if name in validator: aura_cfg['_'+name] = validator[name]
    aura_cfg.update(_needProfessionMask=0, _excludeSomeAbnormalFlags=0, _forceIgnoreCamouflage=0)
    native_rule = 'rule/ch5/mephi/native_eligibility'
    heal_rule = 'rule/ch5/mephi/injured_eligibility'
    child_inputs = {k: 'inputs.'+k for k in ('source', 'candidate', 'selector', 'parameters', 'selection_states')}
    injured_expr = ("nodes.base.accepted and 'hp' in inputs.candidate.components.resources and "
                    "inputs.candidate.components.resources.hp.current < inputs.candidate.components.resources.hp.observed_capacity and "
                    "not inputs.selection_states.candidate.heal_free and "
                    "('healing_allowed' not in inputs.candidate.components.resources.hp.spec.parameters or inputs.candidate.components.resources.hp.spec.parameters.healing_allowed)")
    # spec.parameters is optional on general CHAR resources.
    injured_expr = injured_expr.replace("('healing_allowed' not", "('parameters' not in inputs.candidate.components.resources.hp.spec or 'healing_allowed' not")
    p = {'schemaVersion': 2, 'manifest': {'id': 'package/chapter05/mephi/normal_heal_global_aura', 'requires': ['preset/ark_standard'],
        'metadata': {'required_runtime': CORE, 'builder_sha256': sha(Path(__file__)), 'source_locks': {SOURCE.relative_to(ROOT).as_posix(): SOURCE_SHA},
            'fixed_commit': '56aee3d6c5a29c3a0d192456d70d14252cbb0804', 'native_variant_id': v['variant_id'],
            'formal_approved': False, 'independent_reviewed': False, 'actual_client_verified': False, 'whole_stage_executed': False,
            'reference_policies': {
                'heal_range': 'db_scaled: normalized Circle radius1 * DBrangeRadius20, source CircleRange scalable1; point inclusive radius20',
                'heal_selection': 'injured health ratio ascending then stable actor ID; native postFilter3/max3/excludeOwner0; capture at source AT_BEGINING',
                'healing_status': 'typed native eligibility at cast; health healing_allowed/alive/active/visibility enforced at packet. Native status changes during windup need calibration',
                'aura_validator': 'relative ally CHAR motionALL; no mutant-tag filter. Basic native masks + explicit target_free/ally_target_free/camouflage policy; heal_free only on heal channel',
                'undeclared_actor_defaults': 'explicit player side0/CHAR/ground defaults; all authored C5 enemy actors override side1. No enemy-tag inference',
                'self': 'GlobalAura DEFAULT follows validator, owner allowed by healing excludeOwner0',
                'multi_source_stacking': 'explicit replaceable reference: each source owns one maxStack1 child; independent sources add MULTIPLIER contributions. Fixed stage has one Mephi',
                'aura_lifetime': 'owned permanent parent/children removed on source inactive/death; no synthetic heal or idle emit for aura',
                'windup': 'source33/30 divided by effective ASPD ratio min.01; native animation clamp and callback methods unverified',
                'source_version': 'fixed DB/stage + local frozen prefab/Spine; old enum dump version and current client alignment unverified'},
            'source_evidence': {'resolved_DB': deepcopy(d), 'mode': deepcopy(mode), 'native_heal': deepcopy(raw), 'native_selector': deepcopy(cfg),
                'native_aura': deepcopy(aura), 'native_validator': deepcopy(validator), 'BB': deepcopy(bb), 'geometry': deepcopy(prefab['geometry_sources']),
                'prefab_source': prefab['source'], 'enums': enums, 'enum_dump': {'path': str(dump), 'sha256': sha(dump)},
                'skills_priority': 'No DB EnemySkill/SP rows; sole shared Heal normal slot, interval6. No fabricated skill priority/cooldown'} }},
        'rules': [
            {'id': native_rule, 'kind': 'rule', 'contract': 'targeting.eligibility', 'implementation': {'type': 'provider', 'provider': 'model.targeting.eligibility'}},
            {'id': heal_rule, 'kind': 'calculation_rule', 'contract': 'targeting.eligibility', 'implementation': {'type': 'graph', 'nodes': [
                {'id': 'base', 'rule': native_rule, 'inputs': child_inputs}, {'id': 'injured', 'expression': injured_expr},
                {'id': 'result', 'expression': "{'accepted': nodes.injured, 'reason': 'source_injured_heal' if nodes.injured else 'native_eligibility_or_full_or_heal_free'}"}], 'output': 'nodes.result'}},
            {'id': 'rule/ch5/mephi/steering', 'kind': 'rule', 'contract': 'movement.steering', 'implementation': {'type': 'provider', 'provider': 'ark.movement.steering_velocity'}},
            {'id': 'rule/ch5/mephi/windup', 'kind': 'calculation_rule', 'contract': 'ability.windup', 'parameters': {'minimum_speed': .01},
             'implementation': {'type': 'expression', 'expression': 'inputs.timing_parameters.seconds / max(inputs.attributes.attack_speed_ratio, params.minimum_speed)'}}],
        'entities': [{'id': UID, 'kind': 'entity', 'tags': ['enemy', 'ground', 'boss'], 'metadata': {'native_reference': deepcopy(v['native_reference'])},
            'components': {'attributes': {'base': {'max_hp': 28000, 'atk': 500, 'def': 200, 'mres': 60, 'move_speed': .5,
                'attack_interval': 6, 'attack_speed_ratio': 1, 'mass_level': 3, 'block_cost': root['_blockVolume'], 'hp_recovery_per_sec': 0}},
                'resources': {'hp': {'initial': 28000, 'capacity_attribute': 'max_hp', 'role': 'health'}},
                'spatial': {'motion_mode': 0, 'steering': {'rule': 'rule/ch5/mephi/steering', 'parameters': {
                    'response_factor': mover['_steeringFactor'], 'max_acceleration': mover['_maxSteeringForce'], 'arrival_radius': .05}}},
                'selection_state': {'side': 1, 'motion': 1, 'category': 1, 'unit_type': 2},
                'lifecycle': {'policy': 'policy/ark_lifecycle', 'leak_loss': 1}, 'abilities': [AID],
                'buffs': {'initial': [EMITTER]}, 'behavior': {'machine': 'behavior/ch5/mephi/heal'}}}],
        'selectors': [
            {'id': HS, 'kind': 'selector', 'region': {'type': 'radius', 'radius': 20}, 'filters': [{'state': 'alive'}], 'limit': 3,
             'eligibility': {'rule': heal_rule, 'parameters': {'source_configuration': cfg, 'side_policy': 'relative_ally_enemy', 'neutral_policy': 'reject', 'defaults': default_state()}}},
            {'id': AS, 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'state': 'alive'}],
             'eligibility': {'rule': native_rule, 'parameters': {'source_configuration': aura_cfg, 'side_policy': 'relative_ally_enemy', 'neutral_policy': 'reject', 'defaults': default_state()}}}],
        'abilities': [{'id': AID, 'kind': 'ability', 'parameters': {'healing': True}, 'selector': HS,
            'activation': {'mode': 'automatic_attack', 'parameters': {'auto_only': True}}, 'target_capture': 'at_cast',
            'rules': {'ability.windup': 'rule/ch5/mephi/windup'},
            'timeline': [{'at_seconds': 1.1, 'effect': {'op': 'heal', 'scale': 1, 'read_mode': {'source_attributes': 'at_hit', 'target_attributes': 'at_hit'}}}]}],
        'behaviors': [{'id': 'behavior/ch5/mephi/heal', 'kind': 'behavior', 'initial': 'active', 'states': {'active': {}}, 'transitions': [],
            'decision': {'rule': 'rule/ark_behavior_decision', 'default_mode': 0, 'profiles': [{'mode': 0,
                'selectors': [{'key': 'heal', 'selector': HS}], 'cast_groups': [{'key': 'heal', 'abilities': [AID]}],
                'parameters': {'target_key': 'heal', 'stop_on_target': True, 'stop_cast_groups': ['heal']}}]}}],
        'buffs': [{'id': EMITTER, 'kind': 'buff', 'aura': {'selector': AS, 'buff': MEMBER}, 'removal': {'on_source_death': 'remove'}},
                  {'id': MEMBER, 'kind': 'buff', 'stacking': {'mode': 'independent', 'max_stacks': 1},
                   'modifiers': [{'attribute': 'hp_recovery_per_sec', 'layer': 'direct_ratio', 'value': 1}], 'removal': {'on_source_death': 'remove'}}]}
    return p


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); args = ap.parse_args()
    p = build(); raw = (json.dumps(p, ensure_ascii=False, indent=2)+'\n').encode('utf8'); dest = OUT/'model.json'
    if args.check:
        if dest.read_bytes() != raw: raise ValueError('Mephi authored source drift')
    else: OUT.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
    print(json.dumps({'sha256': sha(dest), 'heal_frames': 33, 'max_targets': 3, 'global_HP_multiplier': 2, 'core': CORE, 'formal_approved': False}))
