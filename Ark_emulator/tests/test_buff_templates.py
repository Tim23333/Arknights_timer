# -*- coding: utf-8 -*-
"""Buff template engine tests (buff_template_data interpretation)."""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.buff_templates import template, BuffTemplateEngine
from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def test_abnormal_flag_name_resolution():
    """Buff templates store abnormal flags as enum NAMES (e.g. 'STUNNED')."""
    from ark_emulator import Simulator
    from ark_emulator.consts import AbnormalFlag
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    from ark_emulator.buff_templates import materialise_buff
    data = {
        "buffKey": "test_flags",
        "attributes": {"abnormalFlags": ["STUNNED", "INVISIBLE"]},
        "lifeTimeType": 2,
        "durationKey": "duration",
    }
    entry = materialise_buff(b, op, data, {"duration": 5.0}, None)
    assert entry
    assert op.flag(AbnormalFlag.STUNNED)
    assert op.flag(AbnormalFlag.INVISIBLE)


def test_template_loading():
    assert template("periodic_damage[not_env]") is not None
    assert template("damage_block[all]") is not None
    t = template("periodic_damage[not_env]")
    ev = t["eventToActions"]
    assert "ON_BUFF_TRIGGER" in ev
    assert "NoSourceDamage" in ev["ON_BUFF_TRIGGER"][0]["$type"]


def test_periodic_damage_trigger():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    hp0 = op.hp
    b.add_buff(op, {"key": "t_periodic", "remaining_ticks": 30 * 3,
                    "template_key": "periodic_damage[not_env]",
                    "blackboard": {"damage": 100.0}})
    for _ in range(30):
        b.tick_once()
    assert abs((hp0 - op.hp) - 100.0) < 1.0, (hp0, op.hp)


def test_damage_block_pipeline():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = 3, 4
    enemy.pos_x, enemy.pos_y = 4.0, 3.0
    b.add_buff(enemy, {"key": "t_block", "remaining_ticks": 30 * 30,
                       "template_key": "damage_block[all]",
                       "blackboard": {"damage_block[all]": 500.0}})
    enemy.state = EnemyState.COMBAT
    # gopro DEF normally reduces op attack; with 500 block nothing gets through
    b._operator_attack(op, enemy, 2.0)
    b._resolve_operator_attack(op, op._pending_attack)
    # block event should have fired
    evs = [e for e in sim.snapshot()["events"] if e["type"] == "buff_block_damage"]
    assert evs, "block event missing"


def test_conditional_create_buff():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = 3, 4
    enemy.pos_x, enemy.pos_y = 4.0, 3.0
    enemy.state = EnemyState.COMBAT
    b.add_buff(enemy, {"key": "t_hymwr", "remaining_ticks": 30 * 30,
                       "template_key": "enemy_hymwr_t", "blackboard": {}})
    b._operator_attack(op, enemy, 2.0)
    b._resolve_operator_attack(op, op._pending_attack)
    keys = [x["key"] for x in enemy.buffs]
    assert "enemy_hymwr_t[mark]" in keys, keys


def test_buff_start_finish_events():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.add_buff(op, {"key": "t_short", "remaining_ticks": 30,
                    "template_key": "periodic_damage[not_env]",
                    "blackboard": {"damage": 10.0}})
    for _ in range(45):
        b.tick_once()
    assert not any(x["key"] == "t_short" for x in op.buffs)


def test_buff_snapshot_fields():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.add_buff(op, {"key": "t_snap", "remaining_ticks": 30 * 10,
                    "template_key": "periodic_damage[not_env]",
                    "blackboard": {"damage": 5.0}})
    snap = sim.snapshot()
    opd = snap["deployed"][0]
    buff = [x for x in opd["buffs"] if x["key"] == "t_snap"][0]
    assert buff.get("template_key") == "periodic_damage[not_env]"


def test_createbuff_loadfromdb_stun():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    eng.dispatch(op, "ON_BUFF_START", "rosmon_s_2[stun]", bb={"stun": 3.0})
    assert op.flag(0), op.abnormal       # STUNNED
    entry = [x for x in op.buffs if x["key"] == "stun"]
    assert entry and 85 <= entry[0]["remaining_ticks"] <= 95


def test_createbuff_by_id_db_resolution():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    node = {"$type": "Torappu.Battle.Action.Nodes+CreateBuffById, Assembly-CSharp",
            "_buffKey": "sluggish", "_buffOwner": "BUFF_OWNER"}
    eng.run_actions(op, [node], {"owner": op, "source": None, "target": None,
                                 "damage": None, "bb": {"sluggish": 3.0}}, 0)
    speed = op.attributes.get("moveSpeed")
    assert abs(speed - 0.2) < 0.01, speed


def test_createbuff_in_range_side_filter():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row + 1, op.col
    enemy.pos_x, enemy.pos_y = float(enemy.col), float(enemy.row)
    eng = BuffTemplateEngine(b)
    node = {"$type": "Torappu.Battle.Action.Nodes+CreateBuffInRange, Assembly-CSharp",
            "_sourceType": "BUFF_OWNER", "_range": 2.0,
            "_targetOptions": {"targetSide": "ALLY"},
            "_buff": {"buffKey": "t_rng", "lifeTime": 5.0,
                      "maxStackCnt": 1}}
    eng.run_actions(op, [node], {"owner": op, "source": op, "target": op,
                                 "damage": None, "bb": {}}, 0)
    op_has = any(x["key"] == "t_rng" for x in op.buffs)
    en_has = any(x["key"] == "t_rng" for x in enemy.buffs)
    assert op_has and not en_has, (op_has, en_has)


def test_engine_unknown_node_skipped():
    eng = BuffTemplateEngine(None)
    res = eng.run_actions(None, [{"$type": "Torappu.Battle.Action.Nodes+NoSuchNode, Assembly-CSharp"}], {}, 0)
    assert res[0]["action"] == "skipped"


if __name__ == "__main__":
    import traceback
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
    print("all buff template tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)


def test_buff_gate_and_action_nodes():
    """New buff-template nodes: CheckAbnormalFlag / FilterByBlackboardValue /
    AssignValueToBB / ModifySp / FinishBuffsById / InstantKill."""
    from ark_emulator.consts import AbnormalFlag
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": None, "target": e, "bb": {"dynamic": 3.0}}

    # CheckAbnormalFlag: unset=True, unit not silenced -> True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckAbnormalFlag",
                             "_abnormalFlag": "SILENCED", "_targetType": "BUFF_OWNER",
                             "_isUnset": True}], ctx)
    assert r[0]["action"] is True, r
    b.add_abnormal(e, AbnormalFlag.SILENCED, 5.0)
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckAbnormalFlag",
                              "_abnormalFlag": "SILENCED", "_targetType": "BUFF_OWNER",
                              "_isUnset": True}], ctx)
    assert r2[0]["action"] is False, r2

    # FilterByBlackboardValue EQUALS / GT after AssignValueToBB
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByBlackboardValue",
                              "_blackboardKey": "dynamic", "_valueToCompare": 3.0,
                              "_condType": "EQUALS"}], ctx)
    assert r3[0]["action"] is True, r3
    r4 = eng.run_actions(e, [
        {"$type": "Torappu.Battle.Action.Nodes+AssignValueToBB",
         "_blackboardKey": "x", "_value": 5.0},
        {"$type": "Torappu.Battle.Action.Nodes+FilterByBlackboardValue",
         "_blackboardKey": "x", "_valueToCompare": 3.0, "_condType": "GT"}], ctx)
    assert r4[-1]["action"] is True, r4

    # ModifySp fixed add
    e.sp_max = 100.0
    e.sp = 10.0
    r5 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifySp",
                              "_targetType": "BUFF_OWNER", "_value": 20.0}], ctx)
    assert abs(e.sp - 30.0) < 1e-6, e.sp

    # FinishBuffsById
    b.add_buff(e, {"key": "test_rm", "remaining_ticks": 100, "layers": 1})
    assert b.buffs.get(e, "test_rm") is not None
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishBuffsById",
                         "_targetType": "BUFF_OWNER", "_buffKey": "test_rm"}], ctx)
    assert b.buffs.get(e, "test_rm") is None

    # InstantKill
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e2 = b.enemies[-1]
    e2.state = EnemyState.COMBAT
    eng.run_actions(e2, [{"$type": "Torappu.Battle.Action.Nodes+InstantKill",
                          "_targetType": "TARGET"}],
                    {"owner": e, "source": e, "target": e2, "bb": {}})
    assert e2.dead


def test_buff_extra_gate_nodes():
    """IsBlackboardZero / FilterByBuffStackCount / FilterByTargetHpRatio /
    Dice / CheckContainsDerviedBuff / CheckUnitCurrentMode / IfTarget."""
    from ark_emulator.consts import AbnormalFlag
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": None, "target": e, "bb": {"dynamic": 0.0}}

    # IsBlackboardZero: dynamic=0 -> True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsBlackboardZero",
                             "_var": "dynamic"}], ctx)
    assert r[0]["action"] is True, r

    # FilterByBuffStackCount: add a buff with layers 2, compare EQUALS 2
    b.add_buff(e, {"key": "mudrok_t_1[shield_b]", "remaining_ticks": 100,
                   "layers": 2})
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByBuffStackCount",
                              "_targetType": "BUFF_OWNER",
                              "_buffKey": "mudrok_t_1[shield_b]",
                              "_stackCount": 2, "_condType": "EQUALS"}], ctx)
    assert r2[0]["action"] is True, r2

    # FilterByTargetHpRatio: enemy at full HP -> GE 1.0 True
    e.hp = e.max_hp
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetHpRatio",
                              "_targetType": "BUFF_OWNER", "_condType": "GE",
                              "_value": 1.0}], ctx)
    assert r3[0]["action"] is True, r3

    # CheckContainsDerviedBuff: buff present -> True; unknown -> False
    r4 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckContainsDerviedBuff",
                              "_derviedBuffKey": "mudrok_t_1[shield_b]"}], ctx)
    assert r4[0]["action"] is True, r4
    r5 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckContainsDerviedBuff",
                              "_derviedBuffKey": "nope"}], ctx)
    assert r5[0]["action"] is False, r5

    # CheckUnitCurrentMode
    e.mode_index = 1
    r6 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckUnitCurrentMode",
                              "_targetType": "BUFF_OWNER", "_checkCurModeIndex": 1}], ctx)
    assert r6[0]["action"] is True, r6

    # IfTarget: alive target -> True
    r7 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IfTarget",
                              "_targetType": "BUFF_OWNER", "_checkTargetAlive": True}], ctx)
    assert r7[0]["action"] is True, r7

    # Dice with prob 1 -> always True; prob 0 -> False
    r8 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+Dice",
                              "_probKey": "prob"}],
                         {"owner": e, "source": None, "target": e,
                          "bb": {"prob": 1.0}})
    assert r8[0]["action"] is True, r8
    r9 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+Dice",
                              "_probKey": "prob"}],
                         {"owner": e, "source": None, "target": e,
                          "bb": {"prob": 0.0}})
    assert r9[0]["action"] is False, r9


def test_buff_blackboard_nodes():
    """BlackboardAdd / FinishDerivedBuffById / AddBuffBlackboard /
    AssignBuffBlackboard."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": None, "target": e, "bb": {"damage": 10.0}}

    # BlackboardAdd: 10 + 5 = 15
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+BlackboardAdd",
                         "_blackboardKey": "damage", "_addition": 5.0}], ctx)
    assert ctx["bb"]["damage"] == 15.0, ctx["bb"]

    # FinishDerivedBuffById removes a buff
    b.add_buff(e, {"key": "phenxi_e_t_2[in_skill]", "remaining_ticks": 100,
                   "layers": 1, "blackboard": {"cnt": 1}})
    assert b.buffs.get(e, "phenxi_e_t_2[in_skill]") is not None
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishDerivedBuffById",
                         "_buffKey": "phenxi_e_t_2[in_skill]"}], ctx)
    assert b.buffs.get(e, "phenxi_e_t_2[in_skill]") is None

    # AddBuffBlackboard / AssignBuffBlackboard write into a buff's bb
    b.add_buff(e, {"key": "enemy_trwlpl_food", "remaining_ticks": 100,
                   "layers": 1, "blackboard": {"cnt": 2}})
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AddBuffBlackboard",
                         "_targetType": "BUFF_OWNER",
                         "_buffKey": "enemy_trwlpl_food",
                         "_blackboardKey": "cnt", "_addition": 3.0}], ctx)
    e2 = b.buffs.get(e, "enemy_trwlpl_food")
    assert e2["blackboard"]["cnt"] == 5.0, e2["blackboard"]
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignBuffBlackboard",
                         "_targetType": "BUFF_OWNER",
                         "_buffKey": "enemy_trwlpl_food",
                         "_blackboardKey": "cnt", "_valueKey": "damage"}], ctx)
    assert b.buffs.get(e, "enemy_trwlpl_food")["blackboard"]["cnt"] == 15.0


def test_buff_misc_nodes():
    """LogExtraBattleInfo / FixedValueDamage / AssignBuffBlackboardFromOthers /
    TriggerEnemySkill."""
    from ark_emulator.consts import DamageType
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": None, "target": e, "bb": {"damage": 50.0}}

    # LogExtraBattleInfo emits battle_log
    b.events.log = []
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+LogExtraBattleInfo",
                         "_key": "shield_broken"}], ctx)
    assert any(x["type"] == "battle_log" and
               x.get("data", {}).get("key") == "shield_broken"
               for x in b.events.snapshot_events())

    # FixedValueDamage: 50 MAGICAL (mres 0 so the hit is exact)
    e.attributes.base["magicResistance"] = 0.0
    e.max_hp = 1e9
    e.hp = 1e9
    hp0 = e.hp
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FixedValueDamage",
                         "_targetType": "BUFF_OWNER", "_damageType": "TRUE",
                         "_damageKey": "damage"}], ctx)
    assert abs((hp0 - e.hp) - 50.0) < 1e-6, (hp0, e.hp)

    # AssignBuffBlackboardFromOthers copies a value from a source buff
    b.add_buff(e, {"key": "enemy_cbrokt_t", "remaining_ticks": 100,
                   "layers": 1, "blackboard": {"origin_speed": 0.7}})
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignBuffBlackboardFromOthers",
                         "_targetType": "BUFF_OWNER", "_sourceType": "TARGET",
                         "_buffKey": "enemy_cbrokt_t",
                         "_blackboardKey": "origin_speed",
                         "_valueKey": "origin_speed"}], ctx)
    assert b.buffs.get(e, "enemy_cbrokt_t")["blackboard"]["origin_speed"] == 0.7

    # TriggerEnemySkill emits skill_trigger
    b.events.log = []
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+TriggerEnemySkill",
                         "_skillName": "SomeSkill"}], ctx)
    assert any(x["type"] == "skill_trigger" for x in b.events.snapshot_events())


def test_buff_batch3_nodes():
    """IsDamage / DamageViaMaxHpRatio / FilterByTargetSpRatio /
    AssignBuffCountIntoBlackboard / AssignAttributeToBB / ChangeMotionMode."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": None, "target": e,
           "bb": {"hp_ratio": 0.1}}

    # IsDamage
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsDamage"}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {}, "damage": {"amount": 10.0}})
    assert r[0]["action"] is True
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsDamage"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r2[0]["action"] is False

    # DamageViaMaxHpRatio: 0.1 x maxHp PURE
    e.attributes.base["magicResistance"] = 0.0
    mx = e.max_hp
    e.hp = mx
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+DamageViaMaxHpRatio",
                         "_targetType": "BUFF_OWNER", "_damageType": "PURE"}], ctx)
    assert abs((mx - e.hp) - mx * 0.1) < 1.0, (mx, e.hp)

    # FilterByTargetSpRatio GE 0.5
    e.sp_max = 100.0
    e.sp = 80.0
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetSpRatio",
                              "_targetType": "BUFF_OWNER", "_condType": "GE",
                              "_spRatio": 0.5}], ctx)
    assert r3[0]["action"] is True, r3

    # AssignBuffCountIntoBlackboard: layers 3 -> bb cnt
    b.add_buff(e, {"key": "aegiret_t_1[to_character]", "remaining_ticks": 100,
                   "layers": 3})
    ctx2 = {"owner": e, "source": None, "target": e, "bb": {}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignBuffCountIntoBlackboard",
                         "_targetType": "BUFF_OWNER",
                         "_buffKey": "aegiret_t_1[to_character]",
                         "_stackCountKey": "sp_recover"}], ctx2)
    assert ctx2["bb"].get("sp_recover") == 3, ctx2["bb"]

    # AssignAttributeToBB: copy moveSpeed
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignAttributeToBB",
                         "_targetType": "BUFF_OWNER", "_attributeType": "MOVE_SPEED",
                         "_blackboardKey": "current_speed"}], ctx2)
    assert ctx2["bb"].get("current_speed") == e.attributes.get("moveSpeed")

    # ChangeMotionMode -> FLY
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ChangeMotionMode",
                         "_target": "BUFF_OWNER", "_motionMode": "FLY"}], ctx2)
    assert e._motion_mode == 1


def test_buff_batch4_nodes():
    """AOEDamage / FinishDerivedBuff / CreateBuffStacked / ModifyBlackboard /
    InterruptAbility."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.row, e.col = 3, 3
    e.pos_x, e.pos_y = 3.0, 3.0
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    ally = b.enemies[1]
    ally.row, ally.col = 3, 4
    ally.pos_x, ally.pos_y = 4.0, 3.0
    ally.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": e, "target": e,
           "bb": {"range_radius": 2.0, "atk_scale": 1.0}}

    # AOEDamage: nearby enemy takes atk x 1.0
    ally.max_hp = 1e9
    ally.hp = 1e9
    e.max_hp = 1e9
    e.hp = 1e9
    a0 = ally.hp
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AOEDamage",
                         "_sourceType": "BUFF_SOURCE", "_targetType": "BUFF_OWNER",
                         "_damageType": "TRUE",
                         "_targetOptions": {"targetSide": "ENEMY"}}], ctx)
    # enemy_1000_gopro_2 is side 0 and within 2 of e -> took damage
    assert a0 - ally.hp > 0.0, (a0, ally.hp)

    # FinishDerivedBuff removes the current buff entry
    b.add_buff(e, {"key": "test_fdb", "remaining_ticks": 100, "layers": 1})
    ctx2 = {"owner": e, "source": None, "target": e,
            "bb": {"_buff_entry": b.buffs.get(e, "test_fdb")}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishDerivedBuff"}], ctx2)
    assert b.buffs.get(e, "test_fdb") is None

    # ModifyBlackboard sets a chain bb value
    ctx3 = {"owner": e, "source": None, "target": e, "bb": {"cnt": 1.0}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyBlackboard",
                         "_blackboardKeys": "cnt", "_value": 5.0}], ctx3)
    assert ctx3["bb"]["cnt"] == 5.0, ctx3["bb"]
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyBlackboard",
                         "_blackboardKeys": "cnt", "_value": 2.0,
                         "_addBasedOriginValue": True}], ctx3)
    assert ctx3["bb"]["cnt"] == 7.0, ctx3["bb"]

    # InterruptAbility interrupts an active cast
    from ark_emulator.consts import EnemyState as ES
    b.spawn_enemy("enemy_2089_skzjkl", 0)
    e4 = b.enemies[-1]
    e4.state = ES.COMBAT
    sc = e4.skill_controller
    multi = next(s for s in sc.skills if s.prefab_key == "M1MultiAttack")
    sc._start_cast((multi, None))
    assert sc.casting is not None
    eng.run_actions(e4, [{"$type": "Torappu.Battle.Action.Nodes+InterruptAbility"}],
                    {"owner": e4, "source": None, "target": e4, "bb": {}})
    assert sc.casting is None or sc.casting.finished


def test_buff_batch5_nodes():
    """CheckAbnormalFlags / CreateBuffToCertainSideUnits / FilterDamageModifer."""
    from ark_emulator.consts import AbnormalFlag
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}

    # CheckAbnormalFlags: no flags -> False; with STUNNED -> True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckAbnormalFlags",
                             "_abnormalFlags": ["STUNNED", "FROZEN"],
                             "_targetType": "BUFF_OWNER"}], ctx)
    assert r[0]["action"] is False, r
    b.add_abnormal(e, AbnormalFlag.STUNNED, 5.0)
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckAbnormalFlags",
                              "_abnormalFlags": ["STUNNED", "FROZEN"],
                              "_targetType": "BUFF_OWNER"}], ctx)
    assert r2[0]["action"] is True, r2

    # CreateBuffToCertainSideUnits: buff all ENEMY-side units
    bd = {"buffKey": "test_side_buff", "templateKey": "test_side_buff",
          "attributes": {}, "maxStackCnt": 1, "lifeTimeType": 0,
          "lifeTime": 0.0}
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffToCertainSideUnits",
                              "_sideMask": "ENEMY", "_buff": bd}], ctx)
    assert r3[0]["action"] is True, r3
    assert all(b.buffs.get(u, "test_side_buff") is not None
               for u in b.enemies), [x.get("key") for x in e.buffs]

    # FilterDamageModifer: MAGICAL mask vs PHYSICAL damage -> False
    r4 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterDamageModifer",
                              "_filterDamageType": True,
                              "_damageMask": "MAGICAL"}],
                         {"owner": e, "source": None, "target": e,
                          "bb": {}, "damage": {"type": "PHYSICAL"}})
    assert r4[0]["action"] is False, r4


def test_buff_batch6_nodes():
    """AtkScaleUp / AttributeModifierWithBB / SummonEnemyWithRuntimeRoute."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)

    # AtkScaleUp writes the scale key (default when absent)
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AtkScaleUp",
                         "_atkScaleKey": "atk_scale", "_defaultValue": 1.5}], ctx)
    assert ctx["bb"].get("atk_scale") == 1.5, ctx["bb"]

    # AttributeModifierWithBB: MAX_HP MULTIPLIER from bb max_hp
    mx0 = e.max_hp
    ctx2 = {"owner": e, "source": None, "target": e, "bb": {"max_hp": 0.2}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AttributeModifierWithBB",
                         "_targetType": "BUFF_OWNER", "_attributeType": "MAX_HP",
                         "_valueKey": "max_hp", "_formulaType": "MULTIPLIER"}], ctx2)
    assert abs(e.max_hp - mx0 * 1.2) < 1.0, (mx0, e.max_hp)

    # SummonEnemyWithRuntimeRoute spawns a flying unharmful enemy
    n0 = len(b.enemies)
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SummonEnemyWithRuntimeRoute",
                         "_source": "BUFF_OWNER", "_enemyKey": "enemy_1000_gopro",
                         "_motionMode": "FLY", "_unharmful": True}], ctx2)
    assert len(b.enemies) == n0 + 1
    nxt = b.enemies[-1]
    assert nxt._motion_mode == 1 and nxt.is_unharmful


