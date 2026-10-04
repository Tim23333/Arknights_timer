"""Source-bound two-mode real PURE melee and .4 arts projectile attacks."""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter08_boss.build_talula_threshold_v3 import CORE, SOURCE, UNIT, sha
from tools.chapter08_boss.talula_policies_v1 import providers

PARENT = ROOT/'packages/campaign/chapter08_consumers/boss/talula.threshold.v3.reference.json'
OUT = ROOT/'packages/campaign/chapter08_consumers/boss/talula.attacks.v1.reference.json'


def build():
    assert sha(PARENT) == 'b3043f93d379d3bf43770adc08203b05f1c8eb0839a22eddf601a0e2b353e1ef'
    p = json.loads(PARENT.read_bytes())
    source = json.loads((SOURCE/'enemies.native.v1.json').read_bytes())
    v = source['variants']['enemy_1503_talula@0/5e75f6c67ed9421f']
    pf = source['prefabs'][v['prefab_key']]
    comps = pf['components']
    stem = 'rule/ch8/talula/'
    meta = p['manifest']['metadata']
    meta['source_locks'].update({x.relative_to(ROOT).as_posix(): sha(x) for x in (PARENT, Path(__file__), Path(__file__).with_name('talula_policies_v1.py'))})
    meta['partial_consumer_scope'] = 'Source two-mode melee/ranged attacks plus HP rage threshold; skills/FSM restart still pending.'
    meta['pending_required_consumers'] = ['DragonFire DB Buff recursive closure and both modes', 'DanceFire40s/160s two-mode source skill', 'FSM pending cast cancellation/restart', 'Original full map/routes/timeline integration']
    meta['reference_policy']['normal_attacks'] = 'Melee PURE scale1 ignores DEF/RES, native40frame; ranged arts literal.4000000059604645 with homing10 native30frame, current source/target attrs at impact.'
    meta['reference_policy']['normal_cycle'] = 'Shared4.5s attackclock135 ticks; TimeMode0 windup divided by ASPD with minimum.01 reference clamp.'
    meta['reference_policy']['range'] = 'DB rangeRadius2.5 chosen as actor range operand; Prefab CircleCollider2D2.0 retained as source geometry discrepancy, native body binding unverified. Closed Euclidean centre distance, configurable content.'
    p['manifest']['id'] = 'package/ch8/talula/attacks_v1'
    p['rules'] = [
        {'id': stem+'eligibility', 'kind': 'rule', 'contract': 'targeting.eligibility', 'implementation': {'type': 'provider', 'provider': 'model.targeting.eligibility'}},
        {'id': stem+'score', 'kind': 'rule', 'contract': 'targeting.score', 'implementation': {'type': 'provider', 'provider': 'reference.c8.talula.taunt'}},
        {'id': stem+'windup', 'kind': 'rule', 'contract': 'ability.windup', 'implementation': {'type': 'expression', 'expression': 'inputs.timing_parameters.seconds / max(inputs.attributes.attack_speed_ratio,.01)'}},
        {'id': stem+'behavior', 'kind': 'rule', 'contract': 'behavior.decision', 'implementation': {'type': 'provider', 'provider': 'reference.c8.talula.dual_attack'}},
        {'id': stem+'steer', 'kind': 'rule', 'contract': 'movement.steering', 'implementation': {'type': 'provider', 'provider': 'ark.movement.steering_velocity'}},
        {'id': stem+'motion', 'kind': 'rule', 'contract': 'projectile.trajectory', 'implementation': {'type': 'provider', 'provider': 'model.projectile.trajectory'}},
        {'id': stem+'collision', 'kind': 'rule', 'contract': 'projectile.collision', 'implementation': {'type': 'provider', 'provider': 'model.projectile.collision'}},
    ]
    p['abilities'], p['selectors'] = [], []
    profiles, ids = [], []
    for mode in v['modes']:
        groups, selectors = [], []
        for role in ('combat','attack'):
            node = mode['nodes']['_'+role]
            raw = node['raw']
            event = next(e for e in node['animation_binding']['events'] if e['name'] == 'OnAttack')
            assert event['frame'] == (40 if role == 'combat' else 30)
            assert raw['_damageType'] == (3 if role == 'combat' else 2)
            aid, sid = 'ability/ch8/talula/'+str(mode['index'])+'/'+role, 'selector/ch8/talula/'+str(mode['index'])+'/'+role
            ids.append(aid)
            groups.append(aid)
            selectors.append({'key': role, 'selector': sid})
            sel = {'id': sid, 'kind': 'selector', 'region': {'type': 'all', 'blocked_only': True}, 'filters': [{'state': 'alive'}], 'limit': 1}
            if role == 'attack':
                config = comps[str(raw['_selector']['m_PathID'])]['raw']
                assert (config['_targetSide'], config['_targetMotion'], config['_targetCategory'], config['_maxNum']) == (2,3,1,1)
                geometry = [c for c in pf['geometry_sources'] if c['unity_type'] == 'CircleCollider2D' and c['raw']['m_GameObject']['m_PathID'] == config['m_GameObject']['m_PathID']]
                assert len(geometry) == 1 and geometry[0]['raw']['m_Radius'] == 2
                sel['region'] = {'type': 'radius', 'radius': v['native_enemy']['resolved']['rangeRadius']}
                sel['eligibility'] = {'rule': stem+'eligibility', 'parameters': {'source_configuration': config,
                    'side_policy': 'relative_ally_enemy', 'neutral_policy': 'reject', 'defaults': deepcopy(DEFAULT_STATE)}}
                sel['metadata'] = {'native_selector': config, 'native_geometry': geometry, 'range_policy': meta['reference_policy']['range']}
            p['selectors'].append(sel)
            effect = {'op': 'damage', 'damage_type': 'true' if role == 'combat' else 'arts', 'scale': raw['_atkScale'],
                'read_mode': {'source_attributes': 'at_hit', 'target_attributes': 'at_hit'},
                'damage_flags': {'source_attack_type': 'NORMAL', 'ignore_for_sp': False}}
            if role == 'attack':
                effect['projectile_definition'] = 'projectile/ch8/talula'
            p['abilities'].append({'id': aid, 'kind': 'ability', 'selector': sid,
                'activation': {'mode': 'automatic_attack', 'condition': 'inputs.resources.mode.current == '+str(mode['index'])+' and inputs.source.components.runtime.blocked_by '+('!=' if role == 'combat' else '==')+' None', 'parameters': {'auto_only': True}},
                'target_capture': 'at_cast', 'timeline': [{'at_seconds': event['seconds'], 'effect': effect}],
                'rules': {'ability.windup': stem+'windup', 'targeting.score': stem+'score'}, 'metadata': {'source_node': node}})
        profiles.append({'mode': mode['index'], 'selectors': selectors, 'cast_groups': [{'key': 'normal', 'abilities': groups}]})
    p['behaviors'][0]['decision'] = {'rule': stem+'behavior', 'mode_resource': 'mode', 'profiles': profiles}
    c = p['entities'][0]['components']
    c['abilities'] = ids
    # Derived source immunities are strict defined DB values, unlike undefined defaults.
    dump = ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs'
    text = dump.read_text(encoding='utf8')
    for name, flag in [('STUNNED',0),('SILENCED',12),('FROZEN',16),('LEVITATE',25)]:
        assert 'public const AbnormalFlag '+name+' = '+str(flag)+';' in text
    assert 'public const AbnormalCombo SLEEPING = 0;' in text
    c['selection_state']['abnormal_immunes'] = [0,12,16,25]
    c['selection_state']['abnormal_combo_immunes'] = [0]
    meta['immunity_enum_source'] = {'path':str(dump),'sha':sha(dump),'defined_source_flags':[0,12,16,25],'defined_source_combos':[0]}
    mover = next(r['raw'] for r in comps.values() if r['native_class'] == 'MoveController')
    c['spatial'] = {'steering': {'rule': stem+'steer', 'parameters': {'response_factor': mover['_steeringFactor'], 'max_acceleration': mover['_maxSteeringForce'], 'arrival_radius': .05}}}
    projectile = source['projectiles']['projectile_enemy_talula']
    simple = next(r['raw'] for r in projectile['components'].values() if r['native_class'] == 'SimpleProjectile')
    motion = next(r['raw'] for r in projectile['components'].values() if r['native_class'] == 'AdvancedMovement')
    assert simple['_lifeTime'] == 10 and motion['_speed'] == 10 and simple['_stopWhenSourceInvalid'] == 0
    p['projectiles'] = [{'id': 'projectile/ch8/talula', 'kind': 'projectile',
        'motion': {'rule': stem+'motion', 'parameters': {'mode': 'homing', 'speed': motion['_speed']}},
        'collision': {'rule': stem+'collision', 'parameters': {'enabled': False}}, 'lifetime_seconds': simple['_lifeTime'],
        'attach_at_launch': False, 'completion_blocking': False,
        'max_hits': 1, 'can_hit_same_target': False, 'stop_after_max': True, 'stop_after_first': False,
        'lifecycle': {'source_invalid': 'retain', 'source_hidden': 'retain', 'target_invalid': 'retain_position', 'target_hidden': 'retain_position',
            'finish_on_reach': True, 'hit_on_reach': True, 'force_reach_on_expire': True, 'hit_on_expire': True},
        'metadata': {'native_projectile': projectile, 'reference_geometry': 'Homing centre to centre, source mount/spine offsets visual-only; direct path no wall collision.'}}]
    f = deepcopy(p)
    f['scenarioDraft'] = {'id': 'scene/ch8/talula/attacks_compile', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 1, 'cols': 4},
        'initialEntities': [{'definition': UNIT, 'instanceAlias': 'boss', 'position': {'row': 0, 'col': 0}}]}
    Compiler(providers=providers()).compile(f)
    return p


if __name__ == '__main__':
    p = build()
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='')
    print(json.dumps({'sha': sha(OUT), 'actual_compile': True, 'complete_boss': False}))
