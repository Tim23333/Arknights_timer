# -*- coding: utf-8 -*-
"""Extra-mode node handlers: WDSLM stands, sandbox trace/toast, DurBus
passengers (activity-only node families, implemented to close the
remaining unhandled surface)."""
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
    b.battle_cost_add(200.0)
    return sim, b


def _enemy(b, row, col, key="enemy_1000_gopro_2"):
    e = b.spawn_enemy_directive(key, row, col, route_index=0)
    return e


def test_wdslm_stands_and_hp_equalization():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    host = _enemy(b, 3, 3, "enemy_1542_wdslm")
    stand1 = _enemy(b, 4, 4)
    stand2 = _enemy(b, 4, 6)
    sim.run_ticks(10)
    host.hp = host.max_hp * 0.5
    stand1.hp = stand1.max_hp
    stand2.hp = stand2.max_hp
    ctx = {"bb": {}, "source": host, "target": stand1}
    reg = {"$type": "RegisterAsStand", "_source": "BUFF_OWNER",
           "_hostAbilityName": "standRegisterList",
           "_standAbilityName": "standRegisterList",
           "useIdToFindHost": True, "hostId": "enemy_1542_wdslm"}
    assert eng._n_RegisterAsStand(stand1, reg, {"bb": {}, "source": stand1,
                                                "target": stand1}) is True
    assert eng._n_RegisterAsStand(stand2, reg, {"bb": {}, "source": stand2,
                                                "target": stand2}) is True
    assert eng._n_CheckHasStands(
        host, {"$type": "CheckHasStands", "_sourceType": "BUFF_OWNER",
               "_abilityName": "standRegisterList"}, ctx) is True
    eq = {"$type": "EqualizeTargetHpRatio", "_source": "BUFF_OWNER",
          "_target": "TARGET", "_useSourceHpRatio": True,
          "_hpRatio": 0.5, "_skipModifierEvent": True}
    ok = eng._n_RunActionsToWdslmAbilityTarget(
        host, {"$type": "RunActionsToWdslmAbilityTarget",
               "_abilityName": "standRegisterList",
               "_sourceType": "BUFF_OWNER",
               "_actionTargetType": "STANDS",
               "_actionsToTarget": [eq]}, ctx)
    assert ok is True
    for s in (stand1, stand2):
        assert abs(s.hp / s.max_hp - 0.5) < 1e-6, \
            "stand HP equalized to the host ratio"


def test_sandbox_trace_and_marks():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    ctx = {"bb": {}, "source": e, "target": e}
    # MarkEntityNotReward
    assert eng._n_SandboxMarkEntityNotReward(
        e, {"$type": "SandboxMarkEntityNotReward", "_target": "BUFF_OWNER",
            "_isUniEnemy": True, "_detailType": "CATCHED_SHINING",
            "_uniDetailType": "CATCHED_SHINING"}, ctx) is True
    assert e._sandbox_not_reward is True
    # ShowToast
    assert eng._n_SandboxShowToast(
        e, {"$type": "SandboxShowToast", "_lastTime": 1.0,
            "_toastKey": "ACT36SIDE_BOSS_NO_FOOD"}, ctx) is True
    assert any(x["type"] == "sandbox_toast"
               for x in b.events.snapshot_events())
    # SetEnemyTraceTarget + CheckEnemyCanTraceTarget
    assert eng._n_SandboxSetEnemyTraceTarget(
        e, {"$type": "SandboxSetEnemyTraceTarget",
            "_targetType": "BUFF_OWNER", "_sourceType": "BUFF_SOURCE",
            "_force": False}, ctx) is True
    assert eng._n_SandboxCheckEnemyCanTraceTarget(
        e, {"$type": "SandboxCheckEnemyCanTraceTarget",
            "_targetType": "BUFF_OWNER", "_checkHasTraceTarget": True,
            "_checkHasTraceTargetNow": False}, ctx) is True
    # EnableTraceTarget disable clears it
    assert eng._n_SandboxEnableTraceTarget(
        e, {"$type": "SandboxEnableTraceTarget", "_target": "BUFF_OWNER",
            "_enabled": False, "_traceTileInstead": False,
            "_wholeTraceInstead": True}, ctx) is True
    assert getattr(e, "_trace_target", None) is None
    assert eng._n_SandboxCheckEnemyCanTraceTarget(
        e, {"$type": "SandboxCheckEnemyCanTraceTarget",
            "_targetType": "BUFF_OWNER", "_checkHasTraceTarget": True,
            "_checkHasTraceTargetNow": False}, ctx) is False
    # MarkTraceReached / rush gates
    assert eng._n_SandboxMarkTraceReached(
        e, {"$type": "SandboxMarkTraceReached", "_target": "TARGET"},
        ctx) is True
    assert e._trace_reached is True
    assert eng._n_SandboxIsRushEnemyMode(
        e, {"$type": "SandboxIsRushEnemyMode"}, ctx) is False
    assert eng._n_SandboxIsRushEnemy(
        e, {"$type": "SandboxIsRushEnemy", "_targetType": "BUFF_OWNER"},
        ctx) is False


