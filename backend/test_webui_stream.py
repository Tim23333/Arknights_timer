"""Latest-only local delivery; fixtures are not game telemetry."""
import json
import unittest
import concurrent.futures

from backend.app.services.webui_stream import LatestStream
from backend.app.services.websocket_api import WebSocketApi
from backend.app.field_policy import PolicyStore


class StreamTests(unittest.TestCase):
    def test_slow_reader_gets_latest_per_topic_not_a_frame_backlog(self):
        stream = LatestStream()
        for frame in range(100):
            stream.publish('clock', {'fixedFrame': frame})
        packets = stream.read_after({}, timeout=0)
        self.assertEqual(len(packets), 1)
        packet = json.loads(packets[0][2])
        self.assertEqual(packet['data']['fixedFrame'], 99)
        self.assertEqual(stream.read_after({'clock': packets[0][0]}, timeout=0), [])

    def test_unchanged_values_do_not_send_and_close_wakes_readers(self):
        stream = LatestStream()
        stream.publish('enemies', {'items': []})
        first = stream.read_after({}, timeout=0)
        stream.publish('enemies', {'items': []})
        self.assertEqual(stream.read_after({'enemies': first[0][0]}, timeout=0), [])
        stream.close()
        self.assertTrue(stream.closed)

    def test_clock_is_available_without_external_ws_or_a_qt_refresh(self):
        api = WebSocketApi(False, 'test')
        api.publish_timer({'connected': True, 'game_time': 1, 'frame_count': 30})
        revision, clock = api.wait_local_update('clock', 0, timeout=0)
        self.assertEqual(clock['fixedFrame'], 30)
        api.publish_timer({'connected': True, 'game_time': 2, 'frame_count': 60})
        next_revision, clock = api.wait_local_update('clock', revision, timeout=0)
        self.assertGreater(next_revision, revision)
        self.assertEqual(clock['fixedFrame'], 60)
        self.assertEqual(api.wait_local_update('modules', 0, timeout=0), (0, None))

    def test_new_session_notifies_modules_even_before_a_new_sample(self):
        api = WebSocketApi(False, 'test')
        api.begin_session()
        revision, _ = api.wait_local_update('modules', 0, timeout=0)
        self.assertGreater(revision, 0)

    def test_close_releases_waiting_reader_and_topics_keep_independent_latest_slots(self):
        stream = LatestStream()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(stream.read_after, {}, 5)
            stream.close()
            self.assertEqual(waiting.result(timeout=1), [])
        stream = LatestStream()
        stream.publish('enemies', {'items': [1]})
        stream.publish('characters', {'items': [2]})
        self.assertEqual(len(stream.read_after({}, timeout=0)), 2)

    def test_entity_frames_do_not_relabel_or_replace_the_authoritative_clock(self):
        api = WebSocketApi(False, 'test')
        api.publish_timer({'connected': True, 'game_time': 1, 'frame_count': 30})
        revision, _ = api.wait_local_update('clock', 0, timeout=0)
        api.publish_runtime({'fixed_frame': 99, 'frame_consistent': True,
                             'game_time': 99, 'enemies': [], 'characters': []})
        self.assertEqual(api.wait_local_update('clock', revision, timeout=0), (revision, None))
        clock = api.wait_local_update('clock', -1, timeout=0)[1]
        self.assertEqual(clock['fixedFrame'], 30)
        self.assertEqual(clock['meta']['sourceFrame'], 30)
        self.assertEqual(clock['gameTime'], 1)

    def test_clock_display_respects_policy_but_not_ws_publishing(self):
        store = PolicyStore()
        api = WebSocketApi(False, 'test', policy_provider=store.snapshot)
        store.commit({'battle.gameTime': {'publish': False}})
        api.policy_changed()
        api.publish_timer({'connected': True, 'game_time': 2, 'frame_count': 60})
        self.assertEqual(api.wait_local_update('clock', -1, timeout=0)[1]['gameTime'], 2)
        store.commit({'battle.gameTime': {'display': False}})
        api.policy_changed()
        self.assertNotIn('gameTime', api.wait_local_update('clock', -1, timeout=0)[1])
        store.commit({'enemy.hp': {'collect': False}})
        api.policy_changed()
        self.assertNotIn('gameTime', api.wait_local_update('clock', -1, timeout=0)[1])
