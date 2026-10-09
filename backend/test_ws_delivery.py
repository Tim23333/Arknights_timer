"""Delivery boundary regressions; synthetic payloads never touch game memory."""
import asyncio
import json
import time

import pytest
import websockets

from backend.app.field_policy import FIELD_REGISTRY, PolicyStore
from backend.app.services.websocket_api import TOPIC_DEFAULTS, WebSocketApi, _Client


def test_all_static_topics_and_subscription_ack_reach_external_client():
    # ROOT CAUSE: the two-slot frame queue discarded nine initial replies before
    # the sender ran. A static topic could then remain missing indefinitely.
    api = WebSocketApi(True, "regression", port=0)
    topics = set(TOPIC_DEFAULTS) - {"ops.heartbeat"}
    for topic in topics:
        api._publish(topic, {"items": [], "meta": {"sourceFrame": 0}})
    api.start_if_enabled()
    try:
        deadline = time.monotonic() + 3
        while not api.port and time.monotonic() < deadline:
            time.sleep(0.01)
        assert api.port

        async def scenario():
            async with websockets.connect(f"ws://127.0.0.1:{api.port}/v2/game") as ws:
                assert json.loads(await ws.recv())["type"] == "game.ready"
                await ws.send(json.dumps({"type": "subscribe", "requestId": "all",
                                          "topics": dict.fromkeys(topics, True)}))
                messages = [json.loads(await asyncio.wait_for(ws.recv(), 2))
                            for _ in range(len(topics) + 1)]
                assert {m["type"] for m in messages} == {
                    *(f"{topic}.updated" for topic in topics), "subscription.updated"}
                assert messages[-1]["data"]["requestId"] == "all"
                assert [m["sequence"] for m in messages] == list(range(2, 13))
        asyncio.run(scenario())
    finally:
        api.stop()


@pytest.mark.parametrize("domain", ["enemy_detail", "character_detail"])
def test_generic_detail_hook_entity_shape_and_three_policy_gates(domain):
    store = PolicyStore()
    api = WebSocketApi(False, "regression", policy_provider=store.snapshot)
    field = f"{domain}.buffs"
    api.publish_fields(domain, {field: []}, entity_id="unit", source_frame=0)
    assert api._snapshots[domain]["items"] == [{"id": "unit", "buffs": []}]
    assert "buffs" not in api._snapshots[domain]
    store.commit({field: {"publish": False}})
    api.policy_changed()
    assert "buffs" not in api._snapshots[domain]["items"][0]
    assert api.local_snapshot()[domain]["items"][0]["buffs"] == []
    store.commit({field: {"display": False}})
    api.policy_changed()
    assert "buffs" not in api.local_snapshot()[domain]["items"][0]
    store.commit({field: {"collect": False, "display": True, "publish": True}})
    api.policy_changed()
    api.publish_fields(domain, {field: ["must not escape"]}, entity_id="unit")
    assert "buffs" not in api._snapshots[domain]["items"][0]
    assert "buffs" not in api.local_snapshot()[domain]["items"][0]


@pytest.mark.parametrize("domain", ["enemy_detail", "character_detail"])
def test_detail_hook_rejects_missing_identity_and_invalid_frame(domain):
    api = WebSocketApi(False, "regression")
    with pytest.raises(ValueError):
        api.publish_fields(domain, {f"{domain}.buffs": []})
    api.publish_fields(domain, {f"{domain}.buffs": []}, entity_id="unit",
                       frame_consistent=False)
    assert api._snapshots[domain]["items"] == []


def test_frame_coalescing_is_bounded_without_dropping_control_replies():
    api = WebSocketApi(False, "regression")
    client = _Client(None, "game")

    async def scenario():
        await api._queue(client, "subscription.updated", {"requestId": "keep"})
        for frame in range(100):
            for topic in ("battle", "quality"):
                await api._queue(client, f"{topic}.updated", {"meta": {"sourceFrame": frame}},
                                 reliable=False)
        assert client.queue.qsize() == 1
        assert len(client.pending) == 2
        assert client.pending["battle.updated"]["data"]["meta"]["sourceFrame"] == 99
        assert client.queue.get_nowait()["data"]["requestId"] == "keep"
        assert client.dropped == 198
    asyncio.run(scenario())


def test_reliable_overflow_explicitly_closes_only_the_slow_client():
    api = WebSocketApi(False, "regression")
    closed = []

    class Socket:
        async def close(self, **kwargs):
            closed.append(kwargs)
    client = _Client(Socket(), "game")

    async def scenario():
        for index in range(client.queue.maxsize + 5):
            await api._queue(client, "error", {"index": index})
        assert client.queue.qsize() == client.queue.maxsize
        assert len(closed) == 1
        assert closed[0]["code"] == 1013
        assert client.closing
        assert client.dropped == 0
    asyncio.run(scenario())


