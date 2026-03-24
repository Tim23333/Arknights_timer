"""
Parse frontend timeline JSON and compute status vs current game frame.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _meta_fps(meta: Dict[str, Any]) -> int:
    fps = meta.get("fps")
    try:
        n = int(fps)
        return max(1, n)
    except (TypeError, ValueError):
        return 60


def _seg_start_end(seg: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    s = seg.get("startFrame", seg.get("start_frame"))
    e = seg.get("endFrame", seg.get("end_frame"))
    try:
        a = int(round(float(s)))
        b = int(round(float(e)))
    except (TypeError, ValueError):
        return None
    lo, hi = (a, b) if a <= b else (b, a)
    return max(0, lo), max(0, hi)


def flatten_schedule(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return sorted flat items + meta (may be empty)."""
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return [], meta

    items: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_name = str(row.get("name") or "未命名轨道")
        row_id = str(row.get("id") or "")
        segs = row.get("segments")
        if not isinstance(segs, list):
            continue
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            bounds = _seg_start_end(seg)
            if bounds is None:
                continue
            start_f, end_f = bounds
            items.append(
                {
                    "row_id": row_id,
                    "row_name": row_name,
                    "segment_id": seg.get("id"),
                    "label": str(seg.get("label") or ""),
                    "note": str(seg.get("note") or ""),
                    "color": str(seg.get("color") or "#888888"),
                    "start_frame": start_f,
                    "end_frame": end_f,
                }
            )

    items.sort(key=lambda x: (x["start_frame"], x["end_frame"], x["row_name"]))
    return items, meta


def resolve_current_frame(
    game: Dict[str, Any],
    fps: int,
) -> Tuple[Optional[int], str]:
    """
    Prefer memory frame_count; fallback to game_time * fps.
    """
    fc = game.get("frame_count")
    if fc is not None:
        try:
            return int(fc), "frame_count"
        except (TypeError, ValueError):
            pass
    gt = game.get("game_time")
    if gt is not None:
        try:
            return max(0, int(round(float(gt) * max(1, fps)))), "game_time_scaled"
        except (TypeError, ValueError):
            pass
    return None, "none"


def enrich_item(
    item: Dict[str, Any],
    current_frame: int,
    fps: int,
) -> Dict[str, Any]:
    s, e = item["start_frame"], item["end_frame"]
    if current_frame < s:
        phase = "upcoming"
    elif current_frame <= e:
        phase = "active"
    else:
        phase = "past"

    def sec_str(frames: int) -> str:
        if fps <= 0:
            return "—"
        sec = frames / fps
        if abs(sec) < 0.0005:
            return "0.000s"
        return f"{sec:.3f}s"

    out = {**item, "phase": phase, "fps": fps}
    if phase == "upcoming":
        d = s - current_frame
        out["frames_until_start"] = d
        out["frames_until_end"] = e - current_frame
        out["until_start_text"] = f"还有 {d} 帧 ({sec_str(d)})"
        out["until_end_text"] = f"距结束还有 {e - current_frame} 帧"
    elif phase == "active":
        d_end = e - current_frame
        out["frames_until_start"] = 0
        out["frames_until_end"] = d_end
        out["until_start_text"] = "已开始"
        out["until_end_text"] = f"本段剩余 {d_end} 帧 ({sec_str(d_end)})"
    else:
        out["frames_until_start"] = None
        out["frames_until_end"] = None
        out["until_start_text"] = "已过"
        out["until_end_text"] = "已过"

    out["range_text"] = f"F{s} – F{e} ({s / fps:.3f}s – {e / fps:.3f}s)"
    return out


