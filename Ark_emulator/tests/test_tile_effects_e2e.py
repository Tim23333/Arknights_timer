# -*- coding: utf-8 -*-
"""End-to-end terrain effect tests on real levels.

Covers tile targetSide filtering (SideType: 1=ALLY 2=ENEMY 3=BOTH 7=ALL),
the tile-blackboard value path for standing buffs (healing tiles) and the
periodic damage tiles (volcano / toxic).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _cells_with(b, tile_key):
    return [(r, c) for r in range(b.map.rows) for c in range(b.map.cols)
            if b.map.tile(r, c) and b.map.tile(r, c).tile_key == tile_key]


def _place_enemy_on(b, cell):
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[-1]
    e.row, e.col = cell
    e.state = EnemyState.COMBAT
    return e


def test_tile_target_side_filtering():
    """Ally-only tiles (healing/grass) never buff enemies; enemy-only tiles
    (deep sea) never buff allies; the ally gets the healing buff."""
    # healing: enemy unaffected
    sim = Simulator("level_act11d0_sub-1-2")
    b = sim.battle
    b.life_point = 10000.0
    cell = _cells_with(b, "tile_healing")[0]
    e = _place_enemy_on(b, cell)
    for _ in range(5):
        b.tick_once()
    assert "tile_healing" not in [x.get("key") for x in e.buffs]

    # grass: enemy unaffected
    sim2 = Simulator("level_act12d0_02")
    b2 = sim2.battle
    b2.life_point = 10000.0
    gcell = _cells_with(b2, "tile_grass")[0]
    e2 = _place_enemy_on(b2, gcell)
    b2.tick_once()
    assert "tile_grass" not in [x.get("key") for x in e2.buffs]

    # deep sea: enemy gets the terrain buff
    sim3 = Simulator("level_act12side_sub-1-3")
    b3 = sim3.battle
    b3.life_point = 10000.0
    dcell = _cells_with(b3, "tile_deepsea")[0]
    e3 = _place_enemy_on(b3, dcell)
    for _ in range(5):
        b3.tick_once()
    keys3 = [x.get("key") for x in e3.buffs]
    assert any(k.startswith("under_sea") for k in keys3), keys3

    # ally on healing tile: buff applied
    sim4 = Simulator("level_act11d0_sub-1-2")
    b4 = sim4.battle
    b4.life_point = 10000.0
    b4.cost = 50.0
    ok, inst = b4.deploy("char_149_scave", cell[0], cell[1], 1)
    assert ok, inst
    op = next(o for o in b4.operators if o.inst_id == inst)
    for _ in range(5):
        b4.tick_once()
    assert "tile_healing" in [x.get("key") for x in op.buffs]


def test_tile_healing_uses_tile_blackboard_value():
    """Healing tile HP recovery reads the per-tile blackboard value
    (loadFromBlackboard mods); with a value injected the operator heals."""
    sim = Simulator("level_act11d0_sub-1-2")
    b = sim.battle
    b.life_point = 10000.0
    b.cost = 50.0
    cell = _cells_with(b, "tile_healing")[0]
    ok, inst = b.deploy("char_149_scave", cell[0], cell[1], 1)
    assert ok, inst
    op = next(o for o in b.operators if o.inst_id == inst)
    op.hp = op.attributes.get("maxHp") - 200.0
    b._tile_bb[cell] = {"hp_recovery_per_sec": 25.0}
    before = op.hp
    for _ in range(35):
        b.tick_once()
    assert "tile_healing" in [x.get("key") for x in op.buffs]
    assert op.hp > before + 20.0, (before, op.hp)


def test_tile_volcano_periodic_damage():
    """Enemies standing on volcano tiles take periodic PURE damage."""
    sim = Simulator("level_act13d5_04")
    b = sim.battle
    b.life_point = 10000.0
    cell = _cells_with(b, "tile_volcano")[0]
    e = _place_enemy_on(b, cell)
    max_hp = e.hp
    for _ in range(45):
        b.tick_once()
    assert e.hp < max_hp - 200.0, (max_hp, e.hp)


def test_tile_toxic_periodic_damage():
    """Enemies standing on toxic tiles take periodic damage."""
    sim = Simulator("level_crisis_v2_03-01")
    b = sim.battle
    b.life_point = 10000.0
    cell = _cells_with(b, "tile_toxic")[0]
    e = _place_enemy_on(b, cell)
    max_hp = e.hp
    for _ in range(45):
        b.tick_once()
    assert e.hp < max_hp - 100.0, (max_hp, e.hp)


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
    print("all tile e2e tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)


def test_reed_tile_mode_switch_changes_buff():
    """SwitchDynamicBuffTileMode flips reed tiles to mode 1 (flaming): a
    unit on the tile swaps buff_reed_extinct -> buff_reed_flaming and the
    snapshot exposes the tile mode."""
    from ark_emulator import Simulator
    from ark_emulator.action_nodes import ActionNodeExecutor
    from ark_emulator.consts import EnemyState
    tiles = []
    for r in range(5):
        for c in range(8):
            key = "tile_reed" if (r, c) == (2, 3) else "tile_floor"
            tiles.append({"tileKey": key, "buildableType": 1,
                          "passableMask": 1, "heightType": 1})
    lv = {
        "name": "reed_test",
        "map": {"rows": 5, "cols": 8, "tiles": tiles},
        "routes": [{
            "startPosition": {"row": 2, "col": 0},
            "endPosition": {"row": 2, "col": 7},
            "checkpoints": [
                {"type": {"name": "MOVE"}, "position": {"row": 2, "col": 7}}],
        }],
        "waveTimeline": [],
        "options": {"maxLifePoint": 3, "initialCost": 10,
                    "costIncreaseTime": 1.0, "maxCost": 99},
        "enemyDbRefs": [],
    }
    sim = Simulator(level_id="custom", custom_level=lv)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 2, 3
    e.pos_x, e.pos_y = 3.0, 2.0
    e.state = EnemyState.COMBAT
    for _ in range(5):
        b.tick_once()
    # mode 0 (extinct): the reed buff is the extinct variant
    assert b.buffs.get(e, "buff_reed_extinct") is not None, e.buffs
    assert b.buffs.get(e, "buff_reed_flaming") is None
    ex = ActionNodeExecutor(b)
    ex.execute([
        {"$type": "Torappu.Battle.Action.Nodes+SwitchDynamicBuffTileMode",
         "_modeIndex": 1, "_tileType": "REED_TILE",
         "_specifyTileType": True}], source=e, target=e, owner=None)
    assert b.tile_mode(2, 3) == 1
    for _ in range(5):
        b.tick_once()
    assert b.buffs.get(e, "buff_reed_extinct") is None
    assert b.buffs.get(e, "buff_reed_flaming") is not None
    snap = sim.snapshot()
    assert snap.get("tileModes", {}).get("2,3") == 1, snap.get("tileModes")


def test_ignite_all_reed_tile_real_state_change():
    """IgniteAllReedTile (Arson) actually ignites reed tiles: mode 1 and
    buff_reed_flaming on a unit standing on the reed."""
    from ark_emulator import Simulator
    from ark_emulator.action_nodes import ActionNodeExecutor
    from ark_emulator.consts import EnemyState
    tiles = []
    for r in range(5):
        for c in range(8):
            key = "tile_reed" if (r, c) == (2, 3) else "tile_floor"
            tiles.append({"tileKey": key, "buildableType": 1,
                          "passableMask": 1, "heightType": 1})
    lv = {
        "name": "ignite_test",
        "map": {"rows": 5, "cols": 8, "tiles": tiles},
        "routes": [{
            "startPosition": {"row": 2, "col": 0},
            "endPosition": {"row": 2, "col": 7},
            "checkpoints": [
                {"type": {"name": "MOVE"}, "position": {"row": 2, "col": 7}}],
        }],
        "waveTimeline": [],
        "options": {"maxLifePoint": 3, "initialCost": 10,
                    "costIncreaseTime": 1.0, "maxCost": 99},
        "enemyDbRefs": [],
    }
    sim = Simulator(level_id="custom", custom_level=lv)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 2, 3
    e.pos_x, e.pos_y = 3.0, 2.0
    e.state = EnemyState.COMBAT
    for _ in range(5):
        b.tick_once()
    assert b.buffs.get(e, "buff_reed_extinct") is not None
    ex = ActionNodeExecutor(b)
    ex.execute([
        {"$type": "Torappu.Battle.Action.Nodes+IgniteAllReedTile"}],
        source=e, target=e, owner=None)
    assert b.tile_mode(2, 3) == 1
    for _ in range(5):
        b.tick_once()
    assert b.buffs.get(e, "buff_reed_extinct") is None
    assert b.buffs.get(e, "buff_reed_flaming") is not None
    assert sim.snapshot().get("tileModes", {}).get("2,3") == 1

