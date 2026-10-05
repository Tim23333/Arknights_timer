"""Independent source aura cap and actual silence recovery with ordered CP/head."""
import json
import os
import traceback
import hashlib
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter10_remaining_v1.build import build, bind_recipients, providers, SOURCE, ROOT, MARK


def fixture(key, sources, members):
    native = json.loads((ROOT / 'packages/campaign/chapter10_source_prepare/enemies.native.v1.json').read_bytes())
    raw = next(buff for entry in native['prefabs']['enemy_1220_dzoms']['components'].values()
               for buff in entry['raw'].get('_buffs', []) if buff['buffKey'] == 'enemy_bloodsucker_mark')
    package = build(key, bloodsucker_mark={'id': MARK, 'kind': 'buff', 'metadata': {'native_inline': raw}})
    # Test-only automatic condition keeps the owned attack and source callbacks.
    package['abilities'][0]['activation']['condition'] = 'False'
    body = package['entities'][0]['id']
    package['buffs'].append({'id': 'buff/independent/remaining/silence', 'kind': 'buff',
                             'selection_flags': {'abnormal_flags': [12]}})
    initial = [{'definition': body, 'instanceAlias': 'aura' + str(i), 'position': {'row': 1, 'col': i + 1}}
               for i in range(sources)]
    for i in range(members):
        name = 'unit/independent/remaining/blood' + str(i)
        package['entities'].append({'id': name, 'kind': 'entity', 'tags': ['enemy'],
            'components': {'attributes': {'base': {'max_hp': 8191, 'atk': 777, 'def': 319, 'mres': 47}},
                'resources': {'hp': {'role': 'health', 'initial': 8191, 'capacity': 8191}},
                'selection_state': {'side': 1, 'motion': 1, 'category': 1, 'unit_type': 2},
                'spatial': {}, 'buffs': {'initial': [MARK]}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
        initial.append({'definition': name, 'instanceAlias': 'blood' + str(i), 'position': {'row': 5, 'col': i}})
    scheduled = []
    if sources == 7:
        # Actual flag application/removal, retaining the original aura identities.
        for actor in (2, 3, 4):
            scheduled.append({'at': 5, 'effect': {'op': 'apply_buff', 'target': actor,
                                                'buff': 'buff/independent/remaining/silence'}})
        scheduled.append({'at': 7, 'effect': {'op': 'remove_buff', 'target': 2,
                                            'buff': 'buff/independent/remaining/silence'}})
    else:
        # Source cap6 becomes five actual members after three marker removals.
        for actor in (3, 4, 5):
            scheduled.append({'at': 5, 'effect': {'op': 'remove_buff', 'target': actor, 'buff': MARK}})
    package['scenarioDraft'] = {'id': 'scene/independent/remaining/' + key, 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 7, 'cols': 12}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
        'initialEntities': initial, 'scheduledEffects': scheduled}
    return bind_recipients(package)


def create(package):
    registry = providers()
    return Engine.create(Compiler(providers=registry).compile(package), providers=registry, seed=32719)


def run_case(package, label, target, expected):
    sim = create(package)
    actual = {}
    for tick in (3, 6, 8):
        sim.advance(tick - sim.session.time)
        actual[str(tick)] = sim.ctx.attributes.value(target, 'atk')
    assert actual == expected, repr(actual)
    straight = create(package)
    straight.advance(10)
    resumed = create(package)
    checkpoints = []
    for tick in (4, 5, 6, 7):
        resumed.advance(tick - resumed.session.time)
        path = Path(os.environ['ARKSIM_RUN_DIR']) / (label + str(tick) + '.checkpoint.json')
        pin = write_ordered(path, resumed.checkpoint())
        resumed = Engine.restore(resumed.program, load_bound(path, pin), providers=providers())
        checkpoints.append({'tick': tick, 'sha256': pin})
    resumed.advance(10 - resumed.session.time)
    head = replay(straight.program, straight.export_replay(), providers=providers())
    assert straight.checkpoint() == resumed.checkpoint() == head.checkpoint()
    assert list(straight.session.events) == list(resumed.session.events) == list(head.session.events)
    return {'actual_attack': actual, 'ordered_checkpoints': checkpoints, 'full_cp_head_equal': True}


def main():
    paths = [SOURCE, Path(__file__), ROOT / 'tools/chapter10_remaining_v1/build.py']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = {str(p): sha(p) for p in paths}
    report = {'schema': 'ark-sim/remaining-independent-peer/v1', 'source_before': before,
              'whole_stage': False, 'client_verified': False, 'cases': [], 'comparison_exclusions': []}
    try:
        lord = run_case(fixture('enemy_1226_dklord_2', 1, 8), 'lord', 'aura0', {'3': 3000, '6': 2700, '8': 2700})
        report['cases'].append({'case': 'actual_mark_removal_lord_cap6', **lord})
        supply = run_case(fixture('enemy_1224_dsuply_2', 7, 1), 'supply', 'blood0', {'3': 1165.5, '6': 1087.8, '8': 1165.5})
        report['cases'].append({'case': 'seven_sources_actual_silence_drop_and_restore_cap5', **supply})
        report['passed'] = True
    except Exception:
        report['passed'] = False
        report['error'] = traceback.format_exc()
    report['source_after'] = {str(p): sha(p) for p in paths}
    report['source_guard_equal'] = before == report['source_after']
    report['actual_exit'] = 0 if report['passed'] and report['source_guard_equal'] else 1
    out = ROOT / 'validation/campaign/chapter10_remaining_peer_v1/actual.v1.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': report['actual_exit'], 'error': report.get('error')}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
