"""Single-battle persistence must not turn old values into live observations."""
import json
import threading
from pathlib import Path
from types import SimpleNamespace

from backend.app.field_policy import PolicyStore, collection_record
from backend.app.services.departure_history import DepartureHistory
from backend.app.storage_paths import data_root
from tools.enemy_health.enemy_reader import EnemyInfo


def departed(frame=20, raw=2):
    enemy = EnemyInfo(100)
    enemy.roster_id = -1
    enemy.eid = 'enemy_test'
    enemy.name = '测试敌人'
    enemy.hp = 30.0
    enemy.max_hp = 100.0
    enemy.lifecycle = 'departed'
    enemy.alive = False
    enemy.planned = True
    enemy.source_frame = frame - 1
    enemy.end_frame = frame
    enemy.end_reason = 'death'
    enemy.finish_reason = raw
    enemy.field_states = {
        'enemy.hp': collection_record(frame - 1, frame, 0, 'historical'),
        'enemy.finish_reason': collection_record(frame, frame, 0, 'historical'),
        'enemy.end_frame': collection_record(frame, frame, 0, 'historical'),
        'enemy.end_reason': collection_record(frame, frame, 0, 'historical'),
    }
    return enemy


def sample(enemy, frame=30, identity='battle-A', witness='live-A'):
    return {'ok': True, 'state': 2, 'fixed_frame': frame,
            'frame_consistent': True, 'enemies': [enemy],
            '_history_identity': identity, '_history_witnesses': [witness]}


def placeholder():
    enemy = departed()
    enemy.addr = 0
    enemy.source_frame = None
    enemy.end_frame = None
    enemy.end_reason = ''
    enemy.finish_reason = None
    enemy.hp = 0.0
    enemy.field_states = {}
    return enemy


def write_history(path, policy=None):
    with DepartureHistory(path) as history:
        history.observe(sample(departed()), policy or PolicyStore().snapshot())


