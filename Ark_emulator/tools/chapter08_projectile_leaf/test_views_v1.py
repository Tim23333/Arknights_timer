"""Subtree reads are deeply readonly and never change World identities or stores."""
import pytest
from ark_sim.kernel.world import World


def test_leaf_read_is_detached_immutable_and_preserves_cached_entity_identity():
    world = World()
    ref = world.create('unit/leaf', {'projectiles': {'instances': {'p1': {'position': {'row': 1, 'col': 2},
                                                                         'jobs': [3, 4]}}}}, alias='source')
    before = world.snapshot()
    actor = world.get(ref)
    leaf = world.component_view('source', ('projectiles', 'instances', 'p1'))
    assert world.snapshot() == before and world.get(ref) is actor
    with pytest.raises(TypeError):
        leaf['position']['row'] = 9
    with pytest.raises(TypeError):
        leaf['jobs'][0] = 9
    world.set(ref, ('projectiles', 'instances', 'p1', 'position'), {'row': 5, 'col': 6})
    assert leaf['position']['row'] == 1 and actor['components']['projectiles']['instances']['p1']['position']['row'] == 1
    assert world.component_view(ref, ('projectiles', 'instances', 'p1'))['position']['row'] == 5


def test_missing_mapping_only_path_default_and_unknown_entity_keep_original_reader_contract():
    world = World()
    ref = world.create('unit/leaf', {'value': [{'name': 'item'}]})
    sentinel = object()
    assert world.component_view(ref, ('missing',), sentinel) is sentinel
    assert world.component_view(ref, ('value', 0), sentinel) is sentinel
    with pytest.raises(KeyError):
        world.component_view(999, ('value',))


def test_leaf_write_keeps_other_records_order_and_one_version_increment():
    world = World()
    ref = world.create('unit/leaf', {'projectiles': {'next_id': 3, 'instances': {'p1': {'x': 1}, 'p2': {'x': 2}}}})
    old = world.get(ref)
    version = world.version(ref)
    world.set(ref, ('projectiles', 'instances', 'p1'), {'x': 3})
    actor = world.get(ref)
    assert world.version(ref) == version + 1 and list(actor['components']['projectiles']['instances']) == ['p1', 'p2']
    assert actor['components']['projectiles']['instances']['p2'] == old['components']['projectiles']['instances']['p2']
