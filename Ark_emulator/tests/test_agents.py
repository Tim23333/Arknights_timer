# -*- coding: utf-8 -*-
"""Scripted agent tests: GreedyDefender plays levels via AgentEnv."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.agent_env import AgentEnv
from ark_emulator.agents import GreedyDefender, play_episode
from ark_emulator.custom_levels import build_level


def _kill_level_env():
    lv = build_level(rows=6, cols=10, enemies=[],
                     options={"initialCost": 99, "maxCost": 99,
                              "costIncreaseTime": 1.0})
    lv["waveTimeline"] = [{"t": 0.5, "key": "enemy_1000_gopro",
                           "routeIndex": 0, "actionType": "SPAWN"}]
    env = AgentEnv(level_id="custom", custom_level=lv,
                   squad=[{"charId": "char_1045_svash2", "phase": 2,
                           "level": 50}])
    env.reset(seed=4)
    return env


def test_greedy_wins_custom_level():
    env = _kill_level_env()
    agent = GreedyDefender(vanguards=("char_1045_svash2",))
    reward, result, tick = play_episode(env, agent, max_steps=5000)
    assert result == "victory", result
    assert reward >= 100.0, reward


def test_greedy_runs_on_main_level():
    env = AgentEnv("level_main_01-01", squad=[
        {"charId": "char_284_spot", "phase": 0, "level": 50},
        {"charId": "char_502_nblade", "phase": 0, "level": 50},
        {"charId": "char_123_fang", "phase": 0, "level": 50},
        {"charId": "char_149_scave", "phase": 0, "level": 50},
        {"charId": "char_150_snakek", "phase": 0, "level": 50},
        {"charId": "char_002_amiya", "phase": 0, "level": 50}])
    agent = GreedyDefender(
        vanguards=("char_502_nblade", "char_123_fang", "char_149_scave"),
        blockers=("char_150_snakek",), medic=None,
        early_blocker="char_284_spot")
    reward, result, tick = play_episode(env, agent, max_steps=4000)
    assert result in ("victory", "defeat", None), result
    assert env.info()["stats"]["deployments"] >= 1


def test_beam_agent_runs_and_wins_custom_level():
    """BeamAgent (tiny rollout) works end-to-end on the custom kill level."""
    from ark_emulator.agents import BeamAgent
    env = _kill_level_env()
    agent = BeamAgent(
        vanguards=("char_1045_svash2",),
        blockers=(), medic=None,
        decide_every=8.0, rollout_seconds=1.0, beam_cells=1,
        beam_deploys=2)
    reward, result, tick = play_episode(env, agent, max_steps=3000)
    assert result == "victory", result
    assert reward >= 100.0, reward


def test_leak_event_carries_position():
    """enemy_reach_exit events expose row/col/route for AI/replay."""
    env = AgentEnv("level_main_01-01")
    env.reset(seed=11)
    saw = False
    for _ in range(1200):
        obs, reward, done, info = env.step(None)
        for ev in obs.get("events", []):
            if ev["type"] == "enemy_reach_exit":
                d = ev["data"]
                assert "row" in d and "col" in d and "routeIndex" in d, d
                saw = True
        if done:
            break
    assert saw, "no leak occurred"


def test_agents_import_and_evaluate_helper():
    from ark_emulator.agents import evaluate
    lv = build_level(rows=6, cols=10, enemies=[])
    lv["waveTimeline"] = [{"t": 0.5, "key": "enemy_1000_gopro",
                           "routeIndex": 0, "actionType": "SPAWN"}]
    stats = evaluate(["custom"],
                     seeds=(1, 2),
                     agent=GreedyDefender(vanguards=("char_1045_svash2",)),
                     squad=[{"charId": "char_1045_svash2", "phase": 2,
                             "level": 50}],
                     max_steps=5000,
                     custom_levels={"custom": lv})
    assert "custom" in stats
    assert len(stats["custom"]["seeds"]) == 2
    assert stats["custom"]["results"] == ["victory", "victory"]


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
    print("all agent tests passed" if not failed else "%d failed" % failed)
    sys.exit(1 if failed else 0)
