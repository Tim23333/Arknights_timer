"""Independent actual disk-record identity and bounded lookup permission check."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
CORE = '12e1e1adf291a505443980bca51046c725382d82fd458e4adbc4482bcf1b9183'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    runtime = args.runtime_root.resolve();sys.path.insert(0, str(runtime));sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw, digest
    assert implementation_digest() == CORE and Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim'
    paths = [p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    paths.append(Path(__file__))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    guard = lambda: {str(p): sha(p) for p in paths}
    before = guard()
    result = {'schema': 'ark-sim/causal-record-root-independent/v1', 'core': CORE,
              'passed': False, 'source_before': before, 'full_suite': False, 'whole_stage': False, 'client_verified': False}
    try:
        package = {'schemaVersion': 2, 'scenarioDraft': {'id': 'scene/causalrecord/rootpeer',
                    'ruleset': 'ruleset/ark_standard', 'map': {'rows': 2, 'cols': 2},
                    'resources': {'life': {'initial': 99999, 'capacity': 99999}}, 'initialEntities': []}}
        path = Path(os.environ['ARKSIM_RUN_DIR']) / 'independent.records.jsonl'
        sim = Engine.create(Compiler().compile(package), seed=919, event_journal_path=path)
        previous = None;issued = []
        for i in range(211):
            payload = {'index': i, 'flags': [False, True, None], 'float': -0.0 if i % 2 else 0.0,
                       'nested': {'raw': [{'value': i / 17, 'name': 'source/actual/' + str(i)}]},
                       'context': {'time': 0, 'owner': {}, 'source': {}, 'value': i + 23}}
            previous = sim.session.emit('peer.actual.causal', payload, cause=previous)
            issued.append(previous)
        records = sim.session._events._records
        expected = {identifier: records[identifier - 1] for identifier in [issued[0], issued[73], issued[147], issued[-1]]}
        raw_sha = sha(path)
        def stores():
            return {'world': sim.session.world.snapshot(), 'jobs': sim.session.scheduler.snapshot(),
                    'RNG': sim.session.random.snapshot(), 'cache': sim.ctx.attributes.checkpoint_cache(),
                    'event_next_id': sim.session._events._next_id, 'event_count': len(records)}
        saved = stores()
        class IndexedOnly:
            def __init__(self):self.reads = []
            def __len__(self):return len(records)
            def __iter__(self):raise AssertionError('A single causal lookup iterated the journal')
            def __getitem__(self, index):
                if type(index) is not int:raise AssertionError('Causal lookup performed a bulk/slice read')
                self.reads.append(index)
                return records[index]
        proxy = IndexedOnly();sim.session._events._records = proxy
        equal = []
        try:
            for identifier, original in expected.items():
                actual = sim.ctx.death_spawns.event(identifier)
                assert actual == original and digest(actual) == digest(original)
                assert struct.pack('>d', actual['payload']['float']) == struct.pack('>d', original['payload']['float'])
                equal.append({'ID': identifier, 'full_record_digest': digest(actual), 'cause': actual['cause']})
            for invalid in [True, False, 1.0, None, '1', -7, 0, len(records) + 4]:
                try:sim.ctx.death_spawns.event(invalid)
                except ValueError:pass
                else:raise AssertionError('Invalid causal ID accepted: ' + repr(invalid))
        finally:sim.session._events._records = records
        assert proxy.reads == [identifier - 1 for identifier in expected]
        assert stores() == saved and sha(path) == raw_sha
        result.update(passed=True, actual_record_count=len(records), queried_records=equal,
                      only_index_reads=proxy.reads, raw_file_before_after_sha256=raw_sha,
                      all_five_stores_unchanged=True, no_trace_payload_context_cause_filtering=True)
    except Exception:result['error'] = traceback.format_exc()
    result['source_after'] = guard()
    result['identity_stable'] = before == result['source_after'] and implementation_digest() == CORE
    result['actual_exit'] = 0 if result['passed'] and result['identity_stable'] else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': result['passed'], 'actual_exit': result['actual_exit'], 'error': result.get('error')}))
    return result['actual_exit']


if __name__ == '__main__':raise SystemExit(main())
