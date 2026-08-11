# -*- coding: utf-8 -*-
"""Enemy attack range: top-level rangeRadius from enemy_database must drive
targeting (melee fallback 1.5, ranged uses the DB value)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _setup():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    # wait out the 0.5s deploy animation so the operator is targetable
    for _ in range(20):
        b.tick_once()
    return sim, b


def _place(b, key, row, col):
    b.spawn_enemy(key, 0)
    e = b.enemies[-1]
    e.pos_x, e.pos_y = float(col), float(row)
    e.row, e.col = row, col
    e.state = EnemyState.ATTACK  # stationary: no route movement
    return e


def test_range_merged_into_attributes():
    sim, b = _setup()
    # sgshot is a ranged unit with rangeRadius 2.0 in enemy_database
    e = _place(b, "enemy_10011_sgshot", 3, 5)
    assert abs(float(e.attributes.get("rangeRadius")) - 2.0) < 1e-6, \
        e.attributes.get("rangeRadius")
    # gopro has no real range -> placeholder 0.0 (melee fallback)
    e2 = _place(b, "enemy_1000_gopro_2", 3, 5)
    assert float(e2.attributes.get("rangeRadius") or 0) <= 0


def test_melee_out_of_range_no_attack():
    sim, b = _setup()
    op = b.operators[0]
    _place(b, "enemy_1000_gopro_2", 3, 5)  # dist 2.0 > melee 1.5
    hp0 = op.hp
    for _ in range(60):
        b.tick_once()
    assert abs(op.hp - hp0) < 0.5, (hp0, op.hp)


def test_melee_diagonal_hits_directly():
    sim, b = _setup()
    op = b.operators[0]
    _place(b, "enemy_1000_gopro_2", 4, 4)  # diagonal dist ~1.41 <= 1.5
    hp0 = op.hp
    for _ in range(60):
        b.tick_once()
    assert op.hp < hp0 - 0.5, (hp0, op.hp)
    # melee must hit directly: no projectile launched
    assert not b.projectiles, b.projectiles


def test_ranged_uses_db_range_and_projectile():
    sim, b = _setup()
    op = b.operators[0]
    _place(b, "enemy_10011_sgshot", 3, 5)  # dist 2.0 <= range 2.0
    hp0 = op.hp
    launched = []
    b.events.subscribe("attack", lambda ev: launched.append(ev))
    # sgshot: attack windup (~69 ticks) + projectile flight (~6 ticks)
    for _ in range(100):
        b.tick_once()
    assert op.hp < hp0 - 0.5, (hp0, op.hp)
    assert any(ev.type == "attack" and
               ev.data.get("type") == "projectile_launch"
               for ev in launched)


def test_ranged_out_of_db_range_no_attack():
    sim, b = _setup()
    op = b.operators[0]
    _place(b, "enemy_10011_sgshot", 3, 7)  # dist 4.0 > range 2.0
    hp0 = op.hp
    for _ in range(60):
        b.tick_once()
    assert abs(op.hp - hp0) < 0.5, (hp0, op.hp)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("OK", t.__name__)
    print("all enemy range tests passed")
