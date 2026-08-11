# -*- coding: utf-8 -*-
"""Damage-formula matrix: physical/magical/true/element vs
def/mres/penetration/fragility/barrier, locking the shared
battle.apply_damage pipeline."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 3)
    return sim, b, b.operators[-1]


def _enemy(b, row=3, col=4, **attrs):
    over = {"attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0,
                           "magicResistance": 0.0}, "row": row, "col": col}
    over["attributes"].update(attrs)
    b.spawn_enemy("enemy_1000_gopro", 0, overrides=over)
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _dmg(b, e, amount, dmg_type, source):
    before = e.hp
    b.apply_damage(e, amount, dmg_type, source=source)
    return before - e.hp


def test_physical_vs_def_and_min_ratio():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 50.0})
    assert abs(_dmg(b, e, 100.0, DamageType.PHYSICAL, op) - 50.0) < 1e-6
    e2 = _enemy(b, col=5, **{"def": 200.0})
    # 100 - 200 -> clamped by the 5% minimum ratio
    assert abs(_dmg(b, e2, 100.0, DamageType.PHYSICAL, op) - 5.0) < 1e-6


def test_physical_penetration():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 50.0})
    op.attributes.base["defPenetrateFixed"] = 30.0
    assert abs(_dmg(b, e, 100.0, DamageType.PHYSICAL, op) - 80.0) < 1e-6


def test_magical_vs_mres_cap():
    sim, b, op = _battle()
    e = _enemy(b, **{"magicResistance": 20.0})
    assert abs(_dmg(b, e, 100.0, DamageType.MAGICAL, op) - 80.0) < 1e-6
    e2 = _enemy(b, col=5, **{"magicResistance": 120.0})
    # mres caps at 100; the 5% minimum ratio still applies -> 5 polish damage
    assert abs(_dmg(b, e2, 100.0, DamageType.MAGICAL, op) - 5.0) < 1e-6


def test_magical_min_ratio_floor():
    sim, b, op = _battle()
    # 1000 atk vs mres 100 -> 50 (5% floor)
    e = _enemy(b, **{"magicResistance": 100.0})
    assert abs(_dmg(b, e, 1000.0, DamageType.MAGICAL, op) - 50.0) < 1e-6
    # 1000 atk vs mres 120 (capped to 100) -> still 50
    e2 = _enemy(b, col=5, **{"magicResistance": 120.0})
    assert abs(_dmg(b, e2, 1000.0, DamageType.MAGICAL, op) - 50.0) < 1e-6
    # normal case unaffected: mres 20 -> 80% damage
    e3 = _enemy(b, col=6, **{"magicResistance": 20.0})
    assert abs(_dmg(b, e3, 1000.0, DamageType.MAGICAL, op) - 800.0) < 1e-6


def test_true_damage_ignores_defence():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 200.0, "magicResistance": 60.0})
    assert abs(_dmg(b, e, 100.0, DamageType.TRUE, op) - 100.0) < 1e-6


def test_element_damage_unaffected_by_defence():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 200.0})
    before = [x for x in e.buffs if x.get("key") == "ep_neural"]
    _dmg(b, e, 100.0, DamageType.ELEMENT, op)
    after = [x for x in e.buffs if x.get("key") == "ep_neural"]
    got = after[-1]["value"] if after else 0.0
    # full-bar model: value = remaining (1000 - 100 damage)
    assert abs(got - 900.0) < 1e-6


def test_fragility_scales_after_mitigation():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 50.0})
    b.add_buff(e, {"key": "weak[phy]", "remaining_ticks": 1000,
                   "layers": 1,
                   "blackboard": {"damage_scale": 1.2}})
    # (100 - 50) x 1.2
    assert abs(_dmg(b, e, 100.0, DamageType.PHYSICAL, op) - 60.0) < 1e-6


def test_barrier_absorbs_after_mitigation():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 50.0})
    e.barrier = 10.0
    got = _dmg(b, e, 100.0, DamageType.PHYSICAL, op)
    assert abs(got - 40.0) < 1e-6, got   # 50 mitigated, 10 absorbed



def test_min_ratio_then_barrier():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 200.0})
    e.barrier = 3.0
    got = _dmg(b, e, 100.0, DamageType.PHYSICAL, op)
    # mitigated to the 5% floor (5), then 3 absorbed -> 2
    assert abs(got - 2.0) < 1e-6, got


def test_magic_penetrate_then_cap():
    sim, b, op = _battle()
    e = _enemy(b, **{"magicResistance": 120.0})
    op.attributes.base["magicResistPenetrateFixed"] = 30.0
    # 120 - 30 = 90 effective mres -> 10% damage
    assert abs(_dmg(b, e, 100.0, DamageType.MAGICAL, op) - 10.0) < 1e-6


def test_percent_and_fixed_penetration():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 200.0})
    op.attributes.base["defPenetrate"] = 0.2
    op.attributes.base["defPenetrateFixed"] = 30.0
    # 200*(1-0.2) - 30 = 130 -> 100 - 130 clamped to 5 (min ratio)
    got = _dmg(b, e, 100.0, DamageType.PHYSICAL, op)
    assert abs(got - 5.0) < 1e-6, got
    e2 = _enemy(b, col=5, **{"def": 50.0})
    got2 = _dmg(b, e2, 100.0, DamageType.PHYSICAL, op)
    # 50*0.8 - 30 = 10 -> 90
    assert abs(got2 - 90.0) < 1e-6, got2


def test_fragility_then_barrier():
    sim, b, op = _battle()
    e = _enemy(b, **{"def": 50.0})
    b.add_buff(e, {"key": "weak[phy]", "remaining_ticks": 1000,
                   "layers": 1,
                   "blackboard": {"damage_scale": 1.2}})
    e.barrier = 10.0
    # (100-50)*1.2 = 60, then 10 absorbed -> 50
    got = _dmg(b, e, 100.0, DamageType.PHYSICAL, op)
    assert abs(got - 50.0) < 1e-6, got



def test_melee_penetration_path():
    """Rdoc (instructor) melee penetration: trait atk_scale 1.2 with
    def_penetrate_fixed 120 fully bypasses a def-100 target - same
    apply_damage pipeline as projectiles."""
    sim, b, op = _battle()
    op = None
    b.operators = []
    ok = False
    for r in range(b.map.rows):
        for c in range(b.map.cols):
            if b.map.buildable(r, c, 1) is not False:
                ok, res = b.deploy("char_4125_rdoc", r, c)
                if ok:
                    break
        if ok:
            break
    op = b.operators[-1]
    e = _enemy(b, row=op.row, col=op.col + 1, **{"def": 100.0})
    atk = float(op.attributes.get("atk"))
    pen = float(op.attributes.get("defPenetrateFixed") or 0.0)
    expect = atk * 1.2 - max(0.0, 100.0 - pen)   # instructor 1.2 trait
    b.events.log = []
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("target") == e.inst_id]
    assert len(dmg) == 1, dmg
    assert abs(dmg[0]["data"]["amount"] - expect) < 0.5, dmg
