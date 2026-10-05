"""Independent public incoming-zero and outgoing-3000 cannon verification."""
import json
import os
import hashlib
import traceback
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter10_gunctrl_v3.build import build, providers, ROOT
from tools.chapter10_gunctrl_v1.build import BODY, P, SOURCE, bind_status_definitions


def main():
    package = build()
    package['selectors'].append({'id': 'selector/independent/cannon_body', 'kind': 'selector',
        'region': {'type': 'all'}, 'filters': [{'tag': 'gunctrl'}, {'state': 'alive'}], 'limit': 1})
    abilities, commands = [], []
    for tick, kind in [(4, 'physical'), (7, 'arts'), (9, 'true')]:
        aid = 'ability/independent/cannon_input/' + kind
        abilities.append(aid)
        package['abilities'].append({'id': aid, 'kind': 'ability', 'activation': {'mode': 'manual'},
            'selector': 'selector/independent/cannon_body',
            'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': kind, 'scale': 1}}]})
        commands.append({'at': tick, 'action': 'skill', 'source': 'focus', 'ability': aid})
    package['entities'].append({'id': 'unit/independent/cannon_focus', 'kind': 'entity', 'tags': ['player'],
        'components': {'attributes': {'base': {'max_hp': 25117, 'atk': 13791, 'def': 317, 'mres': 47, 'block_count': 2}},
            'resources': {'hp': {'role': 'health', 'initial': 25117, 'capacity': 25117}},
            'abilities': abilities, 'selection_state': {'side': 0, 'category': 1, 'motion': 1, 'unit_type': 1},
            'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    package['scenarioDraft'] = {'id': 'scene/independent/cannon_v3', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 9, 'cols': 11}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
        'initialEntities': [{'definition': BODY, 'instanceAlias': 'cannon', 'position': {'row': 2, 'col': 2}},
                            {'definition': 'unit/independent/cannon_focus', 'instanceAlias': 'focus', 'position': {'row': 5, 'col': 6}}],
        'commands': commands, 'scheduledEffects': [{'at': 10, 'effect': {'op': 'modify_resource', 'target': 2, 'resource': 'sp', 'value': 120}}]}
    bind_status_definitions(package)
    files = [SOURCE, Path(__file__), ROOT / 'tools/chapter10_gunctrl_v1/build.py',
             ROOT / 'tools/chapter10_gunctrl_v2/build.py', ROOT / 'tools/chapter10_gunctrl_v3/build.py']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = {str(p): sha(p) for p in files}
    report = {'schema': 'ark-sim/gunctrl-independent-peer/v3', 'source_before': before,
              'whole_stage': False, 'client_verified': False, 'comparison_exclusions': []}
    def create():
        registry = providers()
        return Engine.create(Compiler(providers=registry).compile(package), providers=registry, seed=15509)
    try:
        straight = create()
        straight.advance(14)
        resumed = create()
        cps = []
        for tick in (5, 10, 11):
            resumed.advance(tick - resumed.session.time)
            path = Path(os.environ['ARKSIM_RUN_DIR']) / (str(tick) + '.checkpoint.json')
            pin = write_ordered(path, resumed.checkpoint())
            resumed = Engine.restore(resumed.program, load_bound(path, pin), providers=providers())
            cps.append({'tick': tick, 'sha256': pin})
        resumed.advance(14 - resumed.session.time)
        head = replay(straight.program, straight.export_replay(), providers=providers())
        assert straight.checkpoint() == resumed.checkpoint() == head.checkpoint()
        assert list(straight.session.events) == list(resumed.session.events) == list(head.session.events)
        hits = [thaw(e) for e in straight.session.events if e['type'] == 'damage.accepted']
        incoming = [e for e in hits if e['payload']['target'] == 2]
        outgoing = [e for e in hits if e['payload']['source'] == 2]
        report.update(actual_HP={'cannon': straight.ctx.resources.current('cannon', 'hp'),
                                'focus': straight.ctx.resources.current('focus', 'hp')},
                      actual_hits=hits, ordered_CP=cps, full_cp_head_equal=True)
        assert len(incoming) == 3 and all(e['payload']['amount'] == 0 for e in incoming)
        assert len(outgoing) == 1 and outgoing[0]['payload']['amount'] == 3000
        assert report['actual_HP'] == {'cannon': 10000, 'focus': 22117}
        assert straight.ctx.alive('cannon') and straight.ctx.spatial.selection_state('cannon')['abnormal_flags'] == [5, 7]
        report['passed'] = True
    except Exception:
        report['passed'] = False
        report['error'] = traceback.format_exc()
    report['source_after'] = {str(p): sha(p) for p in files}
    report['source_guard_equal'] = before == report['source_after']
    report['actual_exit'] = 0 if report['passed'] and report['source_guard_equal'] else 1
    output = ROOT / 'validation/campaign/chapter10_gunctrl_peer_v1/actual.v3.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': report['actual_exit'], 'error': report.get('error')}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
