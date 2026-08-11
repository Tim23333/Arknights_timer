"""Taraxa (风絮) liftoff skills:

  - S1 "何处着": liftoff, attack interval *0.2, random heal of one
    injured ally in range (atk * attack@heal_scale)
  - S2 "扶风起": liftoff, self atk +60% (attack@atk)
  - liftoff switches block mode to FLY (taraxa_fly_mode template) so the
    operator can block flying enemies; restored when the skill ends
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle(char_id="char_4222_taraxa", skill_index=0):
    squad = [{"charId": char_id, "phase": 2, "level": 50,
              "skillIndex": skill_index, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    for (r, c) in [(3, 3), (2, 3), (1, 3), (3, 2)]:
        ok = b.deploy(char_id, r, c)
        if ok[0]:
            break
    op = b.operators[0]
    return sim, b, op


def _activate(op, index):
    sc = op.skill_controller
    op.sp = sc.skills[index].sp_cost
    ok, why = sc.activate(index)
    assert ok, why
    return sc


def _spawn_enemy(b, op):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": op.row, "col": op.col + 1})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(sim, b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    if pa.get("ranged"):
        for _ in range(40):
            b.tick_once()
            if not any(not p.dead for p in getattr(b, "projectiles", [])):
                break


def test_taraxa_s1_interval_heal_liftoff():
    """风絮 S1：攻击间隔 ×0.2、随机治疗范围已受伤单位、起飞."""
    sim, b, op = _battle(skill_index=0)
    iv0 = op.attributes.attack_interval()
    _activate(op, 0)
    assert abs(op.attributes.attack_interval() - iv0 * 0.2) < 0.01
    assert str(getattr(op, "_block_mode", "") or "").upper() == "FLY"
    e = _spawn_enemy(b, op)
    injured = op.max_hp - 500.0
    op.hp = injured
    _land_attack(sim, b, op, e)
    healed = op.hp - injured
    assert healed > 0 and abs(healed - op.attributes.get("atk") * 0.4) \
        < 1.0, healed
    print("OK taraxa S1 interval x0.2, heal", healed)


def test_taraxa_s2_atk_liftoff():
    """风絮 S2：自身攻击力 +60%、起飞."""
    sim, b, op = _battle(skill_index=1)
    atk0 = op.attributes.get("atk")
    _activate(op, 1)
    assert abs(op.attributes.get("atk") - atk0 * 1.6) < atk0 * 0.01
    assert str(getattr(op, "_block_mode", "") or "").upper() == "FLY"
    print("OK taraxa S2 atk", atk0, "->", op.attributes.get("atk"))


def test_taraxa_liftoff_blocks_flying_enemy():
    """起飞期间可阻挡飞行敌人（block mode FLY），技能结束释放."""
    sim, b, op = _battle(skill_index=0)
    _activate(op, 0)
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": op.row, "col": op.col})       # 与干员同格
    air = b.enemies[-1]
    air.state = EnemyState.COMBAT
    air.is_flying = True
    air.set_flag(3, 10 ** 9)          # BLOCK_FREE
    b._update_blocking()
    assert air.blocked_by is op, "liftoff operator must block flying enemy"
    # skill ends -> released
    sc = op.skill_controller
    sc.interrupt_active()
    assert str(getattr(op, "_block_mode", "") or "").upper() != "FLY"
    b._update_blocking()
    assert air.blocked_by is None
    print("OK taraxa liftoff blocks flying enemy, released on end")


if __name__ == "__main__":
    test_taraxa_s1_interval_heal_liftoff()
    test_taraxa_s2_atk_liftoff()
    test_taraxa_liftoff_blocks_flying_enemy()
