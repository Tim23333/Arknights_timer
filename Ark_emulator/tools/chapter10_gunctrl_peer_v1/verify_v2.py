"""Independent numeric, native mask and actual ordered CP/head verification."""
import os
import json
import hashlib
import traceback
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter10_gunctrl_v2.build import build, providers, ROOT
from tools.chapter10_gunctrl_v1.build import BODY, MARK, SHOT, SOURCE, RANGE, P

LOG = Path(os.environ['ARKSIM_RUN_DIR'])
OUT = ROOT / 'validation/campaign/chapter10_gunctrl_peer_v1'


def fixture(retire=False):
    package = build()
    initial = [{'definition': BODY, 'instanceAlias': 'cannon', 'position': {'row': 0, 'col': 0}}]
    rows = [('anchor', 0, {'block_count': 3}, {}, (5, 4)),
            ('same_side', 1, {'block_count': 99}, {}, (5, 5)),
            ('ally_free', 1, {}, {'ally_target_free': True}, (5, 6)),
            ('enemy_free', 0, {}, {'ally_target_free': True}, (4, 4)),
            ('target_free', 0, {}, {'target_free': True}, (4, 5)),
            ('air', 1, {}, {'motion': 2}, (6, 5)),
            ('neutral', 2, {}, {}, (6, 4)),
            ('device', 1, {}, {'category': 4}, (6, 6)),
            ('invisible', 1, {}, {'invisible': True}, (5, 3)),
            ('camouflage', 0, {}, {'camouflage': True}, (4, 3)),
            ('corner', 1, {}, {}, (7, 6))]
    package['buffs'] += [{'id': 'buff/independent/cannon/block', 'kind': 'buff',
                         'modifiers': [{'attribute': 'block_count', 'layer': 'flat', 'value': 5}]},
                        {'id': 'buff/independent/cannon/noblock', 'kind': 'buff', 'control': {'block': False}}]
    for name, side, attrs, status, position in rows:
        entity = 'unit/independent/cannon/' + name
        package['entities'].append({'id': entity, 'kind': 'entity', 'tags': ['enemy'] if side == 1 else ['player'],
            'dependencies': ['buff/independent/cannon/block', 'buff/independent/cannon/noblock'],
            'components': {'attributes': {'base': {'max_hp': 9917, 'atk': 0, 'def': 781, 'mres': 57, 'block_count': 0, **attrs}},
                'resources': {'hp': {'role': 'health', 'initial': 9917, 'capacity': 9917}},
                'selection_state': {'side': side, 'motion': 1, 'category': 1, **status}, 'spatial': {},
                'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
        initial.append({'definition': entity, 'instanceAlias': name, 'position': {'row': position[0], 'col': position[1]}})
    scheduled = [{'at': 9, 'effect': {'op': 'modify_resource', 'target': 2, 'resource': 'sp', 'value': 120}}]
    if retire:
        scheduled.append({'at': 10, 'effect': {'op': 'retire', 'target': 3, 'parameters': {'reason': 'withdraw'}}})
    package['scenarioDraft'] = {'id': 'scene/independent/cannon_native_v2', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 12, 'cols': 12}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
        'initialEntities': initial, 'scheduledEffects': scheduled}
    from tools.chapter10_gunctrl_v1.build import bind_status_definitions
    return bind_status_definitions(package)


def create(package):
    registry = providers()
    program = Compiler(providers=registry).compile(package)
    return Engine.create(program, providers=registry, seed=918347)


def cp_head(package, label):
    straight = create(package)
    straight.advance(14)
    resumed = create(package)
    files = []
    for tick in (8, 9, 10, 11):
        resumed.advance(tick - resumed.session.time)
        path = LOG / (label + '.' + str(tick) + '.checkpoint.json')
        sha = write_ordered(path, resumed.checkpoint())
        files.append({'tick': tick, 'path': str(path), 'sha256': sha})
        resumed = Engine.restore(resumed.program, load_bound(path, sha), providers=providers())
    resumed.advance(14 - resumed.session.time)
    head = replay(straight.program, straight.export_replay(), providers=providers())
    assert straight.checkpoint() == resumed.checkpoint() == head.checkpoint()
    assert list(straight.session.events) == list(resumed.session.events) == list(head.session.events)
    return straight, files


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = [SOURCE, RANGE, Path(__file__), ROOT / 'tools/chapter10_gunctrl_v1/build.py',
               ROOT / 'tools/chapter10_gunctrl_v2/build.py']
    before = {str(p): sha(p) for p in sources}
    report = {'schema': 'ark-sim/gunctrl-independent-peer/v2', 'core': implementation_digest(),
              'source_before': before, 'cases': [], 'client_verified': False, 'whole_stage': False}
    try:
        sim, files = cp_head(fixture(), 'native')
        names = ['anchor', 'same_side', 'ally_free', 'enemy_free', 'target_free', 'air', 'neutral', 'device', 'invisible', 'camouflage', 'corner']
        hp = {name: sim.ctx.resources.current(name, 'hp') for name in names}
        expected_hit = {'anchor', 'same_side', 'enemy_free', 'target_free', 'air'}
        report['native_mask_probe'] = {'actual_hp': hp, 'expected_hit': sorted(expected_hit),
            'areas': [thaw(e) for e in sim.session.events if e['type'] == 'area.resolved']}
        assert hp == {name: 6917 if name in expected_hit else 9917 for name in names}
        report['cases'].append('all_native_area_masks_and_true3000')
        report['ordered_cp_files'] = files
        retired, retired_files = cp_head(fixture(retire=True), 'withdraw')
        areas = [thaw(e) for e in retired.session.events if e['type'] == 'area.resolved']
        report['withdraw_probe'] = areas
        assert len(areas) == 1 and areas[0]['payload']['center'] == {'row': 5, 'col': 4}
        assert not retired.ctx.active('anchor') and retired.ctx.resources.current('same_side', 'hp') == 6917
        assert retired.ctx.resources.current('ally_free', 'hp') == 9917
        report['ordered_cp_files'] += retired_files
        report['cases'].append('retired_captured_position_native_masks')
        for stage in ('level_main_10-14', 'level_main_10-15'):
            p = build(stage)
            potential = p['manifest']['metadata']['native_predefine']['inst']['potentialRank']
            assert potential == (0 if stage.endswith('14') else 1)
            if stage.endswith('15'):
                for kwargs in ({'require_complete': True}, {'manfred_sp_binding': {'placeholder': True}}):
                    try: build(stage, **kwargs)
                    except ValueError: pass
                    else: raise AssertionError('Unimplemented required Manfred endpoint accepted')
        report['cases'].append('source_potential_and_required_dependency_reject')
        foreign = create(fixture())
        old = foreign.checkpoint()
        try: foreign.command({'action': 'skill', 'source': 'anchor', 'ability': SHOT})
        except Exception: pass
        else: raise AssertionError('Foreign cannon cast accepted')
        assert old == foreign.checkpoint()
        report['cases'].append('unowned_cast_atomic_reject')
        report['full_cp_head_equal'] = True
        report['comparison_exclusions'] = []
        report['passed'] = True
    except Exception:
        report['passed'] = False
        report['failure'] = traceback.format_exc()
    report['source_after'] = {str(p): sha(p) for p in sources}
    report['source_guard_equal'] = report['source_after'] == before
    report['actual_exit'] = 0 if report['passed'] and report['source_guard_equal'] else 1
    (OUT / 'actual.v2.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': report['actual_exit'], 'cases': report['cases'], 'failure': report.get('failure')}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
