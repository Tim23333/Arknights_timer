# -*- coding: utf-8 -*-
"""Bard (吟游者) trait tests: no basic attack + per-second
HP-recovery aura (atk * 10%) applied as an hpRecoveryPerSec attribute
modifier on every friendly in range (self included), removed out of range /
on retreat, refreshed when the bard ATK changes."""
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


def test_bard_is_bard_and_never_attacks():
    sim, b = _battle()
    b.deploy("char_4091_ulika", 2, 3)      # U-Official (bard, ranged)
    op = b.operators[0]
    ts = op.trait_system
    assert ts.is_bard()
    assert abs(ts.bard_aura_ratio() - 0.1) < 1e-9
    atk = float(op.attributes.get("atk"))
    assert atk > 0
    attrs = {"maxHp": 99999.0, "atk": 0.0, "def": 0.0}
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": attrs, "row": 2, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    before = e.hp
    sim.run_ticks(120)                     # 4 s of combat time
    assert e.hp == before, "bard must never deal damage"
    assert op._pending_attack is None
    assert not any(x.get("type") == "attack"
                   and (x.get("data") or {}).get("unit") == op.inst_id
                   for x in b.events.snapshot_events())


def test_bard_heal_aura_regen_and_self_heal():
    sim, b = _battle()
    b.deploy("char_4091_ulika", 2, 3)      # bard
    b.deploy("char_263_skadi", 3, 3)       # ally in the 3x3 range
    bard = b.operators[0]
    ally = b.operators[1]
    sim.run_ticks(40)                      # past deploy anim
    atk = float(bard.attributes.get("atk"))
    ratio = bard.trait_system.bard_aura_ratio()
    ally.hp -= 600.0
    bard.hp -= 300.0
    sim.run_ticks(30)                      # 1 s
    regen = atk * ratio
    assert abs(ally.hp - (float(ally.max_hp) - 600.0 + regen)) < 0.2, ally.hp
    assert abs(bard.hp - (float(bard.max_hp) - 300.0 + regen)) < 0.2, bard.hp


def test_bard_aura_out_of_range_and_retreat_cleanup():
    sim, b = _battle()
    b.deploy("char_4091_ulika", 2, 3)      # bard
    b.deploy("char_263_skadi", 3, 3)       # in range
    b.deploy("char_174_slbell", 1, 6)      # far away, out of range
    bard = b.operators[0]
    near = b.operators[1]
    far = b.operators[2]
    sim.run_ticks(40)                      # past deploy anim
    assert float(near.attributes.get("hpRecoveryPerSec")) > 0
    assert float(far.attributes.get("hpRecoveryPerSec")) == 0.0
    # retreating the bard removes the modifier (regen stops)
    b.withdraw(bard.inst_id)
    sim.run_ticks(40)
    assert float(near.attributes.get("hpRecoveryPerSec")) == 0.0
    assert not near.attributes._mods.get("hpRecoveryPerSec")


def test_bard_aura_refreshes_on_atk_change():
    sim, b = _battle()
    b.deploy("char_4091_ulika", 2, 3)
    b.deploy("char_263_skadi", 3, 3)
    bard = b.operators[0]
    ally = b.operators[1]
    sim.run_ticks(40)                      # past deploy anim
    base_atk = float(bard.attributes.get("atk"))
    rate0 = float(ally.attributes.get("hpRecoveryPerSec"))
    bard.attributes.add_modifier("atk", additive=base_atk, key="test_atk")
    sim.run_ticks(5)
    rate1 = float(ally.attributes.get("hpRecoveryPerSec"))
    assert abs(rate0 - base_atk * 0.1) < 1e-9, rate0
    assert abs(rate1 - base_atk * 2.0 * 0.1) < 1e-9, (rate0, rate1)


def test_hp_recovery_attribute_regen_generic():
    sim, b = _battle()
    b.deploy("char_263_skadi", 3, 3)
    op = b.operators[0]
    sim.run_ticks(40)                      # past deploy anim
    op.hp -= 500.0
    op.attributes.add_modifier("hpRecoveryPerSec", additive=100.0,
                               key="test_regen")
    sim.run_ticks(30)                      # 1 s -> +100 HP
    assert abs(op.hp - (float(op.max_hp) - 500.0 + 100.0)) < 0.2, op.hp


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