def test_durbus_passengers():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    bus = _enemy(b, 3, 4)
    p1 = _enemy(b, 4, 4)
    p2 = _enemy(b, 4, 5)
    sim.run_ticks(5)
    b._durbus_passengers["GetEnmey"] = [p1, p2]
    ctx = {"bb": {}, "source": bus, "target": bus}
    check = {"$type": "DurBusAbilityCheckPassengers",
             "_targetType": "BUFF_OWNER", "_abilityName": "GetEnmey",
             "_markCurrentPassengers": False,
             "_setSearchPassengersStatus": True,
             "_searchPassengersStatus": False}
    assert eng._n_DurBusAbilityCheckPassengers(bus, check, ctx) is True
    assert eng._n_DurBusAbilityReleasePassenger(
        bus, {"$type": "DurBusAbilityReleasePassenger",
              "_targetType": "BUFF_OWNER", "_abilityName": "GetEnmey",
              "_releaseLastOnly": False}, ctx) is True
    assert len(b._durbus_passengers["GetEnmey"]) == 0
    assert eng._n_DurBusAbilityCheckPassengers(bus, check, ctx) is False
    b._durbus_passengers["GetEnmey"] = [p1]
    assert eng._n_DurBusAbilityKillPassengers(
        bus, {"$type": "DurBusAbilityKillPassengers",
              "_targetType": "BUFF_OWNER", "_abilityName": "GetEnmey",
              "_killLastPassenger": False}, ctx) is True
    assert getattr(p1, "dead", False) is True


def test_sandbox_mode_weather_resources_stats():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    ctx = {"bb": {}, "source": e, "target": e}
    # weather
    assert eng._n_SandboxV3ChangeWeather(
        e, {"$type": "SandboxV3ChangeWeather", "_weatherKey": "weatherId",
            "_enable": True}, {"bb": {"weatherId": "weather_thunder"}}) is True
    assert b._sandbox_weather == "weather_thunder"
    assert eng._n_SandboxCheckCurrentMode(
        e, {"$type": "SandboxCheckCurrentMode", "_checkBuildMode": False,
            "_checkNodeType": False, "_checkSeasonType": False,
            "_checkWeatherType": True,
            "_sandboxWeatherType": "weather_thunder"}, ctx) is True
    assert eng._n_SandboxCheckCurrentMode(
        e, {"$type": "SandboxCheckCurrentMode", "_checkBuildMode": False,
            "_checkNodeType": False, "_checkSeasonType": False,
            "_checkWeatherType": True,
            "_sandboxWeatherType": "weather_sunny"}, ctx) is False
    # stats
    assert eng._n_SandboxV3ModifyBuffStat(
        e, {"$type": "SandboxV3ModifyBuffStat", "_statType": "PROSPERITY",
            "_formula": "ADDITION", "_value": 0.0,
            "_valueBbKey": "prosperity_service"},
        {"bb": {"prosperity_service": 5}, "source": e, "target": e}) is True
    assert b._sandbox_stats.get("PROSPERITY") == 5.0
    assert eng._n_SandboxV3RemoveBuffStat(
        e, {"$type": "SandboxV3RemoveBuffStat"}, ctx) is True
    assert b._sandbox_stats == {}
    # packed resources
    e._packed_res = 30.0
    assert eng._n_SandboxCheckHasResource(
        e, {"$type": "SandboxCheckHasResource", "_target": "BUFF_OWNER",
            "_checkFull": False}, ctx) is True
    assert eng._n_SandboxCollectPackedRes(
        e, {"$type": "SandboxCollectPackedRes", "_target": "BUFF_OWNER"},
        ctx) is True
    assert b._sandbox_res == 30.0
    assert e._packed_res == 0.0


