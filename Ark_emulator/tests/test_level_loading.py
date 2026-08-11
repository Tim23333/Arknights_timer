# -*- coding: utf-8 -*-
"""Level-loading smoke: representative levels across prefixes load and
advance 30 ticks without raising, and wave-instance enemy keys
(enemy_x#N) resolve to the base database key."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator

LEVELS = [
    "level_main_01-01", "level_main_05-07", "level_hard_06-03",
    "level_act11d0_ex01", "level_act22side_01", "level_camp_r_01",
    "level_memory_glacus_1", "level_rogue1_1-5", "level_rogue5_d-2",
    "level_recalrune_02-03", "level_a001_ex04", "level_sandbox1_78",
    "level_lt11_03", "level_main_14-09", "level_act3d0_ex05",
    "level_script_table91d938",   # metadata-only level: empty playable map
]


def test_representative_levels_load():
    for lid in LEVELS:
        sim = Simulator(level_id=lid)
        sim.run_ticks(30)
        b = sim.battle
        assert b.life_point >= 0, lid
        assert b.map is not None, lid


def test_wave_instance_enemy_key_resolves():
    sim = Simulator(level_id="level_main_01-01")
    assert sim.store.resolve_enemy_key("enemy_1056_ganwar#1") == \
        "enemy_1056_ganwar"
    assert sim.store.resolve_enemy_key("enemy_1000_gopro") == \
        "enemy_1000_gopro"
    # the previously failing rogue level now loads
    sim2 = Simulator(level_id="level_rogue1_1-5")
    sim2.run_ticks(60)
    assert sim2.battle.life_point >= 0


def test_official_gamedata_levels_load():
    """Official gamedata levels (converted from Kengxxiao/ArknightsGameData
    zh_CN/gamedata/levels) load and simulate - the client does not ship
    these level assets."""
    for lid in ("level_act44side_01", "level_act10d5_02", "level_act49side_01",
                "level_act2break_sp10", "level_rogue2_b-7",
                "level_sandbox2_01"):
        sim = Simulator(level_id=lid)
        sim.run_ticks(30)
        b = sim.battle
        assert b.life_point >= 0, lid
        assert b.map.rows > 0 and b.map.cols > 0, lid


def test_official_level_predefines_spawn():
    """Official JSON levels carry the FULL predefines (the binary parser
    only stored counts): predefined NPC allies and traps must spawn."""
    sim = Simulator(level_id="level_act10mini_09")
    b = sim.battle
    ids = {(o.char_id, o.row, o.col, o.direction) for o in b.operators}
    assert ("char_220_grani", 5, 7, 1) in ids, ids
    assert ("char_385_finlpp", 5, 5, 2) in ids, ids

    sim2 = Simulator(level_id="level_act10d5_02")
    b2 = sim2.battle
    traps = [(t.token_id, t.row, t.col) for t in b2.tokens]
    assert ("trap_005_sensor", 3, 2) in traps, traps


def test_official_level_hidden_predefines_activate():
    """Hidden predefined NPCs stay pending until the wave activates them
    (ACTIVATE_PREDEFINED) - 灰烬 spawns during the battle."""
    sim = Simulator(level_id="level_act17d0_03")
    b = sim.battle
    assert not any(o.char_id == "char_456_ash" for o in b.operators), \
        "hidden predefined ally must not spawn at battle start"
    for _ in range(600):
        b.tick_once()
        if any(o.char_id == "char_456_ash" for o in b.operators):
            break
    assert any(o.char_id == "char_456_ash" for o in b.operators), \
        "ash must be activated by the wave schedule"
