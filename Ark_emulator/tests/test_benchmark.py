# -*- coding: utf-8 -*-
"""Benchmark harness tests (structure + a tiny real run)."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.benchmark import run_benchmark, save_report, print_report


def test_benchmark_structure():
    rep = run_benchmark(["level_main_01-01", "level_main_00-02"],
                        seeds=(0, 1), max_steps=400)
    assert rep["summary"]["episodes"] == 4, rep["summary"]
    for lid in ("level_main_01-01", "level_main_00-02"):
        lv = rep["levels"][lid]
        assert len(lv["seeds"]) == 2
        for p in lv["seeds"]:
            for k in ("seed", "result", "tick", "reward", "kills", "leaks",
                      "deploys"):
                assert k in p, (lid, p)
    assert 0.0 <= rep["summary"]["winRate"] <= 1.0


def test_save_report(tmp_path=None):
    import tempfile
    rep = run_benchmark(["level_main_01-01"], seeds=(0,), max_steps=300)
    with tempfile.TemporaryDirectory() as td:
        p = save_report(rep, path=os.path.join(td, "report.json"))
        assert os.path.exists(p)
        loaded = json.load(open(p, encoding="utf-8"))
        assert loaded["summary"]["episodes"] == 1


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
    print("all benchmark tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)