def test_act49_tile_types():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    ctx = {"bb": {}, "source": e, "target": e}
    # not written yet -> gate False
    assert eng._n_Act49SideCheckCharacterTileType(
        e, {"$type": "Act49SideCheckCharacterTileType",
            "_targetType": "BUFF_OWNER", "_tileType": "Pure",
            "_checkAnyTile": False}, ctx) is False
    assert eng._n_Act49SideWriteCharacter(
        e, {"$type": "Act49SideWriteCharacter",
            "_targetType": "BUFF_OWNER", "_tileType": "Pure"}, ctx) is True
    assert eng._n_Act49SideCheckCharacterTileType(
        e, {"$type": "Act49SideCheckCharacterTileType",
            "_targetType": "BUFF_OWNER", "_tileType": "Pure",
            "_checkAnyTile": False}, ctx) is True
    assert eng._n_Act49SideCheckWordTileBuildable(
        e, {"$type": "Act49SideCheckWordTileBuildable",
            "_targetType": "BUFF_OWNER"}, ctx) is True
    assert eng._n_Act49SideSetEntityAnimatorColor(
        e, {"$type": "Act49SideSetEntityAnimatorColor",
            "_targetType": "BUFF_OWNER",
            "color": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}}, ctx) is True
    assert e._animator_color.get("r") == 1.0


def test_sandbox_depth_items_animals_states():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    ctx = {"bb": {}, "source": e, "target": e}
    # manually add items from bb
    assert eng._n_SandboxV3ManuallyAddItems(
        e, {"$type": "SandboxV3ManuallyAddItems", "_target": "TARGET",
            "_singleItem": True, "_itemIdsBbKey": "item_id",
            "_itemCntBbKey": "item_count", "_allowEmpty": False,
            "_reason": "ANIMAL_PRODUCE"},
        {"bb": {"item_id": "food_01", "item_count": 3},
         "source": e, "target": e}) is True
    assert b._sandbox_items.get("food_01") == 3
    # entity drop: carried items move to the battle pool
    e._sandbox_items = {"food_02": 2}
    assert eng._n_SandboxEntityDropItem(
        e, {"$type": "SandboxEntityDropItem", "_target": "BUFF_OWNER",
            "_type": "ENEMY"}, ctx) is True
    assert b._sandbox_items.get("food_02") == 2
    assert e._sandbox_items == {}
    # record / restore unit state
    e.hp = 123.0
    e.row, e.col = 1, 2
    assert eng._n_SandboxRecordUnitState(
        e, {"$type": "SandboxRecordUnitState", "_targetType": "TARGET",
            "_additionHpRatioKey": "addition_hp_ratio"},
        {"bb": {}, "source": e, "target": e}) is True
    e.hp = 999.0
    e.row, e.col = 5, 5
    assert eng._n_SandboxSetUniEnemyStatus(
        e, {"$type": "SandboxSetUniEnemyStatus",
            "_targetType": "BUFF_OWNER"}, ctx) is True
    assert e.row == 1 and e.col == 2
    # animal catch
    e._sandbox_animal = True
    assert eng._n_SandboxV3CheckIsAnimalEnemy(
        e, {"$type": "SandboxV3CheckIsAnimalEnemy",
            "_target": "MODIFIER_TARGET"}, ctx) is True
    assert eng._n_SandboxV3CatchAnimalEnemy(
        e, {"$type": "SandboxV3CatchAnimalEnemy",
            "_target": "MODIFIER_TARGET"}, ctx) is True
    assert eng._n_SandboxV3IsCatchedAnimal(
        e, {"$type": "SandboxV3IsCatchedAnimal", "_target": "BUFF_OWNER",
            "_checkIsLegend": False, "_isLegend": False}, ctx) is True
    # trap type gate
    e._trap_type = "AESTHETICS"
    assert eng._n_SandboxV3CheckTrapType(
        e, {"$type": "SandboxV3CheckTrapType", "_target": "BUFF_OWNER",
            "_trapTypeKey": None, "_trapType": "AESTHETICS"}, ctx) is True
    assert eng._n_SandboxV3CheckTrapType(
        e, {"$type": "SandboxV3CheckTrapType", "_target": "BUFF_OWNER",
            "_trapTypeKey": None, "_trapType": "CIVILIZATION"}, ctx) is False


