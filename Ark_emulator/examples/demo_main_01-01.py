"""Ark_emulator smoke demo: run level_main_01-01, deploy operators, observe
enemy movement / blocking / damage, pause, and dump a full-field snapshot.

Run:
    python examples/demo_main_01-01.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ark_emulator import Simulator


def main():
    sim = Simulator(level_id="level_main_01-01")
    print(f"== level {sim.level_id} | seed {sim.battle.seed}")
    print(f"map {sim.battle.map.rows}x{sim.battle.map.cols} | "
          f"life {sim.battle.max_life_point} | cost "
          f"{sim.battle.initial_cost}/{sim.battle.max_cost}")

    # deploy a cheap vanguard blocker on the main route (row 3)
    ok, res = sim.deploy("char_149_scave", 3, 4, direction=1)
    name = sim.battle._char_base("char_149_scave").get("name", "scave")
    print(f"deploy {name} @ (3,4): ok={ok} id={res} cost={sim.battle.cost:.1f}")

    # run 15 more seconds, then activate the operator's skill when ready
    sim.run(seconds=15)
    snap = sim.snapshot()
    for d in snap["deployed"]:
        if d["sp"] >= d["spMax"] and len(d["skills"]) > 1:
            ok, res = sim.activate_skill(d["instId"], 1)
            print(f"activate {d['charId']} skill1: ok={ok} res={res}")
            break
    snap = sim.snapshot()
    print(f"\n== after {snap['t']:.1f}s: life={snap['lifePoint']} "
          f"cost={snap['cost']:.1f} enemies={len(snap['enemies'])}")
    for e in snap["enemies"][:6]:
        print(f"  enemy {e['key']} @ ({e['row']},{e['col']}) hp={e['hp']:.0f} "
              f"state={e['state']} distToExit={e['distToFinal']:.2f}")

    # pause + step + resume
    sim.pause()
    print("\npaused:", sim.snapshot()["paused"])
    sim.step(30)                              # advance 1s while paused
    print("after step(30):", sim.snapshot()["tick"])
    sim.resume()

    # run to the end (max 5 minutes)
    sim.run(seconds=120)
    final = sim.snapshot()
    print(f"\n== final: finished={final['finished']} result={final['result']} "
          f"life={final['lifePoint']} tick={final['tick']}")
    print("events:", len(final["events"]),
          "spawn=", sum(1 for x in final["events"] if x["type"] == "enemy_spawn"),
          "damage=", sum(1 for x in final["events"] if x["type"] == "damage"),
          "reach_exit=", sum(1 for x in final["events"]
                             if x["type"] == "enemy_reach_exit"))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "snapshot_demo.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=1)
    print(f"\nsnapshot written to {out}")


if __name__ == "__main__":
    main()
