"""Trap devices that grant SP to allies:

  - trap_200_muulcl 喷射汽水机: sprays a random friendly operator every
    0.2s, granting attack@sp (3) SP
  - trap_237_hlnpcb 圣堂保育员扮演者: full-map aura - every second
    friendly units recover attack@sp (1) SP; sleeping (DOZE) allies get
    attack@sleeper_sp (2) extra
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import AbnormalFlag


def _setup():
    squad = [{"charId": "char_149_scave", "phase": 2, "level": 50,
              "skillIndex": 0, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 4)
    op = b.operators[0]
    return sim, b, op


def _spawn(b, trap_key, owner):
    ok, pid = b.spawn_token_forced(trap_key, 3, 3, owner=owner)
    assert ok, (trap_key, ok)
    return [t for t in b.tokens if not t.dead][-1]


def _sp_gain(seconds, with_trap, sleeping=False):
    """SP gained over `seconds`（扣除自然回复用对比法）."""
    sim, b, op = _setup()
    if sleeping:
        b.add_abnormal(op, AbnormalFlag.DOZE, seconds + 5.0)
    if with_trap:
        _spawn(b, "trap_237_hlnpcb", op)
    op.sp = 0.0
    for _ in range(seconds * 30):
        b.tick_once()
    return op.sp


def test_soda_machine_grants_sp():
    """喷射汽水机：每 0.2s 给随机友方 +3 技力."""
    sim, b, op = _setup()
    _spawn(b, "trap_200_muulcl", op)
    op.sp = 0.0
    for _ in range(60):          # 2s
        b.tick_once()
    assert op.sp >= 20.0, op.sp   # 至少 7 次 × 3
    assert op.sp <= 35.0, op.sp
    print("OK soda machine SP:", op.sp)


def test_nursery_aura_grants_sp():
    """圣堂保育员：全图友方每秒 +1 技力."""
    base = _sp_gain(4, with_trap=False)
    aura = _sp_gain(4, with_trap=True)
    assert abs((aura - base) - 3.0) < 0.01, (base, aura)
    print("OK nursery aura SP (delta):", aura - base)


def test_nursery_aura_sleeping_extra():
    """圣堂保育员：睡眠（美梦）友方每秒额外 +2 技力（共 +3）."""
    base_sleep = _sp_gain(4, with_trap=False, sleeping=True)
    aura_sleep = _sp_gain(4, with_trap=True, sleeping=True)
    # 睡眠期间：每秒 +1（光环）+ 2（sleeper_sp）= 3，4 秒触发 3 次 = 9
    assert abs((aura_sleep - base_sleep) - 9.0) < 0.01, \
        (base_sleep, aura_sleep)
    print("OK nursery sleeping extra SP (delta):", aura_sleep - base_sleep)


if __name__ == "__main__":
    test_soda_machine_grants_sp()
    test_nursery_aura_grants_sp()
    test_nursery_aura_sleeping_extra()