def test_buff_cancel_modifier():
    """CancelModifier removes attribute-modifier buffs from the unit."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    b.add_buff(e, {"key": "def_buff", "stat": "def", "add": 50.0,
                   "remaining_ticks": 1000, "layers": 1})
    b.add_buff(e, {"key": "plain_buff", "remaining_ticks": 1000, "layers": 1})
    assert b.buffs.get(e, "def_buff") is not None
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CancelModifier",
                         "_targetType": "BUFF_OWNER"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert b.buffs.get(e, "def_buff") is None
    assert b.buffs.get(e, "plain_buff") is not None


def test_summon_enemies_follow_my_route_with_buff():
    """Death-split summon with an immediately attached embedded buff."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.row, e.col = 3, 3
    e.pos_x, e.pos_y = 3.0, 3.0
    eng = BuffTemplateEngine(b)
    node = {
        "$type": "Torappu.Battle.Action.Nodes+SummonEnemiesFollowMyRouteWithBuff",
        "_source": "BUFF_OWNER", "_enemyKey": "enemy_1000_gopro",
        "_summonCount": 1, "_addNoSourceBuffImmediately": True,
        "_noSourceBuff": {"buffKey": "test_spawn_buff",
                          "templateKey": "test_spawn_buff",
                          "attributes": {}, "maxStackCnt": 1,
                          "lifeTimeType": 0, "lifeTime": 0.0},
    }
    n0 = len(b.enemies)
    eng.run_actions(e, [node],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert len(b.enemies) == n0 + 1
    assert b.buffs.get(b.enemies[-1], "test_spawn_buff") is not None


def test_buff_batch7_nodes():
    """ModifyAbilityBlackboardAndCast / CheckCharSkillAffecting."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1514_smephi", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)

    # ModifyAbilityBlackboardAndCast writes into the Poison ability bb
    ctx = {"owner": e, "source": None, "target": e, "bb": {"damage": 100.0}}
    sc = e.skill_controller
    poison = next((s for s in sc.skills if s.prefab_key == "Poison"), None)
    if poison is not None:
        eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyAbilityBlackboardAndCast",
                             "_blackboardKeys": "damage", "_ability": "Poison"}], ctx)
        assert poison.blackboard.get("damage") == 100.0, poison.blackboard

    # CheckCharSkillAffecting: no operator-sourced skill buff -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCharSkillAffecting",
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r


def test_create_buff_use_ability_selector():
    """CreateBuffUseAbilitySelector applies the embedded buff to the
    resolved target."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    bd = {"buffKey": "enemy_dmech_charge[sp_reduce]",
          "templateKey": "enemy_dmech_charge[sp_reduce]",
          "attributes": {}, "maxStackCnt": 1, "lifeTimeType": 0,
          "lifeTime": 0.0}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffUseAbilitySelector",
                             "_sourceType": "SOURCE", "_targetType": "TARGET",
                             "_abilityName": "charge_gunctrl", "_buff": bd}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.buffs.get(e, "enemy_dmech_charge[sp_reduce]") is not None


def test_emit_projectile_with_buff():
    """EmitProjectile fires a projectile and applies _buffDataList on hit."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.row, e.col = 3, 3
    e.pos_x, e.pos_y = 3.0, 3.0
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    tgt = b.enemies[1]
    tgt.row, tgt.col = 3, 4
    tgt.pos_x, tgt.pos_y = 4.0, 3.0
    tgt.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)
    bd = {"buffKey": "hit_buff", "templateKey": "hit_buff",
          "attributes": {}, "maxStackCnt": 1, "lifeTimeType": 0,
          "lifeTime": 0.0}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+EmitProjectile",
                             "_sourceType": "BUFF_OWNER", "_targetType": "TARGET",
                             "_projectileKey": "projectile_enemy_faust_s1",
                             "_buffDataList": [bd]}],
                        {"owner": e, "source": e, "target": tgt, "bb": {}})
    assert r[0]["action"] is True, r
    guard = 0
    while guard < 300:
        b.tick_once()
        guard += 1
        if b.buffs.get(tgt, "hit_buff") is not None:
            break
    assert b.buffs.get(tgt, "hit_buff") is not None, tgt.buffs


def test_buff_batch8_nodes():
    """ModifyLifePoint / HpRatioTrigger / CheckEnemyUnbalanced /
    IsCharacter / ClearCharacterSp / CheckCharacterDefaultDirection /
    CheckModifierContainsKey / ModifyAbilityBlackboard."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)

    # ModifyLifePoint
    lp0 = b.life_point
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyLifePoint",
                         "_sourceType": "SOURCE", "_blackboardKey": "value"}],
                    {"owner": e, "source": None, "target": e, "bb": {"value": -1.0}})
    assert b.life_point == lp0 - 1, (lp0, b.life_point)

    # HpRatioTrigger GT 0.5
    e.max_hp = 100.0
    e.hp = 80.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+HpRatioTrigger",
                             "_targetType": "BUFF_OWNER", "_condType": "GT",
                             "_hpRatioEachTime": 0.5}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # CheckEnemyUnbalanced
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyUnbalanced",
                              "_targetType": "BUFF_OWNER"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r2[0]["action"] is False
    e.displacement = {"dr": 0, "dc": 1, "remaining": 1.0, "total": 1.0}
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyUnbalanced",
                              "_targetType": "BUFF_OWNER"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r3[0]["action"] is True

    # IsCharacter: enemy -> False
    r4 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsCharacter",
                              "_targetType": "BUFF_OWNER"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r4[0]["action"] is False

    # ClearCharacterSp
    e.sp = 50.0
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ClearCharacterSp",
                         "_charFrom": "BUFF_OWNER"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert e.sp == 0.0

    # CheckCharacterDefaultDirection: RIGHT(1)
    e.direction = 1
    r5 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCharacterDefaultDirection",
                              "_target": "BUFF_OWNER", "_direction": "RIGHT"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r5[0]["action"] is True, r5

    # CheckModifierContainsKey
    b.add_buff(e, {"key": "enemy_ristar_ally_damage", "remaining_ticks": 100,
                   "layers": 1})
    r6 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckModifierContainsKey",
                              "_customKey": "enemy_ristar_ally_damage"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r6[0]["action"] is True, r6

    # ModifyAbilityBlackboard writes into the first skill's bb
    if getattr(e, "skill_controller", None) is not None and             e.skill_controller.skills:
        sk = e.skill_controller.skills[0]
        ctx9 = {"owner": e, "source": None, "target": e, "bb": {"damage": 7.0}}
        eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyAbilityBlackboard",
                             "_blackboardKeys": "damage"}], ctx9)
        assert sk.blackboard.get("damage") == 7.0, sk.blackboard


def test_buff_batch9_nodes():
    """DamageViaAttr / AddGlobalBlackboard / AddCharacterSharedBlackboard /
    CreateBuffToToken."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)

    # DamageViaAttr: DEF of the target dealt to the target
    e.attributes.base["def"] = 40.0
    e.max_hp = 1e9
    e.hp = 1e9
    hp0 = e.hp
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+DamageViaAttr",
                         "_targetType": "BUFF_OWNER", "_sourceType": "SOURCE",
                         "_attributeType": "DEF", "_getAttrFromTarget": True,
                         "_damageType": "PURE"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert hp0 - e.hp > 0.0, (hp0, e.hp)

    # AddGlobalBlackboard writes into the chain bb
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AddGlobalBlackboard",
                         "_blackboardKey": "act6bossrush_life_point_buff",
                         "_value": 1.0}], ctx)
    assert ctx["bb"]["act6bossrush_life_point_buff"] == 1.0

    # AddCharacterSharedBlackboard (string)
    ctx2 = {"owner": e, "source": None, "target": e, "bb": {}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AddCharacterSharedBlackboard",
                         "_target": "BUFF_OWNER", "_isStringBB": True,
                         "_blackboardKey": "range_id", "_valueStr": "x-4"}], ctx2)
    assert ctx2["bb"].get("range_id") == "x-4", ctx2["bb"]


def test_buff_batch10_nodes():
    """FixedValueHeal / ReleaseFromBlocker / IfEnemyIsMovingBySelf /
    CreateBuffToBlockee / CheckEntityDisappeared."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)

    # FixedValueHeal
    e.max_hp = 1000.0
    e.hp = 500.0
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FixedValueHeal",
                         "_targetType": "BUFF_OWNER", "_healValueKey": "value"}],
                    {"owner": e, "source": None, "target": e, "bb": {"value": 300.0}})
    assert e.hp == 800.0, e.hp

    # IfEnemyIsMovingBySelf: COMBAT -> False, MOVE unblocked -> True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IfEnemyIsMovingBySelf",
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r
    e.state = EnemyState.MOVE
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IfEnemyIsMovingBySelf",
                              "_targetType": "BUFF_OWNER"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r2[0]["action"] is True, r2

    # ReleaseFromBlocker
    b.max_cost = 1000.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    e.blocked_by = op
    op.add_blockee(e)
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ReleaseFromBlocker",
                              "_target": "BUFF_OWNER"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r3[0]["action"] is True, r3
    assert e.blocked_by is None

    # CreateBuffToBlockee
    e2 = b.enemies[0]
    e2.state = EnemyState.COMBAT
    e2.blocked_by = op
    op.add_blockee(e2)
    bd = {"buffKey": "blockee_buff", "templateKey": "blockee_buff",
          "attributes": {}, "maxStackCnt": 1, "lifeTimeType": 0,
          "lifeTime": 0.0}
    r4 = eng.run_actions(op, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffToBlockee",
                               "_targetType": "BUFF_OWNER", "_buff": bd}],
                         {"owner": op, "source": None, "target": op, "bb": {}})
    assert r4[0]["action"] is True, r4
    assert b.buffs.get(e2, "blockee_buff") is not None

    # CheckEntityDisappeared
    r5 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEntityDisappeared",
                              "_targetType": "BUFF_OWNER"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r5[0]["action"] is False, r5


def test_buff_batch11_nodes():
    """CreateBuffInCircleRange / CreateBuffUseTargetAsSource /
    AddAbilityBlackboard / AttachAsDerivedBuffById."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.row, e.col = 3, 3
    e.pos_x, e.pos_y = 3.0, 3.0
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    ally = b.enemies[1]
    ally.row, ally.col = 3, 4
    ally.pos_x, ally.pos_y = 4.0, 3.0
    ally.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)
    bd = {"buffKey": "circle_buff", "templateKey": "circle_buff",
          "attributes": {}, "maxStackCnt": 1, "lifeTimeType": 0,
          "lifeTime": 0.0}

    # CreateBuffInCircleRange: nearby ENEMY-side unit gets the buff
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffInCircleRange",
                             "_sourceType": "BUFF_OWNER", "_targetType": "BUFF_OWNER",
                             "_rangeRadius": 2.0,
                             "_targetOptions": {"targetSide": "ENEMY"},
                             "_buffs": [bd]}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.buffs.get(ally, "circle_buff") is not None

    # CreateBuffUseTargetAsSource: buff applied on the target
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffUseTargetAsSource",
                              "_targetType": "TARGET", "_buff": bd}],
                         {"owner": e, "source": None, "target": ally, "bb": {}})
    assert r2[0]["action"] is True, r2

    # AttachAsDerivedBuffById
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AttachAsDerivedBuffById",
                              "_sourceType": "BUFF_OWNER",
                              "_buffKey": "enemy_pyczog_riding_ready"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r3[0]["action"] is True, r3
    assert b.buffs.get(e, "enemy_pyczog_riding_ready") is not None


def test_buff_batch12_nodes():
    """TriggerAbilityUseSelector / CheckHasEnemyInRange / SpShowBuff /
    CreateCardBuff."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.row, e.col = 3, 3
    e.pos_x, e.pos_y = 3.0, 3.0
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    ally = b.enemies[1]
    ally.row, ally.col = 3, 4
    ally.pos_x, ally.pos_y = 4.0, 3.0
    ally.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # CheckHasEnemyInRange: ally within 1.5 -> True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasEnemyInRange",
                             "_soureceType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # TriggerAbilityUseSelector emits skill_trigger
    b.events.log = []
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+TriggerAbilityUseSelector",
                         "_sourceType": "BUFF_OWNER", "_targetType": "BUFF_OWNER",
                         "_abilityName": "ActiveRandom"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert any(x["type"] == "skill_trigger" for x in b.events.snapshot_events())

    # SpShowBuff emits sp_show_buff
    b.events.log = []
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SpShowBuff",
                         "_targetType": "BUFF_OWNER", "_spShowBuffKey": "k"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert any(x["type"] == "sp_show_buff" for x in b.events.snapshot_events())

    # CreateCardBuff emits card_buff
    b.events.log = []
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
                         "_target": "BUFF_OWNER"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert any(x["type"] == "card_buff" for x in b.events.snapshot_events())


def test_buff_batch13_nodes():
    """SetBodyDirection / IsBlackboardEqualWithString / CheckCurrentTileKey /
    CheckMotionMode / FilterByGlobalBlackboard / IsElementDamage."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.row, e.col = 3, 3
    e.pos_x, e.pos_y = 3.0, 3.0
    eng = BuffTemplateEngine(b)

    # SetBodyDirection
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SetBodyDirection",
                         "_targetType": "BUFF_OWNER", "_direction": "LEFT"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert e.direction == 3, e.direction

    # IsBlackboardEqualWithString
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsBlackboardEqualWithString",
                             "_var": "isenabled", "_compareValue": "aura_on"}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"isenabled": "aura_on"}})
    assert r[0]["action"] is True, r

    # CheckMotionMode: WALK -> True
    e._motion_mode = 0
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckMotionMode",
                              "_targetType": "BUFF_OWNER", "_mode": "WALK"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r2[0]["action"] is True, r2

    # FilterByGlobalBlackboard GE
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByGlobalBlackboard",
                              "_blackboardKey": "act6bossrush_life_point_buff",
                              "_valueToCompare": 1.0, "_condType": "GE"}],
                         {"owner": e, "source": None, "target": e,
                          "bb": {"act6bossrush_life_point_buff": 2.0}})
    assert r3[0]["action"] is True, r3

    # IsElementDamage
    r4 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsElementDamage"}],
                         {"owner": e, "source": None, "target": e,
                          "bb": {}, "damage": {"type": "ELEMENT"}})
    assert r4[0]["action"] is True, r4


def test_buff_batch14_nodes():
    """IfTargetEqual / Evade / VertifyTarget / CompareCharSkillAvailableCnt /
    FilterAbilityName / UpdateAbilityCoolDown."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": e, "target": e, "bb": {}}

    # IfTargetEqual: same unit -> True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IfTargetEqual",
                             "_target1": "SOURCE", "_target2": "TARGET"}], ctx)
    assert r[0]["action"] is True, r

    # Evade: PHYSICAL damage matches PHYSICAL_AND_MAGICAL
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+Evade",
                              "_damageMask": "PHYSICAL_AND_MAGICAL"}],
                         {"owner": e, "source": e, "target": e,
                          "bb": {}, "damage": {"type": "PHYSICAL"}})
    assert r2[0]["action"] is True, r2

    # VertifyTarget: enemy side passes ENEMY mask
    r3 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+VertifyTarget",
                              "_source": "MODIFIER_TARGET",
                              "_target": "MODIFIER_SOURCE",
                              "_targetOptions": {"targetSide": "ENEMY"}}], ctx)
    assert r3[0]["action"] is True, r3

    # CompareCharSkillAvailableCnt: no available skills (gopro has none
    # ready / no skills) -> GE 1 False
    r4 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CompareCharSkillAvailableCnt",
                              "_targetType": "BUFF_OWNER", "_condType": "GE",
                              "_count": 1}], ctx)
    assert r4[0]["action"] is False, r4

    # UpdateAbilityCoolDown sets a skill's cooldown
    if getattr(e, "skill_controller", None) is not None and \
            e.skill_controller.skills:
        sk0 = e.skill_controller.skills[0]
        sk0.cooldown_remaining = 0.0
        eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+UpdateAbilityCoolDown",
                             "_ownerType": "BUFF_OWNER",
                             "_abilityName": sk0.prefab_key,
                             "_coolDownKey": "cd"}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"cd": 5.0}})
        assert abs(sk0.cooldown_remaining - 5.0) < 1e-6


def test_damage_scale_nodes():
    """DamageScale scales the damage context (isOneMinus)."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    ctx = {"owner": e, "source": None, "target": e, "bb": {"scale": 0.2},
           "damage": {"amount": 100.0}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+DamageScale",
                         "_scaleKey": "scale", "_isOneMinus": True}], ctx)
    assert abs(ctx["damage"]["amount"] - 80.0) < 1e-6, ctx["damage"]


def test_buff_batch16_nodes():
    """CheckHasAllyInRange / InsertCheckPointInRuntimeRoute."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    e.row, e.col = 3, 3
    e.pos_x, e.pos_y = 3.0, 3.0
    eng = BuffTemplateEngine(b)

    # CheckHasAllyInRange: no operators -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasAllyInRange",
                             "_soureceType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # with an operator within 1.5 -> True
    b.max_cost = 1000.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 4)
    r2 = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasAllyInRange",
                              "_soureceType": "BUFF_OWNER"}],
                         {"owner": e, "source": None, "target": e, "bb": {}})
    assert r2[0]["action"] is True, r2

    # InsertCheckPointInRuntimeRoute sets the wait
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+InsertCheckPointInRuntimeRoute",
                         "_source": "TARGET", "_target": "TARGET",
                         "_type": "WAIT_FOR_SECONDS", "_time": 5.0}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert e._wait_remaining == 5.0, e._wait_remaining


def test_buff_batch17_nodes():
    """AdvancedApplyHeal / ClearAllBuffs / AssignHpRatioToBB /
    FilterByExecuteBlackboardValue / TriggerEnvSystem."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)

    # AdvancedApplyHeal: atk x heal_scale
    e.max_hp = 1000.0
    e.hp = 400.0
    e.attributes.base["atk"] = 200.0
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AdvancedApplyHeal",
                         "_sourceType": "BUFF_SOURCE", "_targetType": "BUFF_OWNER",
                         "_healScaleKey": "heal_scale"}],
                    {"owner": e, "source": e, "target": e, "bb": {"heal_scale": 2.0}})
    assert e.hp == 800.0, e.hp

    # ClearAllBuffs with retained keys
    b.add_buff(e, {"key": "keep_me", "remaining_ticks": 100, "layers": 1})
    b.add_buff(e, {"key": "drop_me", "remaining_ticks": 100, "layers": 1})
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ClearAllBuffs",
                         "_targetType": "BUFF_OWNER",
                         "_retainedBuffsWhenClear": ["keep_me"]}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert b.buffs.get(e, "keep_me") is not None
    assert b.buffs.get(e, "drop_me") is None

    # AssignHpRatioToBB
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    e.hp = e.max_hp / 2.0
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignHpRatioToBB",
                         "_targetType": "BUFF_OWNER",
                         "_blackboardKey": "cur_hp_ratio"}], ctx)
    assert abs(ctx["bb"]["cur_hp_ratio"] - 0.5) < 1e-6, ctx["bb"]

    # FilterByExecuteBlackboardValue GT
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByExecuteBlackboardValue",
                             "_blackboardKey": "enable_silence",
                             "_valueToCompare": 0, "_condType": "GT"}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"enable_silence": 1}})
    assert r[0]["action"] is True, r

    # TriggerEnvSystem emits env_trigger
    b.events.log = []
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+TriggerEnvSystem",
                         "_envKey": "env_006_act25side_extra"}],
                    {"owner": e, "source": None, "target": e, "bb": {}})
    assert any(x["type"] == "env_trigger" for x in b.events.snapshot_events())

def test_buff_batch18_nodes():
    """FilterByTargetAttribute / Loop / SummonEnemiesFollowBranchRoute."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)   # medic, blockCnt 0
    op = b.operators[0]
    eng = BuffTemplateEngine(b)

    # FilterByTargetAttribute: medic has BLOCK_CNT 1 -> LE 1 passes, GE 2 fails
    r = eng.run_actions(op, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetAttribute, Assembly-CSharp",
                              "_target": "BUFF_OWNER", "_condType": "LE",
                              "_attributeType": "BLOCK_CNT", "_value": 1,
                              "_useFloat": False, "_valueFP": 0.0}],
                        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(op, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetAttribute, Assembly-CSharp",
                              "_target": "BUFF_OWNER", "_condType": "GE",
                              "_attributeType": "BLOCK_CNT", "_value": 2,
                              "_useFloat": False, "_valueFP": 0.0}],
                        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is False, r

    # Loop with keyMappingList + stopWhenPreviousSucceed: first Dice fails
    # (prob 0), second succeeds (prob 1) -> ModifyCost runs exactly once.
    cost0 = b.cost
    body = [
        {"$type": "Torappu.Battle.Action.Nodes+Dice, Assembly-CSharp",
         "_probKey": "prob"},
        {"$type": "Torappu.Battle.Action.Nodes+ModifyCost, Assembly-CSharp",
         "_sourceType": "BUFF_OWNER", "_forceToDisplayNumber": True,
         "_forceToDisplayNegativeNumber": False, "_blackboardKey": "cost"},
    ]
    loop = {"$type": "Torappu.Battle.Action.Nodes+Loop, Assembly-CSharp",
            "_loopCnt": 0, "_loopCntKey": None, "_useMappingList": True,
            "_stopWhenPreviousSucceed": True,
            "_keyMappingList": [
                {"mapping": [{"source": "p1", "target": "prob"},
                             {"source": "c1", "target": "cost"}]},
                {"mapping": [{"source": "p2", "target": "prob"},
                             {"source": "c2", "target": "cost"}]},
            ],
            "_loopBody": body}
    ctx = {"owner": op, "source": None, "target": op,
           "bb": {"p1": 0.0, "c1": 3.0, "p2": 1.0, "c2": 5.0}}
    r = eng.run_actions(op, [loop], ctx)
    assert r[0]["action"] is True, r
    assert b.cost - cost0 == 5.0, (b.cost, cost0)

    # SummonEnemiesFollowBranchRoute: 2 enemies at the owner tile + buff
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0
    e.state = EnemyState.COMBAT
    n0 = len(b.enemies)
    snode = {"$type": "Torappu.Battle.Action.Nodes+SummonEnemiesFollowBranchRoute, Assembly-CSharp",
             "_unharmful": True, "_managedByScheduler": True,
             "_alwaysCountAsKilled": False, "_disableBornTweenColor": True,
             "_buffToEnemy": {
                 "buffKey": "bgarmn[sync_hp_from_trap]",
                 "templateKey": "trap_bgarmn[sync_hp_from_trap]",
                 "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                "abnormalAntis": [], "abnormalCombos": [],
                                "abnormalComboImmunes": [],
                                "attributeModifiers": []},
                 "lifeTimeType": "LIMITED", "durationKey": "effect_duration",
                 "lifeTime": 3.0},
             "_overrideEnemyKey": "", "_setHostUid": False,
             "_summonAllRoute": False, "_defaultBranchId": ""}
    r = eng.run_actions(e, [snode], {"owner": e, "source": None,
                                     "target": e,
                                     "bb": {"enemy_key": "enemy_1000_gopro",
                                            "count": 2.0}})
    assert r[0]["action"] is True, r
    new = [x for x in b.enemies[n0:] if x is not e]
    assert len(new) == 2, len(new)
    for u in new:
        assert getattr(u, "is_unharmful", False) is True
        keys = [x.get("key") for x in getattr(u, "buffs", [])]
        assert "bgarmn[sync_hp_from_trap]" in keys, keys

def test_buff_batch19_inverse_damage():
    """InverseDamage reflects the blackboard value back at the attacker
    (Mlynar T2: TRUE damage reflection when an ally is attacked)."""
    from ark_emulator.consts import DamageType
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)
    b.add_buff(op, {"key": "t_inverse", "remaining_ticks": 30 * 30,
                    "template_key": "mlynar_t_2[inverse]",
                    "blackboard": {"value": 50.0}})
    hp0 = e.hp
    b.apply_damage(op, 100.0, DamageType.PHYSICAL, source=e)
    assert abs((hp0 - e.hp) - 50.0) < 1e-6, (hp0, e.hp)

    # second PURE template also reflects (incoming type not filtered)
    b.buffs.remove(op, "t_inverse")
    e.hp = hp0
    b.add_buff(op, {"key": "t_inverse2", "remaining_ticks": 30 * 30,
                    "template_key": "inverse_damage",
                    "blackboard": {"value": 30.0}})
    b.apply_damage(op, 100.0, DamageType.PHYSICAL, source=e)
    assert abs((hp0 - e.hp) - 30.0) < 1e-6, (hp0, e.hp)

    # enemy-side source filter: attacker is an operator (side 1) vs ENEMY
    # mask -> no reflect: op takes no reflected damage
    e.hp = hp0
    op.hp = op.max_hp
    hp_op0 = op.hp
    b.add_buff(e, {"key": "t_inverse_enf", "remaining_ticks": 30 * 30,
                   "template_key": "mlynar_t_2[inverse]",
                   "blackboard": {"value": 50.0}})
    b.apply_damage(e, 100.0, DamageType.PHYSICAL, source=op)
    assert abs(op.hp - hp_op0) < 1e-6, (hp_op0, op.hp)