def test_paths_follow_source_or_executable_not_cwd_or_bundle(monkeypatch, tmp_path):
    import backend.app.storage_paths as paths
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths.sys, 'frozen', False, raising=False)
    assert data_root() == Path(paths.__file__).resolve().parents[2] / 'data'
    monkeypatch.setattr(paths.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(paths.sys, 'executable', str(tmp_path / 'release' / 'Timeline.exe'))
    monkeypatch.setattr(paths.sys, '_MEIPASS', str(tmp_path / 'extracted'), raising=False)
    assert data_root() == tmp_path / 'release' / 'data'


def test_restart_restores_original_frames_without_touching_reader_objects(tmp_path):
    path = tmp_path / 'current_battle.json'
    write_history(path)
    original = placeholder()
    with DepartureHistory(path) as history:
        snap = sample(original, 35)
        history.observe(snap, PolicyStore().snapshot())
        restored = snap['enemies'][0]
        assert restored is not original
        assert original.finish_reason is None
        assert restored.finish_reason == 2
        assert restored.hp == 30
        assert restored.source_frame == 19
        assert restored.end_frame == 20
        assert restored.addr == 0
        assert restored.field_states['enemy.hp']['collectionState'] == 'historical'
        assert restored.field_states['enemy.hp']['sourceFrame'] == 19
        assert restored.field_states['enemy.hp']['latestKnownFrame'] == 35


def test_active_enemy_is_never_overwritten(tmp_path):
    path = tmp_path / 'current_battle.json'
    write_history(path)
    enemy = placeholder()
    enemy.lifecycle = 'active'
    enemy.alive = True
    enemy.hp = 80
    with DepartureHistory(path) as history:
        snap = sample(enemy)
        history.observe(snap, PolicyStore().snapshot())
        assert snap['enemies'][0] is enemy
        assert enemy.hp == 80


def test_same_stage_replay_rollback_or_different_process_is_not_restored(tmp_path):
    for frame, identity, witness in ((10, 'battle-A', 'live-A'),
                                     (40, 'battle-B', 'live-A'),
                                     (40, 'battle-A', 'new-enemy')):
        path = tmp_path / 'current_battle.json'
        write_history(path)
        with DepartureHistory(path) as history:
            snap = sample(placeholder(), frame, identity, witness)
            history.observe(snap, PolicyStore().snapshot())
            assert snap['enemies'][0].finish_reason is None


def test_missing_identity_failed_or_inconsistent_sample_preserves_file(tmp_path):
    path = tmp_path / 'current_battle.json'
    write_history(path)
    before = path.read_bytes()
    with DepartureHistory(path) as history:
        for change in ({'_history_identity': None}, {'ok': False},
                       {'frame_consistent': False}, {'fixed_frame': None}):
            snap = sample(placeholder()) | change
            history.observe(snap, PolicyStore().snapshot())
            assert snap['enemies'][0].finish_reason is None
    assert path.read_bytes() == before


def test_reset_durably_invalidates_and_drops_pre_reset_snapshot(tmp_path):
    path = tmp_path / 'current_battle.json'
    write_history(path)
    with DepartureHistory(path) as history:
        history.invalidate()
    with DepartureHistory(path) as history:
        snap = sample(placeholder())
        history.observe(snap, PolicyStore().snapshot())
        assert snap['enemies'][0].finish_reason is None
    assert json.loads(path.read_text(encoding='utf-8'))['records'] == []


def test_capture_off_erases_saved_raw_value_and_cannot_resurrect_on_reenable(tmp_path):
    path = tmp_path / 'current_battle.json'
    write_history(path)
    store = PolicyStore()
    with DepartureHistory(path) as history:
        store.commit({'enemy.finish_reason': {'collect': False}})
        snap = sample(placeholder())
        history.observe(snap, store.snapshot())
        assert snap['enemies'][0].finish_reason is None
        assert snap['enemies'][0].field_states['enemy.finish_reason']['collectionState'] == 'not_collected'
        store.commit({'enemy.finish_reason': {'collect': True}})
        next_snap = sample(placeholder(), 31)
        history.observe(next_snap, store.snapshot())
        assert next_snap['enemies'][0].finish_reason is None
    with DepartureHistory(path) as history:
        snap = sample(placeholder(), 32)
        history.observe(snap, store.snapshot())
        assert snap['enemies'][0].finish_reason is None


def test_corrupt_cache_and_write_failure_do_not_break_observation(tmp_path, monkeypatch):
    path = tmp_path / 'current_battle.json'
    path.write_text('{broken', encoding='utf-8')
    messages = []
    with DepartureHistory(path, log=messages.append) as history:
        import backend.app.services.departure_history as module
        monkeypatch.setattr(module.os, 'replace', lambda *args: (_ for _ in ()).throw(OSError('readonly')))
        snap = sample(departed())
        history.observe(snap, PolicyStore().snapshot())
        assert snap['enemies'][0].finish_reason == 2
    assert any('缓存' in message for message in messages)
    assert not path.with_suffix('.tmp').exists()


def test_raw_zero_unknown_and_null_are_preserved(tmp_path):
    for raw in (0, 99, None):
        path = tmp_path / 'current_battle.json'
        with DepartureHistory(path) as history:
            history.observe(sample(departed(raw=raw)), PolicyStore().snapshot())
        with DepartureHistory(path) as history:
            snap = sample(placeholder(), 31)
            history.observe(snap, PolicyStore().snapshot())
            assert snap['enemies'][0].finish_reason == raw


def test_bottom_level_reset_clears_history_even_when_auto_refresh_disabled():
    from backend import desktop_app
    calls = []
    stub = SimpleNamespace(_closing=False, _source_epoch=0,
                           _webui_runtime_snapshot={}, _auto_refresh_enabled=False,
                           _departure_history=SimpleNamespace(invalidate=lambda epoch: calls.append(('clear', epoch))))
    desktop_app.CoachWindow._on_game_time_reset_main(stub)
    assert calls == [('clear', 1)]
    assert stub._source_epoch == 1


def test_default_logs_are_portable_but_explicit_override_remains(monkeypatch, tmp_path):
    from backend.app import diagnostic_log
    monkeypatch.delenv('TIMELINE_LOG_DIR', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'machine-user-profile'))
    assert diagnostic_log.default_log_root() == data_root() / 'logs'
    monkeypatch.setenv('TIMELINE_LOG_DIR', str(tmp_path / 'chosen'))
    assert diagnostic_log.default_log_root() == tmp_path / 'chosen'


