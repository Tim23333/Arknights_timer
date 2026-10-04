"""Value-equivalent event storage sharing with real simulation witnesses."""
from collections.abc import Mapping
import json
import pytest
from ark_sim import Compiler, Engine
from ark_sim.contracts.models import freeze, thaw, FrozenMapping
from ark_sim.kernel.events import EventLog
from ark_sim.kernel import Session
from ark_sim.domains.context import compact_trace
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene
from tools.m8_trace_legacy_reference import LegacyEventLog, legacy_compact_trace


def test_compact_trace_same_json_values_shares_unchanged_and_changed_aliases():
    plain = {'id': 17, 'definition_id': 'unit/probe', 'components': {'attributes': {'atk': 31},
        'runtime': {'casts': {'cast/17/1': {'id': 'cast/17/1', 'source_snapshot': {'omitted': 1}, 'targets': [2, 3]}}}}}
    entity = freeze(plain)
    value = {'inputs': {'source': entity, 'target': entity}, 'context': {'source': entity, 'target': entity, 'value': 31}}
    current = compact_trace(value)
    assert thaw(current) == legacy_compact_trace(value)
    assert current['inputs']['source'] is current['inputs']['target']
    assert current['inputs']['source']['components']['attributes'] is entity['components']['attributes']
    assert current['inputs']['source']['components']['runtime'] is not entity['components']['runtime']
    assert compact_trace(freeze({'attack': 31, 'scale': .5}))['attack'] == 31


def test_event_payload_aliases_share_frozen_nodes_across_records_and_mutable_input_detaches():
    log = EventLog()
    shared = freeze({'atk': 31, 'operands': [2, 3]})
    mutable = {'health': [100]}
    log.emit('probe', {'a': shared, 'b': shared, 'mutable': mutable}, 0)
    log.emit('probe', {'a': shared}, 1, cause=1)
    mutable['health'].append(0)
    first, second = log.records
    assert first['payload']['a'] is shared
    assert first['payload']['a'] is first['payload']['b'] is second['payload']['a']
    assert first['payload']['mutable']['health'] == (100,)
    with pytest.raises(TypeError):
        first['payload']['a']['atk'] = 0


@pytest.mark.parametrize('payload', [{1: 'bad'}, {'x': float('nan')}, {'x': float('inf')}, {'x': object()},
    freeze({1: 'bad'}), freeze({'x': float('nan')}), freeze({'x': object()})])
def test_untrusted_frozen_and_mutable_invalid_json_are_rejected_without_consuming_id(payload):
    log = EventLog()
    with pytest.raises(ValueError):
        log.emit('bad', payload, 0)
    assert log.records == ()
    assert log.emit('valid', {'operand': 1}, 0) == 1


def test_cycles_are_rejected_but_acyclic_mutable_aliases_are_shared_after_freeze():
    log = EventLog()
    cycle = [];cycle.append(cycle)
    with pytest.raises(ValueError, match='cycle'):
        log.emit('cycle', cycle, 0)
    shared = {'value': [1]}
    log.emit('dag', {'a': shared, 'b': shared}, 0)
    shared['value'][0] = 9
    assert log.records[0]['payload']['a'] is log.records[0]['payload']['b']
    assert log.records[0]['payload']['a']['value'] == (1,)


def test_snapshot_restore_plain_json_detaches_and_keeps_all_event_values():
    log = EventLog()
    log.emit('first', {'operands': [2, 4]}, 0)
    log.emit('second', {'result': 6}, 1, cause=1)
    saved = log.snapshot()
    assert isinstance(saved, dict) and isinstance(saved['records'], list)
    restored = EventLog();restored.restore(saved)
    saved['records'][0]['payload']['operands'][0] = 99
    assert thaw(restored.records) == thaw(log.records)
    with pytest.raises(TypeError):
        restored.records[0]['payload']['operands'][0] = 7
    assert restored.emit('third', {'result': 8}, 2, cause=2) == 3