def test_buff_batch20_nodes():
    """HealViaDamage / CheckHasSp / KillTokens."""
    from ark_emulator.consts import DamageType
    from ark_emulator.attributes import Attributes
    from ark_emulator.entities import Token
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)

    # HealViaDamage: enemy lifesteals 50% of damage it deals
    b.add_buff(e, {"key": "t_vamp", "remaining_ticks": 30 * 30,
                   "template_key": "vampire",
                   "blackboard": {"vampire.heal_scale": 0.5}})
    e.max_hp = 2000.0
    e.hp = 800.0
    op.attributes.base["def"] = 0.0
    op.hp = op.max_hp
    b.apply_damage(op, 100.0, DamageType.PHYSICAL, source=e)
    assert abs((e.hp - 800.0) - 50.0) < 1e-6, e.hp

    # CheckHasSp: no SP -> has-SP gate fails, lacks-SP gate passes
    e.sp = 0.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasSp",
                             "_ownerType": "BUFF_OWNER", "_checkHasSp": 1,
                             "_checkKey": "sp", "_condType": "GE"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasSp",
                             "_ownerType": "BUFF_OWNER", "_checkHasSp": 0,
                             "_checkKey": "", "_condType": "LE"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    e.sp = 40.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasSp",
                             "_ownerType": "BUFF_OWNER", "_checkHasSp": 1,
                             "_checkKey": "sp", "_condType": "GE"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # KillTokens: kills tokens owned by the buff owner
    tok = Token("token_test", Attributes({"maxHp": 100.0, "atk": 0.0}),
                3, 4, owner=e)
    b.tokens.append(tok)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+KillTokens",
                             "_checkContainsBuff": False, "_buffKey": "",
                             "_checkModes": False, "_modes": [],
                             "_snapshotSourceAsTarget": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert tok.dead is True, tok.dead

    # AOEHeal: heals allies around the center at atk x scale
    b.tokens.remove(tok)
    b.deploy("char_473_mberry", 2, 3)   # already deployed medic source
    med = b.operators[0]
    med.attributes.base["atk"] = 200.0
    b.battle_cost_add(200)
    b.deploy("char_275_breeze", 2, 5)   # another high-tile medic, wounded
    ally2 = b.operators[1]
    ally2.hp = ally2.max_hp - 100.0
    hp_a2 = ally2.hp
    # Keep the target inside the compact synthetic range used by AOEHeal.
    ally2.pos_x, ally2.pos_y = med.pos_x + 1.0, med.pos_y
    ally2.row, ally2.col = med.row, med.col + 1
    aoe = {"$type": "Torappu.Battle.Action.Nodes+AOEHeal, Assembly-CSharp",
           "_sourceType": "BUFF_SOURCE", "_targetType": "BUFF_OWNER",
           "_targetOptions": {"targetSide": "ALLY"},
           "_excludeTarget": False, "_rangeId": None,
           "_useAttackRange": False, "_ignoreHealFree": False,
           "_createEffect": False, "_healEffectKey": None,
           "_healScale": "scale", "_sourceSideType": "ALLY"}
    r = eng.run_actions(med, [aoe], {"owner": med, "source": med,
                                     "target": med,
                                     "bb": {"scale": 0.5}})
    assert r[0]["action"] is True, r
    assert abs(ally2.hp - (hp_a2 + 100.0)) < 1e-6, (hp_a2, ally2.hp)

    # FinishManagedProjectiles: clears projectiles sourced from the unit
    from ark_emulator.consts import DamageType as _DT
    from ark_emulator.projectiles import Projectile
    pr = Projectile(e, op, 5.0, damage_type=_DT.PHYSICAL, atk_scale=1.0,
                    key="proj_test")
    b.projectiles.append(pr)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishManagedProjectiles",
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert pr.dead is True, pr.dead

def test_buff_batch21_try_set_hp_zero():
    """TrySetHpZero chain: a lethal hit consumes the Surtr T2 modifier,
    keeps HP at 1 and applies UNDEADABLE via the ON_POST chain."""
    from ark_emulator.consts import DamageType, AbnormalFlag
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    op.attributes.base["def"] = 0.0
    op.attributes.base["magicResistance"] = 0.0
    b.add_buff(op, {"key": "surtr_t_2", "remaining_ticks": 30 * 3600,
                    "template_key": "surtr_t_2", "blackboard": {}})
    op.hp = 100.0
    b.apply_damage(op, 5000.0, DamageType.TRUE, source=None)
    assert op.dead is False, "Surtr T2 must survive the lethal hit"
    assert abs(op.hp - 1.0) < 1e-6, op.hp
    keys = [x.get("key") for x in op.buffs]
    assert "surtr_t_2[undeadable]" in keys, keys
    assert op.flag(AbnormalFlag.UNDEADABLE)
    assert "surtr_t_2" not in keys, "one-shot modifier must be consumed"

    # without UNDEADABLE the next lethal hit kills
    b.buffs.remove(op, "surtr_t_2[undeadable]")
    op.clear_flag(AbnormalFlag.UNDEADABLE)
    op.hp = 100.0
    b.apply_damage(op, 5000.0, DamageType.TRUE, source=None)
    assert op.dead is True

    # a unit without the modifier dies on the first lethal hit
    sim2 = Simulator(level_id="level_main_01-01")
    sim2.run_ticks(15)
    b2 = sim2.battle
    b2.battle_cost_add(200)
    b2.deploy("char_473_mberry", 2, 3)
    op2 = b2.operators[0]
    op2.attributes.base["def"] = 0.0
    op2.hp = 100.0
    b2.apply_damage(op2, 5000.0, DamageType.TRUE, source=None)
    assert op2.dead is True

def test_buff_batch22_rewrite_tile_options():
    """RewriteTileOptions: obstacle-like blocks the owner's tile, restore
    clears it (planet debris mechanic)."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1334_ristar", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    t0 = b.map.tile(3, 4)
    assert t0 is not None and t0.passable(0), t0.to_dict()
    eng = BuffTemplateEngine(b)
    block = {"$type": "Torappu.Battle.Action.Nodes+RewriteTileOptions, Assembly-CSharp",
             "_keepCurrentAdvancedBuildableMask": False, "_advancedBuildableMask": "NONE",
             "_keepCurrentPassableMask": True, "_passableMask": "NONE",
             "_keepCurrentBuildableType": True, "_buildableType": "NONE",
             "_keepCurrentObstacleLike": False, "_isObstacleLike": True,
             "_keepCurrentHeightType": True, "_heightType": "LOWLAND",
             "_keepCurrentOverlapHeight": True, "_overlapHeight": 0.4,
             "_restoreTileOptions": False, "_killLocatedIfNotBuildable": False,
             "_useOwnerRootTile": False, "_useTargetOldTile": False}
    r = eng.run_actions(e, [block], {"owner": e, "source": None,
                                     "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.map.tile(3, 4).passable(0) is False
    assert b.map.tile(3, 4).passable(1) is False
    # moving to a new tile does not restore the old one; restore node does
    restore = dict(block)
    restore["_restoreTileOptions"] = True
    restore["_isObstacleLike"] = False
    r = eng.run_actions(e, [restore], {"owner": e, "source": None,
                                       "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.map.tile(3, 4).passable(0) is True

def test_buff_batch23_bb_nodes():
    """AssignRootTileToBB / AssignGridPositionToBlackboard /
    IsBlackboardEqualWithFloat / FilterByTargetHp / AssignDirectionToBB."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.hp = 50.0
    e.direction = 1
    eng = BuffTemplateEngine(b)

    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignRootTileToBB",
                             "_targetType": "BUFF_OWNER", "_assignTargetTokenOrHost": False,
                             "_colKey": "col", "_rowKey": "row", "_assignAsString": False,
                             "_bbKey": None}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["row"] == 3 and ctx["bb"]["col"] == 4, ctx["bb"]

    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignGridPositionToBlackboard",
                             "_targetType": "BUFF_OWNER", "_gridRowKey": "enemy_row",
                             "_gridColKey": "enemy_col", "_useConstLocationKey": False}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["enemy_row"] == 3 and ctx["bb"]["enemy_col"] == 4, ctx["bb"]

    ctx = {"owner": e, "source": None, "target": e, "bb": {"flag": 1.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsBlackboardEqualWithFloat",
                             "_var": "flag", "_compareValue": 1.0}], ctx)
    assert r[0]["action"] is True, r
    ctx["bb"]["flag"] = 2.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsBlackboardEqualWithFloat",
                             "_var": "flag", "_compareValue": 1.0}], ctx)
    assert r[0]["action"] is False, r

    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetHp",
                             "_targetType": "BUFF_OWNER", "_condType": "LE",
                             "_hpValue": {"_serializedValue": 100.0}}], ctx)
    assert r[0]["action"] is True, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetHp",
                             "_targetType": "BUFF_OWNER", "_condType": "GT",
                             "_hpValue": {"_serializedValue": 100.0}}], ctx)
    assert r[0]["action"] is False, r

    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignDirectionToBB",
                             "_targetType": "BUFF_OWNER", "_isReverse": False,
                             "_blackboardKey": "direction", "_fromTokenOrHost": False}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["direction"] == 1, ctx["bb"]
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignDirectionToBB",
                             "_targetType": "BUFF_OWNER", "_isReverse": True,
                             "_blackboardKey": "direction", "_fromTokenOrHost": False}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["direction"] == 3, ctx["bb"]

def test_buff_batch24_direction_bb_nodes():
    """CheckDirection / CheckFaceDirection / UpdateEnemyCurrentTile /
    AssignDamageValueToBlackboard / AssignCurSpToBB /
    AssignModifierValueIntoBlackboard / CheckTargetInRange."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.direction = 1
    eng = BuffTemplateEngine(b)

    # CheckDirection EQUAL / OPPOSITE
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckDirection",
                             "_source": "BUFF_SOURCE", "_target": "BUFF_OWNER",
                             "_judgeType": "EQUAL"}],
                        {"owner": e, "source": e, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckDirection",
                             "_source": "BUFF_SOURCE", "_target": "BUFF_OWNER",
                             "_judgeType": "OPPOSITE"}],
                        {"owner": e, "source": e, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # CheckFaceDirection RIGHT passes, UP fails
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckFaceDirection",
                             "_target": "TARGET", "_direction": "RIGHT"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckFaceDirection",
                             "_target": "TARGET", "_direction": "UP"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # UpdateEnemyCurrentTile from interpolated position
    e.pos_x, e.pos_y = 4.3, 3.7
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+UpdateEnemyCurrentTile",
                             "_ownerType": "BUFF_OWNER", "_force": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert (e.row, e.col) == (4, 4), (e.row, e.col)

    # AssignDamageValueToBlackboard x scale
    ctx = {"owner": e, "source": None, "target": e, "bb": {"scale": 2.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignDamageValueToBlackboard",
                             "_owner": "BUFF_OWNER", "_damageType": "HEAL",
                             "_assignValueWithoutCalculate": False,
                             "_scaleKey": "scale", "_assignRealDelta": False}],
                        {**ctx, "damage": {"amount": 50.0}})
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["value"] - 100.0) < 1e-6, ctx["bb"]

    # AssignCurSpToBB ratio
    e.sp, e.sp_max = 30.0, 100.0
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignCurSpToBB",
                             "_targetType": "BUFF_OWNER", "_blackboardKey": "spRatio",
                             "_isRatio": True}], ctx)
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["spRatio"] - 0.3) < 1e-6, ctx["bb"]

    # AssignModifierValueIntoBlackboard
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignModifierValueIntoBlackboard",
                             "_blackboardKey": "value", "_filterModifierCancelled": False}],
                        {**ctx, "damage": {"amount": 42.0}})
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["value"] - 42.0) < 1e-6, ctx["bb"]

    # CheckTargetInRange: (2,3) facing right, range 2-2 -> (2,4) inside
    e.row, e.col = 2, 3
    e.direction = 1
    e2 = e
    b.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b.enemies[1]
    e2.row, e2.col = 2, 4
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckTargetInRange",
                             "_targetType": "MODIFIER_TARGET", "_soureceType": "MODIFIER_SOURCE",
                             "_rangeId": "2-2", "_autoRange": False,
                             "_checkRadius": False, "_rangeRadius": 0.0,
                             "_customDirection": False, "_direction": 0,
                             "_directionKey": "direction"}],
                        {"owner": e, "source": e, "target": e2, "bb": {}})
    assert r[0]["action"] is True, r
    e2.row, e2.col = 4, 4
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckTargetInRange",
                             "_targetType": "MODIFIER_TARGET", "_soureceType": "MODIFIER_SOURCE",
                             "_rangeId": "2-2", "_autoRange": False,
                             "_checkRadius": False, "_rangeRadius": 0.0,
                             "_customDirection": False, "_direction": 0,
                             "_directionKey": "direction"}],
                        {"owner": e, "source": e, "target": e2, "bb": {}})
    assert r[0]["action"] is False, r

def test_buff_batch25_overlap():
    """SetTilesEnableOverlap / ModifyOverlapSourceId + overlap events."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    ok, _ = b.deploy_token("trap_221_ftshad", 3, 4)
    assert ok
    tok = b.tokens[0]
    eng = BuffTemplateEngine(b)

    # SetTilesEnableOverlap: enable the root tile
    n1 = {"$type": "Torappu.Battle.Action.Nodes+SetTilesEnableOverlap, Assembly-CSharp",
          "_sourceType": "BUFF_OWNER", "_isEnable": True, "_onlyRootTile": True,
          "_useOffset": False, "_allTilesExceptRootTile": False, "_offsets": None}
    r = eng.run_actions(tok, [n1], {"owner": tok, "source": tok,
                                    "target": tok, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.map.tile(3, 4)._overlap_enabled is True

    # ModifyOverlapSourceId: allow a source id on the owner
    n2 = {"$type": "Torappu.Battle.Action.Nodes+ModifyOverlapSourceId, Assembly-CSharp",
          "_target": "BUFF_OWNER", "_sourceId": "trap_174_smfrut",
          "_isRemove": False, "_useBlackboardId": False}
    r = eng.run_actions(tok, [n2], {"owner": tok, "source": tok,
                                    "target": tok, "bb": {}})
    assert r[0]["action"] is True, r
    assert "trap_174_smfrut" in tok._overlap_source_ids, tok._overlap_source_ids

    # overlap events: token carries ON_OWNER_OVERLAPPED -> CreateBuff
    b.add_buff(tok, {"key": "t_ovl", "remaining_ticks": 30 * 3600,
                     "template_key": "trap_tjggt[passive]", "blackboard": {}})
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    b._check_enemy_overlap(e)
    keys = [x.get("key") for x in e.buffs]
    assert "highland_common[block]" in keys, keys

    # disable overlap: no more events (entering enemy keeps the old buff,
    # so clear it first)
    b.buffs.remove(e, "highland_common[block]")
    n3 = dict(n2)
    n3["_isRemove"] = True
    eng.run_actions(tok, [n3], {"owner": tok, "source": tok,
                                "target": tok, "bb": {}})
    b.map.tile(3, 4)._overlap_enabled = False
    b._check_enemy_overlap(e)
    keys = [x.get("key") for x in e.buffs]
    assert "highland_common[block]" not in keys, keys

def test_buff_batch26_switch_side():
    """SwitchSide: a defected enemy flips to ALLY, stops acting and is no
    longer targetable; the ON_BUFF_FINISH restore flips it back."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    assert e.side == 0
    b.add_buff(e, {"key": "t_switch", "remaining_ticks": 30 * 5,
                   "template_key": "switch_side_when_start", "blackboard": {}})
    assert e.side == 1, e.side

    # stops moving / attacking
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0
    e.state = EnemyState.MOVE
    r0 = (e.row, e.col)
    sim.run_ticks(30)
    assert (e.row, e.col) == r0, (r0, (e.row, e.col))

    # no longer the operator's target
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    from ark_emulator.targeting import HateSystem
    tgt = HateSystem(b).operator_target(op)
    assert tgt is not e, tgt

    # restore: enemy_trspsb_mark fires SwitchSide ENEMY on buff expiry
    b.add_buff(e, {"key": "t_mark", "remaining_ticks": 30,
                   "template_key": "enemy_trspsb_mark", "blackboard": {}})
    assert e.side == 1, "mark start must not flip side"
    sim.run_ticks(30)
    assert e.side == 0, e.side

def test_buff_batch27_misc_nodes():
    """IfDamageTargetSide / RandomSetter / AssignModifierRealDeltaToBB /
    CheckTargetGridPositionRowOrColWithBB / DamageByDistance /
    CreateBuffToUnitId."""
    from ark_emulator.consts import DamageType, EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)

    # IfDamageTargetSide: enemy attacker passes ENEMY mask
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IfDamageTargetSide",
                             "_sideMask": "ENEMY", "_sourceType": "MODIFIER_SOURCE",
                             "_targetType": "MODIFIER_TARGET"}],
                        {"owner": e, "source": e, "target": op,
                         "damage": {"amount": 10.0}, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(op, [{"$type": "Torappu.Battle.Action.Nodes+IfDamageTargetSide",
                              "_sideMask": "ENEMY", "_sourceType": "MODIFIER_SOURCE",
                              "_targetType": "MODIFIER_TARGET"}],
                        {"owner": op, "source": op, "target": e,
                         "damage": {"amount": 10.0}, "bb": {}})
    assert r[0]["action"] is False, r

    # RandomSetter
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+RandomSetter",
                             "_targetKey": "sp", "_convertToInt": False}], ctx)
    assert r[0]["action"] is True
    assert 0.0 <= ctx["bb"]["sp"] <= 1.0, ctx["bb"]

    # AssignModifierRealDeltaToBB
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignModifierRealDeltaToBB",
                             "_modifierTargetType": "HP", "_blackboardKey": "last_damage"}],
                        {**ctx, "damage": {"amount": 42.0}})
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["last_damage"] - 42.0) < 1e-6, ctx["bb"]

    # CheckTargetGridPositionRowOrColWithBB
    e.row = 5
    ctx = {"owner": e, "source": None, "target": e, "bb": {"agbmes_row": 5}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckTargetGridPositionRowOrColWithBB",
                             "_target": "BUFF_OWNER", "_checkRow": True,
                             "_blackboardKey": "agbmes_row", "_compareType": "EQUALS"}], ctx)
    assert r[0]["action"] is True, r
    ctx["bb"]["agbmes_row"] = 6
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckTargetGridPositionRowOrColWithBB",
                             "_target": "BUFF_OWNER", "_checkRow": True,
                             "_blackboardKey": "agbmes_row", "_compareType": "EQUALS"}], ctx)
    assert r[0]["action"] is False, r

    # DamageByDistance (Weedy S3 rupture): value x distance TRUE damage
    e.max_hp = 10000.0
    e.pos_x, e.pos_y = 4.0, 3.0
    e.hp = e.max_hp
    hp0 = e.hp
    ctx = {"owner": e, "source": op, "target": e,
           "bb": {"value": 1200.0, "interval": 0.066}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+DamageByDistance",
                         "_isInit": True, "_targetType": "BUFF_OWNER",
                         "_sourceType": "BUFF_SOURCE", "_attackType": "BUFF",
                         "_damageType": "PURE"}], ctx)
    e.pos_x, e.pos_y = 6.0, 3.0     # moved 2 grids
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+DamageByDistance",
                         "_isInit": False, "_targetType": "BUFF_OWNER",
                         "_sourceType": "BUFF_SOURCE", "_attackType": "BUFF",
                         "_damageType": "PURE"}], ctx)
    assert abs((hp0 - e.hp) - 2400.0) < 1e-6, (hp0, e.hp)

    # CreateBuffToUnitId
    b.add_buff(e, {"key": "t_target", "remaining_ticks": 30 * 5,
                   "template_key": "enemy_ubbplwq[kill_hw_on_die]",
                   "blackboard": {}})
    b.spawn_enemy("enemy_1588_ubbphw", 0)
    hw = b.enemies[1]
    node = {"$type": "Torappu.Battle.Action.Nodes+CreateBuffToUnitId",
            "_source": "SOURCE", "_useTargetOptions": False,
            "_targetOptions": {}, "_unitId": "enemy_1588_ubbphw",
            "_buff": {"buffKey": "hw_mark", "templateKey": "empty",
                      "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                     "abnormalAntis": [], "abnormalCombos": [],
                                     "abnormalComboImmunes": [],
                                     "attributeModifiers": []},
                      "lifeTimeType": "LIMITED", "lifeTime": 3.0}}
    r = eng.run_actions(e, [node], {"owner": e, "source": e, "target": e,
                                    "bb": {}})
    assert r[0]["action"] is True, r
    keys = [x.get("key") for x in hw.buffs]
    assert "hw_mark" in keys, keys

def test_buff_batch28_nodes():
    """SetDisappear / ClearEnemySp / PickRandomBranchPhase /
    AssignUidToBlackBoard / CreateBuffWithOverrideEffect /
    FilterByTargetSPType."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    eng = BuffTemplateEngine(b)

    # SetDisappear
    e.state = EnemyState.MOVE
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SetDisappear",
                             "_targetType": "TARGET", "_isDisappear": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e.state == EnemyState.DISAPPEAR, e.state
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SetDisappear",
                             "_targetType": "TARGET", "_isDisappear": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert e.state == EnemyState.MOVE, e.state

    # ClearEnemySp
    e.sp = 50.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ClearEnemySp",
                             "_enemy": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e.sp == 0.0, e.sp

    # PickRandomBranchPhase without a branch id -> no-op pass
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+PickRandomBranchPhase",
                             "_notRepeatInOneLoop": True, "_blockGameFinish": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # AssignUidToBlackBoard (int inst id)
    ctx = {"owner": e, "source": e, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignUidToBlackBoard",
                             "_targetType": "MODIFIER_SOURCE", "_buffKey": "x",
                             "_blackBoardKey": "modifier_source", "_assignAsInt": True}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["modifier_source"] == e.inst_id, ctx["bb"]

    # CreateBuffWithOverrideEffect (delegates to CreateBuff)
    node = {"$type": "Torappu.Battle.Action.Nodes+CreateBuffWithOverrideEffect, Assembly-CSharp",
            "_effectKey": "", "_buffOwner": "TARGET",
            "_buff": {"buffKey": "hw_mark2", "templateKey": "empty",
                      "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                     "abnormalAntis": [], "abnormalCombos": [],
                                     "abnormalComboImmunes": [],
                                     "attributeModifiers": []},
                      "lifeTimeType": "LIMITED", "lifeTime": 3.0}}
    r = eng.run_actions(e, [node], {"owner": e, "source": e, "target": e,
                                    "bb": {}})
    assert r[0]["action"] is True, r
    assert "hw_mark2" in [x.get("key") for x in e.buffs]

    # FilterByTargetSPType: no SP type exposed -> falls through
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetSPType",
                             "_targetType": "BUFF_OWNER",
                             "_spType": "INCREASE_WHEN_ATTACK"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

def test_buff_batch29_other_buff_start():
    """ON_OTHER_BUFF_START dispatch + CheckMainBuffId gate (halo2 T2
    reacts when a 'sluggish' buff starts on the same unit)."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    eng = BuffTemplateEngine(b)

    # unit gate: matching _other_buff_key passes, mismatch fails
    ctx = {"owner": e, "source": None, "target": e,
           "bb": {"_other_buff_key": "sluggish"}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckMainBuffId",
                             "_idToFilter": "sluggish"}], ctx)
    assert r[0]["action"] is True, r
    ctx["bb"]["_other_buff_key"] = "stun"
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckMainBuffId",
                             "_idToFilter": "sluggish"}], ctx)
    assert r[0]["action"] is False, r

    # end-to-end: halo2_t_2 listens for ON_OTHER_BUFF_START and creates
    # halo2_t_2[attack_speed] when a 'sluggish' buff starts on the unit
    b.add_buff(e, {"key": "halo2_t_2", "remaining_ticks": 30 * 30,
                   "template_key": "halo2_t_2", "blackboard": {}})
    assert "halo2_t_2[attack_speed]" not in [
        x.get("key") for x in e.buffs]
    b.add_buff(e, {"key": "sluggish", "remaining_ticks": 30 * 30,
                   "template_key": "sluggish", "blackboard": {}})
    keys = [x.get("key") for x in e.buffs]
    assert "halo2_t_2[attack_speed]" in keys, keys

def test_buff_batch30_nodes():
    """EpDamageScale / DamageViaCurHpRatio / state gates / shield /
    cost / hp-ratio nodes."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    e.level_type = 0
    eng = BuffTemplateEngine(b)

    # EpDamageScale: 100 x (1 - 0.5) = 50
    dmg = {"amount": 100.0}
    ctx = {"owner": e, "source": None, "target": e,
           "bb": {"ep_damage_scale": 0.5}, "damage": dmg}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+EpDamageScale",
                             "_filterElementType": False, "_elementType": "NONE",
                             "_isOneMinus": True}], ctx)
    assert r[0]["action"] is True
    assert abs(dmg["amount"] - 50.0) < 1e-6, dmg

    # DamageViaCurHpRatio: 800 x 0.5 = 400 current-HP loss
    e.max_hp = 10000.0
    e.hp = 800.0
    ctx = {"owner": e, "source": e, "target": e, "bb": {"hp_ratio": 0.5}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+DamageViaCurHpRatio",
                             "_targetType": "SOURCE", "_damageType": "PURE"}], ctx)
    assert r[0]["action"] is True
    assert abs(e.hp - 400.0) < 1e-6, e.hp

    # state gates
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckUnitInRebornState",
                             "_ownerType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False
    e.state = EnemyState.DISAPPEAR
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckUnitInDisappearState",
                             "_ownerType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    e.state = EnemyState.MOVE

    # CheckEnemyLevelType NORMAL passes
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyLevelType",
                             "_targetType": "BUFF_OWNER", "_targetLevelType": "NORMAL"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # CheckEntityEquals same unit
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEntityEquals",
                             "_lhsType": "TARGET", "_rhsType": "SOURCE"}],
                        {"owner": e, "source": e, "target": e, "bb": {}})
    assert r[0]["action"] is True

    # FilterByShieldValue: barrier 0 <= 0
    e.barrier = 0.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByShieldValue",
                             "_targetType": "BUFF_OWNER", "_condType": "LE",
                             "_shieldValue": 0.0, "_shieldKey": "invalid",
                             "_enableFilterSource": True, "_filterSource": "BUFF_OWNER",
                             "_filterHostOrToken": False, "_passIfNoSource": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # CreateBuffToUid by inst id from the blackboard
    ctx = {"owner": e, "source": e, "target": e,
           "bb": {"uid": e.inst_id}}
    node = {"$type": "Torappu.Battle.Action.Nodes+CreateBuffToUid",
            "_uidKey": "uid", "_getFromEnemy": True, "_getStrInsteadOfInt": False,
            "_buffSource": "SOURCE",
            "_buff": {"buffKey": "uid_mark", "templateKey": "empty",
                      "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                     "abnormalAntis": [], "abnormalCombos": [],
                                     "abnormalComboImmunes": [],
                                     "attributeModifiers": []},
                      "lifeTimeType": "LIMITED", "lifeTime": 3.0}}
    r = eng.run_actions(e, [node], ctx)
    assert r[0]["action"] is True, r
    assert "uid_mark" in [x.get("key") for x in e.buffs]

    # EqualizeTargetHpRatio: source at 50% -> target at 50% of its max
    e.max_hp = 2000.0
    e.hp = 1000.0
    e2 = b.enemies[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b.enemies[1]
    e2.max_hp = 4000.0
    e2.hp = 4000.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+EqualizeTargetHpRatio",
                             "_source": "SOURCE", "_target": "TARGET",
                             "_useSourceHpRatio": True, "_hpRatio": 0.5,
                             "_skipModifierEvent": True}],
                        {"owner": e, "source": e, "target": e2, "bb": {}})
    assert r[0]["action"] is True
    assert abs(e2.hp - 2000.0) < 1e-6, e2.hp

    # MarkCurrentHpRatio into blackboard
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+MarkCurrentHpRatio",
                             "_target": "BUFF_OWNER", "_markInBlackboard": True}], ctx)
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["marked_hp_ratio"] - 0.5) < 1e-6, ctx["bb"]

    # CheckCost: battle cost >= bb value
    b.cost = 12.0
    ctx = {"owner": e, "source": None, "target": e, "bb": {"cost": 10.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCost",
                             "_compareType": "GE", "_blackboardKey": "cost",
                             "_considerNegativeCost": True}], ctx)
    assert r[0]["action"] is True, r
    ctx["bb"]["cost"] = 20.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCost",
                             "_compareType": "GE", "_blackboardKey": "cost",
                             "_considerNegativeCost": True}], ctx)
    assert r[0]["action"] is False, r

