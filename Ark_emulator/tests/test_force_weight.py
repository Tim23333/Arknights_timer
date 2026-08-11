# -*- coding: utf-8 -*-
"""Force/weight (push/pull) mechanics tests based on PRTS 推与拉 tables."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import (
    PUSH_FORCE_TABLE,
    PULL_FORCE_TABLE,
    force_level_from,
    pull_displacement,
    pull_duration,
    pull_pulled_home,
    push_displacement,
    push_initial_speed,
)
from ark_emulator.consts import EnemyState


def _setup():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    return sim, b


def _enemy_at(b, row, col, mass=0):
    b.spawn_enemy("enemy_1000_gopro_2", 0,
                  overrides={"attributes": {"massLevel": mass}})
    e = b.enemies[-1]
    e.state = EnemyState.MOVE
    e.pos_x, e.pos_y = float(col), float(row)
    e.row, e.col = row, col
    return e


def _force_effect(b, op):
    from ark_emulator.operator_skills import ActiveSkillEffect
    eff = ActiveSkillEffect.__new__(ActiveSkillEffect)
    eff.controller = type("C", (), {"battle": b, "op": op})()
    eff.op = op
    return eff


def _slide_to_end(b, e, guard=120):
    n = 0
    while e.displacement is not None and n < guard:
        b.tick_once()
        n += 1
    return n


# ---- force-level math ----
def test_force_level_formula():
    assert force_level_from(1, 0) == 1
    assert force_level_from(1, 1) == 0
    assert force_level_from(2, 1) == 1
    assert force_level_from(3, 1) == 2
    assert force_level_from(1, 2) == -1
    assert force_level_from(1, 4) == -3
    assert force_level_from(11, 6) == 5
    assert force_level_from(1, None) == 1     # missing mass -> 0
    assert force_level_from(1, "x") == 1


def test_push_table_values():
    # 特效类 (effect) 列
    assert push_displacement(1, 0, "effect") == PUSH_FORCE_TABLE[1][3]
    assert abs(push_displacement(1, 0, "effect") - 1.98705) < 1e-9
    # 弹道类 (projectile) 列：同力度更远
    assert abs(push_displacement(1, 0, "projectile") - 2.13705) < 1e-9
    assert abs(push_displacement(3, 0, "projectile") - 3.52392) < 1e-9
    assert abs(push_displacement(3, 0, "effect") - 3.33058) < 1e-9
    # clamp: 受力等级 <= -3 -> 0
    assert push_displacement(1, 4, "effect") == 0.0
    assert push_displacement(3, 13, "projectile") == 0.0
    # 初始速度表
    assert push_initial_speed(3, 0) == 5.8


def test_pull_table_values():
    assert pull_duration(1, 3) == 0.5          # 受力等级 -2 < -1 -> 0.5s
    assert pull_duration(1, 2) == 1.0          # -1 -> 1s
    assert pull_duration(1, 1) == 1.0          # 0 -> 1s
    assert pull_pulled_home(1, 1) is True
    assert pull_pulled_home(11, 6) is True
    assert pull_pulled_home(1, 2) is False
    assert pull_displacement(1, 3, 3.0) == PULL_FORCE_TABLE[-2][4]   # d=3 -> 0.0325
    assert abs(pull_displacement(1, 2, 3.0) - 0.9240) < 1e-9         # d=3 -> 0.9240
    assert abs(pull_displacement(1, 2, 2.0) - 0.5699) < 1e-9         # d=2 -> 0.5699
    assert pull_displacement(1, 4, 2.5) == 0.0


# ---- push integration ----
def test_push_distance_by_weight():
    sim, b = _setup()
    b.deploy("char_1045_svash2", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    cases = [
        (0, 1.98705),   # 力度1 - 重量0 -> 受力等级1 (特效)
        (1, 1.56247),   # 力度1 - 重量1 -> 0
        (2, 0.37363),   # 力度1 - 重量2 -> -1
        (3, 0.08492),   # 力度1 - 重量3 -> -2
        (4, 0.0),       # 力度1 - 重量4 -> -3 不位移
        (13, 0.0),      # 大重量不位移
    ]
    for mass, want in cases:
        e = _enemy_at(b, 3, 4, mass=mass)
        eff._displace(e, 1.0)
        if want == 0.0:
            assert e.displacement is None, (mass, e.displacement)
        else:
            assert e.displacement is not None, mass
            assert abs(e.displacement["total"] - want) < 1e-6, (mass, e.displacement)
            _slide_to_end(b, e)


def test_push_higher_force_hits_further():
    sim, b = _setup()
    b.deploy("char_1045_svash2", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    e = _enemy_at(b, 3, 4, mass=1)
    eff._displace(e, 3.0)                     # 力度3 - 重量1 -> 受力等级2
    assert abs(e.displacement["total"] - 2.77347) < 1e-6
    assert e.displacement["force_level"] == 2


def test_push_projectile_kind_uses_projectile_column():
    sim, b = _setup()
    b.deploy("char_1045_svash2", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    e = _enemy_at(b, 3, 4)
    eff._displace(e, 1.0, kind="projectile")
    assert abs(e.displacement["total"] - 2.13705) < 1e-6
    assert e.displacement["kind"] == "projectile"


def test_push_decelerates_over_table_duration():
    """匀减速: 位移时长 = 2*distance/初速度，终点精确落表。"""
    sim, b = _setup()
    b.deploy("char_1045_svash2", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    e = _enemy_at(b, 3, 4)
    eff._displace(e, 3.0)                     # 受力等级3, v0=5.8
    d = e.displacement
    want_t = 2.0 * d["total"] / push_initial_speed(3, 0)
    assert abs(d["duration_total"] - want_t) < 1e-6
    n = _slide_to_end(b, e)
    assert abs(e.pos_x - (4.0 + 3.33058)) < 0.02, e.pos_x
    assert n > 20, n                            # 明显是渐进滑行而非瞬移


# ---- pull integration ----
def test_pull_force0_drags_to_front():
    sim, b = _setup()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    e = _enemy_at(b, 3, 6, mass=1)            # 3 格前, 力度1 - 重量1 -> 0
    eff._displace(e, -1.0)
    d = e.displacement
    assert d is not None
    assert d["kind"] == "pull"
    assert abs(d["duration_total"] - 1.0) < 1e-9
    # 拉到干员前方 0.5 格（拉力起点）
    _slide_to_end(b, e)
    assert abs(e.pos_x - 3.5) < 0.05, e.pos_x


def test_pull_force0_vs_heavy_still_home():
    sim, b = _setup()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    e = _enemy_at(b, 3, 6, mass=6)
    eff._displace(e, -11.0)                   # 捕网力度11 - 重量6 -> 5
    d = e.displacement
    assert d is not None and d["force_level"] == 5
    _slide_to_end(b, e)
    assert abs(e.pos_x - 3.5) < 0.05, e.pos_x


def test_pull_weak_pulls_short_distance():
    sim, b = _setup()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    # 力度1 - 重量2 -> -1: d=3 时理想拖拽距离 0.9240
    e = _enemy_at(b, 3, 6, mass=2)
    eff._displace(e, -1.0)
    d = e.displacement
    assert d is not None
    assert abs(d["total"] - 0.9240) < 1e-6, d
    assert abs(d["duration_total"] - 1.0) < 1e-9
    _slide_to_end(b, e)
    assert abs(e.pos_x - (6.0 - 0.9240)) < 0.02, e.pos_x


def test_pull_too_heavy_no_movement():
    sim, b = _setup()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    e = _enemy_at(b, 3, 6, mass=4)            # 力度1 - 重量4 -> -3
    eff._displace(e, -1.0)
    assert e.displacement is None


def test_pull_duration_half_when_level_minus2():
    sim, b = _setup()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eff = _force_effect(b, op)
    e = _enemy_at(b, 3, 6, mass=3)            # 力度1 - 重量3 -> -2
    eff._displace(e, -1.0)
    d = e.displacement
    assert d is not None
    assert abs(d["duration_total"] - 0.5) < 1e-9


def test_pull_release_block_and_snapshot():
    sim, b = _setup()
    b.deploy("char_149_scave", 3, 5)
    op = b.operators[0]
    e = _enemy_at(b, 3, 6, mass=1)
    e.attributes.base["moveSpeed"] = 0.0
    for _ in range(10):
        b.tick_once()
    assert e.blocked_by is op
    eff = _force_effect(b, op)
    eff._displace(e, -1.0)
    assert e.blocked_by is None
    snap = e.to_dict()
    disp = snap["displacement"]
    assert disp is not None
    assert disp["kind"] == "pull"
    assert disp["forceLevel"] == 0
    assert "remainingSeconds" in disp and "totalSeconds" in disp
    _slide_to_end(b, e)
    assert e.to_dict()["displacement"] is None


def test_slide_stops_on_impassable_tile():
    from ark_emulator.map import TileData
    sim, b = _setup()
    b.deploy("char_1045_svash2", 3, 3)
    op = b.operators[0]
    idx = b.map.idx(3, 5)
    b.map.tiles[idx] = TileData(idx, {"tileKey": "tile_wall",
                                      "passableMask": 0,
                                      "buildableType": 0, "heightType": 2})
    e = _enemy_at(b, 3, 4)
    eff = _force_effect(b, op)
    eff._displace(e, 3.0)                     # 推力 3.33 格, 撞墙于 col5
    _slide_to_end(b, e)
    assert e.pos_x < 5.0, e.pos_x


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
    print("all force/weight tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