def test_full_scan_remaining_nodes():
    """Handlers for the node types the full 3864-level scan flagged."""
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    other = _enemy(b, 3, 3)
    ctx = {"bb": {}, "source": e, "target": other}
    # HasCharacterInCertainDirection (LEFT of e = (3,3) has `other`)
    assert eng._n_HasCharacterInCertainDirection(
        e, {"$type": "HasCharacterInCertainDirection", "_direction": "LEFT",
            "_target": "BUFF_OWNER", "_checkSameSide": True,
            "_excludeTrapCategory": False}, ctx) is True
    # Act49side anchor + printing progress
    assert eng._n_Act49sideWriteCharacterBasedOnAnchorPos(
        e, {"$type": "Act49sideWriteCharacterBasedOnAnchorPos",
            "_targetType": "BUFF_OWNER", "_tileType": "Anchor"}, ctx) is True
    assert b._act49_tile_types.get((3, 4)) == "Anchor"
    assert eng._n_Act49sideChargePrintingProgress(
        e, {"$type": "Act49sideChargePrintingProgress",
            "_chargeValue": 9999.0}, ctx) is True
    assert b._act49_print_progress == 9999.0
    # Manhattan distance
    ctx2 = {"bb": {}, "source": other, "target": e}
    assert eng._n_AssignManhattanDistanceToBB(
        e, {"$type": "AssignManhattanDistanceToBB",
            "_blackboardKey": "distance", "_sourceType": "BUFF_SOURCE",
            "_targetType": "BUFF_OWNER"},
        ctx2) is True
    assert ctx2["bb"].get("distance") == 1
    # racing
    assert eng._n_SwitchRacingMode(
        e, {"$type": "SwitchRacingMode", "_targetType": "BUFF_OWNER",
            "_racingMode": "Racing"}, ctx) is True
    assert e._racing_mode == "Racing"
    e.hp = 1.0
    assert eng._n_RacingEnemyRecover(
        e, {"$type": "RacingEnemyRecover", "_targetType": "BUFF_OWNER"},
        ctx) is True
    assert e.hp == e.max_hp
    # sub-spine config
    assert eng._n_SwitchSubSpineConfig(
        e, {"$type": "SwitchSubSpineConfig", "_target": "BUFF_OWNER",
            "_defaultToRandom": False, "_indexKey": "", "_index": 2},
        ctx) is True
    assert e._sub_spine_index == 2
    ctx3 = {"bb": {}, "source": e, "target": e}
    assert eng._n_AssignSubSpineConfigIndexToBB(
        e, {"$type": "AssignSubSpineConfigIndexToBB",
            "_target": "BUFF_OWNER", "_indexKey": "spine"},
        ctx3) is True
    assert ctx3["bb"].get("spine") == 2
    # summon by ability selector
    assert eng._n_SummonEnemyByAbilitySelector(
        e, {"$type": "SummonEnemyByAbilitySelector", "_source": "BUFF_OWNER",
            "_useTargetAbilitySelector": True, "_target": "BUFF_OWNER",
            "_abilityName": "SummonTileSelector",
            "_enemyKeys": ["enemy_1000_gopro_2"], "_getEnemyKeysFromBB": None,
            "_summonCount": 1, "_motionMode": "WALK"}, ctx) is True
    assert any(x.enemy_key == "enemy_1000_gopro_2"
               for x in b.enemies[1:])
    # ro4dlc2 seal tiles
    assert eng._n_RO4DLC2TriggerBossSealTileSkill(
        e, {"$type": "RO4DLC2TriggerBossSealTileSkill",
            "_evnSysKey": "env_020_ro4dlc2_boss5", "_startColKey": "startCol",
            "_endColKey": "endCol", "_intervalKey": "interval",
            "_target": "BUFF_OWNER"},
        {"bb": {"startCol": 3, "endCol": 3}, "source": e, "target": e}) is True
    assert any(c == 3 for (_, c) in b._ro4dlc2_seal_tiles)
    # dynamic buff tile mode
    assert eng._n_SwitchDynamicBuffTileModeUseAbilitySelector(
        e, {"$type": "SwitchDynamicBuffTileModeUseAbilitySelector",
            "_sourceType": "BUFF_OWNER", "_targetType": "BUFF_OWNER",
            "_abilityName": "TileSelector", "_operation": "INDEX",
            "_modeIndex": 0}, ctx) is True
    assert b._tile_modes.get((3, 4)) == 0


