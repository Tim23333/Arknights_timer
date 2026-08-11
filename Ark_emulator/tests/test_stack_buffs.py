"""Stack-on-hit buffs (attack@max_stack_cnt family):

  - Closur S3: each hit stacks 3% slow on the target (max 10)
  - Pepe S3: each attack stacks self atk +10% (max 4)
  - Veen S2: each attack stacks self atk +6% and aspd +5 (max 7)
  - Sharp S3: each attack stacks self atk +15% (max 8); switching
    targets resets the stacks
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle(char_id, skill_index):
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


def _spawn(b, op, col_off=1):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": op.row, "col": op.col + col_off})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _hit(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    if pa.get("ranged"):
        for _ in range(30):
            b.tick_once()
            if not any(not p.dead for p in getattr(b, "projectiles", [])):
                break


def _layers(b, unit, key):
    cur = b.buffs.get(unit, key)
    return cur.get("layers", 0) if cur else 0


def test_closur_s3_slow_stack():
    """可露希尔 S3：每次命中目标 +1 层 3% 减速（上限 10 层 = 30%）."""
    sim, b, op = _battle("char_4228_closur", 2)
    _activate(op, 2)
    e = _spawn(b, op)
    ms0 = e.attributes.get("moveSpeed")
    for _ in range(12):
        _hit(b, op, e)
    assert _layers(b, e, "op_closur_slow") == 10
    cur = b.buffs.get(e, "op_closur_slow")
    assert abs(float(cur["mul"]) - 0.03) < 1e-6
    assert abs(float(cur["remaining_ticks"]) - 90) < 1   # 3s * 30
    print("OK closur slow stack:", _layers(b, e, "op_closur_slow"))


def test_pepe_s3_atk_stack():
    """佩佩 S3：每次攻击自身 atk +10%（上限 4 层）."""
    sim, b, op = _battle("char_4058_pepe", 2)
    _activate(op, 2)
    e = _spawn(b, op)
    atk0 = op.attributes.get("atk")
    _hit(b, op, e)
    _hit(b, op, e)
    assert _layers(b, op, "op_pepe_atk_stack") == 2
    # atk0 已含激活 +120%（base×2.2）；2 层叠层 +20% → base×2.4
    assert abs(op.attributes.get("atk") - atk0 * (2.4 / 2.2)) \
        < atk0 * 0.01
    print("OK pepe atk stack:", _layers(b, op, "op_pepe_atk_stack"))


def test_veen_s2_dual_stack():
    """维伊 S2：每次攻击自身 atk +6% 与攻速 +5 同时叠层（上限 7）."""
    sim, b, op = _battle("char_4226_veen", 1)
    _activate(op, 1)
    e = _spawn(b, op)
    for _ in range(8):
        _hit(b, op, e)
    assert _layers(b, op, "op_veen_atk_stack") == 7
    assert _layers(b, op, "op_veen_aspd_stack") == 7
    print("OK veen stacks:", _layers(b, op, "op_veen_atk_stack"),
          _layers(b, op, "op_veen_aspd_stack"))


def test_sharp_s3_stack_reset_on_target_switch():
    """Sharp S3：每次攻击自身 atk +15%（上限 8），切换目标清零."""
    sim, b, op = _battle("char_609_acguad", 2)
    _activate(op, 2)
    e1 = _spawn(b, op, 1)
    e2 = _spawn(b, op, 0)
    _hit(b, op, e1)
    _hit(b, op, e1)
    assert _layers(b, op, "op_acguad_atk_stack") == 2
    _hit(b, op, e2)
    assert _layers(b, op, "op_acguad_atk_stack") == 1   # 清零后 +1
    print("OK sharp stack reset on switch")


if __name__ == "__main__":
    test_closur_s3_slow_stack()
    test_pepe_s3_atk_stack()
    test_veen_s2_dual_stack()
    test_sharp_s3_stack_reset_on_target_switch()
