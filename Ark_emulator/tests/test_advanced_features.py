"""Tests for talents, custom enemies, tile effects and live server."""

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ark_emulator import Simulator


def test_talents():
    sim = Simulator("level_main_01-01")
    ok = None
    for _ in range(30 * 5):
        sim.run_ticks(1)
        ok, _ = sim.deploy("char_149_scave", 3, 4, direction=1)
        if ok:
            break
    assert ok
    snap = sim.snapshot()
    talents = snap["deployed"][0].get("talents") or []
    assert any("单独行动者" in (t.get("name") or "") for t in talents)
    print("OK test_talents", talents[0]["name"] if talents else "none")


def test_custom_enemies():
    sim = Simulator("level_main_01-01", custom_enemies=[
        {"key": "enemy_1000_gopro", "level": 1, "count": 3,
         "routeIndex": 1, "startTime": 2.0, "interval": 1.0,
         "attributes": {"maxHp": 9999, "atk": 500}},
    ])
    sim.run_ticks(30 * 6)
    snap = sim.snapshot()
    spawns = [e for e in snap["events"]
              if e["type"] == "enemy_spawn"
              and e["data"]["key"] == "enemy_1000_gopro"]
    assert len(spawns) == 3
    gopro = [e for e in snap["enemies"] if e["key"] == "enemy_1000_gopro"]
    if gopro:
        assert gopro[0]["hp"] == 9999
    print("OK test_custom_enemies spawns:", len(spawns))


def test_tile_effects_module():
    from ark_emulator.tile_effects import tile_kind, load_tile_defs
    defs = load_tile_defs()
    assert tile_kind("tile_volcano", defs) == "volcano_tile"
    assert tile_kind("tile_toxic", defs) == "dot_tile"
    assert tile_kind("tile_healing", defs) == "buff_tile"
    assert tile_kind("tile_road", defs) == ""
    print("OK test_tile_effects_module")


def test_live_server():
    import socket
    from ark_emulator.live_server import LiveServer
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    sim = Simulator("level_main_01-01")
    srv = LiveServer(sim, port=port, speed=5.0, tick_interval=0.005)
    srv.start()
    try:
        import urllib.request
        # poll until the server has advanced past the first-tick prefab
        # warmup AND reached a stable tick; a fixed real-time sleep is
        # timing-sensitive (warm cache can push the battle into defeat
        # within the window), so wait for a concrete tick instead
        st = {"tick": 0, "lifePoint": 10}
        deadline = time.time() + 15.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/status", timeout=2) as r:
                    st = json.load(r)
            except Exception:
                pass
            if st.get("tick", 0) >= 200:
                break
            time.sleep(0.05)
        assert st["tick"] >= 200, "server should advance past warmup"
        assert 0 < st["lifePoint"] <= 10, st
    finally:
        srv.stop()
    print("OK test_live_server tick:", st["tick"])


def test_global_buffs():
    from ark_emulator import Simulator as S
    sim = S("level_act13side_01")
    sim.run_ticks(30 * 25)          # first routed enemy at t=20s
    snap = sim.snapshot()
    assert snap.get("globalBuffs"), "level should carry global buffs"
    applied = [x for x in snap["events"] if x["type"] == "buff_applied"]
    assert applied, "spawned enemies should get global buff marker"
    print("OK test_global_buffs", snap["globalBuffs"])


def test_tile_actions_parse():
    from ark_emulator.tile_effects import TileEffectSystem, load_tile_defs
    te = TileEffectSystem.__new__(TileEffectSystem)
    te.defs = load_tile_defs()
    class FT:
        tile_key = "tile_volcano"
    acts = te._tile_actions(FT())
    assert acts and "NoSourceDamage" in acts[0].get("$type", "")
    assert acts[0]["_damageType"] == "PURE"
    print("OK test_tile_actions_parse")


