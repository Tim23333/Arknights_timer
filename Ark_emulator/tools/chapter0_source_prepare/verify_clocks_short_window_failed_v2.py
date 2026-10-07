"""Source-capped custom hit/full clocks, native intervals and complete CPP/head."""
from copy import deepcopy
import hashlib
import json
import math
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
from tools.chapter0_source_prepare.verify_consumers_v1 import fixture, ORACLES
MODULE = ROOT / 'packages/campaign/chapter0_consumers/enemies.module.v2.json'


def main():
    output = ROOT / 'validation/campaign/chapter0_source_prepare/clocks.actual.v2.json'
    if output.exists():raise FileExistsError(output)
    source = json.loads(MODULE.read_bytes())
    paths = [MODULE, Path(__file__), ROOT / 'tools/chapter0_source_prepare/verify_consumers_v1.py', ROOT / 'tools/campaign_ordered_checkpoint.py']
    paths += [p for p in (ROOT / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json') and 'validation' not in p.relative_to(ROOT / 'ark_sim').parts]
    guards = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before, core = guards(), implementation_digest()
    report = {'schema': 'ark-sim/chapter0-capped-clock-actual/v2', 'core': core,
              'source_before': before, 'cases': [], 'native_method_formula_verified': False,
              'whole_stage': False, 'client_verified': False}
    for key, (_, hit_frame) in ORACLES.items():
        if hit_frame is None:continue
        original = next(d for d in source['entities'] if d['id'] == 'unit/ch0/' + key)
        ability = next(a for a in source['abilities'] if a['id'] == original['components']['abilities'][0])
        raw = ability['metadata']['native_owned_node']['raw'];cap = raw['_maxAnimScale']
        for speed in (1.25, .75):
            try:
                p = deepcopy(source);p['scenarioDraft'] = fixture(key)['scenarioDraft']
                p['entities'].append(fixture(key)['entities'][-1])
                actor = next(d for d in p['entities'] if d['id'] == original['id'])
                actor['components']['attributes']['base']['attack_speed_ratio'] = speed
                program = Compiler().compile(p);a = Engine.create(program, seed=83)
                a.advance(5)
                path = Path(os.environ['ARKSIM_RUN_DIR']) / (key + '_' + str(speed) + '.checkpoint.json')
                pin = write_ordered(path, a.checkpoint());b = Engine.restore(program, load_bound(path, pin))
                a.advance(115);b.advance(115);h = replay(program, a.export_replay())
                assert a.checkpoint() == b.checkpoint() == h.checkpoint()
                assert list(a.session.events) == list(b.session.events) == list(h.session.events)
                starts = [e for e in a.session.events if e['type'] == 'ability.started']
                hits = [e for e in a.session.events if e['type'] == 'damage.accepted']
                finishes = [e for e in a.session.events if e['type'] == 'ability.finished']
                scale = max(.1, min(speed, cap) if cap > 0 else speed)
                windup = math.ceil(ability['timeline'][0]['at_seconds'] / scale * 30)
                duration = math.ceil(ability['duration_seconds'] / scale * 30)
                interval = math.ceil(original['components']['attributes']['base']['attack_interval'] / speed * 30)
                assert hits[0]['time'] == starts[0]['time'] + windup
                assert finishes[0]['time'] == starts[0]['time'] + duration
                assert len(starts) >= 2 and starts[1]['time'] - starts[0]['time'] == interval
                report['cases'].append({'key': key, 'speed': speed, 'passed': True, 'raw_cap': cap,
                                        'windup_ticks': windup, 'full_ticks': duration, 'interval_ticks': interval,
                                        'actual_first_hit': hits[0]['time'], 'actual_first_finish': finishes[0]['time'],
                                        'checkpoint_sha256': pin, 'complete_CP_head_equal': True,
                                        'complete_checkpoint_digest': digest(a.checkpoint())})
            except Exception:report['cases'].append({'key': key, 'speed': speed, 'passed': False, 'error': traceback.format_exc()})
    report['source_after'] = guards()
    report['identity_stable'] = before == report['source_after'] and core == implementation_digest()
    report['passed'] = report['identity_stable'] and len(report['cases']) == 14 and all(c['passed'] for c in report['cases'])
    report['actual_exit'] = 0 if report['passed'] else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'cases': [{'key': c['key'], 'speed': c['speed'], 'passed': c['passed']} for c in report['cases']]}))
    return report['actual_exit']


if __name__ == '__main__':raise SystemExit(main())
