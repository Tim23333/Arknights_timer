# -*- coding: utf-8 -*-
"""Prefab _damageType uses the GAME enum (PHYSICAL=1 MAGICAL=2 PURE=3
ELEMENT=5); the emulator must translate it to its own enum
(PHYSICAL=0 MAGICAL=1 TRUE=2 ELEMENT=3)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _spawn_skill(enemy_key, prefab_key):
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.spawn_enemy(enemy_key, 0)
    sc = b.enemies[-1].skill_controller
    assert sc is not None, enemy_key
    for s in sc.skills:
        if s.prefab_key == prefab_key:
            return sim, b, s
    raise AssertionError(f"skill {prefab_key} not found for {enemy_key}")


def test_game_damage_types_translated():
    # game MAGICAL(2) -> emulator MAGICAL (frost star ArcticBlast has a
    # single-owner prefab, unlike the merged "1"/"3" shared skills)
    _, _, s = _spawn_skill("enemy_1505_frstar", "ArcticBlast")
    assert s.prefab_damage_type == DamageType.MAGICAL, s.prefab_damage_type
    # game PURE(3) -> emulator TRUE
    _, _, s = _spawn_skill("enemy_2092_skzamy", "AOEAttackInit")
    assert s.prefab_damage_type == DamageType.TRUE, s.prefab_damage_type
    # game PHYSICAL(1) -> emulator PHYSICAL
    _, _, s = _spawn_skill("enemy_10027_vtsk", "MultiCombat")
    assert s.prefab_damage_type == DamageType.PHYSICAL, s.prefab_damage_type


def test_magical_cast_deals_magical_damage():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    for _ in range(20):
        b.tick_once()
    op = b.operators[0]
    b.spawn_enemy("enemy_1505_frstar", 0)
    enemy = b.enemies[-1]
    enemy.row, enemy.col = op.row, op.col
    enemy.pos_x, enemy.pos_y = float(op.col), float(op.row)
    enemy.state = EnemyState.COMBAT
    sc = enemy.skill_controller
    s = next(sk for sk in sc.skills if sk.prefab_key == "ArcticBlast")
    assert s.prefab_damage_type == DamageType.MAGICAL
    sc._start_cast((s, op))
    dmg = []
    for _ in range(150):
        sc.update(1 / 30)
        b.tick_once()
        for ev in b.events.log:
            if ev.type == "damage" and ev.data.get("target") == op.inst_id:
                dmg.append(ev.data)
    assert dmg, "no damage landed on operator"
    assert any(int(d.get("type")) == DamageType.MAGICAL for d in dmg), dmg


def test_malformed_skill_fields_coerced():
    """Some parsed skills carry a blackboard key string in a numeric field
    (e.g. DeepBreathS4.spCost == 'startCol'); loading must not crash."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.spawn_enemy("enemy_2092_skzamy", 0)
    sc = b.enemies[-1].skill_controller
    assert sc is not None
    for s in sc.skills:
        assert isinstance(s.sp_cost, int)
    s = next(sk for sk in sc.skills if sk.prefab_key == "DeepBreathS4")
    assert s.sp_cost == 0, s.sp_cost
    assert s.cooldown is None or isinstance(s.cooldown, float)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("OK", t.__name__)
    print("all damage type tests passed")
