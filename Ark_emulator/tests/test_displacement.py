# -*- coding: utf-8 -*-
"""Displacement (push/pull) mechanics tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState
from ark_emulator.map import TileData


def _setup():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    return sim, b


def _enemy_at(b, x, y):
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e = b.enemies[-1]
    e.state = EnemyState.MOVE
    e.pos_x, e.pos_y = float(x), float(y)
    e.row, e.col = int(y), int(x)
    return e


def test_push_moves_exact_destination():
    sim, b = _setup()
    e = _enemy_at(b, 3, 3)
    b.displace(e, 0, 1, 2.0)         # push right 2 tiles
    guard = 0
    while e.displacement is not None and guard < 90:
        b.tick_once()
        guard += 1
    assert abs(e.pos_x - 5.0) < 0.05 and abs(e.pos_y - 3.0) < 0.05, (
        e.pos_x, e.pos_y)
    assert e.displacement is None


def test_pull_toward_operator():
    sim, b = _setup()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    e = _enemy_at(b, 6, 3)
    # pull toward operator by 3 tiles (source at col 3)
    b.displace(e, 0, -1, 3.0)
    guard = 0
    while e.displacement is not None and guard < 90:
        b.tick_once()
        guard += 1
    assert abs(e.pos_x - 3.0) < 0.05 and abs(e.pos_y - 3.0) < 0.05, (
        e.pos_x, e.pos_y)


def test_push_into_hole_kills():
    sim, b = _setup()
    idx = b.map.idx(3, 5)
    b.map.tiles[idx] = TileData(idx, {"tileKey": "tile_hole",
                                      "buildableType": 0, "passableMask": 0,
                                      "heightType": 1})
    e = _enemy_at(b, 3, 3)
    b.displace(e, 0, 1, 2.0)         # lands on the hole at (3,5)
    guard = 0
    while not e.dead and guard < 60:
        b.tick_once()
        guard += 1
    assert e.dead, "enemy should fall into the hole"
    evs = [x["type"] for x in b.events.snapshot_events()]
    assert "enemy_falldown" in evs, evs


def _force_effect(b, op):
    from ark_emulator.operator_skills import ActiveSkillEffect
    eff = ActiveSkillEffect.__new__(ActiveSkillEffect)
    eff.controller = type("C", (), {"battle": b, "op": op})()
    eff.op = op
    return eff


def test_force_skill_displaces():
    sim, b = _setup()
    b.deploy("char_1045_svash2", 3, 3)
    op = b.operators[0]
    # enemy directly in front (to the right): directional push along facing
    e = _enemy_at(b, 4, 3)
    eff = _force_effect(b, op)
    eff._displace(e, 1.0)
    assert e.displacement is not None
    assert e.displacement["dc"] == 1    # facing right -> push right
    assert e.displacement["dr"] == 0
    assert e.displacement["force_level"] == 1   # ??1 - ??0


def test_force_skill_radial_correction():
    sim, b = _setup()
    b.deploy("char_1045_svash2", 3, 3)
    op = b.operators[0]
    # enemy below: 90? off the facing axis -> radial push + ???? -2
    e = _enemy_at(b, 3, 4)
    eff = _force_effect(b, op)
    eff._displace(e, 1.0)
    assert e.displacement is not None
    assert e.displacement["dr"] == 1    # pushed down (radial, away from op)
    assert e.displacement["dc"] == 0
    assert e.displacement["force_level"] == -1  # 1 - 0 - 2


def test_displacement_releases_block():
    sim, b = _setup()
    # blocker on the enemy's next flow step (3,5) for route 0
    b.deploy("char_149_scave", 3, 5)
    op = b.operators[0]
    e = _enemy_at(b, 4, 3)
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0
    e.attributes.base["moveSpeed"] = 0.0   # freeze route walking
    for _ in range(10):
        b.tick_once()
    assert e.blocked_by is op, e.blocked_by
    b.displace(e, 1, 0, 2.0)          # push down, away from the blocker
    guard = 0
    while e.displacement is not None and guard < 90:
        b.tick_once()
        guard += 1
    assert e.blocked_by is None, e.blocked_by
    assert e.state == EnemyState.MOVE
    assert not any(x.inst_id == e.inst_id
                   for x in op.blocked_enemies)
    # re-approach -> re-blocked
    # Re-enter on the route's upstream side.  Smoothed next nodes may point
    # several tiles forward, so the old ``op.col + 1`` position is already
    # downstream of this blocker and must not be blocked from behind.
    e.row, e.col = op.row, op.col - 1
    e.pos_x, e.pos_y = float(e.col), float(e.row)
    for _ in range(15):
        b.tick_once()
    assert e.blocked_by is op, e.blocked_by


def test_push_stops_at_wall():
    from ark_emulator.map import TileData
    sim, b = _setup()
    idx = b.map.idx(3, 5)
    b.map.tiles[idx] = TileData(idx, {"tileKey": "tile_wall",
                                      "passableMask": 0,
                                      "buildableType": 0, "heightType": 2})
    e = _enemy_at(b, 3, 3)
    b.displace(e, 0, 1, 4.0)       # push right through the wall at col 5
    guard = 0
    while e.displacement is not None and guard < 90:
        b.tick_once()
        guard += 1
    assert e.pos_x < 5.0, e.pos_x   # stopped before the wall


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
    print("all displacement tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
