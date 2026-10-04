"""Independent boundaries against actual M71 runtime, with no V1 imports."""
from pathlib import Path
import json
import sys
from types import MappingProxyType

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent/'unpack_work/campaign_m71_event_storage_candidate'
sys.path.insert(0, str(RUNTIME))
from ark_sim.kernel.session import Session
from ark_sim.contracts.models import FrozenMapping, FrozenTuple, thaw
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts.models import Intent


def disk(tmp_path):
    session = Session(seed=17)
    session.enable_event_journal(tmp_path/'active.jsonl')
    return session


def test_nested_atomic_inner_and_outer_rollback_restore_all_stores(tmp_path):
    s = disk(tmp_path)
    entity = s.world.create('unit', {'hp': 40})
    s.emit('initial', {'hp': 40})
    before = s.checkpoint()
    with pytest.raises(RuntimeError):
        with s.atomic():
            s.emit('outer', {'hp': 30}, cause=1)
            s.world.set(entity, ['hp'], 30)
            s.random.sample('combat')
            s.schedule('later', {}, 5)
            with pytest.raises(ValueError):
                with s.atomic():
                    s.emit('inner', {}, cause=2)
                    s.world.set(entity, ['hp'], 20)
                    raise ValueError('inner rollback')
            assert [e['id'] for e in s.events] == [1, 2]
            assert s.world.get(entity)['components']['hp'] == 30
            s.emit('after-inner', {}, cause=2)
            raise RuntimeError('outer rollback')
    assert s.checkpoint() == before
    assert s.emit('reused-id', {}, cause=1) == 2
    assert [e['type'] for e in s.events] == ['initial', 'reused-id']


def test_stable_readonly_iteration_survives_rollback_append(tmp_path):
    s = disk(tmp_path)
    s.emit('one', {'nested': [1, {'value': -0.0}]})
    iterator = s._events.iter_records()
    with pytest.raises(RuntimeError):
        with s.atomic():
            s.emit('discard', {})
            raise RuntimeError()
    s.emit('two', {})
    record = next(iterator)
    assert list(record) == ['id', 'type', 'payload', 'time', 'cause']
    with pytest.raises(TypeError):
        record['payload']['nested'][1]['value'] = 5
    assert list(iterator) == []
    assert thaw(record)['payload']['nested'][1]['value'] == -0.0


def test_foreign_frozen_mutable_child_not_identity_cached(tmp_path):
    s = disk(tmp_path)
    child = {'array': [1]}
    forged_tuple = tuple.__new__(FrozenTuple, [child])
    forged = object.__new__(FrozenMapping)
    object.__setattr__(forged, '_data', MappingProxyType({'nested': forged_tuple}))
    s.emit('first', forged)
    child['array'].append(2)
    s.emit('second', forged)
    child['array'].append(3)
    assert [thaw(e)['payload'] for e in s.events] == [
        {'nested': [{'array': [1]}]}, {'nested': [{'array': [1, 2]}]}]


@pytest.mark.parametrize('damage', ['missing', 'truncate', 'tamper'])
def test_actual_reference_reload_rejects_file_damage(tmp_path, damage):
    s = disk(tmp_path)
    s.emit('event', {'value': 123})
    checkpoint = json.loads(json.dumps(s.checkpoint(event_reference=True)))
    path = Path(checkpoint['events']['reference']['path'])
    if damage == 'missing':
        path.unlink()
    elif damage == 'truncate':
        path.write_bytes(path.read_bytes()[:-1])
    else:
        path.write_bytes(path.read_bytes().replace(b'123', b'456'))
    target = Session(seed=99)
    before = target.checkpoint()
    with pytest.raises((ValueError, OSError)):
        target.restore(checkpoint)
    assert target.checkpoint() == before


@pytest.mark.parametrize('damage', ['truncate', 'tamper'])
def test_live_owned_bytes_corruption_rejected_on_read_and_export(tmp_path, damage):
    s = disk(tmp_path)
    s.emit('live', {'value': 123})
    path = tmp_path/'active.jsonl'
    raw = path.read_bytes()
    path.write_bytes(raw[:-3] if damage == 'truncate' else raw.replace(b'123', b'456'))
    with pytest.raises(ValueError, match='corrupted'):
        _ = s.events
    with pytest.raises(ValueError, match='corrupted'):
        s.export_events_jsonl(tmp_path/'corrupt-export.jsonl')


def test_reference_reload_independent_branches_full_checkpoint_continuity(tmp_path):
    s = disk(tmp_path)
    s.emit('origin', {'surrogate': '\ud800', 'unicode': '阿米娅', 'integer': 10**120, 'zero': -0.0})
    s.schedule('later', {'x': 1}, 5)
    s.random.sample('combat')
    reference = s.checkpoint(event_reference=True)
    path = tmp_path/'checkpoint.json'
    path.write_text(json.dumps(reference), encoding='utf8')
    s.emit('live-next', {}, cause=1)
    a = Session()
    b = Session()
    a.restore(json.loads(path.read_text(encoding='utf8')))
    b.restore(json.loads(path.read_text(encoding='utf8')))
    assert a.checkpoint() == b.checkpoint()
    assert a.random.sample('combat') == b.random.sample('combat')
    a.emit('branch-a', {}, cause=1)
    b.emit('branch-b', {}, cause=1)
    assert [e['type'] for e in s.events] == ['origin', 'live-next']
    assert [e['type'] for e in a.events] == ['origin', 'branch-a']
    assert [e['type'] for e in b.events] == ['origin', 'branch-b']


