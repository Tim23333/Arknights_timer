# -*- coding: utf-8 -*-
"""Precise cost-recovery timer tests (MECHANICS section 10).

Covers: exact +1 per costIncreaseTime (no float drift), pause-while-full
with remainder retention, timer modifiers (period multiply), absolute set,
lock/unlock, negative-cost half-speed recovery, no-recovery sentinel and
snapshot costTimer fields.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _battle():
    sim = Simulator("level_main_01-01")   # initialCost=10, costIncreaseTime=1
    return sim, sim.battle


def test_precise_periodic_recovery():
    """+1 exactly every 30 ticks (no fractional or drifted timing)."""
    sim, b = _battle()
    assert b.cost == 10.0
    sim.run_ticks(29)
    assert b.cost == 10.0
    sim.run_ticks(1)
    assert b.cost == 11.0
    sim.run_ticks(30)
    assert b.cost == 12.0


def test_pauses_when_full_keeps_remainder():
    sim, b = _battle()
    b.cost = b.max_cost - 1.0
    b._cost_acc = 0.0
    for _ in range(30):
        b.tick_once()
    assert b.cost == b.max_cost
    acc_after = b._cost_acc
    for _ in range(120):                  # 4s paused while full
        b.tick_once()
    assert b.cost == b.max_cost
    assert abs(b._cost_acc - acc_after) < 1e-9
    b.cost = b.max_cost - 9.0             # spend, recovery resumes
    for _ in range(30):
        b.tick_once()
    assert abs(b.cost - (b.max_cost - 8.0)) < 0.01, b.cost


def test_cost_timer_modifier_multiplies_period():
    sim, b = _battle()
    b.add_cost_timer_modifier(0.5)        # period 1.0 -> 0.5s
    assert abs(b.cost_period() - 0.5) < 1e-9
    sim.run_ticks(30)                      # 1s -> +2
    assert abs(b.cost - 12.0) < 0.01, b.cost
    b.remove_cost_timer_modifier(None)
    assert b.cost_period() == 1.0


def test_multiple_modifiers_multiply_and_lock():
    """Multiple cost-timer modifiers multiply the period; a modifier with
    costAddLocked freezes recovery until removed (dump.cs CostTimerModifier)."""
    sim, b = _battle()
    b.add_cost_timer_modifier(1.5, source="a", priority=1)
    b.add_cost_timer_modifier(2.0, source="b", priority=2)
    assert abs(b.cost_period() - 3.0) < 1e-9, b.cost_period()
    sim.run_ticks(30)                        # 1s with 3s period -> no +1
    assert b.cost == 10.0, b.cost
    b.remove_cost_timer_modifier("a")
    assert abs(b.cost_period() - 2.0) < 1e-9
    # costAddLocked freezes natural recovery
    b.add_cost_timer_modifier(1.0, source="lock", priority=9,
                              cost_add_locked=True)
    for _ in range(120):
        b.tick_once()
    assert b.cost == 10.0, b.cost
    st = b.cost_timer_state()
    assert st["locked"] is True, st
    b.remove_cost_timer_modifier("lock")
    for _ in range(60):                      # 2s -> +1
        b.tick_once()
    assert b.cost == 11.0, b.cost


def test_set_and_modify_cost_increase_time():
    sim, b = _battle()
    b.set_cost_increase_time(2.0)
    assert abs(b.cost_period() - 2.0) < 1e-9
    sim.run_ticks(120)                     # 4s -> +2
    assert abs(b.cost - 12.0) < 0.01, b.cost
    b.modify_cost_increase_time(0.5)       # 2.0 * 0.5 = 1.0
    assert abs(b.cost_period() - 1.0) < 1e-9


def test_lock_cost_increasement():
    sim, b = _battle()
    b.lock_cost_increasement(True, reason=1)
    for _ in range(120):
        b.tick_once()
    assert b.cost == 10.0                  # no recovery while locked
    b.lock_cost_increasement(False)
    for _ in range(30):
        b.tick_once()
    assert abs(b.cost - 11.0) < 0.01, b.cost


def test_negative_cost_half_speed():
    sim, b = _battle()
    b.cost = -4.0
    # negative recovery multiplier 0.5 -> effective period 2.0s
    assert abs(b.cost_period() - 2.0) < 1e-9
    sim.run_ticks(120)                     # 4s -> +2
    assert abs(b.cost - (-2.0)) < 0.01, b.cost


def test_no_recovery_sentinel():
    sim, b = _battle()
    b.set_cost_increase_time(1e7)
    for _ in range(90):
        b.tick_once()
    assert b.cost == 10.0
    st = sim.snapshot()["costTimer"]
    assert st["nextCostIn"] is None
    assert st["period"] == 1e7


def test_snapshot_cost_timer_fields():
    sim, b = _battle()
    st = sim.snapshot()["costTimer"]
    for k in ("period", "progress", "nextCostIn", "locked"):
        assert k in st, st
    assert st["period"] == 1.0
    assert 0.0 <= st["progress"] <= 1.0
    assert st["nextCostIn"] is not None and st["nextCostIn"] > 0


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("OK", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    print("all cost manager tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)
