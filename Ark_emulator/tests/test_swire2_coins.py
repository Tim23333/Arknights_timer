"""Swire2 (琳琅诗怀雅) merchant coin system:

  - equipped skill blackboard `sp` key = coin cap (S1=1 / S2=3 / S3=10)
  - talent "大买家": while a skill is active every merchant cost-drain
    grants 1 coin; S3 kills also grant 1 coin
  - S1 "仗义疏财": consumes 1 coin on deploy; the next attack heals one
    injured (<70% HP) ally in the surrounding 8 tiles by atk*heal_scale
  - S3 "千金一掷": on manual close, consumes ALL coins - one
    atk*atk_scale physical hit (plus small push) per coin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle(skill_index):
    squad = [
        {"charId": "char_1033_swire2", "phase": 2, "level": 50,
         "skillIndex": skill_index, "skillLevels": [1, 1, 1]},
        {"charId": "char_149_scave", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},
    ]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 1000.0
    b.cost_increase_time = 1e7
    b.deploy("char_1033_swire2", 3, 3)
    op = b.operators[0]
    return sim, b, op


def _land_attack(sim, b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    for _ in range(12):
        b.tick_once()
        if not any(not p.dead for p in getattr(b, "projectiles", [])):
            break


def test_coin_cap_by_skill():
    """装备技能 sp 键决定金币上限（S1=1 / S2=3 / S3=10）."""
    for si, cap in ((0, 1), (1, 3), (2, 10)):
        sim, b, op = _battle(si)
        assert op._coin_max == cap, (si, op._coin_max)
        assert op._coins == 0
    print("OK coin caps by skill")


def test_s3_activates_and_gains_coins():
    """S3 激活期间费用消耗 +1 金币；击杀 +1 金币."""
    sim, b, op = _battle(2)
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    ok, why = sc.activate(2)
    assert ok, why
    assert sc.active is not None and sc.active.skill.skill_id == \
        "skchr_swire2_3"
    b.tick_once()
    assert sc.active is not None, "S3 must be infinite duration"
    for _ in range(300):          # 10s: cost drain 每 3s
        b.tick_once()
    assert op._coins >= 3, op._coins
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 100.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    b.apply_damage(e, 500.0, 0, source=op)
    assert op._coins >= 4, op._coins
    print("OK S3 coins:", op._coins)


def test_s3_close_burst_spends_all_coins():
    """S3 主动关闭消耗所有金币，每金币一次 atk×atk_scale 物理."""
    sim, b, op = _battle(2)
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    sc.activate(2)
    for _ in range(300):
        b.tick_once()
    op._coins = 5
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    hp0 = e.hp
    atk = op.attributes.get("atk")
    sc.interrupt_active()
    assert op._coins == 0
    dealt = hp0 - e.hp
    assert dealt >= atk * 0.8 * 4 - 1.0, dealt   # ≥4 枚命中
    print("OK S3 burst dealt", round(dealt, 1))


def test_s1_consume_coin_and_heal():
    """S1：无金币不触发；1 金币触发后治疗周围 8 格 HP<70% 友方."""
    sim, b, op = _battle(0)
    sc = op.skill_controller
    assert sc.active is None or sc.active.skill.skill_id != \
        "skchr_swire2_1"   # 0 金币时部署 S1 不触发（可能 active 为 None）
    # 手动给 1 金币再触发
    op._coins = 1
    sc.active = None
    sc.trigger_on_deploy()
    assert sc.active is not None and sc.active.skill.skill_id == \
        "skchr_swire2_1"
    assert op._coins == 0
    b.deploy("char_149_scave", 3, 4)
    ally = b.operators[-1]
    ally.hp = ally.max_hp * 0.5
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 5})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    hp0 = ally.hp
    _land_attack(sim, b, op, e)
    expect = op.attributes.get("atk") * 0.25
    assert abs((ally.hp - hp0) - expect) < 1.0, (ally.hp - hp0, expect)
    assert sc.active is None       # 触发后技能结束
    print("OK S1 heal:", round(ally.hp - hp0, 1))


if __name__ == "__main__":
    test_coin_cap_by_skill()
    test_s3_activates_and_gains_coins()
    test_s3_close_burst_spends_all_coins()
    test_s1_consume_coin_and_heal()
