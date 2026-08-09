# -*- coding: utf-8 -*-
"""关卡地图、路线和敌人计划的稳定 JSON 导出格式。"""

from __future__ import annotations

import math
from datetime import datetime, timezone


SCHEMA_NAME = "arknights-stage-strategy"
SCHEMA_VERSION = 1
TIMELINE_FPS = 60

_BASE_TILE_KEYS = {
    "tile_empty", "tile_floor", "tile_road", "tile_forbidden", "tile_wall",
    "tile_start", "tile_flystart", "tile_end", "tile_allygoal",
    "tile_enemygoal", "tile_hole", "tile_telin", "tile_telout",
}


def _number(value, default=None):
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return default


def classify_tile(tile_key: str, height_type=None, passable_mask=None) -> str:
    """把 80+ 种关卡 tileKey 归到前端可稳定着色的少数类别。"""
    key = (tile_key or "").lower()
    if key in {"tile_start", "tile_flystart", "tile_enemygoal"}:
        return "enemy_spawn"
    if key in {"tile_end", "tile_allygoal"}:
        return "friendly_goal"
    if key == "tile_telin":
        return "teleport_in"
    if key == "tile_telout":
        return "teleport_out"
    if key == "tile_hole":
        return "hole"
    if key in {"tile_forbidden", "tile_empty"}:
        return "forbidden"
    if key == "tile_wall" or height_type == 1:
        return "highland"
    if key and key not in _BASE_TILE_KEYS:
        return "device"
    if passable_mask == 0:
        return "obstacle"
    return "ground"


def normalize_map_snapshot(map_data: dict | None) -> dict:
    source = map_data or {}
    rows = max(0, int(source.get("rows") or 0))
    cols = max(0, int(source.get("cols") or 0))
    cells = []
    for index, tile in enumerate(source.get("tiles") or []):
        if not isinstance(tile, dict):
            continue
        row = int(tile.get("row", index // max(1, cols)))
        col = int(tile.get("col", index % max(1, cols)))
        key = str(tile.get("tileKey") or tile.get("key") or "tile_empty")
        item = {
            "row": row,
            "col": col,
            "tileKey": key,
            "category": tile.get("category") or classify_tile(
                key, tile.get("heightType"), tile.get("passableMask")),
            "heightType": tile.get("heightType"),
            "buildableType": tile.get("buildableType"),
            "passableMask": tile.get("passableMask"),
            "playerSideMask": tile.get("playerSideMask"),
            "advancedBuildableMask": tile.get("advancedBuildableMask"),
        }
        cells.append(item)
    return {
        "mapId": str(source.get("mapId") or ""),
        "rows": rows,
        "cols": cols,
        "tiles": cells,
        "blockEdges": list(source.get("blockEdges") or []),
        "devices": list(source.get("devices") or []),
        "tags": list(source.get("tags") or []),
    }


def serialize_spawn_record(record: dict, fps: int = TIMELINE_FPS) -> dict:
    info = record.get("info")
    enemy_id = str(record.get("key") or getattr(info, "eid", "") or "")
    start_time = _number(record.get("nominal_spawn_time"))
    actual_start_frame = _number(record.get("spawn_frame"))
    actual_end_frame = _number(record.get("end_frame"))
    start_frame = (int(actual_start_frame) if actual_start_frame is not None
                   else round(start_time * fps) if start_time is not None else None)
    return {
        "id": str(record.get("roster_id", "")),
        "order": int(record.get("spawn_order") or 0),
        "enemyId": enemy_id,
        "name": getattr(info, "name", "") or enemy_id,
        "code": getattr(info, "code", "") or "",
        "kind": record.get("spawn_kind") or "dynamic",
        "source": record.get("spawn_source") or "",
        "condition": record.get("spawn_condition") or "",
        "wave": int(record.get("wave_index", -1)),
        "fragment": int(record.get("fragment_index", -1)),
        "action": int(record.get("action_index", -1)),
        "spawnIndex": int(record.get("spawn_index", -1)),
        "routeIndex": int(record.get("route_index", -1)),
        "startTime": start_time,
        "startFrame": start_frame,
        "actualStartFrame": int(actual_start_frame) if actual_start_frame is not None else None,
        "endFrame": int(actual_end_frame) if actual_end_frame is not None else None,
        "endReason": record.get("end_reason") or "",
        "lifecycle": getattr(info, "lifecycle", "pending") if info else "pending",
        "hiddenGroup": record.get("hidden_group") or "",
        "randomSpawnGroup": record.get("random_spawn_group") or "",
        "randomSpawnPack": record.get("random_spawn_pack") or "",
        "randomType": record.get("random_type"),
        "weight": record.get("weight"),
        "managedByScheduler": bool(record.get("managed", False)),
        "notCountInTotal": bool(record.get("not_count_in_total", False)),
    }


def build_stage_export(reader, stage_info: dict | None = None) -> dict:
    """从 EnemyReader 缓存构建可直接导入排轴前端的纯 JSON 对象。"""
    stage_info = stage_info or {}
    records = list(reader._spawn_plan) + list(reader._runtime_spawn_plan)
    spawns = [serialize_spawn_record(record) for record in records]

    known_ids = {str(item.get("id")) for item in spawns}
    for roster_id, info in sorted(
            reader._roster_last.items(), key=lambda pair: pair[1].spawn_order):
        if str(roster_id) in known_ids:
            continue
        start_frame = getattr(info, "spawn_frame", None)
        spawns.append({
            "id": str(roster_id), "order": int(info.spawn_order or 0),
            "enemyId": info.eid or "", "name": info.name or info.eid or "",
            "code": info.code or "", "kind": info.spawn_kind or "dynamic",
            "source": info.spawn_source or "运行时动态追加",
            "condition": info.spawn_condition or "", "wave": -1,
            "fragment": -1, "action": -1, "spawnIndex": -1,
            "routeIndex": int(info.route_index if info.route_index is not None else -1),
            "startTime": None,
            "startFrame": start_frame, "actualStartFrame": start_frame,
            "endFrame": getattr(info, "end_frame", None),
            "endReason": getattr(info, "end_reason", ""),
            "lifecycle": info.lifecycle, "hiddenGroup": "",
            "randomSpawnGroup": "", "randomSpawnPack": "",
            "randomType": None, "weight": None,
            "managedByScheduler": False, "notCountInTotal": False,
        })

    return {
        "schema": SCHEMA_NAME,
        "schemaVersion": SCHEMA_VERSION,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "timeline": {"fps": TIMELINE_FPS, "frameUnit": "game_logic_frame"},
        "stage": {
            "stageId": str(stage_info.get("stageId") or ""),
            "levelId": str(reader.plan_level_id or stage_info.get("levelId") or ""),
            "code": str(stage_info.get("code") or ""),
            "name": str(stage_info.get("name") or ""),
            "mapId": str((reader._level_map_data or {}).get("mapId") or ""),
        },
        "map": normalize_map_snapshot(reader._level_map_data),
        "routes": list(reader._routes_export or []),
        "enemyKinds": {
            "scheduled": "固定波次",
            "conditional": "条件分支/随机组",
            "summoned": "召唤、死亡转阶段或事件占位",
            "dynamic": "运行时动态追加",
        },
        "enemySpawns": sorted(spawns, key=lambda item: (item["order"], item["id"])),
        "operatorActions": [],
    }