def test_restored_lifecycle_and_hp_survive_ws_and_webui_projection(tmp_path):
    from backend.app.services.websocket_api import WebSocketApi
    from tools.enemy_health.enemy_reader import EnemyReader
    path = tmp_path / 'current_battle.json'
    write_history(path)
    store = PolicyStore()
    enemy = placeholder()
    reader = EnemyReader()
    reader._fixed_frame_snap = 35
    reader.set_capture_policy(store.snapshot())
    reader._stamp_fields(enemy, 35, historical=True)
    with DepartureHistory(path) as history:
        snap = sample(enemy, 35)
        history.observe(snap, store.snapshot())
        api = WebSocketApi(False, 'test', policy_provider=store.snapshot)
        api.publish_runtime(snap)
        local = api.local_snapshot()['enemies']['items'][0]
        public = api._snapshots['enemies']['items'][0]
        assert local['lifecycle'] == 'departed'
        assert public['lifecycle'] == 'departed'
        assert local['hp'] == 30
        assert public['finishReason'] == 2
        assert local['fieldStates']['enemy.hp']['sourceFrame'] == 19
        assert local['fieldStates']['enemy.hp']['collectionState'] == 'historical'


def test_reenable_cannot_resave_reader_retained_departed_values(tmp_path):
    path = tmp_path / 'current_battle.json'
    store = PolicyStore()
    enemy = departed()
    with DepartureHistory(path) as history:
        history.observe(sample(enemy), store.snapshot())
        store.commit({'enemy.finish_reason': {'collect': False}})
        history.discard_disabled(store.snapshot())
        store.commit({'enemy.finish_reason': {'collect': True}})
        # A departed reader object cannot be sampled anew. Its old raw value
        # must not get written back simply because the policy generation changed.
        history.observe(sample(enemy, 31), store.snapshot())
    with DepartureHistory(path) as history:
        snap = sample(placeholder(), 32)
        history.observe(snap, store.snapshot())
        assert snap['enemies'][0].finish_reason is None


def test_source_epoch_rejects_old_snapshot_after_reset_but_accepts_new_scan(tmp_path):
    path = tmp_path / 'current_battle.json'
    with DepartureHistory(path) as history:
        history.observe(sample(departed()) | {'_history_epoch': 1}, PolicyStore().snapshot())
        history.invalidate(2)
        old = sample(departed()) | {'_history_epoch': 1}
        history.observe(old, PolicyStore().snapshot())
    assert json.loads(path.read_text(encoding='utf-8'))['records'] == []
    with DepartureHistory(path) as history:
        history.invalidate(2)
        history.observe(sample(departed()) | {'_history_epoch': 2}, PolicyStore().snapshot())
    assert len(json.loads(path.read_text(encoding='utf-8'))['records']) == 1


def test_matching_id_with_different_enemy_or_pending_row_is_not_restored(tmp_path):
    path = tmp_path / 'current_battle.json'
    write_history(path)
    for change in ({'eid': 'other'}, {'lifecycle': 'pending'}, {'planned': False}):
        enemy = placeholder()
        for name, value in change.items():
            setattr(enemy, name, value)
        with DepartureHistory(path) as history:
            snap = sample(enemy)
            history.observe(snap, PolicyStore().snapshot())
            assert snap['enemies'][0].finish_reason is None


def test_static_historical_and_original_attribute_types_are_preserved(tmp_path):
    path = tmp_path / 'current_battle.json'
    enemy = departed()
    enemy.attributes = {1: 400.0}
    enemy.atk = 400.0
    enemy.field_states['enemy.attr_1'] = collection_record(19, 20, 0, 'historical')
    enemy.field_states['enemy.name'] = collection_record(None, 20, 0, 'static')
    with DepartureHistory(path) as history:
        history.observe(sample(enemy), PolicyStore().snapshot())
    with DepartureHistory(path) as history:
        snap = sample(placeholder(), 35)
        history.observe(snap, PolicyStore().snapshot())
        restored = snap['enemies'][0]
        assert restored.attributes == {1: 400.0}
        assert restored.atk == 400.0
        assert restored.name == '测试敌人'
        assert restored.field_states['enemy.name']['collectionState'] == 'static'


