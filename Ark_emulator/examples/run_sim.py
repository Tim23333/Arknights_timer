"""Interactive simulator launcher.

Allows choosing a level (by keyword search), optionally a squad file,
custom enemy config and a custom level JSON, then runs the battle and
prints periodic snapshots (or starts the live server).

Usage::
    python examples/run_sim.py --search 1-1
    python examples/run_sim.py --level level_main_04-03 --squad squad.json
    python examples/run_sim.py --level level_main_01-01 --custom custom.json
    python examples/run_sim.py --level custom --custom-level custom_levels/custom.json
    python examples/run_sim.py --level level_main_01-01 --server --port 8794
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ark_emulator import Simulator
from ark_emulator.config import list_levels, search_levels


def pick_level(args):
    if args.level:
        return args.level
    if args.search:
        hits = search_levels(args.search)
        if not hits:
            print(f"no level matches {args.search!r}")
            return None
        print("matching levels:")
        for i, h in enumerate(hits[:20]):
            print(f"  [{i}] {h['stageId']} ({h['name']}) -> {h['levelId']}")
        try:
            idx = int(input("pick index: ").strip())
            return hits[idx]["levelId"]
        except (ValueError, IndexError):
            print("invalid choice")
            return None
    print(f"available levels: {len(list_levels())}")
    return "level_main_01-01"


def load_json(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="Ark_emulator launcher")
    ap.add_argument("--level", help="level id")
    ap.add_argument("--search", help="search levels by keyword")
    ap.add_argument("--squad", help="squad JSON file")
    ap.add_argument("--custom", help="custom enemies JSON file")
    ap.add_argument("--custom-level", help="custom level JSON file")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--server", action="store_true")
    ap.add_argument("--port", type=int, default=8794)
    args = ap.parse_args()

    level_id = pick_level(args)
    if not level_id:
        return
    squad = load_json(args.squad)
    custom = load_json(args.custom)
    custom_level = load_json(args.custom_level)
    print(f"level {level_id} | squad {len(squad or [])} | "
          f"custom enemies {len(custom or [])} | "
          f"custom level {'yes' if custom_level else 'no'}")

    sim = Simulator(level_id=level_id, squad=squad,
                    custom_enemies=custom, custom_level=custom_level)
    print(f"map {sim.battle.map.rows}x{sim.battle.map.cols} | "
          f"life {sim.battle.max_life_point} | "
          f"cost {sim.battle.initial_cost}")

    if args.server:
        from ark_emulator.live_server import LiveServer
        srv = LiveServer(sim, port=args.port, speed=1.0)
        srv.start()
        print(f"live server: http://127.0.0.1:{args.port}/ "
              f"(/snapshot /events /stream /action /levels)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            srv.stop()
        return

    auto_deploy = squad is not None
    deployed = set()
    interval = max(1, int(args.seconds / 10))
    for step in range(10):
        if auto_deploy:
            for mem in squad:
                cid = mem.get("charId")
                if cid in deployed or sim.battle.cost < 5:
                    continue
                for col in (4, 5, 3, 6, 2):
                    ok, _ = sim.deploy(cid, 3, col, direction=1)
                    if ok:
                        deployed.add(cid)
                        print(f"  auto-deploy {cid} @ (3,{col})")
                        break
        sim.run(seconds=interval)
        snap = sim.snapshot()
        print(f"[{step}] t={snap['t']:.1f}s life={snap['lifePoint']} "
              f"enemies={len(snap['enemies'])} cost={snap['cost']:.1f} "
              f"next={snap['waves'].get('nextSpawnAt')}")
        if snap["finished"]:
            print("battle finished:", snap["result"])
            break


if __name__ == "__main__":
    main()
