"""Source mine mode clock, SP clock and actor-sourced explosion content."""
import json
from pathlib import Path
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter07_predefines.build_ore_v1 import ROOT, SOURCE, sha


def build():
    assert sha(SOURCE) == '9ab8b1049f5e0c9d34977563ccd8ac394044f77ff8da44b9cb717f52a1b9dfcb'
    source = json.loads(SOURCE.read_bytes())
    skill = source['skill_tables']['sktok_mine']['levels'][0]
    bb = {r['key']: r['value'] for r in skill['blackboard']}
    raw = source['skill_prefabs']['sktok_mine']['components']
    selector = next(c['raw'] for c in raw.values() if c['native_class'] == 'AdvancedSelector')
    radius = next(g['raw']['m_Radius'] for g in source['skill_prefabs']['sktok_mine']['geometry_sources'] if g['unity_type'] == 'CircleCollider2D')
    stem, uid = 'ch7/predefined/mine', 'unit/ch7/predefined/mine/level1'
    rule, buff, ability, machine = 'rule/'+stem, 'buff/'+stem, 'ability/'+stem+'/explode', 'behavior/'+stem
    eligibility = {'rule': rule+'/eligibility', 'parameters': {
        'source_configuration': selector, 'side_policy': 'relative_ally_enemy',
        'neutral_policy': 'reject', 'defaults': DEFAULT_STATE}}
    return {'schemaVersion': 2, 'manifest': {'id': 'package/'+stem+'/v1',
        'requires': ['preset/ark_standard'], 'metadata': {
            'source_locks': {str(SOURCE): sha(SOURCE), str(Path(__file__).resolve()): sha(Path(__file__))},
            'pending': ['Collider overlap/contact radius and source postFilter24 interpretation',
                        'Native attack-event with empty animation timing reference',
                        'Native stock15 cards/deployment cost/redeploy join', 'independent proof and whole stage'],
            'reference_policy': 'PhysicsRange uses closed Euclidean centre radius .550000011920929 with typed source qualification. Empty-anim attack event resolves immediate at activation. Buff source order damage_scale before instantDamage applies that same incoming modifier to this explosion. Mode ready at20s and skill SP25 kept separate. After effect suicide uses retire reason dead; original source withdrawal/refund final join separate.',
            'stage_export_allowed': False}},
        'rules': [{'id': rule+'/eligibility', 'kind': 'rule', 'contract': 'targeting.eligibility',
                   'implementation': {'type': 'provider', 'provider': 'model.targeting.eligibility'}},
                  {'id': rule+'/area', 'kind': 'rule', 'contract': 'area.members',
                   'dependencies': [rule+'/eligibility'],
                   'implementation': {'type': 'provider', 'provider': 'model.area.qualified_radius'},
                   'parameters': {'radius': radius, 'eligibility': eligibility}},
                  {'id': rule+'/scale', 'kind': 'rule', 'contract': 'damage.pipeline',
                   'implementation': {'type': 'graph', 'nodes': [
                       {'id': 'value', 'expression': 'inputs.effect.settlement.amount * params.scale'},
                       {'id': 'result', 'expression': "{'accepted':inputs.effect.settlement.accepted,'amount':nodes.value,'allocations':[],'events':[]}"}],
                       'output': 'nodes.result'}, 'parameters': {'scale': bb['damage_scale']}}],
        'behaviors': [{'id': machine, 'kind': 'behavior', 'initial': 'mode0',
                      'states': {'mode0': {}, 'mode1': {}}}],
        'selectors': [{'id': 'selector/'+stem+'/trigger', 'kind': 'selector',
                       'region': {'type': 'circle', 'radius': radius},
                       'filters': [{'state': 'alive'}], 'eligibility': eligibility}],
        'buffs': [{'id': buff+'/mode_timer', 'kind': 'buff',
                   'interval_seconds': 20, 'effects': [{'op': 'transition', 'state': 'mode1'}]},
                  {'id': buff+'/vulnerable', 'kind': 'buff', 'duration_seconds': bb['duration'],
                   'stacking': {'mode': 'refresh', 'identity': ['definition', 'target'], 'max_stacks': 1},
                   'damage_hooks': [{'phase': 'after', 'rule': rule+'/scale',
                                     'condition': "inputs.effect.damage_type in ('physical','arts','true')"}]}],
        'abilities': [{'id': ability, 'kind': 'ability',
                       'activation': {'mode': 'manual', 'costs': [{'resource': 'sp', 'amount': 25}],
                                      'condition': "inputs.source.components.behavior.state == 'mode1'",
                                      'parameters': {'auto_only': True, 'auto_when_ready': True,
                                                     'requires_targets': True, 'blocks_new_activations': True}},
                       'selector': 'selector/'+stem+'/trigger', 'duration_seconds': 0,
                       'timeline': [{'at': 0, 'effect': {'op': 'area', 'target': 'source', 'center': 'source',
                           'membership_rule': rule+'/area', 'effects': [
                               {'op': 'apply_buff', 'buff': buff+'/vulnerable'},
                               {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': bb['damage'],
                                'damage_flags': {'source_attack_type': 'NORMAL', 'ignore_for_sp': False}}]}},
                                    {'at': 0, 'effect': {'op': 'retire', 'target': 'source',
                                                       'parameters': {'reason': 'dead'}}}]}],
        'entities': [{'id': uid, 'kind': 'entity', 'tags': ['device', 'native_mine'], 'components': {
            'attributes': {'base': {'max_hp': 100, 'atk': 0, 'def': 0, 'mres': 0, 'attack_speed_ratio': 1,
                                    'sp_recovery_rate': 1}},
            'resources': {'hp': {'initial': 100, 'capacity': 100, 'role': 'health'},
                          'sp': {'initial': 0, 'capacity': 25, 'recovery_rate': 1,
                                 'recovery': {'mode': 'periodic', 'interval_seconds': 1/30},
                                 'parameters': {'freeze_cast_modes': ['manual'],
                                                'freeze_while_cast': True, 'pause_at_full': True}}},
            'spatial': {'motion_mode': 0, 'blocking': False},
            'selection_state': {'side': 0, 'motion': 1, 'category': 2, 'unit_type': 4},
            'behavior': {'machine': machine, 'state': 'mode0'},
            'buffs': {'initial': [buff+'/mode_timer']}, 'abilities': [ability],
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}}]}


def main():
    out = ROOT/'packages/campaign/chapter07_predefines_consumer/mine.module.v1.json'
    assert not out.exists()
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='')
    print(json.dumps({'sha256': sha(out), 'stage_export_allowed': False}))


if __name__ == '__main__':
    main()
