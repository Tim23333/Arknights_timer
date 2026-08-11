"""Magellan S1 periodic passive sluggish / active bind
(skchr_mgllan_1: attack@interval 3.0 / attack@sluggish 0.7 /
attack@frozen_duration 1.6).

Covers:
  - passive: every 3s sluggish 0.7s inside own + drone ranges
  - active: bind replaces sluggish on the same periodic cadence
  - attack hits while active apply no extra sluggish/bind
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import AbnormalFlag, EnemyState


def _setup():
    squad = [{"charId": "char_248_mgllan", "phase": 2, "level": 50,
              "skillIndex": 0, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    ok = b.deploy("char_248_mgllan", 2, 3)
    assert ok[0], ok
    op = b.operators[0]
    return sim, b, op


def _spawn(b, row, col):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _sluggish(e):
    return [x for x in (getattr(e, "buffs", None) or [])
            if x.get("key") == "op_sluggish_atk"]


def _bind_ticks(e):
    rec = (e.abnormal or {}).get(AbnormalFlag.UNMOVABLE)
    return rec.get("ticks") if rec else 0


def test_mgllan_s1_passive_sluggish_cycle():
    """被动：部署后每 attack@interval=3s 施加 attack@sluggish=0.7s 停顿."""
    sim, b, op = _setup()
    e = _spawn(b, 1, 3)          # 麦哲伦 (2,3) 攻击范围内
    seen = []
    for _ in range(380):
        sim.run_ticks(1)
        if _sluggish(e) and (not seen or seen[-1] < b.tick - 60):
            seen.append(b.tick)
            dur = _sluggish(e)[0].get("remaining_ticks") or 0
            assert 18 <= dur <= 21, dur   # 0.7s * 30 = 21 ticks
    assert len(seen) >= 3, seen           # 106/196/286 附近
    assert seen[1] - seen[0] == 90, seen  # 周期 = 3s = 90 ticks
    print("OK passive sluggish ticks:", seen)


def test_mgllan_s1_active_bind_continuity():
    """主动：停顿变为束缚，且沿用被动周期的同一节奏（激活不重置周期）."""
    sim, b, op = _setup()
    e = _spawn(b, 1, 3)
    passive = []
    for _ in range(400):
        sim.run_ticks(1)
        if _sluggish(e) and (not passive or passive[-1] < b.tick - 60):
            passive.append(b.tick)
    assert passive, passive
    op.sp = 30.0
    ok, why = op.skill_controller.activate(0)
    assert ok, why
    # 激活期间：无停顿 buff
    binds = []
    for _ in range(500):
        sim.run_ticks(1)
        assert not _sluggish(e), "sluggish must not apply while active"
        if _bind_ticks(e) > 0 and (not binds or binds[-1] < b.tick - 60):
            binds.append(b.tick)
    assert binds, "bind never applied while active"
    # 第一个束缚点与最后一个被动停顿点间隔 = 90 ticks（同一周期组件）
    assert binds[0] - passive[-1] == 90, (passive, binds)
    if len(binds) >= 2:
        assert binds[1] - binds[0] == 90, binds
    print("OK active bind ticks:", binds, "after passive:", passive)


def test_mgllan_s1_drone_range():
    """被动覆盖自身 + 所有已部署无人机（token）攻击范围."""
    from ark_emulator.attributes import Attributes
    from ark_emulator.entities import Token
    sim, b, op = _setup()
    e_out = _spawn(b, 4, 5)     # 不在麦哲伦 3x3 范围内
    # 无人机在 (4,4)，range_shape 覆盖 (4,5)
    drone = Token("sktok_mgllan_drone1", Attributes({}),
                  row=4, col=4, owner=op)
    drone.range_shape = [(0, 1)]
    b.tokens.append(drone)
    seen = []
    for _ in range(300):
        sim.run_ticks(1)
        if _sluggish(e_out) and (not seen or seen[-1] < b.tick - 60):
            seen.append(b.tick)
    assert seen, "drone-range enemy never slowed"
    print("OK drone-range sluggish ticks:", seen)


def test_mgllan_s1_no_abnormal_on_attack_hit():
    """激活期间普通攻击命中不附加停顿/束缚（异常只来自周期路径）."""
    sim, b, op = _setup()
    e = _spawn(b, 1, 3)
    op.sp = 30.0
    ok, why = op.skill_controller.activate(0)
    assert ok, why
    before = len(_sluggish(e)) + (1 if _bind_ticks(e) > 0 else 0)
    # 攻击命中（落到 OnAttack 生效帧）
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    after = len(_sluggish(e)) + (1 if _bind_ticks(e) > 0 else 0)
    assert after <= before, (before, after)
    print("OK no extra hit abnormal (before/after)", before, after)


if __name__ == "__main__":
    test_mgllan_s1_passive_sluggish_cycle()
    test_mgllan_s1_active_bind_continuity()
    test_mgllan_s1_drone_range()
    test_mgllan_s1_no_abnormal_on_attack_hit()
