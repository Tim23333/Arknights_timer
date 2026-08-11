"""GainToken inventory -> deployable token API (act36side / event modes).

The GainToken buff node registers player-side token counts in the battle
inventory (snapshot gainedTokens); deploy_gained_token consumes one count
to spawn the token on a tile, and the LiveServer /action endpoint exposes
it to the web UI.
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

TOKEN_KEY = "token_10055_phatm2_mndclv"   # 疯狂牢笼 (phatm2 S3 cage)


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def test_gain_token_node_registers_inventory():
    from ark_emulator.buff_templates import BuffTemplateEngine
    sim, b = _battle()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    assert eng._n_GainToken(op, {"_spiltTokenKey": 0}, {
        "bb": {"token_key": TOKEN_KEY}}) is True
    assert b._gained_tokens.get(TOKEN_KEY) == 1
    assert b.snapshot()["gainedTokens"].get(TOKEN_KEY, {}).get("count") == 1


def test_deploy_gained_token_consumes_inventory():
    sim, b = _battle()
    b._gained_tokens[TOKEN_KEY] = 1
    ok, res = b.deploy_gained_token(TOKEN_KEY, 3, 4)
    assert ok, res
    tok = [t for t in b.tokens if t.token_id == TOKEN_KEY]
    assert tok and (tok[0].row, tok[0].col) == (3, 4)
    assert b._gained_tokens[TOKEN_KEY] == 0
    ok2, res2 = b.deploy_gained_token(TOKEN_KEY, 3, 4)
    assert not ok2 and res2 == "not_gained"


def test_live_server_deploy_gained_action():
    port = _port()
    sim = Simulator("level_main_01-01")
    sim.pause()
    sim.battle._gained_tokens[TOKEN_KEY] = 1
    srv = LiveServer(sim, port=port, speed=1.0, tick_interval=0.005)
    srv.start()
    try:
        _wait_server(port)
        r = _post(port, "/action", {
            "action": "deploy_gained", "tokenKey": TOKEN_KEY,
            "row": 3, "col": 4})
        assert r.get("ok") is True, r
        snap = _get(port, "/snapshot")
        assert snap["gainedTokens"].get(TOKEN_KEY, {}).get(
            "count") == 0
        tok_ids = [t.get("instId") for t in snap.get("tokens", [])]
        assert tok_ids, "gained token must appear in the snapshot"
    finally:
        srv.stop()


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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    import traceback
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
