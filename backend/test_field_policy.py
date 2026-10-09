"""Regression contract for atomic field policies and public projection."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.field_policy import (
    FIELD_REGISTRY, PolicyStore, PolicyValidationError, project_payload,
    collection_record, project_snapshot,
)
from backend.app.custom_options import CustomOptions


class FieldPolicyTests(unittest.TestCase):
    def test_all_switches_are_boolean_and_snapshot_is_immutable(self):
        store = PolicyStore()
        policy = store.snapshot()
        self.assertTrue(policy.enabled('enemy.hp'))
        with self.assertRaises(TypeError):
            policy.fields['enemy.hp'] = None

    def test_conflict_is_rejected_without_flipping_dependencies(self):
        store = PolicyStore()
        before = store.snapshot()
        with self.assertRaises(PolicyValidationError) as caught:
            store.commit({'enemy.next_checkpoint': {'collect': False}})
        self.assertIn('enemy.checkpoint_countdown', str(caught.exception))
        self.assertIs(store.snapshot(), before)

    def test_capture_off_retains_consumer_preferences(self):
        store = PolicyStore()
        policy = store.commit({'enemy.precise_pos': {'collect': False}})
        self.assertFalse(policy.enabled('enemy.precise_pos'))
        self.assertTrue(policy.enabled('enemy.precise_pos', 'display'))
        self.assertTrue(policy.enabled('enemy.precise_pos', 'publish'))
        projected = project_payload('enemy', {'precisePosition': {'x': 1}}, policy)
        self.assertNotIn('precisePosition', projected)

    def test_switch_change_does_not_mutate_previous_generation(self):
        store = PolicyStore()
        previous = store.snapshot()
        next_policy = store.commit({'enemy.precise_pos': {'publish': False}})
        self.assertEqual(next_policy.generation, previous.generation + 1)
        self.assertTrue(previous.enabled('enemy.precise_pos', 'publish'))
        self.assertFalse(next_policy.enabled('enemy.precise_pos', 'publish'))
        self.assertEqual(next_policy.collected_ids, previous.collected_ids)

    def test_invalid_types_and_unknown_keys_rejected(self):
        store = PolicyStore()
        for candidate in ({'enemy.hp': {'collect': 0}}, {'enemy.missing': {}},
                          {'enemy.hp': {'automatic': True}}):
            with self.subTest(candidate=candidate):
                with self.assertRaises(PolicyValidationError):
                    store.commit(candidate)

    def test_registered_path_projection_is_nested_and_leaves_source_unchanged(self):
        store = PolicyStore()
        policy = store.commit({'enemy.next_waypoint': {'publish': False}})
        value = {'pathing': {'nextWaypoint': {'row': 1}, 'route': {'index': 2}},
                 'columns': {'next_waypoint': '(1, 2)', 'current_route': '主 #2'}}
        public = project_payload('enemy', value, policy)
        self.assertNotIn('nextWaypoint', public['pathing'])
        self.assertNotIn('next_waypoint', public['columns'])
        self.assertIn('route', public['pathing'])
        self.assertIn('nextWaypoint', value['pathing'])

    def test_persisted_policy_is_atomic_and_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'options.json'
            options = CustomOptions(path).load()
            store = PolicyStore(options)
            store.commit({'enemy.precise_pos': {'collect': False}})
            restored = PolicyStore(CustomOptions(path).load())
            self.assertFalse(restored.snapshot().enabled('enemy.precise_pos'))
            self.assertEqual(json.loads(path.read_text())['field_policy']['version'], 1)

    def test_disk_failure_keeps_policy_and_options_previous_state(self):
        with tempfile.TemporaryDirectory() as directory:
            options = CustomOptions(Path(directory) / 'options.json').load()
            store = PolicyStore(options)
            old = store.snapshot()
            with patch('backend.app.custom_options.save', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    store.commit({'enemy.precise_pos': {'collect': False}})
            self.assertIs(store.snapshot(), old)
            self.assertEqual(options.get('field_policy'), {'version': 1, 'fields': {}})

    def test_frame_metadata_preserves_source_when_completion_is_newer(self):
        record = collection_record(100, 101, 2, 'current', accepted_frame=100)
        self.assertEqual(record['sourceFrame'], 100)
        self.assertEqual(record['latestKnownFrame'], 101)
        self.assertEqual(record['acceptedFrame'], 100)
        self.assertEqual(record['collectionState'], 'current')

    def test_registry_covers_all_public_domains(self):
        self.assertTrue({'enemy', 'character', 'battle', 'stage', 'deploy', 'rng',
                         'enemy_detail', 'character_detail', 'quality'} <=
                        {spec.domain for spec in FIELD_REGISTRY.values()})

    def test_default_unattributed_tracking_remains_disabled(self):
        self.assertFalse(PolicyStore().snapshot().enabled('character.unattributed_damage'))

    def test_every_actual_ui_data_column_has_a_registry_entry(self):
        # Qt 列定义中的纯按钮/行号没有采集属性，其余列都必须有稳定 ID。
        import re
        root = Path(__file__).parent / 'app'
        for domain in ('enemy', 'character'):
            source = (root / f'{domain}_ui.py').read_text(encoding='utf-8')
            keys = set(re.findall(r"_col\('([^']+)'", source)) - {'row', 'detail'}
            for key in keys:
                self.assertIn(f'{domain}.{key}', FIELD_REGISTRY)

    def test_turning_off_rng_leaf_masks_every_role_and_selected(self):
        store = PolicyStore()
        policy = store.commit({'rng.predictions': {'publish': False}})
        payload = {'selected': {'predictions': [1], 'cursor': 2},
                   'by_role': {'imp': {'predictions': [3]},
                               'trivial': {'predictions': [4]}}}
        projected = project_payload('rng', payload, policy)
        self.assertNotIn('predictions', projected['selected'])
        self.assertNotIn('predictions', projected['by_role']['imp'])
        self.assertNotIn('predictions', projected['by_role']['trivial'])

    def test_snapshot_projection_clones_changed_branches_not_frame_metadata(self):
        # ROOT CAUSE: copying every entity's 70 provenance records multiple times
        # per publish consumed the 60Hz frame budget. Immutable accepted metadata
        # can be shared; only branches containing disabled values need a copy.
        policy = PolicyStore().commit({'enemy.precise_pos': {'publish': False}})
        payload = {'position': {'x': 2}, 'precisePosition': {'x': 2.1},
                   'columns': {'pos': '(2,3)', 'precise_pos': '(2.1,3.1)'},
                   'fieldStates': {'enemy.pos': {'sourceFrame': 1}}}
        result = project_snapshot('enemy', payload, policy)
        self.assertNotIn('precisePosition', result)
        self.assertNotIn('precise_pos', result['columns'])
        self.assertIsNot(result, payload)
        self.assertIsNot(result['columns'], payload['columns'])
        self.assertIs(result['position'], payload['position'])
        self.assertIs(result['fieldStates'], payload['fieldStates'])
        self.assertIn('precisePosition', payload)
        self.assertIn('precise_pos', payload['columns'])

    def test_snapshot_wildcard_projection_preserves_source_roles(self):
        policy = PolicyStore().commit({'rng.predictions': {'publish': False}})
        payload = {'by_role': {'battle': {'predictions': [3], 'history': [1]},
                               'other': {'predictions': [4]}}}
        result = project_snapshot('rng', payload, policy)
        self.assertNotIn('predictions', result['by_role']['battle'])
        self.assertNotIn('predictions', result['by_role']['other'])
        self.assertEqual(payload['by_role']['battle']['predictions'], [3])
        self.assertIs(result['by_role']['battle']['history'], payload['by_role']['battle']['history'])

    def test_public_projection_remains_deep_independent(self):
        payload = {'position': {'x': 2}, 'fieldStates': {'enemy.pos': {'sourceFrame': 1}}}
        result = project_payload('enemy', payload, PolicyStore().snapshot())
        result['position']['x'] = 9
        result['fieldStates']['enemy.pos']['sourceFrame'] = 5
        self.assertEqual(payload['position']['x'], 2)
        self.assertEqual(payload['fieldStates']['enemy.pos']['sourceFrame'], 1)


if __name__ == '__main__':
    unittest.main()
