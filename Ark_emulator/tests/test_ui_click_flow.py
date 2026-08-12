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
import urllib.parse
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


def test_deploy_uses_selected_skill_and_direction():
    """The deployment confirmation's skill/direction choices reach the
    instantiated operator, not merely the browser preview."""
    port = _port()
    sim = Simulator("level_main_01-01", squad=[{
        "charId": "char_002_amiya", "phase": 2, "level": 50,
        "skillIndex": 0}])
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        _post(port, "/action", {"action": "step", "n": 300})
        result = _post(port, "/action", {
            "action": "deploy", "charId": "char_002_amiya",
            "row": 2, "col": 3, "direction": 3, "skillIndex": 1})
        assert result["ok"] is True, result
        operator = _get(port, "/snapshot")["deployed"][0]
        assert operator["direction"] == 3
        assert operator["equippedSkillIndex"] == 1
        assert operator["skills"][1]["equipped"] is True
        assert operator["skills"][0]["equipped"] is False
        events = _get(port, "/events")["events"]
        deploy = next(e for e in events if e["type"] == "deploy")
        assert deploy["data"]["skillIndex"] == 1
        # Per-deployment selection must not mutate the configured squad.
        assert _get(port, "/status")["squad"][0]["skillIndex"] == 0
    finally:
        srv.stop()


def test_deploy_rejects_invalid_selected_skill_before_cost():
    port = _port()
    sim = Simulator("level_main_01-01")
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        _post(port, "/action", {"action": "step", "n": 300})
        cost_before = _get(port, "/snapshot")["cost"]
        result = _post(port, "/action", {
            "action": "deploy", "charId": "char_002_amiya",
            "row": 2, "col": 3, "direction": 1, "skillIndex": 99})
        assert result == {"ok": False, "result": "invalid_skill"}
        snapshot = _get(port, "/snapshot")
        assert snapshot["cost"] == cost_before
        assert snapshot["deployed"] == []
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
        assert "关卡选择" in html
        assert "实时事件流" in html
        assert "pendingDeployment" in html
        assert "confirmDeployment" in html
        assert "data-pending-dir" in html
        assert "data-pending-skill" in html
        assert 'id="configOperatorSearch"' in html
        assert 'id="configOperatorResults"' in html
        assert "searchConfigOperators" in html
        assert "addConfigOperator" in html
        assert "搜索并加入干员" in html
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/editor" % port, timeout=5) as r:
            editor = r.read().decode("utf-8", "replace")
        assert r.status == 200 and "buildLevel" in editor
    finally:
        srv.stop()


def test_web_console_catalog_speed_and_restart():
    """The full console can search operators and control speed/restart."""
    port = _port()
    sim = Simulator("level_main_01-01", squad=[
        {"charId": "char_002_amiya", "phase": 2, "level": 50}])
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        status = _wait_server(port)
        assert status["level"]["levelId"] == "level_main_01-01"
        assert status["squad"][0]["charId"] == "char_002_amiya"

        ops = _get(port, "/operators?q=" +
                   urllib.parse.quote("阿米娅"))
        assert any(x["charId"] == "char_002_amiya" and
                   x["name"] == "阿米娅" for x in ops["hits"])
        amiya = next(x for x in ops["hits"]
                     if x["charId"] == "char_002_amiya")
        assert amiya["skills"] and amiya["maxPhase"] == 2
        all_ops = _get(port, "/operators")
        assert len(all_ops["hits"]) >= 400

        r = _post(port, "/action", {"action": "speed", "speed": 4})
        assert r == {"ok": True, "speed": 4.0}
        assert _get(port, "/status")["speed"] == 4.0

        _post(port, "/action", {"action": "step", "n": 30})
        assert _get(port, "/status")["tick"] >= 30
        r = _post(port, "/action", {"action": "restart"})
        assert r["ok"] is True
        assert _get(port, "/status")["tick"] == 0
    finally:
        srv.stop()


def test_live_squad_update_enables_drag_deploy_without_restart():
    """Adding a bottom-deck member is live and keeps the battle clock."""
    port = _port()
    sim = Simulator("level_main_01-01")
    sim.pause()
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        _post(port, "/action", {"action": "step", "n": 300})
        before = _get(port, "/status")["tick"]
        response = _post(port, "/squad", {"squad": [{
            "charId": "char_002_amiya", "phase": 2, "level": 50,
            "potential": 0}]})
        assert response["ok"] is True
        assert _get(port, "/status")["tick"] == before
        deploy = _post(port, "/action", {"action": "deploy",
            "charId": "char_002_amiya", "row": 2, "col": 3,
            "direction": 1})
        assert deploy["ok"] is True, deploy
        operator = _get(port, "/snapshot")["deployed"][0]
        assert (operator["row"], operator["col"]) == (2, 3)
        assert operator["maxHp"] > 1000  # E2/Lv50 config was consumed
    finally:
        srv.stop()


def test_live_server_rejects_duplicate_port():
    """A stale server cannot keep serving old code on the same port."""
    port = _port()
    first = LiveServer(Simulator("level_main_01-01"), port=port,
                       tick_interval=0.005)
    second = LiveServer(Simulator("level_main_01-01"), port=port,
                        tick_interval=0.005)
    first.start()
    try:
        _wait_server(port)
        try:
            second.start()
        except OSError:
            pass
        else:
            raise AssertionError("duplicate server should not share a port")
        assert second._thread is None
    finally:
        second.stop()
        first.stop()
