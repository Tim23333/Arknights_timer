"""Project source ray definitions to the actual JT8-3 seven interior rows."""
import json
import hashlib
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v4_candidate'
BASE = ROOT / 'packages/campaign/chapter08_consumers/bsnake'
PARENT = BASE / 'first_screen.module.v2.json'
SOURCE = BASE / 'source.closure.v1.json'
OUT = BASE / 'first_screen.native7rows.v3.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    data = json.loads(SOURCE.read_bytes())
    native_map = data['native_stage_document']['mapData']['map']
    rows, cols = len(native_map), len(native_map[0])
    assert (rows, cols) == (9, 15)
    screen = next(row['raw'] for row in data['prefab']['components'].values() if row['native_class'] == 'BsnakeScreenAttack')
    assert screen['_borderToPeel'] == 1
    p = json.loads(PARENT.read_bytes())
    original = deepcopy(p['projectiles'])
    representative = [row for row in original if '/r1/' in row['id']]
    assert len(representative) == 4
    prototype = next(row for row in p['abilities'] if row['id'] == 'ability/ch8/bsnake/firecommon')
    first = deepcopy(prototype['timeline'][0])
    p['projectiles'] = []
    prototype['timeline'] = []
    for row in range(1, rows - 1):
        for definition in representative:
            item = deepcopy(definition)
            item['id'] = item['id'].replace('/r1/', '/r' + str(row) + '/')
            item['motion']['parameters']['row'] = row
            p['projectiles'].append(item)
        event = deepcopy(first)
        for child in event['effect']['on_success']:
            child['projectile_definition'] = child['projectile_definition'].replace('/r1/', '/r' + str(row) + '/')
        prototype['timeline'].append(event)
    assert len(p['projectiles']) == 28 and len(prototype['timeline']) == 7
    p['manifest']['id'] = 'package/ch8/bsnake/first_screen_native7_v3'
    meta = p['manifest']['metadata']
    meta['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, SOURCE, Path(__file__))})
    meta['source_native_map_dimensions'] = {'rows': rows, 'cols': cols}
    meta['source_screen_rows'] = list(range(1, rows - 1))
    meta['scope'] = 'Native JT8-3 seven interior rows×ten sourcevolleys; firstscreen graph only, no wholeBoss or stage admission'
    meta['reference_policy'] = 'Native border1 and map9x15 give seven projectile row definitions. Original ray geometry/RNG .1 and delay quantum remain replaceable reference policies; no source actor relocation.'
    return p


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler
    from tools.chapter08_bsnake.screen_policy_v1 import providers
    p = build()
    scene = deepcopy(p)
    scene['scenarioDraft'] = {'id': 'scene/screen/native_rows_compile', 'ruleset': 'ruleset/ark_standard',
                              'map': {'rows': 9, 'cols': 15}, 'initialEntities': [{'definition': p['entities'][0]['id'],
                                  'instanceAlias': 'boss', 'position': {'row': 4, 'col': 10}}]}
    Compiler(providers=providers()).compile(scene)
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'projectile_definitions': len(p['projectiles']), 'rows': 7, 'actual_compile': True}))
