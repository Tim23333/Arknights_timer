"""Dedicated deployment reads must stop before parsing disabled subtrees."""
import unittest
from unittest.mock import Mock

from backend.app.field_policy import PolicyStore
from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader


class DeployPolicyTests(unittest.TestCase):
    def test_disabled_logs_and_squad_skip_reader_chains(self):
        reader = DeployTrackerReader(Mock())
        reader._read_log_list = Mock(return_value=[])
        reader._read_squad = Mock(return_value=[])
        policy = PolicyStore().commit({key: {'collect': False} for key in
                                       ('deploy.events', 'deploy.journal', 'stage.squad')})
        reader.set_capture_policy(policy)
        self.assertEqual(reader.get_events(), [])
        self.assertEqual(reader.get_journal_events(), [])
        self.assertEqual(reader.get_squad(), [])
        reader._read_log_list.assert_not_called()
        reader._read_squad.assert_not_called()

    def test_disabled_stage_preserves_internal_session_identity(self):
        reader = DeployTrackerReader(Mock())
        reader._stage_info = {'stageId': 'main_01-07'}
        reader.set_capture_policy(PolicyStore().commit({'stage.stage': {'collect': False}}))
        self.assertEqual(reader.get_stage_info(), {})
        self.assertEqual(reader._stage_info['stageId'], 'main_01-07')


if __name__ == '__main__':
    unittest.main()