def test_second_batch_nodes():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    ctx = {"bb": {}, "source": e, "target": e}
    # balloon force accumulates
    n1 = {"$type": "Act47SideAddForceToBalloon", "_force": 2,
          "_forceKey": "force_extra", "_isUpForce": False,
          "_targetType": "BUFF_OWNER", "_isMinus": False}
    assert eng._n_Act47SideAddForceToBalloon(e, n1, ctx) is True
    assert eng._n_Act47SideAddForceToBalloon(e, n1, ctx) is True
    assert e._balloon_force == 4.0
    n1["_isMinus"] = True
    assert eng._n_Act47SideAddForceToBalloon(e, n1, ctx) is True
    assert e._balloon_force == 2.0
    # friction
    assert eng._n_UpdateFrictionFactor(
        e, {"$type": "UpdateFrictionFactor", "_target": "BUFF_OWNER",
            "_frictionFactor": 0.0, "_restoreFrictionFactor": False},
        ctx) is True
    assert e._friction_factor == 0.0
    assert eng._n_UpdateFrictionFactor(
        e, {"$type": "UpdateFrictionFactor", "_target": "BUFF_OWNER",
            "_frictionFactor": 0.0, "_restoreFrictionFactor": True},
        ctx) is True
    assert e._friction_factor == 1.0
    # effect transform / SP UI / progress
    assert eng._n_EnableEffectTransform(
        e, {"$type": "EnableEffectTransform", "_targetType": "BUFF_OWNER",
            "_enabled": True}, ctx) is True
    assert e._effect_transform is True
    assert eng._n_ModifyEnemySpUIFlag(
        e, {"$type": "ModifyEnemySpUIFlag", "_targetType": "BUFF_OWNER",
            "_isShow": True}, ctx) is True
    assert e._sp_ui_show is True
    assert eng._n_RegistProgressBuff(
        e, {"$type": "RegistProgressBuff"}, ctx) is True
    assert b._progress_buffs == [e.inst_id]
    # magic circuit obstacle in range (melee shape -> own tile)
    assert eng._n_SetMagicCircuitLikeObstacleInRange(
        e, {"$type": "SetMagicCircuitLikeObstacleInRange",
            "_targetType": "BUFF_OWNER", "_isLikeObstacle": True,
            "_rangeId": None}, ctx) is True
    assert e._magic_circuit_obstacle is True
    # electric work / coop score
    assert eng._n_AssignElectricWorkCountToManager(
        e, {"$type": "AssignElectricWorkCountToManager",
            "_target": "BUFF_SOURCE", "_workType": "WOOD", "count": 1},
        ctx) is True
    assert b._electric_work.get("WOOD") == 1
    assert eng._n_CoopBoatGainScore(
        e, {"$type": "CoopBoatGainScore", "_score": 0,
            "_loadFromBlackboard": True, "_scoreKey": "score",
            "isMin": False},
        {"bb": {"score": 50}, "source": e, "target": e}) is True
    assert b._coop_scores.get("boat") == 50.0
    # union-find member count (2 adjacent gopro enemies)
    e2 = _enemy(b, 3, 3)
    ctx2 = {"bb": {}, "source": e, "target": e}
    assert eng._n_AssignUnionFindMemberCntToBB(
        e, {"$type": "AssignUnionFindMemberCntToBB",
            "_targetType": "BUFF_OWNER",
            "_abilityName": "sandbox_v3_relic_dyn_id13", "_key": "count"},
        ctx2) is True
    assert ctx2["bb"].get("count") == 2


