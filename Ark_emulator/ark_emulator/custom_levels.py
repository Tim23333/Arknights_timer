"""Custom level support: inject a user-defined level into the simulator.

Schema (JSON):
{
  "name": "my_level",
  "map": {
    "rows": 5, "cols": 8,
    "tiles": [ {"tileKey": "tile_floor", "buildableType": 1,
                "passableMask": 1, "heightType": 1}, ... rows*cols ]
  },
  "routes": [
    {"startPosition": {"row": 2, "col": 0},
     "endPosition": {"row": 2, "col": 7},
     "checkpoints": [{"type": {"name": "MOVE"}, "position":
                      {"row": 2, "col": 7}}]}
  ],
  "waveTimeline": [
    {"t": 1.0, "key": "enemy_1000_gopro", "routeIndex": 0,
     "actionType": "SPAWN"}
  ],
  "options": {"maxLifePoint": 3, "initialCost": 10,
              "costIncreaseTime": 1.0, "maxCost": 99},
  "enemyDbRefs": []
}

The emulator merges this into the same shape the built-in levels provide
(sim bundle level + raw level), so BattleController runs it unchanged.
"""

import io as _io
import json
import os

_DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "custom_levels")


def build_level(rows=5, cols=8, route_row=2, enemies=None,
                options=None, name="custom"):
    """Build a minimal custom level with a straight route."""
    tiles = []
    for r in range(rows):
        for c in range(cols):
            key = "tile_floor"
            if c == cols - 1:
                key = "tile_end"
            tiles.append({
                "tileKey": key,
                "buildableType": 1,
                "passableMask": 1,
                "heightType": 1,
            })
    wave = []
    for i, e in enumerate(enemies or [{"key": "enemy_1000_gopro",
                                       "count": 5, "interval": 2.0,
                                       "start": 2.0}]):
        t = float(e.get("start", 2.0))
        for j in range(int(e.get("count", 1))):
            wave.append({
                "t": t + j * float(e.get("interval", 2.0)),
                "key": e["key"],
                "routeIndex": e.get("routeIndex", 0),
                "actionType": "SPAWN",
            })
    return {
        "name": name,
        "map": {"rows": rows, "cols": cols, "tiles": tiles},
        "routes": [{
            "startPosition": {"row": route_row, "col": 0},
            "endPosition": {"row": route_row, "col": cols - 1},
            "checkpoints": [{
                "type": {"name": "MOVE"},
                "position": {"row": route_row, "col": cols - 1},
            }],
        }],
        "waveTimeline": sorted(wave, key=lambda x: x["t"]),
        "options": options or {
            "maxLifePoint": 3, "initialCost": 10,
            "costIncreaseTime": 1.0, "maxCost": 99,
        },
        "enemyDbRefs": [],
    }


def load_level(path_or_dict):
    """Load a custom level from a JSON file or an in-memory dict."""
    if isinstance(path_or_dict, dict):
        return normalize(path_or_dict)
    with _io.open(path_or_dict, encoding="utf-8") as f:
        return normalize(json.load(f))


def normalize(level):
    """Fill defaults so BattleController can consume the level directly."""
    lv = dict(level)
    lv.setdefault("map", {})
    m = lv["map"]
    rows = int(m.get("rows", 5))
    cols = int(m.get("cols", 8))
    tiles = m.get("tiles") or []
    if len(tiles) < rows * cols:
        for r in range(rows):
            for c in range(cols):
                if len(tiles) >= rows * cols:
                    break
                tiles.append({"tileKey": "tile_floor", "buildableType": 1,
                              "passableMask": 1, "heightType": 1})
    m["rows"] = rows
    m["cols"] = cols
    m["tiles"] = tiles
    lv.setdefault("routes", [{
        "startPosition": {"row": 0, "col": 0},
        "endPosition": {"row": 0, "col": cols - 1},
        "checkpoints": [],
    }])
    lv.setdefault("waveTimeline", [])
    lv.setdefault("options", {})
    lv.setdefault("enemyDbRefs", [])
    lv.setdefault("globalBuffs", [])
    return lv


def save_level(level, path=None, directory=_DEFAULT_DIR):
    """Save a custom level JSON (creates custom_levels/ if needed)."""
    os.makedirs(directory, exist_ok=True)
    name = level.get("name") or "custom"
    path = path or os.path.join(directory, f"{name}.json")
    with _io.open(path, "w", encoding="utf-8") as f:
        json.dump(normalize(level), f, ensure_ascii=False, indent=1)
    return path


def list_levels(directory=_DEFAULT_DIR):
    """List custom level files in the custom_levels directory."""
    if not os.path.isdir(directory):
        return []
    out = []
    for fn in sorted(os.listdir(directory)):
        if fn.endswith(".json"):
            out.append(fn[:-5])
    return out
