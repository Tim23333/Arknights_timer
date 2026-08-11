"""attack@sp hit-attached SP recovery.

Windflit S1 "此身为筑" (skchr_windft_1, attack@sp=1): the next attack
gives 1 SP to every reliable-battery wearer - caster (profession 32)
and supporter (16) operators, including Windflit himself.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _setup():
    squad = [
        {"charId": "char_433_windft", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},
        {"charId": "char_002_amiya", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},   # caster
        {"charId": "char_003_kalts", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},   # medic (no battery)
    ]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    for (r, c) in [(3, 3), (2, 3), (1, 3)]:
        ok = b.deploy("char_433_windft", r, c)
        if ok[0]:
            break
    op = b.operators[0]
    b.deploy("char_002_amiya", 2, 4)
    for (r, c) in [(1, 3), (1, 4), (2, 2), (0, 3), (1, 2)]:
        ok = b.deploy("char_003_kalts", r, c)
        if ok[0]:
            break
    return sim, b, op


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def _find(b, char_id):
    return [o for o in b.operators if o.char_id == char_id][-1]


def test_windflit_s1_gives_sp_to_battery_wearers():
    """掠风 S1 命中：术师/辅助（含自身）+1 技力，医疗不回."""
    sim, b, op = _setup()
    amiya = _find(b, "char_002_amiya")
    kalts = _find(b, "char_003_kalts")
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": op.row, "col": op.col + 1})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    amiya.sp = 0.0
    kalts.sp = 0.0
    ok, why = sc.activate(0)
    assert ok, why
    _land_attack(b, op, e)
    assert op.sp == 1.0, op.sp                # 掠风自己是辅助（装备者）
    assert amiya.sp == 1.0, amiya.sp          # 术师
    assert kalts.sp == 0.0, kalts.sp          # 医疗不装备可靠电池
    print("OK windflit S1 SP: self", op.sp, "amiya", amiya.sp,
          "kalts", kalts.sp)


def test_windflit_s1_no_sp_without_activation():
    """未激活技能时普攻不回复技力."""
    sim, b, op = _setup()
    amiya = _find(b, "char_002_amiya")
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": op.row, "col": op.col + 1})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    amiya.sp = 0.0
    op.sp = 0.0
    _land_attack(b, op, e)
    assert amiya.sp == 0.0
    print("OK no SP without activation")


if __name__ == "__main__":
    test_windflit_s1_gives_sp_to_battery_wearers()
    test_windflit_s1_no_sp_without_activation()
