# -*- coding: utf-8 -*-
"""Act31Side pollute-area mechanic tests (13-04 hard boss fight)."""
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


def _enemy(b, row=2, col=3, bb=None):
    e = b.spawn_enemy_directive("enemy_1000_gopro_2", row, col, route_index=0)
    if bb:
        e.blackboard = dict(bb)
    return e


def test_act31_add_pollute_and_gate():
    sim, b = _battle()
    m = b.act31
    _enemy(b, 3, 4)
    assert m.add_area_pollute(3, 4, 50, radius=1.0) is True
    assert m.check_in_pollute_area(3, 4) is True
    assert m.check_in_pollute_area(3, 3) is True, "road neighbor polluted"
    assert not m.check_in_pollute_area(2, 4), "wall neighbor excluded"
    assert not m.check_in_pollute_area(5, 5)
    assert m.check_root_tile_pollute_value(3, 4, "GE", 50) is True
    assert m.check_root_tile_pollute_value(3, 4, "GE", 51) is False


def test_act31_purify_connected_area():
    sim, b = _battle()
    m = b.act31
    for c in (2, 3, 4):
        assert m.add_area_pollute(3, c, 30, radius=0.0) is True
    assert m.purify_area_pollute(3, 3, 10) is True
    assert m.pollute.get((3, 2)) == 20
    assert m.pollute.get((3, 4)) == 20
    assert m.check_in_pollute_area(3, 2) is True
    # purify enough to clear the whole connected area
    assert m.purify_area_pollute(3, 3, 999) is True
    assert m.pollute == {}


def test_act31_death_pollute_uses_bb_value():
    sim, b = _battle()
    m = b.act31
    e = _enemy(b, 3, 4, bb={"value": 77})
    assert m.death_pollute_tile(3, 4, radius=1.0,
                                value=m.pollute_value(e, None)) is True
    assert m.pollute.get((3, 4)) == 77
    assert m.pollute.get((3, 3)) == 77


def test_act31_node_handlers_and_scale():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 2, 3, bb={"value": 5})
    ctx = {"bb": {}, "source": e, "target": e}
    assert eng._n_Act31SideAddAreaPollute(
        e, {"$type": "Act31SideAddAreaPollute",
            "_sourceType": "BUFF_OWNER", "_addPolluteV": 0,
            "_needCheckTile": False, "_rangeRadius": 1.0}, ctx) is True
    assert b.act31.check_in_pollute_area(2, 3)
    assert eng._n_Act31SideCheckInPolluteArea(
        e, {"$type": "Act31SideCheckInPolluteArea",
            "_sourceType": "BUFF_OWNER"}, ctx) is True
    assert eng._n_Act31SideAssignAreaPolluteValueToBB(
        e, {"$type": "Act31SideAssignAreaPolluteValueToBB",
            "_sourceType": "BUFF_OWNER", "_polluteVKey": "dynamic",
            "_assignPVRatio": False, "_assignTilePV": True}, ctx) is True
    assert ctx["bb"].get("dynamic") == 5
    assert eng._n_Act31SidePurifyAreaPollute(
        e, {"$type": "Act31SidePurifyAreaPollute",
            "_sourceType": "BUFF_OWNER", "_addPolluteV": 0}, ctx) is True
    assert not b.act31.check_in_pollute_area(2, 3)
    # ModifyEnemyGraphicScale
    assert eng._n_ModifyEnemyGraphicScale(
        e, {"$type": "ModifyEnemyGraphicScale", "_ownerType": "BUFF_OWNER",
            "_isAdd": True, "_scaleValue": 0.27, "_needMax": True,
            "_maxValue": 0.27}, ctx) is True
    assert abs(getattr(e, "_graphic_scale", 0) - 0.27) < 1e-6


def test_act31_hard_13_04_no_unhandled():
    """level_hard_13-04 must not hit unhandled Act31Side / graphic nodes."""
    sim = Simulator(level_id="level_hard_13-04")
    b = sim.battle
    sim.run_ticks(900)
    un = [x for x in b.events.snapshot_events()
          if x["type"] == "buff_node_unhandled"]
    bad = [x for x in un if any(k in str(x.get("data", {}).get("node"))
                                for k in ("Act31Side", "GraphicScale"))]
    assert not bad, [x["data"] for x in bad]
    assert "act31" in b.snapshot()


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
