"""Compile exact44birth native JT8-3 map, controls and active device branch."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_wave_track_v4_candidate'
CORE = '4bf1cc96ae41f2850b645c25d772ada1d472f7b0202127fff340a4fc2b0b04c3'
SOURCE = ROOT / 'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json'
BASE = ROOT / 'packages/campaign/chapter08_consumers'
OUT = ROOT / 'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v3.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def providers():
    from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers as boss
    from tools.chapter08_flame_device.policies_v1 import providers as flame
    from tools.chapter08_ranged.policies_secondary_v1 import providers as ranged
    return {**boss(), **flame(), **ranged()}


def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_joint_v4.active_branches_v2 import compose
    from tools.campaign_content_composition_v2 import compose_modules, reachable_content
    assert implementation_digest() == CORE
    plan = json.loads(SOURCE.read_bytes())
    stage = plan['stages']['level_main_08-17']
    native = deepcopy(stage['native_document'])
    assert stage['spawn_count'] == 44
    paths = {'enemy_1108_uterer': BASE / 'uterer/module.v1.reference.json',
             'enemy_1110_uamord': BASE / 'ranged/uamord.module.v4.json',
             'enemy_1111_ucommd': BASE / 'ranged/ucommd.module.v2.json',
             'enemy_1515_bsnake': BASE / 'bsnake/four_modes.wave_source.v5.json'}
    modules, bindings, variants = [], {}, []
    pins = {str(SOURCE): sha(SOURCE)}
    for identifier in stage['variant_ids']:
        variant = plan['variants'][identifier]
        key = variant['native_enemy']['native_id']
        path = paths[key]
        package = json.loads(path.read_bytes())
        entities = package.get('entities', []) + [row for row in package.get('definitions', []) if row['kind'] == 'entity']
        unit = next(row for row in entities if row['components'].get('attributes', {}).get('base', {}).get('max_hp') ==
                    variant['native_enemy']['resolved']['attributes']['maxHp'])
        modules.append((key, package))
        bindings[key] = {'unit': unit['id'], 'motion': 'WALK'}
        pins[str(path)] = sha(path)
        variants.append({'variant_id': identifier, 'native_reference': variant['native_reference'],
                         'unit': unit['id'], 'module_sha': sha(path)})
    flame = BASE / 'flame/module.v4.joint.json'
    loop = BASE / 'flame/loop.profile.v3.json'
    predefined = BASE / 'flame/predefines.profile.v2.json'
    controls_path = ROOT / 'packages/campaign/chapter08_stage_controls/controls.module.v1.json'
    roster_path = ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json'
    for label, path in (('native_flame', flame), ('fixed12', roster_path)):
        modules.append((label, json.loads(path.read_bytes())))
    roster = json.loads(roster_path.read_bytes())
    control_package = json.loads(controls_path.read_bytes())
    controls = {row['id']: row for row in control_package['controls']}
    story_controls = {key: controls[identifier] for key, identifier in control_package['manifest']['metadata']['story_bindings'].items()}
    opera_controls = {key: controls[identifier] for key, identifier in control_package['manifest']['metadata']['opera_bindings'].items()}
    loop_profile = json.loads(loop.read_bytes())
    raw_predefines = json.loads(predefined.read_bytes())['native_predefines']
    profile = {'native_predefines': raw_predefines, 'initial_entities': loop_profile['initial_entities'], 'card_bindings': [], 'resources': {}}
    tile_profiles = {'tile_telin': {'type': 'route_checkpoint_portal', 'role': 'entry'},
                     'tile_telout': {'type': 'route_checkpoint_portal', 'role': 'exit'}}
    scene, scene_controls = compose(native, 'level_main_08-17', bindings, tile_profiles,
                                    branch_profile=loop_profile, predefined_profile=profile,
                                    story_controls=story_controls, opera_controls=opera_controls)
    scene['roster'] = deepcopy(roster['manifest']['metadata']['roster'])
    scene['rules'] = deepcopy(roster['manifest']['metadata']['stage_rules'])
    modules.append(('all_native_controls', {'controls': scene_controls}))
    spawn_path = ROOT / 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json'
    spawn = json.loads(spawn_path.read_bytes())
    modules.append(('native_spawn_rectangle', {'rules': [row for row in spawn['rules'] if row['id'] == 'rule/m7_spawn_rectangle']}))
    definitions, _ = compose_modules(modules)
    speed_id = scene['rules']['movement.speed']
    speed = deepcopy(definitions[speed_id])
    speed['parameters']['multiplier'] = native['options']['moveMultiplier']
    reg = providers()
    package, _ = reachable_content(scene, modules, {speed_id: {'definition': speed,
        'reason': 'Exactnative moveMultiplier.5', 'source': str(SOURCE)}},
        manifest_id='package/ch8/jt83/native_draft_v3', providers=reg)
    for path in (flame, loop, predefined, controls_path, roster_path, spawn_path, Path(__file__).resolve()):
        pins[str(path)] = sha(path)
    births = sum(action.get('count', 1) for wave in scene['timeline']['waves'] for fragment in wave['fragments']
                 for action in fragment['actions'] if action['kind'] == 'spawn')
    assert births == 44 and len(scene['initialEntities']) == 10 and len(scene['roster']) == 12
    assert scene['parameters']['deploy_capacity'] == 9 and scene['resources']['dp']['initial'] == 15
    assert scene['resources']['life']['initial'] == 3 and scene['branches']['bsnake_flame']['loop'] is True
    package['manifest']['metadata'].update(source_locks=pins, required_core=CORE, source_births=44,
        variant_bindings=variants, native_options=native['options'], full_stage_executed=False,
        source_admission_status='compiled_draft_pending_source_join_review', client_verified=False,
        pending_required=['WaveV4 ownfull/baseline/peer exactgates beforepromotion',
                          'Fourmode publickill completechain sourceproof', 'Nativevisualaura bookkeeping and sourcecallgraph review',
                          'Source Story/Opera control policy independent review', 'Fullfixed12 onlylifeoverlay publicprocess/durableCP/head'])
    Compiler(providers=reg).compile(package)
    return package


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    package = build()
    assert not OUT.exists()
    OUT.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'actual_compile': True, 'births': 44,
                      'definitions': len(package['definitions']), 'whole_stage_approved': False}))
