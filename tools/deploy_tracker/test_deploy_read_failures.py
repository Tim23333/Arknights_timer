"""A failed/partial list read cannot replace complete operation history."""
import struct
from unittest.mock import Mock

import pytest

from tools.deploy_tracker.ak_deploy_reader import (
    DeploymentReadError, DeployTrackerReader, LOGITEM_STRUCT,
)


def _header(items=0x2000, count=1, version=1):
    header = bytearray(0x20)
    struct.pack_into('<Qii', header, 0x10, items, count, version)
    return bytes(header)


def _string(value):
    data = bytearray(max(0x60, 0x14 + len(value) * 2))
    struct.pack_into('<i', data, 0x10, len(value))
    data[0x14:0x14 + len(value) * 2] = value.encode('utf-16-le')
    return bytes(data)


def _reader():
    reader = DeployTrackerReader(Mock(is_ptr=lambda address: address >= 0x1000))
    reader._logs_list_addr = 0x1000
    reader._char_names = {'char_test': '测试干员'}
    memory = {
        (0x1000, 0x20): _header(),
        (0x2018, 4): struct.pack('<i', 1),
        (0x2020, 0x30): struct.pack(LOGITEM_STRUCT, 1.5, 7, 0x3000, 0, 1, 2, 3, 0),
        (0x3000, 0x60): _string('char_test'),
    }
    reader._read = Mock(side_effect=lambda address, size: memory.get((address, size)))
    reader._read_many = Mock(side_effect=lambda requests: [memory.get(request) for request in requests])
    return reader, memory


@pytest.mark.parametrize('failure', (
    'header', 'capacity', 'capacity_too_small', 'payload', 'short_payload',
    'string', 'short_string', 'negative_count', 'too_many_items',
))
def test_incomplete_log_read_raises_instead_of_returning_empty_or_partial(failure):
    reader, memory = _reader()
    if failure == 'header':
        memory[(0x1000, 0x20)] = None
    elif failure == 'capacity':
        memory[(0x2018, 4)] = None
    elif failure == 'capacity_too_small':
        memory[(0x2018, 4)] = struct.pack('<i', 0)
    elif failure == 'payload':
        memory[(0x2020, 0x30)] = None
    elif failure == 'short_payload':
        memory[(0x2020, 0x30)] = memory[(0x2020, 0x30)][:-1]
    elif failure == 'string':
        memory[(0x3000, 0x60)] = None
    elif failure == 'short_string':
        memory[(0x3000, 0x60)] = _string('char_test')[:0x16]
    elif failure == 'negative_count':
        memory[(0x1000, 0x20)] = _header(count=-1)
    elif failure == 'too_many_items':
        memory[(0x1000, 0x20)] = _header(count=50001)
    with pytest.raises(DeploymentReadError):
        reader.get_events()


def test_zero_events_are_valid_and_do_not_read_payload_or_strings():
    reader, memory = _reader()
    memory[(0x1000, 0x20)] = _header(items=0, count=0)
    assert reader.get_events() == []
    assert reader._read.call_count == 1
    reader._read_many.assert_not_called()


def test_complete_event_keeps_zero_optional_string_and_character_name():
    reader, _ = _reader()
    event, = reader.get_events()
    assert event['timestamp'] == 1.5
    assert event['charId'] == 'char_test'
    assert event['charName'] == '测试干员'
    assert event['extraInfo'] == ''


def test_list_changed_during_read_is_rejected():
    reader, memory = _reader()
    headers = iter((_header(), _header(version=2)))
    reader._read.side_effect = lambda address, size: (
        next(headers) if address == 0x1000 else memory.get((address, size)))
    with pytest.raises(DeploymentReadError, match='列表发生变化'):
        reader.get_events()


def test_long_string_reads_tail_instead_of_fabricating_empty_text():
    reader, memory = _reader()
    text = 'char_' + 'x' * 50
    full = _string(text)
    memory[(0x3000, 0x60)] = full[:0x60]
    memory[(0x3000, len(full))] = full
    event, = reader.get_events()
    assert event['charId'] == text


def test_failed_squad_does_not_fall_back_as_if_verified_empty():
    reader, memory = _reader()
    reader._journal_squad_list_addr = 0x1000
    reader._squad_list_addr = 0x4000
    memory[(0x1000, 0x20)] = None
    with pytest.raises(DeploymentReadError):
        reader.get_squad()
    assert reader._read.call_args.args[0] == 0x1000
