# -*- coding: utf-8 -*-
"""Blessing (\u62a4\u4f51\u8005) trait tests: basic attacks deal MAGICAL
damage normally; while a skill is active the attack becomes a heal on the
most wounded friendly in range (atk * heal_scale, default 0.75)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True
    return sim, b


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_blessing_attack_magical_without_skill():
    sim, b = _battle()
    b.deploy("char_343_tknogi", 2, 3)         # \u6708\u79be (blessing)
    op = b.operators[0]
    ts = op.trait_system
    assert ts.is_blessing()
    assert abs(ts.blessing_heal_scale() - 0.75) < 1e-9
    assert b._char_damage_type(op) == DamageType.MAGICAL
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 500.0,
                       "magicResistance": 0.0, "moveSpeed": 0.0},
        "row": 2, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    atk = float(op.attributes.get("atk"))
    _land_attack(b, op, e)
    for _ in range(60):
        b.tick_once()
        if not b.projectiles:
            break
    assert abs((50000.0 - e.hp) - atk) < 0.01, e.hp


def test_blessing_heals_ally_while_skill_active():
    sim, b = _battle()
    b.deploy("char_343_tknogi", 2, 3)         # blessing
    b.deploy("char_263_skadi", 3, 3)          # ally in range
    op = b.operators[0]
    ally = b.operators[1]
    sc = op.skill_controller
    assert sc is not None
    ally.hp -= 500.0
    hp0 = ally.hp
    # no skill active -> still targets enemies
    from ark_emulator.targeting import HateSystem
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0,
                       "moveSpeed": 0.0},
        "row": 2, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    t0 = HateSystem(b).operator_target(op)
    assert t0 is e, "without a skill the blessing attacks enemies"
    # activate a skill -> attack becomes a heal on the wounded ally
    op.sp = 9999.0
    ok, _ = sc.activate(0)
    assert ok
    t1 = HateSystem(b).operator_target(op)
    assert t1 is ally, t1
    _land_attack(b, op, ally)
    atk = float(op.attributes.get("atk"))
    expect = hp0 + atk * 0.75
    assert abs(ally.hp - expect) < 0.2, (ally.hp, expect)
    assert e.hp == 50000.0, "no damage while healing"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
