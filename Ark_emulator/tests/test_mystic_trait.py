# -*- coding: utf-8 -*-
"""Mystic (\u79d8\u672f\u5e08) stored-attack trait tests: with no target in
range the operator stores one charge per attack interval (max `times`); when
a target appears the current attack plus all stored charges fire together at
full ATK (merge_cnt charges merge into a single stronger hit, e.g. \u7ef4\u4f0a)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7     # no natural recovery
    b.battle_cost_add(100.0)
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True
    # static decoy far away: keeps the battle running (victory only
    # triggers when waves are finished AND no enemies are left)
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 1e9, "atk": 0.0, "def": 0.0,
                       "moveSpeed": 0.0},
        "row": 7, "col": 7})
    for e in b.enemies:
        e.state = EnemyState.COMBAT
    return sim, b


def _spawn_enemy(b, row, col, hp=50000.0):
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": 0.0,
                       "moveSpeed": 0.0, "magicResistance": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _damage_sum(b, e):
    return sum(x["data"]["amount"] for x in b.events.snapshot_events()
               if x["type"] == "damage" and x["data"]["target"] == e.inst_id)


def test_mystic_stores_up_to_times_without_target():
    sim, b = _battle()
    b.deploy("char_469_indigo", 2, 3)        # \u6df1\u975b (mystic)
    op = b.operators[0]
    ts = op.trait_system
    assert ts.is_mystic()
    assert ts.mystic_max_times() == 3
    assert ts.mystic_merge_cnt() == 1
    sim.run_ticks(280)                       # ~3.1 s per storage x 3
    assert op._mystic_stored == 3, op._mystic_stored
    sim.run_ticks(90)
    assert op._mystic_stored == 3, "full storage must idle, not overflow"


def test_mystic_releases_all_stored_charges_on_target():
    sim, b = _battle()
    b.deploy("char_469_indigo", 2, 3)
    op = b.operators[0]
    sim.run_ticks(280)                       # fill 3 charges
    atk = float(op.attributes.get("atk"))
    e = _spawn_enemy(b, 2, 5)                # inside 3-13 range
    op.attack_timer = 0.01                  # fire on the next tick
    sim.run_ticks(60)                        # windup ~41f + flight ~6f
    total = _damage_sum(b, e)
    assert abs(total - atk * 4.0) < atk * 0.05, (total, atk)
    assert abs(e.hp - (50000.0 - atk * 4.0)) < atk * 0.05, e.hp
    assert op._mystic_stored == 0, "charges consumed after release"


def test_mystic_merge_cnt_weiyi():
    sim, b = _battle()
    b.deploy("char_4226_veen", 2, 3)         # \u7ef4\u4f0a: times 9, merge 3
    op = b.operators[0]
    ts = op.trait_system
    assert ts.mystic_max_times() == 9
    assert ts.mystic_merge_cnt() == 3
    op._mystic_stored = 9                    # skip the 27 s wait
    atk = float(op.attributes.get("atk"))
    e = _spawn_enemy(b, 2, 5)
    op.attack_timer = 0.01                  # fire on the next tick
    sim.run_ticks(30)
    total = _damage_sum(b, e)
    # current attack (1x) + 3 merged groups (3x each) = 10x ATK
    assert abs(total - atk * 10.0) < atk * 0.05, (total, atk)
    assert abs(e.hp - (50000.0 - atk * 10.0)) < atk * 0.05, e.hp
    assert op._mystic_stored == 0


def test_mystic_attack_is_magical():
    sim, b = _battle()
    b.deploy("char_469_indigo", 2, 3)
    op = b.operators[0]
    from ark_emulator.consts import DamageType
    assert b._char_damage_type(op) == DamageType.MAGICAL


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
