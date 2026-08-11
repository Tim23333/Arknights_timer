# -*- coding: utf-8 -*-
"""Lightweight level end-to-end smoke: several level types run a full
battle (deploy + 60s) without crashes or buff-event errors."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator

_SQUAD = [
    {"charId": "char_149_scave", "phase": 2, "level": 50,
     "skillIndex": 1, "skillLevels": [7, 7, 7]},
    {"charId": "char_473_mberry", "phase": 2, "level": 50,
     "skillIndex": 0, "skillLevels": [7, 7, 7]},
    {"charId": "char_002_amiya", "phase": 2, "level": 50,
     "skillIndex": 2, "skillLevels": [7, 7, 7]},
]


def _run_level(lid, stage, ticks):
    sim = Simulator(level_id=lid, stage_id=stage, squad=_SQUAD)
    sim.run_ticks(30)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    for c in _SQUAD:
        placed = False
        for row in range(1, 6):
            for col in range(1, 8):
                ok, _ = b.deploy(c["charId"], row, col)
                if ok:
                    placed = True
                    break
            if placed:
                break
    sim.run_ticks(ticks)
    snap = b.snapshot()
    errs = [e for e in snap["events"]
            if e.get("type") == "buff_event_error"]
    assert not errs, (lid, errs[:3])
    return snap


def test_level_smoke_basic():
    snap = _run_level("level_main_01-01", "main_01-01", 1800)
    assert snap["tick"] > 0


def test_level_smoke_mechanic():
    snap = _run_level("level_act38side_ex06", "act38side_ex06", 1800)
    assert snap["tick"] > 0


def test_level_smoke_roguelike():
    snap = _run_level("level_rogue5_b-9-a", "rogue5_b-9-a", 1800)
    assert snap["tick"] > 0