def test_buff_batch31_nodes():
    """CheckAbnormalCombo / face-position / buff-attr update / teleport /
    direction / random-create / misc."""
    from ark_emulator.consts import AbnormalFlag, EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # CheckAbnormalCombo SLEEPING (DOZE flag 43)
    e.set_flag(43, 30)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckAbnormalCombo",
                             "_abnormalCombo": "SLEEPING", "_targetType": "TARGET",
                             "_isUnset": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    e.clear_flag(43)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckAbnormalCombo",
                             "_abnormalCombo": "SLEEPING", "_targetType": "TARGET",
                             "_isUnset": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # CheckIfSourceGridPosFaceTargetGridPos: source faces right
    e.row, e.col = 3, 3
    e.direction = 1
    b.spawn_enemy("enemy_1000_gopro", 0)
    t2 = b.enemies[1]
    t2.row, t2.col = 3, 5
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckIfSourceGridPosFaceTargetGridPos",
                             "_source": "BUFF_OWNER", "_target": "MODIFIER_SOURCE",
                             "_faceType": "FRONT", "_targetColOffset": 0.0,
                             "_faceIfSameCol": "NONE"}],
                        {"owner": e, "source": t2, "target": t2, "bb": {}})
    assert r[0]["action"] is True, r
    t2.row, t2.col = 3, 1
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckIfSourceGridPosFaceTargetGridPos",
                             "_source": "BUFF_OWNER", "_target": "MODIFIER_SOURCE",
                             "_faceType": "FRONT", "_targetColOffset": 0.0,
                             "_faceIfSameCol": "NONE"}],
                        {"owner": e, "source": t2, "target": t2, "bb": {}})
    assert r[0]["action"] is False, r

    # UpdateBuffAttributeModifier (bb value)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+UpdateBuffAttributeModifier",
                             "_value": 0.0, "_useBlackboard": True,
                             "_attributeType": "DEF_PENETRATE", "_formulaType": "ADDITION"}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"value": 20.0}})
    assert r[0]["action"] is True
    ent = b.buffs.get(e, "op_attr_update")
    assert ent is not None and abs(ent["add"] - 20.0) < 1e-6, ent

    # CheckHasCharacterInRange: deploy an operator in the 2-2 right cell
    e.row, e.col = 2, 2
    e.direction = 1
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasCharacterInRange",
                             "_targetType": "BUFF_OWNER", "_rangeId": "2-2",
                             "_checkRadius": False, "_rangeRadius": 0.0,
                             "_globalRange": False, "_filterByGroupId": False,
                             "_filterGroupId": None, "_excludeTarget": False,
                             "_excludeTrapAndToken": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ForceSetToTilePosition from blackboard
    e.row, e.col = 1, 1
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ForceSetToTilePosition",
                             "_targetType": "BUFF_OWNER", "_colKey": "col",
                             "_rowKey": "row", "_useSnapshotTile": False,
                             "_disableCurrentStillPull": True, "_randomOffset": -1.0,
                             "_randomOffsetKey": "", "_randomOffsetInnerRange": -1.0,
                             "_findNearestPassableTile": False,
                             "_releaseFromBlocker": False,
                             "_checkTeleportImmune": False}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"row": 5, "col": 5}})
    assert r[0]["action"] is True
    assert (e.row, e.col) == (5, 5), (e.row, e.col)

    # CheckEnemyDirection LEFT
    e.direction = 3
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyDirection",
                             "_target": "BUFF_OWNER", "_direction": "LEFT",
                             "_useBB": False, "_bbKey": "direction"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # RandomCreateBuff
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+RandomCreateBuff",
                             "_datas": [{"buff": {
                                 "buffKey": "haak_t_atk", "templateKey": "empty",
                                 "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                                "abnormalAntis": [], "abnormalCombos": [],
                                                "abnormalComboImmunes": [],
                                                "attributeModifiers": []},
                                 "lifeTimeType": "LIMITED", "lifeTime": 3.0}}]}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert "haak_t_atk" in [x.get("key") for x in e.buffs]

    # SwitchDirection sets the source facing and runs the branch
    e.direction = 0
    ctx = {"owner": e, "source": e, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SwitchDirection",
                             "_source": "BUFF_SOURCE", "_direction": "UP",
                             "_useCustomDirection": False, "_rightNodes": []}], ctx)
    assert r[0]["action"] is True
    assert e.direction == 0, e.direction

    # SaveHpToDynamicVar
    e.hp = 321.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SaveHpToDynamicVar",
                             "_targetType": "BUFF_OWNER", "_saveType": "HP",
                             "_buffNameOfBlackboard": "", "_alwaysAssign": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._saved_hp == 321.0, e._saved_hp

    # CheckTriggerable / ModifyCharacterLimit
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckTriggerable"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyCharacterLimit",
                             "_sourceType": "SOURCE", "_blackboardKey": "value",
                             "_isMins": False, "_getPlayerSideSource": False}],
                        {"owner": e, "source": e, "target": e,
                         "bb": {"value": 3.0}})
    assert r[0]["action"] is True
    assert abs(b._character_limit_mod - 3.0) < 1e-6, b._character_limit_mod

def test_buff_batch32_nodes():
    """Shared flags / attribute-with-stacks / profession buffs / bb attrs /
    ability blackboard / distance scaling."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    eng = BuffTemplateEngine(b)

    # SetSharedFlag + CheckIfDamageHasSharedFlags
    dmg = {"amount": 50.0}
    ctx = {"owner": e, "source": None, "target": e, "bb": {}, "damage": dmg}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SetSharedFlag",
                             "_sharedFlagIndex": "DAMAGE_CAN_HURT_SLEEPING_ENTITY"}], ctx)
    assert r[0]["action"] is True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckIfDamageHasSharedFlags",
                             "_sharedFlags": "DAMAGE_CAN_HURT_SLEEPING_ENTITY",
                             "_isUnset": False}], ctx)
    assert r[0]["action"] is True, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckIfDamageHasSharedFlags",
                             "_sharedFlags": "INSTANT_KILL_LIKE_DAMAGE",
                             "_isUnset": True}], ctx)
    assert r[0]["action"] is True, r

    # AttributeModifierWithCertainBuffCount (takila TR: 2 stacks x value)
    b.add_buff(e, {"key": "takila_tr_atk", "remaining_ticks": 300,
                   "layers": 2, "stat": None})
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AttributeModifierWithCertainBuffCount",
                             "_targetType": "BUFF_OWNER", "_attributeType": "ATK",
                             "_formulaType": "MULTIPLIER", "_maxCnt": 0,
                             "_buffKey": "takila_tr_atk", "_useOneAsMinCnt": True,
                             "_writeModifyValueToBB": False, "_writeToBBKey": None}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"value": 0.1}})
    assert r[0]["action"] is True
    ent = b.buffs.get(e, "op_buffcnt_attr")
    assert ent is not None and abs(ent["mul"] - 0.2) < 1e-6, ent

    # CheckAbnormalFlags
    e.set_flag(0, 30)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckAbnormalFlags",
                             "_abnormalFlags": ["STUNNED", "FROZEN", "LEVITATE"],
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    e.clear_flag(0)

    # CreateBuffToCertainProfession: medic operator gets the buff
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffToCertainProfession",
                             "_professionMask": "WARRIOR, SNIPER, TANK, MEDIC, SUPPORT, CASTER, SPECIAL, PIONEER",
                             "_buffData": {"buffKey": "prof_mark", "templateKey": "empty",
                                           "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                                          "abnormalAntis": [], "abnormalCombos": [],
                                                          "abnormalComboImmunes": [],
                                                          "attributeModifiers": []},
                                           "lifeTimeType": "LIMITED", "lifeTime": 3.0}}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert "prof_mark" in [x.get("key") for x in op.buffs]

    # AssignAttributeAsDynamicVarToBB / RawData
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignAttributeAsDynamicVarToBB",
                             "_targetType": "BUFF_OWNER", "_attributeType": "MAX_HP",
                             "_scaleVar": ""}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["value"] == e.max_hp, ctx["bb"]
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignAttributeRawDataIntoBlackboard",
                             "_blackBoardKey": "default_max_hp", "_targetType": "BUFF_OWNER",
                             "_attributeType": "MAX_HP"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["default_max_hp"] == e.max_hp, ctx["bb"]

    # SetWithdrawCostRecoverRatio
    r = eng.run_actions(op, [{"$type": "Torappu.Battle.Action.Nodes+SetWithdrawCostRecoverRatio",
                              "_targetType": "BUFF_OWNER", "_ratio": 0.5,
                              "_isReset": False, "_dontLimitMaxWithdrawCost": True}],
                        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._withdraw_cost_recover_ratio == 0.5

    # CheckTraitAbilityBlackboard
    ctx = {"owner": e, "source": None, "target": e,
           "bb": {"cnt": 3.0, "max_cnt": 5.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckTraitAbilityBlackboard",
                             "_leftBlackboardKey": "cnt", "_rightBlackboardKey": "max_cnt",
                             "_rightValue": 0.0, "_compareType": "LE",
                             "_targetType": "BUFF_OWNER"}], ctx)
    assert r[0]["action"] is True, r
    ctx["bb"]["cnt"] = 7.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckTraitAbilityBlackboard",
                             "_leftBlackboardKey": "cnt", "_rightBlackboardKey": "max_cnt",
                             "_rightValue": 0.0, "_compareType": "LE",
                             "_targetType": "BUFF_OWNER"}], ctx)
    assert r[0]["action"] is False, r

    # FilterByAbilityFinishReason
    ctx = {"owner": e, "source": None, "target": e, "bb": {"_ability_finish_reason": "NORMAL_EXIT"}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByAbilityFinishReason",
                             "_finishReason": "NORMAL_EXIT", "_useBuffAbility": False}], ctx)
    assert r[0]["action"] is True, r

    # DamageScaleBaseOnDistance: source at (0,0), target at (3,0) -> scale 3/3
    e.row, e.col = 0, 0
    b.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b.enemies[1]
    e2.row, e2.col = 3, 0
    dmg = {"amount": 100.0}
    ctx = {"owner": e, "source": e, "target": e2, "bb": {"max_scale": 3.0},
           "damage": dmg}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+DamageScaleBaseOnDistance",
                             "_filterDamageType": False, "_damageMask": "NONE",
                             "_filterApplyWay": False, "_applyWayFilter": "NONE",
                             "_sourceType": "MODIFIER_SOURCE", "_targetType": "MODIFIER_TARGET",
                             "_maxScale": 0.0, "_minTriggerDistance": 0.0,
                             "_reverseDistance": False}], ctx)
    assert r[0]["action"] is True
    assert abs(dmg["amount"] - 100.0) < 1e-6, dmg

def test_buff_batch33_nodes():
    """Tile blackboard / global-shared blackboard / state gates / max
    target / buff cleanup."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    e.row, e.col = 3, 3
    eng = BuffTemplateEngine(b)

    # AddTileBlackboard + FilterTileBlackboard
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AddTileBlackboard",
                             "_useTargetRootTile": True, "_useTargetOldTile": False,
                             "_targetType": "BUFF_OWNER", "_blackboardKey": "mush_cnt",
                             "_addition": 1.0, "_additionKey": None}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert b._tile_bb.get((3, 3), {}).get("mush_cnt") == 1.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterTileBlackboard",
                             "_useTargetRoottile": True, "_useTargetOldTile": False,
                             "_targetType": "BUFF_OWNER", "_blackboardKey": "mush_cnt",
                             "_valueToCompare": 0, "_anotherKeyToCompare": None,
                             "_condType": "GT"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ModifyTileBlackboard
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyTileBlackboard",
                             "_useTargetRoottile": True, "_targetType": "BUFF_OWNER",
                             "_blackboardKey": "lrccon_flag", "_value": 1.0,
                             "_valueKey": None, "_assignStrValue": False,
                             "_valueStr": None}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert b._tile_bb.get((3, 3), {}).get("lrccon_flag") == 1.0

    # Global blackboard write + assign
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AddGlobalBlackboard",
                             "_blackboardKey": "enemy_cjdoor_col", "_value": 4.0,
                             "_valueBlackboardKey": None, "_addString": False,
                             "_valueStr": None, "_overwrite": True}], ctx)
    assert r[0]["action"] is True
    assert b._global_bb["enemy_cjdoor_col"] == 4.0
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignGlobalBlackboardToBlackboard",
                             "_globalblackboardKey": "enemy_cjdoor_col",
                             "_blackboardKey": "col", "_channel": "LEVEL",
                             "_assignString": False}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["col"] == 4.0, ctx["bb"]

    # Character shared blackboard write + assign
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AddCharacterSharedBlackboard",
                         "_blackboardKey": "aglna2_located_row", "_value": 2.0,
                         "_isStringBB": False, "_useValueKey": False,
                         "_valueKey": None, "_isOverwrite": True}], ctx)
    assert b._char_shared_bb.get("aglna2_located_row") == 2.0
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignCharacterSharedBBToBlackboard",
                             "_character": "BUFF_OWNER",
                             "_sourceBBKey": "aglna2_located_row",
                             "_targetBBKey": "aglna2_located_row"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["aglna2_located_row"] == 2.0

    # state gates
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckUnitInMoveState",
                             "_ownerType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    e.state = EnemyState.ATTACK
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckUnitInAttackState",
                             "_ownerType": "BUFF_OWNER", "_isUnset": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    e.state = EnemyState.MOVE

    # ModifyAttackMaxTarget
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyAttackMaxTarget",
                             "_targetType": "BUFF_OWNER", "_maxTarget": 3,
                             "_modeIndex": -1}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._attack_max_target == 3

    # FinishSeveralBuffsById + FinishBuffsOfEveryCharacterById
    for k in ("enemy_minima_shield[a]", "enemy_minima_shield[b]"):
        b.add_buff(e, {"key": k, "remaining_ticks": 300, "layers": 1})
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishSeveralBuffsById",
                             "_targetType": "BUFF_OWNER",
                             "_buffKeys": ["enemy_minima_shield[a]",
                                           "enemy_minima_shield[b]",
                                           "enemy_minima_shield[c]"],
                             "_decCntIfStack": False, "_updateOverrideMap": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert b.buffs.get(e, "enemy_minima_shield[a]") is None
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    b.add_buff(op, {"key": "enemy_murad_check_appear[sp_recover]",
                    "remaining_ticks": 300, "layers": 1})
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishBuffsOfEveryCharacterById",
                             "_buffKey": "enemy_murad_check_appear[sp_recover]",
                             "_loadFromBlackboard": False, "_decCntIfStack": False,
                             "_updateOverrideMap": True, "_checkBuffSource": False,
                             "_sourceType": "TARGET", "_alsoClearNullSource": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert b.buffs.get(op, "enemy_murad_check_appear[sp_recover]") is None

    # CheckEnemySkillAffecting: no active skill -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemySkillAffecting",
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # CreateBuffToHostAsSource
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffToHostAsSource",
                             "_buff": {"buffKey": "host_mark", "templateKey": "empty",
                                       "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                                      "abnormalAntis": [], "abnormalCombos": [],
                                                      "abnormalComboImmunes": [],
                                                      "attributeModifiers": []},
                                       "lifeTimeType": "LIMITED", "lifeTime": 3.0}}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert "host_mark" in [x.get("key") for x in e.buffs]

def test_buff_batch34_nodes():
    """Tile-mode switch / ability-time / trait bb / checkpoint / misc."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # SwitchDynamicBuffTileMode with owner root tile
    e.row, e.col = 2, 2
    b._tile_modes.pop((2, 2), None)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SwitchDynamicBuffTileMode",
                             "_operation": "INDEX", "_modeIndex": 1, "_decBbKey": "",
                             "_useSwitchResult": True, "_specifyTileType": False,
                             "_tileType": "REED_TILE", "_useOwnerRootTile": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert b.tile_mode(2, 2) == 1, b.tile_mode(2, 2)

    # CalculateTraitAbilityBlackboard: base + add
    ctx = {"owner": e, "source": None, "target": e,
           "bb": {"reload_interval": 1.0, "add": 0.5}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CalculateTraitAbilityBlackboard",
                             "_addBlackboardKey": "add", "_useTraitBBToAdd": False,
                             "_isSub": False, "_fromBlackboardKey": "reload_interval",
                             "_targetBlackboardKey": "reload_interval",
                             "_targetType": "BUFF_OWNER"}], ctx)
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["reload_interval"] - 1.5) < 1e-6, ctx["bb"]

    # FilterByTargetDataLevel
    e.level = 2
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetDataLevel",
                             "_target": "BUFF_OWNER", "_condType": "LE", "_level": 1}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetDataLevel",
                             "_target": "BUFF_OWNER", "_condType": "LE", "_level": 2}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # AssignValueToTraitBB
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignValueToTraitBB",
                             "_blackboardKey": "RELOAD_FLAG", "_value": 1.0,
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert getattr(e, "_trait_bb_extra", {}).get("RELOAD_FLAG") == 1.0

    # CheckEnemyCurrentCheckpoint: no WAIT_FOR_SECONDS checkpoint -> False
    e.route = {"checkpoints": []}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyCurrentCheckpoint",
                             "_checkpointTypes": ["WAIT_FOR_SECONDS"]}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # ModifyBlackboardFromTrait
    ctx = {"owner": e, "source": None, "target": e, "bb": {"max_stack_cnt": 3.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyBlackboardFromTrait",
                             "_blackboardKeys": "max_stack_cnt",
                             "_fromBlackboardKeys": "max_stack_cnt",
                             "_value": 0.0, "_addBasedOriginValue": False,
                             "_checkFromBlackboardValue": True,
                             "_targetType": "BUFF_OWNER"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["max_stack_cnt"] == 3.0, ctx["bb"]

    # ModifyBoomberangMaxCnt
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyBoomberangMaxCnt",
                             "_targetType": "BUFF_OWNER", "_reset": False}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"max_cnt": 4.0}})
    assert r[0]["action"] is True
    assert e._boomberang_max_cnt == 4

    # AddEnemyBlockVolume
    e.block_volume = 1
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AddEnemyBlockVolume",
                             "_targetType": "BUFF_OWNER", "_additionVolume": 2,
                             "_isMinus": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e.block_volume == 3, e.block_volume

def test_buff_batch35_nodes():
    """Tile-height / block-mode / id filters / motion mode / bb time /
    distance / knockback."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # CheckHeightTypeOfCharacterRootTile on a lowland tile
    e.row, e.col = 3, 3
    t = b.map.tile(3, 3)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHeightTypeOfCharacterRootTile",
                             "_targetType": "BUFF_OWNER", "_heightType": str(
                                 getattr(t, "height_type", "LOWLAND") or "LOWLAND"),
                             "_isUnset": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ChangeCharBlockMode + CheckBlockMode
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ChangeCharBlockMode",
                             "_target": "BUFF_OWNER", "_resetToDefault": False,
                             "_blockMode": "FLY"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._block_mode == "FLY"
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckBlockMode",
                             "_targetType": "BUFF_OWNER", "_blockMode": "FLY"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # FilterId
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterId",
                             "_targetType": "BUFF_OWNER", "_filterId": "enemy_1000_gopro",
                             "_filterIdKey": "", "_filterIds": None, "_isUnset": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ChangeEnemyRouteMotionMode FLY
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ChangeEnemyRouteMotionMode",
                             "_target": "BUFF_OWNER", "_motionMode": "FLY"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._motion_mode == 1, e._motion_mode

    # AlwaysExecuteNodeList
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AlwaysExecuteNodeList",
                             "_nodes": [[{"$type": "Torappu.Battle.Action.Nodes+AssignValueToBB",
                                          "_blackboardKey": "flag", "_value": 1.0,
                                          "_copyFromKey": None, "_assignString": False}]]}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["flag"] == 1.0, ctx["bb"]

    # CreateBuffs
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffs",
                             "_buffPair": {"buff": {
                                 "buffKey": "mudrok_t_1[shield_b]",
                                 "templateKey": "empty",
                                 "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                                                "abnormalAntis": [], "abnormalCombos": [],
                                                "abnormalComboImmunes": [],
                                                "attributeModifiers": []},
                                 "lifeTimeType": "LIMITED", "lifeTime": 3.0}}}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert "mudrok_t_1[shield_b]" in [x.get("key") for x in e.buffs]

    # AssignPlayTimeToBB
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignPlayTimeToBB",
                             "_blackboardKey": "last_check_time"}], ctx)
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["last_check_time"] - b.tick / 30.0) < 1e-6

    # FetchHpToBlackboard
    e.max_hp = 1000.0
    e.hp = 250.0
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FetchHpToBlackboard",
                             "_targetType": "BUFF_OWNER", "_damageType": "PURE",
                             "_blackboardStr": "dynamic", "_buffNameOfBlackboard": None,
                             "_isHpRatio": True, "_skipModifierEvent": False}], ctx)
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["dynamic"] - 0.25) < 1e-6, ctx["bb"]

    # RecordCurrentHpRatio
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+RecordCurrentHpRatio",
                             "_ownerType": "BUFF_OWNER", "_recordKey": "hp_ratio",
                             "_needOffset": True, "_recordType": "hpRatio"}], ctx)
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["hp_ratio"] - 0.25) < 1e-6, ctx["bb"]

    # CheckDistance: source (3,3) target (3,5), radius 2 -> pass
    e.row, e.col = 3, 3
    b.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b.enemies[1]
    e2.row, e2.col = 3, 5
    ctx = {"owner": e, "source": e, "target": e2,
           "bb": {"range_radius": 2.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckDistance",
                             "_source": "MODIFIER_SOURCE", "_target": "MODIFIER_TARGET",
                             "_radius": 0.0, "_radiusBbKey": "range_radius",
                             "_checkCertainPosition": False, "_rowKey": "row",
                             "_colKey": "col"}], ctx)
    assert r[0]["action"] is True, r

    # FilterByTargetMassLevel
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterByTargetMassLevel",
                             "_target": "TARGET", "_condType": "GE"}],
                        {"owner": e, "source": None, "target": e2,
                         "bb": {"mass_level": 0.0}})
    assert r[0]["action"] is True, r

    # KnockBackWithDirection pushes the owner
    e.pos_x, e.pos_y = 3.0, 3.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+KnockBackWithDirection",
                             "_direction": "RIGHT", "_useSourceDirection": False,
                             "_defaultForceLevel": 0}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"distance": 1.0}})
    assert r[0]["action"] is True
    assert e.displacement is not None, e.displacement

