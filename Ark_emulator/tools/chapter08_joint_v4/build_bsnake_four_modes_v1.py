"""Compose native sevenrow first and final screens with normal source skills."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v4_candidate'
BASE = ROOT / 'packages/campaign/chapter08_consumers/bsnake'
PARENT = BASE / 'partial_join.module.v1.json'
ROWS = BASE / 'first_screen.native7rows.v3.json'
SOURCE = BASE / 'source.closure.v1.json'
OUT = BASE / 'four_modes.module.v1.json'
FINAL = 'buff/ch8/source/bsnake_s[final_screen_attack]'
CANCEL = 'buff/ch8/source/bsnake_t[hint_cancel]'
VOLLEY = 'ability/ch8/bsnake/firecommon'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    p = json.loads(PARENT.read_bytes())
    rows = json.loads(ROWS.read_bytes())
    source = json.loads(SOURCE.read_bytes())
    definitions = {row['id']: deepcopy(row) for row in p['definitions']}
    owner = definitions['unit/ch8/bsnake/cadb87696bef4de2']
    component = owner['components']
    for row in list(definitions.values()):
        if row['kind'] == 'projectile' and row['id'].startswith('projectile/ch8/bsnake/firecommon/'):
            definitions.pop(row['id'])
    for row in rows['projectiles']:
        definitions[row['id']] = deepcopy(row)
    volley = definitions[VOLLEY]
    volley['timeline'] = deepcopy(next(row for row in rows['abilities'] if row['id'] == VOLLEY)['timeline'])
    volley['activation']['condition'] = 'inputs.resources.mode.current >= 2 and inputs.resources.screen_packets.current < 10'
    rebirth = component['rebirth']
    rebirth['max_count'] = 2
    rule = definitions[rebirth['restore_rule']]
    rule['implementation']['expression'] = 'inputs.parameters.capacity * inputs.parameters.ratio if context.rebirth.count == 1 else 0'
    first_condition = 'inputs.source.components.runtime.rebirth.count == 1'
    for effect in rebirth['on_begin']:
        if effect.get('buff') == 'buff/ch8/source/bsnake_t[protect]/reborn':
            effect['condition'] = first_condition
    rebirth['on_begin'].append({'op': 'remove_buff', 'target': 'source', 'buff': 'buff/ch8/source/bsnake_t[protect]/reborn',
                               'condition': 'inputs.source.components.runtime.rebirth.count == 2'})
    end_node = source['BSON']['templates']['enemy_bsnake_s[final_screen_attack]']['parsed']['eventToActions']['ON_BUFF_FINISH'][0]
    assert end_node['_skipReborn'] is False and end_node['_noSource'] is False
    parent_screen = definitions['buff/ch8/source/bsnake_s[screen_attack]']
    final_screen = deepcopy(parent_screen)
    final_screen['id'] = FINAL
    final_screen['on_remove'] = [{'op': 'instant_kill', 'target': 'source',
                                 'parameters': {'cause': 'source_final_screen_finish', 'skip_rebirth': False}}]
    # Native final start cancels existing futurehint display. Visual cancellation
    # carries realowner and keeps flag for subsequent Hint invocations.
    definitions[CANCEL] = {'id': CANCEL, 'kind': 'buff', 'effects': [{'op': 'emit', 'event': 'source.bsnake.hint.clear'}]}
    definitions[FINAL] = final_screen
    hint = definitions['ability/ch8/bsnake/hint']
    hint['activation']['condition'] = 'inputs.resources.mode.current < 3'
    retained = ['buff/source/bsnake/reborn_up', FINAL, CANCEL]
    rebirth['retain_buffs'] = list(dict.fromkeys(rebirth['retain_buffs'] + retained))
    rebirth['zero_restore_lifecycle'] = {
        'mode': 'terminal_active', 'counts': [2], 'duration_seconds': 28,
        'owned_abilities': [VOLLEY], 'retained_buffs': retained, 'completion_buffs': [FINAL],
        'on_enter': [{'op': 'modify_resource', 'target': 'source', 'resource': 'mode', 'value': 3},
                     {'op': 'modify_resource', 'target': 'source', 'resource': 'screen_packets', 'value': 0},
                     {'op': 'transition', 'target': 'source', 'state': 'finalscreen'},
                     {'op': 'remove_buff', 'target': 'source', 'buff': 'buff/ch8/source/bsnake_t[hint]'},
                     {'op': 'apply_buff', 'target': 'source', 'buff': CANCEL},
                     {'op': 'apply_buff', 'target': 'source', 'buff': FINAL}],
    }
    behavior = definitions[component['behavior']['machine']]
    behavior['states']['finalscreen'] = {}
    p['manifest']['id'] = 'package/ch8/bsnake/four_modes_v1'
    meta = p['manifest']['metadata']
    meta['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, ROWS, SOURCE, Path(__file__))})
    meta['explicit_final_source_template'] = source['BSON']['templates']['enemy_bsnake_s[final_screen_attack]']['parsed']
    meta['scope'] = 'Four actualmodes normal0/enraged1/firstscreen2/finalscreen3 and native7rows tenvolleys; wave-release/tracksource not yet composed'
    meta['pending_required'] = ['Realwavefinish/tracksource True sourceBuff lifecycles',
                                'Fullstage native source conversion/onlylifeoverlay/commands/whole3way',
                                'Independent full sourcefield→fourmode join review', 'Originalsource firstHP .5 vsPRTS100% conflict remains explicit']
    p['definitions'] = list(definitions.values())
    return p


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler
    from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers, BASE
    p = build()
    loop = json.loads((BASE.parent / 'flame/loop.profile.v3.json').read_bytes())
    fixture = deepcopy(p)
    fixture['definitions'].append({'id': 'unit/ch8/flame/level1', 'kind': 'entity', 'components': {'spatial': {}}})
    fixture['scenarioDraft'] = {'id': 'scene/bsnake/fourmode_compile', 'ruleset': 'ruleset/ark_standard',
                               'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'],
                               'initialEntities': loop['initial_entities'] + [{'definition': 'unit/ch8/bsnake/cadb87696bef4de2',
                                  'instanceAlias': 'boss', 'position': {'row': 4, 'col': 10}}]}
    Compiler(providers=providers()).compile(fixture)
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'definitions': len(p['definitions']), 'actual_compile': True}))
