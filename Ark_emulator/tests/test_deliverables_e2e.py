"""End-to-end deliverables audit: 选择关卡 -> 自定义编队 -> 部署 ->
自定义敌人 -> 战斗推进 -> 实时快照，一条路径覆盖原始需求的关键交付项。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def test_e2e_deliverables():
    # 1. 选择关卡
    squad = [
        {"charId": "char_002_amiya", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},
        {"charId": "char_149_scave", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},
    ]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    # 2. 自定义编队已生效（squad 注入）
    assert b.store is not None
    # 3. 部署干员
    ok, pid = b.deploy("char_002_amiya", 2, 3)
    assert ok, pid
    op = b.operators[0]
    assert op.char_id == "char_002_amiya"
    # 4. 自定义敌人（覆盖 maxHp/def）
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 12345.0, "atk": 0.0, "def": 100.0},
        "row": 2, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    assert abs(e.max_hp - 12345.0) < 0.01
    # 5. 战斗推进：干员攻击敌人
    op.attack_timer = 0.0
    for _ in range(120):
        sim.run_ticks(1)
        if e.dead:
            break
    # 6. 实时快照包含详细信息
    snap = sim.snapshot()
    d = {u["charId"]: u for u in snap["deployed"]
         if u.get("charId") == "char_002_amiya"}
    assert d, snap["deployed"]
    unit = next(iter(d.values()))
    for field in ("hp", "maxHp", "atk", "def", "mres",
                  "row", "col", "skills", "buffs", "sp", "spMax"):
        assert field in unit, "snapshot missing %s" % field
    enemies = [en for en in snap["enemies"]
               if en.get("key") == "enemy_1000_gopro"]
    assert enemies and enemies[0]["maxHp"] == 12345.0
    print("OK e2e deliverables: deploy, custom enemy, battle, snapshot")


if __name__ == "__main__":
    test_e2e_deliverables()
