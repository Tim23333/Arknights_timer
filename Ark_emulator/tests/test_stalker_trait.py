# -*- coding: utf-8 -*-
"""Stalker (\u4f0f\u51fb\u5ba2) trait tests: basic attacks hit EVERY enemy
inside the operator attack range, 50% physical & magical dodge (defensive
damageHitrate 50), and tauntLevel -1 (enemies avoid attacking her)."""
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
    b.cost_increase_time = 1e7     # no natural recovery
    b.battle_cost_add(100.0)
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True
    return sim, b


def _spawn(b, key, row, col, hp=50000.0, atk=0.0, **extra):
    attrs = {"maxHp": hp, "atk": atk, "def": 0.0, "moveSpeed": 0.0}
    attrs.update(extra)
    b.spawn_enemy(key, 0, overrides={"attributes": attrs,
                                     "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_stalker_stats_and_dodge_attrs():
    sim, b = _battle()
    b.deploy("char_355_ethan", 3, 3)          # \u4f0a\u6851 (stalker)
    op = b.operators[0]
    ts = op.trait_system
    assert ts.is_stalker()
    assert abs(ts.stalker_dodge_prob() - 0.5) < 1e-9
    assert abs(op.attributes.get("damageHitratePhysical") - 50.0) < 1e-9
    assert abs(op.attributes.get("damageHitrateMagical") - 50.0) < 1e-9
    assert op.attributes.get("tauntLevel") == -1, "base data taunt -1"


def test_stalker_attacks_all_in_range():
    sim, b = _battle()
    b.deploy("char_355_ethan", 3, 3)
    op = b.operators[0]
    atk = float(op.attributes.get("atk"))
    e1 = _spawn(b, "enemy_1000_gopro_2", 3, 4)   # in range
    e2 = _spawn(b, "enemy_1000_gopro_2", 3, 5)   # in range (y-1 col +2)
    e3 = _spawn(b, "enemy_1000_gopro_2", 2, 4)   # in range
    far = _spawn(b, "enemy_1000_gopro_2", 6, 6)  # out of range
    _land_attack(b, op, e1)
    for e in (e1, e2, e3):
        assert abs((50000.0 - e.hp) - atk) < 0.01, (e.inst_id, e.hp, atk)
    assert far.hp == 50000.0, "out-of-range enemy must not be hit"
    evs = b.events.snapshot_events()
    att = [x for x in evs if x["type"] == "attack"
           and (x.get("data") or {}).get("unit") == op.inst_id]
    assert att and sorted((att[-1].get("data") or {}).get("targets", [])) == \
        sorted([e1.inst_id, e2.inst_id, e3.inst_id]), att[-1]


def test_stalker_dodge_misses_about_half():
    sim, b = _battle()
    b.deploy("char_355_ethan", 3, 3)
    op = b.operators[0]
    op.hp = 1e9                       # never die during the rolls
    src = _spawn(b, "enemy_1000_gopro_2", 3, 4, atk=100.0)
    n = 200
    landed = 0
    for _ in range(n):
        r = b.apply_damage(op, 100.0, DamageType.PHYSICAL, source=src)
        if r.amount > 0:
            landed += 1
    ratio = landed / float(n)
    assert 0.3 <= ratio <= 0.7, ratio
    # magical dodge works too
    landed = 0
    for _ in range(n):
        r = b.apply_damage(op, 100.0, DamageType.MAGICAL, source=src)
        if r.amount > 0:
            landed += 1
    ratio = landed / float(n)
    assert 0.3 <= ratio <= 0.7, ratio


def test_stalker_low_taunt():
    sim, b = _battle()
    b.deploy("char_355_ethan", 3, 3)
    b.deploy("char_263_skadi", 3, 4)
    from ark_emulator.targeting import HateSystem
    h = HateSystem(b)
    ethan, skadi = b.operators[0], b.operators[1]
    assert h.operator_hate(ethan) < h.operator_hate(skadi)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
