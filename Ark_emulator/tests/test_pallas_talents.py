"""Pallas (帕拉斯, char_485_pallas) talent tests.

Covers talent 1 英雄的诞生 ([米诺斯] operators above 80% HP get a
peak-performance ATK% aura, same-name takes max, includes Pallas herself)
and talent 2 女神的振奋 (each attack on an enemy heals self + the friendly
operator in the tile directly in front for a flat 40/45 HP).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle(phase=2):
    squad = [{"charId": "char_485_pallas", "phase": phase, "level": 1},
             {"charId": "char_333_sidero", "phase": 2, "level": 1},
             {"charId": "char_002_amiya", "phase": 2, "level": 1}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy(b):
    ok, pid = b.deploy("char_485_pallas", 3, 3)      # ground, facing right
    assert ok, pid
    ok, sid = b.deploy("char_333_sidero", 3, 2)      # minos ally, in front-left
    assert ok, sid
    ok, aid = b.deploy("char_002_amiya", 2, 3)       # non-minos ranged ally
    assert ok, aid
    by_id = {o.inst_id: o for o in b.operators}
    return by_id[pid], by_id[sid], by_id[aid]


def _aura_key(unit):
    return "talent_aura:peak_performance:%d" % unit.inst_id


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_pallas_minos_aura_and_self():
    sim, b = _battle()
    pallas, sidero, amiya = _deploy(b)
    sim.run_ticks(1)
    for unit, present in ((pallas, True), (sidero, True), (amiya, False)):
        found = [x for x in unit.buffs if x.get("key") == _aura_key(unit)]
        assert bool(found) == present, (unit.char_id, found)
        if found:
            assert abs(found[-1].get("mul", 0.0) - 0.25) < 1e-9
            assert found[-1].get("stat") == "atk"


def test_pallas_aura_hp_condition():
    sim, b = _battle()
    pallas, sidero, amiya = _deploy(b)
    sim.run_ticks(1)
    assert [x for x in sidero.buffs if x.get("key") == _aura_key(sidero)]
    sidero.hp = sidero.max_hp * 0.7
    sim.run_ticks(1)
    assert not [x for x in sidero.buffs
                if x.get("key") == _aura_key(sidero)], "buff must drop <=80%"
    sidero.hp = sidero.max_hp
    sim.run_ticks(1)
    found = [x for x in sidero.buffs if x.get("key") == _aura_key(sidero)]
    assert found, "buff must return above 80%"
    assert abs(found[-1].get("mul", 0.0) - 0.25) < 1e-9


def test_pallas_aura_e1_value():
    sim, b = _battle(phase=1)
    pallas, sidero, amiya = _deploy(b)
    sim.run_ticks(1)
    found = [x for x in sidero.buffs if x.get("key") == _aura_key(sidero)]
    assert found, "E1 aura should apply"
    assert abs(found[-1].get("mul", 0.0) - 0.15) < 1e-9


def test_pallas_attack_heal_self_and_front():
    sim, b = _battle()
    pallas, sidero, amiya = _deploy(b)
    # ally in the tile directly in front (3,4): move sidero there
    b.operators = [o for o in b.operators if o.inst_id != sidero.inst_id]
    sidero.row, sidero.col = 3, 4
    sidero.deploy_tick = b.tick
    b.operators.append(sidero)
    hp_p0 = pallas.hp = pallas.max_hp - 100.0
    hp_s0 = sidero.hp = sidero.max_hp - 200.0
    e = b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 5})
    e.state = EnemyState.COMBAT
    _land_attack(b, pallas, e)
    assert abs(pallas.hp - (hp_p0 + 40.0)) < 1e-6, pallas.hp
    assert abs(sidero.hp - (hp_s0 + 40.0)) < 1e-6, sidero.hp
    # non-front ally is not healed
    assert abs(amiya.hp - amiya.max_hp) < 1e-9


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
