"""Fragility (\u8106\u5f31) system tests.

Covers PhonoR-0 talent 1 aura (magic + element fragility on enemies in
attack range inside the 40s deploy window, game phonor_t_1[aura] ->
weak[magic][inf] / weak[ep][inf]) and the generic damage pipeline:
weak[magic]/weak[phy] scale their own HP-damage type, weak[ep] scales
element EP, generic weak scales every HP-damage type, and multiple
fragility buffs multiply.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle(char_id="char_4136_phonor"):
    squad = [{"charId": char_id, "phase": 2, "level": 50,
              "skillIndex": 0, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy(b, char_id, row=2, col=3):
    ok, pid = b.deploy(char_id, row, col)
    assert ok, pid
    return b.operators[0]


def _spawn(b, row, col):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0,
                       "magicResistance": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _hp_loss(b, e, amount, dmg_type, source):
    before = e.hp
    b.apply_damage(e, amount, dmg_type, source=source)
    return before - e.hp


def _ep(e, key):
    rec = [x for x in e.buffs if x.get("key") == key]
    return rec[-1]["value"] if rec else 0.0


def test_phonor_aura_applies_fragility_in_range():
    sim, b = _battle()
    op = _deploy(b, "char_4136_phonor")
    scale = float(op.talent_system.bb("damage_scale"))
    assert scale > 1.0
    e = _spawn(b, 2, 4)                       # in attack range
    sim.run_ticks(25)                         # finish deploy anim + aura tick
    for key in ("weak[magic]", "weak[ep]"):
        rec = b.buffs.get(e, key)
        assert rec is not None, key
        assert abs(float(rec["blackboard"]["damage_scale"]) - scale) < 1e-9


def test_phonor_aura_skips_out_of_range():
    sim, b = _battle()
    _deploy(b, "char_4136_phonor")
    far = _spawn(b, 4, 4)                     # outside attack range
    sim.run_ticks(25)
    assert b.buffs.get(far, "weak[magic]") is None
    assert b.buffs.get(far, "weak[ep]") is None


def test_phonor_weakness_scales_magic_but_not_physical():
    sim, b = _battle()
    op = _deploy(b, "char_4136_phonor")
    scale = float(op.talent_system.bb("damage_scale"))
    e = _spawn(b, 2, 4)
    sim.run_ticks(25)
    mag = _hp_loss(b, e, 100.0, DamageType.MAGICAL, op)
    assert abs(mag - 100.0 * scale) < 1e-6, (mag, scale)
    e2 = _spawn(b, 2, 5)
    sim.run_ticks(2)
    phy = _hp_loss(b, e2, 100.0, DamageType.PHYSICAL, op)
    assert abs(phy - 100.0) < 1e-6, phy


def test_phonor_weakness_scales_element_ep():
    sim, b = _battle()
    op = _deploy(b, "char_4136_phonor")
    scale = float(op.talent_system.bb("damage_scale"))
    e = _spawn(b, 2, 4)
    sim.run_ticks(25)
    _hp_loss(b, e, 100.0, DamageType.ELEMENT, op)
    # full-bar model: value = remaining (1000 - scaled EP damage)
    assert abs(_ep(e, "ep_neural") -
               (1000.0 - 100.0 * scale)) < 1e-6


def test_phonor_aura_expires_after_window():
    sim, b = _battle()
    op = _deploy(b, "char_4136_phonor")
    e = _spawn(b, 2, 4)
    sim.run_ticks(25)
    assert b.buffs.get(e, "weak[magic]") is not None
    op.deploy_tick = b.tick - 1201           # window (40s) already over
    sim.run_ticks(35)                         # buffs expire within 1s
    assert b.buffs.get(e, "weak[magic]") is None
    assert b.buffs.get(e, "weak[ep]") is None


def test_generic_weak_scales_all_hp_damage():
    sim, b = _battle("char_003_kalts")
    op = _deploy(b, "char_003_kalts")
    e = _spawn(b, 3, 4)
    b.add_buff(e, {"key": "weak", "remaining_ticks": 1000, "layers": 1,
                   "blackboard": {"damage_scale": 1.2}})
    for dmg_type, label in ((DamageType.PHYSICAL, "phy"),
                            (DamageType.MAGICAL, "mag"),
                            (DamageType.TRUE, "pure")):
        got = _hp_loss(b, e, 100.0, dmg_type, op)
        assert abs(got - 120.0) < 1e-6, (label, got)
    _hp_loss(b, e, 100.0, DamageType.ELEMENT, op)
    # generic weak: no EP scaling -> remaining 900
    assert abs(_ep(e, "ep_neural") - 900.0) < 1e-6


def test_physical_fragility_scales_physical_only():
    sim, b = _battle("char_003_kalts")
    op = _deploy(b, "char_003_kalts")
    e = _spawn(b, 3, 4)
    b.add_buff(e, {"key": "weak[phy]", "remaining_ticks": 1000, "layers": 1,
                   "blackboard": {"damage_scale": 1.25}})
    phy = _hp_loss(b, e, 100.0, DamageType.PHYSICAL, op)
    assert abs(phy - 125.0) < 1e-6, phy
    mag = _hp_loss(b, e, 100.0, DamageType.MAGICAL, op)
    assert abs(mag - 100.0) < 1e-6, mag


def test_fragility_buffs_multiply():
    sim, b = _battle("char_003_kalts")
    op = _deploy(b, "char_003_kalts")
    e = _spawn(b, 3, 4)
    b.add_buff(e, {"key": "weak", "remaining_ticks": 1000, "layers": 1,
                   "blackboard": {"damage_scale": 1.2}})
    b.add_buff(e, {"key": "weak[magic]", "remaining_ticks": 1000,
                   "layers": 1,
                   "blackboard": {"damage_scale": 1.1}})
    mag = _hp_loss(b, e, 100.0, DamageType.MAGICAL, op)
    assert abs(mag - 132.0) < 1e-6, mag


def test_withdraw_clears_fragility():
    sim, b = _battle()
    op = _deploy(b, "char_4136_phonor")
    e = _spawn(b, 2, 4)
    sim.run_ticks(25)
    assert b.buffs.get(e, "weak[magic]") is not None
    ok, _ = b.withdraw(op.inst_id)
    assert ok
    sim.run_ticks(35)
    assert b.buffs.get(e, "weak[magic]") is None
    assert b.buffs.get(e, "weak[ep]") is None
