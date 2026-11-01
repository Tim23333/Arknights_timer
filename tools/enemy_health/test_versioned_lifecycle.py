"""Relocated battle fields must preserve paused readiness and owner checks."""
import struct
from unittest.mock import Mock

import pytest

from tools.enemy_health import game_structs as gs
from tools.enemy_health.battle_lifecycle import LifecycleReader
from tools.stage_global_state.engine_clock import read_pause
from tools.stage_global_state.memory import ReadFailure


@pytest.mark.parametrize('valid_owner', (True, False))
def test_lifecycle_uses_relocated_profile_fields_and_checks_ownership(monkeypatch, valid_owner):
    offsets = {'M_STATE': 0x330, 'SCHEDULER': 0x48, 'LEVEL_DATA': 0x1A8, 'UNIT_MANAGER': 0x3A0}
    for name, offset in offsets.items():
        monkeypatch.setattr(gs.BattleControllerFields, name, offset)
    bc, flow, klass, flow_klass = 0x10000, 0x20000, 0x30000, 0x40000
    block = bytearray(0x3A8)
    struct.pack_into('<Q', block, 0, klass)
    struct.pack_into('<Q', block, 0x10, 0x50000)
    # Poison the old state/root slots: falling back to them cannot pass.
    struct.pack_into('<i', block, 0x220, -1)
    struct.pack_into('<i', block, offsets['M_STATE'], 2)
    identities = []
    for name, offset, address in [('Scheduler', offsets['SCHEDULER'], 0x60000),
                                  ('LevelData', offsets['LEVEL_DATA'], 0x70000),
                                  ('UnitManager', offsets['UNIT_MANAGER'], 0x80000)]:
        struct.pack_into('<Q', block, offset, address)
        identities.append((address, name))
    flow_raw = bytearray(0x38)
    struct.pack_into('<Q', flow_raw, 0, flow_klass)
    struct.pack_into('<Q', flow_raw, 0x10, 0x90000)
    memory = Mock()
    memory.read.side_effect = lambda address, size: {
        bc: bytes(block), flow: bytes(flow_raw)}[address][:size]
    slots = [struct.pack('<Q', bc), struct.pack('<Q', flow)]
    memory.read_many.side_effect = [slots, slots + [bytes(flow_raw[0x20:])]]
    if not valid_owner:
        memory.identity.side_effect = ReadFailure('binding_invalid')
    reader = LifecycleReader.__new__(LifecycleReader)
    reader.m, reader.battle_klass, reader.flow_klass = memory, klass, flow_klass
    reader.battle_slot, reader.flow_slot = 0xA0000, 0xB0000
    if valid_owner:
        assert reader.sample() == dict(battle=(bc, 0x50000), ready=True,
                                       transiting=False, source='', target='')
        assert [call.args for call in memory.identity.call_args_list] == identities
    else:
        with pytest.raises(ReadFailure, match='binding_invalid'):
            reader.sample()
    memory.read.assert_any_call(bc, 0x3A8)


@pytest.mark.parametrize('count, expected', ((0, False), (1, True), (257, None)))
def test_pause_uses_versioned_field_without_weakening_list_validation(monkeypatch, count, expected):
    monkeypatch.setattr(gs.BattleControllerFields, 'PAUSE_STATE', 0x380)
    memory = Mock()
    memory.pointer.side_effect = {0x10380: 0x20000, 0x20010: 0x30000, 0x30010: 0x40000}.__getitem__
    memory.integer.return_value = count
    if expected is None:
        with pytest.raises(ReadFailure, match='unsupported_layout'):
            read_pause(memory, 0x10000)
    else:
        assert read_pause(memory, 0x10000) is expected
    assert [call.args for call in memory.identity.call_args_list] == [
        (0x20000, 'EnableStateWithKey`1'), (0x30000, 'ListSet`1'), (0x40000, 'List`1')]
