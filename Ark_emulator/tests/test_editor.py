# -*- coding: utf-8 -*-
"""Editor / custom-level enemy placement tests.

Covers: /editor page, /enemies search endpoint, explicit spawn positions
from wave-timeline events and custom-enemy overrides, and an end-to-end
custom level with a visually placed enemy.
"""
import os
import sys
import json
import socket
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.custom_levels import build_level
from ark_emulator.live_server import LiveServer


def test_explicit_spawn_from_timeline():
    """waveTimeline events with row/col spawn the enemy at that tile."""
    lv = build_level(rows=6, cols=10, enemies=[])
    lv["waveTimeline"] = [
        {"t": 1.0, "key": "enemy_1000_gopro", "routeIndex": 0,
         "actionType": "SPAWN", "row": 1, "col": 2},
    ]
    sim = Simulator(level_id="custom", custom_level=lv)
    sim.run_ticks(31)
    e = sim.battle.enemies[0]
    assert (e.row, e.col) == (1, 2), (e.row, e.col)


def test_explicit_spawn_from_custom_enemy_override():
    sim = Simulator("level_main_01-01", custom_enemies=[
        {"key": "enemy_1000_gopro", "startTime": 0.5, "row": 2, "col": 3}])
    sim.run_ticks(16)
    e = sim.battle.enemies[0]
    assert (e.row, e.col) == (2, 3), (e.row, e.col)


def test_editor_flow_placed_enemy_moves_along_route():
    """The level JSON the editor builds (row/col SPAWN) runs end-to-end."""
    lv = build_level(rows=6, cols=10, enemies=[])
    lv["waveTimeline"] = [
        {"t": 0.5, "key": "enemy_1000_gopro", "routeIndex": 0,
         "actionType": "SPAWN", "row": 3, "col": 1},
    ]
    sim = Simulator(level_id="custom", custom_level=lv)
    sim.run_ticks(16)                       # t=0.5 -> tick 15 processed
    e = sim.battle.enemies[0]
    assert (e.row, e.col) == (3, 1)
    sim.run_ticks(30)                      # 1s: should have moved (or leaked)
    if sim.battle.enemies:
        e2 = sim.battle.enemies[0]
        assert (e2.row, e2.col) != (3, 1), "enemy should leave the spawn tile"
    else:
        assert sim.battle.life_point < 3, "enemy vanished without leaking"


def test_editor_page_and_enemies_endpoint():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    sim = Simulator("level_main_01-01")
    srv = LiveServer(sim, port=port, speed=0)
    srv.start()
    try:
        time.sleep(0.4)
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/editor", timeout=10) as r:
            html = r.read().decode("utf-8")
        assert "place mode" in html and "enemies JSON" in html, html[:200]
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/enemies?q=gopro",
                timeout=10) as r:
            d = json.load(r)
        keys = [h["key"] for h in d["hits"]]
        assert any(k == "enemy_1000_gopro" for k in keys), keys
        assert all("gopro" in k for k in keys), keys
        # names resolve (Chinese names from the roster)
        assert any(h.get("name") for h in d["hits"])
    finally:
        srv.stop()


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
    print("all editor tests passed" if not failed else "%d failed" % failed)
    sys.exit(1 if failed else 0)
