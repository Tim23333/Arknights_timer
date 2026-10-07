"""Fixed public12 participation with legal cells, source slots/DP and finite end."""
import json
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v2.life99999.json'


def main():
    package = json.loads(PACKAGE.read_bytes())
    scene = package['scenarioDraft']
    defs = {d['id']: d for d in package['definitions']}
    placements = [('myrtle', '151_myrtle', 0, 5, 1, 'right'),
                  ('bpipe', '222_bpipe', 1200, 5, 1, 'right'),
                  ('chen', '010_chen', 1500, 4, 4, 'right'),
                  ('plosis', '128_plosis', 1800, 4, 3, 'right'),
                  ('liskam', '107_liskam', 2100, 4, 7, 'right'),
                  ('angel', '103_angel', 2400, 6, 7, 'up'),
                  ('demkni', '202_demkni', 2700, 4, 5, 'right'),
                  ('amgoat', '180_amgoat', 3000, 5, 6, 'up'),
                  ('kalts', '003_kalts', 3900, 6, 6, 'up'),
                  ('lisa', '358_lisa', 4800, 3, 6, 'right'),
                  ('weedy', '400_weedy', 5100, 3, 7, 'down'),
                  ('cgbird', '179_cgbird', 5400, 6, 5, 'up')]
    commands, terrain = [], []
    for alias, suffix, tick, row, col, facing in placements:
        entity = 'unit/char_' + suffix
        assert entity in scene['roster']
        mask = 1 if defs[entity]['components']['deployable']['terrain'] == 'ground' else 2
        tile = scene['map']['tiles'][row * scene['map']['cols'] + col]
        assert tile['buildableType'] & mask
        commands.append({'at': tick, 'action': 'deploy', 'entity': entity, 'row': row, 'col': col,
                         'facing': facing, 'alias': 'c10_' + alias})
        terrain.append({'alias': alias, 'position': {'row': row, 'col': col}, 'tile': tile,
                        'source_cost': defs[entity]['components']['attributes']['base']['deploy_cost']})
    for alias, tick in [('myrtle', 1100), ('bpipe', 4100), ('chen', 4500), ('liskam', 4700), ('demkni', 5300)]:
        commands.append({'at': tick, 'action': 'withdraw', 'source': 'c10_' + alias})
    skills = [('myrtle', 600, 'campaign_myrtle_s2'), ('bpipe', 2700, 'campaign_bpipe_s3'),
              ('plosis', 3300, 'plosis_s2_first_packet'), ('amgoat', 3600, 'campaign_amgoat_s3'),
              ('kalts', 4200, 'kalts_summon'), ('demkni', 4350, 'demkni_s3'),
              ('kalts', 4500, 'kalts_host_s3'), ('lisa', 5700, 'lisa_s3'),
              ('weedy', 5850, 'campaign_weedy_deploy_cannon'), ('weedy', 5910, 'campaign_weedy_s3'),
              ('cgbird', 6900, 'cgbird_s3'), ('cgbird', 6930, 'support_night_bird')]
    summons = {'kalts_summon': (5, 3, 'right'), 'campaign_weedy_deploy_cannon': (4, 8, 'left'),
               'support_night_bird': (7, 7, 'up')}
    for alias, tick, name in skills:
        aid = 'ability/' + name
        entity = next('unit/char_' + suffix for candidate, suffix, *_ in placements if candidate == alias)
        assert aid in defs[entity]['components']['abilities']
        command = {'at': tick, 'action': 'skill', 'source': 'c10_' + alias, 'ability': aid}
        if name in summons:
            row, col, facing = summons[name]
            assert scene['map']['tiles'][row * scene['map']['cols'] + col]['buildableType'] & 1
            command['payload'] = {'position': {'row': row, 'col': col}, 'facing': facing}
        commands.append(command)
    # Surviving actors are genuinely withdrawn; actual rejected outcomes for
    # already dead/retired actors are recorded by the public command system.
    for index, (alias, *_rest) in enumerate(placements):
        commands.append({'at': 12000 + index, 'action': 'withdraw', 'source': 'c10_' + alias})
    commands.sort(key=lambda row: row['at'])
    folder = ROOT / 'scenarios/campaign/chapter10/level_main_10-14/public_plan_v1_finite'
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / 'commands.json'
    assert not output.exists()
    output.write_text(json.dumps(commands, indent=2) + '\n', encoding='utf8')
    result = {'schema': 'ark-sim/chapter10-public-plan/v1', 'source_package': str(PACKAGE),
        'source_package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
        'commands_sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'planned_distinct12': 12,
        'commands': len(commands), 'source_slots': 8, 'source_initial_DP': 10, 'source_terrain_checks': terrain,
        'native_cannon_not_a_deployment_slot': True, 'summon_slot_reserved_by_public_withdraw': True,
        'finite_withdraw_at': 12000, 'actual_outcomes_verified': False, 'whole_stage_executed': False,
        'scope': 'Source-legal public attempts; no guaranteed acceptance or perfect victory. All rejections must be saved.'}
    (folder / 'plan.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'planned12': 12, 'commands': len(commands), 'native_slots': 8, 'native_DP': 10}))


if __name__ == '__main__':
    main()
