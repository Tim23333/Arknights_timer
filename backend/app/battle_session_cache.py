"""单局战斗的有界最终快照缓存。

缓存只覆盖同一局的最新完整状态，不保存逐帧录像：敌我运行时快照一份、
关卡计划一份、操作记录一份，以及每条 RNG 最多由追踪器提供的历史上限。
战斗结束或地址失效后会冻结最后完整运行时快照，供各导出入口继续使用。
"""
from __future__ import annotations

import math
import time
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def json_safe(value: Any, _seen: set[int] | None = None, _depth: int = 0) -> Any:
    """把 dataclass、``__slots__`` 模型和容器转换为可写入 JSON 的副本。"""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, bytes):
        return value.hex()
    if _depth >= 20:
        return str(value)

    seen = _seen if _seen is not None else set()
    object_id = id(value)
    if object_id in seen:
        return "<循环引用>"

    if isinstance(value, dict):
        seen.add(object_id)
        try:
            return {
                str(key): json_safe(item, seen, _depth + 1)
                for key, item in value.items()
            }
        finally:
            seen.discard(object_id)
    if isinstance(value, (list, tuple, set)):
        seen.add(object_id)
        try:
            return [json_safe(item, seen, _depth + 1) for item in value]
        finally:
            seen.discard(object_id)
    if is_dataclass(value) and not isinstance(value, type):
        seen.add(object_id)
        try:
            return {
                field.name: json_safe(getattr(value, field.name), seen, _depth + 1)
                for field in fields(value)
            }
        finally:
            seen.discard(object_id)

    slot_names: list[str] = []
    for cls in type(value).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        slot_names.extend(slots)
    if slot_names:
        seen.add(object_id)
        try:
            return {
                name: json_safe(getattr(value, name), seen, _depth + 1)
                for name in dict.fromkeys(slot_names)
                if not name.startswith("_") and hasattr(value, name)
            }
        finally:
            seen.discard(object_id)
    if hasattr(value, "__dict__"):
        seen.add(object_id)
        try:
            return {
                str(key): json_safe(item, seen, _depth + 1)
                for key, item in vars(value).items()
                if not str(key).startswith("_")
            }
        finally:
            seen.discard(object_id)
    return str(value)


def _stage_identity(info: dict | None) -> str:
    info = info or {}
    return str(info.get("stageId") or info.get("levelId") or "")


def _rng_copy(data: dict) -> dict:
    """RNG 缓存沿用公开导出字段，主动去掉内部 raw 整数。"""
    copied = {
        key: json_safe(data.get(key))
        for key in (
            "id", "label", "role", "kind", "status", "cursor", "cursor2",
            "total", "rate", "activity",
        )
        if key in data
    }
    copied["history"] = [
        {key: json_safe(item.get(key)) for key in ("seq", "frac", "ts")
         if item.get(key) is not None}
        for item in (data.get("history") or [])
    ]
    copied["predictions"] = [
        {key: json_safe(item.get(key)) for key in ("n", "frac")
         if item.get(key) is not None}
        for item in (data.get("predictions") or [])
    ]
    return copied


