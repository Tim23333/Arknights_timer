# -*- coding: utf-8 -*-
"""Subclass trait tests: hammer splash, phalanx idle defense, liberator
idle ramp (blockCnt 0 / no attack / ATK ramps / skill reset)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7     # no natural recovery
    b.battle_cost_add(100.0)
    return sim, b


def _spawn(b, key, row, col, hp=99999.0, atk=0.0, **extra):
    attrs = {"maxHp": hp, "atk": atk, "def": 0.0}
    attrs.update(extra)
    b.spawn_enemy(key, 0, overrides={
        "attributes": attrs, "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_hammer_splash_hits_neighbors():
    sim, b = _battle()
    b.deploy("char_4131_odda", 3, 3)          # Quartz (hammer)
    op = b.operators[0]
    assert op.trait_system.is_hammer()
    atk = float(op.attributes.get("atk"))
    assert atk > 0
    main = _spawn(b, "enemy_1000_gopro_2", 3, 4, hp=99999.0)
    near1 = _spawn(b, "enemy_1000_gopro_2", 2, 4, hp=99999.0)
    near2 = _spawn(b, "enemy_1000_gopro_2", 4, 4, hp=99999.0)
    far = _spawn(b, "enemy_1000_gopro_2", 6, 4, hp=99999.0)
    _land_attack(b, op, main)
    assert abs((99999.0 - main.hp) - atk) < 0.01, (main.hp, atk)
    assert abs((99999.0 - near1.hp) - atk * 0.5) < 0.01, near1.hp
    assert abs((99999.0 - near2.hp) - atk * 0.5) < 0.01, near2.hp
    assert far.hp == 99999.0, far.hp
    assert any(x["type"] == "attack"
               and (x.get("data") or {}).get("type") == "hammer_splash"
               for x in b.events.snapshot_events())


def test_phalanx_idle_defense_toggle():
    sim, b = _battle()
    b.deploy("char_344_beewax", 2, 3)         # Beehunter (phalanx, ranged)
    op = b.operators[0]
    assert op.trait_system.is_phalanx()
    base_def = float(op.attributes.base.get("def"))
    base_mr = float(op.attributes.base.get("magicResistance"))
    op.trait_system.phalanx_sync()            # idle: doubled DEF + 20 MR
    assert abs(op.attributes.get("def") - base_def * 2.0) < 0.01
    assert abs(op.attributes.get("magicResistance") - (base_mr + 20.0)) < 0.01
    op._pending_attack = {"target": None}     # mid-windup: bonus off
    op.trait_system.phalanx_sync()
    assert abs(op.attributes.get("def") - base_def) < 0.01
    assert abs(op.attributes.get("magicResistance") - base_mr) < 0.01
    op._pending_attack = None
    op.trait_system.phalanx_sync()
    assert abs(op.attributes.get("def") - base_def * 2.0) < 0.01


def test_liberator_idle_no_attack_block0():
    sim, b = _battle()
    b.deploy("char_445_wscoot", 3, 3)         # Wind Chime (liberator)
    op = b.operators[0]
    assert op.trait_system.is_librator()
    op.trait_system.librator_sync(False, 0.0)
    assert op.attributes.get("blockCnt") == 0.0
    e = _spawn(b, "enemy_1000_gopro_2", 3, 3, hp=99999.0)
    for _ in range(90):
        b.tick_once()
    att = [x for x in b.events.snapshot_events()
           if x["type"] == "attack"
           and (x.get("data") or {}).get("unit") == op.inst_id]
    assert not att, "liberator must not attack while idle"
    assert e.hp == 99999.0


def test_liberator_ramp_and_skill_reset():
    sim, b = _battle()
    b.deploy("char_445_wscoot", 3, 3)
    op = b.operators[0]
    base_atk = float(op.attributes.base.get("atk"))
    base_block = float(op.attributes.base.get("blockCnt"))
    ts = op.trait_system
    ts.librator_sync(False, 0.0)
    assert abs(op.attributes.get("atk") - base_atk) < 0.01
    assert op.attributes.get("blockCnt") == 0.0
    # 2s idle -> +10% ATK (2.0 bonus over 40s)
    ts.librator_sync(False, 2.0)
    assert abs(op.attributes.get("atk") - base_atk * 1.1) < 0.01, \
        op.attributes.get("atk")
    # skill starts: blocking resumes, ramped ATK freezes
    ts.librator_sync(True, 0.0)
    assert abs(op.attributes.get("blockCnt") - base_block) < 0.01
    assert abs(op.attributes.get("atk") - base_atk * 1.1) < 0.01
    # skill ends: ramp resets to 0, idle blockCnt 0 returns
    ts.librator_sync(False, 0.0)
    assert abs(op.attributes.get("atk") - base_atk) < 0.01
    assert op.attributes.get("blockCnt") == 0.0