def test_shared_event_journal_atomic_rollback_truncates_and_restores_causal_ids():
    session = Session()
    shared = freeze({'operand': 7})
    session.emit('first', {'a': shared})
    before = session.checkpoint()
    with pytest.raises(RuntimeError):
        with session.atomic():
            session.emit('second', {'a': shared}, cause=1)
            session.emit('third', {'a': shared}, cause=2)
            raise RuntimeError('rollback')
    assert session.checkpoint() == before
    assert session.emit('replacement', {'a': shared}, cause=1) == 2
    assert session.events[0]['payload']['a'] is session.events[1]['payload']['a']


@pytest.mark.parametrize('trace_mode', ['compact', 'full'])
def test_legacy_storage_and_new_storage_real_simulation_events_are_value_equal(monkeypatch, trace_mode):
    import ark_sim.kernel.session as sessions
    import ark_sim.domains.context as contexts
    data = scene(mode='automatic_attack', repeats=2)
    from ark_sim.content.compiler import PRESET_PATH
    ruleset = json.loads(PRESET_PATH.read_bytes())['rulesets'][0]
    ruleset['id'] = 'ruleset/m8_trace_review'
    ruleset.setdefault('parameters', {})['trace_mode'] = trace_mode
    data['rulesets'] = [ruleset]
    data['scenarioDraft']['ruleset'] = ruleset['id']
    # Real sampling and causal branches must survive the storage change too.
    data['abilities'][0]['timeline'][0]['effect'] = {'op': 'random', 'stream': 'review/imp', 'probability': .5,
        'on_success': [{'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 3}],
        'on_failure': [{'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 1}]}
    program = Compiler().compile(data)
    legacy_log = sessions.EventLog
    current_compactor = contexts.compact_trace
    with monkeypatch.context() as patch:
        patch.setattr(sessions, 'EventLog', LegacyEventLog)
        patch.setattr(contexts, 'compact_trace', legacy_compact_trace)
        old = Engine.create(program, seed=17);old.advance(5)
    assert sessions.EventLog is legacy_log and contexts.compact_trace is current_compactor
    current = Engine.create(program, seed=17);current.advance(5)
    assert current.session.random.samples
    assert thaw(current.session.events) == thaw(old.session.events)
    assert first_difference(current.snapshot(), old.snapshot()) is None


def test_new_storage_real_checkpoint_and_replay_keep_operands_events_and_random():
    program = Compiler().compile(scene(mode='automatic_attack', repeats=2))
    sim = Engine.create(program, seed=19)
    sim.advance(2)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(4);restored.advance(4)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert thaw(sim.session.events) == thaw(restored.session.events)
    again = replay(program, sim.export_replay())
    assert first_difference(sim.snapshot(), again.snapshot()) is None
    assert thaw(sim.session.events) == thaw(again.session.events)


def test_frozen_public_constructor_with_mutable_forgery_is_validated_and_detached():
    from types import MappingProxyType
    node = freeze({'safe': True})
    mutable = [1]
    # FrozenMapping is a data representation, not a strong security boundary.
    object.__setattr__(node, '_data', MappingProxyType({'mutable': mutable}))
    log = EventLog();log.emit('probe', node, 0)
    mutable.append(2)
    assert log.records[0]['payload']['mutable'] == (1,)
    object.__setattr__(node, '_data', MappingProxyType({'loop': node}))
    with pytest.raises(ValueError, match='cycle'):
        log.emit('cycle', node, 1)


class MisleadingInt(int):
    def __int__(self):
        return 999


class MisleadingFloat(float):
    def __float__(self):
        return 999.0


class MisleadingString(str):
    def __str__(self):
        return 'different'


@pytest.mark.parametrize('frozen_input', [False, True])
def test_scalar_and_key_subclasses_keep_legacy_json_underlying_values(frozen_input):
    payload = {MisleadingString('key'): MisleadingString('abc'), 'integer': MisleadingInt(3), 'float': MisleadingFloat(3.0)}
    if frozen_input:
        payload = freeze(payload)
    old, current = LegacyEventLog(), EventLog()
    old.emit('subclasses', payload, 0);current.emit('subclasses', payload, 0)
    assert thaw(current.records) == thaw(old.records)
    assert thaw(current.records[0]['payload']) == {'key': 'abc', 'integer': 3, 'float': 3.0}
