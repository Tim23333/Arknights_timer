# -*- coding: utf-8 -*-
"""Level predefines (traps/towers/NPC allies) spawn tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.predefines import parse_level_predefines


def test_parse_predefines_structure():
    d = parse_level_predefines("level_act11d0_03")
    assert len(d.get("tokenInsts") or []) == 1
    t = d["tokenInsts"][0]
    assert t["characterKey"] == "trap_014_tower"
    assert (t["row"], t["col"]) == (3, 6)
    assert t["level"] == 1


def test_predefined_token_spawns():
    sim = Simulator(level_id="level_act11d0_03")
    sim.run_ticks(30)
    snap = sim.snapshot()
    assert snap["predefines"]["tokens"] == 1
    toks = [t for t in snap["tokens"] if t["tokenId"] == "trap_014_tower"]
    assert toks and (toks[0]["row"], toks[0]["col"]) == (3, 6), toks


def test_predefined_character_spawns():
    sim = Simulator(level_id="level_a001_01")
    sim.run_ticks(30)
    snap = sim.snapshot()
    assert snap["predefines"]["characters"] == 1
    ops = [o for o in snap["deployed"] if o["charId"] == "char_220_grani"]
    assert ops and (ops[0]["row"], ops[0]["col"]) == (3, 4), ops


def test_hidden_predefined_activation():
    sim = Simulator(level_id="level_act11d0_03")
    sim.run_ticks(15)
    b = sim.battle
    b.predefines["tokenInsts"] = [{
        "row": 2, "col": 2, "characterKey": "trap_014_tower",
        "alias": "trap_014_tower#9", "level": 1, "hidden": True,
    }]
    b._predefined_pending = [("token", b.predefines["tokenInsts"][0])]
    before = len(b.tokens)
    spawned = b.activate_predefined_alias("trap_014_tower#9")
    assert len(spawned) == 1
    assert len(b.tokens) == before + 1
    assert b._predefined_pending == []


def test_predefined_tower_attacks():
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_act11d0_03")
    sim.run_ticks(15)
    b = sim.battle
    tower = b.tokens[0]
    assert tower.token_skill_bb.get("tower_t_4[magic_attack].atk_scale")         == 0.05
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = tower.row + 1, tower.col
    enemy.pos_x, enemy.pos_y = float(enemy.col), float(enemy.row)
    enemy.state = EnemyState.COMBAT
    hp0 = enemy.hp
    for _ in range(30 * 6):
        b.tick_once()
    # tower deals maxHp * 5% magical per 1.5s hit
    assert hp0 - enemy.hp >= 10, hp0 - enemy.hp


def test_predefined_tower_heals():
    from ark_emulator.entities import Operator
    from ark_emulator.attributes import Attributes
    sim = Simulator(level_id="level_act11d0_03")
    sim.run_ticks(15)
    b = sim.battle
    tower = b.tokens[0]
    op = Operator("char_test", Attributes({
        "maxHp": 10000, "atk": 0, "def": 9999, "blockCnt": 0,
        "baseAttackTime": 99.0, "attackSpeed": 100}),
        row=tower.row, col=tower.col + 1, deploy_tick=-100)
    op.pos_x, op.pos_y = float(op.col), float(op.row)
    b.operators.append(op)
    op.hp = 100.0
    for _ in range(30 * 12):
        b.tick_once()
    assert op.hp >= 115.0, op.hp   # ~+10 per 5s


def test_wave_activate_and_lifecycle():
    # level_act12d0_tr01: ACTIVATE_PREDEFINED at t=1.0 (trap_016_peon#1)
    sim = Simulator(level_id="level_act12d0_tr01")
    sim.run_ticks(30 * 3)
    b = sim.battle
    peons = [t for t in b.tokens if t.token_id == "trap_016_peon"]
    assert peons, "wave ACTIVATE_PREDEFINED should spawn the peon"
    # TRIGGER_PREDEFINED
    u = b._predefined_unit("trap_016_peon")
    assert u is not None
    r = b.trigger_predefined("trap_016_peon")
    assert r is not None
    # WITHDRAW_PREDEFINED
    before = len(b.tokens)
    r2 = b.withdraw_predefined("trap_016_peon")
    assert r2 is not None
    assert len(b.tokens) == before - 1
    evs = [x["type"] for x in b.events.snapshot_events()]
    assert "predefined_triggered" in evs
    assert "predefined_withdrawn" in evs


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
    print("all predefines tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
