# -*- coding: utf-8 -*-
"""LiveServer end-to-end chain: level reload, squad / custom-enemy config,
deploy action, SSE stream and full JSON-serializable snapshot containing the
latest wave fields (randomGroups / branches / hiddenGroups).
"""
import json
import os
import socket
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState
from ark_emulator.live_server import LiveServer


def _port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _get(port, path, timeout=8):
    with urllib.request.urlopen(
            "http://127.0.0.1:%d%s" % (port, path), timeout=timeout) as r:
        return json.load(r)


def _post(port, path, body, timeout=8):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _wait_server(port):
    for _ in range(60):
        try:
            return _get(port, "/status", timeout=2)
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("live server did not start")


def _wait_until(pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_snapshot_unit_detail_fields():
    """Snapshots expose element bars, attackSpeed/blockCnt, enemy
    mass/range/talentBlackboard for real-time AI consumers."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 3)
    e = b.spawn_enemy("enemy_1519_bgball", 0, overrides={
        "attributes": {"maxHp": 50000.0}, "row": 3, "col": 4})
    e.state = EnemyState.COMBAT
    b.add_ep(e, 3, 500.0)
    snap = b.snapshot()
    en = next(x for x in snap["enemies"] if x["instId"] == e.inst_id)
    assert en["elements"].get("ep_dark", 0.0) >= 500.0, en["elements"]
    assert "attackSpeed" in en and "blockCnt" in en
    assert "massLevel" in en and "rangeRadius" in en
    assert abs(en["talentBlackboard"].get(
        "mode_1.hp_ratio", 0.0) - 0.6) < 1e-9, en["talentBlackboard"]
    op = next(x for x in snap["deployed"]
              if x["charId"] == "char_149_scave")
    assert "elements" in op and "attackSpeed" in op and "blockCnt" in op


def test_live_server_level_reload_and_config_chain():
    """/new reloads a level, /config rebuilds with a custom squad + custom
    enemies, and the new snapshot fields stay JSON-serializable over HTTP."""
    port = _port()
    sim = Simulator("level_lt01_01", seed=123)
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        # level listing
        ls = _get(port, "/levels")
        assert "levels" in ls and "level_lt01_01" in ls["levels"], ls
        # snapshot exposes the newest wave fields and is JSON-serializable
        snap = _get(port, "/snapshot")
        assert len(snap["waves"]["randomGroups"]) == 4, \
            snap["waves"].get("randomGroups")
        assert "branches" in snap
        assert "hiddenGroups" in snap
        # reload a different level through the web endpoint
        r = _get(port, "/new?level=level_main_01-01")
        assert r["ok"] is True
        assert _wait_until(
            lambda: _get(port, "/status", timeout=2).get("tick", -1) >= 0)
        # apply squad + custom enemies; server rebuilds the battle
        r = _post(port, "/config", {
            "squad": [{"charId": "char_002_amiya", "phase": 2,
                       "level": 30, "potential": 1}],
            "custom_enemies": [{"key": "enemy_1000_gopro", "count": 2,
                                "startTime": 1.0}],
        })
        assert r["ok"] is True and r["squad"], r
        # pause and step to the custom spawn time (1s -> tick 30)
        _post(port, "/action", {"action": "pause"})
        _post(port, "/action", {"action": "step", "n": 60})
        snap = _get(port, "/snapshot")
        gopro = [e for e in snap["enemies"]
                 if e.get("charId", e.get("key")) == "enemy_1000_gopro"]
        assert len(gopro) == 2, [e.get("key") for e in snap["enemies"]]
        # give enough deployment cost, then deploy from the configured squad
        srv.sim.battle.cost = 50.0
        r = _post(port, "/action", {"action": "deploy",
                                    "charId": "char_002_amiya",
                                    "row": 2, "col": 3, "direction": 1})
        assert r["ok"] is True, r
        snap = _get(port, "/snapshot")
        assert [d["charId"] for d in snap["deployed"]] == \
            ["char_002_amiya"]
        # event endpoint
        evs = _get(port, "/events")
        assert isinstance(evs["events"], list) and evs["events"]
    finally:
        srv.stop()


def test_live_server_sse_stream_and_editor():
    """The SSE /stream pushes JSON batches containing a full snapshot; the
    editor page and enemy search endpoints respond."""
    port = _port()
    sim = Simulator("level_main_01-01")
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/stream" % port, timeout=8) as r:
            chunk = r.read(4096).decode("utf-8", "replace")
        assert "data: " in chunk and '"snapshot"' in chunk, chunk[:200]
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/editor" % port, timeout=8) as r:
            editor = r.read().decode("utf-8", "replace")
        assert "buildLevel" in editor
        hits = _get(port, "/enemies?q=gopro")
        assert hits["hits"], hits
        assert any("gopro" in h["key"] for h in hits["hits"])
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
    print("all live server chain tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)
