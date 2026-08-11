# -*- coding: utf-8 -*-
"""AgentEnv (AI battle interface) tests.

Covers: reset/obs/info, valid+invalid actions, reward deltas (kills/leaks),
victory bonus, determinism, and the random-policy demo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.agent_env import AgentEnv, play_random
from ark_emulator.custom_levels import build_level


def test_reset_obs_info():
    env = AgentEnv("level_main_01-01", squad=[{"charId": "char_002_amiya"}])
    obs, info = env.reset(seed=7)
    assert obs["tick"] == 0 and "map" in obs and "deployed" in obs
    assert info["levelId"] == "level_main_01-01"
    assert info["lifePoint"] > 0 and info["cost"] >= 0
    assert env.squad_ids() == ["char_002_amiya"]


def test_invalid_action_no_crash():
    env = AgentEnv("level_main_01-01")
    env.reset(seed=1)
    obs, reward, done, info = env.step({"type": "nonsense"})
    assert info["invalid"] is True and reward == 0.0 and done is False
    obs, reward, done, info = env.step({"type": "deploy", "charId": "nope",
                                        "row": 0, "col": 0})
    assert info["invalid"] is True


def test_deploy_action_valid():
    env = AgentEnv("level_main_01-01", squad=[
        {"charId": "char_149_scave", "phase": 2, "level": 50}])
    env.reset(seed=2)
    env.sim.battle.max_cost = 100000.0
    env.sim.battle.battle_cost_add(100.0)
    obs, reward, done, info = env.step({"type": "deploy",
                                        "charId": "char_149_scave",
                                        "row": 3, "col": 3,
                                        "direction": 1})
    assert info["invalid"] is False, info
    assert any(o["charId"] == "char_149_scave"
               for o in obs["deployed"]), obs["deployed"]


def _kill_level_env():
    lv = build_level(rows=6, cols=10, enemies=[])
    lv["waveTimeline"] = [{"t": 0.5, "key": "enemy_1000_gopro",
                           "routeIndex": 0, "actionType": "SPAWN"}]
    env = AgentEnv(level_id="custom", custom_level=lv,
                   kill_reward=10.0, leak_penalty=20.0,
                   victory_bonus=100.0, defeat_penalty=-50.0)
    env.reset(seed=3)
    env.sim.battle.max_cost = 100000.0
    env.sim.battle.battle_cost_add(100.0)
    return env


def test_kill_and_victory_reward():
    env = _kill_level_env()
    env.step({"type": "deploy", "charId": "char_1045_svash2",
              "row": 2, "col": 5, "direction": 1})
    total = 0.0
    guard = 0
    while not env.info()["finished"] and guard < 20000:
        obs, reward, done, info = env.step({"type": "step_ticks",
                                            "ticks": 30})
        total += reward
        guard += 1
        if done:
            break
    assert env.info()["result"] == "victory", env.info()["result"]
    assert total >= 100.0, total        # victory bonus dominates
    assert env.info()["stats"]["kills"] >= 1


def test_determinism():
    def trace(seed):
        env = AgentEnv("level_main_01-01")
        env.reset(seed=seed)
        snapshots = []
        for _ in range(120):
            env.step({"type": "step_ticks", "ticks": 5})
            s = env.observe()
            snapshots.append((s["tick"], s["cost"], s["lifePoint"],
                              len(s["enemies"])))
        return snapshots
    assert trace(42) == trace(42)


def test_wait_action_advances_tick():
    env = AgentEnv("level_main_01-01")
    obs, _ = env.reset(seed=9)
    t0 = obs["tick"]
    obs, reward, done, info = env.step(None)
    assert info["invalid"] is False
    assert obs["tick"] == t0 + 1


def test_legal_actions():
    env = AgentEnv("level_main_01-01", squad=[
        {"charId": "char_149_scave", "phase": 2, "level": 50}])
    env.reset(seed=10)
    env.sim.battle.max_cost = 100000.0
    env.sim.battle.battle_cost_add(100.0)
    acts = env.legal_actions(max_cells=8)
    deploys = [a for a in acts if a["type"] == "deploy"]
    assert deploys, acts
    assert all(a["charId"] == "char_149_scave" for a in deploys)
    # deploy one, then withdraw becomes legal
    obs, _, _, info = env.step(deploys[0])
    assert info["invalid"] is False
    acts2 = env.legal_actions()
    assert any(a["type"] == "withdraw" for a in acts2)
    # the deployed char is no longer deployable
    assert not any(a["type"] == "deploy" and a["charId"] == "char_149_scave"
                   for a in acts2)


def test_reward_shaping_damage():
    env = _kill_level_env()
    env.damage_reward = 0.01
    env.step({"type": "deploy", "charId": "char_1045_svash2",
              "row": 2, "col": 5, "direction": 1})
    total = 0.0
    guard = 0
    while not env.info()["finished"] and guard < 20000:
        obs, reward, done, info = env.step(None)
        total += reward
        guard += 1
        if done:
            break
    # damage shaping should add positive reward on top of kill/victory
    assert total > 100.0, total


def test_batch_env():
    from ark_emulator.agent_env import BatchEnv
    batch = BatchEnv(3, "level_main_01-01")
    outs = batch.reset_all(seeds=[1, 2, 3])
    assert len(outs) == 3
    obs0, _ = outs[0]
    assert obs0["tick"] == 0
    rs = batch.step_all([None, None, None])
    assert len(rs) == 3
    ticks = [o["tick"] for o, _, _, _ in rs]
    assert ticks == [1, 1, 1]
    assert all(not d for d in batch.done_all())


def test_play_random_demo():
    total, result, tick = play_random(AgentEnv("level_main_01-01"), steps=60,
                                      seed=5)
    assert isinstance(total, float) and result in ("victory", "defeat",
                                                   None)


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
    print("all agent env tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)
