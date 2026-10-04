"""Root's separate source and overlay review; does not invoke author audit."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'validation/campaign/chapter02_03_refjoin_v1'
CORE = '8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from tools.build_campaign_runthrough_input import apply
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest() == CORE
    freeze = read(OUT / 'freeze.json')
    assert freeze['core'] == CORE and sha(OUT / 'freeze.json') == '41b6516c3f44ff3999c084614de928ad11f24d25a55d6036c36f187148f6c653'
    for rel, pin in freeze['evidence_artifacts'].items():
        assert sha(ROOT / rel) == pin, rel
    prefix = read(OUT / 'prefix_verification.json')
    assert prefix['core'] == CORE and prefix['guards_equal']
    assert prefix['guards_before'] == prefix['guards_after']
    for path, pin in prefix['guards_after'].items():
        assert sha(Path(path)) == pin, path
    results = []
    prep = read(OUT / 'preparation.json')
    mapping = {'max_hp': 'maxHp', 'atk': 'atk', 'def': 'def', 'mres': 'magicResistance',
               'move_speed': 'moveSpeed', 'attack_interval': 'baseAttackTime', 'mass_level': 'massLevel'}
    for item in prep['results']:
        stage = item['stage']
        package_path, life_path = Path(item['native_package']), Path(item['life_package'])
        package, life = read(package_path), read(life_path)
        assert life == apply(package, sha(package_path))
        parent = read(ROOT / item['source_parent'])
        assert package['definitions'] == parent['definitions'] == life['definitions']
        for key in parent['scenarioDraft']:
            if key not in {'id', 'metadata'}:
                assert package['scenarioDraft'][key] == parent['scenarioDraft'][key], key
        commands = Path(item['commands'])
        old_commands = ROOT / ('scenarios/campaign/chapter02/02-10/commands.runthrough_exploratory_v1.json'
                               if stage == '02-10' else 'scenarios/campaign/chapter03/03-08/commands.runthrough_v1.json')
        assert commands.read_bytes() == old_commands.read_bytes()
        if stage == '02-10':
            source_path = ROOT / 'packages/campaign/chapter02_sources/native.reference.json'
            source = read(source_path)
            native = read(ROOT / 'packages/campaign/native_reference/level_main_02-10.json')
            bindings = read(ROOT / 'packages/campaign/chapter02_units/main_02-10.enemies.combat_guard.reference_module.json')['manifest']['metadata']['variant_bindings']
        else:
            source_path = ROOT / 'packages/campaign/chapter03_plans/source.plan.json'
            source = read(source_path)
            native = source['stages']['level_main_03-08']['native_document']
            bindings = package['manifest']['metadata']['variant_bindings']
        definitions = {d['id']: d for d in package['definitions']}
        scene = package['scenarioDraft']
        population = Counter()
        action_rows = 0
        for wi, wave in enumerate(scene['timeline']['waves']):
            assert len(wave['fragments']) == len(native['waves'][wi]['fragments'])
            for fi, fragment in enumerate(wave['fragments']):
                assert len(fragment['actions']) == len(native['waves'][wi]['fragments'][fi]['actions'])
                for ai, action in enumerate(fragment['actions']):
                    raw = native['waves'][wi]['fragments'][fi]['actions'][ai]
                    assert action['metadata']['native_action_index'] == ai and action['metadata']['native_action'] == raw
                    for actual_key, source_key in [('count','count'), ('managed','managedByScheduler'), ('delay_seconds','preDelay'), ('interval_seconds','interval'), ('blocks_fragment','blockFragment')]:
                        assert action[actual_key] == raw[source_key]
                    assert action['blocks_wave'] == (not raw['dontBlockWave'])
                    action_rows += 1
                    if action['kind'] != 'spawn':
                        continue
                    population[action['spawn']['definition']] += raw['count']
                    route = deepcopy(native['routes'][raw['routeIndex']])
                    rows = scene['map']['rows']
                    for k in ('startPosition','endPosition'):
                        route[k]['row'] = rows - 1 - route[k]['row']
                    route['checkpoints'] = route.get('checkpoints') or []
                    for cp in route['checkpoints']:
                        if cp.get('position') is not None:
                            cp['position']['row'] = rows - 1 - cp['position']['row']
                    for k, value in route.items():
                        if k != 'motionMode':
                            assert action['spawn']['route'][k] == value, (stage,k)
        checked = []
        pending_reference_defaults = []
        assert {b['unit_definition'] for b in bindings} == set(population)
        for binding in bindings:
            variant = source['variants'][binding['variant_id']]
            assert variant['native_reference'] == binding['native_reference']
            assert binding['native_reference'] in native['enemyDbRefs']
            definition = definitions[binding['unit_definition']]
            attrs = variant['native_enemy']['resolved']['attributes']
            base = definition['components']['attributes']['base']
            for actual_key, source_key in mapping.items():
                if source_key not in attrs:
                    assert source_key == 'massLevel' and base[actual_key] == 0
                    assert all(not row['enemyData']['attributes']['massLevel']['m_defined']
                               for row in variant['native_enemy']['raw_rows'])
                    pending_reference_defaults.append({'unit':definition['id'], 'field':actual_key,
                        'selected_value':0, 'reason':'Source table massLevel undefined; explicit existing reference default, client/native default unproved'})
                    continue
                assert base[actual_key] == attrs[source_key], (stage, binding['variant_id'], actual_key)
            assert base['attack_speed_ratio'] == attrs['attackSpeed'] / 100
            health = definition['components']['resources']['hp']
            assert health['initial'] == base['max_hp']
            if 'capacity' in health:
                assert health['capacity'] == base['max_hp']
            else:
                assert health['capacity_attribute'] == 'max_hp'
            assert definition['components']['lifecycle']['leak_loss'] == variant['native_enemy']['resolved']['lifePointReduce']
            checked.append({'unit': definition['id'], 'variant': binding['variant_id'], 'base_attributes': base, 'hp': health, 'births': population[definition['id']]})
        assert scene['metadata']['native_options'] == native['options']
        assert scene['parameters']['deploy_capacity'] == native['options']['characterLimit']
        assert scene['resources']['dp']['initial'] == native['options']['initialCost']
        assert scene['resources']['life']['initial'] == native['options']['maxLifePoint'] == 3
        assert scene['initialEntities'] == [] and len(scene['roster']) == 12
        results.append({'stage': stage, 'passed': True, 'births': sum(population.values()), 'source_action_rows': action_rows,
                        'source_sha': sha(source_path), 'package_sha': sha(package_path), 'overlay_sha': sha(life_path),
                        'commands_sha': sha(commands), 'variants': checked,
                        'pending_reference_defaults':pending_reference_defaults})
    assert implementation_digest() == CORE
    report = OUT / 'root_independent_source_review.json'
    with report.open('x', encoding='utf8') as f:
        json.dump({'core':CORE, 'passed':True, 'results':results, 'helper_sha':sha(Path(__file__)),
                   'author_freeze_sha':sha(OUT/'freeze.json'), 'scope':'Separate root source arithmetic/input review; no old checkpoint migration, whole-stage or client approval'}, f, indent=2)
    print(json.dumps({'passed':True, 'stages':len(results), 'sha':sha(report)}))


if __name__ == '__main__':
    main()
