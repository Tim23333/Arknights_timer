"""Enemy skill xLua action-node coverage for the high-frequency node
types (TriggerAbility / DamageViaMaxHpRatio / CreateBuffToBlockee /
EmitProjectile / TriggerBuffsByKeys / Withdraw / ModifyCost /
AssignValueToBB)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _setup():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 1000.0
    b.cost_increase_time = 1e7
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 5000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return sim, b, op, e


def _exec(b, node, source, target=None, owner=None):
    from ark_emulator.action_nodes import ActionNodeExecutor
    ex = ActionNodeExecutor(b)
    ex.execute([node], source=source, target=target, owner=owner)


def test_damage_via_max_hp_ratio():
    sim, b, op, e = _setup()
    hp0 = e.hp
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+DamageViaMaxHpRatio",
        "_targetType": "TARGET", "_damageType": "PURE",
        "_maxHpRatio": 0.25}, e, target=e)
    assert abs((hp0 - e.hp) - e.max_hp * 0.25) < 0.5, (hp0, e.hp)
    print("OK DamageViaMaxHpRatio", hp0 - e.hp)


def test_create_buff_to_blockee():
    sim, b, op, e = _setup()
    e.blocked_by = op
    op.add_blockee(e)
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+CreateBuffToBlockee",
        "_buff": {"buffKey": "crzjdg_m2_s1[block_damage]",
                  "loadFromDB": False}}, e)
    assert b.buffs.get(op, "crzjdg_m2_s1[block_damage]"), \
        "blocker must receive the buff"
    print("OK CreateBuffToBlockee")


def test_trigger_buffs_by_keys():
    sim, b, op, e = _setup()
    b.add_buff(e, {"key": "enemy_bqthie_buff_steal",
                   "template_key": "enemy_bqthie_buff_steal",
                   "remaining_ticks": 600, "layers": 1,
                   "source": op, "blackboard": {}})
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+TriggerBuffsByKeys",
        "_targetType": "TARGET",
        "_buffKeys": ["enemy_bqthie_buff_steal"]}, e, target=e)
    print("OK TriggerBuffsByKeys (no crash)")


def test_modify_cost_and_assign_bb():
    sim, b, op, e = _setup()
    owner = type("O", (), {"skill": type("S", (), {
        "blackboard": {"cost": 5.0}})()})()
    cost0 = b.cost
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+ModifyCost",
        "_blackboardKey": "cost"}, e, owner=owner)
    assert abs((b.cost - cost0) - 5.0) < 1e-6, b.cost - cost0
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+AssignValueToBB",
        "_blackboardKey": "xbchst[try_devour]", "_value": 1.0},
        e, owner=owner)
    assert owner.skill.blackboard.get("xbchst[try_devour]") == 1.0
    print("OK ModifyCost + AssignValueToBB")


def test_withdraw_source():
    sim, b, op, e = _setup()
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+Withdraw",
        "_withdrawSource": False, "_switchToDeadState": True,
        "_force": True}, e)
    assert getattr(e, "dead", False), "source must withdraw"
    print("OK Withdraw")


def test_summon_follow_my_route():
    sim, b, op, e = _setup()
    before = len(b.enemies)
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+SummonEnemiesFollowMyRoute",
        "_enemyKey": "enemy_1000_gopro", "_summonCount": 2,
        "_managedByScheduler": True}, e)
    assert len(b.enemies) - before == 2
    assert b.enemies[-1].route_index == getattr(e, "route_index", 0)
    print("OK SummonEnemiesFollowMyRoute")


def test_rebuild_character_on_random_tile():
    sim, b, op, e = _setup()
    e.dead = True
    e.hp = 0.0
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+RebuildCharacterOnRandomTile",
        "_target": "TARGET", "_createBuff": True,
        "_buff": {"buffKey": "enemy_ltniak[appear_effect]",
                  "loadFromDB": False}}, e, target=e)
    assert not e.dead and e.hp == e.max_hp
    assert b.buffs.get(e, "enemy_ltniak[appear_effect]")
    print("OK RebuildCharacterOnRandomTile")


def test_finish_several_buffs_by_id():
    sim, b, op, e = _setup()
    for k in ("enemy_pyczog_electrify[effect]",
              "enemy_pyczog_roar[atk]"):
        b.add_buff(e, {"key": k, "remaining_ticks": 600, "layers": 1,
                       "source": op, "blackboard": {}})
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+FinishSeveralBuffsById",
        "_targetType": "SOURCE",
        "_buffKeys": ["enemy_pyczog_electrify[effect]",
                      "enemy_pyczog_roar[atk]"]}, e)
    assert b.buffs.get(e, "enemy_pyczog_electrify[effect]") is None
    assert b.buffs.get(e, "enemy_pyczog_roar[atk]") is None
    print("OK FinishSeveralBuffsById")


def test_create_no_source_buff():
    sim, b, op, e = _setup()
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+CreateNoSourceBuff",
        "_buff": {"buffKey": "trap_shmbmb_damage", "loadFromDB": False}},
        e, target=e)
    assert b.buffs.get(e, "trap_shmbmb_damage")
    print("OK CreateNoSourceBuff")


def test_change_route_motion_mode():
    sim, b, op, e = _setup()
    from ark_emulator.action_nodes import ActionNodeExecutor
    ex = ActionNodeExecutor(b)
    orig = ex._dispatch
    seen = []
    def traced(ntype, node, source, target, owner):
        seen.append(ntype)
        return orig(ntype, node, source, target, owner)
    ex._dispatch = traced
    ex.execute([{
        "$type": "Torappu.Battle.Action.Nodes+ChangeEnemyRouteMotionMode",
        "_target": "TARGET", "_motionMode": "FLY"}],
        source=e, target=e, owner=None)
    assert seen, "dispatch never called"
    # 直接调 _dispatch 验证分支（绕过 execute 的 short 提取）
    node2 = {"$type": "Torappu.Battle.Action.Nodes+ChangeEnemyRouteMotionMode",
             "_target": "TARGET", "_motionMode": "FLY"}
    ex._dispatch(node2.get("$type"), node2, e, e, None)
    assert getattr(e, "_motion_mode", 0) == 1, \
        "direct dispatch failed: %s" % getattr(e, "_motion_mode", 0)
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+ChangeEnemyRouteMotionMode",
        "_target": "TARGET", "_motionMode": "FLY"}, e, target=e)
    assert getattr(e, "_motion_mode", 0) == 1, getattr(e, "_motion_mode", 0)
    print("OK ChangeEnemyRouteMotionMode")


def test_ifnot_and_check_abnormal():
    sim, b, op, e = _setup()
    # IfNot(CheckAbnormalFlag SILENCED unset): true when NOT silenced
    # 未沉默：Check(unset)=True → IfNot=False
    ok = _exec_cond(b, {
        "$type": "Torappu.Battle.Action.Nodes+IfNot",
        "_conditionNode": {
            "$type": "Torappu.Battle.Action.Nodes+CheckAbnormalFlag",
            "_abnormalFlag": "SILENCED", "_targetType": "TARGET",
            "_isUnset": True}}, e, target=e)
    assert not ok
    b.add_abnormal(e, 12, 5.0)     # silenced
    # 沉默后：Check(unset)=False → IfNot=True
    ok2 = _exec_cond(b, {
        "$type": "Torappu.Battle.Action.Nodes+IfNot",
        "_conditionNode": {
            "$type": "Torappu.Battle.Action.Nodes+CheckAbnormalFlag",
            "_abnormalFlag": "SILENCED", "_targetType": "TARGET",
            "_isUnset": True}}, e, target=e)
    assert ok2
    print("OK IfNot + CheckAbnormalFlag")


def test_assign_attribute_to_bb():
    sim, b, op, e = _setup()
    owner = type("O", (), {"skill": type("S", (), {"blackboard": {}})()})()
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+AssignAttributeToBB",
        "_targetType": "SOURCE", "_attributeType": "ATK",
        "_blackboardKey": "atk"}, e, owner=owner)
    assert abs(owner.skill.blackboard.get("atk", 0.0) -
               float(e.attributes.get("atk") or 0.0)) < 1e-6
    print("OK AssignAttributeToBB")


def test_aoe_damage_from_projectile():
    sim, b, op, e = _setup()
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 5000.0, "atk": 0.0, "def": 0.0},
        "row": e.row + 1, "col": e.col})
    e2 = b.enemies[-1]
    e2.state = EnemyState.COMBAT
    hp0 = e.hp
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+AOEDamageFromProjectile",
        "_damageType": "MAGICAL"}, op, target=e)
    assert hp0 - e.hp > 0
    print("OK AOEDamageFromProjectile")


def test_main15_and_log_extra_info():
    sim, b, op, e = _setup()
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+Main15TryNextPrtsAction",
        "_doNextWhenSuccess": True, "_forceNext": False}, e)
    assert any(x["type"] == "prts_try_next"
               for x in b.events.snapshot_events())
    _exec(b, {
        "$type": "Torappu.Battle.Action.Nodes+LogExtraBattleInfo",
        "_logType": "SIMPLE", "_key": "kill_with_phase2_skill2",
        "_additionValue": 1}, e)
    assert b.stats.get("extraInfo", {}).get("kill_with_phase2_skill2") == 1
    print("OK Main15TryNextPrtsAction + LogExtraBattleInfo")


def _exec_cond(b, node, source, target=None, owner=None):
    from ark_emulator.action_nodes import ActionNodeExecutor
    ex = ActionNodeExecutor(b)
    return ex._check_condition(node, source, target, owner)


if __name__ == "__main__":
    test_damage_via_max_hp_ratio()
    test_create_buff_to_blockee()
    test_trigger_buffs_by_keys()
    test_modify_cost_and_assign_bb()
    test_withdraw_source()
    test_summon_follow_my_route()
    test_rebuild_character_on_random_tile()
    test_finish_several_buffs_by_id()
    test_create_no_source_buff()
    test_change_route_motion_mode()
    test_ifnot_and_check_abnormal()
    test_assign_attribute_to_bb()
    test_aoe_damage_from_projectile()
    test_main15_and_log_extra_info()
