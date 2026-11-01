"""Captured WaveData must not be confused with a handler back-reference."""
import struct
from unittest.mock import Mock

import pytest

from tools.enemy_health import game_structs as gs
from tools.stage_global_state import wave_state as ws
from tools.stage_global_state.memory import ReadFailure


@pytest.mark.parametrize('phase,name', ((1, 'PRE_DELAY'), (5, 'POST_DELAY')))
@pytest.mark.parametrize('valid_wave_owner', (True, False))
def test_versioned_handler_and_delay_iterator_validate_their_distinct_owners(
        monkeypatch, phase, name, valid_wave_owner):
    monkeypatch.setattr(gs.DefaultWaveHandlerFields, 'SCHEDULER', 0x28)
    bc, scheduler, root, wave_iter, wave, array, handler, mode, delay, counter, fixed = (
        n * 0x1000 for n in range(1, 12))
    root_raw, wave_raw, delay_raw, counter_raw = (bytearray(n) for n in (0x48, 0x48, 0x30, 0x48))
    struct.pack_into('<i', root_raw, 0x10, 2)
    struct.pack_into('<Q', root_raw, 0x18, wave_iter)
    struct.pack_into('<i', wave_raw, 0x10, phase)
    struct.pack_into('<QQQQ', wave_raw, 0x18, delay, scheduler, wave, 0)
    struct.pack_into('<i', delay_raw, 0x10, 1)
    struct.pack_into('<QQ', delay_raw, 0x18, counter, wave if valid_wave_owner else handler)
    struct.pack_into('<i', counter_raw, 0x10, 1)
    struct.pack_into('<Q', counter_raw, 0x18, fixed)
    struct.pack_into('<fii', counter_raw, 0x20, 1.5, 45, 10)
    blocks = {root: bytes(root_raw), wave_iter: bytes(wave_raw), delay: bytes(delay_raw),
              counter: bytes(counter_raw), fixed: b'fixed123',
              array + 0x18: struct.pack('<iiQ', 1, 0, wave)}
    pointers = {scheduler + gs.SchedulerFields.M_WAVES: array,
                scheduler + 0x118: handler, bc + gs.BattleControllerFields.GAME_MODE: mode,
                handler + 0x28: scheduler}
    blocks.update({address: struct.pack('<Q', value) for address, value in pointers.items()})
    names = {wave_iter: ws.WAVE, wave: 'WaveData', handler: 'DefaultWaveHandler',
             mode: 'DefaultGameMode', delay: getattr(ws, name),
             counter: '<WaitForFixedSeconds>d__0', fixed: 'WaitForFixedUpdate'}
    memory = Mock()
    memory.read.side_effect = lambda address, size: blocks[address][:size]
    memory.pointer.side_effect = pointers.__getitem__
    memory.identity.side_effect = lambda address, expected=None: (0, names[address], '')
    memory.array.return_value = [wave]
    memory.read_many.side_effect = lambda requests, **kwargs: [blocks[a][:n] for a, n in requests]
    reader = ws.WaveStateReader(memory, bc, scheduler, lifecycle_verified=True)
    reader.active_root = Mock(return_value=root)
    if valid_wave_owner:
        result = reader.sample(demand={'waveWait'})
        assert result['waveWait']['remainingResumeCount'] == 35
        assert result['waveWait']['phase'] == ('pre_delay' if phase == 1 else 'post_delay')
        assert memory.read_many.call_args.kwargs == {'structural_check': True}
    else:
        with pytest.raises(ReadFailure, match='binding_invalid'):
            reader.sample(demand={'waveWait'})
    memory.pointer.assert_any_call(handler + 0x28)