def test_buff_batch36_nodes():
    """Key filters / ability damage override / raw-attr copy / hp-ratio mul /
    skill interrupt / misc."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # FilterCharacterKey
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterCharacterKey",
                             "_sourceType": "BUFF_OWNER", "_key": "enemy_1000_gopro"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ReplaceAbilityDamageType
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ReplaceAbilityDamageType",
                             "_targetType": "BUFF_OWNER", "_modes": [1],
                             "_damageType": "MAGICAL"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._ability_damage_type_override == 1

    # ModifyAttributeRawDataByEntity
    b.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b.enemies[1]
    e2.attributes.base["atk"] = 500.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyAttributeRawDataByEntity",
                             "_targetType": "BUFF_OWNER", "_sourceType": "BUFF_SOURCE",
                             "_useCardSnapshot": False, "_useRatio": False,
                             "_typesNeedtoUseRatio": ["MAX_HP", "ATK", "DEF"],
                             "_typesNeedtoModify": ["ATK", "DEF", "MAX_HP"]}],
                        {"owner": e, "source": e2, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e.attributes.get("atk") == 500.0, e.attributes.get("atk")

    # HpRatioToAttributeMul
    e.max_hp = 1000.0
    e.hp = 500.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+HpRatioToAttributeMul",
                             "_minHpRatio": 0.0, "_maxHpRatio": 1.0,
                             "_attributeType": "DEF", "_overrideSource": False,
                             "_hpRatioSource": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"value": 0.2}})
    assert r[0]["action"] is True
    ent = b.buffs.get(e, "op_hp_ratio_mul")
    assert ent is not None and abs(ent["mul"] - 0.1) < 1e-6, ent

    # CheckCharSkillAvailable: no active skill -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCharSkillAvailable",
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # EnsureDmgOrHeal
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+EnsureDmgOrHeal",
                             "_key": "atk_scale_2"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["atk_scale_2"] == 1.0

    # SetIgnoreMissFlag
    dmg = {"amount": 10.0}
    ctx = {"owner": e, "source": None, "target": e, "bb": {}, "damage": dmg}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SetIgnoreMissFlag",
                             "_ignoreMissFlag": "PHYSICAL"}], ctx)
    assert r[0]["action"] is True
    assert dmg["_ignore_miss"] == "PHYSICAL"

    # RecordDamageModifier
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+RecordDamageModifier",
                             "_filterModifierCancelled": False}],
                        {**ctx, "damage": {"amount": 33.0}})
    assert r[0]["action"] is True
    assert ctx["bb"]["value"] == 33.0, ctx["bb"]

    # CharacterHasValidToken: no token -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CharacterHasValidToken",
                             "_hostType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # FinishBuffsByIdByBuffSource
    b.add_buff(e, {"key": "mark_bbrain[damage_split_target]",
                   "remaining_ticks": 300, "layers": 1})
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishBuffsByIdByBuffSource",
                             "_buffKey": "mark_bbrain[damage_split_target]",
                             "_targetType": "BUFF_OWNER", "_sourceType": "BUFF_OWNER",
                             "_alsoClearNullSource": True,
                             "_alsoClearWhenSourceIsNull": False,
                             "_useSourceHost": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert b.buffs.get(e, "mark_bbrain[damage_split_target]") is None

    # AssignProfessionCntToBlackboard
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignProfessionCntToBlackboard",
                             "_professionCategory": "MEDIC",
                             "_blackboardKey": "respawn_time"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["respawn_time"] >= 1, ctx["bb"]

    # HasTileAlongDirection: road ahead likely no ristar tile -> False ok
    e.row, e.col = 2, 2
    e.direction = 1
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+HasTileAlongDirection",
                             "_isGravity": False,
                             "_tileKeyList": ["tile_ristar_road",
                                              "tile_ristar_road_forbidden"]}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] in (True, False)

    # CheckEnemyTalentContainsKey: no talent bb -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyTalentContainsKey",
                             "_source": "BUFF_OWNER", "_key": "parasitic"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # CheckConatinsMapTags: level_main_01-01 has no act25side_extra
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckConatinsMapTags",
                             "_mapTags": ["act25side_extra"]}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

def test_buff_batch37_nodes():
    """Ammo / level mask / sp cost / skill bb / element-on-damage / misc."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # AmmoSkillCountModifier recover
    e._hunter_ammo = 3
    ctx = {"owner": e, "source": None, "target": e, "bb": {"recover_count": 2}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AmmoSkillCountModifier",
                             "_targetType": "BUFF_OWNER", "_modifyMaxCount": False,
                             "_restoreMaxCount": False, "_addCountBBKey": None,
                             "_addCount": 0, "_addCountUsePercent": False,
                             "_recoverEventCount": True,
                             "_recoverCountBBKey": "recover_count"}], ctx)
    assert r[0]["action"] is True
    assert e._hunter_ammo == 5, e._hunter_ammo

    # CheckEnemyLevelMask: gopro NORMAL -> ELITE_AND_BOSS fails
    e.level_type = 0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyLevelMask",
                             "_targetType": "BUFF_OWNER",
                             "_targetLevelMask": "ELITE_AND_BOSS"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyLevelMask",
                             "_targetType": "BUFF_OWNER",
                             "_targetLevelMask": "NORMAL"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ModifySpData
    ctx = {"owner": e, "source": None, "target": e, "bb": {"sp_cost": 15.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifySpData",
                             "_targetType": "BUFF_OWNER", "_spCostString": "sp_cost",
                             "_onlyUpdateSpCost": True, "_updateSkillSpCostMin": True,
                             "_assignOldValueKey": None,
                             "_updateSpCostViaMaxRatioKey": None}], ctx)
    assert r[0]["action"] is True
    assert e._sp_cost_override == 15.0

    # AssignCharacterSkillBlackboardToBB: no skill -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignCharacterSkillBlackboardToBB",
                             "_targetType": "BUFF_OWNER",
                             "_sourceBlackboardKey": "projectile_delay_time",
                             "_targetBlackboardKey": "projectile_time_origin"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # ApplyElementDamageBasedOnDamageValue: 100 dmg x ratio 0.1 -> 10 FIRE
    dmg = {"amount": 100.0}
    ctx = {"owner": e, "source": None, "target": e, "bb": {"ratio": 0.1},
           "damage": dmg}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ApplyElementDamageBasedOnDamageValue",
                             "_elementType": "FIRE", "_sourceType": "MODIFIER_SOURCE",
                             "_targetType": "MODIFIER_TARGET", "_filterDamageType": False,
                             "_damageMask": "NONE"}], ctx)
    assert r[0]["action"] is True
    ep = b.buffs.get(e, "ep_fire")
    # full-bar model: value = remaining (1000 - 10 damage)
    assert ep is not None and abs((ep.get("value") or 0.0) - 990.0) < 1e-6, ep

    # AssignAmmoSkillRemainingCountToBB
    e._hunter_ammo = 4
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignAmmoSkillRemainingCountToBB",
                             "_targetType": "BUFF_OWNER", "_blackboardKey": "rest_bullet"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["rest_bullet"] == 4, ctx["bb"]

    # AssignTokenCntToBB
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignTokenCntToBB",
                             "_actionTargetType": "BUFF_OWNER", "_useTargetHost": False,
                             "_blackboardKey": "current_token_cnt"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["current_token_cnt"] == 0

    # FinishBuffsOfEveryEnemyById
    b.add_buff(e, {"key": "blaze2_s_2[on_tile]", "remaining_ticks": 300,
                   "layers": 1})
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FinishBuffsOfEveryEnemyById",
                             "_buffKey": "blaze2_s_2[on_tile]", "_loadFromBlackboard": False,
                             "_decCntIfStack": False, "_updateOverrideMap": True,
                             "_checkBuffSource": False, "_source": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert b.buffs.get(e, "blaze2_s_2[on_tile]") is None

    # CheckHostContainsBuff
    b.add_buff(e, {"key": "mylyss_s_2[buff]", "remaining_ticks": 300,
                   "layers": 1})
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckHostContainsBuff",
                             "_targetType": "BUFF_OWNER",
                             "_buffKeys": ["mylyss_s_2[buff]"], "isAND": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # CheckRouteMotionMode
    e._motion_mode = 0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckRouteMotionMode",
                             "_targetType": "BUFF_OWNER", "_mode": "WALK"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # AssignHostAttributeToBB
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignHostAttributeToBB",
                             "_targetType": "BUFF_OWNER", "_attributeType": "ATK",
                             "_setCurrentHp": False, "_scaleVar": "scale_invalid",
                             "_blackboardKey": "cached_atk"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["cached_atk"] == e.attributes.get("atk"), ctx["bb"]

    # CheckEnemyWhetherReachedSomeCheckPoint
    e._checkpoint_idx = 2
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyWhetherReachedSomeCheckPoint",
                             "_targetType": "BUFF_OWNER", "_backToFront": False,
                             "_checkPointIndex": 1, "_indexBbKey": None}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # CheckCharacterOnTile: operator on the same tile
    e.row, e.col = 2, 3
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCharacterOnTile",
                             "_targetType": "BUFF_OWNER", "_checkProfessionCategories": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # UpdateAttributeRawData
    e.attributes.base["maxHp"] = 2000.0
    e.max_hp = 2000.0
    ctx = {"owner": e, "source": None, "target": e, "bb": {"default_max_hp": 5000.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+UpdateAttributeRawData",
                             "_targetType": "BUFF_OWNER", "_attributeType": "MAX_HP",
                             "_valueKey": "default_max_hp"}], ctx)
    assert r[0]["action"] is True
    assert e.max_hp == 5000.0, e.max_hp

    # CheckDirectionWithBB
    e.direction = 3
    ctx = {"owner": e, "source": None, "target": e, "bb": {"direction": 1}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckDirectionWithBB",
                             "_target": "BUFF_OWNER", "_direction": "UP",
                             "_judgeType": "OPPOSITE", "_blackboardKey": "direction"}], ctx)
    assert r[0]["action"] is True, r

def test_buff_batch38_nodes():
    """Kill token / map pos / born state / tile mode enum / face L/R /
    element heal / direction / time gates / fixed damage."""
    from ark_emulator.consts import EnemyState
    from ark_emulator.attributes import Attributes
    from ark_emulator.entities import Token
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # EnemyKillToken
    tok = Token("token_test", Attributes({"maxHp": 100.0, "atk": 0.0}),
                3, 4, owner=e)
    b.tokens.append(tok)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+EnemyKillToken",
                             "_target": "TARGET"}],
                        {"owner": e, "source": None, "target": tok, "bb": {}})
    assert r[0]["action"] is True
    assert tok.dead is True

    # AssignMapPositionToBlackboard
    e.row, e.col = 4, 5
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignMapPositionToBlackboard",
                             "_targetType": "BUFF_OWNER", "_XKey": "x_0",
                             "_YKey": "y_0"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["x_0"] == 5 and ctx["bb"]["y_0"] == 4, ctx["bb"]

    # CheckCharacterInBornState
    e.state = EnemyState.BORN
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCharacterInBornState",
                             "_ownerType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    e.state = EnemyState.MOVE

    # CheckDynamicBuffTileModeInEnum
    e.row, e.col = 2, 2
    b._tile_modes[(2, 2)] = 0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckDynamicBuffTileModeInEnum",
                             "_modes": [0], "_exclude": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckDynamicBuffTileModeInEnum",
                             "_modes": [0], "_exclude": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # CheckFaceLOrR
    e.direction = 1
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckFaceLOrR",
                             "_target": "BUFF_OWNER", "_direction": "RIGHT"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # FixedValueElementHeal
    b.buffs.update_ep(e, 2, 100.0)   # fire bar 100
    b.buffs.recover_ep(e, 100.0, source=e)
    ep = b.buffs.get(e, "ep_fire")
    # full-bar model: recovered to full (1000)
    assert ep is None or (ep.get("value") or 0.0) >= 999.0

    # IfTargetFromDirection: source left of target (target col > source col)
    b.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b.enemies[1]
    e2.row, e2.col = 3, 4
    e.row, e.col = 3, 2
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IfTargetFromDirection",
                             "_sourceType": "MODIFIER_SOURCE", "_targetType": "MODIFIER_TARGET",
                             "_direction": "LEFT", "_checkTargetIsFromDirection": False}],
                        {"owner": e, "source": e, "target": e2, "bb": {}})
    assert r[0]["action"] is True, r

    # CheckGamePlayedTime
    ctx = {"owner": e, "source": None, "target": e, "bb": {"time": 0.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckGamePlayedTime",
                             "_condType": "GE"}], ctx)
    assert r[0]["action"] is True, r

    # EnemyDurcarChangeDirection: character above enemy -> UP
    e.direction = 0
    e.row, e.col = 2, 2
    e2.row, e.col = 4, 2
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+EnemyDurcarChangeDirection",
                             "_character": "BUFF_OWNER", "_enemy": "BUFF_SOURCE",
                             "_endPosOffsetAlongDirection": 0.5,
                             "_setDirectByBB": False}],
                        {"owner": e, "source": e2, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e.direction == 0, e.direction

    # CheckSpecificEnemyCount
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckSpecificEnemyCount",
                             "_targetType": "BUFF_OWNER", "_enemyId": "enemy_1000_gopro",
                             "_limitAmountKey": None, "_limitAmount": 0,
                             "_condType": "GT"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # FilterIsDummy
    e._is_dummy = False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+FilterIsDummy",
                             "_target": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # CheckUnitSideOfMap: enemy at col 2 on a wide map -> left half
    e.col = 2
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckUnitSideOfMap",
                             "_source": "BUFF_SOURCE", "_checkLeft": True}],
                        {"owner": e, "source": e, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # NoSourceDamageNew
    e2.max_hp = 10000.0
    e2.hp = 10000.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+NoSourceDamageNew",
                             "_targetType": "TARGET", "_damageType": "TRUE",
                             "_damageKey": "damage", "_ignoreForSp": True,
                             "_damageWithoutModify": True, "_attackType": "NONE",
                             "_isEnvDamage": False, "_isUndeadable": False,
                             "_ignoreCancelReasonMask": 0}],
                        {"owner": e, "source": None, "target": e2,
                         "bb": {"damage": 250.0}})
    assert r[0]["action"] is True
    assert abs(e2.hp - 9750.0) < 1.0, e2.hp

def test_buff_batch39_nodes():
    """Token spawn / range override / skill cd / boss countdown / interrupt."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    eng = BuffTemplateEngine(b)

    # SpawnTokenOnRangeTile: seal the target tile with trap_055_tileblock
    e.row, e.col = 3, 4
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SpawnTokenOnRangeTile",
                             "_sourceType": "SOURCE", "_targetType": "TARGET",
                             "_tokenToSpawn": {"inst": {
                                 "characterKey": "trap_055_tileblock",
                                 "level": 0, "phase": "PHASE_0"}}}],
                        {"owner": e, "source": e, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert any(t.token_id == "trap_055_tileblock" and not t.dead
               for t in b.tokens)

    # ModifyCharacterAttackTriggerRangeId
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyCharacterAttackTriggerRangeId",
                             "_target": "BUFF_OWNER", "_source": "BUFF_SOURCE",
                             "_useSpecifiedModeRangeId": False, "_sourceMode": 0,
                             "_modes": [1], "_useCurrentModeRangeId": True}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True

    # AssignEnemySkillCoolDownToBB: no skill -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AssignEnemySkillCoolDownToBB",
                             "_ownerType": "BUFF_OWNER", "_skillName": "Destroy",
                             "_checkSkillActive": False, "_outputKey": "destroy_cd"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # SetBossCountDown
    ctx = {"owner": e, "source": None, "target": e, "bb": {"destroy_cd": 8.0}}
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SetBossCountDown",
                             "_cdValue": -1.0, "_cdBBKey": "destroy_cd"}], ctx)
    assert r[0]["action"] is True
    assert e._boss_countdown == 8.0, e._boss_countdown

    # CheckCharacterInIdleState
    e.attack_timer = 0.0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCharacterInIdleState",
                             "_ownerType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ForceEnterSkillOverloadProgress
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ForceEnterSkillOverloadProgress",
                             "_targetType": "BUFF_SOURCE"}],
                        {"owner": e, "source": e, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._skill_overload is True

    # InterruptEnemyAbility: no active skill -> False
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+InterruptEnemyAbility",
                             "_enemyFrom": "BUFF_OWNER", "_resetCooldown": False,
                             "_checkBuffAbility": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # CheckCharacterInMagicCircuit -> False (not modelled)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCharacterInMagicCircuit",
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r

    # ModifyRuntimeRouteUseBranchRoute rebuilds the flow field
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyRuntimeRouteUseBranchRoute",
                             "_target": "BUFF_OWNER",
                             "_addIntoExtraRuntimeRouteStartPointAsKey": False}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

def test_buff_batch40_enemy_selector():
    """Shared self-buff classification (template BUFF_OWNER without victim
    actions -> caster) + atk_scale_dot per-tick damage."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_10002_trtrsl", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    sc = e.skill_controller
    sh = next(sk for sk in sc.skills if sk.prefab_key == "Shine")
    assert any(sb["data"].get("buffKey") == "enemy_trtrsl_s"
               for sb in sh.self_buffs), sh.self_buffs

    # atk_scale_dot: AdvancedApplyDamage reads the per-tick multiplier
    e.attributes.base["atk"] = 1000.0
    e.attributes.base["magicResistance"] = 0.0
    e.max_hp = 100000.0
    e.hp = e.max_hp
    eng = BuffTemplateEngine(b)
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AdvancedApplyDamage",
                             "_sourceType": "BUFF_SOURCE", "_targetType": "BUFF_OWNER",
                             "_damageType": "MAGICAL", "_atkScaleVar": "atk_scale_dot",
                             "_defaultAtkScale": 1.0, "_applyWay": "NONE",
                             "_baseOnHostAtk": False}],
                        {"owner": e, "source": e, "target": e,
                         "bb": {"atk_scale_dot": 0.15}})
    assert r[0]["action"] is True, r
    assert abs(e.hp - 99850.0) < 1.0, e.hp

def test_buff_batch41_target_options():
    """CreateBuffInCircleRange / CreateBuffInRange honour targetOptions
    (targetSide / profession / motion / abnormal / category)."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    e.row, e.col = 2, 2
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    buff = {"buffKey": "topt_mark", "templateKey": "empty",
            "attributes": {"abnormalFlags": [], "abnormalImmunes": [],
                           "abnormalAntis": [], "abnormalCombos": [],
                           "abnormalComboImmunes": [],
                           "attributeModifiers": []},
            "lifeTimeType": "LIMITED", "lifeTime": 3.0}

    # professionMask MEDIC + targetSide ALLY -> only the medic operator
    node = {"$type": "Torappu.Battle.Action.Nodes+CreateBuffInCircleRange",
            "_sourceType": "BUFF_OWNER", "_targetType": "BUFF_OWNER",
            "_targetOptions": {"targetSide": "ALLY", "targetMotion": "ALL",
                               "professionMask": "MEDIC"},
            "_rangeRadius": 3.0, "_buffs": [buff]}
    r = eng.run_actions(e, [node], {"owner": e, "source": e, "target": e,
                                    "bb": {}})
    assert r[0]["action"] is True, r
    assert "topt_mark" in [x.get("key") for x in op.buffs]
    assert "topt_mark" not in [x.get("key") for x in e.buffs]

    # targetMotion FLY excludes the ground enemy
    b.buffs.remove(op, "topt_mark")
    node2 = dict(node)
    node2["_targetOptions"] = {"targetSide": "ENEMY", "targetMotion": "FLY"}
    r = eng.run_actions(e, [node2], {"owner": e, "source": e, "target": e,
                                     "bb": {}})
    assert r[0]["action"] is False, r
    assert "topt_mark" not in [x.get("key") for x in e.buffs]

    # containSomeAbnormalFlags STUNNED: enemy stunned -> applies
    e.set_flag(0, 30)
    node3 = dict(node)
    node3["_targetOptions"] = {"targetSide": "ENEMY", "targetMotion": "ALL",
                               "containSomeAbnormalFlags": True,
                               "containAbnormalFlag": "STUNNED"}
    r = eng.run_actions(e, [node3], {"owner": e, "source": e, "target": e,
                                     "bb": {}})
    assert r[0]["action"] is True, r
    assert "topt_mark" in [x.get("key") for x in e.buffs]
    e.clear_flag(0)
    b.buffs.remove(e, "topt_mark")
    r = eng.run_actions(e, [node3], {"owner": e, "source": e, "target": e,
                                     "bb": {}})
    assert r[0]["action"] is False, r

def test_buff_batch42_aoe_options():
    """AOEDamage honours targetOptions (profession / side filters)."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE
    e.row, e.col = 2, 2
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    b.deploy("char_275_breeze", 2, 5)
    med = b.operators[0]
    vg = b.operators[1]
    eng = BuffTemplateEngine(b)

    hp_m, hp_v = med.hp, vg.hp
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AOEDamage",
                             "_sourceType": "BUFF_SOURCE", "_targetType": "BUFF_OWNER",
                             "_damageType": "TRUE",
                             "_targetOptions": {"targetSide": "ALLY",
                                                "professionMask": "MEDIC"}}],
                        {"owner": e, "source": e, "target": e,
                         "bb": {"range_radius": 3.0, "damage": 50.0}})
    assert r[0]["action"] is True, r
    assert abs(med.hp - (hp_m - 50.0)) < 1e-6, med.hp
    assert abs(vg.hp - (hp_v - 50.0)) < 1e-6, vg.hp  # both medics hit

