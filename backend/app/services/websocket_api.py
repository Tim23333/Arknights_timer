"""本机 WebSocket 游戏与运维数据服务。

网络线程只消费主程序提交的不可变 JSON 快照，绝不直接访问 Qt 或游戏内存。
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


HOST = "127.0.0.1"
PORT = 8765
SCHEMA_VERSION = 1

# The public protocol must never reveal addresses copied from scanner diagnostics.
# Four hexadecimal digits keeps semantic labels such as ``0x0`` intact while
# covering the 32-bit and 64-bit addresses emitted by the game readers.
_INTERNAL_ADDRESS_PATTERN = re.compile(
    r"(?<![0-9A-Za-z])0x[0-9a-fA-F]{4,}(?![0-9A-Za-z])")
_INTERNAL_FIELD_NAMES = frozenset({"addr", "address", "pointer", "obj", "array", "process", "via"})

TOPIC_DEFAULTS: dict[str, float] = {
    "battle": 20.0, "stage": 2.0, "enemies": 10.0,
    "characters": 10.0, "enemy_detail": 2.0,
    "character_detail": 2.0, "deploy": 4.0, "rng": 2.0,
    "quality": 2.0, "ops.heartbeat": 0.5,
}
TOPIC_LIMITS: dict[str, tuple[float, float]] = {
    "battle": (1.0, 60.0), "stage": (0.2, 20.0),
    "enemies": (1.0, 20.0), "characters": (1.0, 20.0),
    "enemy_detail": (0.2, 60.0), "character_detail": (0.2, 60.0),
    "deploy": (1.0, 20.0), "rng": (1.0, 10.0),
    "quality": (0.5, 5.0), "ops.heartbeat": (0.2, 2.0),
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _safe(value: Any) -> Any:
    """将运行时值转换为公开 JSON，并移除内部字段与地址文本。

    所有 WebSocket 主题最终都会经过本函数。除了丢弃显式的指针字段，
    还会替换诊断字符串中嵌入的进程地址，避免 ``status`` 等人类可读字段
    绕过结构化白名单。
    """
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return _INTERNAL_ADDRESS_PATTERN.sub("[redacted-address]", value)
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()
                if str(key).lower() not in _INTERNAL_FIELD_NAMES
                and not str(key).lower().endswith(("_addr", "_ptr", "pointer"))}
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in value]
    # Default Python object representations include ``at 0x...``. Re-enter the
    # string branch so an unexpected runtime object cannot bypass redaction.
    return _safe(str(value))


def _entity_id(prefix: str, entity: Any, fallback: int) -> str:
    for name in ("roster_id", "unique_id", "eid", "cid"):
        value = getattr(entity, name, None)
        if value not in (None, "", 0):
            return f"{prefix}-{value}"
    return f"{prefix}-{fallback}"


def _enemy_basic(entity: Any, index: int) -> dict[str, Any]:
    position = getattr(entity, "position", None)
    if not isinstance(position, dict):
        position = {
            "x": getattr(entity, "pos_x", None),
            "y": getattr(entity, "pos_y", None),
        }
    return {
        "id": _entity_id("enemy", entity, index),
        "name": getattr(entity, "name", ""),
        "code": getattr(entity, "enemy_id", getattr(entity, "code", "")),
        "lifecycle": getattr(entity, "lifecycle", "active"),
        "alive": bool(getattr(entity, "alive", True)),
        "hp": getattr(entity, "hp", None),
        "maxHp": getattr(entity, "max_hp", None),
        "position": _safe(position),
        "action": _safe(getattr(entity, "action", {})),
        "shield": getattr(entity, "shield", None),
        "abnormalStatus": _safe(getattr(entity, "abnormal_status", [])),
    }


def _character_basic(entity: Any, index: int) -> dict[str, Any]:
    return {
        "id": _entity_id("character", entity, index),
        "characterId": getattr(entity, "cid", ""),
        "name": getattr(entity, "name", ""),
        "kind": "token" if getattr(entity, "is_token", False) else "operator",
        "alive": bool(getattr(entity, "alive", True)),
        "position": _safe(getattr(entity, "position", {})),
        "hp": getattr(entity, "hp", None), "maxHp": getattr(entity, "max_hp", None),
        "sp": getattr(entity, "sp", None), "maxSp": getattr(entity, "max_sp", None),
        "skill": _safe(getattr(entity, "skill", {})),
        "blockedCount": getattr(entity, "blocked_count", 0),
        "buffCount": getattr(entity, "buff_count", 0),
        "damageTotal": getattr(entity, "damage_total", 0),
        "healingTotal": getattr(entity, "healing_total", 0),
    }


def _detail(entity: Any, basic: dict[str, Any]) -> dict[str, Any]:
    """建立详情白名单；所有指针/地址字段均在此边界被排除。"""
    return {
        **basic,
        "attributes": _safe(getattr(entity, "attributes", {})),
        "rawAttributes": _safe(getattr(entity, "raw_attributes", {})),
        "buffs": _safe(getattr(entity, "buffs", [])),
        "globalBuffs": _safe(getattr(entity, "global_buffs", [])),
        "skills": _safe(getattr(entity, "skills_detail", getattr(entity, "skills", []))),
        "talents": _safe(getattr(entity, "talents", [])),
        "specialShield": _safe(getattr(entity, "special_shield", None)),
    }


def _rng_engine(snapshot: Any) -> dict[str, Any] | None:
    """筛选 RNG 引擎的公开状态，明确排除进程地址与原始容器指针。"""
    if not isinstance(snapshot, dict):
        return None
    public_fields = (
        "id", "role", "kind", "label", "status", "total", "cursor", "cursor2",
        "history", "predictions", "rate", "activity", "paired", "rawOnly",
    )
    return {name: _safe(snapshot.get(name)) for name in public_fields if name in snapshot}


def _rng_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    """构造稳定的 RNG 公开协议，不透传内部进程与地址字段。"""
    by_role = snapshot.get("by_role")
    safe_roles = {
        str(role): public
        for role, engine in (by_role.items() if isinstance(by_role, dict) else ())
        if (public := _rng_engine(engine)) is not None
    }
    return {
        "status": _safe(snapshot.get("status")),
        "selected": _rng_engine(snapshot.get("selected")),
        "selected_id": _safe(snapshot.get("selected_id")),
        "by_role": safe_roles,
    }


@dataclass(eq=False)
class _Client:
    websocket: Any
    kind: str
    subscriptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_sent: dict[str, float] = field(default_factory=dict)
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=2))
    dropped: int = 0


class WebSocketApi:
    """管理本机版本化 WebSocket 协议及其发布快照。

    由 GUI/采样线程调用 ``publish_*``；网络生命周期及客户端背压完全封装在本类。
    """

    def __init__(
        self,
        enabled: bool,
        app_version: str,
        port: int = PORT,
        status_listener: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._enabled = bool(enabled)
        self._app_version = app_version
        self._port = int(port)
        self._bound_port = 0
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._clients: set[_Client] = set()
        self._snapshots: dict[str, Any] = {}
        self._session_id = f"session-{uuid.uuid4().hex}"
        self._sequence = 0
        self._started_at = time.monotonic()
        self._dropped = 0
        self._resyncs = 0
        self._error = ""
        self._status_listener = status_listener

    @property
    def port(self) -> int:
        with self._lock:
            return self._bound_port

    def start_if_enabled(self) -> None:
        if self._enabled:
            self._start()

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        with self._lock:
            if self._enabled == enabled:
                return
            self._enabled = enabled
        if enabled:
            self._start()
        else:
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(lambda: None)
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            self._bound_port = 0
            self._loop = None
            self._thread = None
        self._notify_status()

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = {"game": 0, "ops": 0}
            for client in self._clients:
                counts[client.kind] += 1
            return {
                "enabled": self._enabled,
                "state": "ready" if self._bound_port else ("stopped" if not self._enabled else "starting"),
                "port": self._bound_port,
                "error": self._error,
                "gameClients": counts["game"], "opsClients": counts["ops"],
                "droppedOutboundFrames": self._dropped, "resyncCount": self._resyncs,
            }

    def _ops_payload(self) -> dict[str, Any]:
        """构造可对外发送的运维状态；端口仅供本地 UI 读取，不进入协议。"""
        local = self.status_snapshot()
        with self._lock:
            available = set(self._snapshots)
        return {
            "service": {
                "state": local["state"], "enabled": local["enabled"],
                "appVersion": self._app_version, "protocolVersion": SCHEMA_VERSION,
                "uptimeSeconds": round(time.monotonic() - self._started_at, 3),
            },
            "capabilities": {
                "battle": "battle" in available, "enemies": "enemies" in available,
                "characters": "characters" in available, "deploy": "deploy" in available,
                "rng": "rng" in available,
            },
            "modules": {
                "timer": {"state": "ready" if "battle" in available else "unavailable"},
                "enemy": {"state": "streaming" if "enemies" in available else "unavailable"},
                "characters": {"state": "streaming" if "characters" in available else "unavailable"},
                "deploy": {"state": "ready" if "deploy" in available else "unavailable"},
                "rng": {"state": "ready" if "rng" in available else "unavailable"},
            },
            "metrics": {
                "gameClients": local["gameClients"], "opsClients": local["opsClients"],
                "droppedOutboundFrames": local["droppedOutboundFrames"],
                "resyncCount": local["resyncCount"],
            },
        }

    def detail_rate_hz(self) -> float:
        """返回当前客户端请求的最大详情采样频率；无订阅时为零。"""
        with self._lock:
            rates = [float(client.subscriptions[name]["rateHz"])
                     for client in self._clients
                     for name in ("enemy_detail", "character_detail")
                     if name in client.subscriptions]
        return max(rates, default=0.0)

    def publish_timer(self, cache: dict[str, Any]) -> None:
        timer = copy.deepcopy(cache)
        with self._lock:
            current_state = self._snapshots.get("battle", {}).get("state", "unknown")
        self._merge_battle({
            "state": "unavailable" if not timer.get("connected") else current_state,
            "gameTime": _safe(timer.get("game_time")),
            "fixedFrame": _safe(timer.get("frame_count")),
            "clockSource": _safe(timer.get("source")),
            "connected": bool(timer.get("connected")),
            "configured": bool(timer.get("configured")),
            "sampledAt": _safe(timer.get("last_refresh")),
            "message": _safe(timer.get("message")),
        })

    def publish_runtime(self, snapshot: dict[str, Any]) -> None:
        if not snapshot.get("frame_consistent", True):
            self._publish("quality", self._quality(snapshot))
            return
        enemies = [_enemy_basic(entity, index) for index, entity in enumerate(snapshot.get("enemies", ()), 1)]
        characters = [_character_basic(entity, index) for index, entity in enumerate(snapshot.get("characters", ()), 1)]
        self._merge_battle(self._battle(snapshot))
        self._publish("enemies", {"items": enemies})
        self._publish("characters", {"items": characters, "globalDamageSummary": _safe(snapshot.get("global_damage_summary", {}))})
        external_enemies = list(snapshot.get("external_enemy_details", ()))
        external_characters = list(snapshot.get("external_character_details", ()))
        live_enemy_basics = {getattr(entity, "addr", None): basic
                             for entity, basic in zip(snapshot.get("enemies", ()), enemies)}
        live_character_basics = {getattr(entity, "addr", None): basic
                                 for entity, basic in zip(snapshot.get("characters", ()), characters)}
        self._publish("enemy_detail", {"items": [
            _detail(entity, live_enemy_basics.get(getattr(entity, "addr", None), _enemy_basic(entity, index)))
            for index, entity in enumerate(external_enemies, 1)
        ], "loading": bool(snapshot.get("external_detail_loading"))})
        self._publish("character_detail", {"items": [
            _detail(entity, live_character_basics.get(getattr(entity, "addr", None), _character_basic(entity, index)))
            for index, entity in enumerate(external_characters, 1)
        ], "loading": bool(snapshot.get("external_detail_loading"))})
        self._publish("quality", self._quality(snapshot))

    def publish_deploy(self, events: list[Any], stage: dict[str, Any], squad: list[Any], journal: list[Any]) -> None:
        self._publish("stage", {"stage": _safe(stage), "squad": _safe(squad)})
        self._publish("deploy", {"events": _safe(events), "journal": _safe(journal)})

    def publish_rng(self, snapshot: dict[str, Any]) -> None:
        self._publish("rng", _rng_payload(snapshot))

    def _battle(self, snap: dict[str, Any]) -> dict[str, Any]:
        """构造敌我完整帧的补充字段，不覆盖计时器链的权威时钟。"""
        state_code = snap.get("state")
        state_names = {0: "idle", 1: "initializing", 2: "playing", 3: "finished"}
        return {"state": state_names.get(state_code, "unknown"), "stateCode": _safe(state_code),
                "speedLevel": _safe(snap.get("speed_level")),
                "timeScale": _safe(snap.get("time_scale")), "isPaused": bool(snap.get("paused_snapshot")),
                "frameConsistent": bool(snap.get("frame_consistent", True))}

    def _merge_battle(self, update: dict[str, Any]) -> None:
        """合并计时器与敌我帧，保证 battle 主题始终使用固定字段集合。"""
        empty = {
            "state": "unknown", "stateCode": None, "gameTime": None,
            "fixedFrame": None, "clockSource": None, "connected": False,
            "configured": False, "sampledAt": None, "message": "",
            "speedLevel": None, "timeScale": None, "isPaused": None,
            "frameConsistent": None,
        }
        with self._lock:
            merged = {**empty, **self._snapshots.get("battle", {}), **update}
        self._publish("battle", merged)

    def _quality(self, snap: dict[str, Any]) -> dict[str, Any]:
        io_metrics = snap.get("io_metrics")
        return {"sampleHz": _safe(snap.get("sample_hz")), "loopMs": _safe(snap.get("loop_ms")),
                "frameMs": _safe(snap.get("frame_ms")),
                "ioMs": _safe(io_metrics.get("io_ms") if isinstance(io_metrics, dict) else None),
                "frameConsistent": bool(snap.get("frame_consistent", True)),
                "pausedSnapshot": bool(snap.get("paused_snapshot")),
                "droppedOutboundFrames": self._dropped, "resyncCount": self._resyncs}

    def _publish(self, topic: str, data: Any) -> None:
        with self._lock:
            self._snapshots[topic] = data
            loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(lambda: asyncio.create_task(self._broadcast(topic)))

    def _start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._error = ""
            self._thread = threading.Thread(target=self._run, name="ak-websocket-api", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as exc:
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"
                self._bound_port = 0
            self._notify_status()

    async def _serve(self) -> None:
        import websockets

        self._loop = asyncio.get_running_loop()
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        try:
            async with websockets.serve(self._handler, HOST, self._port) as server:
                with self._lock:
                    self._bound_port = server.sockets[0].getsockname()[1]
                self._notify_status()
                while not self._stop.is_set():
                    await asyncio.sleep(0.1)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        await asyncio.gather(*(client.websocket.close(code=1001, reason="service stopped") for client in list(self._clients)), return_exceptions=True)

    async def _heartbeat_loop(self) -> None:
        """即使游戏未运行，也持续向运维客户端发送协商后的健康状态。"""
        while not self._stop.is_set():
            for client in list(self._clients):
                if client.kind == "ops":
                    await self._emit(client, "ops.heartbeat", self._ops_payload())
            await asyncio.sleep(0.1)

    async def _handler(self, websocket: Any) -> None:
        path = getattr(getattr(websocket, "request", None), "path", "")
        kind = "game" if path == "/v1/game" else "ops" if path == "/v1/ops" else ""
        if not kind:
            await websocket.close(code=1008, reason="unsupported endpoint")
            return
        client = _Client(websocket=websocket, kind=kind)
        if kind == "ops":
            client.subscriptions["ops.heartbeat"] = {"rateHz": TOPIC_DEFAULTS["ops.heartbeat"]}
        sender = asyncio.create_task(self._sender(client))
        try:
            initial = self._ops_payload() if kind == "ops" else self.status_snapshot()
            await self._queue(client, "ops.status" if kind == "ops" else "game.ready", initial)
            with self._lock:
                self._clients.add(client)
            async for raw in websocket:
                await self._command(client, raw)
        finally:
            sender.cancel()
            with self._lock:
                self._clients.discard(client)

    async def _command(self, client: _Client, raw: str) -> None:
        try:
            command = json.loads(raw)
        except (TypeError, ValueError):
            await self._queue(client, "error", {"code": "INVALID_JSON", "message": "消息必须是 JSON 对象。"})
            return
        if command.get("type") == "subscribe":
            topics = command.get("topics")
            if not isinstance(topics, dict):
                await self._queue(client, "error", {"code": "INVALID_SUBSCRIPTION", "message": "topics 必须是对象。"})
                return
            result: dict[str, Any] = {}
            for name, options in topics.items():
                if name not in TOPIC_DEFAULTS or (client.kind == "ops" and name != "ops.heartbeat"):
                    result[name] = {"error": "unsupported topic"}
                    continue
                options = {} if options is True else options
                if not isinstance(options, dict):
                    result[name] = {"error": "options must be an object"}
                    continue
                requested = options.get("rateHz", TOPIC_DEFAULTS[name])
                if not isinstance(requested, (int, float)):
                    result[name] = {"error": "rateHz must be a number"}
                    continue
                if name in {"enemy_detail", "character_detail"}:
                    scope = options.get("scope", "all")
                    if scope not in {"all", "selected"}:
                        result[name] = {"error": "scope must be all or selected"}
                        continue
                    if scope == "selected" and not isinstance(options.get("ids"), list):
                        result[name] = {"error": "selected scope requires an ids array"}
                        continue
                lower, upper = TOPIC_LIMITS[name]
                effective = min(upper, max(lower, float(requested)))
                client.subscriptions[name] = {**options, "rateHz": effective}
                result[name] = {"requestedRateHz": requested, "effectiveRateHz": effective}
                if name in self._snapshots:
                    await self._emit(client, name, self._snapshots[name], force=True)
            response: dict[str, Any] = {"topics": result}
            if isinstance(command.get("requestId"), str):
                response["requestId"] = command["requestId"]
            await self._queue(client, "subscription.updated", response)
            return
        if command.get("type") == "unsubscribe":
            for name in command.get("topics", []):
                client.subscriptions.pop(name, None)
            return
        if command.get("type") == "deploy.get_history":
            await self._emit(client, "deploy", self._snapshots.get("deploy", {"events": [], "journal": []}), force=True)
            return
        await self._queue(client, "error", {"code": "UNSUPPORTED_COMMAND", "message": "不支持的客户端命令。"})

    async def _broadcast(self, topic: str) -> None:
        data = self._snapshots.get(topic)
        if data is None:
            return
        for client in list(self._clients):
            await self._emit(client, topic, data)

    async def _emit(self, client: _Client, topic: str, data: Any, force: bool = False) -> None:
        options = client.subscriptions.get(topic)
        if options is None:
            return
        now = time.monotonic()
        rate = float(options["rateHz"])
        if not force and now - client.last_sent.get(topic, 0.0) < 1.0 / rate:
            return
        client.last_sent[topic] = now
        message_type = topic if topic == "ops.heartbeat" else f"{topic}.updated"
        await self._queue(client, message_type, self._topic_data(topic, data, options))

    @staticmethod
    def _topic_data(topic: str, data: Any, options: dict[str, Any]) -> Any:
        if topic not in {"enemy_detail", "character_detail"}:
            return data
        if options.get("scope", "all") == "all":
            return data
        requested_ids = options.get("ids", [])
        if not isinstance(requested_ids, list):
            return {**data, "items": []}
        selected = set(str(item) for item in requested_ids)
        return {**data, "items": [item for item in data.get("items", [])
                                   if item.get("id") in selected]}

    async def _queue(self, client: _Client, message_type: str, data: Any) -> None:
        with self._lock:
            self._sequence += 1
            message = json.dumps({"type": message_type, "schemaVersion": SCHEMA_VERSION,
                                  "sessionId": self._session_id, "sequence": self._sequence,
                                  "emittedAt": _now(), "data": data}, ensure_ascii=False, separators=(",", ":"))
        if client.queue.full():
            try:
                client.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            client.dropped += 1
            with self._lock:
                self._dropped += 1
        client.queue.put_nowait(message)

    async def _sender(self, client: _Client) -> None:
        while True:
            await client.websocket.send(await client.queue.get())

    def _notify_status(self) -> None:
        """向宿主报告服务生命周期变化；监听方负责切换到自己的线程。"""
        listener = self._status_listener
        if listener is None:
            return
        try:
            listener(self.status_snapshot())
        except Exception:
            pass
