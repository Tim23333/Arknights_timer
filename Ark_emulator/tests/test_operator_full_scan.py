"""Full-operator skill pipeline smoke (all deployable operators).

Each operator deploys on a fresh Simulator, every manual skill is
activated with SP filled and interrupted.  Failures are collected and
reported; run via pytest (parallelized with multiprocessing inside).
"""
import json
import multiprocessing
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _operators():
    project_root = Path(__file__).resolve().parents[2]
    characters = project_root / "ark_parser" / "character" / "data" / "characters.json"
    d = json.load(open(characters, encoding="utf-8"))
    ops = []
    for k, v in d.items():
        if k.startswith(("token_", "trap_")):
            continue
        pos = v.get("position")
        if pos in (1, 2):
            ops.append((k, pos))
    return ops


def _check_one(item):
    cid, p = item
    try:
        sim = Simulator(level_id="level_main_01-01")
        sim.run_ticks(10)
        b = sim.battle
        b.max_cost = 100000.0
        b.cost = 0.0
        b.cost_increase_time = 1e7
        b.battle_cost_add(100.0)
        mask = 2 if p == 2 else 1
        deployed = None
        for r in range(b.map.rows):
            for c in range(b.map.cols):
                if b.map.buildable(r, c, mask) is not False:
                    ok, res = b.deploy(cid, r, c)
                    if ok:
                        deployed = b.operators[-1]
                        break
                    elif res and str(res) not in ("occupied", "not_buildable"):
                        return (cid, "deploy:%s" % res)
            if deployed:
                break
        if deployed is None:
            return (cid, "deploy_fail")
        sc = deployed.skill_controller
        if sc is None:
            # 无技能数据（skills null）的干员不要求 controller
            if not (deployed.skills or []):
                return None
            return (cid, "no_controller")
        manual = [s for s in sc.skills
                  if getattr(s, "sp_type", None) not in (0, 8)]
        if not manual:
            return None        # 纯部署/被动技能：部署时已自动触发
        worked = 0
        for i, s in enumerate(sc.skills):
            if getattr(s, "sp_type", None) in (0, 8):
                continue
            deployed.sp = float(getattr(s, "sp_cost", 0) or 0) + 1
            try:
                r = sc.activate(i)
                ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
                if ok or (isinstance(r, tuple) and r[1] == "already_active"):
                    worked += 1
            except Exception as ex:
                return (cid, "activate_crash:%s" % str(ex)[:50])
            try:
                sc.interrupt_active()
            except Exception:
                pass
        if worked == 0:
            return (cid, "no_skill_activated")
        return None
    except Exception as ex:
        return (cid, "crash:%s" % str(ex)[:60])


def test_operator_full_scan():
    ops = _operators()
    pool = multiprocessing.Pool(processes=8)
    results = pool.map(_check_one, ops)
    pool.close()
    pool.join()
    fails = [r for r in results if r is not None]
    assert not fails, "operator failures:\n" + \
        "\n".join("%s %s" % f for f in fails[:40])
    print("OK full operator scan:", len(ops), "operators")


if __name__ == "__main__":
    test_operator_full_scan()
