"""手工集成测试：以独立客户端连续观察本机 WebSocket 60 秒。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time

import websockets


GAME_TOPICS = {
    "battle": {"rateHz": 60},
    "stage": {"rateHz": 20},
    "enemies": {"rateHz": 20},
    "characters": {"rateHz": 20},
    "enemy_detail": {"scope": "all", "rateHz": 60},
    "character_detail": {"scope": "all", "rateHz": 60},
    "deploy": {"rateHz": 20, "includeHistory": True},
    "rng": {"rateHz": 10},
    "quality": {"rateHz": 5},
}


async def main() -> None:
    game = await websockets.connect("ws://127.0.0.1:8765/v1/game")
    ops = await websockets.connect("ws://127.0.0.1:8765/v1/ops")
    await game.recv()
    await ops.recv()
    await game.send(json.dumps({
        "type": "subscribe",
        "requestId": "full-60-second-simulation",
        "topics": GAME_TOPICS,
    }))
    await ops.send(json.dumps({
        "type": "subscribe",
        "topics": {"ops.heartbeat": {"rateHz": 2}},
    }))

    stats: dict[str, dict] = {}
    sequences = {"game": [], "ops": []}
    started = time.monotonic()
    while time.monotonic() - started < 60:
        game_task = asyncio.create_task(game.recv())
        ops_task = asyncio.create_task(ops.recv())
        done, pending = await asyncio.wait(
            {game_task, ops_task}, timeout=2, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            try:
                message = json.loads(task.result())
            except Exception:
                continue
            source = "game" if task is game_task else "ops"
            name = message.get("type", "unknown")
            entry = stats.setdefault(name, {
                "count": 0, "fields": set(), "fingerprints": set(),
                "itemCounts": [], "nonEmptyItemMessages": 0,
            })
            data = message.get("data")
            entry["count"] += 1
            if isinstance(data, dict):
                entry["fields"].update(data.keys())
                encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
                entry["fingerprints"].add(hashlib.sha256(encoded.encode()).hexdigest())
                items = data.get("items")
                if isinstance(items, list):
                    entry["itemCounts"].append(len(items))
                    entry["nonEmptyItemMessages"] += bool(items)
            if isinstance(message.get("sequence"), int):
                sequences[source].append(message["sequence"])

    result = {}
    for name, entry in sorted(stats.items()):
        counts = entry["itemCounts"]
        result[name] = {
            "count": entry["count"],
            "fields": sorted(entry["fields"]),
            "distinctPayloads": len(entry["fingerprints"]),
            "itemCountMinMax": [min(counts), max(counts)] if counts else None,
            "nonEmptyItemMessages": entry["nonEmptyItemMessages"],
        }
    sequence_result = {
        name: {
            "count": len(values),
            "strictlyIncreasing": all(b > a for a, b in zip(values, values[1:])),
            "firstLast": [values[0], values[-1]] if values else None,
        }
        for name, values in sequences.items()
    }
    print(json.dumps({
        "durationSeconds": round(time.monotonic() - started, 2),
        "messages": result,
        "sequences": sequence_result,
    }, ensure_ascii=False))
    await game.close()
    await ops.close()


if __name__ == "__main__":
    asyncio.run(main())