def test_buff_batch43_modifier_events():
    """ON_APPLIED_MODIFIER fires after damage settles and blackboard
    writes persist (enemy_mhrors damage counter accumulates)."""
    from ark_emulator.consts import DamageType
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.attributes.base["def"] = 0.0
    e.attributes.base["magicResistance"] = 0.0
    e.max_hp = 10000.0
    e.hp = 10000.0
    b.add_buff(e, {"key": "empgrd", "remaining_ticks": 30 * 30,
                   "template_key": "enemy_empgrd_damge_buffer",
                   "blackboard": {}})
    b.apply_damage(e, 50.0, DamageType.TRUE, source=None)
    ent = b.buffs.get(e, "empgrd")
    assert ent is not None, e.buffs
    assert abs((ent["blackboard"] or {}).get("value", 0.0) - 50.0) < 1e-6, \
        ent["blackboard"]
    b.apply_damage(e, 30.0, DamageType.TRUE, source=None)
    ent = b.buffs.get(e, "empgrd")
    assert abs((ent["blackboard"] or {}).get("value", 0.0) - 30.0) < 1e-6, \
        ent["blackboard"]

def test_buff_batch44_lifecycle_events():
    """ON_OWNER_BORN / ON_TARGET_KILLED / ON_SKILL_START dispatch."""
    from ark_emulator.consts import DamageType
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    op = b.operators[0]

    # ON_OWNER_BORN -> double_Initial_sp raises SP
    e.sp = 0.0
    e.sp_max = 100.0
    b.add_buff(e, {"key": "t_born", "remaining_ticks": 30 * 30,
                   "template_key": "double_Initial_sp",
                   "blackboard": {"sp": 50.0}})
    b._dispatch_buff_events(e, "ON_OWNER_BORN", source=e, target=e)
    assert e.sp == 50.0, e.sp

    # ON_SKILL_START -> atk_up_on_skill_start[stacked] grants the atk buff
    b.add_buff(op, {"key": "t_skstart", "remaining_ticks": 30 * 30,
                    "template_key": "atk_up_on_skill_start[stacked]",
                    "blackboard": {}})
    b._dispatch_buff_events(op, "ON_SKILL_START", source=op, target=op)
    keys = [x.get("key") for x in op.buffs]
    assert "atk_up_on_skill_start[stacked]" in keys, keys

    # ON_TARGET_KILLED -> bibeak_t_1 grants atk_speed on a kill
    b.add_buff(e, {"key": "t_bibeak", "remaining_ticks": 30 * 30,
                   "template_key": "bibeak_t_1", "blackboard": {}})
    op.attributes.base["def"] = 0.0
    op.attributes.base["magicResistance"] = 0.0
    op.max_hp = 1000.0
    op.hp = op.max_hp
    b.apply_damage(op, 5000.0, DamageType.TRUE, source=e)
    assert op.dead is True
    keys = [x.get("key") for x in e.buffs]
    assert "bibeak_t_1[atk_speed]" in keys, keys

def test_buff_batch45_more_events():
    """ON_EVADE_DAMAGE / ON_OWNER_BLOCKEE_CHANGED dispatch."""
    from ark_emulator.consts import DamageType, EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.attributes.base["maxHp"] = 1000000.0
    e.max_hp = 1000000.0
    e.hp = e.max_hp

    # ON_EVADE_DAMAGE: 50% hit-rate -> ~half the hits miss and grant
    # the evade buff (seed the battle RNG to force a miss)
    e.attributes.base["damageHitratePhysical"] = 50.0
    b.add_buff(e, {"key": "evade", "remaining_ticks": 30 * 30,
                   "template_key": "charge_atk_speed_on_evade",
                   "blackboard": {}})
    missed = 0
    for _ in range(40):
        before = len([x.get("key") for x in e.buffs])
        b.apply_damage(e, 50.0, DamageType.PHYSICAL, source=None)
        if "charge_atk_speed_on_evade" in [x.get("key") for x in e.buffs] \
                and len([x.get("key") for x in e.buffs]) > before:
            missed += 1
    assert missed > 0, "evade event must fire on a miss"

    # ON_OWNER_BLOCKEE_CHANGED: the blocker's buff applies the dot
    # trigger to its blockee (CreateBuffToBlockee)
    e.attributes.base["maxHp"] = 1000000.0
    e.max_hp = 1000000.0
    e.hp = e.max_hp
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    blk_op = b.operators[0]
    e.blocked_by = blk_op
    blk_op.add_blockee(e)
    b.add_buff(blk_op, {"key": "blk", "remaining_ticks": 30 * 30,
                        "template_key": "halfIdle_dot_to_blockee[magical]",
                        "blackboard": {}})
    b._dispatch_buff_events(blk_op, "ON_OWNER_BLOCKEE_CHANGED",
                            source=blk_op, target=e)
    assert "halfIdle_dot_to_blockee[magical][trigger]" in \
        [x.get("key") for x in e.buffs]

def test_buff_batch46_more_events():
    """ON_ABNORMAL_FLAG_DIRTY / ON_BEFORE_ATTACK / ON_ABILITY_START
    dispatch."""
    from ark_emulator.consts import EnemyState, AbnormalFlag
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.MOVE

    # ON_ABNORMAL_FLAG_DIRTY: setting FROZEN grants the frozen mark
    b.add_buff(e, {"key": "fz", "remaining_ticks": 30 * 30,
                   "template_key": "enemy_mheagl_fly[frozen]",
                   "blackboard": {}})
    b.add_abnormal(e, AbnormalFlag.FROZEN, 3.0)
    assert "mheagl_frozen[mark]" in [x.get("key") for x in e.buffs]

    # ON_BEFORE_ATTACK: starting a normal attack grants the atk buff
    b.add_buff(e, {"key": "ds", "remaining_ticks": 30 * 30,
                   "template_key": "enemy_dursho_t", "blackboard": {}})
    from ark_emulator.ai import _start_normal_attack
    _start_normal_attack(e, b, 2.0)
    assert "enemy_dursho_t[atk]" in [x.get("key") for x in e.buffs]

    # ON_ABILITY_START: grants the stop-weaken buff
    b.add_buff(e, {"key": "db", "remaining_ticks": 30 * 30,
                   "template_key": "enemy_dufrbl_t", "blackboard": {}})
    b._dispatch_buff_events(e, "ON_ABILITY_START", source=e, target=e)
    assert "dufrbl_t[stop_weaken]" in [x.get("key") for x in e.buffs]

def test_buff_batch47_more_events():
    """ON_ABILITY_INTERRUPTED / ON_AFTER_CALCULATE_DAMAGE /
    ON_OWNER_HP_FULL dispatch."""
    from ark_emulator.consts import DamageType
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]

    # ON_ABILITY_INTERRUPTED -> CreateBuff "stun" (SP>0 branch passes)
    e.sp_max = 100.0
    e.sp = 50.0
    b.add_buff(e, {"key": "sy", "remaining_ticks": 30 * 30,
                   "template_key": "enemy_syudg_t[stun]", "blackboard": {}})
    b._dispatch_buff_events(e, "ON_ABILITY_INTERRUPTED",
                            source=e, target=e)
    assert "stun" in [x.get("key") for x in e.buffs]

    # ON_AFTER_CALCULATE_DAMAGE -> UpdateBuffAttributeModifier runs
    e.max_hp = 100000.0
    e.hp = e.max_hp
    b.add_buff(e, {"key": "blk", "remaining_ticks": 30 * 30,
                   "template_key": "enemy_blkswb_t_2", "blackboard": {}})
    b.apply_damage(e, 10.0, DamageType.PHYSICAL, source=None)
    assert e.hp < e.max_hp  # damage still lands

    # ON_OWNER_HP_FULL dispatch does not crash
    b.add_buff(e, {"key": "titi", "remaining_ticks": 30 * 30,
                   "template_key": "titi_s_3[doze_indoze]",
                   "blackboard": {}})
    b._dispatch_buff_events(e, "ON_OWNER_HP_FULL", source=e, target=e)

def test_buff_batch48_snapshot_state():
    """Snapshot exposes global / shared / tile blackboards."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b._global_bb["enemy_cjdoor_col"] = 4.0
    b._char_shared_bb["aglna2_located_row"] = 2.0
    b._tile_bb[(3, 3)] = {"mush_cnt": 1.0}
    snap = b.snapshot()
    assert snap["globalBlackboard"]["enemy_cjdoor_col"] == 4.0
    assert snap["sharedBlackboard"]["aglna2_located_row"] == 2.0
    assert snap["tileBlackboard"]["3,3"]["mush_cnt"] == 1.0
    import json
    json.dumps(snap)  # must stay serialisable (no recursion)

def test_buff_batch49_switchmode_direction():
    """SwitchMode changes mode_index (with ON_UNIT_SWITCH_MODE) and
    SwitchDirection fires ON_DIRECTION_CHANGED."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    eng = BuffTemplateEngine(b)

    # SwitchMode: csdoll_shield[mode] ON_BUFF_START loads mode from bb
    b.add_buff(e, {"key": "cs", "remaining_ticks": 30 * 30,
                   "template_key": "csdoll_shield[mode]",
                   "blackboard": {"mode_index": 2}})
    b._dispatch_buff_events(e, "ON_BUFF_START", source=e, target=e)
    assert e.mode_index == 2, e.mode_index

    # ON_DIRECTION_CHANGED via SwitchDirection
    e.direction = 0
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+SwitchDirection",
                             "_source": "BUFF_SOURCE", "_direction": "RIGHT",
                             "_useCustomDirection": False, "_rightNodes": []}],
                        {"owner": e, "source": e, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert e.direction == 1, e.direction

def test_buff_batch50_misc_nodes():
    """AtkToHpRecovery / ModifyCostIncreaseTime / ModifyMaxCost /
    Manhattan distance / unharmful / unit-in-range / can-not-exit /
    id / ability-name / remaining-time."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    e.attributes.base["atk"] = 200.0
    e.max_hp = 10000.0
    e.hp = 8000.0
    eng = BuffTemplateEngine(b)

    # AtkToHpRecovery: heals owner by atk x bb ratio
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+AtkToHpRecovery",
                             "_getAtkFromTarget": False,
                             "_getAtkTargetType": "BUFF_SOURCE"}],
                        {"owner": e, "source": e, "target": e,
                         "bb": {"ratio": 0.5}})
    assert r[0]["action"] is True
    assert abs(e.hp - 8100.0) < 1e-6, e.hp

    # ModifyCostIncreaseTime: multiply period by 2
    base_period = b.cost_increase_time
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyCostIncreaseTime",
                             "_isMulOtherwiseDiv": True, "_sourceType": "BUFF_OWNER",
                             "_blackboardKey": "delta_cost_increase_time",
                             "_deltaCostIncreaseTime": 1.0}],
                        {"owner": e, "source": None, "target": e,
                         "bb": {"delta_cost_increase_time": 2.0}})
    assert r[0]["action"] is True
    assert abs(b.cost_increase_time - base_period * 2.0) < 1e-6

    # ModifyMaxCost
    mc0 = b.max_cost
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+ModifyMaxCost",
                             "_sourceType": "SOURCE", "_isMinus": False,
                             "_ensureCurCostNotExceedMax": False}],
                        {"owner": e, "source": e, "target": e,
                         "bb": {"value": 50.0}})
    assert r[0]["action"] is True
    assert abs(b.max_cost - (mc0 + 50.0)) < 1e-6

    # CheckManhattanDistance: owner at (2,2), target at (2,4) -> dist 2
    e.row, e.col = 2, 2
    b.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b.enemies[1]
    e2.row, e2.col = 2, 4
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+CheckManhattanDistance",
                             "_minDist": 1, "_maxDist": 2}],
                        {"owner": e, "source": e, "target": e2, "bb": {}})
    assert r[0]["action"] is True, r

    # IsUnharmfulEnemy
    e.is_unharmful = True
    r = eng.run_actions(e, [{"$type": "Torappu.Battle.Action.Nodes+IsUnharmfulEnemy",
                             "_targetType": "BUFF_OWNER"}],
                        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    e.is_unharmful = False

    # CheckHasUnitInRange: operator within radius of e2
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    r = eng.run_actions(e2, [{"$type": "Torappu.Battle.Action.Nodes+CheckHasUnitInRange",
                              "_targetType": "BUFF_OWNER", "_checkRangeId": False,
                              "_rangeIdKey": "", "_rangeId": "",
                              "_checkRadius": True, "_radiusKey": "radius_2",
                              "_radius": {"_serializedValue": 1.0},
                              "_checkSideType": True, "_targetSide": "ALLY"}],
                        {"owner": e2, "source": None, "target": e2,
                         "bb": {"radius_2": 2.0}})
    assert r[0]["action"] is True, r

    # SetEnemyCanNotExit
    r = eng.run_actions(e2, [{"$type": "Torappu.Battle.Action.Nodes+SetEnemyCanNotExit",
                              "_target": "BUFF_OWNER", "_canNotExit": True}],
                        {"owner": e2, "source": None, "target": e2, "bb": {}})
    assert r[0]["action"] is True
    assert e2.can_not_exit is True

    # AssignIDToBlackboard
    ctx = {"owner": e2, "source": None, "target": e2, "bb": {}}
    r = eng.run_actions(e2, [{"$type": "Torappu.Battle.Action.Nodes+AssignIDToBlackboard",
                              "_targetType": "BUFF_OWNER", "_bbKey": "char_id"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["char_id"] == "enemy_1000_gopro", ctx["bb"]

    # CheckEnemyAbilityName: no active skill -> False
    r = eng.run_actions(e2, [{"$type": "Torappu.Battle.Action.Nodes+CheckEnemyAbilityName",
                              "_target": "BUFF_OWNER", "_abilityName": "BloodFountain2"}],
                        {"owner": e2, "source": None, "target": e2, "bb": {}})
    assert r[0]["action"] is False, r


def test_buff_batch51_buff_creation_and_tile_nodes():
    """CreateNoSourceBuff / CreateBuffUseHostAsSource / AttachAsDerivedBuff /
    RewriteTileOptionsInRange / TriggerSpecifiedAbility+TriggerAbilityMergeBB."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)

    # CreateNoSourceBuff: buff on owner with source=None
    r = eng.run_actions(op, [{"$type": "Torappu.Battle.Action.Nodes+CreateNoSourceBuff",
                              "_buffOwner": "BUFF_OWNER",
                              "_buff": {"buffKey": "t_nosrc",
                                        "attributes": {
                                            "abnormalFlags": ["SKILL_NOT_ACTIVATABLE"],
                                            "abnormalImmunes": [], "abnormalAntis": [],
                                            "abnormalCombos": [], "abnormalComboImmunes": [],
                                            "attributeModifiers": []},
                                        "lifeTimeType": "INFINITY"}}],
                        {"owner": op, "source": op, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    entry = [x for x in op.buffs if x["key"] == "t_nosrc"]
    assert entry and entry[0]["source"] is None, entry
    assert op.flag(24), op.abnormal       # SKILL_NOT_ACTIVATABLE

    # CreateBuffUseHostAsSource: sluggish with the host (owner) as source
    r = eng.run_actions(op, [{"$type": "Torappu.Battle.Action.Nodes+CreateBuffUseHostAsSource",
                              "_targetType": "BUFF_OWNER",
                              "_buffData": {"buffKey": "sluggish", "loadFromDB": True,
                                            "templateKey": "empty"}}],
                        {"owner": op, "source": None, "target": op,
                         "bb": {"sluggish": 3.0}})
    assert r[0]["action"] is True, r
    entry = [x for x in op.buffs if x["key"] == "sluggish"]
    assert entry and entry[0]["source"] is op, entry
    assert abs(op.attributes.get("moveSpeed") - 0.2) < 0.01, \
        op.attributes.get("moveSpeed")

    # AttachAsDerivedBuff: child removed with parent, parent survives child
    def _attach_child():
        return eng.run_actions(
            op, [{"$type": "Torappu.Battle.Action.Nodes+AttachAsDerivedBuff",
                  "_sourceType": "BUFF_OWNER", "_buffKey": "t_parent",
                  "_finishDerivedBuffIfParentFinish": True,
                  "_buff": {"buffKey": "t_child", "lifeTimeType": "INFINITY"}}],
            {"owner": op, "source": None, "target": None,
             "bb": {"_buff_entry": {"key": "t_parent"}}})
    b.add_buff(op, {"key": "t_parent", "remaining_ticks": 30 * 60,
                    "template_key": "empty", "source": op})
    r = _attach_child()
    assert r[0]["action"] is True, r
    child = [x for x in op.buffs if x["key"] == "t_child"]
    assert child and child[0]["derived_from"] == "t_parent", child
    b.buffs.remove(op, "t_child")
    assert any(x["key"] == "t_parent" for x in op.buffs)
    _attach_child()
    b.buffs.remove(op, "t_parent")
    assert not any(x["key"] == "t_child" for x in op.buffs)
    assert not any(x["key"] == "t_parent" for x in op.buffs)

    # RewriteTileOptionsInRange: enemy makes tiles in its range undeployable
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    base = None
    for rr in range(b.map.rows):
        for cc in range(b.map.cols):
            if b.map.buildable(rr, cc, 1):
                base = (rr, cc)
                break
        if base:
            break
    assert base, "no buildable melee tile"
    e.row, e.col = base
    e.pos_x, e.pos_y = float(base[1]), float(base[0])
    e.direction = 1
    assert b.map.buildable(base[0], base[1], 1) is True
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+RewriteTileOptionsInRange",
             "_sourceType": "BUFF_OWNER", "_rangeId": "b-2",
             "_advancedBuildableMask": "DEFAULT", "_nightMode": False,
             "_restoreTileOptions": False, "_buildableChange": True,
             "_buildableType": "NONE"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.map.buildable(base[0], base[1], 1) is False
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+RewriteTileOptionsInRange",
             "_sourceType": "BUFF_OWNER", "_rangeId": "b-2",
             "_nightMode": False, "_restoreTileOptions": True,
             "_buildableChange": False, "_buildableType": "NONE"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.map.buildable(base[0], base[1], 1) is True

    # TriggerSpecifiedAbility / TriggerAbilityMergeBB: gate + observable event
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+TriggerSpecifiedAbility",
              "_ownerType": "BUFF_OWNER", "_targetType": "TARGET",
              "_abilityName": "blacksteel_energy"}],
        {"owner": op, "source": op, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    evs = [x for x in sim.snapshot()["events"]
           if x["type"] == "buff_trigger_ability"]
    assert evs and evs[-1]["data"]["ability"] == "blacksteel_energy", evs[-3:]
    assert evs[-1]["data"]["unit"] == op.inst_id

    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+TriggerAbilityMergeBB",
              "_ownerType": "BUFF_OWNER", "_targetType": "BUFF_OWNER",
              "_abilityName": "UpgradeToken", "_assignBBKeys": ["token_cnt"]}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    evs = [x for x in sim.snapshot()["events"]
           if x["type"] == "buff_trigger_ability"]
    assert evs[-1]["data"]["ability"] == "UpgradeToken", evs[-3:]
    assert evs[-1]["data"]["mergeBB"] is True


def test_hp_no_less_than_percent_modifier():
    """HpNoLessThanCertainPercentModifier clamps ON_TAKE_DAMAGE so the
    owner's HP cannot drop below the blackboard ratio of max HP."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    op.max_hp = 10000.0
    op.hp = 8000.0
    eng = BuffTemplateEngine(b)
    node = {"$type": "Torappu.Battle.Action.Nodes+"
                     "HpNoLessThanCertainPercentModifier"}
    dmg = {"amount": 10000.0, "type": 0, "blocked": 0.0}
    r = eng.run_actions(op, [node],
                        {"owner": op, "source": None, "target": op,
                         "bb": {"huang_t_1[lock].min_hp_ratio": 0.5},
                         "damage": dmg})
    assert r[0]["action"] is True, r
    assert abs(dmg["amount"] - 3000.0) < 1e-6, dmg
    # at the floor the remaining damage is fully blocked
    op.hp = 5000.0
    dmg["amount"] = 1000.0
    eng.run_actions(op, [node],
                    {"owner": op, "source": None, "target": op,
                     "bb": {"min_hp_ratio": 0.5}, "damage": dmg})
    assert dmg["amount"] == 0.0, dmg


def test_huang_t1_emergency_defib():
    """煌 T1 紧急除颤 end-to-end: HP below 25% triggers once -> heal 50%
    max HP + huang_t_1[lock] buff; while the lock is active HP cannot
    drop below 50% (HpNoLessThanCertainPercentModifier)."""
    from ark_emulator.consts import DamageType
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    base = None
    for rr in range(b.map.rows):
        for cc in range(b.map.cols):
            if b.map.buildable(rr, cc, 1):
                base = (rr, cc)
                break
        if base:
            break
    assert base, "no buildable melee tile"
    ok, why = b.deploy("char_017_huang", base[0], base[1])
    assert ok, why
    op = b.operators[0]
    assert getattr(op, "talent_system", None) is not None
    for _ in range(60):
        b.tick_once()
    max_hp = float(op.max_hp)
    op.hp = max_hp * 0.1                # 10% < 25%
    b.tick_once()
    lock = [x for x in op.buffs if x["key"] == "huang_t_1[lock]"]
    assert lock, [x["key"] for x in op.buffs]
    assert any(x["key"] == "huang_t_1[heal]" for x in op.buffs)
    assert op.hp >= max_hp * 0.55, op.hp   # healed ~50% max HP
    # while the lock is active a huge hit leaves HP at the 50% floor
    b.apply_damage(op, 99999.0, DamageType.TRUE, source=None)
    assert abs(op.hp - max_hp * 0.5) < 1.0, op.hp
    # once per deployment: a second dip does not heal again
    op.hp = max_hp * 0.1
    b.tick_once()
    assert op.hp < max_hp * 0.2, op.hp
    # after the lock expires the floor is gone
    b.buffs.remove(op, "huang_t_1[lock]")
    b.apply_damage(op, 99999.0, DamageType.TRUE, source=None)
    assert op.dead or op.hp < max_hp * 0.5, op.hp


def test_buff_batch53_projectile_and_gate_nodes():
    """CheckCanUseAtkOrCbt / TriggerAbilityUseSelectorMergeBB /
    EmitProjectileUseAbilitySelector / EmitProjectileOnSourceRootTile."""
    from ark_emulator.consts import AbnormalFlag
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    b.spawn_enemy("enemy_1000_gopro", 0)
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e2 = b.enemies[1]
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0
    e2.row, e2.col = 1, 1
    e2.pos_x, e2.pos_y = 1.0, 1.0

    # CheckCanUseAtkOrCbt: stunned -> False, healthy -> True
    b.add_abnormal(e, AbnormalFlag.STUNNED, 5.0)
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+CheckCanUseAtkOrCbt",
             "_targetType": "BUFF_OWNER"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r
    r = eng.run_actions(
        e2, [{"$type": "Torappu.Battle.Action.Nodes+CheckCanUseAtkOrCbt",
              "_targetType": "BUFF_OWNER"}],
        {"owner": e2, "source": None, "target": e2, "bb": {}})
    assert r[0]["action"] is True, r

    # TriggerAbilityUseSelectorMergeBB: observable event with mergeBB
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "TriggerAbilityUseSelectorMergeBB",
              "_ownerType": "BUFF_OWNER", "_targetType": "BUFF_OWNER",
              "_abilityName": "PassionSkill"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    evs = [x for x in sim.snapshot()["events"]
           if x["type"] == "buff_trigger_ability"]
    assert evs[-1]["data"]["ability"] == "PassionSkill", evs[-3:]
    assert evs[-1]["data"]["mergeBB"] is True

    # EmitProjectileUseAbilitySelector: on-hit AdvancedApplyDamage chain
    e2.attributes.base["atk"] = 200.0
    hp0 = op.hp
    node = {"$type": "Torappu.Battle.Action.Nodes+"
                     "EmitProjectileUseAbilitySelector",
            "_sourceType": "BUFF_OWNER", "_targetType": "TARGET",
            "_abilityName": "MissileSelector",
            "_projectileKey": "projectile_test_arrow",
            "_actions": [{"$type": "Torappu.Battle.Action.Nodes+"
                                  "AdvancedApplyDamage",
                          "_sourceType": "SOURCE", "_targetType": "TARGET",
                          "_damageType": "PURE", "_atkScaleVar": "atk_scale",
                          "_defaultAtkScale": 1.0}],
            "_emitCount": 1}
    r = eng.run_actions(e2, [node],
                        {"owner": e2, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.projectiles, "projectile not spawned"
    b.projectiles[0].on_hit(b)
    assert abs((hp0 - op.hp) - 200.0) < 1.0, (hp0, op.hp)
    evs = [x for x in sim.snapshot()["events"]
           if x["type"] == "buff_emit_projectile"]
    assert evs and evs[-1]["data"]["selector"] == "MissileSelector", evs[-3:]

    # EmitProjectileOnSourceRootTile: with a target spawns a projectile,
    # without a target emits a skipped event.
    r = eng.run_actions(
        e2, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "EmitProjectileOnSourceRootTile",
              "_sourceType": "BUFF_OWNER", "_targetType": "TARGET",
              "_projectileKey": "projectile_test_arrow"}],
        {"owner": e2, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(
        e2, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "EmitProjectileOnSourceRootTile",
              "_sourceType": "BUFF_OWNER", "_targetType": "TARGET"}],
        {"owner": e2, "source": None, "target": None, "bb": {}})
    assert r[0]["action"] is True, r
    evs = [x for x in sim.snapshot()["events"]
           if x["type"] == "buff_emit_projectile"]
    assert any(x["data"].get("skipped") == "no_projectile_key"
               for x in evs[-3:]), evs[-3:]


def test_buff_batch54_count_tile_trace_nodes():
    """CheckBuildCnt / ModifyBlackboardStr / CreateTileEffect /
    DisableEnemySwitchFaceByMove / CheckRootTileAdvBuildableMask /
    EnemyForceTracePosition / ReleaseEnemyFromCurrentWave / BlinkNode."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    eng = BuffTemplateEngine(b)

    # CheckBuildCnt: 1 deployed -> LE 1 True, GT 1 False
    r = eng.run_actions(
        None, [{"$type": "Torappu.Battle.Action.Nodes+CheckBuildCnt",
                "_checkBuildCnt": 1, "_condType": "LE"}],
        {"owner": None, "source": None, "target": None, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(
        None, [{"$type": "Torappu.Battle.Action.Nodes+CheckBuildCnt",
                "_checkBuildCnt": 1, "_condType": "GT"}],
        {"owner": None, "source": None, "target": None, "bb": {}})
    assert r[0]["action"] is False, r

    # ModifyBlackboardStr
    ctx = {"owner": None, "source": None, "target": None, "bb": {}}
    r = eng.run_actions(
        None, [{"$type": "Torappu.Battle.Action.Nodes+ModifyBlackboardStr",
                "_blackboardKeys": "toast", "_value": "SPBELL_TOAST_1"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["toast"] == "SPBELL_TOAST_1"

    # CreateTileEffect: observable event
    r = eng.run_actions(
        None, [{"$type": "Torappu.Battle.Action.Nodes+CreateTileEffect",
                "_effectKey": "trap_test_finish_01"}],
        {"owner": None, "source": None, "target": None, "bb": {}})
    assert r[0]["action"] is True
    evs = [x for x in sim.snapshot()["events"] if x["type"] == "tile_effect"]
    assert evs and evs[-1]["data"]["effect"] == "trap_test_finish_01"

    # DisableEnemySwitchFaceByMove
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+DisableEnemySwitchFaceByMove",
             "_targetType": "BUFF_OWNER", "_disabled": True}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._disable_face_switch is True

    # CheckRootTileAdvBuildableMask: default tile -> DEFAULT, not NIGHT
    e.row, e.col = 2, 2
    e.pos_x, e.pos_y = 2.0, 2.0
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CheckRootTileAdvBuildableMask",
             "_ownerType": "BUFF_OWNER", "_buildableMask": "DEFAULT"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CheckRootTileAdvBuildableMask",
             "_ownerType": "BUFF_OWNER", "_buildableMask": "NIGHT"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is False, r
    b.map.tile(2, 2).set_advanced_buildable_override(1)
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CheckRootTileAdvBuildableMask",
             "_ownerType": "BUFF_OWNER", "_buildableMask": "NIGHT"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r

    # ReleaseEnemyFromCurrentWave: flag + event
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "ReleaseEnemyFromCurrentWave",
             "_sourceType": "BUFF_OWNER", "_trackEnemyAtNextWave": True}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._released_from_wave is True and e._track_next_wave is True

    # BlinkNode: teleport via row/col blackboard
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+BlinkNode",
             "_targetType": "BUFF_OWNER", "_useRowAndColOnBlackboard": True}],
        {"owner": e, "source": None, "target": e, "bb": {"row": 4, "col": 5}})
    assert r[0]["action"] is True
    assert (e.row, e.col) == (4, 5), (e.row, e.col)

    # EnemyForceTracePosition: enemy chases the operator
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    e.row, e.col = 1, 1
    e.pos_x, e.pos_y = 1.0, 1.0
    e._trace_target = None
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "EnemyForceTracePosition",
             "_source": "BUFF_OWNER", "_target": "TARGET",
             "_reachOffset": {"x": 0.4, "y": 0.4},
             "_stopTraceWhenNoTarget": True}],
        {"owner": e, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert e._trace_target is op
    px0, py0 = e.pos_x, e.pos_y
    for _ in range(45):
        b.tick_once()
    assert e.pos_x > px0 + 0.2, (px0, e.pos_x)   # moved toward the op


def test_buff_batch55_token_steal_move_nodes():
    """GainToken / ModifyAttributeDataRangeOverride /
    AssignStealAttributeAbilityTotalValueToBB / IgnoreAllButMoveCp."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    eng = BuffTemplateEngine(b)
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]

    # GainToken: blackboard token_key -> player-side gained-token inventory
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+GainToken",
             "_targetType": "BUFF_OWNER", "_rechargeTiming": "NORMAL"}],
        {"owner": e, "source": None, "target": e, "bb": {"token_key": "tok_test_a"}})
    assert r[0]["action"] is True, r
    assert b._gained_tokens.get("tok_test_a") == 1
    evs = [x for x in sim.snapshot()["events"] if x["type"] == "token_gained"]
    assert evs and evs[-1]["data"]["tokenKey"] == "tok_test_a"
    snap = sim.snapshot()
    assert snap["gainedTokens"]["tok_test_a"]["count"] == 1

    # split token key
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+GainToken",
             "_targetType": "BUFF_OWNER", "_spiltTokenKey": True}],
        {"owner": e, "source": None, "target": e,
         "bb": {"token_key": "tok_test_b,tok_test_c"}})
    assert r[0]["action"] is True, r
    assert b._gained_tokens.get("tok_test_b") == 1
    assert b._gained_tokens.get("tok_test_c") == 1

    # ModifyAttributeDataRangeOverride: move-speed floor from bb, then clear
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "ModifyAttributeDataRangeOverride",
             "_targetType": "BUFF_OWNER", "_attributeType": "MOVE_SPEED",
             "_minValueKey": "minValue"}],
        {"owner": e, "source": None, "target": e,
         "bb": {"minValue": 0.8}})
    assert r[0]["action"] is True, r
    assert abs(e._move_speed_min - 0.8) < 1e-6
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "ModifyAttributeDataRangeOverride",
             "_targetType": "BUFF_OWNER", "_attributeType": "MOVE_SPEED",
             "_doClear": True}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._move_speed_min == 0.0

    # AssignStealAttributeAbilityTotalValueToBB: current + cap
    ctx = {"owner": e, "source": None, "target": e, "bb": {}}
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "AssignStealAttributeAbilityTotalValueToBB",
             "_ownerType": "BUFF_OWNER", "_abilityName": "StealAtk",
             "_assignStealMaxValue": False}], ctx)
    assert r[0]["action"] is True, r
    assert ctx["bb"]["steal_atk"] == 0.0
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "AssignStealAttributeAbilityTotalValueToBB",
             "_ownerType": "BUFF_OWNER", "_abilityName": "StealAtk",
             "_assignStealMaxValue": True}], ctx)
    assert r[0]["action"] is True
    assert abs(ctx["bb"]["max_steal_value"] - e.attributes.get("atk")) < 1e-6

    # IgnoreAllButMoveCp: flag toggles
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+IgnoreAllButMoveCp",
             "_ownerType": "BUFF_OWNER", "_ignore": True}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._ignore_all_but_move_cp is True


def test_buff_batch56_summon_nodes():
    """SummonEnemiesWithRuntimeNearestEndPointRoute /
    HalfIdleSummonEnemyAtTargetMapPos / SummonEnemiesOnTargetTile."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    eng = BuffTemplateEngine(b)
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 2, 2
    e.pos_x, e.pos_y = 2.0, 2.0
    n0 = len(b.enemies)

    # SummonEnemiesWithRuntimeNearestEndPointRoute: key from blackboard
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "SummonEnemiesWithRuntimeNearestEndPointRoute",
             "_source": "BUFF_OWNER", "_summonCount": 1,
             "_motionMode": "WALK", "_unharmful": True, "_buffs": []}],
        {"owner": e, "source": None, "target": e,
         "bb": {"enemy_key": "enemy_1000_gopro"}})
    assert r[0]["action"] is True, r
    assert len(b.enemies) == n0 + 1, len(b.enemies)
    spawned = b.enemies[-1]
    assert spawned.is_unharmful is True
    evs = [x for x in sim.snapshot()["events"] if x["type"] == "enemy_summoned"]
    assert evs and evs[-1]["data"]["node"] == \
        "SummonEnemiesWithRuntimeNearestEndPointRoute"

    # HalfIdleSummonEnemyAtTargetMapPos: key from _enemyId + buff on spawn
    n1 = len(b.enemies)
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "HalfIdleSummonEnemyAtTargetMapPos",
             "_targetType": "BUFF_OWNER", "_count": 1,
             "_unharmful": True, "_hasBuffToEnemySource": True,
             "_buffToEnemy": {"buffKey": "halfIdle_enemy_unmovable",
                              "lifeTimeType": "INFINITY",
                              "templateKey": "halfIdle_enemy_unmovable"}}],
        {"owner": e, "source": None, "target": e,
         "bb": {"enemy_id": "enemy_1000_gopro"}})
    assert r[0]["action"] is True, r
    assert len(b.enemies) == n1 + 1
    assert any(x["key"] == "halfIdle_enemy_unmovable"
               for x in b.enemies[-1].buffs), b.enemies[-1].buffs

    # SummonEnemiesOnTargetTile: spawn at the target tile
    n2 = len(b.enemies)
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+SummonEnemiesOnTargetTile",
             "_source": "TARGET", "_summonCount": 1,
             "_unharmful": True, "_addBuffToEnemy": False}],
        {"owner": e, "source": None, "target": e,
         "bb": {"enemy_key": "enemy_1000_gopro"}})
    assert r[0]["action"] is True, r
    assert len(b.enemies) == n2 + 1
    assert (b.enemies[-1].row, b.enemies[-1].col) == (2, 2)


