# -*- coding: utf-8 -*-
"""Operator skill activation smoke: representative operators across every
profession must deploy and have a working skill pipeline. Deploy-trigger
skills (spType 8) auto-activate on deploy; manual skills activate with SP
filled; an already-active deploy skill legitimately blocks others."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator

# (char_id, position 1=melee 2=ranged)
OPS = [
    ("char_010_chen", 1),      # 近卫
    ("char_136_hsguma", 1),    # 重装
    ("char_112_siege", 1),     # 先锋
    ("char_002_amiya", 2),     # 术师
    ("char_103_angel", 2),     # 射手
    ("char_003_kalts", 2),     # 医疗
    ("char_101_sora", 2),      # 辅助
    ("char_102_texas", 1),     # 特种 (德克萨斯)
]


def _deploy(b, cid, pos):
    mask = 2 if pos == 2 else 1
    for r in range(b.map.rows):
        for c in range(b.map.cols):
            if b.map.buildable(r, c, mask) is not False:
                ok, res = b.deploy(cid, r, c)
                if ok:
                    return b.operators[-1]
    return None


def test_operator_skill_pipeline_smoke():
    for cid, pos in OPS:
        sim = Simulator(level_id="level_main_01-01")
        sim.run_ticks(10)
        b = sim.battle
        b.max_cost = 100000.0
        b.cost = 0.0
        b.cost_increase_time = 1e7
        b.battle_cost_add(100.0)
        op = _deploy(b, cid, pos)
        assert op is not None, "deploy %s" % cid
        sc = op.skill_controller
        assert sc is not None, "no skill controller for %s" % cid
        worked = False
        for i, s in enumerate(sc.skills):
            sc.equipped_index = i
            if getattr(s, "sp_type", None) in (0, 8):
                continue       # deploy/passive skills are not manual
            op.sp = float(getattr(s, "sp_cost", 0) or 0) + 1
            r = sc.activate(i)
            ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
            if ok or (isinstance(r, tuple) and r[1] == "already_active"):
                worked = True
            try:
                sc.interrupt_active()
            except Exception:
                sc.active = None
        # every tested operator either has a manual skill that activates,
        # or is occupied by an auto-activated deploy skill (already_active
        # on the first try counts)
        assert worked, "no working manual skill for %s" % cid
        print("OK", cid)
