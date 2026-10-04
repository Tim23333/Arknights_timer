"""Record exact source dependencies and remaining whole-Boss consumers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json'
OUT = ROOT / 'packages/campaign/chapter08_consumers/bsnake/requirements.v2.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    data = json.loads(SOURCE.read_bytes())
    assert data['source_modes_count'] == 4
    skill = {row['prefabKey']: row for row in data['variant']['native_enemy']['resolved']['skills']}
    screen = {row['key']: row['value'] for row in skill['ScreenAttack']['blackboard']}
    assert screen == {'atk_scale': 1, 'duration': 28, 'interval': 2, 'trig_cnt': 10, 'invincible': 15}
    components = data['prefab']['components']
    templates = data['BSON']['templates']
    raw_reborn = data['RebornTalent']['raw']
    assert raw_reborn['_maxRespawnCnt'] == 2 and raw_reborn['_hpRechargeRatio'] == .5
    assert raw_reborn['_extraRebornDataPresets'][0]['hpRechargeRatio'] == 0
    modes = []
    for row in data['source_hook_resolved_modes']:
        mode = row['raw']['raw']
        modes.append({'index': row['index'], 'native_mode': mode,
                      'resolved_attack_nodes': row['raw']['nodes'],
                      'resolved_animations': row['resolved_animations'],
                      'general_abilities': [components[str(ref['m_PathID'])]
                                            for ref in mode['_generalAbilities']]})
    graph = []
    for name, row in templates.items():
        events = row['parsed']['eventToActions']
        graph.append({'template': name, 'document_sha256': row['document_sha256'],
                      'event_nodes': {event: [{'class': node['$type'].split('+')[-1].split(',')[0],
                                             'raw': node} for node in nodes]
                                      for event, nodes in events.items()}})
    requirements = [
        {'id': 'normal_attacks', 'source': 'modes0/1 melee combat and unblocked attack; OnAttack frame31',
         'status': 'consumer_pending', 'expected': 'PURE ATK770 before boost, sourceATK1155 after boost, then dragon_fire application'},
        {'id': 'burned_source_protection', 'source': 'enemy_bsnake_t[protect] ON_TAKE_DAMAGE CheckContainsBuff MODIFIER_SOURCE then DamageScale',
         'status': 'consumer_pending', 'expected': 'damage factor 1-.5 only when actual damage source has live dragon_fire; silenceability preserved'},
        {'id': 'first_rebirth', 'source': 'RebornTalent ratio.5 plus reborn_up maxHP/ATK .5',
         'status': 'generic_source_gate_passed_boss_composition_pending', 'expected': 'HP0 waiting; capacity75000, first restore37500, ATK1155'},
        {'id': 'first_screen', 'source': 'mode2 screen Buff/28s/10x2s/invincible15',
         'status': 'full_buff_graph_pending', 'expected': 'owned periodic screen actions while HP0 waiting; invincible15; mode1 resume plus wave track/release source controls'},
        {'id': 'final_screen', 'source': 'mode3 restore0; final_screen_attack ON_BUFF_FINISH InstantKill skipRebornFalse',
         'status': 'generic_source_gate_passed_boss_composition_pending', 'expected': 'HP0 finite28s, ten periodic volleys, real completion Buff and once death; no positiveHP workaround'},
        {'id': 'ignite', 'source': 'Ignite19/19 chosen mode0/1 components and selectors',
         'status': 'consumer_pending', 'expected': 'actual qualified target selection, exact animation hook and dynamic dragon_fire'},
        {'id': 'dragon_fire_explode', 'source': 'DragonFireExplode35/35 enemy_bsnake_s_2',
         'status': 'consumer_pending', 'expected': 'full source node chain: advanceddamage, finish dragon_fire, qualified AOE and reignite'},
        {'id': 'summon_flame_hint', 'source': 'SummonFlame50/init75; hint27; seven groups and exact ten predefined devices',
         'status': 'device_and_branch_primitives_ready_boss_trigger_pending', 'expected': 'native hint cancellation and trigger order; no fabricated activation times in whole stage'},
        {'id': 'wave_and_bgm', 'source': 'finish_current_wave_when_buff_finish / track_at_next_wave_when_buff_finish / play_bgm_when_buff_finish',
         'status': 'consumer_pending', 'expected': 'real wave control transitions; explicit visual/audio observations'},
    ]
    return {'schema': 'ark-sim/chapter08-bsnake-requirements/v2',
            'source_locks': {str(SOURCE): sha(SOURCE), str(Path(__file__)): sha(Path(__file__))},
            'source_stats': data['variant']['native_enemy']['resolved'], 'source_modes': modes,
            'source_reborn': data['RebornTalent'], 'source_skill_profiles': skill,
            'source_buff_graph': graph, 'source_hint_aliases': data['hint_alias_sets7x5'],
            'requirements': requirements, 'full_boss_complete': False, 'whole_stage_executed': False,
            'client_verified': False, 'policy': 'Reference-source consumers with replaceable timing/geometry; source gaps remain explicit'}


if __name__ == '__main__':
    value = build()
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'requirements': len(value['requirements']),
                      'modes': len(value['source_modes']), 'templates': len(value['source_buff_graph'])}))
