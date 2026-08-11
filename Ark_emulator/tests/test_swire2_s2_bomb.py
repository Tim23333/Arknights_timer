"""Swire2 (琳琅诗怀雅) S2 "见面礼" champagne bomb:

  - deploy consumes 1 coin and places a bomb on the first buildable
    ground tile inside the operator's range
  - touching the first enemy deals owner atk * attack@atk_scale (1.4)
    physical damage and sluggish 2s
  - after duration_switch (3s) on field it can trigger once more (total
    2 hits), then the bomb is consumed
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _setup():
    squad = [{"charId": "char_1033_swire2", "phase": 2, "level": 50,
              "skillIndex": 1, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 1000.0
    b.cost_increase_time = 1e7
    b.deploy("char_1033_swire2", 3, 3)
    op = b.operators[0]
    return sim, b, op


def test_s2_places_bomb_and_first_touch():
    """S2：消耗金币放炸弹；触碰造成 atk×1.4 伤害 + 停顿 2s."""
    sim, b, op = _setup()
    sc = op.skill_controller
    op._coins = 1
    sc.active = None
    sc.trigger_on_deploy()
    assert op._coins == 0
    bombs = [t for t in b.tokens
             if t.token_id == "token_10031_swire2_gdtrap"]
    assert bombs, "bomb must be placed"
    bomb = bombs[-1]
    assert (bomb.row, bomb.col) == (3, 4)      # 面前可部署地面
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": bomb.row, "col": bomb.col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    atk = op.attributes.get("atk")
    hp0 = e.hp
    for _ in range(5):
        b.tick_once()
    dealt = hp0 - e.hp
    assert abs(dealt - atk * 1.4) < 1.0, dealt
    slg = [x for x in (getattr(e, "buffs", None) or [])
           if x.get("key") == "op_sluggish_atk"]
    assert slg and abs(float(slg[0]["mul"]) + 0.5) < 1e-6
    assert 50 <= float(slg[0]["remaining_ticks"]) <= 60      # ~2s
    assert not bomb.dead and getattr(bomb, "_bomb_hits", 0) == 1
    print("OK S2 first touch:", round(dealt, 1))


def test_s2_second_trigger_after_3s():
    """3 秒后炸弹可额外触发一次（共 2 次），用完消失."""
    sim, b, op = _setup()
    sc = op.skill_controller
    op._coins = 1
    sc.active = None
    sc.trigger_on_deploy()
    bomb = [t for t in b.tokens
            if t.token_id == "token_10031_swire2_gdtrap"][-1]
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": bomb.row, "col": bomb.col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    atk = op.attributes.get("atk")
    for _ in range(5):
        b.tick_once()
    hp1 = e.hp
    # 跑到炸弹消失（3s 后第二次触发）
    for _ in range(120):
        b.tick_once()
        if getattr(bomb, "dead", False):
            break
    extra = hp1 - e.hp
    assert getattr(bomb, "dead", False), "bomb must be consumed after 2 hits"
    assert getattr(bomb, "_bomb_hits", 0) == 2
    assert extra >= atk * 1.4 - 1.0, extra     # 第二次至少 atk×1.4
    print("OK S2 second trigger, extra:", round(extra, 1))


if __name__ == "__main__":
    test_s2_places_bomb_and_first_touch()
    test_s2_second_trigger_after_3s()
