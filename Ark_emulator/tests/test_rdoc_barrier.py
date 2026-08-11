"""Doctor (医生, char_4125_rdoc) talent 2 "交感神经激活" tests.

Covers overheal -> decaying shield conversion (cap = source ATK * 5000%,
1s grace then 0.1s decay by ceil(current*rate), E1 2% / E2 1% per 0.1s),
priority absorption before the generic barrier pool, and snapshot output.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType


def _battle(phase=2):
    squad = [{"charId": "char_4125_rdoc", "phase": phase, "level": 1},
             {"charId": "char_002_amiya", "phase": 2, "level": 1}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy_pair(b, phase=2):
    ok, doc_id = b.deploy("char_4125_rdoc", 3, 3)      # ground (3,3)
    assert ok, doc_id
    ok, ally_id = b.deploy("char_002_amiya", 2, 3)     # high ground (2,3)
    assert ok, ally_id
    doc = [o for o in b.operators if o.inst_id == doc_id][0]
    ally = [o for o in b.operators if o.inst_id == ally_id][0]
    assert doc.talent_system.rdoc_overheal_params() is not None
    return doc, ally


def test_rdoc_overheal_converts_to_shield():
    sim, b = _battle()
    doc, ally = _deploy_pair(b)
    ally.hp = ally.max_hp - 100.0
    hp0 = ally.hp
    b.apply_heal(ally, 250.0, source=doc)
    assert abs(ally.hp - (hp0 + 100.0)) < 1e-6
    assert abs(ally._rdoc_shield - 150.0) < 1e-6
    expect_cap = doc.attributes.get("atk") * 50.0
    assert abs(ally._rdoc_shield_cap - expect_cap) < 1e-6
    evs = b.events.snapshot_events()
    add = [x for x in evs if x["type"] == "rdoc_shield_added" and
           x["data"]["unit"] == ally.inst_id]
    assert add and abs(add[-1]["data"]["amount"] - 150.0) < 1e-6


def test_rdoc_shield_capped_at_atk_scale():
    sim, b = _battle()
    doc, ally = _deploy_pair(b)
    cap = doc.attributes.get("atk") * 50.0
    b.apply_heal(ally, cap + 999.0, source=doc)
    assert abs(ally._rdoc_shield - cap) < 1e-6
    before = ally._rdoc_shield
    b.apply_heal(ally, 500.0, source=doc)
    # game: once current >= trigger-time cap, further overheal adds nothing
    assert abs(ally._rdoc_shield - before) < 1e-6


def test_rdoc_decay_e2_after_1s_ceil():
    sim, b = _battle()
    doc, ally = _deploy_pair(b)
    b.apply_heal(ally, 151.0, source=doc)   # full HP ally -> 151 overheal
    assert abs(ally._rdoc_shield - 151.0) < 1e-6
    sim.run_ticks(30)
    assert abs(ally._rdoc_shield - 151.0) < 1e-6, "1s grace must hold"
    sim.run_ticks(1)
    # E2: 1% of 151 = 1.51 -> ceil = 2
    assert abs(ally._rdoc_shield - 149.0) < 1e-6, ally._rdoc_shield
    sim.run_ticks(3)
    assert abs(ally._rdoc_shield - 147.0) < 1e-6, ally._rdoc_shield
    sim.run_ticks(3)
    assert abs(ally._rdoc_shield - 145.0) < 1e-6, ally._rdoc_shield


def test_rdoc_decay_e1_rate():
    sim, b = _battle(phase=1)
    doc, ally = _deploy_pair(b, phase=1)
    params = doc.talent_system.rdoc_overheal_params()
    assert abs(params[0] - 0.02) < 1e-9, params
    b.apply_heal(ally, 100.0, source=doc)
    sim.run_ticks(30)
    assert abs(ally._rdoc_shield - 100.0) < 1e-6, "1s grace must hold"
    sim.run_ticks(1)
    # E1: 2% of 100 = 2 -> ceil 2
    assert abs(ally._rdoc_shield - 98.0) < 1e-6, ally._rdoc_shield


def test_rdoc_absorbs_before_generic_barrier():
    sim, b = _battle()
    doc, ally = _deploy_pair(b)
    ally.hp = ally.max_hp - 100.0
    b.apply_heal(ally, 200.0, source=doc)   # overheal 100 -> rdoc shield
    assert abs(ally._rdoc_shield - 100.0) < 1e-6
    b.add_barrier(ally, 100.0)
    hp0 = ally.hp
    b.apply_damage(ally, 150.0, DamageType.TRUE, source=None)
    assert abs(ally.hp - hp0) < 1e-9
    assert abs(ally._rdoc_shield - 0.0) < 1e-6
    assert abs(ally.barrier - 50.0) < 1e-6
    evs = b.events.snapshot_events()
    bh = [x for x in evs if x["type"] == "barrier_hit" and
          x["data"]["unit"] == ally.inst_id][-1]
    assert abs(bh["data"]["amount"] - 150.0) < 1e-6
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"]["target"] == ally.inst_id][-1]
    assert abs(dmg["data"]["barrierAbsorbed"] - 150.0) < 1e-6
    assert abs(dmg["data"]["amount"] - 0.0) < 1e-6
    b.apply_damage(ally, 100.0, DamageType.TRUE, source=None)
    assert abs(ally.barrier - 0.0) < 1e-6
    assert abs(ally.hp - (hp0 - 50.0)) < 1e-6


def test_rdoc_shield_in_snapshot():
    sim, b = _battle()
    doc, ally = _deploy_pair(b)
    b.apply_heal(ally, 80.0, source=doc)
    snap = sim.snapshot()
    deployed = {u["instId"]: u for u in snap["deployed"]}
    assert deployed[ally.inst_id]["rdocShield"] == 80.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    import traceback
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
