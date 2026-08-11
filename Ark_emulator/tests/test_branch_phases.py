# -*- coding: utf-8 -*-
"""Level branch (BranchData) phase scheduling tests.

Covers the cursor-based BranchRuntime model (Nodes.MoveNextLevelBranch):
every trigger advances the branch cursor and deals the next phase like a
fragment (phase.preDelay + action.preDelay / count / interval), including
hiddenGroup rune gating and random spawn group resolution. Also verifies
that pending branch phases keep the battle from ending early.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.custom_levels import build_level
from ark_emulator.events import EventType


def _spawn_trace(sim, ticks, stop_on_finish=False):
    """Advance the battle and return [(tick, enemy_key), ...] spawns."""
    b = sim.battle
    out = []
    last_seq = 0
    for _ in range(ticks):
        if b.finished and stop_on_finish:
            break
        b.tick_once()
        for ev in b.events.snapshot_events(since_seq=last_seq):
            if ev["type"] == EventType.ENEMY_SPAWN:
                out.append((b.tick, ev["data"].get("key")))
        if b.events.log:
            last_seq = b.events.log[-1].seq
    return out


def _run_fire(diff, do_branch):
    sim = Simulator(level_id="level_act38side_ex06", rune_difficulty=diff,
                    seed=3)
    b = sim.battle
    b.life_point = 10000.0
    if do_branch:
        b.execute_branch("fire")
    trace = _spawn_trace(sim, 45 * 30)
    return [k for _, k in trace]


def test_branch_fire_hidden_difficulty_gating():
    """Branch SPAWN actions still respect hiddenGroup runes: NORMAL fires
    only cnvfire (hidden 'normal'), FOUR_STAR only cnvfire_1 ('fstar')."""
    base1 = _run_fire(1, False)
    br1 = _run_fire(1, True)
    assert br1.count("enemy_10041_cnvfire") == \
        base1.count("enemy_10041_cnvfire") + 1, (base1, br1)
    assert "enemy_10041_cnvfire_1" not in br1

    base2 = _run_fire(2, False)
    br2 = _run_fire(2, True)
    assert br2.count("enemy_10041_cnvfire_1") == \
        base2.count("enemy_10041_cnvfire_1") + 1, (base2, br2)
    assert "enemy_10041_cnvfire" not in br2


def test_branch_cursor_advances_and_loops():
    """Each trigger moves the cursor to the next phase; is_loop wraps."""
    sim = Simulator(level_id="level_rogue5_b-9-e", seed=5)
    b = sim.battle
    branch = b.raw["branches"]["dysuib_relic_branch"]
    phases = branch["phases"]
    assert len(phases) == 24
    for expect in range(4):
        n = b.execute_branch("dysuib_relic_branch")
        assert n > 0
        assert b._branch_cursors["dysuib_relic_branch"] == expect + 1
        assert b._branch_phases[-1]["phase"] == expect
    # wrap around with is_loop=True
    b._branch_cursors["dysuib_relic_branch"] = len(phases)
    assert b.execute_branch("dysuib_relic_branch", is_loop=True) > 0
    assert b._branch_phases[-1]["phase"] == 0
    assert b._branch_cursors["dysuib_relic_branch"] == 1


def test_branch_random_group_resolution_deterministic():
    """Branch phase random spawn groups resolve with the battle RNG to one
    candidate per group; same seed reproduces the same winners."""
    def winners(seed):
        sim = Simulator(level_id="level_rogue5_b-9-a", seed=seed)
        b = sim.battle
        b.execute_branch("dysuib_relic_branch")
        sched = b._branch_phases[-1]["scheduler"]
        return [(g["groupKey"], g["key"]) for g in sched.random_groups]

    a1 = winners(5)
    a2 = winners(5)
    b1 = winners(6)
    assert a1 == a2
    assert a1, "expected resolved groups"
    # phase 0 of this branch uses group r1
    assert any(gk == "r1" for gk, _ in a1), a1
    assert all(k is not None for _, k in a1)
    # deterministic seeds may still pick the same winner; both are valid
    assert all(not k.startswith("__bad__") for _, k in a1 + b1)


def test_branch_phase_timing():
    """Branch phase actions spawn at now + action.preDelay (balloon branch:
    cnvbln at 2s/6s and cnvbln_2 at 30s)."""
    sim = Simulator(level_id="level_act38side_ex06", rune_difficulty=1,
                    seed=3)
    b = sim.battle
    b.life_point = 10000.0
    b.execute_branch("balloon")
    trace = _spawn_trace(sim, 40 * 30)
    bln = [(t, k) for t, k in trace
           if k and k.startswith("enemy_10040_cnvbln")]
    assert (61, "enemy_10040_cnvbln") in bln, bln
    assert (181, "enemy_10040_cnvbln") in bln, bln
    assert (901, "enemy_10040_cnvbln_2") in bln, bln


def test_branch_pending_phase_delays_victory():
    """A scheduled-but-not-yet-fired branch phase keeps the battle running
    after the main waves finish (victory waits for branch actions)."""
    cl = build_level(rows=5, cols=8, enemies=[],
                     options={"maxLifePoint": 3, "initialCost": 10,
                              "costIncreaseTime": 1.0, "maxCost": 99})
    sim = Simulator(custom_level=cl, seed=1)
    b = sim.battle
    b.life_point = 10000.0
    b.raw["branches"] = {
        "test": {"phases": [{"preDelay": None, "actions": [
            {"actionType": {"value": 0, "name": "SPAWN"},
             "key": "enemy_1000_gopro", "count": 1, "preDelay": 60.0,
             "interval": 1.0, "routeIndex": 0},
        ]}]},
    }
    b.execute_branch("test")
    # main waves are empty and finish on the first tick; the branch phase
    # (spawn at t=60) must keep the battle alive until then
    trace = _spawn_trace(sim, 65 * 30)
    assert b.waves.finished
    assert (1801, "enemy_1000_gopro") in trace, \
        [(t, k) for t, k in trace if k]
    # battle did not end before the branch spawn fired
    assert b.result in (None, "victory")


def test_branch_random_phase_pick():
    """execute_branch_random picks a valid phase; not_repeat avoids repeats
    until the phase pool is exhausted."""
    sim = Simulator(level_id="level_rogue5_b-9-a", seed=7)
    b = sim.battle
    n_phases = len(b.raw["branches"]["dysuib_relic_branch"]["phases"])
    picked = []
    for _ in range(3):
        n = b.execute_branch_random("dysuib_relic_branch", not_repeat=True)
        assert n > 0
        picked.append(b._branch_phases[-1]["phase"])
    assert len(set(picked)) == 3, picked
    assert all(0 <= p < n_phases for p in picked)


def test_branch_snapshot_exposes_state():
    """Snapshot exposes branch cursors and the number of active phases."""
    sim = Simulator(level_id="level_act38side_ex06", rune_difficulty=1,
                    seed=3)
    b = sim.battle
    b.life_point = 10000.0
    b.execute_branch("fire")
    snap = b.snapshot()
    assert snap["branches"]["cursors"] == {"fire": 1}
    assert snap["branches"]["activePhases"] == 1
    b.tick_once()
    assert b.snapshot()["branches"]["activePhases"] == 0


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
    print("all branch phase tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)