def test_sender_discards_old_session_and_policy_from_both_channels():
    store = PolicyStore()
    api = WebSocketApi(False, "regression", policy_provider=store.snapshot)

    async def scenario():
        sent = []
        done = asyncio.Event()

        class Socket:
            async def send(self, message):
                sent.append(json.loads(message))
                done.set()
        client = _Client(Socket(), "game")
        await api._queue(client, "enemies.updated", {"items": ["old session"]})
        api.begin_session()
        await api._queue(client, "battle.updated", {"meta": {"policyGeneration": 0}}, reliable=False)
        store.commit({"battle.gameTime": {"publish": False}})
        await api._queue(client, "error", {"code": "fresh"})
        sender = asyncio.create_task(api._sender(client))
        try:
            await asyncio.wait_for(done.wait(), 1)
            assert len(sent) == 1
            assert sent[0]["data"]["code"] == "fresh"
            assert sent[0]["sequence"] == 1
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
    asyncio.run(scenario())


def test_blocked_sender_preserves_replies_and_delivers_latest_per_topic():
    api = WebSocketApi(False, "regression")

    async def scenario():
        entered, release, complete = asyncio.Event(), asyncio.Event(), asyncio.Event()
        sent = []

        class Socket:
            async def send(self, message):
                if not sent:
                    entered.set()
                    await release.wait()
                sent.append(json.loads(message))
                if len(sent) == 4:
                    complete.set()
        client = _Client(Socket(), "game")
        await api._queue(client, "game.ready", {})
        sender = asyncio.create_task(api._sender(client))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            for frame in range(100):
                for topic in ("battle", "quality"):
                    await api._queue(client, f"{topic}.updated", {"meta": {"sourceFrame": frame}}, reliable=False)
            await api._queue(client, "deploy.updated", {"events": ["complete history"]})
            release.set()
            await asyncio.wait_for(complete.wait(), 1)
            assert [message["type"] for message in sent] == ["game.ready", "deploy.updated", "battle.updated", "quality.updated"]
            assert [message["sequence"] for message in sent] == [1, 2, 3, 4]
            assert sent[1]["data"]["events"] == ["complete history"]
            assert sent[2]["data"]["meta"]["sourceFrame"] == 99
            assert sent[3]["data"]["meta"]["sourceFrame"] == 99
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
    asyncio.run(scenario())


@pytest.mark.parametrize("domain", ["enemy_detail", "character_detail"])
def test_all_generic_detail_leaves_reach_real_socket_and_cannot_leak_at_root(domain):
    store = PolicyStore()
    api = WebSocketApi(True, "regression", port=0, policy_provider=store.snapshot)
    fields = {spec.id: [] for spec in FIELD_REGISTRY.values() if spec.domain == domain}
    api.publish_fields(domain, fields, entity_id="synthetic-unit", source_frame=0)
    api.start_if_enabled()
    try:
        deadline = time.monotonic() + 3
        while not api.port and time.monotonic() < deadline:
            time.sleep(0.01)
        assert api.port

        async def scenario():
            async with websockets.connect(f"ws://127.0.0.1:{api.port}/v2/game") as ws:
                await ws.recv()
                await ws.send(json.dumps({"type": "subscribe", "topics": {
                    domain: {"scope": "selected", "ids": ["synthetic-unit"]}}}))
                data = json.loads(await asyncio.wait_for(ws.recv(), 2))["data"]
                assert data["items"][0]["id"] == "synthetic-unit"
                for field in fields:
                    leaf = FIELD_REGISTRY[field].paths[0]
                    assert data["items"][0][leaf] == []
                    assert leaf not in data
                assert data["meta"]["sourceFrame"] == 0
                assert json.loads(await ws.recv())["type"] == "subscription.updated"
        asyncio.run(scenario())
        # Even a malformed direct producer cannot relocate detail fields to
        # the root to bypass disabled publication.
        store.commit({field: {"publish": False} for field in fields})
        api.policy_changed()
        api._publish(domain, {"buffs": ["malformed"], "items": [{"id": "synthetic-unit", "buffs": []}]})
        assert "buffs" not in api._snapshots[domain]
        assert "buffs" not in api._snapshots[domain]["items"][0]
    finally:
        api.stop()


def test_detail_resubscribe_clears_old_scope_pending_after_ack():
    api = WebSocketApi(False, "regression")
    client = _Client(None, "game")

    async def scenario():
        await api._queue(client, "enemy_detail.updated", {"items": [{"id": "old"}]}, reliable=False)
        await api._command(client, json.dumps({"type": "subscribe", "topics": {
            "enemy_detail": {"scope": "selected", "ids": ["new"]}}}))
        assert not client.pending
        assert client.queue.get_nowait()["type"] == "subscription.updated"
        with pytest.raises(ValueError):
            await api._queue(client, "unregistered.updated", {}, reliable=False)
    asyncio.run(scenario())