def test_squad_level_potential():
    from ark_emulator import Simulator as S
    sim = S("level_main_01-01")
    data = sim.battle._char_base("char_002_amiya")
    a1 = sim.battle._char_attrs(data, 0, 1)
    a50 = sim.battle._char_attrs(data, 0, 50)
    assert abs(a1["maxHp"] - 699) < 0.01 and abs(a1["atk"] - 276) < 0.01
    assert abs(a50["maxHp"] - 958) < 0.01 and abs(a50["atk"] - 390) < 0.01
    a70 = sim.battle._char_attrs(data, 1, 70)   # phase1 lv70
    assert abs(a70["maxHp"] - 1198) < 0.01, a70["maxHp"]
    bonus = sim.battle._potential_bonus(data, 5)
    assert bonus.get("maxHp") == 200 and bonus.get("atk") == 30
    assert bonus.get("cost") == -2
    # end-to-end deploy with squad config
    sim2 = S("level_main_01-01", squad=[
        {"charId": "char_002_amiya", "level": 50, "phase": 0,
         "potential": 5}])
    for _ in range(30 * 10):
        sim2.run_ticks(1)
        # amiya is ranged: needs a highland cell (buildableType & 2)
        ok, _ = sim2.deploy("char_002_amiya", 2, 3, direction=1)
        if ok:
            break
    assert ok
    op = sim2.snapshot()["deployed"][0]
    assert abs(op["maxHp"] - 1158) < 0.01, op["maxHp"]
    assert abs(op["atk"] - 420) < 0.01, op["atk"]
    print("OK test_squad_level_potential hp:", op["maxHp"], "atk:", op["atk"])


def test_squad_skill_levels():
    from ark_emulator import Simulator as S
    from ark_emulator.operator_skills import OperatorSkillController
    from ark_emulator.attributes import Attributes
    from ark_emulator.entities import Operator
    for lvls, expected in (([1, 1, 1], 40.0), ([7, 7, 7], 32.0),
                           ([10, 10, 10], 30.0)):
        sim = S("level_main_01-01", squad=[
            {"charId": "char_002_amiya", "phase": 2, "level": 50,
             "skillLevels": lvls}])
        sk_data = sim.battle._char_skills("char_002_amiya")
        op = Operator("char_002_amiya", Attributes({}), row=0, col=0)
        ctl = OperatorSkillController(op, sim.battle, sk_data, lvls)
        assert abs(ctl.skills[0].sp_cost - expected) < 0.01,             (lvls, ctl.skills[0].sp_cost)
    print("OK test_squad_skill_levels")


def test_enemy_db_level():
    from ark_emulator import Simulator as S
    sim = S("level_a001_ex03")
    assert sim.battle._enemy_db_level("enemy_1002_nsabr") == 1
    assert sim.battle._enemy_db_level("enemy_1014_rogue") == 1
    assert sim.battle._enemy_db_level("enemy_missing") == 0
    sim.run_ticks(30 * 15)
    snap = sim.snapshot()
    rogue = [e for e in snap["enemies"] if e["key"] == "enemy_1014_rogue"]
    if rogue:
        assert rogue[0]["level"] == 1 and rogue[0]["maxHp"] > 1000
    print("OK test_enemy_db_level")


