# -*- coding: utf-8 -*-
"""Instructor-family talent aura tests (杜宾 / 诗怀雅 / 鞭刃 / 苍苔).

The auras are re-evaluated every tick: 3-star field atk (Dobermann),
melee-in-8-cells atk (Swire), block-capacity-split melee buffs (Whislash)
and conditional ally/self def (Bryo'ta).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _auras(u):
    return [(x["key"], x.get("stat"), x.get("add"),
             round(x.get("mul") or 0.0, 4))
            for x in u.buffs
            if (x.get("key") or "").startswith("talent_aura:")]


def test_doberm_rarity3_field_atk_aura():
    sim, b = _battle()
    b.deploy("char_130_doberm", 3, 3, direction=1)    # 3-star instructor
    b.deploy("char_149_scave", 3, 4, direction=1)     # 3-star vanguard
    b.deploy("char_1045_svash2", 3, 5, direction=1)   # 5-star
    b.tick_once()
    doberm, scave, svash2 = b.operators
    assert _auras(doberm) == []
    scave_auras = _auras(scave)
    assert any(_s == "atk" and m == 0.1
               for k, _s, _a, m in scave_auras), scave_auras
    assert _auras(svash2) == []


def test_swire_melee_cell8_atk_aura():
    sim, b = _battle()
    b.deploy("char_308_swire", 3, 3, direction=1)     # instructor
    b.deploy("char_149_scave", 3, 4, direction=1)     # melee in 3x3
    b.deploy("char_002_amiya", 2, 4, direction=1)     # ranged in 3x3
    b.tick_once()
    swire, scave, amiya = b.operators
    assert _auras(swire) == []
    scave_auras = _auras(scave)
    assert any(_s == "atk" and m == 0.1
               for k, _s, _a, m in scave_auras), scave_auras
    assert _auras(amiya) == []


def test_whislash_block_capacity_split_aura():
    sim, b = _battle()
    b.deploy("char_265_sophia", 3, 3, direction=1)    # Whislash
    b.deploy("char_199_yak", 3, 4, direction=1)       # block 3 defender
    b.deploy("char_149_scave", 3, 5, direction=1)     # block 2 vanguard
    b.tick_once()
    _, yak, scave = b.operators
    yak_a = _auras(yak)
    scave_a = _auras(scave)
    assert any(_s == "attackSpeed" and a == 6.0
               for k, _s, a, _m in yak_a), yak_a
    assert any(_s == "def" and m == 0.12
               for k, _s, _a, m in yak_a), yak_a
    assert any(_s == "attackSpeed" and a == 3.0
               for k, _s, a, _m in scave_a), scave_a
    assert any(_s == "def" and m == 0.06
               for k, _s, _a, m in scave_a), scave_a


def test_bryota_ally_aura_switches_to_self_when_blocking():
    from ark_emulator.consts import EnemyState
    sim, b = _battle()
    b.deploy("char_4106_bryota", 3, 3, direction=1)   # Bryo'ta
    b.deploy("char_149_scave", 3, 4, direction=1)     # melee ally in 3x3
    b.tick_once()
    bryota, scave = b.operators
    scave_a = _auras(scave)
    assert any(_s == "def" and m == 0.12
               for k, _s, _a, m in scave_a), scave_a
    assert _auras(bryota) == []
    # an enemy on Bryo'ta's tile makes her block -> ally buff drops, her
    # own def buff turns on
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 99999, "atk": 0, "def": 0},
        "row": 3, "col": 3})
    b.enemies[-1].state = EnemyState.MOVE
    for _ in range(40):
        b.tick_once()
        if bryota.blocked_enemies:
            break
    assert bryota.blocked_enemies
    assert _auras(scave) == [], _auras(scave)
    bryota_a = _auras(bryota)
    assert any(_s == "def" and m == 0.12
               for k, _s, _a, m in bryota_a), bryota_a