def test_waiting_for_live_witness_does_not_destroy_same_battle_file(tmp_path):
    path = tmp_path / 'current_battle.json'
    write_history(path)
    before = path.read_bytes()
    with DepartureHistory(path) as history:
        snap = sample(placeholder(), witness='different')
        history.observe(snap, PolicyStore().snapshot())
    assert path.read_bytes() == before


def test_history_updates_are_not_queued_every_frame(tmp_path, monkeypatch):
    with DepartureHistory(tmp_path / 'current_battle.json') as history:
        queued = []
        original_queue = history._queue
        monkeypatch.setattr(history, '_queue', lambda payload: (queued.append(payload), original_queue(payload)))
        enemy = departed()
        for frame in range(30, 100):
            history.observe(sample(enemy, frame), PolicyStore().snapshot())
        assert len(queued) == 1
        assert history._pending is None or len(history._pending['records']) == 1


def test_blocked_disk_writer_does_not_block_observe_and_reset_wins(tmp_path, monkeypatch):
    import backend.app.services.departure_history as module
    started = threading.Event()
    release = threading.Event()
    replaced = []
    real_replace = module.os.replace

    def replace(source, target):
        if not replaced:
            started.set()
            assert release.wait(5)
        real_replace(source, target)
        replaced.append(target)

    monkeypatch.setattr(module.os, 'replace', replace)
    path = tmp_path / 'current_battle.json'
    with DepartureHistory(path) as history:
        try:
            history.observe(sample(departed()), PolicyStore().snapshot())
            assert started.wait(2)
            # The writer is blocked in IO while the owner can still reset.
            history.invalidate(1)
            assert history._pending['records'] == []
            assert not history.close(timeout=0)
        finally:
            release.set()
    assert json.loads(path.read_text(encoding='utf-8'))['records'] == []
    assert not list(tmp_path.glob('*.tmp'))


def test_bootstrap_process_birth_handles_spaces_and_pid_reuse(monkeypatch):
    from tools.enemy_health.memcore import MemCore
    mc = MemCore('unused-adb', adb_serial='serial')
    monkeypatch.setattr(mc, '_select_device', lambda: None)
    monkeypatch.setattr(mc, '_ensure_root', lambda: None)
    monkeypatch.setattr(mc, '_pid_for_known_package', lambda: ('game', 123))
    monkeypatch.setattr(mc, 'reload_maps', lambda: setattr(mc, 'regions', [(0x1000, 0x3000, 'r', '')]))
    monkeypatch.setattr(mc, 'channel', lambda: SimpleNamespace(batch_read=lambda *args, **kwargs: [b'x']))
    boot = '12345678-1234-1234-1234-123456789abc'
    command = []

    def shell(text, timeout):
        command.append(text)
        # Field 22 is starttime; the comm field can itself contain spaces and ')'.
        return boot + '\r\n123 (game ) process) S ' + '0 ' * 18 + '999 0\r\n'

    monkeypatch.setattr(mc, 'shell', shell)
    assert mc.connect() == 123
    assert mc.process_instance == (boot, 999)
    assert command == ['cat /proc/sys/kernel/random/boot_id /proc/123/stat']
    monkeypatch.setattr(mc, 'shell', lambda *args, **kwargs: 'unreadable')
    assert mc.connect() == 123
    assert mc.process_instance is None


def test_capture_identity_does_not_read_memory_and_changes_on_process_birth():
    mc = SimpleNamespace(process_instance=('boot', 1), adb_serial='serial', package='game', pid=123)
    reader = SimpleNamespace(mc=mc, bc_addr=100, sched_addr=200, plan_level_id='same-stage')
    enemy = departed()
    enemy.lifecycle = 'active'
    enemy.alive = True
    snap = sample(enemy)
    DepartureHistory.capture_identity(reader, snap)
    identity = snap['_history_identity']
    assert len(identity) == 64
    assert len(snap['_history_witnesses']) == 1
    mc.process_instance = ('boot', 2)
    DepartureHistory.capture_identity(reader, snap)
    assert snap['_history_identity'] != identity


