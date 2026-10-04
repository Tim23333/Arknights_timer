"""Exact Talula once-only HP consumer; remaining Boss skills explicitly pending."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest

CORE = '3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
SOURCE = ROOT/'packages/campaign/chapter08_source_prepare/integration'
OUT = ROOT/'packages/campaign/chapter08_consumers/boss/talula.threshold.v3.reference.json'
VID = 'enemy_1503_talula@0/5e75f6c67ed9421f'
UNIT = 'unit/ch8/talula/5e75f6c67ed9421f'
RAGE = 'buff/ch8/talula/ftrtal_t[rage]'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    assert implementation_digest() == CORE
    paths = [SOURCE/'source.plan.v1.json', SOURCE/'enemies.native.v1.json', Path(__file__)]
    pins = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    assert pins[paths[0].relative_to(ROOT).as_posix()] == '9fd95c8f85d4cd464976954c08f97a40a9f855cb3dca23bcd73c6f403d779a66'
    assert pins[paths[1].relative_to(ROOT).as_posix()] == '9b2a5b1b0d2dfe623421596181a3fc6462ccd4f9cf660cba6f4e75120600941e'
    plan, source = [json.loads(p.read_bytes()) for p in paths[:2]]
    v = plan['variants'][VID]
    resolved = v['native_enemy']['resolved']
    pf = source['prefabs'][resolved['prefabKey']]
    comps = pf['components']
    root = next(c for c in comps.values() if c['native_class'] == 'Enemy')
    half = comps['-6202890692967067911']
    checker = comps[str(half['raw']['_checker']['m_PathID'])]
    assert half['native_class'] == 'ToggleableOnlyOncePassiveBuffAbility'
    assert checker['native_class'] == 'HpRatioToggleChecker'
    assert checker['raw']['_maxHpRatio'] == .5 and checker['raw']['_useLTForMax'] == 0
    assert checker['raw']['_minHpRatio'] == checker['raw']['_restoreDelay'] == 0
    assert half['raw']['_setToggleFalseOnDetached'] == half['raw']['_isInverseToggle'] == 0
    assert not half['raw']['_buffsWhenToggleOff'] and len(half['raw']['_buffs']) == 1
    buff = half['raw']['_buffs'][0]
    assert buff['buffKey'] == 'ftrtal_t[rage]' and buff['templateKey'] == 'switch_mode_restart_fsm'
    assert buff['lifeTimeType'] == 2 and buff['lifeTime'] == 0 and buff['maxStackCnt'] == 1
    assert buff['blackboard'] == [{'key': 'mode', 'value': 1.0, 'valueStr': ''}]
    mods = buff['attributes']['attributeModifiers']
    assert [(m['attributeType'], m['formulaItem'], m['loadFromBlackboard']) for m in mods] == [(2, 1, 1), (3, 1, 1)]
    bb = {r['key']: r['value'] for r in resolved['talentBlackboard']}
    assert bb == {'halfhp.def': 1.0, 'halfhp.magic_resistance': .8, 'halfhp.hp_ratio': .5}
    switch = source['bson_templates']['templates']['switch_mode_restart_fsm']
    assert switch['document_sha256'] == '453784345b492d6e7f409caf22c60ed195df097749d07dc83555a539093f0ad7'
    attrs = resolved['attributes']
    policy = {
        'source_checker': '0 <= HP/maxHP <= .5; OnlyOnce parent latches after first match despite checker.toggleOnce0.',
        'latch_recipe': 'Default→half only transition, permanent max1 rage Buff, explicit mode resource1.',
        'threshold_denominator': 'Source base max_hp50000; this partial consumer has no maxHP-changing dependencies. Full integration must consume effective maxHP if any such modifier is introduced.',
        'threshold_clock': 'Existing V2 behavior boundary checks HP after command effects, before attack decision; native subframe ordering remains replaceable.',
        'modifiers': 'formulaItem1 percent DEF+1 and RES+.8; source DEF700/RES50 become1400/90.',
        'restart_FSM': 'State/mode changes implemented; cast cancellation and restart of full attack/skill profiles pending complete Boss integration.',
        'client_verified': False, 'native_method_bodies_verified': False,
    }
    p = {'schemaVersion': 2, 'manifest': {'id': 'package/ch8/talula/threshold_v3', 'requires': ['preset/ark_standard'], 'metadata': {
        'source_locks': pins, 'required_runtime': CORE, 'variant': VID, 'native_reference': v['native_reference'],
        'native_resolved': resolved, 'source_root': root, 'source_half': half, 'source_checker': checker,
        'source_switch_template': switch, 'reference_policy': policy,
        'partial_consumer_scope': 'HP threshold/rage modifiers/mode latch only; not a complete Boss entity or stage-admitted module.',
        'pending_required_consumers': ['Both mode combat and ranged attacks', 'DragonFire loadFromDB buff and two mode selectors',
            'DanceFire source40s/160s cooldown/area/animation in both modes', 'Actual FSM cast cancellation/restart', 'Full original map/routes/timeline integration'],
        'whole_stage_executed': False, 'complete_boss': False}},
        'entities': [{'id': UNIT, 'kind': 'entity', 'tags': ['enemy', 'ground', 'boss'], 'components': {
            'attributes': {'base': {'max_hp': attrs['maxHp'], 'atk': attrs['atk'], 'def': attrs['def'], 'mres': attrs['magicResistance'],
                'move_speed': attrs['moveSpeed'], 'attack_interval': attrs['baseAttackTime'], 'attack_speed_ratio': attrs['attackSpeed']/100,
                'mass_level': attrs['massLevel'], 'block_cost': root['raw']['_blockVolume']}},
            'resources': {'hp': {'initial': attrs['maxHp'], 'capacity_attribute': 'max_hp', 'role': 'health'}, 'mode': {'initial': 0, 'capacity': 1}},
            'selection_state': {'side': 1, 'motion': 1, 'category': 1, 'unit_type': 2}, 'spatial': {},
            'lifecycle': {'policy': 'policy/ark_lifecycle', 'leak_loss': resolved['lifePointReduce']},
            'behavior': {'machine': 'behavior/ch8/talula/threshold'}}}],
        'buffs': [{'id': RAGE, 'kind': 'buff', 'stacking': {'mode': 'max', 'max_stacks': 1},
            'modifiers': [{'attribute': 'def', 'layer': 'direct_ratio', 'value': bb['halfhp.def']},
                {'attribute': 'mres', 'layer': 'direct_ratio', 'value': bb['halfhp.magic_resistance']}],
            'metadata': {'native_inline_buff': buff}}],
        'behaviors': [{'id': 'behavior/ch8/talula/threshold', 'kind': 'behavior', 'initial': 'default',
            'states': {'default': {}, 'half': {}}, 'transitions': [{'from': 'default', 'to': 'half',
                'condition': 'inputs.resources.hp.current > 0 and inputs.resources.hp.current <= inputs.source.components.attributes.base.max_hp * params.ratio',
                'parameters': {'ratio': bb['halfhp.hp_ratio']}, 'effects': [
                    {'op': 'modify_resource', 'target': 'self', 'resource': 'mode', 'value': 1},
                    {'op': 'apply_buff', 'target': 'self', 'buff': RAGE}]}]}]}
    fixture = dict(p)
    fixture['scenarioDraft'] = {'id': 'scene/ch8/talula/threshold_compile', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 1, 'cols': 1},
        'initialEntities': [{'definition': UNIT, 'instanceAlias': 'boss', 'position': {'row': 0, 'col': 0}}]}
    Compiler().compile(fixture)
    assert pins == {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    return p


if __name__ == '__main__':
    p = build()
    assert not OUT.exists()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='')
    print(json.dumps({'sha': sha(OUT), 'actual_compile': True, 'complete_boss': False}))
