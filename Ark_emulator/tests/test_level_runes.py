# -*- coding: utf-8 -*-
"""Level runes (stage tags / crisis contracts) support: the stage bundle
carries rune dicts (gbuff_lifepoint / ebuff_attribute / cbuff_char_cost /
global_forbid_location / cbuff_max_cost / global_initial_cost_add /
char_attribute_mul ...) which must be applied at battle init, spawn and
deploy time."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _battle(level_id):
    sim = Simulator(level_id=level_id, rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy_anywhere(b, char_id="char_149_scave"):
    for r in range(b.map.rows):
        for c in range(b.map.cols):
            if b.map.buildable(r, c, 1) is not False:
                ok, res = b.deploy(char_id, r, c)
                if ok:
                    return b.operators[-1]
    return None


def test_lifepoint_and_enemy_attribute_runes():
    # level_a001_ex04: gbuff_lifepoint +1 (base 3), ebuff_attribute
    # atk x1.1 / def x1.0 / max_hp x1.0
    sim, b = _battle("level_a001_ex04")
    assert b.max_life_point == 4 and b.life_point == 4
    assert abs(b._rune_enemy_mul.get("atk", 1.0) - 1.1) < 1e-9
    level = b._enemy_db_level("enemy_1000_gopro")
    merged = b.store.build_merged_enemy("enemy_1000_gopro", level)
    base_atk = (merged["data"].get("attributes") or {}).get("atk")
    e = b.spawn_enemy("enemy_1000_gopro", 0)
    assert abs(e.attributes.get("atk") - base_atk * 1.1) < 0.01, (
        e.attributes.get("atk"), base_atk)


def test_operator_cost_rune():
    # level_a001_ex04: cbuff_char_cost scale x3 (fen base cost 12)
    sim, b = _battle("level_a001_ex04")
    op = _deploy_anywhere(b)
    assert op is not None
    assert abs(op.cost - 36.0) < 1e-6, op.cost


def test_forbidden_locations():
    # level_act11d0_ex01: global_forbid_location (4,5)|(4,6)|(3,5)|(3,6)
    sim, b = _battle("level_act11d0_ex01")
    assert (3, 5) in b._rune_forbidden
    assert (4, 6) in b._rune_forbidden
    ok, res = b.deploy("char_149_scave", 3, 5)
    assert ok is False and res == "forbidden_location", (ok, res)


def test_initial_cost_and_max_cost_runes():
    # level_act11d0_sub-1-1: global_initial_cost_add -10 (options 15 -> 5)
    sim = Simulator(level_id="level_act11d0_sub-1-1", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    assert abs(b.initial_cost - 5.0) < 1e-9, b.initial_cost
    assert abs(b.cost - 5.0) < 1e-9, b.cost
    # level_hard_12-01: cbuff_max_cost 20
    sim2 = Simulator(level_id="level_hard_12-01", rune_difficulty=2)
    sim2.run_ticks(10)
    assert abs(sim2.battle.max_cost - 20.0) < 1e-9, sim2.battle.max_cost


def test_operator_attribute_rune():
    # level_act11d0_ex04: char_attribute_mul atk x0.6
    sim, b = _battle("level_act11d0_ex04")
    op = _deploy_anywhere(b)
    assert op is not None
    assert abs(b._rune_char_mul.get("atk", 1.0) - 0.6) < 1e-9
    # the deployed atk must equal the rune-free same-config deploy x 0.6
    _, b0 = _battle("level_main_01-01")
    op0 = _deploy_anywhere(b0)
    assert op0 is not None
    ratio = op.attributes.get("atk") / op0.attributes.get("atk")
    assert abs(ratio - 0.6) < 0.01, (op.attributes.get("atk"),
                                      op0.attributes.get("atk"))



def test_character_limit_rune():
    # FOUR_STAR main_01-01: gbuff_placable_char_num -4 (limit 8 -> 4)
    sim = Simulator("level_main_01-01", rune_difficulty=2)
    sim.run_ticks(10)
    assert sim.battle.character_limit == 4, sim.battle.character_limit


def test_enemy_attack_range_rune():
    # level_act3d0_ex01: ebuff_attack_radius range_scale 2.0; gopro has no
    # rangeRadius so the melee default 1.5 is scaled to 3.0
    sim = Simulator("level_act3d0_ex01", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    e = b.spawn_enemy("enemy_1000_gopro", 0)
    assert abs(e.attributes.get("rangeRadius") - 3.0) < 1e-9, \
        e.attributes.get("rangeRadius")


def test_enemy_weight_rune():
    # level_main_02-08: ebuff_weight +2
    sim = Simulator("level_main_02-08", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    e = b.spawn_enemy("enemy_1000_gopro", 0)
    assert abs(float(e.attributes.get("massLevel") or 0.0) - 2.0) < 1e-9


def test_enemy_skill_blackboard_runes():
    # level_act11d0_ex05: enemy_skill_blackb_mul sp x2 on ltsmer_2 charge
    sim = Simulator("level_act11d0_ex05", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    e = b.spawn_enemy("enemy_1088_ltsmer_2", 0)
    s = next(x for x in e.skill_controller.skills
             if x.prefab_key == "charge")
    assert abs(s.blackboard.get("sp", 0.0) - (-4.0)) < 1e-9, s.blackboard
    # level_act26side_ex08: enemy_skill_blackb_add boom_value_ally +800
    sim2 = Simulator("level_act26side_ex08", rune_difficulty=2)
    sim2.run_ticks(10)
    b2 = sim2.battle
    e2 = b2.spawn_enemy("enemy_1343_ltrock_2", 0)
    s2 = next(x for x in e2.skill_controller.skills
              if x.prefab_key == "Boom")
    assert abs(s2.blackboard.get("boom_value_ally", 0.0) - 1600.0) < 1e-9, \
        s2.blackboard
    assert abs(s2.blackboard.get("blockee_value", 0.0) - 1000.0) < 1e-9



def test_enemy_talent_blackboard_rune():
    # level_act12side_ex05: enemy_talent_blackb_mul Boom.atk_scale x2
    sim = Simulator("level_act12side_ex05", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    e = b.spawn_enemy("enemy_15075_dqzklz", 0)
    s = next(x for x in e.skill_controller.skills
             if x.prefab_key == "Boom")
    assert abs(s.blackboard.get("atk_scale", 0.0) - 2.0) < 1e-9, \
        s.blackboard



def _find_tile(b, tile_key):
    for r in range(b.map.rows):
        for c in range(b.map.cols):
            t = b.map.tile(r, c)
            if t and t.tile_key == tile_key:
                return (r, c)
    return None


def test_map_tile_blackboard_assign():
    # level_act22side_01 (ALL): map_tile_blackb_assign overrides
    # tile_reed/reedf/reedw with ignite/extinct/cooldown/damage/ep_damage
    sim = Simulator("level_act22side_01", rune_difficulty=15)
    sim.run_ticks(10)
    b = sim.battle
    pos = _find_tile(b, "tile_reed") or _find_tile(b, "tile_reedf") or \
        _find_tile(b, "tile_reedw")
    assert pos is not None, "level must contain a reed tile"
    bb = b.tile_blackboard(pos[0], pos[1])
    assert abs(bb.get("damage", 0.0) - 40.0) < 1e-9, bb
    assert abs(bb.get("ignite_duration", 0.0) - 15.0) < 1e-9, bb
    assert abs(bb.get("extinct_duration", 0.0) - 20.0) < 1e-9, bb


def test_map_tile_blackboard_add_by_location():
    # level_act22side_ex04: map_tile_blackb_add location (1,10) mode 1.0
    sim = Simulator("level_act22side_ex04", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    bb = b.tile_blackboard(1, 10)
    assert abs(bb.get("mode", 0.0) - 1.0) < 1e-9, bb
    other = b.tile_blackboard(1, 9)
    assert other.get("mode") is None, other


def test_map_tile_blackboard_mul():
    # level_act16d5_ex08: map_tile_blackb_mul tile_yinyang_road
    # buff_yinyang[same].atk_scale 0.5
    sim = Simulator("level_act16d5_ex08", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    pos = _find_tile(b, "tile_yinyang_road")
    assert pos is not None
    bb = b.tile_blackboard(pos[0], pos[1])
    assert abs(bb.get("buff_yinyang[same].atk_scale", 0.0) - 0.5) < 1e-9, bb



def test_predefines_enable_rune():
    # level_act11d0_ex06 (FOUR_STAR): level_predefines_enable activates
    # the hidden trap_014_tower instances
    sim = Simulator("level_act11d0_ex06", rune_difficulty=2)
    sim.run_ticks(10)
    b = sim.battle
    towers = [t for t in b.tokens if t.token_id == "trap_014_tower"]
    assert len(towers) == 8, len(towers)
    assert not b._predefined_pending
    assert towers[0].alias == "trap_014_tower#1"


def test_random_predefine_tokens_on_tile():
    # level_rogue5_1-1 (ALL): level_predefine_tokens_random_spawn_on_tile
    # places trap_225_dysbox on every tile_dygmny_1 cell
    sim = Simulator("level_rogue5_1-1", rune_difficulty=15)
    sim.run_ticks(10)
    b = sim.battle
    cells = [(r, c) for r in range(b.map.rows) for c in range(b.map.cols)
             if b.map.tile(r, c) and
             b.map.tile(r, c).tile_key == "tile_dygmny_1"]
    assert cells, "level must contain dygmny_1 cells"
    for r, c in cells:
        cnt = sum(1 for t in b.tokens
                  if t.token_id == "trap_225_dysbox" and
                  (t.row, t.col) == (r, c))
        assert cnt == 1, ((r, c), cnt)



def test_env_system_runes_parsed_and_exposed():
    # env_gbuff_new: level_act17side_tr01 heal_scale 1.5
    sim = Simulator("level_act17side_tr01", rune_difficulty=1)
    sim.run_ticks(10)
    b = sim.battle
    gb = [x for x in b.env_systems if x["kind"] == "gbuff"]
    assert gb and gb[0]["key"] == "heal_scale", gb
    assert abs(gb[0]["attributes"].get("heal_scale", 0.0) - 1.5) < 1e-9
    snap = sim.snapshot()
    assert any(x.get("key") == "heal_scale" for x in snap.get(
        "envSystems", [])), snap.get("envSystems")
    # env_system_new: level_act25side_sp01 env_006_act25side_extra
    sim2 = Simulator("level_act25side_sp01", rune_difficulty=15)
    sim2.run_ticks(10)
    sys2 = [x for x in sim2.battle.env_systems if x["kind"] == "system"]
    assert sys2 and sys2[0]["key"] == "env_006_act25side_extra", sys2