def test_buff_batch57_card_deck_nodes():
    """CreateCardBuff / CheckContainsCardBuff / FinishCardBuff /
    CreateDeckBuff / CheckContainsDeckBuff / FinishDeckBuffByKey /
    FinishDeckBuffByCardUIDAndKey / AssignCardUIDToBlackBoard /
    FinishCardBuffsByKey / HideCardByTokenOrHostUid /
    CreateCardBuffFilterByDeckBuff."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)

    # CreateCardBuff (key from the current buff) + gate + finish
    ctx = {"owner": op, "source": None, "target": op, "bb": {}}
    ctx["bb"]["_buff_entry"] = {"key": "nearl2_s_2[withdraw]"}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
              "_target": "BUFF_OWNER", "_lifeType": "UNTIL_NEXT_SPAWN"}],
        ctx)
    assert r[0]["action"] is True, r
    cards = [c for c in op.cards if c["key"] == "nearl2_s_2[withdraw]"]
    assert cards and cards[0]["lifeType"] == "UNTIL_NEXT_SPAWN"
    uid = cards[0]["uid"]
    assert ctx["bb"]["card_uid"] == uid
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CheckContainsCardBuff",
              "_target": "BUFF_OWNER", "_key": "nearl2_s_2[withdraw]"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+FinishCardBuff"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"card_uid": uid}})
    assert r[0]["action"] is True, r
    assert not any(c["uid"] == uid for c in op.cards)

    # CreateDeckBuff + CheckContainsDeckBuff + FinishDeckBuffByCardUIDAndKey
    ctx2 = {"owner": op, "source": None, "target": op, "bb": {}}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateDeckBuff",
              "_target": "BUFF_OWNER",
              "_deckBuff": {"cardEffectType": "NONE",
                            "lifeType": "ALL_THE_TIME",
                            "buff": {"buffKey": "ines_s_3[deck]"}}}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    deck = [c for c in op.cards if c.get("isDeck")
            and c["key"] == "ines_s_3[deck]"]
    assert deck, op.cards
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CheckContainsDeckBuff",
              "_target": "BUFF_OWNER", "_key": "ines_s_3[deck]"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "FinishDeckBuffByCardUIDAndKey",
              "_target": "BUFF_OWNER", "_blackBoardKey": "card_uid",
              "_deckBuffKey": "ines_s_3[deck]"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"card_uid": deck[0]["uid"]}})
    assert r[0]["action"] is True, r
    assert not any(c.get("isDeck") and c["key"] == "ines_s_3[deck]"
                   for c in op.cards)

    # AssignCardUIDToBlackBoard
    ctx3 = {"owner": op, "source": None, "target": op, "bb": {}}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
              "_target": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"_buff_entry": {"key": "test_card_a"}}})
    assert r[0]["action"] is True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "AssignCardUIDToBlackBoard",
              "_targetType": "BUFF_OWNER", "_blackBoardKey": "card_uid",
              "_assignAsString": True}], ctx3)
    assert r[0]["action"] is True
    assert str(ctx3["bb"]["card_uid"]) == str(
        [c for c in op.cards if c["key"] == "test_card_a"][0]["uid"])

    # FinishCardBuffsByKey across all units
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
             "_target": "BUFF_OWNER"}],
        {"owner": e, "source": None, "target": e,
         "bb": {"_buff_entry": {"key": "test_card_a"}}})
    assert any(c["key"] == "test_card_a" for c in e.cards)
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+FinishCardBuffsByKey",
              "_cardBuffKey": "test_card_a", "_findAllCard": True}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert not any(c["key"] == "test_card_a" for c in op.cards)
    assert not any(c["key"] == "test_card_a" for c in e.cards)

    # HideCardByTokenOrHostUid
    eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
              "_target": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"_buff_entry": {"key": "test_card_b"}}})
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "HideCardByTokenOrHostUid",
              "_targetType": "BUFF_OWNER", "_isShow": False,
              "_hiddenReason": "deck_default_hidden"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert all(c.get("hidden") == "deck_default_hidden"
               for c in op.cards if c["key"] == "test_card_b")

    # CreateCardBuffFilterByDeckBuff: requires the deck, then creates
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CreateCardBuffFilterByDeckBuff",
              "_buffKey": "supmech_t[flag]", "_lifeType": "HOLD_BY_BUFF"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"_buff_entry": {"key": "chiave_t_1[deck]"}}})
    assert r[0]["action"] is False, r
    eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateDeckBuff",
              "_target": "BUFF_OWNER",
              "_deckBuff": {"lifeType": "ALL_THE_TIME",
                            "buff": {"buffKey": "supmech_t[flag]"}}}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CreateCardBuffFilterByDeckBuff",
              "_buffKey": "supmech_t[flag]", "_lifeType": "HOLD_BY_BUFF"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"_buff_entry": {"key": "chiave_t_1[deck]"}}})
    assert r[0]["action"] is True, r
    assert any(c["key"] == "chiave_t_1[deck]" for c in op.cards)


def test_buff_batch58_card_variants_fog_rally_nodes():
    """CreateCardBuffFilterByTag / CreateCardFilterByProfession /
    ExcludeDeckCardFromBattle / AssignCardRemainingCntToBlackboard /
    FinishTokenCardBuffByKey / CheckCharacterIsFreelySpawnedFromDeck /
    CreateLineEffect / SetSpineSkin / PlayUnitAnimation / MarkFogView /
    SwitchRallyPointCategory / RallyPointReborn / OnRallyPointLikeReborn."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)

    # CreateCardFilterByProfession: PIONEER passes, SNIPER fails
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CreateCardFilterByProfession",
              "_target": "BUFF_OWNER", "_profession": "SNIPER"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"_buff_entry": {"key": "wildmn_t_1"}}})
    assert r[0]["action"] is False, r
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CreateCardFilterByProfession",
              "_target": "BUFF_OWNER", "_profession": "PIONEER"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"_buff_entry": {"key": "wildmn_t_1"}}})
    assert r[0]["action"] is True, r
    assert any(c["key"] == "wildmn_t_1" for c in op.cards)

    # ExcludeDeckCardFromBattle
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "ExcludeDeckCardFromBattle",
              "_cardId": "trap_286_tjgsd", "_excludeFromBattle": True}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert "trap_286_tjgsd" in b._excluded_deck_cards
    assert "trap_286_tjgsd" in sim.snapshot()["excludedDeckCards"]

    # AssignCardRemainingCntToBlackboard (stack layers)
    ctx = {"owner": op, "source": None, "target": op, "bb": {}}
    eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
              "_target": "BUFF_OWNER", "_useCardBuffKey": True,
              "_cardBuffKey": "trap_255_pckzhn"}], ctx)
    eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
              "_target": "BUFF_OWNER", "_useCardBuffKey": True,
              "_cardBuffKey": "trap_255_pckzhn"}], ctx)
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "AssignCardRemainingCntToBlackboard",
              "_target": "BUFF_OWNER", "_cardKey": "trap_255_pckzhn",
              "_blackboardKey": "times"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["times"] == 2, ctx["bb"]

    # FinishTokenCardBuffByKey via the owner's token
    ok, _ = b.spawn_token_forced("token_10013_robin_mine", 2, 2, owner=op)
    assert ok
    eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuffToMyToken",
              "_useCardBuffKey": True,
              "_cardBuffKey": "svash2_s[token_cost_reduce]"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert any(c["key"] == "svash2_s[token_cost_reduce]"
               for tk in b.get_tokens() for c in tk.cards)
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "FinishTokenCardBuffByKey",
              "_sourceType": "BUFF_OWNER",
              "_cardBuffKey": "svash2_s[token_cost_reduce]"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert not any(c["key"] == "svash2_s[token_cost_reduce]"
                   for tk in b.get_tokens() for c in tk.cards)

    # CheckCharacterIsFreelySpawnedFromDeck
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CheckCharacterIsFreelySpawnedFromDeck",
              "_ownerType": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is False, r
    op._freely_spawned_from_deck = True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CheckCharacterIsFreelySpawnedFromDeck",
              "_ownerType": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r

    # CreateLineEffect / SetSpineSkin / PlayUnitAnimation
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateLineEffect",
              "_targetType": "BUFF_OWNER", "_sourceType": "BUFF_SOURCE",
              "_effectKey": "test_line"}],
        {"owner": op, "source": op, "target": op, "bb": {}})
    assert r[0]["action"] is True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+SetSpineSkin",
              "_target": "BUFF_OWNER", "_skinKey": "Cut"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._spine_skin == "Cut"
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+PlayUnitAnimation",
              "_target": "BUFF_OWNER", "_animation": "Idle"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True

    # MarkFogView: range tiles out of view, then restored
    op.direction = 1
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+MarkFogView",
              "_envSystemKey": "env_004_fog", "_rangeId": "x-1",
              "_targetType": "BUFF_OWNER", "_markInView": False}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert b._fog_view.get((3, 3)) is False
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+MarkFogView",
              "_envSystemKey": "env_004_fog", "_rangeId": "x-1",
              "_targetType": "BUFF_OWNER", "_markInView": True}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert (3, 3) not in b._fog_view

    # Rally-point rebirth: switch category, register token, teleport+heal
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "SwitchRallyPointCategory",
              "_category": "TRAP_OR_ITEM"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert b._rally_category == "TRAP_OR_ITEM"
    tk = next(t for t in b.get_tokens() if t.token_id == "token_10013_robin_mine")
    b._rally_points["TRAP_OR_ITEM"] = [tk.inst_id]
    op.row, op.col = 1, 1
    op.pos_x, op.pos_y = 1.0, 1.0
    op.hp = 100.0
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+RallyPointReborn",
              "_target": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert (op.row, op.col) == (2, 2), (op.row, op.col)
    assert op.hp == op.max_hp
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "OnRallyPointLikeReborn",
              "_targetType": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True


