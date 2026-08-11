"""Projectile system tests (flight frames + hit settlement)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.attributes import Attributes
from ark_emulator.consts import DamageType
from ark_emulator.entities import Enemy, Operator
from ark_emulator.projectiles import Projectile, projectile_speed


def test_flight_frames():
    src = Enemy("enemy_test", Attributes({"maxHp": 1000, "atk": 100,
                                          "baseAttackTime": 1.0,
                                          "attackSpeed": 100}),
                route_index=0, row=0, col=0)
    src.pos_x, src.pos_y = 0.0, 0.0
    tgt = Operator("char_test", Attributes({"maxHp": 500, "def": 0,
                                            "baseAttackTime": 1.0,
                                            "attackSpeed": 100}),
                   row=0, col=5)
    tgt.pos_x, tgt.pos_y = 5.0, 0.0
    p = Projectile(src, tgt, 10.0, DamageType.PHYSICAL, key="test")
    assert p.distance == 5.0
    assert p.flight_frames == 15          # 5 grids @ 10 grids/s = 0.5s = 15f
    frames = 0
    while not p.dead and frames < 100:
        p.update(1 / 30.0)
        frames += 1
    assert p.hit and p.travel_t >= 0.49
    print("OK test_flight_frames hit_frames:", frames)


def test_speed_lookup():
    assert projectile_speed("projectile_faust_s1") == 10.0
    assert projectile_speed("projectile_enemy_sgshot") == 10.0
    # exact extracted speed table (was 8.0 under the old heuristic)
    assert projectile_speed("projectile_enemy_magic_ball") == 10.0
    assert projectile_speed("") == 10.0
    print("OK test_speed_lookup")


def test_projectile_dict():
    src = Enemy("e", Attributes({"maxHp": 10, "atk": 1}), route_index=0,
                row=0, col=0)
    tgt = Operator("o", Attributes({"maxHp": 10, "def": 0}), row=0, col=2)
    p = Projectile(src, tgt, 10.0, key="k")
    d = p.to_dict()
    assert d["key"] == "k" and d["flightFrames"] == 6
    assert "pos" in d and "distance" in d
    print("OK test_projectile_dict", d["flightFrames"], "frames")


def test_operator_ranged_damage_lands():
    """Regression: ranged projectile damage must land in the real battle
    (hit callback wrapper used to swallow default damage)."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState

    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    # amiya is ranged (caster); deploy 4 tiles away from the route start
    b.deploy("char_002_amiya", 2, 6, direction=1)   # highland
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 1700.0, "atk": 0.0,
                         "def": 0.0, "moveSpeed": 0.0},
        "row": 2, "col": 7})
    enemy = b.enemies[0]
    enemy.state = EnemyState.COMBAT
    hp0 = enemy.max_hp
    # let the battle run until the projectile lands
    for _ in range(120):
        b.tick_once()
        if enemy.dead or any(not getattr(p, "dead", True)
                             for p in b.projectiles) is False:
            pass
        if not b.projectiles and enemy.hp < hp0:
            break
    assert enemy.hp < hp0, (enemy.hp, hp0)
    print("OK test_operator_ranged_damage_lands", round(hp0 - enemy.hp, 1))


def test_ranged_operator_basic_attack_launches_projectile():
    """Ranged operators (position 2) fire a projectile for basic attacks;
    damage settles on projectile hit, after the launch tick."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState

    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_1027_greyy2", 2, 3, direction=1)   # bombarder, ranged
    op = b.operators[0]
    assert op.position == 2
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 99999, "atk": 0, "def": 0},
        "row": 2, "col": 4})
    enemy = b.enemies[-1]
    enemy.state = EnemyState.COMBAT
    launch = hit = None
    hp0 = enemy.hp
    for _ in range(200):
        b.tick_once()
        for x in b.events.snapshot_events()[-6:]:
            if x["type"] != "attack":
                continue
            if x["data"].get("type") == "projectile_launch" and launch is None:
                launch = x["tick"]
            if x["data"].get("type") == "projectile_hit" and hit is None:
                hit = x["tick"]
        if hit is not None:
            break
    assert launch is not None, "ranged basic attack must launch a projectile"
    assert hit is not None and hit > launch, (launch, hit)
    assert enemy.hp < hp0, "projectile damage did not land"


def test_melee_operator_basic_attack_no_projectile():
    """Melee guards (position 1) resolve basic attacks directly at the hit
    frame without spawning a projectile."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState

    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 3, direction=1)      # vanguard, melee
    op = b.operators[0]
    assert op.position == 1
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 99999, "atk": 0, "def": 0},
        "row": 3, "col": 4})
    enemy = b.enemies[-1]
    enemy.state = EnemyState.COMBAT
    hp0 = enemy.hp
    for _ in range(120):
        b.tick_once()
    launches = [x for x in b.events.snapshot_events()
                if x["type"] == "attack" and
                x["data"].get("type") == "projectile_launch"]
    assert not launches, "melee attack must not launch a projectile"
    assert enemy.hp < hp0, "melee damage did not land"


if __name__ == "__main__":
    test_flight_frames()
    test_speed_lookup()
    test_projectile_dict()
    test_operator_ranged_damage_lands()
    print("all projectile tests passed")