def test_raw_reader_pathing_names_are_restored_not_public_schema_aliases(tmp_path):
    from backend.app.services.websocket_api import WebSocketApi
    path = tmp_path / 'current_battle.json'
    enemy = departed()
    point = {'row': 0, 'col': 3, 'label': 'A4'}
    enemy.pathing = {'available': False, 'historical': True, 'sample_frame': 19,
                     'intent_end': point, 'next_waypoint': point,
                     'route': {'kind': 'main', 'index': 0, 'label': '主#1'},
                     'next_checkpoint': {'index': 0, 'type': 0, 'label': '移动', 'target': point},
                     'checkpoint_countdown': {'seconds': None, 'frames': None}}
    for key in ('intent_end', 'next_waypoint', 'current_route', 'next_checkpoint', 'checkpoint_countdown'):
        enemy.field_states['enemy.' + key] = collection_record(19, 20, 0, 'historical')
    store = PolicyStore()
    with DepartureHistory(path) as history:
        history.observe(sample(enemy), store.snapshot())
    with DepartureHistory(path) as history:
        snap = sample(placeholder(), 35)
        history.observe(snap, store.snapshot())
        assert snap['enemies'][0].pathing['intent_end'] == point
        assert snap['enemies'][0].pathing['next_waypoint'] == point
        api = WebSocketApi(False, 'test', policy_provider=store.snapshot)
        api.publish_runtime(snap)
        public = api._snapshots['enemies']['items'][0]['pathing']
        assert public['intentEnd']['label'] == 'A4'
        assert public['nextCheckpoint']['label'] == '移动'
        assert public['available'] is False
        assert public['sampleFrame'] == 19


def test_nonfinite_numeric_values_never_become_restored_success(tmp_path):
    path = tmp_path / 'current_battle.json'
    enemy = departed()
    enemy.hp = float('nan')
    with DepartureHistory(path) as history:
        history.observe(sample(enemy), PolicyStore().snapshot())
    with DepartureHistory(path) as history:
        snap = sample(placeholder(), 35)
        history.observe(snap, PolicyStore().snapshot())
        assert snap['enemies'][0].field_states['enemy.hp']['collectionState'] == 'unavailable'
        assert snap['enemies'][0].finish_reason == 2


def test_in_process_frame_rollback_clears_previous_departure_records(tmp_path):
    path = tmp_path / 'current_battle.json'
    with DepartureHistory(path) as history:
        history.observe(sample(departed(), 30), PolicyStore().snapshot())
        snap = sample(placeholder(), 10)
        history.observe(snap, PolicyStore().snapshot())
        assert snap['enemies'][0].finish_reason is None
    assert json.loads(path.read_text(encoding='utf-8'))['records'] == []


def test_signed_but_invalid_schema_fields_and_integrity_fail_closed(tmp_path):
    import hashlib
    path = tmp_path / 'current_battle.json'
    for bad in ({'schema': 2, 'records': []},
                {'schema': 1, 'records': [{}]},
                {'schema': 1, 'records': [{'roster_id': -1, 'eid': 'e', 'fields': {
                    'enemy.hp': {'state': {}, 'values': {'arbitrary': 12}}}}]}):
        digest = hashlib.sha256(json.dumps(bad, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        path.write_text(json.dumps(dict(bad, checksum=digest)), encoding='utf-8')
        messages = []
        with DepartureHistory(path, log=messages.append) as history:
            assert history._loaded is None
        assert messages
    write_history(path)
    tampered = json.loads(path.read_text(encoding='utf-8'))
    tampered['frame'] = 999  # Deliberately retain the old checksum.
    path.write_text(json.dumps(tampered), encoding='utf-8')
    with DepartureHistory(path) as history:
        snap = sample(placeholder(), 1000)
        history.observe(snap, PolicyStore().snapshot())
        assert snap['enemies'][0].finish_reason is None
