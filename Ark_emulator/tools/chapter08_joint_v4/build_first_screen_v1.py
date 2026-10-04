"""First native28s screen cycle after real5s revival, with finite10periodic volleys."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v4_candidate'
CORE = '20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30'
SOURCE = ROOT / 'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json'
FIRE = ROOT / 'packages/campaign/chapter08_consumers/bsnake/firecommon.module.v2.json'
OUT = FIRE.with_name('first_screen.module.v1.json')
SCREEN = 'buff/ch8/source/bsnake_s[screen_attack]'
INVINCIBLE = 'buff/ch8/source/reborn_up[invincible]'
BOOST = 'buff/source/bsnake/reborn_up'
VOLLEY = 'ability/ch8/bsnake/firecommon'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    data = json.loads(SOURCE.read_bytes())
    profile = next(row for row in data['variant']['native_enemy']['resolved']['skills'] if row['prefabKey'] == 'ScreenAttack')
    bb = {row['key']: row['value'] for row in profile['blackboard']}
    assert bb == {'atk_scale': 1, 'duration': 28, 'interval': 2, 'trig_cnt': 10, 'invincible': 15}
    template = data['BSON']['templates']['enemy_bsnake_s[screen_attack]']['parsed']['eventToActions']
    assert template['ON_BUFF_FINISH'][0]['_modeIndex'] == 1 and template['ON_BUFF_FINISH'][0]['_restartFSM']
    assert template['ON_BUFF_FINISH'][1]['_buff']['attributes']['abnormalFlags'] == ['INVINCIBLE']
    p = json.loads(FIRE.read_bytes())
    entity = p['entities'][0]
    component = entity['components']
    component['resources'].update(hp={'initial': 50000, 'capacity_attribute': 'max_hp', 'role': 'health'},
                                  mode={'initial': 0, 'capacity': 3}, screen_packets={'initial': 0, 'capacity': 10})
    p['rules'].append({'id': 'rule/ch8/bsnake/first_restore', 'kind': 'rule', 'contract': 'resource.recovery',
                       'implementation': {'type': 'expression', 'expression': 'inputs.parameters.capacity * inputs.parameters.ratio'}})
    p['rules'].append({'id': 'rule/ch8/bsnake/invincible', 'kind': 'rule', 'contract': 'damage.pipeline',
                       'implementation': {'type': 'graph', 'nodes': [{'id': 'result', 'expression':
                           "{'accepted':False,'amount':0,'allocations':[],'events':[]}"}], 'output': 'nodes.result'}})
    component['behavior'] = {'machine': 'behavior/ch8/bsnake/firstscreen'}
    p['behaviors'] = [{'id': 'behavior/ch8/bsnake/firstscreen', 'kind': 'behavior',
                       'initial': 'normal', 'states': {'normal': {}, 'screen': {}, 'enraged': {}}, 'transitions': []}]
    restart = {'op': 'restart_behavior', 'target': 'self', 'state': 'enraged',
               'parameters': {'abilities': [VOLLEY], 'reset_attack_clock': True,
                              'initial_cooldowns': {}, 'reason': 'source_first_screen_finish'}}
    p['buffs'] = [
        {'id': BOOST, 'kind': 'buff', 'modifiers': [
            {'attribute': 'max_hp', 'layer': 'direct_ratio', 'value': .5},
            {'attribute': 'atk', 'layer': 'direct_ratio', 'value': .5}]},
        {'id': SCREEN, 'kind': 'buff', 'duration_seconds': bb['duration'], 'interval_seconds': bb['interval'],
         'control': {'move': False, 'block': False, 'attack': False},
         'selection_flags': {'target_free': True, 'abnormal_flags': [5]},
         'damage_hooks': [{'phase': 'after', 'rule': 'rule/ch8/bsnake/invincible'}],
         'effects': [{'op': 'trigger_ability', 'target': 'source', 'ability': VOLLEY,
                      'condition': 'inputs.source.components.resources.screen_packets.current < 10'}],
         'on_remove': [{'op': 'modify_resource', 'target': 'source', 'resource': 'mode', 'value': 1}, restart,
                       {'op': 'apply_buff', 'target': 'source', 'buff': INVINCIBLE},
                       {'op': 'emit', 'target': 'source', 'event': 'source.bsnake.hint.requested'}]},
        {'id': INVINCIBLE, 'kind': 'buff', 'duration_seconds': bb['invincible'],
         'selection_flags': {'target_free': True, 'abnormal_flags': [5]},
         'damage_hooks': [{'phase': 'after', 'rule': 'rule/ch8/bsnake/invincible'}]},
    ]
    volley = next(row for row in p['abilities'] if row['id'] == VOLLEY)
    volley['activation']['parameters'] = {'auto_only': True}
    volley['activation']['condition'] = 'inputs.resources.mode.current == 2 and inputs.resources.screen_packets.current < 10'
    volley['activation']['on_start'] = [
        {'op': 'modify_resource', 'target': 'source', 'resource': 'screen_packets', 'delta': 1},
        {'op': 'emit', 'target': 'source', 'event': 'source.bsnake.screen.volley'},
    ]
    component['rebirth'] = {'resource': 'hp', 'max_count': 1, 'delay_seconds': 5, 'restore_ratio': .5,
                            'restore_rule': 'rule/ch8/bsnake/first_restore', 'retain_buffs': [BOOST],
                            'on_begin': [{'op': 'apply_buff', 'target': 'source', 'buff': BOOST}],
                            'on_finish': [{'op': 'modify_resource', 'target': 'source', 'resource': 'mode', 'value': 2},
                                          {'op': 'transition', 'target': 'source', 'state': 'screen'},
                                          {'op': 'apply_buff', 'target': 'source', 'buff': SCREEN}]}
    p['manifest']['id'] = 'package/ch8/bsnake/first_screen_v1'
    p['manifest']['metadata'] = {
        'required_runtime': CORE, 'source_locks': {str(path): sha(path) for path in (SOURCE, FIRE, Path(__file__))},
        'source_screen_profile': profile, 'source_finish_template': template,
        'scope': 'First5s revival→native28s periodic10volley→mode1/invincible15; Hint request is observed, actual hint consumer pending',
        'source_conflict': 'RawRebornTalent hpRechargeRatio.5 plus boost.5 yields37500; PRTS current prose says100%. Literal fixedsource policy preserved for user comparison.',
        'reference_policy': 'Original three-row controlledfire module geometry; hidden represented by target_free+INVINCIBLE+movement/block/attack controls; native animation visuals emitted separately in future full consumer',
        'full_boss_complete': False, 'whole_stage_executed': False, 'client_verified': False,
    }
    return p


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_bsnake.screen_policy_v1 import providers
    assert implementation_digest() == CORE
    p = build()
    fixture = deepcopy(p)
    fixture['scenarioDraft'] = {'id': 'scene/bsnake/firstscreen_compile', 'ruleset': 'ruleset/ark_standard',
                                'map': {'rows': 5, 'cols': 8}, 'initialEntities': [
                                    {'definition': p['entities'][0]['id'], 'instanceAlias': 'boss', 'position': {'row': 2, 'col': 6}}]}
    Compiler(providers=providers()).compile(fixture)
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'actual_compile': True}))
