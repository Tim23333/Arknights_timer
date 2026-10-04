"""Strictly join normalcombat, two source skills, firstscreen and loop-hint modules."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v4_candidate'
BASE = ROOT / 'packages/campaign/chapter08_consumers/bsnake'
OUT = BASE / 'partial_join.module.v1.json'
CORE = '20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30'
PATHS = [BASE / name for name in ('combat.module.v2.json', 'skills.module.v4.json',
                                  'first_screen.module.v2.json', 'summon_hint.module.v4.json')]
FIRE = BASE.parent / 'boss/dragon_fire.module.v12.joint.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def providers():
    from tools.chapter08_bsnake_combat.policies_v1 import providers as combat
    from tools.chapter08_bsnake_skills.policies_v1 import providers as skills
    from tools.chapter08_bsnake.screen_policy_v1 import providers as screen
    from tools.chapter08_joint_v4.build_summon_hint_v2 import providers as hint
    return {**combat(), **skills(), **screen(), **hint()}


def build():
    from tools.campaign_content_composition_v2 import compose_modules
    modules = [(path.name, json.loads(path.read_bytes())) for path in PATHS]
    fire = json.loads(FIRE.read_bytes())
    combat, skills, screen, hint = [value for _, value in modules]
    owner = combat['entities'][0]['id']
    entity = deepcopy(combat['entities'][0])
    component = entity['components']
    screen_component = screen['entities'][0]['components']
    component['resources'].update(deepcopy(screen_component['resources']))
    component['resources'].update(deepcopy(hint['manifest']['metadata']['resources_required']))
    component['resources']['hp'] = deepcopy(screen_component['resources']['hp'])
    component['abilities'] += skills['manifest']['metadata']['owned_ability_bindings']
    component['abilities'] += screen_component['abilities'] + hint['manifest']['metadata']['owned_abilities']
    assert len(component['abilities']) == len(set(component['abilities']))
    component['rebirth'] = deepcopy(screen_component['rebirth'])
    component['rebirth']['on_begin'].insert(0, {'op': 'remove_buff', 'target': 'source', 'buff': 'buff/ch8/source/bsnake_t[protect]'})
    component['rebirth']['on_begin'].append({'op': 'apply_buff', 'target': 'source', 'buff': 'buff/ch8/source/bsnake_t[protect]/reborn'})
    component['rebirth']['retain_buffs'].append('buff/ch8/source/bsnake_t[protect]/reborn')
    component['rebirth']['on_finish'].insert(1, {'op': 'modify_resource', 'target': 'source', 'resource': 'screen_packets', 'value': 0})
    component['behavior'] = deepcopy(screen_component['behavior'])
    decision = deepcopy(combat['behaviors'][0]['decision'])
    screen_behavior = deepcopy(screen['behaviors'][0])
    screen_behavior['decision'] = decision
    screen_entity_free = deepcopy(screen)
    screen_entity_free.pop('entities')
    screen_entity_free['behaviors'] = [screen_behavior]
    source_combat = deepcopy(combat)
    source_combat['entities'] = [entity]
    source_combat.pop('behaviors')
    definitions, provenance = compose_modules([
        ('combat', source_combat), ('skills', skills), ('screen', screen_entity_free),
        ('hint', hint), ('dynamic_fire', fire)])
    normal_ids = combat['entities'][0]['components']['abilities']
    entries = [{'ability': aid, 'priority': 0, 'attack_clock': True, 'require_attack_control': True,
                'condition': 'inputs.source.components.resources.mode.current == ' + str(index), 'parameters': {}}
               for index, aid in enumerate(normal_ids)]
    entries += deepcopy(skills['manifest']['metadata']['arbitration_entries'])
    for aid in screen_component['abilities'] + hint['manifest']['metadata']['owned_abilities']:
        condition = 'inputs.source.components.resources.mode.current == 1 and inputs.branches.bsnake_flame.available == True' if aid.endswith('/summon_flame') else 'False'
        entries.append({'ability': aid, 'priority': 20, 'attack_clock': False, 'require_attack_control': False,
                        'condition': condition, 'parameters': {}})
    entity['components']['ability_arbitration'] = {'priority_order': 'higher_first', 'busy': 'blocking_casts', 'entries': entries}
    definitions[owner] = entity
    from tools.chapter08_joint_v4.build_first_screen_v1 import SCREEN, INVINCIBLE
    first = definitions[SCREEN]
    first['on_remove'] = [effect for effect in first['on_remove'] if effect.get('event') != 'source.bsnake.hint.requested']
    first['on_remove'].append({'op': 'trigger_ability', 'target': 'source', 'ability': 'ability/ch8/bsnake/hint'})
    clocks = {aid: definitions[aid]['initial_cooldown_seconds'] for aid in entity['components']['abilities']
              if 'initial_cooldown_seconds' in definitions[aid] and '/phase1' in aid or aid.endswith('/summon_flame')}
    for effect in first['on_remove']:
        if effect['op'] == 'restart_behavior':
            effect['parameters']['abilities'] = list(entity['components']['abilities'])
            effect['parameters']['initial_cooldowns'] = clocks
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ch8/bsnake/partial_join_v1',
            'requires': ['preset/ark_standard'], 'metadata': {
                'required_runtime': CORE, 'source_locks': {str(path): sha(path) for path in PATHS + [FIRE, Path(__file__)]},
                'provenance_before_explicit_join': provenance,
                'join_overrides': ['Owner components union, finite arbitration, source rebirth protect replacement',
                                  'firstscreen mode1 restart allowned initialclocks, Hint actualcallback'],
                'scope': 'Modes0/1 combat+Ignite/Explode and first28screen+loopSummon consumer; no finalscreen/wavetrack source policy yet',
                'pending_required': ['Native finalzero screen fullgraph', 'Real finish+track source to nextwave True',
                                     'Boss mode transitions/initialCDpause source timing review', 'FullJT8-3source map/7rowfire/36goals'],
                'full_boss_complete': False, 'whole_stage_executed': False, 'client_verified': False}},
            'definitions': list(definitions.values())}


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest() == CORE
    p = build()
    loop = json.loads((BASE.parent / 'flame/loop.profile.v3.json').read_bytes())
    scene = deepcopy(p)
    # Compile only the source actor; branch references are declared primitive
    # device definitions in this structural fixture, not original native25SP.
    scene['definitions'].append({'id': 'unit/ch8/flame/level1', 'kind': 'entity', 'components': {'spatial': {}}})
    scene['scenarioDraft'] = {'id': 'scene/bsnake/partial_compile', 'ruleset': 'ruleset/ark_standard',
                              'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'],
                              'initialEntities': loop['initial_entities'] + [{'definition': 'unit/ch8/bsnake/cadb87696bef4de2',
                                  'position': {'row': 4, 'col': 10}}]}
    Compiler(providers=providers()).compile(scene)
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'definitions': len(p['definitions']), 'actual_compile': True}))