def describe_current_step(
    items: List[Dict[str, Any]],
    current_frame: int,
) -> Dict[str, Any]:
    """Which segment is active / what we are waiting for."""
    if not items:
        return {
            "kind": "empty",
            "summary": "尚未加载排轴 JSON",
            "detail": None,
        }

    for i, it in enumerate(items):
        if it["start_frame"] <= current_frame <= it["end_frame"]:
            return {
                "kind": "active",
                "summary": f"正在执行：{it['row_name']} — {it['label'] or '区间'} (F{it['start_frame']}–F{it['end_frame']})",
                "index": i,
                "item": it,
            }

    if current_frame < items[0]["start_frame"]:
        n = items[0]
        d = n["start_frame"] - current_frame
        return {
            "kind": "before_start",
            "summary": f"尚未开始，距第一项还有 {d} 帧",
            "next_index": 0,
            "next_item": n,
            "frames_until_next": d,
        }

    if current_frame > items[-1]["end_frame"]:
        return {
            "kind": "after_end",
            "summary": "排轴已全部结束（相对当前帧）",
            "last_index": len(items) - 1,
            "last_item": items[-1],
        }

    for i in range(len(items) - 1):
        a, b = items[i], items[i + 1]
        if a["end_frame"] < current_frame < b["start_frame"]:
            d = b["start_frame"] - current_frame
            return {
                "kind": "idle",
                "summary": f"空闲：上一段已结束，距下一段「{b['row_name']}」还有 {d} 帧",
                "after_index": i,
                "next_index": i + 1,
                "next_item": b,
                "frames_until_next": d,
            }

    return {
        "kind": "unknown",
        "summary": "无法判定当前阶段",
        "detail": None,
    }


def game_frame_for_anchor(schedule_payload: Dict[str, Any], game: Dict[str, Any]) -> Optional[int]:
    """与排轴 meta.fps 一致，解析当前游戏帧（用于「从当前帧起算」锚点）。"""
    _, meta = flatten_schedule(schedule_payload)
    fps = _meta_fps(meta)
    cf, _ = resolve_current_frame(game, fps)
    return cf


def build_status_payload(
    schedule_payload: Optional[Dict[str, Any]],
    game: Dict[str, Any],
    *,
    relative_anchor_game_frame: Optional[int] = None,
) -> Dict[str, Any]:
    if not schedule_payload:
        return {
            "ok": True,
            "schedule_loaded": False,
            "game": game,
            "fps": 60,
            "current_frame": None,
            "current_frame_source": "none",
            "relative_anchor_game_frame": relative_anchor_game_frame,
            "items": [],
            "current_step": describe_current_step([], 0),
            "message": "请 POST /api/schedule/load 上传前端导出的 JSON。",
        }

    flat, meta = flatten_schedule(schedule_payload)
    fps = _meta_fps(meta)
    current_frame, src = resolve_current_frame(game, fps)
    raw_game_frame = current_frame

    if current_frame is not None and relative_anchor_game_frame is not None:
        try:
            anchor = int(relative_anchor_game_frame)
        except (TypeError, ValueError):
            anchor = 0
        current_frame = int(current_frame) - anchor
        src = f"{src}_rel_anchor"

    if current_frame is None:
        enriched = []
        for x in flat:
            s, e = x["start_frame"], x["end_frame"]
            enriched.append(
                {
                    **x,
                    "phase": "unknown",
                    "fps": fps,
                    "range_text": f"F{s} – F{e} ({s / fps:.3f}s – {e / fps:.3f}s)",
                    "until_start_text": "—",
                    "until_end_text": "—",
                    "frames_until_start": None,
                    "frames_until_end": None,
                }
            )
        step = {
            "kind": "no_game_frame",
            "summary": str(game.get("message") or "无法读取游戏帧，请先配置进程/地址或确认游戏运行中。"),
            "detail": None,
        }
    else:
        enriched = [enrich_item(dict(x), current_frame, fps) for x in flat]
        step = describe_current_step(flat, current_frame)

    out: Dict[str, Any] = {
        "ok": True,
        "schedule_loaded": True,
        "game": game,
        "fps": fps,
        "current_frame": current_frame,
        "current_frame_source": src,
        "relative_anchor_game_frame": relative_anchor_game_frame,
        "items": enriched,
        "current_step": step,
        "message": "ok",
    }
    if raw_game_frame is not None:
        out["raw_game_frame"] = raw_game_frame
    return out
