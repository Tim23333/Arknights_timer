# -*- coding: utf-8 -*-
"""Full enemy-skill smoke: every enemy x every skill must spawn, cast and
update without crashing (regression for empty-blackboard entries etc.)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState

_CATALOG = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "..", "ark_parser", "enemy", "data",
    "skill_behavior_catalog.json")


def _iter_catalog():
    with open(_CATALOG, encoding="utf-8") as f:
        catalog = json.load(f)
    for prefab, entries in catalog.items():
        for entry in entries:
            yield prefab, entry


def test_enemy_skill_smoke_all_catalog():
    """Every enemy x every skill spawns, casts and updates without error."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    errors = []
    processed = 0
    for prefab, entry in _iter_catalog():
        eid = entry.get("enemyId") or ""
        processed += 1
        try:
            b.spawn_enemy(eid, 0)
            if not b.enemies:
                continue
            e = b.enemies[-1]
            e.state = EnemyState.COMBAT
            sc = e.skill_controller
            if sc is None:
                b.enemies = []
                continue
            tgt = b.operators[0] if b.operators else None
            for sk in sc.skills:
                try:
                    e.sp = sk.sp_cost if sk.sp_cost else 5.0
                    sc._start_cast((sk, tgt))
                    for _ in range(90):
                        sc.update(1.0 / 30.0)
                except Exception as ex:  # noqa: BLE001
                    errors.append((eid, prefab, sk.prefab_key,
                                   repr(ex)[:120]))
                    break
        except Exception as ex:  # noqa: BLE001
            errors.append((eid, prefab, "ALL", repr(ex)[:140]))
        finally:
            b.enemies = []
            b.tokens = []
            b.projectiles = []
    assert not errors, (processed, errors[:20])
