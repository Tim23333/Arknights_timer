# -*- coding: utf-8 -*-
"""Batch boss-behaviour verification: representative leader enemies with
skill data must resolve their skill controllers and cast at least one
skill within a 60s window against an in-range operator.

Covers the generic enemy-skill pipeline (parse -> cooldown/priority ->
target selection -> cast) for bosses with very different skill sets:
Talulah (4), Patriot (phase skills), W (C4), Faust (CriticalHit +
SummonBallis), Mudrock (shield + occupy), Frost Star Winter (5),
"Evolution's Essence" (11), Sui phase (7), Kirsten (5), Mandragora (6).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState
from ark_emulator.custom_levels import build_level


def _empty_level():
    """A wave-less custom level so the scan is not disturbed by the
    story level's own spawns / early finish."""
    return build_level(rows=6, cols=10, route_row=3, enemies=[])


def _cast_once(key, boss_col=5, secs=60, atk=50.0, fill_sp=True):
    """Spawn the boss near an operator and return (skills, first_cast)."""
    sim = Simulator(level_id="custom",
                    custom_level=_empty_level())
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_127_estell", 3, 4)
    e = b.spawn_enemy(key, 0, overrides={
        "attributes": {"atk": atk}, "row": 3, "col": boss_col})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    if sc is None:
        return [], None
    n_skills = len(sc.skills)
    if fill_sp and e.sp_max > 0:
        e.sp = e.sp_max          # skills are SP-gated; fill for the scan
    b.events.log = []
    first = None
    for _ in range(int(secs * 30)):
        b.tick_once()
        if first is None:
            for ev in b.events.log:
                if ev.type == "skill_cast" and \
                        ev.data.get("unit") == e.inst_id:
                    first = (b.tick, ev.data.get("skill"))
                    break
    return n_skills, first


def test_talulah_casts_all_phases():
    n, first = _cast_once("enemy_1503_talula")
    assert n == 4
    assert first is not None and first[1] in (
        "DragonFire", "DanceFire", "DragonFire[Half]", "DanceFire[Half]")


def test_patriot_casts_spear_when_in_range():
    # melee boss: operator must be adjacent (col 5 -> dist 1)
    n, first = _cast_once("enemy_1506_patrt", boss_col=5)
    assert n == 3
    assert first is not None, "patriot should cast throwspear[Rage]"
    assert first[1] == "throwspear[Rage]"


def test_w_casts_c4():
    n, first = _cast_once("enemy_1504_cqbw")
    assert n == 1 and first is not None and first[1] == "C4"


def test_faust_critical_hit_and_ballista():
    n, first = _cast_once("enemy_1508_faust")
    assert n == 2 and first is not None
    assert first[1] in ("CriticalHit", "SummonBallis")


def test_mudrock_shield_and_occupy():
    n, first = _cast_once("enemy_1511_mdrock")
    assert n == 2 and first is not None
    assert first[1] in ("RefreshShield", "occupy")


def test_frost_star_winter_five_skills():
    n, first = _cast_once("enemy_1510_frstar2")
    assert n == 5 and first is not None


def test_evolution_essence_11_skills():
    n, first = _cast_once("enemy_1519_bgball")
    assert n == 11 and first is not None


def test_sui_phase_all_seven_cast():
    n, first = _cast_once("enemy_1526_sfsui")
    assert n == 7 and first is not None


def test_kirsten_star_skills():
    n, first = _cast_once("enemy_1543_cstlrs")
    assert n == 5 and first is not None
    assert first[1] in ("BecomeStar", "BecomeStar2", "Reborning")


def test_mandragora_reborn_and_selfstun():
    n, first = _cast_once("enemy_1523_mandra")
    assert n == 6 and first is not None
    assert first[1] in ("Reborn", "SelfStun")


def test_shared_prefab_buffs_scoped_to_owner():
    """Same-named prefabs shared by several enemies (e.g. "Invincible" is
    used by xbmoth/xbmothb/xbpffr/xbfrog and the extracted catalog merges
    telex/faust/ymmons components under the same key) must only expose the
    casting enemy's own buffs."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    e = b.spawn_enemy("enemy_7021_xbmoth", 0, overrides={"row": 3, "col": 5})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    inv = next(s for s in sc.skills if s.prefab_key == "Invincible")
    keys = [bd.get("buffKey") for bd in inv.prefab_buffs]
    assert keys == ["enemy_xbmoth_s[mode]"], keys
    # none of the other owners' invincible buffs may leak in
    leaked = [k for k in keys if any(
        tok in k for tok in ("telex", "faust", "ymmons", "cshost",
                             "flwitch", "dycant", "embald", "shorbb"))]
    assert not leaked, leaked


def test_melee_range_skills_reach_adjacent():
    """Skills whose bb range_radius is a sub-1.0 EFFECT radius (0.8 melee)
    must still select the adjacent operator through the enemy's attack
    range (1.5 melee reach), not fail target selection."""
    n, first = _cast_once("enemy_7014_dva", secs=60)
    assert n == 1 and first is not None and first[1] == "PowerAttack"


def test_start_battle_fires_after_initial_cd():
    n, first = _cast_once("enemy_15071_dqyrzf", secs=95)
    assert n == 1 and first is not None and first[1] == "StartBattle"


def test_elbert_blink():
    n, first = _cast_once("enemy_2144_shwks2", secs=95)
    assert n == 1 and first is not None and first[1] == "Blink"


def test_round_stone_durance():
    n, first = _cast_once("enemy_6005_llstone", secs=95)
    assert n == 2 and first is not None
    assert first[1] in ("Durance", "CardDurance")


def test_sp_gate_blocks_until_ready():
    """Skills are SP-gated: Bombard (SP 50) must not cast while SP is
    low and must cast once the bar is full."""
    sim = Simulator(level_id="custom", custom_level=_empty_level())
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_127_estell", 3, 4)
    e = b.spawn_enemy("enemy_2119_dyshhj", 0, overrides={
        "attributes": {"atk": 30.0}, "row": 3, "col": 5})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    s = next(x for x in sc.skills if x.prefab_key == "Bombard")
    assert s.sp_cost == 50
    s.cooldown_remaining = 0.0              # cd gate open
    assert sc._skill_available(s) is False  # SP still too low (20/50)
    e.sp = e.sp_max
    assert sc._skill_available(s) is True
