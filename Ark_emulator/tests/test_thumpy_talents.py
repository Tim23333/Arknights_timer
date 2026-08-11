# -*- coding: utf-8 -*-
"""Thumpy (珊比) talent wiring + generic barrier (屏障) subsystem tests.

Covers talent 1 探险理论 (erosion attach on physical output + burst-cooldown
reduction), talent 2 坚硬脚板 (DEF stacks + barrier on marked-enemy burst),
and the barrier absorption pool in the damage pipeline.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy_thumpy(b):
    b.deploy("char_4235_thumpy", 3, 3)       # 珊比, ground, facing right
    op = b.operators[0]
    assert op.talent_system is not None
    return op


def _spawn(b, key, row, col, mass=1.0, hp=50000.0):
    b.spawn_enemy(key, 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": 0.0,
                       "massLevel": mass},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_thumpy_talent1_ep_attach_and_mark():
    sim, b = _battle()
    op = _deploy_thumpy(b)
    ts = op.talent_system
    assert ts._has_thumpy_ep()
    e = _spawn(b, "enemy_1000_gopro_2", 3, 4)
    _land_attack(b, op, e)
    marks = [x for x in e.buffs if x.get("key") == "thumpy_water_mark"]
    assert marks, [x.get("key") for x in e.buffs]
    assert marks[-1].get("source") is op
    ep = [x for x in e.buffs if x.get("key") == "ep_water"]
    assert ep and ep[-1].get("value", 0.0) > 0, ep
    ratio = ts.bb("ep_damage_ratio[trigger]")
    expect = op.attributes.get("atk") * float(ratio)
    # full-bar model: value = remaining (1000 - damage)
    assert abs(ep[-1]["value"] - (1000.0 - expect)) < 1e-6, (ep[-1], expect)


def test_thumpy_talent1_reduces_burst_cd_instead_of_ep():
    sim, b = _battle()
    op = _deploy_thumpy(b)
    e = _spawn(b, "enemy_1000_gopro_2", 3, 4)
    b.add_buff(e, {"key": "ep_burst_cd_1", "remaining_ticks": 60 * 30,
                   "layers": 1})
    cd = [x for x in e.buffs if x.get("key") == "ep_burst_cd_1"][0]
    ticks0 = cd["remaining_ticks"]
    _land_attack(b, op, e)
    assert cd["remaining_ticks"] == ticks0 - 30, (
        cd["remaining_ticks"], ticks0)
    assert not [x for x in e.buffs if x.get("key") == "ep_water"]
    assert any(x["type"] == "thumpy_ep_cd_reduce"
               for x in b.events.snapshot_events())


def test_thumpy_talent2_burst_reward_stacks():
    sim, b = _battle()
    op = _deploy_thumpy(b)
    ts = op.talent_system
    assert ts.bb("shield_value") is not None, "talent 2 should unlock at E2"
    e = _spawn(b, "enemy_1000_gopro_2", 3, 4)
    b.add_ep(e, 1, 990.0)                     # near burst threshold
    _land_attack(b, op, e)                    # EP attach -> burst
    db = [x for x in op.buffs if x.get("key") == "thumpy_t2_def"]
    assert db, [x.get("key") for x in op.buffs]
    assert db[-1]["layers"] == 1, db[-1]
    assert op.barrier > 0, "talent 2 should grant a barrier"
    shield = float(ts.bb("shield_value"))
    assert abs(op.barrier - shield) < 1e-6, op.barrier
    # second burst: DEF stack +2, barrier accumulates
    for x in [x for x in e.buffs if x.get("key") == "ep_burst_cd_1"]:
        e.buffs.remove(x)
    b.add_ep(e, 1, 990.0)
    _land_attack(b, op, e)
    db = [x for x in op.buffs if x.get("key") == "thumpy_t2_def"]
    assert db[-1]["layers"] == 2, db[-1]
    assert abs(op.barrier - shield * 2) < 1e-6, op.barrier


def test_barrier_absorbs_damage_before_hp():
    sim, b = _battle()
    op = _deploy_thumpy(b)
    b.add_barrier(op, 500.0)
    assert op.barrier == 500.0
    hp0 = op.hp
    b.apply_damage(op, 300.0, DamageType.TRUE, source=None)
    assert abs(op.hp - hp0) < 1e-9
    assert abs(op.barrier - 200.0) < 1e-6
    evs = b.events.snapshot_events()
    assert any(x["type"] == "barrier_hit" and
               abs(x["data"]["amount"] - 300.0) < 1e-6 for x in evs)
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"]["target"] == op.inst_id][-1]
    assert abs(dmg["data"]["barrierAbsorbed"] - 300.0) < 1e-6
    assert abs(dmg["data"]["amount"] - 0.0) < 1e-6
    # partial absorption then HP damage
    b.apply_damage(op, 150.0, DamageType.TRUE, source=None)
    assert abs(op.barrier - 50.0) < 1e-6
    assert abs(op.hp - hp0) < 1e-9
    b.apply_damage(op, 100.0, DamageType.TRUE, source=None)
    assert abs(op.barrier - 0.0) < 1e-6
    assert abs(op.hp - (hp0 - 50.0)) < 1e-6
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and x["data"]["target"] == op.inst_id][-1]
    assert abs(dmg["data"]["barrierAbsorbed"] - 50.0) < 1e-6
    assert abs(dmg["data"]["amount"] - 50.0) < 1e-6


if __name__ == "__main__":
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
    print("all thumpy talent tests passed" if not failed
          else f"{failed} failed")
    sys.exit(1 if failed else 0)
