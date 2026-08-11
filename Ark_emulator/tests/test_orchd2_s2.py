"""Orchid2 (焰狐龙梓兰) S2 "飞翔瞪射":

  - liftoff (block mode FLY) on activation
  - 3 arrow waves (3/4/5 shots, each atk * attack@atk_scale_loop) fired
    at front-range enemies after the 0.2s takeoff animation
  - landing burst at skill end: atk * attack@atk_scale_end to all enemies
    in the small front area
  - block mode restored on expire
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _setup():
    squad = [{"charId": "char_1048_orchd2", "phase": 2, "level": 50,
              "skillIndex": 1, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    for (r, c) in [(3, 3), (2, 3), (1, 3), (3, 2)]:
        ok = b.deploy("char_1048_orchd2", r, c)
        if ok[0]:
            break
    op = b.operators[0]
    return sim, b, op


def test_orchd2_s2_waves_and_landing():
    """兰 S2：起飞 + 3 波箭（3/4/5×atk×1.2）+ 降落 atk×2.4."""
    sim, b, op = _setup()
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, why = sc.activate(1)
    assert ok, why
    assert str(getattr(op, "_block_mode", "") or "").upper() == "FLY"
    atk = op.attributes.get("atk")
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": op.row, "col": op.col + 2})       # 前方 2 格
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    start_tick = sc.active._orchd2_start_tick
    # 跑到第 3 波完成（起飞 6 ticks + 2×39 间隔 ≈ tick 84 后）
    while b.tick < start_tick + 100:
        b.tick_once()
    before = 50000.0 - e.hp
    assert before >= atk * 1.2 * (3 + 4 + 5) - 1.0, before
    # 跑到技能结束（4.2s=126 ticks）触发降落伤害
    while sc.active is not None and b.tick < start_tick + 200:
        b.tick_once()
    total = 50000.0 - e.hp
    assert total >= atk * 1.2 * 12 + atk * 2.4 - 1.0, total
    assert str(getattr(op, "_block_mode", "") or "").upper() != "FLY"
    print("OK orchd2 S2 waves+landing total", round(total, 1))


if __name__ == "__main__":
    test_orchd2_s2_waves_and_landing()
