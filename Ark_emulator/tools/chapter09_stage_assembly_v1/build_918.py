"""Full source 9-18 input assembly, with runtime admission kept separate."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/source.plan.v1.json'
STAGE = 'level_main_09-16'


def build():
    from tools.chapter06_review.stage_converter_v7 import compose, exact
    from tools.chapter09_pillar_v1.registration import registrations
    from tools.chapter09_pillar_v1.build_map_profile import build as map_profile
    from tools.chapter09_pillar_v1.bigforce import build as bigforce
    from tools.chapter09_demolition_v2.build import BODY, STOCK, bind_status_definitions
    from tools.campaign_content_composition_v2 import compose_modules, reachable_content
    from tools.chapter09_stage_assembly_v1.providers import providers
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    source = json.loads(SOURCE.read_bytes()); row = source['stages'][STAGE]; native = deepcopy(row['native_document'])
    modules = []; pins = {str(SOURCE): hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
    module_names = [
        'ordinary/enemy_1165_duhond.module.v1.json', 'more_ordinary/enemy_1168_dumage.module.v1.json',
        'more_ordinary/enemy_1169_duphlx.module.v1.json', 'coupled_v2/duholy_dushdo.module.v2.json',
        'duspfr_v1/module.v1.json', 'demolition/level_main_09-16.module.v2.json']
    for name in module_names:
        path = ROOT / 'packages/campaign/chapter09_consumers' / name
        modules.append((name, json.loads(path.read_bytes()))); pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    roster_path = ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json'
    roster = json.loads(roster_path.read_bytes()); modules.append(('fixed12', roster)); pins[str(roster_path)] = hashlib.sha256(roster_path.read_bytes()).hexdigest()
    modules.append(('native_per_cell_force', bigforce()))
    definitions, _ = compose_modules(modules)
    variants = {}; native_binding = {}
    for vid in row['variant_ids']:
        raw = source['variants'][vid]['native_reference']; key = raw['id']
        if key == 'enemy_1173_duspfr': unit = 'unit/ch9/duspfr/body'
        elif key == 'enemy_1174_duholy': unit = 'unit/ch9/coupled/duholy/' + vid.split('/')[-1]
        elif key == 'enemy_1175_dushdo': unit = 'unit/ch9/coupled/dushdo/' + vid.split('/')[-1]
        else: unit = 'unit/ch9/' + key.split('_', 2)[2] + '/' + vid.split('/')[-1]
        assert unit in definitions and raw in native['enemyDbRefs']
        native_binding[key] = {'unit': unit, 'motion': 'WALK'}
        variants[vid] = {'native_reference': raw, 'unit': unit}
    registration = registrations(STAGE, native, {'trap_043_dupilr': 'unit/ch9/pillar/body'})
    assert len(registration['records']) == 3
    # The timeline converter handles only waves/options/runes. Predefines are
    # separately converted below using exact source registration records.
    projection = deepcopy(native); projection['predefines'] = {'characterInsts': [], 'tokenInsts': [], 'characterCards': [], 'tokenCards': []}
    assert not any(native.get('hardPredefines', {}).values()), 'Active hard predefines require their own exact consumer'
    projection['hardPredefines'] = None
    profile = map_profile(native)
    scene, controls = compose(projection, STAGE, native_binding, profile['tile_mechanics'])
    scene['map'] = profile
    scene['roster'] = deepcopy(roster['manifest']['metadata']['roster'])
    assert len(scene['roster']) == 12
    scene['rules'] = deepcopy(roster['manifest']['metadata']['stage_rules'])
    scene['initialEntities'] = []
    for record in registration['records']:
        item = deepcopy(record['initial_entity'])
        item['parameters'] = {'native_bucket': record['bucket'], 'native_instance': deepcopy(record['raw_native']),
                              'source_record_index': record['record_index'], 'raw_alias': record['raw_alias']}
        scene['initialEntities'].append(item)
    cards = native['predefines']['tokenCards']; assert len(cards) == 1
    card = cards[0]; assert card['inst']['characterKey'] == 'trap_045_dublst' and card['initialCnt'] == 2
    assert card['hidden'] is False and card['skillIndex'] == 0 and card['mainSkillLvl'] == 1
    assert not card.get('overrideSkillBlackboard') and not card.get('overrideTalents')
    scene['cards'] = [BODY]; scene['resources'][STOCK] = {'initial': 2, 'capacity': 2}
    scene['resources']['life'] = {'initial': 99999, 'capacity': 99999}
    scene['metadata']['native_predefines'] = deepcopy(native['predefines'])
    scene['metadata']['native_card_bindings'] = [{'native_bucket': 'tokenCards', 'native_card': deepcopy(card), 'definition': BODY, 'stock_resource': STOCK}]
    scene['metadata']['registration_policy'] = registration
    if controls: modules.append(('exact_route_preview_controls', {'definitions': controls}))
    placement_path = ROOT / 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json'
    placement = json.loads(placement_path.read_bytes()); modules.append(('source_spawn_rectangle', {'rules': [r for r in placement['rules'] if r['id'] == 'rule/m7_spawn_rectangle']}))
    pins[str(placement_path)] = hashlib.sha256(placement_path.read_bytes()).hexdigest()
    merged, _ = compose_modules(modules)
    # Status projection uses the complete final definition closure, including
    # selected operators' Buffs and the current pillar lifecycle consumers.
    authored = {'buffs': [d for d in merged.values() if d['kind'] == 'buff'], 'rules': [d for d in merged.values() if d['kind'] in ('rule', 'calculation_rule')]}
    bind_status_definitions(authored)
    changed = next(r for r in authored['rules'] if r['id'] == 'rule/ch9/demolition/push')
    speed_id = scene['rules']['movement.speed']; speed = deepcopy(merged[speed_id]); speed['parameters']['multiplier'] = native['options']['moveMultiplier']
    replacements = {speed_id: {'definition': speed, 'reason': 'Exact source moveMultiplier', 'source': str(SOURCE)},
        changed['id']: {'definition': changed, 'reason': 'Complete final Buff closure for live displacement flags', 'source': str(SOURCE)}}
    package, composition = reachable_content(scene, modules, replacements, manifest_id='package/ch9/native_draft/' + STAGE, providers=providers())
    births = sum(action['count'] for wave in scene['timeline']['waves'] for fragment in wave['fragments'] for action in fragment['actions'] if action['kind'] == 'spawn')
    assert births == row['spawn_count'] == 34
    assert scene['parameters']['deploy_capacity'] == 8 and scene['resources']['dp']['initial'] == 12
    assert exact(scene['roster'], roster['manifest']['metadata']['roster'])
    package['manifest']['metadata'].update({'source_locks': pins, 'native_source_digest': hashlib.sha256(json.dumps(native, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
        'native_options': native['options'], 'native_predefines': native['predefines'], 'variant_bindings': variants,
        'native_hard_predefines': native.get('hardPredefines'), 'difficulty_profile': 'NORMAL1; empty hard buckets kept as source, not instantiated',
        'registration_records': registration, 'source_births': 34, 'source_routes': 25, 'only_base_life_override': 99999,
        'required_runtime': implementation_digest(), 'full_stage_executed': False, 'admission_status': 'complete_source_inputs_own_core_and_whole_run_pending',
        'pending': ['Exact runtime full regression and baseline before runthrough admission', 'Independent stage source/profile/action/alias review', 'Public twelve-squad/card plan and full observations/CP/head run'],
        'client_verified': False})
    Compiler(providers=providers()).compile(package)
    return package


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT));import ark_sim
    assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim'
    package=build();args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'source_births':34,'definitions':len(package['definitions']),'package_sha':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
