# -*- coding: utf-8 -*-
"""UI click-flow automation: the same HTTP endpoints the web page uses
when the player clicks (ground to deploy, operator to skill, operator to
retreat) drive the battle, and every step is verified through the live
snapshot / event endpoints.
"""
import json
import os
import socket
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.live_server import LiveServer


def _port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _post(port, path, body):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _get(port, path):
    with urllib.request.urlopen(
            "http://127.0.0.1:%d%s" % (port, path), timeout=20) as r:
        return json.load(r)


def _wait_server(port):
    for _ in range(50):
        try:
            return _get(port, "/status")
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("live server did not start")


def test_click_flow_deploy_skill_withdraw():
    """Click sequence: step (cost) -> deploy fen -> skill (SP not ready
    yet -> not_ready) -> withdraw (redeploy timer starts)."""
    port = _port()
    sim = Simulator("level_main_01-01")
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        # grow deployment cost (initial 10 < fen 12)
        _post(port, "/action", {"action": "step", "n": 300})
        r = _post(port, "/action", {"action": "deploy",
                                    "charId": "char_149_scave",
                                    "row": 3, "col": 4, "direction": 1})
        assert r["ok"] and isinstance(r["result"], int), r
        inst = r["result"]
        snap = _get(port, "/snapshot")
        assert [d["charId"] for d in snap["deployed"]] == \
            ["char_149_scave"]
        # skill before SP is ready -> not_ready (game semantics)
        r = _post(port, "/action", {"action": "skill",
                                    "instId": inst, "skillIndex": 0})
        assert r["ok"] is False and r["result"] == "not_ready", r
        # withdraw -> operator gone + redeploy timer
        r = _post(port, "/action", {"action": "withdraw", "instId": inst})
        assert r["ok"] is True, r
        snap = _get(port, "/snapshot")
        assert not snap["deployed"]
        assert any(x["charId"] == "char_149_scave" and
                   x["redeployIn"] > 60 for x in snap["redeploys"])
        evs = _get(port, "/events")
        types = [e["type"] for e in evs["events"]]
        assert "deploy" in types and "withdraw" in types
    finally:
        srv.stop()


def test_click_flow_manual_skill_cast():
    """Click the skill button with SP full: manual skill activates and
    emits a skill_cast event; snapshot reflects the casting state."""
    port = _port()
    sim = Simulator("level_main_01-01")
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        _post(port, "/action", {"action": "step", "n": 300})
        r = _post(port, "/action", {"action": "deploy",
                                    "charId": "char_002_amiya",
                                    "row": 2, "col": 3, "direction": 1})
        assert r["ok"] and isinstance(r["result"], int), r
        inst = r["result"]
        # fill SP of the manual S2 (simulates an already-ready skill)
        op = srv.sim.battle.operators[0]
        sc = op.skill_controller
        s2 = sc.skills[1]
        op.sp = s2.sp_cost
        r = _post(port, "/action", {"action": "skill",
                                    "instId": inst, "skillIndex": 1})
        assert r["ok"] is True, r
        evs = _get(port, "/events")
        cast = [e for e in evs["events"] if e["type"] == "skill_cast"]
        assert cast and cast[-1]["data"]["skillId"] == "skchr_amiya_2"
        assert cast[-1]["data"]["instId"] == inst
        snap = _get(port, "/snapshot")
        dep = snap["deployed"][0]
        assert dep["activeSkill"]["skillId"] == "skchr_amiya_2"
        # retreat
        r = _post(port, "/action", {"action": "withdraw", "instId": inst})
        assert r["ok"] is True, r
    finally:
        srv.stop()


def test_web_pages_load_with_click_handlers():
    """The served battle page and editor page load over HTTP and contain
    the click-to-deploy / click-to-skill / click-to-retreat handlers."""
    port = _port()
    sim = Simulator("level_main_01-01")
    sim.pause()
    srv = LiveServer(sim, port=port, speed=0.1, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/" % port, timeout=5) as r:
            html = r.read().decode("utf-8", "replace")
        assert r.status == 200 and "action" in html
        assert "deploy" in html
        assert "withdraw" in html or "retreat" in html
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/editor" % port, timeout=5) as r:
            editor = r.read().decode("utf-8", "replace")
        assert r.status == 200 and "buildLevel" in editor
    finally:
        srv.stop()
