# -*- coding: utf-8 -*-
import asyncio
import json
import time
import unittest
from types import SimpleNamespace

import websockets

from backend.app.services.websocket_api import WebSocketApi


class WebSocketApiTests(unittest.TestCase):
    def setUp(self):
        self.api = WebSocketApi(enabled=True, app_version="test", port=0)
        self.api.start_if_enabled()
        deadline = time.monotonic() + 3
        while self.api.port == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertNotEqual(self.api.port, 0)

    def tearDown(self):
        self.api.stop()

    def test_game_subscription_receives_versioned_battle_message(self):
        async def scenario():
            async with websockets.connect(
                f"ws://127.0.0.1:{self.api.port}/v1/game") as websocket:
                ready = json.loads(await websocket.recv())
                self.assertEqual(ready["type"], "game.ready")
                await websocket.send(json.dumps({
                    "type": "subscribe", "topics": {"battle": {"rateHz": 60}},
                }))
                updated = json.loads(await websocket.recv())
                self.assertEqual(updated["type"], "subscription.updated")
                self.api.publish_timer({"connected": True, "game_time": 12.5, "frame_count": 750})
                message = json.loads(await websocket.recv())
                self.assertEqual(message["type"], "battle.updated")
                self.assertEqual(message["schemaVersion"], 1)
                self.assertEqual(message["data"]["gameTime"], 12.5)

        asyncio.run(scenario())

    def test_ops_endpoint_rejects_game_topics(self):
        async def scenario():
            async with websockets.connect(
                f"ws://127.0.0.1:{self.api.port}/v1/ops") as websocket:
                status = json.loads(await websocket.recv())
                self.assertEqual(status["type"], "ops.status")
                self.assertNotIn("port", status["data"])
                self.assertEqual(status["data"]["service"]["protocolVersion"], 1)
                await websocket.send(json.dumps({
                    "type": "subscribe", "topics": {"battle": {"rateHz": 20}},
                }))
                updated = json.loads(await websocket.recv())
                self.assertEqual(updated["type"], "subscription.updated")
                self.assertEqual(updated["data"]["topics"]["battle"]["error"], "unsupported topic")

        asyncio.run(scenario())

    def test_ops_heartbeat_runs_without_game_frames(self):
        async def scenario():
            async with websockets.connect(
                f"ws://127.0.0.1:{self.api.port}/v1/ops") as websocket:
                await websocket.recv()
                await websocket.send(json.dumps({
                    "type": "subscribe", "topics": {"ops.heartbeat": {"rateHz": 2}},
                }))
                await websocket.recv()
                message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=1.5))
                self.assertEqual(message["type"], "ops.heartbeat")

        asyncio.run(scenario())

    def test_disabling_releases_listener(self):
        self.api.set_enabled(False)
        self.assertFalse(self.api.status_snapshot()["enabled"])
        self.assertEqual(self.api.port, 0)

    def test_detail_target_filter_never_returns_unrequested_entities(self):
        data = {"items": [{"id": "enemy-1"}, {"id": "enemy-2"}]}
        projected = WebSocketApi._topic_data(
            "enemy_detail", data, {"scope": "selected", "ids": ["enemy-2"]})
        self.assertEqual(projected["items"], [{"id": "enemy-2"}])

    def test_selected_detail_subscription_requires_ids(self):
        async def scenario():
            async with websockets.connect(
                f"ws://127.0.0.1:{self.api.port}/v1/game") as websocket:
                await websocket.recv()
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "topics": {"enemy_detail": {"scope": "selected"}},
                }))
                updated = json.loads(await websocket.recv())
                self.assertEqual(
                    updated["data"]["topics"]["enemy_detail"]["error"],
                    "selected scope requires an ids array",
                )

        asyncio.run(scenario())

    def test_battle_snapshot_keeps_timer_clock_when_runtime_arrives_later(self):
        self.api.publish_runtime({
            "frame_consistent": True, "state": 2, "play_time": 15.0,
            "fixed_frame": 450, "speed_level": 2, "time_scale": 2.0,
            "paused_snapshot": False, "enemies": [], "characters": [],
        })
        self.api.publish_timer({
            "connected": True, "configured": True, "game_time": 15.1,
            "frame_count": 453, "source": "guest", "last_refresh": "now",
            "message": "ok",
        })
        self.api.publish_runtime({
            "frame_consistent": True, "state": 2, "play_time": 99.0,
            "fixed_frame": 2970, "speed_level": 2, "time_scale": 2.0,
            "paused_snapshot": False, "enemies": [], "characters": [],
        })
        battle = self.api._snapshots["battle"]
        self.assertEqual(battle["state"], "playing")
        self.assertEqual(battle["stateCode"], 2)
        self.assertEqual(battle["gameTime"], 15.1)
        self.assertEqual(battle["fixedFrame"], 453)
        self.assertEqual(battle["speedLevel"], 2)
        self.assertEqual(battle["clockSource"], "guest")
        self.assertTrue(battle["frameConsistent"])

    def test_runtime_exports_enemy_pos_x_and_pos_y(self):
        enemy = SimpleNamespace(
            eid="enemy-1", name="enemy", pos_x=3.25, pos_y=7.5,
            hp=100.0, max_hp=100.0, alive=True, lifecycle="active",
        )
        self.api.publish_runtime({
            "frame_consistent": True, "state": 2, "enemies": [enemy], "characters": [],
        })

        position = self.api._snapshots["enemies"]["items"][0]["position"]
        self.assertEqual(position, {"x": 3.25, "y": 7.5})

    def test_runtime_exports_route_intent_without_internal_addresses(self):
        enemy = SimpleNamespace(
            eid="enemy-1", name="enemy", pos_x=3.25, pos_y=7.5,
            hp=100.0, max_hp=100.0, alive=True, lifecycle="active",
            route_intent_enabled=True, route_intent_status="ready",
            intent_end={"row": 1, "col": 10}, route_source="main",
            intent_route_index=0, route_display="主 #1（A1 → F10）",
            next_waypoint={"row": 2, "col": 9},
            next_checkpoint={"index": 0, "type": 0, "type_name": "移动至目标格",
                             "position": {"row": 2, "col": 9}, "configured_time": 0.0},
            checkpoint_countdown=28.333, countdown_source="fragment",
            countdown_target=80.0, checkpoint_condition=None, addr=0x123456,
        )
        self.api.publish_runtime({"frame_consistent": True, "state": 2,
                                  "enemies": [enemy], "characters": []})
        route = self.api._snapshots["enemies"]["items"][0]["routeIntent"]
        self.assertEqual(route["route"]["index"], 0)
        self.assertEqual(route["countdownSource"], "fragment")
        self.assertEqual(route["nextCheckpoint"], {
            "index": 0, "type": 0, "typeName": "移动至目标格",
            "position": {"row": 2, "col": 9}, "configuredTime": 0.0,
        })
        self.assertNotIn("0x123456", json.dumps(route))

    def test_runtime_exports_dynamic_route_without_checkpoint(self):
        enemy = SimpleNamespace(
            eid="enemy-1", route_intent_enabled=True, route_intent_status="ready",
            intent_end={"row": 4, "col": 1}, route_source="runtime",
            intent_route_index=None, route_display="运行时动态路线",
            next_waypoint={"row": 4, "col": 9}, next_checkpoint=None,
            checkpoint_countdown=None, countdown_source=None, countdown_target=None,
            checkpoint_condition="该检查点无倒计时",
        )
        self.api.publish_runtime({"frame_consistent": True, "state": 2,
                                  "enemies": [enemy], "characters": []})

        route = self.api._snapshots["enemies"]["items"][0]["routeIntent"]
        self.assertEqual(route["route"], {
            "source": "runtime", "index": None, "display": "运行时动态路线",
        })
        self.assertEqual(route["nextWaypoint"], {"row": 4, "col": 9})
        self.assertIsNone(route["nextCheckpoint"])
        self.assertEqual(route["condition"], "该检查点无倒计时")

    def test_disabled_route_intent_never_leaks_previous_projection(self):
        enemy = SimpleNamespace(
            eid="enemy-1", route_intent_enabled=False,
            route_intent_status="disabled", intent_end={"row": 1, "col": 10},
            route_source="main", intent_route_index=0,
            route_display="主 #1（A1 → F10）", next_waypoint={"row": 2, "col": 9},
            next_checkpoint={"index": 0, "type": 0}, checkpoint_countdown=12.0,
            countdown_source="local", countdown_target=12.0,
            checkpoint_condition="stale", addr=0x123456,
        )
        self.api.publish_runtime({"frame_consistent": True, "state": 2,
                                  "enemies": [enemy], "characters": []})
        route = self.api._snapshots["enemies"]["items"][0]["routeIntent"]
        self.assertEqual(route["status"], "disabled")
        self.assertFalse(route["enabled"])
        for key in ("endPosition", "route", "nextWaypoint", "nextCheckpoint",
                    "countdown", "countdownSource", "countdownTarget", "condition"):
            self.assertIsNone(route[key])

    def test_quality_uses_nested_io_metrics(self):
        self.api.publish_runtime({
            "frame_consistent": True, "state": 2, "enemies": [], "characters": [],
            "io_metrics": {"io_ms": 12.5},
        })

        self.assertEqual(self.api._snapshots["quality"]["ioMs"], 12.5)

    def test_rng_payload_excludes_process_and_address_fields(self):
        engine = {
            "id": 1, "role": "imp", "history": [0.1], "predictions": [0.2],
            "status": "engine=0x7991c196b000",
            "obj": "0x1234", "array": "0x5678", "process": "0x9999",
        }
        self.api.publish_rng({
            "status": "BattleController=0x7994bd87d5e8", "process": "0x1111", "via": "pointer-chain",
            "engines": [engine], "selected": engine, "selected_id": 1,
            "by_role": {"imp": engine},
        })

        payload = self.api._snapshots["rng"]
        self.assertEqual(payload["by_role"]["imp"]["history"], [0.1])
        self.assertEqual(payload["selected"]["predictions"], [0.2])
        self.assertNotIn("process", json.dumps(payload))
        self.assertNotIn("via", json.dumps(payload))
        self.assertNotIn("obj", json.dumps(payload))
        self.assertNotIn("array", json.dumps(payload))
        self.assertNotIn("0x7994bd87d5e8", json.dumps(payload))
        self.assertNotIn("0x7991c196b000", json.dumps(payload))
        self.assertIn("[redacted-address]", payload["status"])

    def test_rng_payload_redacts_default_runtime_object_representation(self):
        engine = {"id": 1, "role": "imp", "label": object()}
        self.api.publish_rng({"status": "ok", "selected": engine, "by_role": {"imp": engine}})

        self.assertNotIn("0x", json.dumps(self.api._snapshots["rng"]))

    def test_sequence_is_independent_for_each_client(self):
        async def scenario():
            async with websockets.connect(
                    f"ws://127.0.0.1:{self.api.port}/v1/game") as first, \
                    websockets.connect(
                    f"ws://127.0.0.1:{self.api.port}/v1/game") as second:
                first_ready = json.loads(await first.recv())
                second_ready = json.loads(await second.recv())
                command = json.dumps({
                    "type": "subscribe", "topics": {"battle": {"rateHz": 60}},
                })
                await first.send(command)
                await second.send(command)
                first_sub = json.loads(await first.recv())
                second_sub = json.loads(await second.recv())
                self.api.publish_timer({
                    "connected": True, "game_time": 1.0, "frame_count": 30,
                })
                first_update = json.loads(await first.recv())
                second_update = json.loads(await second.recv())
                self.assertEqual([
                    first_ready["sequence"], first_sub["sequence"],
                    first_update["sequence"],
                ], [1, 2, 3])
                self.assertEqual([
                    second_ready["sequence"], second_sub["sequence"],
                    second_update["sequence"],
                ], [1, 2, 3])

        asyncio.run(scenario())

    def test_begin_session_rotates_id_and_clears_previous_battle_topics(self):
        from backend.app.services.websocket_api import _Client

        self.api.publish_runtime({
            "frame_consistent": True, "state": 2,
            "enemies": [], "characters": [],
        })
        client = _Client(websocket=object(), kind="game")
        client.last_sent["battle"] = time.monotonic()
        with self.api._lock:
            self.api._clients.add(client)
        before = self.api._session_id
        after = self.api.begin_session()
        self.assertNotEqual(after, before)
        self.assertNotIn("enemies", self.api._snapshots)
        self.assertNotIn("characters", self.api._snapshots)
        self.assertEqual(self.api.status_snapshot()["resyncCount"], 1)
        self.assertEqual(client.last_sent, {})
        with self.api._lock:
            self.api._clients.discard(client)

    def test_ops_endpoint_cannot_request_deploy_history(self):
        async def scenario():
            async with websockets.connect(
                    f"ws://127.0.0.1:{self.api.port}/v1/ops") as websocket:
                await websocket.recv()
                await websocket.send(json.dumps({"type": "deploy.get_history"}))
                message = json.loads(await websocket.recv())
                self.assertEqual(message["type"], "error")
                self.assertEqual(message["data"]["code"], "ENDPOINT_FORBIDDEN")

        asyncio.run(scenario())

    def test_game_endpoint_can_request_deploy_history_without_subscription(self):
        async def scenario():
            self.api.publish_deploy(
                [{"op": 0}], {"stageId": "test"}, [], [])
            async with websockets.connect(
                    f"ws://127.0.0.1:{self.api.port}/v1/game") as websocket:
                await websocket.recv()
                await websocket.send(json.dumps({"type": "deploy.get_history"}))
                message = json.loads(await websocket.recv())
                self.assertEqual(message["type"], "deploy.updated")
                self.assertEqual(message["data"]["events"], [{"op": 0}])

        asyncio.run(scenario())

    def test_non_object_command_and_invalid_unsubscribe_return_errors(self):
        async def scenario():
            async with websockets.connect(
                    f"ws://127.0.0.1:{self.api.port}/v1/game") as websocket:
                await websocket.recv()
                await websocket.send("[]")
                first = json.loads(await websocket.recv())
                self.assertEqual(first["data"]["code"], "INVALID_COMMAND")
                await websocket.send(json.dumps({
                    "type": "unsubscribe", "topics": "battle",
                }))
                second = json.loads(await websocket.recv())
                self.assertEqual(second["data"]["code"], "INVALID_UNSUBSCRIBE")

        asyncio.run(scenario())

    def test_detail_requests_preserve_selected_scope_and_cap_all_sampling(self):
        from backend.app.services.websocket_api import _Client

        selected = _Client(websocket=object(), kind="game")
        selected.subscriptions["enemy_detail"] = {
            "scope": "selected", "ids": ["enemy-2"], "rateHz": 60.0,
        }
        all_units = _Client(websocket=object(), kind="game")
        all_units.subscriptions["character_detail"] = {
            "scope": "all", "rateHz": 60.0,
        }
        with self.api._lock:
            self.api._clients.update((selected, all_units))
        requests = self.api.detail_requests()
        self.assertEqual(requests["enemy_detail"]["ids"], {"enemy-2"})
        self.assertFalse(requests["enemy_detail"]["scopeAll"])
        self.assertEqual(requests["enemy_detail"]["rateHz"], 60.0)
        self.assertTrue(requests["character_detail"]["scopeAll"])
        self.assertEqual(requests["character_detail"]["rateHz"], 5.0)
        with self.api._lock:
            self.api._clients.difference_update((selected, all_units))

    def test_stop_timeout_keeps_running_thread_reference(self):
        class ThreadProbe:
            def __init__(self):
                self.join_calls = []

            def join(self, timeout=None):
                self.join_calls.append(timeout)

            def is_alive(self):
                return True

        self.api.stop()
        probe = ThreadProbe()
        self.api._thread = probe
        self.api._bound_port = 8765
        self.assertFalse(self.api.stop(timeout=0))
        self.assertIs(self.api._thread, probe)
        self.assertEqual(self.api.port, 8765)
        self.api._thread = None
        self.api._bound_port = 0

    def test_safe_redacts_address_suffixes_and_non_finite_numbers(self):
        from backend.app.services.websocket_api import _safe

        payload = _safe({
            "time_address": "0x12345678", "nativePointer": "0x87654321",
            "value": float("nan"),
        })
        self.assertNotIn("time_address", payload)
        self.assertNotIn("nativePointer", payload)
        self.assertIsNone(payload["value"])
