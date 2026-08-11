# -*- coding: utf-8 -*-
"""Enemy normal-attack hit frames: damage/projectile lands at the spine
OnAttack frame (hit_frame_ratio * interval), not at attack start."""
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
    for _ in range(20):
        b.tick_once()
    return sim, b


def _place(b, key, row, col):
    b.spawn_enemy(key, 0)
    e = b.enemies[-1]
    e.pos_x, e.pos_y = float(col), float(row)
    e.row, e.col = row, col
    e.state = EnemyState.ATTACK  # stationary
    return e


def test_melee_damage_waits_for_hit_frame():
    sim, b = _setup()
    op = b.operators[0]
    e = _place(b, "enemy_1000_gopro_2", 3, 4)  # adjacent, dist 1.0
    hp0 = op.hp
    for _ in range(5):
        b.tick_once()
    assert abs(op.hp - hp0) < 0.5, "damage landed before the hit frame"
    landed = None
    for i in range(40):
        b.tick_once()
        if op.hp < hp0 - 0.5:
            landed = i
            break
    assert landed is not None, "melee damage never landed"
    # gopro: interval 1.4s, hit ratio 0.5 -> hit at ~21 ticks after start
    assert 12 <= landed <= 30, landed


def test_ranged_projectile_launches_at_hit_frame():
    sim, b = _setup()
    op = b.operators[0]
    _place(b, "enemy_10011_sgshot", 3, 5)  # dist 2.0 <= range 2.0
    launches = []
    b.events.subscribe("attack", lambda ev: launches.append(ev))
    first = None
    for i in range(100):
        b.tick_once()
        for ev in launches:
            if ev.data.get("type") == "projectile_launch":
                first = ev.tick
                break
        if first is not None:
            break
    assert first is not None, "no projectile launched"
    # sgshot attacks at global tick 35: interval 3.5s, hit ratio ~0.65
    # -> launch at ~35 + 69 = 104 (never before the hit frame)
    assert first >= 45, f"projectile launched too early at tick {first}"
    assert first <= 125, first


def test_pending_attack_exposed_in_snapshot():
    sim, b = _setup()
    op = b.operators[0]
    _place(b, "enemy_1000_gopro_2", 3, 4)
    for _ in range(3):
        b.tick_once()
    e = b.enemies[0]
    snap = sim.snapshot()
    enemy_snap = next(x for x in snap["enemies"] if x.get("key") == "enemy_1000_gopro_2")
    pa = enemy_snap.get("pendingAttack")
    assert pa is not None, "pendingAttack missing during windup"
    assert pa["target"] == op.inst_id and pa["ranged"] is False
    # first attack lands at ~tick 21; the next windup starts at ~tick 42,
    # so at total tick 33 the first attack is fully resolved
    for _ in range(30):
        b.tick_once()
    snap2 = sim.snapshot()
    enemy_snap2 = next(x for x in snap2["enemies"] if x.get("key") == "enemy_1000_gopro_2")
    assert enemy_snap2.get("pendingAttack") is None, enemy_snap2.get("pendingAttack")


def test_skill_damage_waits_for_hit_frame():
    """Skill effects land at the spine OnAttack hit frame (sgcat bigAttack
    hits at 0.5s = 15 frames after the cast starts), not immediately."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    for _ in range(20):
        b.tick_once()
    op = b.operators[0]
    b.spawn_enemy("enemy_10020_sgcat", 0)
    e = b.enemies[-1]
    e.row, e.col = op.row, op.col
    e.pos_x, e.pos_y = float(op.col), float(op.row)
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    s = next(sk for sk in sc.skills if sk.prefab_key == "bigAttack")
    assert s.hit_times and abs(s.hit_times[0] - 0.5) < 0.2, s.hit_times
    cast_tick = b.tick
    sc._start_cast((s, op))
    dmg_tick = None
    for _ in range(60):
        # the battle AI drives the skill controller once per tick
        b.tick_once()
        for ev in b.events.log:
            if ev.type == "damage" and ev.data.get("target") == op.inst_id:
                dmg_tick = ev.tick
                break
        if dmg_tick is not None:
            break
    assert dmg_tick is not None, "no skill damage landed"
    delay = dmg_tick - cast_tick
    assert 12 <= delay <= 22, (dmg_tick, cast_tick, delay)


def test_operator_melee_waits_for_hit_frame():
    """Operator melee damage lands at the spine hit frame (scave ~16 frames
    for a 1.05s attack), not at the attack start."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    for _ in range(20):
        b.tick_once()
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    enemy = b.enemies[-1]
    enemy.row, enemy.col = 3, 4
    enemy.pos_x, enemy.pos_y = 4.0, 3.0
    enemy.state = EnemyState.COMBAT
    hp0 = enemy.hp
    for _ in range(5):
        b.tick_once()
    assert abs(enemy.hp - hp0) < 0.5, "damage landed before the hit frame"
    landed = None
    for i in range(40):
        b.tick_once()
        if enemy.hp < hp0 - 0.5:
            landed = i
            break
    assert landed is not None, "operator damage never landed"
    assert 10 <= landed <= 25, landed


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("OK", t.__name__)
    print("all attack timing tests passed")
