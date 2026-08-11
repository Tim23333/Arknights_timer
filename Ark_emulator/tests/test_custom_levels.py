# -*- coding: utf-8 -*-
"""Custom level injection tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.custom_levels import build_level, load_level, save_level


def test_custom_level_runs():
    lv = build_level(rows=6, cols=10, route_row=3, enemies=[
        {"key": "enemy_1000_gopro", "count": 5, "interval": 1.0,
         "start": 1.0}])
    sim = Simulator(level_id="custom", custom_level=lv)
    sim.run(seconds=10)
    snap = sim.snapshot()
    assert snap["map"]["rows"] == 6 and snap["map"]["cols"] == 10
    assert snap["waves"]["spawned"] == 5
    assert len(snap["enemies"]) > 0
    assert all(e["row"] == 3 for e in snap["enemies"]), \
        [e["row"] for e in snap["enemies"]]


def test_custom_level_save_load_roundtrip():
    lv = build_level(rows=4, cols=6, name="rt_test")
    path = save_level(lv, directory=r"G:\Arknights\Ark_emulator\custom_levels")
    loaded = load_level(path)
    assert loaded["map"]["rows"] == 4
    assert loaded["map"]["cols"] == 6
    sim = Simulator(level_id="custom", custom_level=loaded)
    sim.run(seconds=3)
    assert sim.battle.map.rows == 4


def test_editor_page_renders():
    from ark_emulator.web_ui import editor_html
    html = editor_html()
    assert "Custom level editor" in html
    assert "/custom-level" in html
    assert "buildLevel" in html


def test_multipoint_route_runs():
    lv = {
        "name": "mp_test",
        "map": {"rows": 6, "cols": 10, "tiles": [
            {"tileKey": "tile_floor", "buildableType": 1,
             "passableMask": 1, "heightType": 1} for _ in range(60)]},
        "routes": [{
            "startPosition": {"row": 2, "col": 0},
            "endPosition": {"row": 4, "col": 9},
            "checkpoints": [
                {"type": {"name": "MOVE"}, "position": {"row": 2, "col": 4}},
                {"type": {"name": "MOVE"}, "position": {"row": 4, "col": 5}},
            ]}],
        "waveTimeline": [{"t": 1.0, "key": "enemy_1000_gopro",
                          "routeIndex": 0, "actionType": "SPAWN"}],
        "options": {"maxLifePoint": 3, "initialCost": 10,
                    "costIncreaseTime": 1.0, "maxCost": 99},
    }
    sim = Simulator(level_id="custom", custom_level=lv)
    sim.run(seconds=15)
    snap = sim.snapshot()
    assert len(snap["enemies"]) > 0
    e = snap["enemies"][0]
    # L-shaped route ends at (4,9); enemy should be near there
    assert e["col"] >= 8, e


def test_route_aware_bot_clears_1_1():
    import sys as _sys
    _sys.path.insert(0, r"G:\Arknights\Ark_emulator\examples")
    from bot import Bot
    squad = [
        {"charId": "char_149_scave", "level": 50, "phase": 2},
        {"charId": "char_002_amiya", "level": 50, "phase": 2},
        {"charId": "char_102_texas", "level": 50, "phase": 2},
        {"charId": "char_172_svrash", "level": 50, "phase": 2},
        {"charId": "char_128_plosis", "level": 50, "phase": 2},
        {"charId": "char_150_snakek", "level": 50, "phase": 2},
        {"charId": "char_122_beagle", "level": 50, "phase": 2},
        {"charId": "char_124_kroos", "level": 50, "phase": 2},
    ]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    bot = Bot(sim, squad)
    guard = 0
    while not sim.battle.finished and guard < 30 * 90:
        bot.tick()
        sim.battle.tick_once()
        guard += 1
    assert sim.battle.result == "victory", (sim.battle.result, sim.battle.tick)
    assert len(sim.battle.operators) >= 3


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("OK", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    print("all custom level tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
