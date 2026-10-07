"""Actual chapter0 native-hit/blocker/no-target/flyer model checks."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2];sys.path.insert(0, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import digest, thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound

MODULE = ROOT / 'packages/campaign/chapter0_consumers/enemies.module.v1.json'
ORACLES = {'enemy_1007_slime': (130, 10), 'enemy_1027_mob': (250, 12),
           'enemy_1030_wteeth': (500, 19), 'enemy_1000_gopro': (190, 18),
           'enemy_1007_slime_2': (185, 10), 'enemy_1002_nsabr': (200, 12),
           'enemy_1029_shdsbr': (240, 12), 'enemy_1005_yokai': (0, None)}


def fixture(key, distance=0):
    p = json.loads(MODULE.read_bytes())
    p['entities'].append({'id': 'unit/ch0/probe/player', 'kind': 'entity', 'tags': ['player'],
                          'components': {'attributes': {'base': {'max_hp': 10000, 'atk': 0, 'def': 37, 'mres': 0, 'block_count': 1}},
                                         'resources': {'hp': {'role': 'health', 'initial': 10000, 'capacity': 10000}},
                                         'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1},
                                         'spatial': {'blocking': True}, 'abilities': [],
                                         'deployable': {'base_cost': 0, 'terrain': 'ground', 'capacity': 1},
                                         'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    p['scenarioDraft'] = {'id': 'scene/ch0/source/' + key, 'ruleset': 'ruleset/ark_standard',
                          'map': {'rows': 3, 'cols': 6},
                          'initialEntities': [{'definition': 'unit/ch0/' + key, 'instanceAlias': 'enemy',
                                               'position': {'row': 1, 'col': distance},
                                               'route': {'motionMode': 'FLY' if key == 'enemy_1005_yokai' else 'WALK',
                                                         'startPosition': {'row': 1, 'col': distance},
                                                         'endPosition': {'row': 1, 'col': 5}, 'checkpoints': []}},
                                              {'definition': 'unit/ch0/probe/player', 'instanceAlias': 'player',
                                               'position': {'row': 1, 'col': 0}}]}
    return p


def main():
    output = ROOT / 'validation/campaign/chapter0_source_prepare/consumers.actual.v1.json'
    if output.exists():raise FileExistsError(output)
    paths = [MODULE, Path(__file__), ROOT / 'tools/campaign_ordered_checkpoint.py']
    paths += [p for p in (ROOT / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json') and 'validation' not in p.relative_to(ROOT / 'ark_sim').parts]
    guard = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before, core = guard(), implementation_digest()
    result = {'schema': 'ark-sim/chapter0-consumer-actual/v1', 'core': core, 'cases': [],
              'source_before': before, 'whole_stage': False, 'client_verified': False}
    for key, (attack, frame) in ORACLES.items():
        try:
            p = fixture(key);program = Compiler().compile(p)
            a = Engine.create(program, seed=37);a.advance(5)
            path = Path(os.environ['ARKSIM_RUN_DIR']) / (key + '.checkpoint.json')
            pin = write_ordered(path, a.checkpoint());b = Engine.restore(program, load_bound(path, pin))
            a.advance(35);b.advance(35);h = replay(program, a.export_replay())
            assert a.checkpoint() == b.checkpoint() == h.checkpoint()
            assert list(a.session.events) == list(b.session.events) == list(h.session.events)
            hits = [thaw(e) for e in a.session.events if e['type'] == 'damage.accepted']
            if frame is not None:
                starts = [e for e in a.session.events if e['type'] == 'ability.started' and e['payload']['source'] == a.session.world.resolve('enemy')]
                assert len(hits) == len(starts) == 1 and hits[0]['payload']['amount'] == attack - 37
                assert hits[0]['time'] == starts[0]['time'] + frame
                assert a.ctx.resources.current('player', 'hp') == 10000 - (attack - 37)
                assert a.ctx.get('enemy', ('runtime', 'blocked_by')) == a.session.world.resolve('player')
                far = fixture(key, distance=2);f = Engine.create(Compiler().compile(far), seed=37);f.advance(40)
                assert not [e for e in f.session.events if e['type'] == 'damage.accepted']
            else:
                assert not hits and a.ctx.resources.current('player', 'hp') == 10000
                assert a.ctx.get('enemy', ('runtime', 'blocked_by')) is None
                assert a.ctx.get('enemy', ('spatial', 'position'))['col'] > 0
            result['cases'].append({'key': key, 'passed': True, 'actual_hits': hits,
                                    'checkpoint_sha256': pin, 'complete_CP_head_equal': True,
                                    'complete_checkpoint_digest': digest(a.checkpoint())})
        except Exception:
            result['cases'].append({'key': key, 'passed': False, 'error': traceback.format_exc()})
    result['source_after'] = guard()
    result['identity_stable'] = before == result['source_after'] and core == implementation_digest()
    result['passed'] = result['identity_stable'] and all(c['passed'] for c in result['cases'])
    result['actual_exit'] = 0 if result['passed'] else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': result['passed'], 'results': [{'key': c['key'], 'passed': c['passed']} for c in result['cases']]}))
    return result['actual_exit']


if __name__ == '__main__':raise SystemExit(main())
