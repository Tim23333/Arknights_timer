"""Independent nested savepoint, metadata normalization and thread/store checks."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from ark_sim.kernel import Session, World
from ark_sim.contracts import Intent


class HostileString(str):
    def __deepcopy__(self, memo):
        raise AssertionError('Untrusted metadata deepcopy hook must not run')


def make():
    s = Session(seed=82293)
    ref = s.commit([Intent('create', data={'definition_id': 'unit/root', 'alias': 'source',
                'tags': ['z', 'a'], 'components': {'counter': {'value': 11}, 'payload': {'rows': [{'x': 1}], 'flag': True}}})])[0]
    return s, ref


def test_nested_inner_rollback_outer_failure_and_postfailure_public_state():
    s, ref = make()
    before = s.checkpoint()
    with pytest.raises(RuntimeError, match='outer'):
        with s.atomic():
            s.commit([Intent('set', ref, ('counter', 'value'), 17)])
            after_outer = s.checkpoint() if not s._atomic_depth else s.world.snapshot()
            with pytest.raises(ValueError, match='inner'):
                with s.atomic():
                    s.commit([Intent('create', data={'definition_id': 'unit/inner', 'alias': 'temporary',
                              'components': {'nested': {'array': [1, 2]}}}),
                              Intent('emit', data={'type': 'peer.inner', 'payload': {'x': 3}}),
                              Intent('schedule', data={'kind': 'peer.unused', 'at': 12, 'payload': {'a': 1}})])
                    raise ValueError('inner')
            assert s.world.snapshot() == after_outer
            assert s.world.get(ref)['components']['counter']['value'] == 17
            with pytest.raises(KeyError):
                s.world.resolve('temporary')
            raise RuntimeError('outer')
    assert s.checkpoint() == before
    s.commit([Intent('set', ref, ('counter', 'value'), 19)])
    assert s.world.get(ref)['components']['counter']['value'] == 19


def test_metadata_builtin_normalization_matches_original_snapshot_restore():
    world = World()
    ref = world.create(HostileString('unit/meta'), {'value': 7}, tags=[HostileString('z'), HostileString('a')], alias=HostileString('alias'))
    old = World()
    old.restore(world.snapshot())
    stage = world._fork_validated()
    assert stage.snapshot() == old.snapshot()
    stage.set(ref, ('value',), 8)
    assert world.get(ref)['components']['value'] == 7
    world._adopt_validated(stage, preserve_views=True)
    assert world.get(ref)['components']['value'] == 8
    assert stage.snapshot()['entities'] == []
    with pytest.raises(ValueError):
        world._adopt_validated(stage, preserve_views=True)


def test_real_session_threads_serialize_entire_nested_increment():
    s, ref = make()
    def increment(_):
        with s.atomic():
            current = s.world.get(ref)['components']['counter']['value']
            with s.atomic():
                s.commit([Intent('set', ref, ('counter', 'value'), current + 1)])
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(increment, range(96)))
    assert s.world.get(ref)['components']['counter']['value'] == 107
    assert s.world.version(ref) == 97


@pytest.mark.parametrize('value', [float('nan'), float('inf'), object()])
def test_public_json_boundary_still_rejects_malformed_batch_atomically(value):
    s, ref = make()
    before = s.checkpoint()
    with pytest.raises((ValueError, TypeError)):
        s.commit([Intent('set', ref, ('counter', 'value'), 13), Intent('set', ref, ('payload',), {'invalid': value})])
    assert s.checkpoint() == before
