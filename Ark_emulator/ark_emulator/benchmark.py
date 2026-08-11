"""Batch agent benchmark: scripted agents vs levels x seeds.

Produces a baseline report (JSON) so future RL/search policies can be
compared: per-level win rate, reward, kills/leaks/deploys, end tick.
"""
import json
import os
import time

from .agent_env import BatchEnv
from .agents import GreedyDefender

DEFAULT_LEVELS = [
    "level_main_00-02",
    "level_main_01-01",
    "level_main_01-02",
    "level_main_01-03",
    "level_main_01-04",
]

DEFAULT_SQUAD = [
    {"charId": "char_284_spot", "phase": 0, "level": 50},
    {"charId": "char_502_nblade", "phase": 0, "level": 50},
    {"charId": "char_123_fang", "phase": 0, "level": 50},
    {"charId": "char_149_scave", "phase": 0, "level": 50},
    {"charId": "char_150_snakek", "phase": 0, "level": 50},
    {"charId": "char_002_amiya", "phase": 0, "level": 50},
]


def default_agent():
    return GreedyDefender(
        vanguards=("char_502_nblade", "char_123_fang", "char_149_scave"),
        blockers=("char_150_snakek",),
        medic=None,
        early_blocker="char_284_spot")


def run_benchmark(level_ids=DEFAULT_LEVELS, seeds=(0, 1, 2), agent=None,
                  squad=None, max_steps=3000):
    """Run agent over levels x seeds; returns the report dict."""
    if agent is None:
        agent = default_agent()
    squad = squad if squad is not None else DEFAULT_SQUAD
    import copy as _copy
    t0 = time.time()
    out = {
        "meta": {
            "generatedBy": "benchmark.py",
            "agent": type(agent).__name__,
            "levelCount": len(level_ids),
            "seeds": list(seeds),
            "maxSteps": int(max_steps),
        },
        "levels": {},
    }
    for lid in level_ids:
        batch = BatchEnv(len(seeds), level_id=lid, squad=list(squad))
        batch.reset_all(seeds=list(seeds))
        # each env gets its own agent copy (no shared _ever/redeploy state)
        agents = [_copy.deepcopy(agent) for _ in range(len(seeds))]
        rewards = [0.0] * len(seeds)
        finals = [None] * len(seeds)
        steps = 0
        while steps < max_steps:
            infos = batch.info_all()
            if all(i["finished"] for i in infos):
                break
            obss = [e.observe() for e in batch.envs]
            actions = [ag.act(e, o, i)
                       for ag, e, o, i in zip(agents, batch.envs, obss,
                                              infos)]
            rs = batch.step_all(actions)
            for k, (o, r, d, i) in enumerate(rs):
                rewards[k] += r
                if d and finals[k] is None:
                    finals[k] = (i["result"], i["tick"])
            steps += 1
        per = []
        for k in range(len(seeds)):
            info = batch.info_all()[k]
            st = info["stats"]
            res = finals[k] or ("running", info["tick"])
            per.append({
                "seed": seeds[k],
                "result": res[0],
                "tick": res[1],
                "reward": round(rewards[k], 1),
                "kills": st.get("kills", 0),
                "leaks": st.get("leaks", 0),
                "deploys": st.get("deployments", 0),
                "casts": st.get("skillCasts", 0),
            })
        wins = sum(1 for p in per if p["result"] == "victory")
        out["levels"][lid] = {
            "seeds": per,
            "winRate": round(wins / len(seeds), 3),
        }
    total_eps = len(level_ids) * len(seeds)
    total_wins = sum(1 for lv in out["levels"].values()
                     for p in lv["seeds"] if p["result"] == "victory")
    out["summary"] = {
        "episodes": total_eps,
        "wins": total_wins,
        "winRate": round(total_wins / max(1, total_eps), 3),
        "elapsedSec": round(time.time() - t0, 1),
    }
    return out


def save_report(report, path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "examples", "benchmark_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return path


def print_report(report):
    print(f"agent={report['meta']['agent']} "
          f"seeds={report['meta']['seeds']} "
          f"winRate={report['summary']['winRate']} "
          f"({report['summary']['wins']}/{report['summary']['episodes']}) "
          f"{report['summary']['elapsedSec']}s")
    for lid, lv in report["levels"].items():
        row = lv["seeds"][0]
        print(f"  {lid}: winRate={lv['winRate']} "
              f"result={row['result']} kills={row['kills']} "
              f"leaks={row['leaks']} deploys={row['deploys']}")
