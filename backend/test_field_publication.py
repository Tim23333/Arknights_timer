"""Regression tests for v2 policy publication and local/WS independence."""
import unittest
from types import SimpleNamespace

from backend.app.field_policy import PolicyStore
from backend.app.services.websocket_api import WebSocketApi


class FieldPublicationTests(unittest.TestCase):
    def test_raw_finish_reason_zero_null_and_unknown_obey_policy(self):
        for raw in (0, 2, 8, 12, 99, None):
            enemy = SimpleNamespace(eid='e', lifecycle='departed', end_reason='death',
                                    end_frame=0, finish_reason=raw)
            self.api.publish_runtime({'fixed_frame': 100, 'enemies': [enemy]})
            self.assertEqual(self.api.local_snapshot()['enemies']['items'][0]['finishReason'], raw)
            self.assertEqual(self.api._snapshots['enemies']['items'][0]['finishReason'], raw)
        enemy.field_states = {'enemy.finish_reason': {'collectionState': 'unavailable'}}
        enemy.finish_reason = 2  # Unavailable stale/default data must not be published.
        self.api.publish_runtime({'fixed_frame': 100, 'enemies': [enemy]})
        self.assertIsNone(self.api.local_snapshot()['enemies']['items'][0]['finishReason'])
        self.store.commit({'enemy.finish_reason': {'publish': False}})
        self.api.policy_changed()
        self.assertNotIn('finishReason', self.api._snapshots['enemies']['items'][0])
        self.assertIn('finishReason', self.api.local_snapshot()['enemies']['items'][0])
        self.store.commit({'enemy.finish_reason': {'display': False}})
        self.api.policy_changed()
        self.assertNotIn('finishReason', self.api.local_snapshot()['enemies']['items'][0])
        self.store.commit({'enemy.finish_reason': {'collect': False, 'display': True, 'publish': True}})
        self.api.policy_changed()
        # Capture changes invalidate the complete batch until the next sample.
        enemy.field_states = {'enemy.finish_reason': {'collectionState': 'not_collected'}}
        self.api.publish_runtime({'fixed_frame': 101, 'enemies': [enemy]})
        self.assertNotIn('finishReason', self.api.local_snapshot()['enemies']['items'][0])

    def test_finish_reason_common_hook_and_detail_keep_original_code(self):
        enemy = SimpleNamespace(eid='e', finish_reason=8, end_reason='death')
        self.api.publish_runtime({'fixed_frame': 100, 'enemies': [enemy], 'detail_enemy': enemy})
        self.assertEqual(self.api.local_snapshot()['enemy_detail']['items'][0]['finishReason'], 8)
        self.api.publish_fields('enemy', {'enemy.finish_reason': 8}, entity_id='e', source_frame=100)
        self.assertEqual(self.api._snapshots['enemies']['items'][0]['finishReason'], 8)
        self.store.commit({'enemy.finish_reason': {'publish': False}})
        self.api.policy_changed()
        self.assertNotIn('finishReason', self.api._snapshots['enemies']['items'][0])

    def test_departure_metadata_is_public_and_obeys_independent_switches(self):
        enemy = SimpleNamespace(eid='e', lifecycle='departed', end_reason='death', end_frame=0)
        self.api.publish_runtime({'fixed_frame': 100, 'enemies': [enemy]})
        row = self.api.local_snapshot()['enemies']['items'][0]
        self.assertEqual(row['endReason'], 'death')
        self.assertEqual(row['endFrame'], 0)
        self.store.commit({'enemy.end_reason': {'publish': False}, 'enemy.end_frame': {'display': False}})
        self.api.policy_changed()
        self.assertNotIn('endReason', self.api._snapshots['enemies']['items'][0])
        self.assertNotIn('endFrame', self.api.local_snapshot()['enemies']['items'][0])

    def setUp(self):
        self.store = PolicyStore()
        self.api = WebSocketApi(False, "test", policy_provider=self.store.snapshot)

    def test_local_display_does_not_depend_on_ws_publish_switch(self):
        self.store.commit({"enemy.hp": {"collect": True, "display": True, "publish": False}})
        self.api.publish_runtime({"ok": True, "character_ok": True,
            "fixed_frame": 100, "frame_consistent": True,
            "enemies": [SimpleNamespace(eid="e", hp=8, max_hp=10)], "characters": []})
        self.assertEqual(self.api.local_snapshot()["enemies"]["items"][0]["hp"], 8)
        self.assertNotIn("hp", self.api._snapshots["enemies"]["items"][0])

    def test_policy_change_invalidates_cached_values_before_new_sampling(self):
        self.api.publish_timer({"connected": True, "game_time": 10, "frame_count": 300})
        self.store.commit({"battle.gameTime": {"collect": True, "display": True, "publish": False}})
        self.api.policy_changed()
        self.assertNotIn("gameTime", self.api._snapshots["battle"])
        self.assertEqual(self.api.local_snapshot()["battle"]["gameTime"], 10)

    def test_failed_character_read_is_not_a_valid_empty_deployed_list(self):
        self.api.publish_runtime({"ok": True, "character_ok": False,
            "fixed_frame": 100, "frame_consistent": True, "enemies": [], "characters": []})
        self.assertEqual(self.api._snapshots["characters"]["meta"]["collectionState"], "unavailable")

    def test_new_registered_field_uses_common_publication_hook(self):
        self.api.publish_fields("enemy", {"enemy.hp": 5}, entity_id="enemy-e", source_frame=12)
        item = self.api._snapshots["enemies"]["items"][0]
        self.assertEqual(item["hp"], 5)
        self.assertEqual(item["id"], "enemy-e")
        self.assertEqual(self.api._snapshots["enemies"]["meta"]["sourceFrame"], 12)

    def test_hook_rejects_unknown_field_and_never_accepts_raw_pointers(self):
        with self.assertRaises(ValueError):
            self.api.publish_fields("enemy", {"enemy.pointer": 123}, entity_id="e")

    def test_character_position_comes_from_grid_not_missing_position_property(self):
        self.api.publish_runtime({"ok": True, "character_ok": True,
            "fixed_frame": 100, "frame_consistent": True, "enemies": [],
            "characters": [SimpleNamespace(cid="c", grid_row=3, grid_col=8)]})
        point = self.api._snapshots["characters"]["items"][0]["position"]
        self.assertEqual(point, {"row": 3, "col": 8, "x": 8, "y": 3})

    def test_unknown_action_leaves_cannot_bypass_registered_switches(self):
        self.api.publish_runtime({"fixed_frame": 1, "enemies": [SimpleNamespace(
            eid="e", action={"state_name": "move", "secret_predictor": "old", "animation_remaining": 99})]})
        self.assertEqual(self.api._snapshots["enemies"]["items"][0]["action"], {"state_name": "move"})

    def test_failed_field_does_not_export_internal_default_zero(self):
        self.api.publish_runtime({"fixed_frame": 1, "enemies": [SimpleNamespace(
            eid="e", hp=0, max_hp=0, field_states={"enemy.hp": {"collectionState": "unavailable"}})]})
        self.assertNotIn("hp", self.api._snapshots["enemies"]["items"][0])
        self.assertNotIn("maxHp", self.api.local_snapshot()["enemies"]["items"][0])

    def test_old_configuration_result_cannot_refill_invalidated_cache(self):
        old_generation = self.store.snapshot().generation
        self.store.commit({"enemy.name": {"collect": False}})
        self.api.policy_changed()
        self.api.publish_runtime({"policy_generation": old_generation, "fixed_frame": 1,
                                  "enemies": [SimpleNamespace(eid="e", name="old")]})
        self.assertNotIn("enemies", self.api.local_snapshot())

    def test_local_selected_heavy_detail_works_without_ws_subscriber(self):
        enemy = SimpleNamespace(eid="e", addr=100, raw_attributes={1: 20}, buffs=[{"name": "buff"}])
        self.api.publish_runtime({"fixed_frame": 1, "enemies": [enemy], "detail_enemy": enemy})
        self.assertEqual(self.api.local_snapshot()["enemy_detail"]["items"][0]["rawAttributes"], {"1": 20})

    def test_enemy_detail_skills_use_current_primary_sample(self):
        live = SimpleNamespace(eid='e', addr=100, skills=[{'id': 'skill'}],
            skills_detail=[{'id': 'skill', 'cooldown': 3}], field_states={
                'enemy.skill': {'collectionState': 'current', 'sourceFrame': 100}})
        heavy = SimpleNamespace(eid='e', addr=100, skills_detail=[], field_states={
            'enemy_detail.skills': {'collectionState': 'unavailable'}})
        self.api.publish_runtime({'fixed_frame': 100, 'enemies': [live],
                                  'detail_enemy': heavy})
        row = self.api.local_snapshot()['enemy_detail']['items'][0]
        self.assertEqual(row['skills'], [{'id': 'skill', 'cooldown': 3}])
        self.assertEqual(row['fieldStates']['enemy_detail.skills']['collectionState'], 'current')
        self.assertEqual(row['fieldStates']['enemy_detail.skills']['sourceFrame'], 100)
        live.field_states['enemy.skill'] = {'collectionState': 'unavailable', 'sourceFrame': 101}
        self.api.publish_runtime({'fixed_frame': 101, 'enemies': [live],
                                  'detail_enemy': heavy})
        row = self.api.local_snapshot()['enemy_detail']['items'][0]
        self.assertNotIn('skills', row)
        self.assertEqual(row['fieldStates']['enemy_detail.skills']['collectionState'],
                         'unavailable')

    def test_stopped_source_is_explicitly_unavailable_not_a_current_last_frame(self):
        self.api.publish_fields("enemy", {"enemy.hp": 5}, entity_id="e", source_frame=12)
        self.api.invalidate_domains(("enemies",), "source_stopped")
        data = self.api.local_snapshot()["enemies"]
        self.assertEqual(data["items"], [])
        self.assertEqual(data["meta"]["collectionState"], "unavailable")

    def test_root_damage_summary_obeys_nested_field_policy(self):
        self.store.commit({"character.damage_physical": {"publish": False}})
        summary = SimpleNamespace(global_total_damage=123, damage_by_type={1:77}, unattributed_damage_total=88)
        self.api.publish_runtime({"fixed_frame": 1, "global_damage_summary": summary})
        data = self.api._snapshots["characters"]["globalDamageSummary"]
        self.assertNotIn("physical", data["damageByType"])
        self.assertNotIn("unattributedDamage", data)

    def test_hook_rejects_delayed_batch_from_old_sampling_policy(self):
        generation = self.store.snapshot().generation
        self.store.commit({"enemy.name": {"publish": False}})
        self.api.publish_fields("enemy", {"enemy.hp": 5}, entity_id="e", source_frame=12,
                                policy_generation=generation)
        self.assertNotIn("enemies", self.api.local_snapshot())

    def test_battle_fields_keep_clock_and_runtime_source_frames_separate(self):
        self.api.publish_timer({"connected": True, "game_time": 10, "frame_count": 600})
        self.api.publish_runtime({"fixed_frame": 599, "frame_end": 599, "latest_known_frame": 600,
                                  "state": 2, "speed_level": 1, "time_scale": 1})
        states = self.api.local_snapshot()["battle"]["fieldStates"]
        self.assertEqual(states["battle.gameTime"]["sourceFrame"], 600)
        self.assertEqual(states["battle.speedLevel"]["sourceFrame"], 599)

    def test_old_session_payload_cannot_be_relabelled_as_new_session(self):
        self.api.publish_fields("enemy", {"enemy.hp": 5}, entity_id="e", source_frame=12)
        previous = self.api.local_snapshot()["enemies"]
        self.api.begin_session()
        self.api._publish("enemies", previous)
        self.assertNotIn("enemies", self.api.local_snapshot())


if __name__ == "__main__":
    unittest.main()
