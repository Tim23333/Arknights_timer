"""Version labels never replace live layout, ownership and frame validation."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from tools.stage_global_state.reader import StageGlobalReader
from tools.stage_global_state.memory import ReadFailure


def prepared_reader(*, version='9.9.9', identity_error=None):
    mc = SimpleNamespace(process_instance=('boot', 100), package='com.hypergryph.arknights',
                         version_name=version, shell=Mock(side_effect=AssertionError('version query not needed')))
    channel = object()
    owner = SimpleNamespace(mc=mc, _chan=channel, bc_addr=0x10000, log=lambda _: None)
    memory = Mock(mc=mc, channel=channel)
    memory.identity.side_effect = identity_error
    memory.guard = {'complete': True, 'start': 100, 'end': 100}
    stage = StageGlobalReader(owner)
    stage._validate_binding = Mock()
    stage._prepare_stage = Mock()
    stage._prepare_engine = Mock()
    with patch('tools.stage_global_state.reader.OptionalMemoryAccess', return_value=memory), \
         patch('tools.stage_global_state.reader.MemoryAccess', return_value=memory), \
         patch('tools.stage_global_state.reader.WaveStateReader'):
        stage.prepare()
    return stage, owner, memory


@pytest.mark.parametrize('version', ('2.7.81', '2.8.0', '9.9.9', None))
def test_prepare_accepts_verified_layout_without_querying_package_version(version):
    stage, owner, memory = prepared_reader(version=version)
    assert stage.prepare_reason == ''
    owner.mc.shell.assert_not_called()
    memory.identity.assert_called_once_with(owner.bc_addr, 'BattleController')
    stage._validate_binding.assert_called_once_with(initial=True)
    assert stage._transport_ready()
    with patch('tools.stage_global_state.reader.read_pause', return_value=True):
        stage.engine = SimpleNamespace(sample=lambda: 0.0)
        assert stage.sample_runtime() == {'isPaused': True, 'timeScale': 0.0}


def test_layout_mismatch_still_fails_closed():
    stage, _, _ = prepared_reader(identity_error=ReadFailure('unsupported_layout'))
    assert stage.prepare_reason == 'unsupported_layout'
    stage._validate_binding.assert_not_called()


def test_new_process_or_battle_cannot_reuse_verified_transport():
    stage, owner, _ = prepared_reader()
    owner.mc.process_instance = ('boot', 200)
    assert not stage._transport_ready()
    assert stage.sample_runtime() == {'isPaused': None, 'timeScale': None}


def test_optional_capture_must_match_core_frame_even_after_version_gate_removal():
    stage, _, memory = prepared_reader()
    stage.sample = Mock(return_value={'values': {}})
    assert stage.sample_optional(None, {'fixed_frame': 100}, 1)[1] is True
    memory.end_sample.assert_called_once()
    memory.guard = {'complete': True, 'start': 101, 'end': 101}
    assert stage.sample_optional(None, {'fixed_frame': 100}, 1)[1] is False
    memory.guard = {'complete': False, 'start': 100, 'end': 100}
    assert stage.sample_optional(None, {'fixed_frame': 100}, 1)[1] is False


def test_transport_reconnect_rebinds_without_a_package_version_query():
    stage, owner, _ = prepared_reader()
    owner._chan = object()
    assert stage._transport_ready()
    assert stage.runtime_memory.channel is owner._chan
    assert stage.memory.channel is owner._chan
    owner.mc.shell.assert_not_called()
