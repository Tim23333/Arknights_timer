"""Extract source operands into the ore/mine consumer contract, no runtime claim."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter07_predefines/source.v4.reference.json'
PIN = '9ab8b1049f5e0c9d34977563ccd8ac394044f77ff8da44b9cb717f52a1b9dfcb'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sha(SOURCE) == PIN
    source = json.loads(SOURCE.read_bytes())
    skills = {}
    for name, prefab in source['skill_prefabs'].items():
        grouped = {}
        for pointer, item in prefab['components'].items():
            grouped.setdefault(item['native_class'], []).append(
                {'pointer': pointer, 'raw': item['raw']})
        action = grouped['AnimatedActionToTargetAbility'][0]['raw']
        selector_pointer = str(action['_selector']['m_PathID'])
        selector = prefab['components'][selector_pointer]
        assert selector['native_class'] == 'AdvancedSelector'
        skills[name] = {
            'table': source['skill_tables'][name],
            'action': grouped['AnimatedActionToTargetAbility'][0],
            'selector': {'pointer': selector_pointer, 'raw': selector['raw']},
            'cast_skill': grouped['CastSkill'][0],
            'trigger': grouped.get('SelectorTrigger', grouped.get('AlwaysTrigger')),
            'range_components': grouped.get('PhysicsRange', grouped.get('AutoLoadBoxRange')),
            'range_geometry': prefab['geometry_sources'],
            'after_affecting': grouped.get('BuffAfterAffecting', []),
        }
    stages = {}
    for name, stage in source['stages'].items():
        instances = []
        for item in stage['instances']:
            raw = item['raw_native']
            instances.append({'bucket': item['bucket'], 'native': raw,
                              'character': item['raw_character']})
        stages[name] = {'instances': instances,
                        'controls': stage['controls'],
                        'native_options': stage['native_options'],
                        'native_branches': stage['native_branches']}
    templates = {name: {'parsed': row['parsed'], 'sha': row['document_sha256']}
                 for name, row in source['bson_templates']['templates'].items()}
    notes = [
        'ore_s finishes with a conditional PURE packet only when ore_immune is absent; source attackType NONE, source actor exists, ignoreSP false, skipModifier false, considerUnhurtable false.',
        'ore_buff finishes with ore_listener test then mode from blackboard; exact listener consumers and mode effects are separate enemy dependencies.',
        'Ore action timeMode 2, preDelay .6000000238418579, cooldown 1.0; skill table SP7 init0/increment1/value500. Action and SP clocks remain separate.',
        'Ore side2/category2 selection reference must explicitly map neutral side. Raw targetSide3/category1/motion3/ignoreTargetFree1 still enforces camouflage rules.',
        'Mine native talent timer20 differs from skill SP25. Preserve both mode-change readiness and SP readiness; NeverTrigger ordinary melee remains disabled.',
        'Mine PhysicsRange CircleCollider radius .550000011920929; collider overlap, candidate radius and postFilter24 need a declared reference policy and independent boundary cases.',
        'Mine active Buff order applies 15s damage_scale[input] first, then fixed PURE damage2000. Whether same explosion sees the new modifier follows source order and independent expected pipeline.',
        'Mine instant_damage_pure template is actor-sourced NORMAL, not actor-free no_source_damage; normal attack SP and hooks follow exact source flags.',
        'Mine after-affecting suicide source Withdraw switchToDead true; zero refund, stock15 native cards, max counts/cost/cooldown remain real source data.',
        'Ore TrapMode terrain rewrites buildable0/passable2/height .4000000059604645 and actual ground routes must be preserved.',
        '7-17 keeps ore aliases #1/#2; 7-18 alias remains null. Generated internal runtime IDs must be distinguished from native aliases.',
        'Fixed table 56aee, local skill/BSON 20260831, entity assets20250327 are pinned separate versions; no client alignment assertion.',
    ]
    report = {
        'schema': 'ark-sim/chapter07-predefines-consumer-requirements/v1',
        'source': {'path': str(SOURCE), 'sha256': PIN},
        'extractor': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
        'skills': skills, 'entity_prefabs': source['prefabs'],
        'templates': templates, 'stages': stages,
        'consumer_requirements': notes, 'source_policy_notes': source['source_policy_notes'],
        'runtime_created': False, 'mechanisms_verified': False,
        'whole_stage_executed': False, 'client_verified': False,
    }
    out = ROOT / 'packages/campaign/chapter07_predefines_consumer/requirements.v1.json'
    data = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if out.exists():
        assert out.read_bytes() == data, 'Frozen requirement bytes differ'
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    assert sha(SOURCE) == PIN
    print(json.dumps({'sha256': sha(out), 'runtime_created': False,
                      'stages': list(stages), 'skills': list(skills)}))


if __name__ == '__main__':
    main()