def test_failed_emit_does_not_consume_id_and_switch_is_idle_only(tmp_path):
    s = disk(tmp_path)
    with pytest.raises(ValueError):
        s.emit('bad', {'value': float('nan')})
    assert s.emit('good', {}) == 1
    with s.atomic():
        with pytest.raises(RuntimeError):
            s.enable_event_journal(tmp_path/'other.jsonl')


def test_failed_disk_batch_does_not_publish_world_scheduler_or_events(tmp_path, monkeypatch):
    s = disk(tmp_path)
    entity = s.world.create('unit', {'hp': 40})
    s.emit('origin', {})
    before = s.checkpoint()
    records = s._events._records
    append = records.append
    calls = 0
    def fail_second(record):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('injected disk failure')
        append(record)
    monkeypatch.setattr(records, 'append', fail_second)
    with pytest.raises(OSError):
        s.commit([Intent('set', entity, ('hp',), 5),
                  Intent('schedule', data={'kind': 'future', 'at': 5}),
                  Intent('emit', data={'type': 'first', 'payload': {}}),
                  Intent('emit', data={'type': 'second', 'payload': {}})])
    assert s.checkpoint() == before


def test_reference_semantic_invalid_rehashed_bytes_rejected(tmp_path):
    import hashlib
    s = disk(tmp_path)
    s.emit('original', {'value': 1})
    checkpoint = s.checkpoint(event_reference=True)
    reference = checkpoint['events']['reference']
    path = Path(reference['path'])
    line = json.loads(path.read_bytes())
    line['payload']['value'] = float('nan')
    raw = json.dumps(line).encode() + b'\n'
    path.write_bytes(raw)
    reference.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    with pytest.raises(ValueError, match='finite'):
        Session().restore(checkpoint)


def test_atomic_partial_disk_write_rolls_back_rng_versions_sequence_epoch(tmp_path, monkeypatch):
    s = disk(tmp_path)
    entity = s.world.create('unit', {'hp': 40})
    s.emit('origin', {})
    s.world.get(entity)  # Populate the derived readonly view before failure.
    before = s.checkpoint()
    epoch = s.cache_epoch
    records = s._events._records
    file = records._file
    class BrokenWriter:
        def __getattr__(self, name):
            return getattr(file, name)
        def write(self, value):
            file.write(value[:5])
            raise OSError('partial write followed by persistent IO failure')
        def truncate(self, *args):
            raise AssertionError('Rollback must not require disk IO')
    with pytest.raises(OSError):
        with s.atomic():
            s.world.set(entity, ['hp'], 1)
            s.random.sample('combat')
            s.schedule('later', {}, 5)
            monkeypatch.setattr(records, '_file', BrokenWriter())
            s.emit('bad-write', {'long': list(range(30))})
    assert s.checkpoint() == before
    assert s.cache_epoch == epoch + 1
    assert s.world.get(entity)['components']['hp'] == 40
    monkeypatch.setattr(records, '_file', file)
    assert s.emit('recovered', {}) == 2
    assert [e['type'] for e in s.events] == ['origin', 'recovered']


def test_full_export_bytes_preserve_every_value_and_order(tmp_path):
    s = disk(tmp_path)
    for i in range(20):
        s.emit('value', {'signed': -0.0, 'nested': [i, True, None, '中文']}, cause=i or None)
    meta = s.export_events_jsonl(tmp_path/'export.jsonl')
    values = [json.loads(line) for line in Path(meta['path']).read_bytes().splitlines()]
    assert values == thaw(s.events)
    assert meta['count'] == 20
    with pytest.raises(ValueError):
        s.export_events_jsonl(tmp_path/'active.jsonl')


@pytest.mark.parametrize('ruleset,damage', [('ruleset/ark_standard', 850), ('ruleset/custom_balance', 60)])
def test_real_source_engine_checkpoint_reload_replay_full_values(tmp_path, ruleset, damage):
    program = Compiler().compile(ROOT/'packages/custom/custom_guard.json', ruleset=ruleset)
    normal = Engine.create(program, seed=123)
    normal.session.advance(15)
    simulation = Engine.create(program, seed=123)
    simulation.session.enable_event_journal(tmp_path/'engine.jsonl')
    simulation.session.advance(15)
    assert simulation.snapshot() == normal.snapshot()
    checkpoint_path = tmp_path/'engine-checkpoint.json'
    checkpoint_path.write_text(json.dumps(simulation.checkpoint(event_reference=True)), encoding='utf8')
    restored = Engine.restore(program, json.loads(checkpoint_path.read_text(encoding='utf8')))
    for live in (normal, simulation, restored):
        live.session.advance(15)
    assert normal.snapshot() == simulation.snapshot() == restored.snapshot()
    assert normal.checkpoint() == simulation.checkpoint() == restored.checkpoint()
    assert simulation.ctx.state()['damage_dealt'] == damage
    repeated = replay(program, simulation.export_replay(), event_journal_path=tmp_path/'replay.jsonl')
    assert repeated.snapshot() == simulation.snapshot()
    assert repeated.checkpoint() == simulation.checkpoint()
