"""Full stage run: a complete level battle loop from deploy to
finish/settlement, verifying the whole sim pipeline stays healthy."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def test_full_stage_run_to_finish():
    squad = [
        {"charId": "char_002_amiya", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},
        {"charId": "char_149_scave", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},
        {"charId": "char_003_kalts", "phase": 2, "level": 50,
         "skillIndex": 0, "skillLevels": [1, 1, 1]},
    ]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 3)
    b.deploy("char_002_amiya", 2, 3)
    b.deploy("char_003_kalts", 1, 3)
    for _ in range(5400):          # 180s 上限
        sim.run_ticks(1)
        if getattr(b, "finished", False):
            break
    snap = sim.snapshot()
    assert getattr(b, "finished", False), "stage must finish"
    assert snap.get("result") in ("victory", "defeat")
    assert snap["stats"]["kills"] > 0
    print("OK full stage run: result", snap.get("result"),
          "kills", snap["stats"]["kills"], "tick", b.tick)


if __name__ == "__main__":
    test_full_stage_run_to_finish()