def test_third_batch_nodes():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    ctx = {"bb": {}, "source": e, "target": e}
    # legion hand / profession
    b._legion_hand = ["a", "b", "c"]
    assert eng._n_LegionModeOnlyCheckHandCardNotFull(
        e, {"$type": "LegionModeOnlyCheckHandCardNotFull"}, ctx) is True
    b._legion_hand = list(range(8))
    assert eng._n_LegionModeOnlyCheckHandCardNotFull(
        e, {"$type": "LegionModeOnlyCheckHandCardNotFull"}, ctx) is False
    assert eng._n_LegionModeOnlyModifyMaxProfessionBuffCnt(
        e, {"$type": "LegionModeOnlyModifyMaxProfessionBuffCnt",
            "_sourceType": "BUFF_OWNER", "_addValue": 2,
            "_resetToDefault": False}, ctx) is True
    assert b._legion_profession_buff_cnt == 2
    b._legion_profession_counts = {"TANK": 3}
    ctx2 = {"bb": {}, "source": e, "target": e}
    assert eng._n_LegionModeOnlyAssignSpecifiedProfessionStackCntToBB(
        e, {"$type": "LegionModeOnlyAssignSpecifiedProfessionStackCntToBB",
            "_assignBlackboardKey": "tank_buff_cnt",
            "_queryProfessionCategory": "TANK",
            "_sourceType": "BUFF_OWNER"}, ctx2) is True
    assert ctx2["bb"].get("tank_buff_cnt") == 3
    # forces
    assert eng._n_InitForces(
        e, {"$type": "InitForces", "_targetType": "BUFF_OWNER",
            "_passBallForceKey": "passing_force",
            "_slapShotForceKey": "slapshot_force",
            "_clearanceForceKey": "clearance_force"},
        {"bb": {"passing_force": 1, "slapshot_force": 2,
                "clearance_force": 3}, "source": e, "target": e}) is True
    assert e._forces == {"passing": 1.0, "slapshot": 2.0, "clearance": 3.0}
    # gather listeners
    assert eng._n_GatherRegisterListener(
        e, {"$type": "GatherRegisterListener", "_target": "BUFF_OWNER",
            "_listenerType": "ENEMY"}, ctx) is True
    assert len(b._gather_listeners) == 1
    assert eng._n_GatherRemoveListener(
        e, {"$type": "GatherRemoveListener", "_target": "BUFF_OWNER",
            "_convertWhenRemove": False}, ctx) is True
    assert b._gather_listeners == []
    # ristar move to a ristar road tile
    b.map.tile(2, 4).tile_key = "tile_ristar_road"
    assert eng._n_RistarMove(
        e, {"$type": "RistarMove", "_isAllyTrigger": True,
            "_tileKeyList": ["tile_ristar_road",
                             "tile_ristar_road_forbidden"]}, ctx) is True
    assert (e.row, e.col) == (2, 4)
    # spawn by uid
    assert eng._n_SpawnCharacterByUid(
        e, {"$type": "SpawnCharacterByUid", "_target": "BUFF_OWNER",
            "_freely": False, "_addBuffToTarget": False,
            "_getPosViaBB": False, "_buffs": []},
        {"bb": {"uid": "enemy_1000_gopro_2"}, "source": e, "target": e},
    ) is True
    assert any(x.enemy_key == "enemy_1000_gopro_2"
               for x in b.enemies[1:])


