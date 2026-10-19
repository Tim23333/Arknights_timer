"""Coexisting desktop/web consumers preserve readers and independent detail demand."""
import time
from unittest.mock import Mock, patch

import pytest

from backend import test_webui_runtime as runtime_fixture
from backend.app.services.websocket_api import entity_public_id
from tools.enemy_health.enemy_reader import EnemyInfo


@pytest.fixture
def host():
    fixture = runtime_fixture.WebUiRuntimeTests('test_real_window_registry_and_unavailable_clock')
    fixture.setUp()
    fixture.window._webui = fixture.runtime
    try:
        yield fixture
    finally:
        fixture.window._enemy_poll = None
        fixture.window._webui = None
        fixture.tearDown()


def test_open_web_and_show_desktop_preserve_visibility_and_accepted_sources(host):
    window = host.window
    window.show()
    poll = window._enemy_poll = Mock()
    source = window._enemy_reader
    before = window._websocket_api.local_versions()
    window._websocket_api.publish_timer({'connected': True, 'frame_count': 461, 'game_time': 15.3})
    with patch('webbrowser.open') as browser:
        assert window.open_webui() == host.url
        browser.assert_called_once_with(host.url)
    assert window.isVisible() and window.updatesEnabled()
    assert window._enemy_reader is source and window._enemy_poll is poll
    assert host.request('api/command', {'action': 'frontend', 'params': {'target': 'desktop'}})['mode'] == 'shared'
    state = host.request('api/state')
    assert state['version'] and state['clock']['fixedFrame'] == 461
    assert window.isVisible() and window.updatesEnabled()
    poll.set_detail_target.assert_not_called()
    poll.set_character_detail_target.assert_not_called()
    assert window._websocket_api.local_versions() == before


def test_legacy_web_confirmation_cannot_hide_desktop_or_close_its_details(host):
    window = host.window
    window.show()
    dialog = window._enemy_detail_dialog = Mock()
    try:
        assert window._switch_frontend('confirm-web', token='old-tab', client_id='page')['mode'] == 'shared'
        assert window.isVisible() and window.updatesEnabled()
        dialog.close.assert_not_called()
    finally:
        window._enemy_detail_dialog = None


def test_web_detail_selections_are_independent_from_desktop_and_other_pages(host):
    window = host.window
    poll = window._enemy_poll = Mock()
    enemies = [EnemyInfo(100), EnemyInfo(200)]
    for index, enemy in enumerate(enemies, 1):
        enemy.roster_id = index
    window._webui_runtime_snapshot = {'enemies': enemies}
    ids = [entity_public_id('enemy', enemy, i) for i, enemy in enumerate(enemies, 1)]
    for client, identity in zip(('page-a', 'page-b'), ids):
        host.request('api/command', {'action': 'detail', 'params': {'kind': 'enemy', 'id': identity, 'clientId': client}})
    assert window._shared_detail_requests()['enemy_detail']['ids'] == set(ids)
    assert window._shared_detail_requests()['enemy_detail']['rateHz'] == 60.0
    host.request('api/command', {'action': 'detail', 'params': {'kind': 'enemy', 'id': None, 'clientId': 'page-a'}})
    assert window._shared_detail_requests()['enemy_detail']['ids'] == {ids[1]}
    poll.set_detail_target.assert_not_called()
    host.runtime._detail_targets['page-b']['seen'] = time.monotonic() - 11
    assert not window._shared_detail_requests()['enemy_detail']['ids']


def test_web_detail_targets_do_not_survive_a_new_battle_session(host):
    window = host.window
    window._enemy_poll = Mock()
    enemy = EnemyInfo(100)
    window._webui_runtime_snapshot = {'enemies': [enemy]}
    identity = entity_public_id('enemy', enemy, 1)
    host.request('api/command', {'action': 'detail', 'params': {'kind': 'enemy', 'id': identity, 'clientId': 'page'}})
    assert host.runtime.detail_requests()['enemy_detail']['ids'] == {identity}
    window._websocket_api.begin_session()
    assert not host.runtime.detail_requests()['enemy_detail']['ids']