class BattleSessionCache:
    """保存当前/最近一局最后完整数据的内存缓存。"""

    PLAYING = 2
    FINISHED = 3

    def __init__(self, app_version: str = "") -> None:
        self.app_version = app_version
        self._serial = 0
        self._reset()

    def _reset(self, stage_info: dict | None = None) -> None:
        self._serial += 1
        now = _iso_now()
        self._session_id = f"{int(time.time() * 1000)}-{self._serial}"
        self._started_at = now
        self._updated_at = now
        self._finalized_at = ""
        self._final_reason = ""
        self._finalized = False
        self._saw_playing = False
        self._last_frame: int | None = None
        self._last_play_time: float | None = None
        self._stage_info = json_safe(stage_info or {})
        self._pending_stage_info: dict = {}
        self._pending_stage_export: dict = {}
        self._stage_export: dict = {}
        self._battle: dict = {}
        self._runtime_ref: dict | None = None
        self._frozen_runtime: dict | None = None
        self._deploy = {
            "stage": {}, "battle": {}, "squad": [],
            "liveEvents": [], "journalEvents": [],
        }
        self._rng: dict[str, dict] = {}
        self._rng_signatures: dict[str, tuple] = {}
        self._pending_rng: dict[str, dict] = {}
        self._blocked_rng: dict[str, tuple[Any, Any]] = {}

    @staticmethod
    def _runtime_payload(snapshot: dict | None) -> dict:
        if not snapshot:
            return {}
        battle_keys = (
            "state", "speed_level", "time_scale", "play_time", "scheduler_time",
            "fixed_frame", "frame_duration", "frame_start", "frame_end",
            "frame_consistent", "paused_snapshot", "pause_consistent",
            "on_field_count", "planned_count",
        )
        read_keys = (
            "read_mode", "read_backend", "memsrv_version", "strict_60hz",
            "full_60hz", "sample_hz", "loop_ms", "frame_ms",
            "character_frame_ms", "io_metrics",
        )
        return {
            "battle": {
                key: json_safe(snapshot.get(key)) for key in battle_keys
                if key in snapshot
            },
            "read": {
                key: json_safe(snapshot.get(key)) for key in read_keys
                if key in snapshot
            },
            "enemies": json_safe(snapshot.get("enemies") or []),
            "characters": json_safe(snapshot.get("characters") or []),
            "characterHistory": json_safe(
                snapshot.get("character_stats_history") or []),
            "globalDamageSummary": json_safe(
                snapshot.get("global_damage_summary")),
        }

    def _touch(self) -> None:
        self._updated_at = _iso_now()

    def _has_payload(self) -> bool:
        return bool(
            self._runtime_ref or self._frozen_runtime or self._stage_export
            or self._stage_info or self._deploy["stage"]
            or self._deploy["liveEvents"] or self._deploy["journalEvents"]
            or self._rng
        )

    def _should_start_new(self, state: int, frame: int | None,
                          play_time: float | None, stage_info: dict | None) -> bool:
        if not self._has_payload() or state != self.PLAYING:
            return False
        pending_id = _stage_identity(self._pending_stage_info)
        stage_id = _stage_identity(stage_info)
        old_stage_id = _stage_identity(self._stage_info or self._deploy["stage"])
        if ((pending_id and old_stage_id and pending_id != old_stage_id)
                or (stage_id and old_stage_id and stage_id != old_stage_id)):
            return True
        if self._finalized and self._final_reason == "battle_finished":
            return True
        if (frame is not None and self._last_frame is not None
                and frame + 5 < self._last_frame):
            return True
        if (frame is None and play_time is not None
                and self._last_play_time is not None
                and (play_time + 3.0 < self._last_play_time
                     or (self._finalized and play_time <= 1.0
                         and self._last_play_time >= 1.5))):
            return True
        return False

    def observe_runtime(self, snapshot: dict,
                        stage_info: dict | None = None,
                        stage_export: dict | None = None) -> None:
        """接收一份敌我完整帧；结束帧不会覆盖最后一份 PLAYING 数据。"""
        if not snapshot:
            return
        state = int(snapshot.get("state", -1) or 0)
        frame_value = snapshot.get("fixed_frame")
        frame = int(frame_value) if isinstance(frame_value, (int, float)) else None
        play_value = snapshot.get("play_time")
        play_time = float(play_value) if isinstance(play_value, (int, float)) else None
        if self._should_start_new(state, frame, play_time, stage_info):
            new_stage = stage_info or self._pending_stage_info
            pending_export = self._pending_stage_export
            pending_rng = self._pending_rng
            previous_rng = {
                role: (data.get("id"), data.get("total"))
                for role, data in self._rng.items()
            }
            self._reset(new_stage)
            self._blocked_rng = previous_rng
            if pending_export:
                self._stage_export = pending_export
            if pending_rng:
                self._rng.update(pending_rng)
                for role in pending_rng:
                    self._blocked_rng.pop(role, None)
        elif self._finalized and state == self.PLAYING \
                and self._final_reason == "battle_finished":
            # 未能证明是新一局时，FINISHED 之后残留/回跳的 PLAYING 读数
            # 不得解冻并覆盖已经封存的最终状态。
            return

        was_finalized = self._finalized

        if stage_info:
            self._stage_info = json_safe(stage_info)
        elif self._pending_stage_info and not self._stage_info:
            self._stage_info = self._pending_stage_info
        if stage_export:
            self._stage_export = json_safe(stage_export)
        self._battle.update({
            key: json_safe(snapshot.get(key))
            for key in ("state", "speed_level", "time_scale", "play_time",
                        "scheduler_time", "fixed_frame", "frame_duration")
            if key in snapshot
        })

        if (snapshot.get("ok") and state in (1, self.PLAYING)
                and snapshot.get("frame_consistent", True)):
            self._runtime_ref = snapshot
            self._frozen_runtime = None
            if state == self.PLAYING:
                self._saw_playing = True
                self._last_frame = frame if frame is not None else self._last_frame
                self._last_play_time = (
                    play_time if play_time is not None else self._last_play_time)
                # 地址瞬断后恢复到同一局时继续更新；真正 FINISHED 后再次 PLAYING
                # 已在 _should_start_new 中开启新会话。
                if was_finalized and self._final_reason != "battle_finished":
                    if self._pending_stage_info:
                        self._stage_info = self._pending_stage_info
                    if self._pending_stage_export:
                        self._stage_export = self._pending_stage_export
                    self._pending_stage_info = {}
                    self._pending_stage_export = {}
                self._finalized = False
                self._finalized_at = ""
                self._final_reason = ""
        self._touch()
        if state == self.FINISHED and self._saw_playing:
            self.finalize("battle_finished")

    def observe_stage(self, stage_info: dict | None = None,
                      stage_export: dict | None = None) -> None:
        if self._finalized and self._final_reason == "battle_finished":
            if stage_info:
                self._pending_stage_info = json_safe(stage_info)
            if stage_export:
                self._pending_stage_export = json_safe(stage_export)
            self._touch()
            return
        if stage_info:
            info = json_safe(stage_info)
            self._stage_info = info
        if stage_export:
            self._stage_export = json_safe(stage_export)
        self._touch()

    def observe_deploy(self, events: list | None = None,
                       battle: dict | None = None,
                       stage_info: dict | None = None,
                       journal: list | None = None,
                       squad: list | None = None) -> None:
        battle = battle or {}
        state_value = battle.get("state")
        state = int(state_value) if isinstance(state_value, (int, float)) else -1
        play_value = battle.get("playTime")
        play_time = float(play_value) if isinstance(play_value, (int, float)) else None
        if self._should_start_new(state, None, play_time, stage_info):
            new_stage = stage_info or self._pending_stage_info
            pending_export = self._pending_stage_export
            pending_rng = self._pending_rng
            previous_rng = {
                role: (data.get("id"), data.get("total"))
                for role, data in self._rng.items()
            }
            self._reset(new_stage)
            self._blocked_rng = previous_rng
            if pending_export:
                self._stage_export = pending_export
            if pending_rng:
                self._rng.update(pending_rng)
                for role in pending_rng:
                    self._blocked_rng.pop(role, None)
        old_stage_id = _stage_identity(self._stage_info or self._deploy["stage"])
        new_stage_id = _stage_identity(stage_info)
        defer_stage = bool(
            self._finalized and state != self.PLAYING
            and old_stage_id and new_stage_id and old_stage_id != new_stage_id)
        if defer_stage:
            self._pending_stage_info = json_safe(stage_info)
        elif stage_info:
            self._stage_info = json_safe(stage_info)
            self._deploy["stage"] = json_safe(stage_info)
        if battle:
            self._deploy["battle"] = json_safe(battle)
            self._battle.update(json_safe(battle))
        if squad is not None:
            incoming = json_safe(squad)
            if incoming or not self._deploy["squad"]:
                self._deploy["squad"] = incoming
        if journal is not None:
            incoming = json_safe(journal)
            if incoming or not self._deploy["journalEvents"]:
                self._deploy["journalEvents"] = incoming
        if events is not None:
            incoming = json_safe(events)
            # 失败帧/销毁中的空读不能冲掉已经完整读取的操作列表。
            if incoming or not self._deploy["liveEvents"]:
                self._deploy["liveEvents"] = incoming
        if state == self.PLAYING:
            self._saw_playing = True
            self._last_play_time = (
                play_time if play_time is not None else self._last_play_time)
            if not (self._finalized and self._final_reason == "battle_finished"):
                self._finalized = False
                self._finalized_at = ""
                self._final_reason = ""
        self._touch()
        if state == self.FINISHED and self._saw_playing:
            self.finalize("battle_finished")

    def observe_rng(self, by_role: dict | None) -> None:
        for role, data in (by_role or {}).items():
            if not role or not isinstance(data, dict):
                continue
            history = data.get("history") or []
            last_seq = history[-1].get("seq") if history else None
            signature = (
                data.get("id"), data.get("total"), data.get("cursor"),
                data.get("cursor2"), data.get("status"), len(history), last_seq,
            )
            old = self._rng.get(str(role))
            blocked = self._blocked_rng.get(str(role))
            if blocked is not None:
                blocked_id, blocked_total = blocked
                new_total = data.get("total")
                same_stale_engine = data.get("id") == blocked_id and not (
                    isinstance(new_total, (int, float))
                    and isinstance(blocked_total, (int, float))
                    and new_total < blocked_total)
                if same_stale_engine:
                    continue
                self._blocked_rng.pop(str(role), None)
            if (self._finalized and self._final_reason == "battle_finished"
                    and old is not None
                    and data.get("id") != old.get("id")):
                self._pending_rng[str(role)] = _rng_copy(data)
                continue
            old_total = old.get("total") if old else None
            new_total = data.get("total")
            if (old is not None and isinstance(old_total, (int, float))
                    and isinstance(new_total, (int, float))
                    and new_total < old_total):
                continue
            if self._rng_signatures.get(str(role)) == signature:
                continue
            copied = _rng_copy(data)
            if old is not None and data.get("id") == old.get("id"):
                merged = {
                    item.get("seq"): item
                    for item in (old.get("history") or [])
                    if item.get("seq") is not None
                }
                for item in copied.get("history") or []:
                    if item.get("seq") is not None:
                        merged[item["seq"]] = item
                copied["history"] = [
                    merged[key] for key in sorted(merged)[-600:]
                ]
            self._rng[str(role)] = copied
            self._rng_signatures[str(role)] = signature
            self._touch()

    def finalize(self, reason: str) -> None:
        if not self._has_payload():
            return
        if self._frozen_runtime is None and self._runtime_ref is not None:
            self._frozen_runtime = self._runtime_payload(self._runtime_ref)
        self._finalized = True
        self._final_reason = str(reason or "unknown")
        self._finalized_at = _iso_now()
        self._touch()

    def has_data(self) -> bool:
        return self._has_payload()

    def has_stage_export(self) -> bool:
        return bool(self._stage_export)

    def has_deploy(self) -> bool:
        return bool(self._deploy["stage"] or self._stage_info
                    or self._deploy["liveEvents"] or self._deploy["journalEvents"])

    def has_rng(self, role: str) -> bool:
        return role in self._rng

    def is_finalized(self) -> bool:
        return self._finalized

    def stage_export(self) -> dict:
        return json_safe(self._stage_export)

    def deploy_state(self) -> dict:
        result = json_safe(self._deploy)
        if not result.get("stage"):
            result["stage"] = json_safe(self._stage_info)
        return result

    def rng_role(self, role: str) -> dict | None:
        value = self._rng.get(role)
        return json_safe(value) if value is not None else None

    def bundle(self) -> dict:
        runtime = self._frozen_runtime
        if runtime is None:
            runtime = self._runtime_payload(self._runtime_ref)
        deploy = self.deploy_state()
        stage = json_safe(self._stage_info or deploy.get("stage") or {})
        return {
            "format": "ArknightsBattleFinalSnapshot",
            "formatVersion": 1,
            "appVersion": self.app_version,
            "session": {
                "id": self._session_id,
                "startedAt": self._started_at,
                "lastUpdatedAt": self._updated_at,
                "finalized": self._finalized,
                "finalizedAt": self._finalized_at or None,
                "finalReason": self._final_reason or None,
                "boundedCache": True,
            },
            "stage": stage,
            "battle": json_safe(self._battle),
            "stagePlan": self.stage_export(),
            "operations": deploy,
            "runtime": json_safe(runtime),
            "rng": json_safe(self._rng),
        }