def test_roguelike_buff_nodes():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 3, 4)
    ctx = {"bb": {}, "source": e, "target": e}
    # zone / duel / deify stage gates
    b._rogue_zone_type = "SP"
    assert eng._n_RoguelikeCheckZoneType(
        e, {"$type": "RoguelikeCheckZoneType", "_zoneType": "SP"}, ctx) is True
    b._rogue_duel_stage = "STAGE_CHOSEN"
    assert eng._n_RoguelikeDuelModeCheckStage(
        e, {"$type": "RoguelikeDuelModeCheckStage",
            "gameStage": "STAGE_CHOSEN"}, ctx) is True
    b._rogue_deify_stage = "STAGE_BATTLE"
    assert eng._n_RoguelikeDeifyModeCheckStage(
        e, {"$type": "RoguelikeDeifyModeCheckStage",
            "gameStage": "STAGE_BATTLE"}, ctx) is True
    # dice
    assert eng._n_RollRogueDice(
        e, {"$type": "RollRogueDice", "_maxVal": 12}, ctx) is True
    assert 1 <= ctx["bb"].get("dice", 0) <= 12
    # exp log
    assert eng._n_RoguelikeLogExpUseSerializedTrapID(
        e, {"$type": "RoguelikeLogExpUseSerializedTrapID",
            "_expKey": "toolgun_exp_1", "_trapID": "trap_131_toolgun"},
        {"bb": {"toolgun_exp_1": 5}, "source": e, "target": e}) is True
    assert b._rogue_exp_use.get("trap_131_toolgun") == 5.0
    # boss gate
    e._roguelike_boss = True
    assert eng._n_IsRogueLikeBoss(
        e, {"$type": "IsRogueLikeBoss", "_targetType": "MODIFIER_TARGET"},
        ctx) is True
    # inherit hp
    e.hp = e.max_hp * 0.4
    assert eng._n_RoguelikeInheritEnemyHp(
        e, {"$type": "RoguelikeInheritEnemyHp", "_target": "BUFF_OWNER"},
        ctx) is True
    assert abs(e._roguelike_hp_ratio - 0.4) < 1e-6
    # shield gate
    assert eng._n_HaveShieldRoguelike(
        e, {"$type": "HaveShieldRoguelike",
            "_onlyCheckWhetherHaveShieldWhenEnteringBattle": True},
        ctx) is False
    b._rogue_shield = 1
    assert eng._n_HaveShieldRoguelike(
        e, {"$type": "HaveShieldRoguelike",
            "_onlyCheckWhetherHaveShieldWhenEnteringBattle": True},
        ctx) is True
    # toast
    assert eng._n_RoguelikeShowToastRL04(
        e, {"$type": "RoguelikeShowToastRL04",
            "_toastTypeRL04": "GOLD_STEAL", "_lastTime": 3.0}, ctx) is True
    assert any(x["type"] == "roguelike_toast_rl04"
               for x in b.events.snapshot_events())
    # candle holder count
    e._candle_holder = True
    ctx2 = {"bb": {}, "source": e, "target": e}
    assert eng._n_RoguelikeAssignCharacterInCandleHolderCntToBlackboard(
        e, {"$type": "RoguelikeAssignCharacterInCandleHolderCntToBlackboard",
            "_target": "BUFF_OWNER", "blackboardKey": "cnt"}, ctx2) is True
    assert ctx2["bb"].get("cnt") == 0  # enemies not counted, only chars
    # storm direction
    e._storm_direction = "N"
    assert eng._n_Rogue6StormDirectionCheck(
        e, {"$type": "Rogue6StormDirectionCheck", "_target": "BUFF_OWNER"},
        ctx) is True


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
