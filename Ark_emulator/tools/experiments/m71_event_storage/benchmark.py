"""Bounded actual 0-1 source trace; journal retention/export/checkpoint costs.

No all-stage run. The measured input is the complete trace from 120 real ticks;
the trace is stored exactly once in each mode, without synthetic repetition.
"""
from pathlib import Path
import gc
import hashlib
import importlib.util
import json
import platform
import sys
import time
import tracemalloc
import uuid

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent/'unpack_work/campaign_m71_event_storage_candidate'
OUT = ROOT/'validation/campaign/m71_event_storage'
RUN = OUT/('run-'+uuid.uuid4().hex)
sys.path.insert(0, str(RUNTIME))
sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.kernel.events import EventLog
from ark_sim.contracts.models import digest, thaw
from tools.campaign_streaming_evidence import observations as old_observations

spec = importlib.util.spec_from_file_location('m71_v12', ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v12.py')
v12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v12)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(call):
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    result = call()
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {'seconds': elapsed, 'current_incremental_bytes': current,
                    'peak_incremental_bytes': peak}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RUN.mkdir(parents=True)
    package = ROOT/'packages/ark_content/level_main_00_01.json'
    commands_path = ROOT/'scenarios/level_main_00_01/commands.json'
    program = Compiler().compile(package)
    sim = Engine.create(program, seed=123)
    for item in json.loads(commands_path.read_text(encoding='utf8')):
        action = dict(item)
        sim.submit(action, at=action.pop('at'))
    started = time.perf_counter()
    sim.session.advance(120)
    source_elapsed = time.perf_counter() - started
    source = sim.session.events
    rows = []
    logs = []
    for mode in ('memory', 'disk'):
        def build():
            log = EventLog()
            if mode == 'disk':
                log.enable_disk(RUN/'benchmark-active.jsonl')
            for event in source:
                event_id = log.emit(event['type'], event['payload'], event['time'], event['cause'])
                assert event_id == event['id']
            return log
        log, storage = measure(build)
        assert thaw(log.records) == thaw(source)
        value_digest = digest(log.records)
        checkpoint, full = measure(log.snapshot)
        assert digest(checkpoint) == digest(sim.session._events.snapshot())
        row = {'mode': mode, 'store': storage, 'full_checkpoint': full,
               'event_value_sha256': value_digest}
        if mode == 'disk':
            reference, ref_measure = measure(lambda: log.snapshot(event_reference=True))
            exported, export_measure = measure(lambda: log.export_jsonl(RUN/'benchmark-export.jsonl'))
            row.update(reference_checkpoint=ref_measure, direct_export=export_measure,
                       reference=reference, export=exported)
        rows.append(row)
        logs.append(log)
    assert rows[0]['event_value_sha256'] == rows[1]['event_value_sha256']
    expected = old_observations(sim)
    sim.session.enable_event_journal(RUN/'simulation-active.jsonl')
    actual = v12.observations(sim, RUN/'simulation-export.jsonl')
    assert expected == {key: actual[key] for key in expected}
    cp_meta = v12.write_checkpoint(sim, RUN/'simulation-checkpoint.json')
    restored = Engine.restore(program, json.loads(Path(cp_meta['path']).read_text(encoding='utf8')))
    assert restored.snapshot() == sim.snapshot()
    sim.session.advance(30)
    restored.session.advance(30)
    assert sim.snapshot() == restored.snapshot()
    files = sorted((RUNTIME/'ark_sim').rglob('*.py'))
    sources = {str(p.relative_to(RUNTIME/'ark_sim')): sha(p) for p in files}
    core = hashlib.sha256(json.dumps(sources, sort_keys=True, ensure_ascii=False,
                                  separators=(',', ':')).encode()).hexdigest()
    report = {'schema': 'ark-sim/m71-event-storage-benchmark/v1', 'passed': True,
        'scope': 'Complete actual 0-1 trace through tick 120; not fullstage RSS or 36-stage acceptance',
        'source': {'package': str(package), 'sha256': sha(package),
                   'commands': str(commands_path), 'commands_sha256': sha(commands_path),
                   'ticks': 120, 'events': len(source), 'simulation_seconds': source_elapsed},
        'environment': {'python': sys.version, 'platform': platform.platform()},
        'core': core, 'runtime_fingerprint': sim.runtime_fingerprint,
        'program_fingerprint': program.fingerprint, 'results': rows,
        'v12_full_observation_hashes_equal': True, 'actual_checkpoint_reload_and_30_tick_continuation_equal': True,
        'script_sha256': sha(Path(__file__)), 'v12_sha256': sha(Path(v12.__file__)),
        'notes': ['tracemalloc counts Python allocation, not process RSS or OS file cache',
                  'Input complete trace remains resident outside measured regions in both modes',
                  'Disk journal keys preserve insertion order; v12 recanonicalizes one event per hash']}
    (OUT/'benchmark.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'events': len(source), 'results': rows, 'core': core}), flush=True)

if __name__ == '__main__':
    main()
