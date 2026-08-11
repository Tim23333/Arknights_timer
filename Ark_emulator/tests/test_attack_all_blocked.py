# -*- coding: utf-8 -*-
"""Centurion / pusher trait tests.

Both subclass traits read "attackAllBlocked" from data_class_traits.json:
a basic attack hits every enemy the operator currently blocks (PRTS
"simultaneously attack all blocked enemies"), snapshotted at windup and
pruned at the hit frame.
"""
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
    return sim, b


def _spawn(b, key, row, col, hp=99999.0, atk=0.0, **extra):
    attrs = {"maxHp": hp, "atk": atk, "def": 0.0}
    attrs.update(extra)
    b.spawn_enemy(key, 0, overrides={
        "attributes": attrs, "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def test_centurion_flag_and_attacks_all_blocked():
    sim, b = _battle()
    b.deploy("char_143_ghost", 3, 3)          # Specter (centurion, block 2)
    op = b.operators[0]
    assert op.trait_system is not None
    assert op.trait_system.attack_all_blocked() is True
    e1 = _spawn(b, "enemy_1000_gopro_2", 3, 3)
    e2 = _spawn(b, "enemy_1000_gopro_2", 3, 3)
    b._update_blocking()
    assert {e.blocked_by for e in (e1, e2)} == {op}
    hp0 = (e1.hp, e2.hp)
    for _ in range(90):
        b.tick_once()
    assert e1.hp < hp0[0] and e2.hp < hp0[1], (e1.hp, e2.hp)
    multi = [x for x in b.events.snapshot_events()
             if x["type"] == "attack"
             and set((x.get("data") or {}).get("targets") or [])
             == {e1.inst_id, e2.inst_id}]
    assert multi, "expected one multi-target attack event"


def test_pusher_attacks_all_blocked():
    sim, b = _battle()
    b.deploy("char_277_sqrrel", 3, 3)         # Shaw (pusher, block 2)
    op = b.operators[0]
    assert op.trait_system is not None
    assert op.trait_system.attack_all_blocked() is True
    e1 = _spawn(b, "enemy_1000_gopro_2", 3, 3)
    e2 = _spawn(b, "enemy_1000_gopro_2", 3, 3)
    b._update_blocking()
    assert {e.blocked_by for e in (e1, e2)} == {op}
    hp0 = (e1.hp, e2.hp)
    for _ in range(90):
        b.tick_once()
    assert e1.hp < hp0[0] and e2.hp < hp0[1], (e1.hp, e2.hp)


def test_no_blocked_enemies_means_no_attack():
    sim, b = _battle()
    b.deploy("char_143_ghost", 3, 3)
    op = b.operators[0]
    for _ in range(90):
        b.tick_once()
    events = [x for x in b.events.snapshot_events()
              if x["type"] == "attack"]
    assert not events, "centurion must idle when nothing is blocked"
    assert not op.dead


def test_dead_target_pruned_at_hit_frame():
    sim, b = _battle()
    b.deploy("char_143_ghost", 3, 3)
    op = b.operators[0]
    e1 = _spawn(b, "enemy_1000_gopro_2", 3, 3, hp=10.0)
    e2 = _spawn(b, "enemy_1000_gopro_2", 3, 3)
    b._update_blocking()
    assert {e.blocked_by for e in (e1, e2)} == {op}
    # windup with both targets, then the first dies before the hit frame
    b._operator_attack(op, e1, op.attributes.attack_interval(),
                       targets=[e1, e2])
    pa = b._pending_attack_live(op._pending_attack)
    assert pa is not None and len(pa["targets"]) == 2
    b.apply_damage(e1, 99999.0, DamageType.PHYSICAL, source=op)
    pa = b._pending_attack_live(op._pending_attack)
    assert pa is not None and len(pa["targets"]) == 1
    assert pa["target"] is e2
    pa["remaining"] = 0
    assert b._resolve_operator_attack(op, pa) is True
    assert e2.hp < e2.max_hp



