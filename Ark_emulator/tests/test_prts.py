# -*- coding: utf-8 -*-
"""Mainline-15 PRTS script manager tests (ark_emulator/prts.py).

Covers the priority queue, the sub-action pipeline (move -> spawn /
drag / create-buff), skip/filter semantics and the Main15* buff-node
handlers wired to the manager.
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
    b.battle_cost_add(200.0)
    return sim, b


def _bind_prts(b, row=2, col=2):
    e = b.spawn_enemy_directive("enemy_1564_mpprts", row, col, route_index=0)
    assert b.prts.prts_enemy is e, "PRTS enemy bound at spawn"
    return e


def _atk_buff(key, value):
    return {"buffKey": key,
            "lifeTime": 3600.0,
            "attributes": {"attributeModifiers": [
                {"attributeType": 1, "value": value, "formulaItem": 0}]}}


def test_prts_priority_queue_picks_highest_first():
    sim, b = _battle()
    p = b.prts
    p.TrySpawnEnemyOnMostSurround(b.map.tile(3, 3), 50, None,
                                  "enemy_1001_gopro", "enemy_1000_gopro_2")
    p.TrySpawnEnemyOnMostSurround(b.map.tile(3, 4), 110, None,
                                  "enemy_1001_gopro", "enemy_1000_gopro_2")
    assert len(p.pending) == 2
    assert p.TryPickNextAction() is True
    assert p.last_main_action == "MOVE_AND_SPAWNENEMY"
    assert p.last_sub_action == "MOVE_TO_DRAG"
    assert p.sub_queue[0]["targetPos"] == (4.0, 3.0), \
        "the priority-110 action (tile 3,4) is picked first"
    assert len(p.pending) == 1


def test_prts_spawn_enemy_on_tile():
    sim, b = _battle()
    _bind_prts(b)
    b.deploy("char_149_scave", 3, 3)
    sim.run_ticks(20)
    b.prts.TrySpawnEnemyOnMostSurround(b.map.tile(3, 4), 50, None,
                                       "enemy_1001_gopro",
                                       "enemy_1000_gopro_2")
    assert b.prts.TryPickNextAction() is True
    sim.run_ticks(180)
    assert b.prts.spawn_count == 1, "PRTS spawned exactly one enemy"
    assert b.prts.finished_count >= 1
    evs = [x for x in b.events.snapshot_events()
           if x["type"] == "prts_spawn_enemy"]
    assert evs, "prts_spawn_enemy event emitted"
    assert evs[0]["data"]["row"] == 3 and evs[0]["data"]["col"] == 4


def test_prts_move_then_create_buff():
    sim, b = _battle()
    prts = _bind_prts(b, 2, 2)
    bd = _atk_buff("prts_test_buff", 100)
    assert b.prts.TryMoveAndCreateBuff(100, (6.0, 5.0), bd) is True
    assert b.prts.TryPickNextAction() is True
    sim.run_ticks(260)
    assert b.prts.finished_count >= 1
    assert abs(prts.pos_x - 6.0) <= 0.2 and abs(prts.pos_y - 5.0) <= 0.2, \
        "PRTS moved to the buff target tile"
    assert b.buffs.get(prts, "prts_test_buff") is not None, \
        "CREATE_BUFF applied the buff to the PRTS enemy"


def test_prts_drag_source_and_arrive_buff():
    sim, b = _battle()
    prts = _bind_prts(b, 2, 2)
    sim.run_ticks(10)
    victim = b.spawn_enemy_directive("enemy_1000_gopro_2", 2, 3,
                                     route_index=0)
    sim.run_ticks(5)
    bd = _atk_buff("prts_test_arrive", 50)
    assert b.prts.TryMoveAndDragSource(200, victim, (5.0, 5.0), bd) is True
    assert b.prts.TryPickNextAction() is True
    sim.run_ticks(320)
    assert b.prts.finished_count >= 1
    assert b.buffs.get(victim, "prts_test_arrive") is not None, \
        "arrive buff applied to the dragged source on arrival"
    assert getattr(victim, "_prts_dragged", False) is False, \
        "drag released after arrival"
    assert prts is not None


def test_prts_try_next_skip_and_filter():
    sim, b = _battle()
    p = b.prts
    assert p.TryNextSubAction() is False, "empty queue returns False"
    victim = b.spawn_enemy_directive("enemy_1000_gopro_2", 2, 3,
                                     route_index=0)
    assert p.TryMoveAndDragSource(10, None, (1.0, 1.0)) is False, \
        "invalid source rejected"
    assert p.TryMoveAndDragSource(10, victim, (1.0, 1.0)) is True
    assert p.SkipPrtsAction("MOVE_AND_DRAG_SOURCE") is True
    assert not p.pending, "skip removed the pending action"
    assert p.FilterCurrenSubAction("MOVE_TO_DRAG") is False
    p.TryMoveAndDragSource(10, victim, (1.0, 1.0))
    assert p.TryNextSubAction(force_next=True) is True
    assert p.last_sub_action == "MOVE_TO_DRAG"
    assert p.FilterCurrenSubAction("MOVE_TO_DRAG") is True


def test_prts_main15_node_handlers():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    op = None
    ok, pid = b.deploy("char_149_scave", 3, 3)
    assert ok
    op = next(o for o in b.operators if o.inst_id == pid)
    sim.run_ticks(20)
    # InsertPrtsAction (chooseSource) queues an action at the source tile
    res = eng._n_Main15InsertPrtsAction(
        op, {"$type": "Main15InsertPrtsAction",
             "_actionType": "MOVE_AND_SPAWNENEMY", "_priority": 110,
             "_chooseSource": True,
             "_enemyKeyFly": None, "_enemyKeyHL": "enemy_1001_gopro",
             "_enemyKeyLL": "enemy_1000_gopro_2"},
        {"bb": {}, "source": op, "target": op})
    assert res is True
    assert len(b.prts.pending) == 1
    assert any(x["type"] == "main15_insert_prts"
               for x in b.events.snapshot_events())
    # TryNextPrtsAction advances the pipeline
    res = eng._n_Main15TryNextPrtsAction(
        op, {"$type": "Main15TryNextPrtsAction",
             "_doNextWhenSuccess": True, "_forceNext": False},
        {"bb": {}, "source": op})
    assert res is True
    assert b.prts.last_main_action == "MOVE_AND_SPAWNENEMY"
    # FilterPrtsLastSubAction gate matches the current sub-action
    gate = eng._n_Main15FilterPrtsLastSubAction(
        op, {"$type": "Main15FilterPrtsLastSubAction",
             "_actionType": "MOVE_TO_DRAG", "_filterActionInstead": False,
             "_mainActionType": "MOVE_AND_SPAWNENEMY"},
        {"bb": {}})
    assert gate is True
    gate = eng._n_Main15FilterPrtsLastSubAction(
        op, {"$type": "Main15FilterPrtsLastSubAction",
             "_actionType": "MOVE_TO_ORIGIN", "_filterActionInstead": True,
             "_mainActionType": "MOVE_AND_SPAWNENEMY"},
        {"bb": {}})
    assert gate is True, "filterActionInstead inverts the match"
    # ForceSetBattleSpeedLevel
    eng._n_Main15ForceSetBattleSpeedLevel(
        op, {"$type": "Main15ForceSetBattleSpeedLevel", "_enable": True},
        {"bb": {}})
    assert b.prts.force_battle_speed is True
    assert b._main15_force_speed is True


def test_prts_enemy_key_resolves_to_buff_owner():
    """The drag-on-locate template uses ``enemy_key`` as the buff owner's
    own enemy key (the dragged enemy re-spawns when located)."""
    sim, b = _battle()
    e = b.spawn_enemy_directive("enemy_1000_gopro_2", 2, 3, route_index=0)
    from ark_emulator.prts import _resolve_enemy_key
    assert _resolve_enemy_key(b, "enemy_key", {}, owner=e) == \
        "enemy_1000_gopro_2"
    # node-level: the queued spawn action carries the resolved key
    res = b.prts.insert_from_node(
        e, {"$type": "Main15InsertPrtsAction",
            "_actionType": "MOVE_AND_SPAWNENEMY", "_priority": 50,
            "_chooseSource": True,
            "_enemyKeyFly": "enemy_key",
            "_enemyKeyHL": None, "_enemyKeyLL": None},
        {"bb": {}, "source": e, "target": e})
    assert res is True
    action = b.prts.pending[0][2]
    assert action["enemyKeyFly"] == "enemy_1000_gopro_2"


def test_prts_env_config_resolves_spawn_keys_by_height():
    """The env_v060_mainline15_prtsCtrl config maps the lowland/highland
    placeholder spawn keys through the trap pairs by tile height."""
    sim, b = _battle()
    # main_01-01 has no env rune; inject the config key so the manager
    # picks up the extracted env-system config
    b.env_systems.append({"key": "env_v060_mainline15_prtsCtrl",
                          "kind": "system"})
    p = b.prts
    p._config_tried = False     # main_01-01 probed configs during the ticks
    p._ensure_config()
    assert p.config is not None
    assert p.prts_enemy_key == "enemy_10072_mpprhd"
    assert abs(p.spawn_check_dist - 0.01) < 1e-9
    # lowland tile -> the lowland pair (mpweak); the tile carries no
    # pre-placed trap so the first matching pair wins
    tile = b.map.tile(3, 3)
    tile.height_type = 0
    assert p._config_spawn_key(tile) == "enemy_10082_mpweak"
    tile.height_type = 1
    assert p._config_spawn_key(tile) == "enemy_10074_mpcata"


def test_prts_snapshot_exposed():
    sim, b = _battle()
    snap = b.snapshot()
    assert "prts" in snap
    assert snap["prts"]["active"] is False
    _bind_prts(b)
    snap = b.snapshot()
    assert snap["prts"]["prtsEnemy"] is not None


def test_main15_18_prts_system_runs():
    """Real-data smoke: the 15-18 boss stage binds the PRTS enemy, fires
    Main15InsertPrtsAction nodes and advances the script queue."""
    sim = Simulator(level_id="level_main_15-18")
    b = sim.battle
    sim.run_ticks(700)
    prts = b.prts.to_dict()
    assert prts["active"] is True, "PRTS enemy bound"
    evs = [x for x in b.events.snapshot_events()
           if x["type"] in ("main15_insert_prts", "prts_action_start",
                            "prts_try_next")]
    assert evs, "PRTS script events observed"


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
