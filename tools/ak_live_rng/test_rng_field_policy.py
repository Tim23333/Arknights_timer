"""RNG switches must suppress prediction work, not merely JSON visibility."""
import unittest
from unittest.mock import Mock

from backend.app.field_policy import PolicyStore
from tools.ak_live_rng.rng_service import RngService
from tracker import EngineTracker


class RngPolicyTests(unittest.TestCase):
    def test_rng_batch_prediction_and_cursor_share_one_accepted_state(self):
        # ROOT CAUSE: snapshot released the tracker lock before predict acquired
        # it again. A poll between the locks mixed two states in one public batch.
        from rng_engines import DotNetRandom
        tracker = EngineTracker(Mock(), {'id': 1, 'label': 'test', 'role': 'imp',
                                         'kind': 'knuth', 'paired': False,
                                         'obj': 123, 'array': 456})
        tracker.state = DotNetRandom(seed=42)
        expected = tracker.state.clone().next_int()
        import threading
        class InterveningLock:
            # Schedule a competing poll immediately after the snapshot's first
            # critical section. It still obtains the same underlying lock.
            def __init__(self):
                self.native = threading.Lock()
                self.once = True
            def __enter__(self):
                self.native.acquire()
            def __exit__(self, *args):
                self.native.release()
                if self.once:
                    self.once = False
                    with self.native:
                        tracker.state.next_int()
                        tracker.total += 1
        tracker.lock = InterveningLock()
        snapshot = tracker.snapshot(0, 1)
        self.assertEqual(snapshot['cursor'], 0)
        self.assertEqual(snapshot['total'], 0)
        self.assertEqual(snapshot['predictions'][0]['raw'], expected)
        self.assertEqual(tracker.state.inext, 1)

    def test_reenabled_rng_requires_successful_read_in_new_generation(self):
        from rng_engines import DotNetRandom
        store = PolicyStore()
        service = RngService(reader=Mock(), use_cache=False)
        tracker = EngineTracker(Mock(), {'id': 1, 'label': 'test', 'role': 'imp',
                                         'kind': 'knuth', 'paired': False,
                                         'obj': 123, 'array': 456})
        tracker.read_state = Mock(side_effect=lambda: DotNetRandom(seed=42))
        service._trackers = {1: tracker}
        service._selected_id = 1
        service.set_capture_policy(store.snapshot())
        tracker.poll()
        self.assertEqual(service.snapshot(0, 0)['collectionState'], 'current')
        service.set_capture_policy(store.commit({'rng.cursor': {'collect': False}}))
        service.set_capture_policy(store.commit({'rng.cursor': {'collect': True}}))
        waiting = service.snapshot(0, 0)
        self.assertEqual(waiting['collectionState'], 'unavailable')
        self.assertNotIn('selected', waiting)
        tracker.poll()
        self.assertEqual(service.snapshot(0, 0)['collectionState'], 'current')
        tracker.read_state = Mock(return_value=None)
        tracker.poll()
        failed = service.snapshot(0, 0)
        self.assertEqual(failed['collectionState'], 'unavailable')
        self.assertNotIn('selected', failed)

    def test_disabled_history_stops_per_value_dto_and_rate_work(self):
        from rng_engines import DotNetRandom
        tracker = EngineTracker(Mock(), {'id': 1, 'label': 'test', 'role': 'imp',
                                         'kind': 'knuth', 'paired': False,
                                         'obj': 123, 'array': 456})
        tracker.state = DotNetRandom(seed=42)
        advanced = tracker.state.clone()
        advanced.next_int()
        tracker.read_state = Mock(return_value=advanced)
        policy = PolicyStore().commit({key: {'collect': False} for key in
                                       ('rng.history', 'rng.rate', 'rng.activity')})
        tracker.set_capture_policy(policy)
        self.assertEqual(tracker.poll(), [])
        self.assertEqual(len(tracker.history), 0)
        self.assertEqual(len(tracker.call_times), 0)
        self.assertEqual(tracker.total, 1)

    def test_zero_prediction_length_skips_predict_function(self):
        tracker = EngineTracker(Mock(), {'id': 1, 'label': 'test', 'role': 'imp',
                                         'kind': 'knuth', 'paired': False,
                                         'obj': 123, 'array': 456})
        tracker.predict = Mock(return_value=[])
        tracker.snapshot(0, 0)
        tracker.predict.assert_not_called()

    def test_service_disables_prediction_and_history_before_tracker_work(self):
        service = RngService(reader=Mock(), use_cache=False)
        tracker = Mock()
        tracker.engine = {'id': 1, 'role': 'imp'}
        tracker.snapshot.return_value = {key: 0 for key in
            ('id', 'label', 'role', 'cursor', 'total', 'rate', 'status')}
        tracker.snapshot.return_value.update(history=[1], predictions=[2])
        service._trackers = {1: tracker}
        service._selected_id = 1
        policy = PolicyStore().commit({'rng.predictions': {'collect': False},
                                       'rng.history': {'collect': False}})
        service.set_capture_policy(policy)
        snapshot = service.snapshot(50, 12)
        self.assertNotIn('predictions', snapshot['selected'])
        self.assertNotIn('history', snapshot['selected'])
        self.assertTrue(all(call.args[:2] == (0, 0)
                            for call in tracker.snapshot.call_args_list))


if __name__ == '__main__':
    unittest.main()
