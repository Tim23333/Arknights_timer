# -*- coding: utf-8 -*-
"""Exact range_table shapes + deployment direction rotation tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.battle import range_offsets_rotated
from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def test_exact_range_shapes():
    r = sorted(range_offsets_rotated("3-3", 1))
    assert (0, 0) in r and (0, 3) in r and (-1, 0) in r and (1, 3) in r
    # 12 cells (4 cols x 3 rows)
    assert len(r) == 12, len(r)
    r1 = sorted(range_offsets_rotated("1-1", 1))
    assert r1 == [(0, 0), (0, 1)], r1


def test_range_rotation():
    up = sorted(range_offsets_rotated("1-1", 0))
    assert up == [(-1, 0), (0, 0)], up          # self + tile above
    down = sorted(range_offsets_rotated("1-1", 2))
    assert down == [(0, 0), (1, 0)], down
    left = sorted(range_offsets_rotated("1-1", 3))
    assert left == [(0, -1), (0, 0)], left


def test_direction_affects_attacks():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3, direction=1)   # 1-1 facing right
    op = b.operators[0]
    assert sorted(op.range_shape) == [(0, 0), (0, 1)]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e_right = b.enemies[0]
    e_right.row, e_right.col = 3, 4
    e_right.pos_x, e_right.pos_y = 4.0, 3.0
    e_right.state = EnemyState.COMBAT
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e_up = b.enemies[-1]
    e_up.row, e_up.col = 2, 3
    e_up.pos_x, e_up.pos_y = 3.0, 2.0
    e_up.state = EnemyState.COMBAT
    hp_r, hp_u = e_right.hp, e_up.hp
    for _ in range(30 * 4):
        b.tick_once()
    assert e_right.hp < hp_r, "right enemy should be attacked"
    assert abs(e_up.hp - hp_u) < 0.5, "up enemy out of range"


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
    print("all range tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