def test_special_tile_template_buffs():
    """Ice/mire terrain buffs ride the buff-template engine (freeze chain /
    mire trigger) instead of doing nothing."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState

    # ice: standing on tile_icestr applies the cold buff + derived buffs
    sim = Simulator("level_act14side_01")
    b = sim.battle
    cell = next((r, c) for r in range(b.map.rows)
                for c in range(b.map.cols)
                if b.map.tile(r, c) and
                b.map.tile(r, c).tile_key == "tile_icestr")
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = cell
    e.state = EnemyState.COMBAT
    for _ in range(10):
        b.tick_once()
    keys = [x.get("key") for x in e.buffs]
    assert "tile_icestr[cold]" in keys, keys
    # IsCharacterOrTokenOrTrap gate: an enemy takes the c2e (character-to-
    # enemy) cold branch, a character would take the e2c branch
    assert "c2e_cold" in keys, keys
    assert "e2c_cold" not in keys, keys

    # mire: buff_mire chain (trigger/effect/log) applied
    sim2 = Simulator("level_act22side_01")
    b2 = sim2.battle
    cell2 = next((r, c) for r in range(b2.map.rows)
                 for c in range(b2.map.cols)
                 if b2.map.tile(r, c) and
                 b2.map.tile(r, c).tile_key == "tile_mire")
    b2.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b2.enemies[0]
    e2.row, e2.col = cell2
    e2.state = EnemyState.COMBAT
    for _ in range(3):
        b2.tick_once()
    keys2 = [x.get("key") for x in e2.buffs]
    assert "buff_mire" in keys2, keys2
    assert "buff_mire[trigger]" in keys2, keys2
    print("OK test_special_tile_template_buffs ice/mire")


def test_operator_skill_effects():
    """Operator skill effects: whole-map stun + heal_scale."""
    from ark_emulator import Simulator as S
    sim = S("level_main_01-01")
    sim.battle.life_point = 1000.0   # leaks must not defeat before skill 40 SP
    deployed = False
    for _ in range(30 * 60):
        sim.run_ticks(1)
        if not deployed and sim.battle.cost >= 14:
            ok, _ = sim.deploy("char_102_texas", 3, 4, direction=1)
            deployed = ok
        snap = sim.snapshot()
        if deployed and snap["deployed"] and snap["deployed"][0]["sp"] >= 40:
            break
    assert deployed
    op = snap["deployed"][0]
    idx = next((i for i, s in enumerate(op["skills"])
                if s["skillId"].endswith("_2")), None)
    assert idx is not None
    ok2, _ = sim.activate_skill(op["instId"], idx)
    assert ok2
    # sword rain is a projectile: 0.5s cast windup + flight to each enemy;
    # stun lasts 2s (60 ticks), snapshot while it is still active
    sim.run_ticks(45)
    snap2 = sim.snapshot()
    stunned = [e for e in snap2["enemies"] if e.get("abnormal")]
    assert len(stunned) >= 3, f"whole-map stun should hit many: {len(stunned)}"
    print("OK test_operator_skill_effects stunned:", len(stunned))


def test_operator_attack_effects():
    """attack@-prefixed skill effects apply on each attack while active."""
    from ark_emulator.operator_skills import ActiveSkillEffect
    from ark_emulator.attributes import Attributes as A
    from ark_emulator.entities import Enemy as E

    class FakeSkill:
        duration = 5.0
        range_id = ""
        blackboard = {}
        attack_effects = {"atk_scale": 0.3, "stun": 0.5}

    class FakeBattle:
        rng = None
        def __init__(self):
            from ark_emulator.rng import SystemRandomClone
            self.rng = SystemRandomClone(1)
            self.damage_log = []
            self.abnormal_log = []
            self.ops = []; self.enemies = []
        def get_operators(self): return self.ops
        def get_enemies(self): return self.enemies
        def get_tokens(self): return []
        def emit(self, *a): return None
        def apply_damage(self, t, amount, dt, source=None):
            self.damage_log.append(amount); t.take_damage(amount); return amount
        def apply_heal(self, *a): return 0
        def add_buff(self, u, b): return None
        def add_abnormal(self, u, f, s):
            self.abnormal_log.append((f, s)); return True
        def add_ep(self, *a): return None

    b = FakeBattle()
    op = type("OP", (), {"inst_id": 1, "attributes": A({"atk": 100}),
                          "pos_x": 0, "pos_y": 0, "dead": False,
                          "skill_controller": None})()
    eff = ActiveSkillEffect.__new__(ActiveSkillEffect)
    eff.controller = type("C", (), {"battle": b, "op": op})()
    eff.op = op
    eff.skill = FakeSkill()
    eff.remaining = 5.0
    eff.buffs = []
    eff.attack_effects = FakeSkill.attack_effects
    tgt = E("e", A({"maxHp": 500, "def": 0}), route_index=0, row=1, col=0)
    eff.apply_on_attack(tgt)
    assert b.damage_log and abs(b.damage_log[0] - 30) < 0.01
    assert b.abnormal_log and b.abnormal_log[0][0] == 0
    print("OK test_operator_attack_effects")


def test_operator_ep_damage():
    """Skill ep_damage_ratio applies element damage to enemies in range."""
    from ark_emulator.operator_skills import ActiveSkillEffect
    from ark_emulator.attributes import Attributes as A
    from ark_emulator.entities import Enemy as E

    class FakeSkill:
        duration = 5.0
        range_id = ""
        blackboard = {"ep_damage_ratio": 0.2}
        attack_effects = {}
        sp_cost = 0

    class FakeBattle:
        rng = None
        def __init__(self):
            from ark_emulator.rng import SystemRandomClone
            from ark_emulator.buffs import BuffSystem
            self.rng = SystemRandomClone(1)
            self.buffs = BuffSystem(self)
            self.ep_log = []; self.ops = []; self.enemies = []
        def get_operators(self): return self.ops
        def get_enemies(self): return self.enemies
        def get_tokens(self): return []
        def emit(self, *a): return None
        def apply_damage(self, *a): return 0
        def apply_heal(self, *a): return 0
        def add_buff(self, u, b): return self.buffs.apply(u, b)
        def add_abnormal(self, *a): return None
        def add_ep(self, u, t, amt):
            self.ep_log.append(amt)
            return self.buffs.update_ep(u, t, amt)

    b = FakeBattle()
    op = type("OP", (), {"inst_id": 1, "attributes": A({"atk": 100}),
                          "pos_x": 0, "pos_y": 0, "dead": False,
                          "skill_controller": None, "range_shape": [],
                          "row": 0, "col": 0})()
    eff = ActiveSkillEffect.__new__(ActiveSkillEffect)
    eff.controller = type("C", (), {"battle": b, "op": op})()
    eff.op = op
    eff.skill = FakeSkill()
    eff.remaining = 5.0
    eff.buffs = []
    eff.attack_effects = {}
    tgt = E("e", A({"maxHp": 2000, "def": 0, "epDamageResistance": 0}),
            route_index=0, row=1, col=0)
    b.enemies.append(tgt)
    eff.on_start()
    assert b.ep_log and abs(b.ep_log[0] - 20) < 0.01
    print("OK test_operator_ep_damage ep:", b.ep_log[0])


def test_char_damage_type():
    """Operator damage type from description (???? -> MAGICAL)."""
    from ark_emulator import Simulator as S
    from ark_emulator.consts import DamageType
    sim = S("level_main_01-01")
    cases = {"char_002_amiya": DamageType.MAGICAL,   # ??
             "char_149_scave": DamageType.PHYSICAL}   # ??
    for cid, expected in cases.items():
        op = type("OP", (), {"char_id": cid})()
        got = sim.battle._char_damage_type(op)
        assert got == expected, (cid, got, expected)
    print("OK test_char_damage_type")


def test_operator_multi_hit():
    """attack@times multi-hit (e.g. ???? 6 hits) applies per-hit damage."""
    from ark_emulator.operator_skills import ActiveSkillEffect
    from ark_emulator.attributes import Attributes as A
    from ark_emulator.entities import Enemy as E

    class FakeSkill:
        duration = 5.0
        range_id = ""
        blackboard = {}
        attack_effects = {"times": 4, "atk_scale": 0.55}
        sp_cost = 0

    class FakeBattle:
        rng = None
        def __init__(self):
            from ark_emulator.rng import SystemRandomClone
            self.rng = SystemRandomClone(1)
            self.damage_log = []; self.ops = []; self.enemies = []
        def get_operators(self): return self.ops
        def get_enemies(self): return self.enemies
        def get_tokens(self): return []
        def emit(self, *a): return None
        def apply_damage(self, t, amt, dt, source=None):
            self.damage_log.append(amt); t.take_damage(amt); return amt
        def apply_heal(self, *a): return 0
        def add_buff(self, *a): return None
        def add_abnormal(self, *a): return None
        def add_ep(self, *a): return None
        def _char_damage_type(self, op): return 0

    b = FakeBattle()
    op = type("OP", (), {"inst_id": 1, "attributes": A({"atk": 100}),
                          "pos_x": 0, "pos_y": 0, "dead": False,
                          "skill_controller": None, "row": 0, "col": 0,
                          "range_shape": [], "char_id": "t"})()
    eff = ActiveSkillEffect.__new__(ActiveSkillEffect)
    eff.controller = type("C", (), {"battle": b, "op": op})()
    eff.op = op
    eff.skill = FakeSkill()
    eff.remaining = 5.0
    eff.buffs = []
    eff.attack_effects = FakeSkill.attack_effects
    tgt = E("e", A({"maxHp": 500, "def": 0}), route_index=0, row=1, col=0)
    eff.apply_on_attack(tgt)
    assert len(b.damage_log) == 4 and abs(b.damage_log[0] - 55) < 0.01
    print("OK test_operator_multi_hit hits:", len(b.damage_log))


def test_operator_dot():
    """interval-based DoT skills tick periodically while active."""
    from ark_emulator.operator_skills import ActiveSkillEffect
    from ark_emulator.attributes import Attributes as A
    from ark_emulator.entities import Enemy as E

    class FakeSkill:
        duration = 5.0
        range_id = ""
        blackboard = {"interval": 1.0, "atk_scale": 0.3}
        attack_effects = {}
        sp_cost = 0

    class FakeBattle:
        tick = 0
        rng = None
        def __init__(self):
            from ark_emulator.rng import SystemRandomClone
            from ark_emulator.buffs import BuffSystem
            self.rng = SystemRandomClone(1)
            self.buffs = BuffSystem(self)
            self.damage_log = []; self.ops = []; self.enemies = []
        def get_operators(self): return self.ops
        def get_enemies(self): return self.enemies
        def get_tokens(self): return []
        def emit(self, *a): return None
        def apply_damage(self, t, amt, dt, source=None):
            self.damage_log.append(amt); t.take_damage(amt); return amt
        def apply_heal(self, *a): return 0
        def add_buff(self, *a): return None
        def add_abnormal(self, *a): return None
        def add_ep(self, *a): return None

    b = FakeBattle()
    op = type("OP", (), {"inst_id": 1, "attributes": A({"atk": 100}),
                          "pos_x": 0, "pos_y": 0, "dead": False,
                          "skill_controller": None, "row": 0, "col": 0,
                          "range_shape": [], "char_id": "t"})()
    eff = ActiveSkillEffect.__new__(ActiveSkillEffect)
    eff.controller = type("C", (), {"battle": b, "op": op})()
    eff.op = op
    eff.skill = FakeSkill()
    eff.remaining = 5.0
    eff.buffs = []
    eff.attack_effects = {}
    tgt = E("e", A({"maxHp": 2000, "def": 0, "magicResistance": 0}),
            route_index=0, row=1, col=0)
    b.enemies.append(tgt)
    for i in range(5 * 30):
        b.tick = i
        eff.tick(1 / 30)
    assert len(b.damage_log) == 5 and abs(b.damage_log[0] - 30) < 0.01
    print("OK test_operator_dot hits:", len(b.damage_log))


def test_web_config():
    """Live server /config saves squad + custom enemies and reloads."""
    from ark_emulator.live_server import LiveServer
    import json as _j, urllib.request as _ur

    import socket as _sk
    _s = _sk.socket(); _s.bind(("127.0.0.1", 0)); port = _s.getsockname()[1]; _s.close()
    sim = Simulator("level_main_01-01")
    srv = LiveServer(sim, port=port, speed=5.0, tick_interval=0.005)
    srv.start()
    try:
        time.sleep(0.6)
        squad = [{"charId": "char_002_amiya", "level": 50, "phase": 0,
                  "potential": 5, "skillLevels": [7, 7, 7]}]
        req = _ur.Request(f"http://127.0.0.1:{port}/config",
                          data=_j.dumps({"squad": squad}).encode(),
                          headers={"Content-Type": "application/json"},
                          method="POST")
        with _ur.urlopen(req, timeout=8) as r:
            d = _j.load(r)
        assert d.get("ok") and srv.sim.squad == squad
        with _ur.urlopen(f"http://127.0.0.1:{port}/config", timeout=5) as r:
            d2 = _j.load(r)
        assert d2.get("squad") == squad
    finally:
        srv.stop()
    print("OK test_web_config")


def test_token_deploy():
    """Token (summon) deploy with full attributes + attack loop."""
    from ark_emulator import Simulator as S
    sim = S("level_main_01-01")
    ok, res = sim.deploy_token("token_10002_kalts_mon3tr", 3, 4)
    assert ok
    sim.run_ticks(120)
    snap = sim.snapshot()
    assert len(snap["tokens"]) == 1
    t = snap["tokens"][0]
    assert t["maxHp"] > 2000 and t["atk"] > 500
    print("OK test_token_deploy Mon3tr hp:", t["maxHp"], "atk:", t["atk"])


def test_redeploy_cooldown():
    """Retreat starts a respawnTime cooldown; redeploy blocked until it ends."""
    from ark_emulator import Simulator as S
    sim = S("level_main_01-01")
    ok = None
    for _ in range(30 * 30):
        sim.run_ticks(1)
        ok, _ = sim.deploy("char_149_scave", 3, 4, direction=1)
        if ok:
            break
    assert ok
    sim.withdraw(sim.snapshot()["deployed"][0]["instId"])
    cd = sim.battle._redeploy_until["char_149_scave"]
    assert abs((cd - sim.battle.tick) / 30.0 - 70.0) < 1.0
    sim.battle._tick = cd - 1
    a, ra = sim.battle.deploy("char_149_scave", 3, 4, direction=1)
    assert not a and ra == "on_cooldown"
    sim.battle._tick = cd
    sim.battle.cost = 99
    b, _ = sim.battle.deploy("char_149_scave", 3, 4, direction=1)
    assert b
    print("OK test_redeploy_cooldown")


def test_ep_burst_effects():
    """Element burst applies real side-split effects + cooldown lock
    (PRTS: enemy SANITY = paralysis + locked element damage; enemy FIRE =
    mres-20 during the burst + locked element damage)."""
    from ark_emulator.buffs import BuffSystem
    from ark_emulator.entities import Enemy as E
    from ark_emulator.attributes import Attributes as A

    class B:
        tick = 10
        def __init__(self):
            self.buffs = BuffSystem(self)
            self.dmg = []; self.abn = []
        def emit(self, *a): return None
        def apply_damage(self, t, amt, dt, source=None):
            self.dmg.append((dt, amt)); t.take_damage(amt); return amt
        def apply_heal(self, *a): return 0
        def add_buff(self, u, b): return self.buffs.apply(u, b)
        def add_abnormal(self, u, f, s):
            self.abn.append((f, s)); return True
        def add_ep(self, u, t, amt): return self.buffs.update_ep(u, t, amt)

    b = B()
    e = E("e", A({"maxHp": 5000, "def": 0, "magicResistance": 0,
                  "epDamageResistance": 0}), route_index=0, row=0, col=0)
    for _ in range(20):
        b.buffs.update_ep(e, 0, 100)
    assert b.dmg == [], "enemy SANITY burst element damage is EP-locked"
    assert e.flag(39), "enemy SANITY burst must paralyse"
    assert e.abnormal[39]["layers"] == 3
    assert abs(b.buffs.get(e, "ep_burst_cd_0")["remaining_ticks"]
               - 10 * 30) < 2
    b2 = B()
    e2 = E("e2", A({"maxHp": 5000, "def": 0, "magicResistance": 0,
                    "epDamageResistance": 0}), route_index=0, row=0, col=0)
    for _ in range(20):
        b2.buffs.update_ep(e2, 2, 100)
    assert b2.dmg == [], "enemy FIRE burst element damage is EP-locked"
    mres = b2.buffs.get(e2, "ep_fire_mres")
    assert mres is not None and mres["add"] == -20.0
    print("OK test_ep_burst_effects")


def test_retreat_refund():
    """Retreat refunds 50% of deploy cost."""
    from ark_emulator import Simulator as S
    sim = S("level_main_01-01")
    ok = None
    for _ in range(30 * 30):
        sim.run_ticks(1)
        ok, _ = sim.deploy("char_149_scave", 3, 4, direction=1)
        if ok:
            break
    assert ok
    before = sim.battle.cost
    sim.withdraw(sim.snapshot()["deployed"][0]["instId"])
    after = sim.battle.cost
    assert abs((after - before) - 6.0) < 0.01, (before, after)
    print("OK test_retreat_refund refund:", after - before)


def test_cost_recovery_interval():
    """Cost recovers +1 per costIncreaseTime seconds; large values = none."""
    from ark_emulator import Simulator as S
    sim = S("level_main_01-01")          # costIncreaseTime=1.0
    sim.run_ticks(30 * 3)
    # precise periodic timer: +1 exactly at t=1/2/3s (10 + 3)
    assert abs(sim.battle.cost - 13.0) < 0.01, sim.battle.cost
    sim2 = S("level_memory_bgsnow_1")    # costIncreaseTime=3.0
    base = sim2.battle.initial_cost
    sim2.run_ticks(30 * 9)
    assert abs(sim2.battle.cost - (base + 3.0)) < 0.01,         (sim2.battle.cost, base)
    print("OK test_cost_recovery_interval")


def test_vanguard_cost_recovery():
    """Vanguard skills (????) recover cost periodically while active."""
    from ark_emulator.operator_skills import ActiveSkillEffect
    from ark_emulator.attributes import Attributes as A

    class B:
        tick = 0
        def __init__(self):
            self.cost = 20; self.max_cost = 99
        def battle_cost_add(self, amt):
            self.cost = min(self.max_cost, self.cost + amt)
        def get_operators(self): return []
        def get_enemies(self): return []
        def get_tokens(self): return []
        def apply_damage(self, *a): return 0
        def add_ep(self, *a): return None
        def emit(self, *a): return None

    b = B()
    op = type("OP", (), {"attributes": A({"atk": 0}),
                          "range_shape": []})()
    class FS:
        duration = 5.0
        range_id = ""
        blackboard = {"interval": 0.57, "cost": 1.0}
        attack_effects = {}
        sp_cost = 0
    eff = ActiveSkillEffect.__new__(ActiveSkillEffect)
    eff.controller = type("C", (), {"battle": b, "op": op})()
    eff.op = op
    eff.skill = FS()
    eff.remaining = 5.0
    eff.buffs = []
    eff.attack_effects = {}
    for i in range(3 * 30):
        b.tick = i
        eff.tick(1 / 30)
    assert b.cost > 20
    print("OK test_vanguard_cost_recovery cost:", b.cost)


if __name__ == "__main__":






    test_talents()
    test_custom_enemies()
    test_tile_effects_module()
    test_tile_actions_parse()
    test_global_buffs()
    test_squad_level_potential()
    test_squad_skill_levels()
    test_enemy_db_level()
    test_operator_skill_effects()
    test_operator_attack_effects()
    test_operator_ep_damage()
    test_char_damage_type()
    test_operator_multi_hit()
    test_operator_dot()
    test_live_server()
    test_web_config()
    test_token_deploy()
    test_redeploy_cooldown()
    test_ep_burst_effects()
    test_retreat_refund()
    test_cost_recovery_interval()
    test_vanguard_cost_recovery()
    print("all advanced feature tests passed")
