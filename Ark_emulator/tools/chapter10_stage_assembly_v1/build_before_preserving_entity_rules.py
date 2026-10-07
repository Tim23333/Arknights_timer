"""Full first chapter10 source assembly; admission and full execution separate."""
from copy import deepcopy
import json
import hashlib
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
STAGE = 'level_main_10-14'
PLAN = ROOT / 'packages/campaign/chapter10_source_prepare/source.plan.v1.json'


def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter06_review.stage_converter_v7 import compose, exact
    from tools.chapter09_pillar_v1.registration import registrations
    from tools.campaign_content_composition_v2 import compose_modules, reachable_content
    from tools.chapter10_bloodline_v1.build import build_all, MARK, entity_id
    from tools.chapter10_remaining_v2.build import build as lord
    from tools.chapter10_remaining_v1.build import build as remaining, bind_recipients
    from tools.chapter10_dkmage_source_v1.build import build as mage, BODY as MAGE
    from tools.chapter10_gunctrl_v3.build import build as cannon
    from tools.chapter10_gunctrl_v1.build import BODY as CANNON, bind_status_definitions
    from tools.chapter10_environment_v1.build import build as environment
    from tools.campaign_elemental_receivers_v1.build import mount as receivers
    from tools.chapter10_stage_assembly_v1.providers import providers
    plan = json.loads(PLAN.read_bytes())
    row = plan['stages'][STAGE]
    native = deepcopy(row['native_document'])
    blood = build_all()
    mark = deepcopy(next(buff for buff in blood['buffs'] if buff['id'] == MARK))
    parent = lord()
    magician = mage()
    raw_blood = {entity['id']: entity for entity in blood['entities']}
    # Lord bridge publishes the same six actors with its explicit ATK rule
    # wrapping. Mage's duplicate raw actors must match frozen blood exactly;
    # publish one actor declaration and preserve all ownership in that actor.
    deduplicated = []
    retained = []
    for entity in magician['entities']:
        if entity['id'] in raw_blood:
            if not exact(entity, raw_blood[entity['id']]):
                raise ValueError('Mage blood dependency differs from authoritative raw source')
            deduplicated.append(entity['id'])
        else:
            retained.append(entity)
    magician['entities'] = retained
    env = environment()
    env_row = env['manifest']['metadata']['stages'][STAGE]
    roster_path = ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json'
    roster = json.loads(roster_path.read_bytes())
    modules = [('lord_with_authenticated_blood', parent), ('native_mage', magician),
               ('native_supply', remaining('enemy_1224_dsuply_2', bloodsucker_mark=mark)),
               ('native_cannon_v3', cannon(STAGE, require_complete=True)),
               ('native_environment', {'rules': env['rules']}), ('fixed12', roster)]
    placement_path = ROOT / 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json'
    placement = json.loads(placement_path.read_bytes())
    modules.append(('source_spawn_rectangle', {'rules': [rule for rule in placement['rules'] if rule['id'] == 'rule/m7_spawn_rectangle']}))
    definitions, provenance = compose_modules(modules)
    native_bindings = {}
    for identifier in row['variant_ids']:
        ref = plan['variants'][identifier]['native_reference']
        key = ref['id']
        if key in ('enemy_1220_dzoms', 'enemy_1220_dzoms_2', 'enemy_1221_dzomg',
                   'enemy_1221_dzomg_2', 'enemy_1222_dpvt', 'enemy_1222_dpvt_2'):
            unit = entity_id(key)
        elif key == 'enemy_1226_dklord_2':
            unit = 'unit/ch10/remaining/lord'
        elif key == 'enemy_1224_dsuply_2':
            unit = 'unit/ch10/remaining/supply'
        elif key == 'enemy_1225_dkmage_2':
            unit = MAGE
        else:
            raise ValueError('Required enemy source consumer absent: ' + key)
        assert unit in definitions
        native_bindings[key] = {'unit': unit, 'motion': 'WALK'}
    reg = registrations(STAGE, native, {'trap_058_gunctrl': CANNON})
    assert len(reg['records']) == 1
    record = reg['records'][0]
    initial = deepcopy(record['initial_entity'])
    initial['parameters'] = {'native_bucket': record['bucket'], 'native_instance': record['raw_native'],
                             'source_record_index': record['record_index'], 'raw_alias': record['raw_alias']}
    profile = {'native_predefines': native['predefines'], 'initial_entities': [initial],
               'card_bindings': [], 'resources': {}}
    assert not any(native.get('hardPredefines', {}).values())
    projection = deepcopy(native)
    projection['hardPredefines'] = None
    scene, controls = compose(projection, STAGE, native_bindings, env_row['map']['tile_mechanics'], predefined_profile=profile)
    scene['map'] = deepcopy(env_row['map'])
    scene['roster'] = deepcopy(roster['manifest']['metadata']['roster'])
    assert len(scene['roster']) == 12
    scene['rules'] = {'movement.speed': 'rule/ch10/environment/native_speed', 'movement.path': 'rule/ch10/environment/diagonal_path'}
    scene['resources']['life'] = {'initial': 99999, 'capacity': 99999}
    if controls:
        modules.append(('native_UI_information_controls', {'definitions': controls}))
    definitions, _ = compose_modules(modules)
    integrated = {'schemaVersion': 2, 'definitions': list(definitions.values())}
    before_binding = deepcopy(integrated['definitions'])
    binding_view = {'entities': [d for d in integrated['definitions'] if d['kind'] == 'entity'],
                    'rules': [d for d in integrated['definitions'] if d['kind'] in ('rule', 'calculation_rule')]}
    bind_recipients(binding_view)
    existing_ids = {d['id'] for d in integrated['definitions']}
    integrated['definitions'].extend(rule for rule in binding_view['rules'] if rule['id'] not in existing_ids)
    ally_ids = [entity['id'] for entity in integrated['definitions'] if entity['kind'] == 'entity' and
                entity['components'].get('selection_state', {}).get('side', 0) == 0]
    receivers(integrated, entities=ally_ids)
    bind_status_definitions(integrated)
    modules = [('explicit_final_combination', integrated)]
    package, composition = reachable_content(scene, modules, manifest_id='package/ch10/source/' + STAGE, providers=providers())
    births = sum(action['count'] for wave in scene['timeline']['waves'] for fragment in wave['fragments']
                 for action in fragment['actions'] if action['kind'] == 'spawn')
    assert births == 32 and scene['resources']['dp']['initial'] == 10 and scene['parameters']['deploy_capacity'] == 8
    changes = {d['id']: {'before': old, 'after': d} for d in integrated['definitions']
               for old in before_binding if old['id'] == d['id'] and old != d}
    paths = [PLAN, roster_path, placement_path, Path(__file__), ROOT / 'tools/chapter10_stage_assembly_v1/providers.py',
             ROOT / 'tools/campaign_elemental_receivers_v1/build.py', ROOT / 'tools/chapter10_dkmage_source_v1/build.py',
             ROOT / 'tools/chapter10_remaining_v2/build.py', ROOT / 'tools/chapter10_remaining_v1/build.py',
             ROOT / 'tools/chapter10_gunctrl_v3/build.py', ROOT / 'tools/chapter10_environment_v1/build.py',
             ROOT / 'tools/chapter10_bloodline_v1/build.py']
    package['manifest']['metadata'].update({'source_locks': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'native_document': native, 'native_bindings': native_bindings, 'native_registration': reg,
        'raw_duplicate_actor_authority': {'matched_raw': deduplicated, 'authority': 'lord source bridge after explicit recipient wrapper'},
        'explicit_definition_changes': changes, 'raw_module_provenance': provenance,
        'source_births': births, 'source_routes': 30, 'only_base_life_override': 99999,
        'required_runtime': implementation_digest(), 'whole_stage_executed': False, 'client_verified': False,
        'pending_model_gaps': ['New elemental lease validation candidate integration', 'Independent complete source assembly review',
                               'Fixed public12 deployment/commands and whole process/CP/head'],
        'admission_status': 'Complete source draft; no whole-stage/model approval'})
    Compiler(providers=providers()).compile(package)
    return package


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime_root.resolve()))
    sys.path.insert(1, str(ROOT))
    value = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert not args.output.exists()
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'package': str(args.output), 'definitions': len(value['definitions']), 'source_births': 32}))
