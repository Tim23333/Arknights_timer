"""Full-bundle scan for unhandled buff nodes.

Loads every level in the stage bundle, runs ``ticks`` logic ticks and
reports any ``buff_node_unhandled`` events (deduped per node type per
level).  Uses a small multiprocessing pool; each worker shares one parsed
DataStore bundle (process-level cache) so memory stays flat.

Usage:  python tools/scan_unhandled.py [--ticks 600] [--workers 4]
"""
import argparse
import collections
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.loader import DataStore


def _scan_slice(args):
    level_ids, ticks = args
    out = {}
    for lid in level_ids:
        try:
            sim = Simulator(level_id=lid)
            b = sim.battle
            sim.run_ticks(ticks)
            un = [x for x in b.events.snapshot_events()
                  if x["type"] == "buff_node_unhandled"]
            if un:
                out[lid] = [x["data"].get("node") for x in un]
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--stride", type=int, default=1,
                    help="scan every Nth level (1 = full bundle)")
    args = ap.parse_args()

    store = DataStore()
    keys = sorted(store.bundle["levels"])
    sample = keys[::args.stride] if args.stride > 1 else keys
    print(f"levels to scan: {len(sample)} (of {len(keys)}), "
          f"ticks={args.ticks}, workers={args.workers}", flush=True)

    chunk = max(1, len(sample) // (args.workers * 8))
    slices = [sample[i:i + chunk]
              for i in range(0, len(sample), chunk)]
    pool = multiprocessing.Pool(processes=args.workers)
    results = pool.map(_scan_slice,
                       [(sl, args.ticks) for sl in slices],
                       chunksize=1)
    pool.close()
    pool.join()

    by_node = collections.Counter()
    levels = {}
    for r in results:
        for lid, nodes in r.items():
            levels[lid] = nodes
            for n in nodes:
                by_node[n] += 1
    print(f"scanned {len(sample)} levels; unhandled node types: "
          f"{len(by_node)}, instances: {sum(by_node.values())}")
    for n, c in by_node.most_common(40):
        print(f"  {c:4d} {n}")
    if levels:
        print("levels with unhandled:")
        for lid, nodes in sorted(levels.items()):
            print(f"  {lid}: {nodes}")
    return 0 if not by_node else 1


if __name__ == "__main__":
    raise SystemExit(main())
