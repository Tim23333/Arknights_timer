"""Isolated storage comparison: same V2 algorithm/event values, separate RSS."""
import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from tools.audit_m7_trace_storage import rss


def unique_containers(value):
    seen, stack = set(), [value]
    while stack:
        item = stack.pop()
        if not isinstance(item, (Mapping, tuple, list)) or id(item) in seen:
            continue
        seen.add(id(item))
        stack.extend(item.values() if isinstance(item, Mapping) else item)
    return len(seen)


def run(storage, ticks):
    import ark_sim.kernel.session as sessions
    import ark_sim.domains.context as contexts
    if storage == 'legacy':
        from tools.m8_trace_legacy_reference import LegacyEventLog, legacy_compact_trace
        sessions.EventLog = LegacyEventLog
        contexts.compact_trace = legacy_compact_trace
    package = ROOT/'validation/campaign/m7_00_10_frozen_exploratory_20261002.package.json'
    commands = ROOT/'validation/campaign/m7_00_10_frozen_exploratory_20261002.commands.json'
    program = Compiler().compile(json.loads(package.read_bytes()))
    sim = Engine.create(program, seed=953816614)
    for row in json.loads(commands.read_bytes()):
        action = dict(row);sim.submit(action, at=action.pop('at'))
    before = rss();start = time.perf_counter();sim.advance(ticks);elapsed = time.perf_counter()-start
    after = rss()
    digest = hashlib.sha256()
    event_bytes = 0
    for row in sim.session.events:
        raw = json.dumps(thaw(row), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')
        digest.update(raw);digest.update(b'\n');event_bytes += len(raw)
    state = sim.ctx.state()
    return {'schema': 'ark-sim/m8-storage-benchmark/v1', 'storage': storage, 'ticks': ticks, 'elapsed_seconds': elapsed,
        'rss_before': before, 'rss_after': after, 'event_count': len(sim.session.events), 'event_value_sha256': digest.hexdigest(),
        'serialized_event_bytes': event_bytes, 'unique_retained_event_containers': unique_containers(sim.session.events),
        'state': state, 'runtime_fingerprint': sim.runtime_fingerprint, 'program_fingerprint': program.fingerprint,
        'same_current_V2_algorithm_with_legacy_storage_reference': True,
        'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest(),
        'commands_sha256': hashlib.sha256(commands.read_bytes()).hexdigest(),
        'limitations': ['prefix only, not full4500 RSS estimate', 'legacy storage reference does not reproduce old runtime source identity']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage', choices=['legacy', 'current'], required=True)
    parser.add_argument('--ticks', type=int, default=30)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.ticks <= 300:
        raise ValueError('isolated benchmark prefix must stay between1 and300 ticks')
    value = run(args.storage, args.ticks)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: value[k] for k in ('storage', 'ticks', 'elapsed_seconds', 'rss_after', 'event_count',
        'unique_retained_event_containers', 'event_value_sha256')}))
