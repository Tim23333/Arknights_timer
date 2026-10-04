"""Life-only overlay and legal native-tile fixed12 reference rotation."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from tools.chapter08_joint_v4.build_jt83_draft_v1 import ROOT, OUT as PARENT

COMMANDS = ROOT / 'scenarios/campaign/chapter08/level_main_08-17/public_plan_v1/commands.json'
OVERLAY = PARENT.with_name('level_main_08-17.native_draft.v1.life99999.v1.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if path.exists():
        assert path.read_bytes() == raw, 'Frozen input differs'
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def build():
    assert sha(PARENT) == '905cbdd790e9ebf84607a60ec8fdbdd60a2bc2f6ee601fae74b60ae8eecf9a18'
    p = json.loads(PARENT.read_bytes())
    roster = p['scenarioDraft']['roster']
    placements = [(0, '151_myrtle', 5, 7, 'up'), (870, '222_bpipe', 5, 7, 'up'),
                  (1350, '128_plosis', 6, 7, 'up'), (1830, '010_chen', 4, 5, 'right'),
                  (2310, '107_liskam', 3, 7, 'right'), (2790, '202_demkni', 5, 8, 'left'),
                  (3270, '103_angel', 4, 7, 'up'), (3750, '180_amgoat', 2, 8, 'down'),
                  (4230, '003_kalts', 4, 9, 'left'), (4710, '358_lisa', 6, 8, 'up'),
                  (5490, '400_weedy', 3, 8, 'left'), (5970, '179_cgbird', 6, 11, 'left')]
    scene = p['scenarioDraft']
    definitions = {row['id']: row for row in p['definitions']}
    reserved = {(item['position']['row'], item['position']['col']) for item in scene['initialEntities']}
    commands = []
    for at, key, row, col, facing in placements:
        unit = 'unit/char_' + key
        assert unit in roster and (row, col) not in reserved
        terrain = definitions[unit]['components']['deployable']['terrain']
        tile = scene['map']['tiles'][row * scene['map']['cols'] + col]
        assert tile['buildableType'] == (1 if terrain == 'ground' else 2)
        commands.append({'at': at, 'action': 'deploy', 'entity': unit, 'row': row, 'col': col,
                         'facing': facing, 'alias': 'c83_' + key.split('_', 1)[1]})
    for at, key in ((810, 'myrtle'), (4650, 'bpipe'), (5130, 'chen'), (5610, 'liskam')):
        commands.append({'at': at, 'action': 'withdraw', 'source': 'c83_' + key})
    skills = [(300, 'myrtle', 'ability/campaign_myrtle_s2'), (2400, 'bpipe', 'ability/campaign_bpipe_s3'),
              (4500, 'kalts', 'ability/kalts_summon'), (4800, 'kalts', 'ability/kalts_host_s3'),
              (4800, 'amgoat', 'ability/campaign_amgoat_s3'), (5100, 'demkni', 'ability/demkni_s3'),
              (5400, 'lisa', 'ability/lisa_s3'), (5400, 'plosis', 'ability/plosis_s2_first_packet'),
              (6090, 'weedy', 'ability/campaign_weedy_deploy_cannon'), (6150, 'weedy', 'ability/campaign_weedy_s3'),
              (6540, 'cgbird', 'ability/cgbird_s3'), (6570, 'cgbird', 'ability/support_night_bird')]
    for at, key, ability in skills:
        assert ability in definitions
        command = {'at': at, 'action': 'skill', 'source': 'c83_' + key, 'ability': ability}
        if ability == 'ability/kalts_summon':
            command['payload'] = {'position': {'row': 5, 'col': 9}, 'facing': 'left'}
        elif ability == 'ability/campaign_weedy_deploy_cannon':
            command['payload'] = {'position': {'row': 3, 'col': 7}, 'facing': 'left'}
        elif ability == 'ability/support_night_bird':
            command['payload'] = {'position': {'row': 6, 'col': 10}, 'facing': 'left'}
        commands.append(command)
    commands.sort(key=lambda command: command['at'])
    assert len(commands) == 28
    write(COMMANDS, commands)
    native_life = deepcopy(scene['resources']['life'])
    scene['resources']['life'] = {'initial': 99999, 'capacity': 99999}
    scene['metadata']['runthrough_profile'] = {'base_life_resource': 'life', 'base_life': 99999,
        'fixed12': deepcopy(roster), 'source_births': 44, 'deploy_capacity': 9,
        'public_commands_sha256': sha(COMMANDS), 'operator_enemy_HP': 'Original exact source module HP',
        'training_deployment_exception': False, 'client_verified': False,
        'accuracy': 'Reference-source model; user client feedback pending'}
    p['manifest']['metadata']['goal_base_life_authoring'] = {'native': native_life,
        'selected_initial': 99999, 'selected_capacity': 99999, 'only_authoring': 'Campaign user base life policy'}
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    validate_native_overlay(p, json.loads(PARENT.read_bytes()), COMMANDS)
    write(OVERLAY, p)
    return {'parent_sha': sha(PARENT), 'overlay_sha': sha(OVERLAY), 'commands_sha': sha(COMMANDS),
            'planned_commands': 28, 'selected_players': 12, 'source_births': 44,
            'only_base_life_changed': True, 'actual_run_pending': True, 'source_admission_pending': True}


if __name__ == '__main__':
    print(json.dumps(build()))
