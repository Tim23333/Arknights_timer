"""Twelve public deployment attempts, selected skills and owned units on 3-8."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/campaign/runthrough/level_main_03-08.m54.life99999.json'
OUT = ROOT / 'scenarios/campaign/chapter03/03-08/commands.runthrough_v1.json'
PIN = 'b8c05acafb3b5bf179894c56fb52e67c02e6214073e70bf6389dea583f1fceb1'


def build():
    raw = PACKAGE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('Frozen 3-8 life99999 input changed')
    p = json.loads(raw); scene = p['scenarioDraft']; defs = {d['id']: d for d in p['definitions']}
    slots = [('char_151_myrtle', 'myrtle', 0, 2, 7, 'left'),
             ('char_222_bpipe', 'bpipe', 450, 2, 6, 'left'),
             ('char_103_angel', 'angel', 900, 1, 9, 'left'),
             ('char_180_amgoat', 'amgoat', 1560, 3, 5, 'left'),
             ('char_202_demkni', 'saria', 2250, 4, 8, 'left'),
             ('char_128_plosis', 'plosis', 2790, 4, 5, 'right'),
             ('char_003_kalts', 'kalts', 3420, 2, 9, 'left'),
             ('char_107_liskam', 'liskam', 4110, 5, 7, 'left'),
             ('char_010_chen', 'chen', 4860, 5, 6, 'left'),
             ('char_400_weedy', 'weedy', 5580, 2, 7, 'left'),
             ('char_179_cgbird', 'night', 6060, 4, 5, 'right'),
             ('char_358_lisa', 'lisa', 6420, 3, 5, 'right')]
    commands = [{'at': 5300, 'action': 'withdraw', 'source': 'myrtle'},
                {'at': 5850, 'action': 'withdraw', 'source': 'plosis'},
                {'at': 6300, 'action': 'withdraw', 'source': 'amgoat'}]
    for name, alias, at, row, col, facing in slots:
        unit = 'unit/' + name
        definition = defs[unit]
        terrain = definition['components']['deployable']['terrain']
        tile = scene['map']['tiles'][row * scene['map']['cols'] + col]
        if tile['buildableType'] != (1 if terrain == 'ground' else 2):
            raise ValueError('Invalid source terrain for ' + unit)
        commands.append({'at': at, 'action': 'deploy', 'definition': unit, 'alias': alias,
                         'position': {'row': row, 'col': col}, 'facing': facing})
        commands.append({'at': at + 720, 'action': 'skill', 'source': alias,
                         'ability': definition['metadata']['selected_skill_ability']})
    commands += [
        {'at': 4300, 'action': 'skill', 'source': 'kalts', 'ability': 'ability/kalts_summon',
         'position': {'row': 4, 'col': 7}, 'facing': 'left'},
        {'at': 5640, 'action': 'skill', 'source': 'weedy', 'ability': 'ability/campaign_weedy_deploy_cannon',
         'position': {'row': 2, 'col': 5}, 'facing': 'left'},
        {'at': 6500, 'action': 'skill', 'source': 'night', 'ability': 'ability/support_night_bird',
         'position': {'row': 4, 'col': 6}, 'facing': 'left'}]
    commands += [{'at': 7800 + index, 'action': 'withdraw', 'source': alias}
                 for index, (_, alias, *_rest) in enumerate(slots)]
    return sorted(commands, key=lambda item: item['at'])


if __name__ == '__main__':
    result = build(); raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_bytes(raw)
    print(json.dumps({'commands': len(result), 'deployments': 12, 'sha256': hashlib.sha256(raw).hexdigest(),
                      'scope': 'Public attempts; actual affordability, skills, tokens and survival outcomes recorded at runtime'}))
