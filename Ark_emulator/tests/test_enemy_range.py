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


def test_mephisto_global_radius_is_healing_not_operator_attack():
    """Mephisto's rangeRadius=20 belongs to his three-target heal.

    It must never be interpreted as a full-map physical attack on operators.
    """
    sim, b = _setup()
    # Keep this focused on Mephisto; the stage's own melee wave would
    # otherwise reach the operator during the long repeated-cycle check.
    b.waves.update = lambda: []
    op = b.operators[0]
    mephisto = _place(b, "enemy_1507_mephi", 3, 8)
    mephisto.attack_timer = 0.0
    hp0 = op.hp
    for _ in range(220):
        b.tick_once()
    assert abs(op.hp - hp0) < 0.5, (hp0, op.hp)
    damage = [event for event in b.events.log
              if event.type == "damage"
              and event.data.get("source") == mephisto.inst_id
              and event.data.get("target") == op.inst_id]
    assert damage == [], [event.to_dict() for event in damage]


def test_mephisto_heals_three_lowest_hp_enemies():
    sim, b = _setup()
    mephisto = _place(b, "enemy_1507_mephi", 3, 8)
    allies = [_place(b, "enemy_1007_slime", row, 7)
              for row in (1, 2, 3, 4)]
    for index, ally in enumerate(allies, 1):
        ally.hp = ally.max_hp * index / 10.0
        ally.attack_timer = 999.0
    hp0 = [ally.hp for ally in allies]
    mephisto.attack_timer = 0.0
    b.tick_once()                 # lock the three lowest-HP hostile targets
    mephisto.attack_timer = 999.0  # isolate one healing action
    for _ in range(220):
        b.tick_once()
        if mephisto._pending_attack is None:
            break
    assert all(allies[i].hp > hp0[i] for i in range(3)), \
        [(ally.hp, hp0[i]) for i, ally in enumerate(allies)]
    assert abs(allies[3].hp - hp0[3]) < 0.5, (allies[3].hp, hp0[3])
    heals = [event for event in b.events.log
             if event.type == "heal"
             and event.data.get("source") == mephisto.inst_id]
    assert len(heals) == 3, [event.to_dict() for event in heals]


def test_main_05_10_opening_myrtle_is_not_hit_by_mephisto():
    """Regression for the live web repro: Myrtle at (4, 1), t=4.7667."""
    squad = [{"charId": "char_151_myrtle", "phase": 2, "level": 70,
              "skillIndex": 0}]
    sim = Simulator(level_id="level_main_05-10", squad=squad)
    b = sim.battle
    while b.tick < 143:
        b.tick_once()
    b.battle_cost_add(200)
    ok, _ = b.deploy("char_151_myrtle", 4, 1, direction=1, skill_index=0)
    assert ok
    myrtle = b.operators[-1]
    while b.tick < 24 * 30:
        b.tick_once()
    mephisto = next(enemy for enemy in b.enemies
                    if enemy.enemy_key == "enemy_1507_mephi")
    damage = [event for event in b.events.log
              if event.type == "damage"
              and event.data.get("source") == mephisto.inst_id
              and event.data.get("target") == myrtle.inst_id]
    assert damage == [], [event.to_dict() for event in damage]
    assert abs(myrtle.hp - myrtle.max_hp) < 0.5, \
        (myrtle.hp, myrtle.max_hp)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("OK", t.__name__)
    print("all enemy range tests passed")