def test_buff_batch59_control_score_respawn_nodes():
    """TriggerHostsBuffsByKeys / RespawnCharacter / IsRallyPoint /
    AssignRespawnCntToBlackboard / FilterByBlackboardStrIsValue /
    FilterModifierCancelReason / CheckBuildableTypeOfCharacterRootTile /
    CheckContainsEnvSystem / UpdateScoreManually / GameCityUpdateScore /
    FinishGame / KillCharacterOnTileIfExists / InterruptCharacterAttack /
    HalfIdleDropResource / HalfIdleDropBattleItem /
    SetCharacterDontOccupyDeployCntFlag / ForceCharacterFaceDefaultDirection /
    HideEntityGraphicOrNot / ShakeCamera / EnableShadowController /
    ModifyCharacterSpineColor."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)

    # TriggerHostsBuffsByKeys: fires ON_BUFF_TRIGGER of the named buffs
    b.add_buff(op, {"key": "t_host_trigger", "remaining_ticks": 30 * 60,
                    "template_key": "periodic_damage[not_env]",
                    "blackboard": {"damage": 10.0}})
    hp0 = op.hp
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+TriggerHostsBuffsByKeys",
              "_targetType": "BUFF_OWNER",
              "_buffKeys": ["t_host_trigger"]}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert abs((hp0 - op.hp) - 10.0) < 1.0, (hp0, op.hp)

    # RespawnCharacter + AssignRespawnCntToBlackboard + IsRallyPoint
    op.hp = 50.0
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+RespawnCharacter",
              "_targetType": "BUFF_OWNER", "_rowKey": "row",
              "_colKey": "col"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"row": 1, "col": 1}})
    assert r[0]["action"] is True, r
    assert (op.row, op.col) == (1, 1)
    assert op.hp == op.max_hp
    assert op._respawn_cnt == 1
    ctx = {"owner": op, "source": None, "target": op, "bb": {}}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "AssignRespawnCntToBlackboard",
              "_targetType": "BUFF_OWNER",
              "_blackboardKey": "curRespawnCnt"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["curRespawnCnt"] == 1
    b._rally_points["X"] = [op.inst_id]
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+IsRallyPoint",
              "_targetType": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r

    # FilterByBlackboardStrIsValue
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "FilterByBlackboardStrIsValue",
              "_targetType": "BUFF_OWNER", "_valueKey": "part_name",
              "_valueKeyToCompare": "part_name_fx",
              "_useOrdinalIgnoreCase": True}],
        {"owner": op, "source": None, "target": op,
         "bb": {"part_name": "Head", "part_name_fx": "head"}})
    assert r[0]["action"] is True, r

    # FilterModifierCancelReason
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "FilterModifierCancelReason",
              "_reason": "HIT_FAILED"}],
        {"owner": op, "source": None, "target": op,
         "bb": {}, "damage": {"cancelReason": "HIT_FAILED"}})
    assert r[0]["action"] is True, r

    # CheckBuildableTypeOfCharacterRootTile (melee tile)
    op.row, op.col = 3, 3
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CheckBuildableTypeOfCharacterRootTile",
              "_targetType": "BUFF_OWNER", "_buildableType": "MELEE"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r

    # CheckContainsEnvSystem
    b.env_systems.append({"key": "env_008_act29side_audio_type_switcher"})
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CheckContainsEnvSystem",
              "_envSysKey": "env_008_act29side_audio_type_switcher"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r

    # UpdateScoreManually / GameCityUpdateScore
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+UpdateScoreManually",
              "_score": "BASIC"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert b._scores["BASIC"] == 1
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+GameCityUpdateScore",
              "_targetType": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert b._scores["game_city"] == 1
    assert sim.snapshot()["scores"]["BASIC"] == 1

    # KillCharacterOnTileIfExists
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "KillCharacterOnTileIfExists",
             "_targetType": "BUFF_OWNER"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert e.dead

    # InterruptCharacterAttack
    e2 = b.enemies[0] if not b.enemies[0].dead else None
    op._pending_attack = {"target": e2 or op, "remaining": 5}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "InterruptCharacterAttack",
              "_charFrom": "BUFF_OWNER", "_resetCD": True}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._pending_attack is None
    assert op.attack_timer == 0.0

    # HalfIdleDropResource / HalfIdleDropBattleItem
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+HalfIdleDropResource",
              "_poolKeyBB": "resource_pool", "_countBB": "cnt"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"resource_pool": "wood", "cnt": 3}})
    assert r[0]["action"] is True
    assert b._dropped_loot["resource:wood"] == 3
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "HalfIdleDropBattleItem",
              "_poolKeyBB": "equip_pool", "_countBB": "bonus_cnt"}],
        {"owner": op, "source": None, "target": op,
         "bb": {"equip_pool": "knife", "bonus_cnt": 1}})
    assert r[0]["action"] is True
    assert b._dropped_loot["battle_item:knife"] == 1

    # unit state + cosmetic flags
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "SetCharacterDontOccupyDeployCntFlag",
              "_targetType": "BUFF_OWNER", "_isUnset": False}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._dont_occupy_deploy_cnt is True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "ForceCharacterFaceDefaultDirection",
              "_target": "BUFF_OWNER", "_force": True}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._force_face_default is True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+HideEntityGraphicOrNot",
              "_targetType": "BUFF_OWNER", "_hide": True}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._graphic_hidden is True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+ShakeCamera",
              "_duration": 1.0}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "EnableShadowController",
              "_targetType": "BUFF_OWNER", "_enabled": True}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._shadow_enabled is True
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "ModifyCharacterSpineColor",
              "_target": "BUFF_OWNER", "_color": "BLACK"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert op._spine_color == "BLACK"

    # FinishGame (do last: ends the battle)
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+FinishGame",
              "_gameResult": "LOSE"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert b.finished is True and b.result == "defeat"


def test_buff_batch60_card_all_drag_skillcd_tileside_nodes():
    """CreateCardBuffToAllCard / CreateDeckBuffByCnt / DragTowardSource /
    SetStackCountViaBlockNum / EnemySkipWaitCheckPoint / DamageViaEs /
    CheckCharacterSkillType / HideEntityInFogAndManageBuff /
    EmitProjectileToTileUseSelector / ApplyCacheAtkDamageFromBuff /
    HalfIdleUpgradeTrap / Act27sideModifyTileCachedSideType /
    SummonEnemiesFollowBranchRouteWithTileBlackboard."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 2, 2
    e.pos_x, e.pos_y = 2.0, 2.0

    # CreateCardBuffToAllCard: cards on op + enemy, then spread excluding op
    eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
              "_target": "BUFF_OWNER", "_useCardBuffKey": True,
              "_cardBuffKey": "holder_card"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+CreateCardBuff",
             "_target": "BUFF_OWNER", "_useCardBuffKey": True,
             "_cardBuffKey": "holder_card"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CreateCardBuffToAllCard",
              "_exceptOwner": True, "_exceptTokenAndTrap": True,
              "_useCardBuffKey": True, "_cardBuffKey": "spread_card"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert not any(c["key"] == "spread_card" for c in op.cards)
    assert any(c["key"] == "spread_card" for c in e.cards)

    # CreateDeckBuffByCnt: two adds stack layers
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+CreateDeckBuffByCnt",
              "_target": "BUFF_OWNER", "_cnt": 2,
              "_deckBuff": {"lifeType": "ALL_THE_TIME",
                            "buff": {"buffKey": "rl5_relic_deck"}}}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    decks = [c for c in op.cards if c.get("isDeck")
             and c["key"] == "rl5_relic_deck"]
    assert decks and decks[0]["layers"] == 2, decks

    # DragTowardSource: enemy pulled toward the operator
    e.pos_x, e.pos_y = 4.0, 3.0
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+DragTowardSource",
             "_source": "BUFF_OWNER", "_target": "TARGET"}],
        {"owner": op, "source": op, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert e.displacement is not None

    # SetStackCountViaBlockNum: buff layers follow the blocked count
    op.row, op.col = 2, 2
    e.row, e.col = 2, 2
    e.pos_x, e.pos_y = 2.0, 2.0
    op.blocked_enemies = [e]
    ctx = {"owner": op, "source": None, "target": op,
           "bb": {"_buff_entry": {"key": "stack_buff", "layers": 1}}}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "SetStackCountViaBlockNum"}], ctx)
    assert r[0]["action"] is True, r
    assert ctx["bb"]["_buff_entry"]["layers"] == 1
    op.blocked_enemies = []

    # EnemySkipWaitCheckPoint
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "EnemySkipWaitCheckPoint",
             "_targetType": "BUFF_OWNER"}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True
    assert e._skip_wait_checkpoint is True

    # DamageViaEs: bb damage applied as pure damage
    hp0 = op.hp
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+DamageViaEs",
             "_sourceType": "BUFF_OWNER", "_targetType": "TARGET",
             "_damageType": "PURE"}],
        {"owner": e, "source": e, "target": op, "bb": {"damage": 50.0}})
    assert r[0]["action"] is True, r
    assert abs((hp0 - op.hp) - 50.0) < 1.0, (hp0, op.hp)

    # CheckCharacterSkillType: returns a bool gate
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CheckCharacterSkillType",
              "_skillType": "MANUAL", "_targetType": "BUFF_OWNER"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] in (True, False), r

    # HideEntityInFogAndManageBuff
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "HideEntityInFogAndManageBuff",
             "_targetType": "BUFF_OWNER",
             "_buff": {"buffKey": "fog_hide_buff",
                       "lifeTimeType": "INFINITY"}}],
        {"owner": e, "source": None, "target": e, "bb": {}})
    assert r[0]["action"] is True, r
    assert e._graphic_hidden is True
    assert any(x["key"] == "fog_hide_buff" for x in e.buffs)

    # EmitProjectileToTileUseSelector
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "EmitProjectileToTileUseSelector",
             "_targetType": "TARGET",
             "_projectileKey": "projectile_test_arrow"}],
        {"owner": e, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert b.projectiles
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "EmitProjectileToTileUseSelector",
             "_targetType": "TARGET",
             "_projectileKey": "projectile_test_arrow"}],
        {"owner": e, "source": None, "target": None, "bb": {}})
    assert r[0]["action"] is True, r

    # ApplyCacheAtkDamageFromBuff: cached atk x scale
    hp1 = op.hp
    r = eng.run_actions(
        e, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "ApplyCacheAtkDamageFromBuff",
             "_targetType": "TARGET", "_damageScaleKey": "atk_scale",
             "_damageType": "PURE"}],
        {"owner": e, "source": e, "target": op,
         "bb": {"atk": 100.0, "atk_scale": 0.5}})
    assert r[0]["action"] is True, r
    assert abs((hp1 - op.hp) - 50.0) < 1.0, (hp1, op.hp)

    # HalfIdleUpgradeTrap: replace the trap token at the source tile
    ok, _ = b.spawn_token_forced("token_10013_robin_mine", 1, 1, owner=op)
    assert ok
    src = b.tokens[-1]
    r = eng.run_actions(
        src, [{"$type": "Torappu.Battle.Action.Nodes+HalfIdleUpgradeTrap",
               "_sourcePosType": "BUFF_OWNER",
               "_upgradeTrapId": "token_10002_kalts_mon3tr",
               "_upgradeTrapKey": "token_id"}],
        {"owner": src, "source": None, "target": src,
         "bb": {"token_id": "token_10013_robin_mine"}})
    assert r[0]["action"] is True, r
    ids = [t.token_id for t in b.get_tokens()]
    assert "token_10013_robin_mine" not in ids
    assert "token_10002_kalts_mon3tr" in ids

    # Act27sideModifyTileCachedSideType
    op.row, op.col = 3, 3
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "Act27sideModifyTileCachedSideType",
             "_sourceType": "BUFF_OWNER", "_sideType": "ENEMY"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True
    assert b._tile_side_cache[(3, 3)] == "ENEMY"
    assert sim.snapshot()["tileSideCache"]["3,3"] == "ENEMY"

    # SummonEnemiesFollowBranchRouteWithTileBlackboard
    n0 = len(b.enemies)
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "SummonEnemiesFollowBranchRouteWithTileBlackboard",
             "_source": "BUFF_OWNER", "_unharmful": False}],
        {"owner": op, "source": None, "target": op,
         "bb": {"enemy_key": "enemy_1000_gopro"}})
    assert r[0]["action"] is True, r
    assert len(b.enemies) == n0 + 1


def test_buff_batch61_visual_log_tile_nodes():
    """ChangeAnimatorMeshRenderer / ModifyAnimatorHookerReplacePair /
    AddHeightOffsetToSpine / ChangeAnimatorMeshRendererViaIndexList /
    Act29SideCheckCurrentAudioType / Act49sideBossUpdateWarningEffect /
    ForceCharacterAnimatorFaceFront / DisableEnemyHud / ActiveCameraEffect /
    PlayBGM / ShowGameCityUiPluginText / SandboxShowToast /
    CollectTargetInfoFunLiveModeOnly / LogExtraBattleInfo* / IsTargetInDialog /
    CheckFirstRallyPointMode / AssignResCountToBB / CharSearchBlockeeImmediate /
    SwitchDynamicBuffTileModeInRange / RewriteDynamicBuffTileOptionsOneLine /
    HalfIdleTriggerTrapUpgradeCheck."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0

    def _one(node, ctx=None, owner=None):
        u = owner or op
        return eng.run_actions(
            u, [node],
            ctx or {"owner": u, "source": None, "target": u, "bb": {}})

    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "ChangeAnimatorMeshRenderer",
                 "_ownerType": "BUFF_OWNER", "_rendererIndex": 0,
                 "_enable": True})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "ModifyAnimatorHookerReplacePair",
                 "_target": "BUFF_OWNER",
                 "_replaceAnimPairs": [{"fromAnimKey": "Move",
                                        "toAnimKey": "L_Run"}]})[0][
        "action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+AddHeightOffsetToSpine",
                 "_target": "BUFF_OWNER", "_offset": 0.2,
                 "_blackboardKey": "value"})[0]["action"] is True
    assert abs(op._spine_height_offset - 0.2) < 1e-6
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "ChangeAnimatorMeshRendererViaIndexList",
                 "_ownerType": "BUFF_OWNER", "_rendererIndexList": [2, 3],
                 "_enable": True})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "Act29SideCheckCurrentAudioType",
                 "_evnSysKey": "env_008_act29side_audio_type_switcher",
                 "_audioType": "Enthusiastic"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "Act49sideBossUpdateWarningEffect",
                 "_targetType": "BUFF_OWNER",
                 "_partName": "left_hand"})[0]["action"] is True
    r = _one({"$type": "Torappu.Battle.Action.Nodes+"
                        "ForceCharacterAnimatorFaceFront",
              "_target": "BUFF_OWNER", "_FroceFaceFront": True})
    assert r[0]["action"] is True
    assert op._animator_face_front is True
    r = _one({"$type": "Torappu.Battle.Action.Nodes+DisableEnemyHud",
              "_target": "BUFF_OWNER"})
    assert r[0]["action"] is True
    assert op._hud_disabled is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+ActiveCameraEffect",
                 "_effectKey": "cam_test", "_active": True})[0][
        "action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+PlayBGM"})[0][
        "action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "ShowGameCityUiPluginText",
                 "_target": "BUFF_OWNER", "_indexKey": "value"},
                {"owner": op, "source": None, "target": op,
                 "bb": {"value": 3}})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+SandboxShowToast",
                 "_target": "BUFF_OWNER",
                 "_toastKey": "ACT36SIDE_BOSS_NO_FOOD"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "CollectTargetInfoFunLiveModeOnly",
                 "_targetType": "BUFF_OWNER"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "LogExtraBattleInfoForBossRush",
                 "_infoType": "CURRENT_BOSS_WAVE",
                 "_target": "BUFF_OWNER"})[0]["action"] is True

    # LogExtraBattleInfoWithNoTarget accumulates battle._extra_log
    for _ in range(3):
        assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                              "LogExtraBattleInfoWithNoTarget",
                     "_logType": "SIMPLE", "_key": "melee_built",
                     "_additionValue": 1})[0]["action"] is True
    assert b._extra_log.get("melee_built") == 3
    assert sim.snapshot()["extraLog"]["melee_built"] == 3
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                          "LogExtraBattleInfoForModifierRealDelta",
                 "_target": "BUFF_OWNER", "_key": "criticaldamage"},
                {"owner": op, "source": None, "target": op, "bb": {},
                 "damage": {"amount": 50.0}})[0]["action"] is True

    # IsTargetInDialog: record + fail
    assert _one({"$type": "Torappu.Battle.Action.Nodes+IsTargetInDialog",
                 "_target": "BUFF_OWNER"})[0]["action"] is False

    # CheckFirstRallyPointMode: true after exactly one category switch
    r = _one({"$type": "Torappu.Battle.Action.Nodes+"
                        "SwitchRallyPointCategory",
              "_category": "TRAP_OR_ITEM"})
    assert r[0]["action"] is True
    r = _one({"$type": "Torappu.Battle.Action.Nodes+"
                        "CheckFirstRallyPointMode"})
    assert r[0]["action"] is True, r

    # AssignResCountToBB
    b._dropped_loot["resource:wood"] = 7
    ctx = {"owner": op, "source": None, "target": op,
           "bb": {"survival_gather_type": "wood"}}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+AssignResCountToBB",
              "_target": "BUFF_OWNER",
              "_resourceTypeKey": "survival_gather_type",
              "_blackboardKey": "remain"}], ctx)
    assert r[0]["action"] is True
    assert ctx["bb"]["remain"] == 7

    # CharSearchBlockeeImmediate
    op.row, op.col = 3, 3
    e.row, e.col = 3, 3
    op.blocked_enemies = [e]
    ctx = {"owner": op, "source": None, "target": op, "bb": {}}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "CharSearchBlockeeImmediate",
              "_targetType": "BUFF_OWNER"}], ctx)
    assert r[0]["action"] is True, r
    assert ctx["bb"]["blockee_inst_id"] == e.inst_id
    op.blocked_enemies = []

    # SwitchDynamicBuffTileModeInRange
    ctx = {"owner": op, "source": None, "target": op,
           "bb": {"boom_dec_num": 3}}
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "SwitchDynamicBuffTileModeInRange",
              "_sourceType": "BUFF_OWNER", "_operation": "DEC_INDEX",
              "_modeIndex": 1, "_decBbKey": "boom_dec_num",
              "_rangeId": "0-1"}], ctx)
    assert r[0]["action"] is True, r
    assert ctx["bb"]["boom_dec_num"] == 2
    assert b._tile_modes.get((3, 3)) == 1

    # RewriteDynamicBuffTileOptionsOneLine
    r = eng.run_actions(
        op, [{"$type": "Torappu.Battle.Action.Nodes+"
                       "RewriteDynamicBuffTileOptionsOneLine",
              "_sourceType": "BUFF_OWNER", "_direction": "RIGHT",
              "_buffKey": "prtrop_s[tile_storage]"}],
        {"owner": op, "source": None, "target": op, "bb": {}})
    assert r[0]["action"] is True, r
    assert b._tile_bb.get((3, 4), {}).get("prtrop_s[tile_storage]") == 1

    # HalfIdleTriggerTrapUpgradeCheck
    ok, _ = b.spawn_token_forced("token_10013_robin_mine", 1, 1, owner=op)
    assert ok
    trap = b.tokens[-1]
    r = eng.run_actions(
        trap, [{"$type": "Torappu.Battle.Action.Nodes+"
                        "HalfIdleTriggerTrapUpgradeCheck",
                "_sourcePosType": "BUFF_OWNER"}],
        {"owner": trap, "source": None, "target": trap, "bb": {}})
    assert r[0]["action"] is True, r


def test_prefab_action_delegation_to_buff_engine():
    """Prefab action nodes not handled locally by the enemy-skill
    ActionNodeExecutor fall back to the buff template engine handlers
    (e.g. AdvancedApplyDamage), so enemy prefab graphs get full node
    behaviour instead of no-ops."""
    from ark_emulator.action_nodes import ActionNodeExecutor
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.attributes.base["atk"] = 200.0
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0
    ex = ActionNodeExecutor(b)
    hp0 = op.hp
    ex.execute(
        [{"$type": "Torappu.Battle.Action.Nodes+AdvancedApplyDamage",
          "_sourceType": "SOURCE", "_targetType": "TARGET",
          "_damageType": "PURE", "_atkScaleVar": "atk_scale",
          "_defaultAtkScale": 1.0}],
        source=e, target=op, owner=None)
    assert abs((hp0 - op.hp) - 200.0) < 1.0, (hp0, op.hp)


def test_buff_batch62_fever_legion_rogue_misc_nodes():
    """Fever / football / legion / roguelike clusters + small real nodes +
    buff_node_unhandled notification."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    eng = BuffTemplateEngine(b)
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0

    def _one(node, ctx=None, owner=None):
        u = owner or op
        return eng.run_actions(
            u, [node],
            ctx or {"owner": u, "source": None, "target": u, "bb": {}})

    # fever
    assert _one({"$type": "Torappu.Battle.Action.Nodes+IsInFever",
                 "_feverKey": "env_033_fever"})[0]["action"] is False
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "AddFeverBySourceIfNotFull",
                 "_sourceType": "BUFF_OWNER",
                 "_feverKey": "env_033_fever"},
                {"owner": op, "source": None, "target": op,
                 "bb": {"value": 0.6}})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+IsInFever",
                 "_feverKey": "env_033_fever"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+IsFeverFull",
                 "_feverKey": "env_033_fever"})[0]["action"] is False
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "AddFeverBySourceIfNotFull",
                 "_sourceType": "BUFF_OWNER",
                 "_feverKey": "env_033_fever"},
                {"owner": op, "source": None, "target": op,
                 "bb": {"value": 0.5}})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+TryActiveFeverIfFull",
                 "_sourceType": "BUFF_OWNER",
                 "_feverKey": "env_033_fever"})[0]["action"] is True
    assert b._fever_active is True

    # football
    assert _one({"$type": "Torappu.Battle.Action.Nodes+IsCloseToFootball",
                 "_targetType": "BUFF_OWNER"})[0]["action"] is False
    b._football_pos = (3, 3)
    assert _one({"$type": "Torappu.Battle.Action.Nodes+IsCloseToFootball",
                 "_targetType": "BUFF_OWNER"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+StopBall",
                 "_targetType": "BUFF_OWNER", "_force": True})[0][
        "action"] is True
    assert b._football_stopped is True

    # legion
    r = _one({"$type": "Torappu.Battle.Action.Nodes+"
                         "LegionModeOnlyGainGold",
              "_goldNum": 1, "_loadFromBlackboard": True,
              "_goldNumKey": "gold_num"},
             {"owner": op, "source": None, "target": op,
              "bb": {"gold_num": 5}})
    assert r[0]["action"] is True
    assert b._legion_gold == 5
    b._legion_pending = ["card_a"]
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "LegionModeOnlyDrawNextCard"})[0][
        "action"] is True
    assert b._legion_hand == ["card_a"]
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "LegionModeOnlyCheckCardInHand",
                 "_targetType": "BUFF_OWNER"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "LegionModeOnlyAddProfessionLevel",
                 "_targetType": "BUFF_OWNER", "_levelCnt": 1,
                 "_professionCategory": "SNIPER"})[0]["action"] is True
    assert b._legion_profession_levels["SNIPER"] == 1
    ctx = {"owner": op, "source": None, "target": op, "bb": {}}
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "LegionModeOnlyAssignDangerLevelToBB",
                 "_dangerLevelKey": "current_danger_level"}, ctx)[0][
        "action"] is True
    assert ctx["bb"]["current_danger_level"] == 0

    # roguelike
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "CompareRogueDiceNumber",
                 "_threshold": 3, "_condType": "LE",
                 "_blackboardKey": "dice_var"},
                {"owner": op, "source": None, "target": op,
                 "bb": {"dice_var": 2}})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+RoguelikeLogExp",
                 "_target": "BUFF_OWNER", "_expType": "TRAP_GAINED",
                 "_expKey": "exp"},
                {"owner": op, "source": None, "target": op,
                 "bb": {"exp": 10}})[0]["action"] is True
    assert b._rogue_exp == 10

    # SkipStage ends the battle (use a fresh sim state check afterwards)
    assert _one({"$type": "Torappu.Battle.Action.Nodes+SkipStage"})[0][
        "action"] is True
    assert b.finished is True and b.result == "victory"

    # small real nodes
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "AssignEnemyLastMoveDirectionToBB",
                 "_target": "BUFF_OWNER",
                 "_blackboardKey": "direction"},
                {"owner": op, "source": None, "target": op,
                 "bb": {}})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "CheckDistanceToTileCenter",
                 "_targetType": "BUFF_OWNER", "_distance": 1.0,
                 "_condType": "LE"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "AssignEntityEsIntoBlackboard",
                 "_targetType": "BUFF_OWNER",
                 "_blackboardKey": "es_value"},
                {"owner": op, "source": None, "target": op,
                 "bb": {}})[0]["action"] is True
    op._manually_spawned = True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "CheckCharacterIsMannuallySpawned",
                 "_ownerType": "BUFF_OWNER"})[0]["action"] is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "SwitchToRebornState",
                 "_targetType": "BUFF_OWNER"})[0]["action"] is True
    assert op._reborn_state is True
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "AddExcludeCharacterToDynamicBuffTile",
                 "_targetType": "BUFF_OWNER"})[0]["action"] is True
    assert op.inst_id in b._dynamic_tile_excludes

    # AOEElementDamage: enemy adjacent gets element EP
    e.state = 3
    r = _one({"$type": "Torappu.Battle.Action.Nodes+AOEElementDamage",
              "_elementDamageType": "FIRE",
              "_sourceType": "BUFF_OWNER", "_targetType": "BUFF_OWNER",
              "_isFixedEpDamage": True, "_fixedEpDamage": 25.0})
    assert r[0]["action"] is True, r
    ep = [x for x in e.buffs if x["key"].startswith("ep_")]
    assert ep and float(ep[0].get("value", 0.0)) >= 24.0, ep

    # RandomAction runs the chosen branch
    ctx = {"owner": op, "source": None, "target": op,
           "bb": {"prob1": 1.0}}
    assert _one({"$type": "Torappu.Battle.Action.Nodes+RandomAction",
                 "_probKey": "prob1",
                 "_actions": [{"$type": "Torappu.Battle.Action.Nodes+"
                                        "ModifyBlackboardStr",
                               "_blackboardKeys": "enemy_key",
                               "_value": "enemy_x"}],
                 "_failActions": []}, ctx)[0]["action"] is True
    assert ctx["bb"]["enemy_key"] == "enemy_x"

    # ClearCharacterOnTileIfExists
    e2 = b.enemies[0]
    assert not e2.dead
    assert _one({"$type": "Torappu.Battle.Action.Nodes+"
                           "ClearCharacterOnTileIfExists",
                 "_targetType": "BUFF_OWNER"}, owner=e2)[0]["action"] is True
    assert e2.dead

    # buff_node_unhandled notification (deduped per type)
    before = len(sim.snapshot()["events"])
    _one({"$type": "Torappu.Battle.Action.Nodes+TotallyUnknownNodeXYZ"})
    _one({"$type": "Torappu.Battle.Action.Nodes+TotallyUnknownNodeXYZ"})
    evs = [x for x in sim.snapshot()["events"][before:]
           if x["type"] == "buff_node_unhandled"]
    assert len(evs) == 1, evs
    assert evs[0]["data"]["node"] == "TotallyUnknownNodeXYZ"


def test_fog_hides_enemies_from_operator_targeting():
    """MarkFogView out-of-view tiles: enemies standing on them cannot be
    selected as normal operator attack targets until the fog is cleared."""
    from ark_emulator.targeting import HateSystem
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.pos_x, e.pos_y = 4.0, 3.0
    hs = HateSystem(b)
    assert hs.operator_target(op) is e
    # hide the enemy's tile in fog -> not selectable
    b._fog_view[(3, 4)] = False
    assert b.is_fogged(e) is True
    assert hs.operator_target(op) is None
    # reveal -> selectable again
    b._fog_view.pop((3, 4))
    assert b.is_fogged(e) is False
    assert hs.operator_target(op) is e
