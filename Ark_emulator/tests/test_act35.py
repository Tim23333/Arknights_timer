# -*- coding: utf-8 -*-
"""Act35Side gem mechanic tests (ark_emulator/act35.py + buff handlers).

The env_017_act35side gems (Clear/Polluted) are reused by the mainline
15-18 boss fight; these cover summon / gates / count / line-eliminate.
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


def _enemy(b, row=2, col=3):
    return b.spawn_enemy_directive("enemy_1000_gopro_2", row, col,
                                   route_index=0)


def test_act35_summon_gem_tracks_tile():
    sim, b = _battle()
    m = b.act35
    assert m.summon_gem(3, 4, "Polluted") is True
    assert m.check_on_gems_tile(3, 4) is True
    assert m.gems_count() == 1
    gem = m.gems[(3, 4)]
    assert gem["type"] == "Polluted"
    assert gem["enemy"] is not None and not gem["enemy"].dead
    assert "enemy_sggem_t[polluted]" in [
        x.get("key") for x in gem["enemy"].buffs]
    # occupied tile cannot host a second gem
    assert m.summon_gem(3, 4, "Clear") is False
    assert m.summon_gem(0, 0, "Clear") is False, "start tile excluded"


def test_act35_gate_and_count_blackboard():
    sim, b = _battle()
    m = b.act35
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b)
    sim.run_ticks(10)
    # not on a gems tile -> gate False
    ok = eng._n_Act35SideCheckIfOnGemsTile(
        e, {"$type": "Act35SideCheckIfOnGemsTile",
            "_targetType": "BUFF_OWNER", "_excludeLinkGems": True,
            "_checkNotOn": False}, {"bb": {}, "source": e, "target": e})
    assert ok is False
    assert m.summon_gem(3, 4, "Polluted") is True
    gem = m.gems[(3, 4)]["enemy"]
    # the gate is evaluated on the gem enemy itself (BUFF_OWNER)
    ok = eng._n_Act35SideCheckIfOnGemsTile(
        gem, {"$type": "Act35SideCheckIfOnGemsTile",
            "_targetType": "BUFF_OWNER", "_excludeLinkGems": True,
            "_checkNotOn": False}, {"bb": {}, "source": gem, "target": gem})
    assert ok is True
    ok = eng._n_Act35SideCheckIfOnGemsTile(
        gem, {"$type": "Act35SideCheckIfOnGemsTile",
            "_targetType": "BUFF_OWNER", "_excludeLinkGems": True,
            "_checkNotOn": True}, {"bb": {}, "source": gem, "target": gem})
    assert ok is False, "_checkNotOn inverts"
    # count to blackboard
    ctx = {"bb": {}, "source": e, "target": e}
    assert eng._n_Act35SideAssignGemsCountToBlackboard(
        e, {"$type": "Act35SideAssignGemsCountToBlackboard",
            "_targetType": "BUFF_OWNER", "_excludeLinkGems": True,
            "_blackboardKey": "cnt", "_maxCountKey": "max_target",
            "_maxCount": 999999}, ctx) is True
    assert ctx["bb"].get("cnt") == 1


def test_act35_summon_range_and_four_directions():
    sim, b = _battle()
    m = b.act35
    # circle radius 1 -> all valid, unoccupied tiles in the 3x3
    valid = {(r, c) for r in range(4, 7) for c in range(4, 7)
             if m._valid_tile(r, c)}
    assert valid, "expected some summonable tiles around (5,5)"
    assert m.summon_gems_in_range(5, 5, "Polluted", is_circle=True,
                                  radius=1.0) is True
    assert set(m.gems.keys()) == valid
    assert all(m.check_on_gems_tile(r, c) for r, c in valid)
    # four directions
    before = m.gems_count()
    expected = sum(
        1 for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
        if m._valid_tile(2 + dr, 5 + dc))
    assert m.summon_gems_in_four_directions(2, 5, "Clear") is True
    assert m.gems_count() == before + expected


def test_act35_eliminate_by_direction():
    sim, b = _battle()
    m = b.act35
    for dc in range(3, 7):
        assert m.summon_gem(3, dc, "Polluted") is True
    assert m.gems_count() == 4
    assert m.eliminate_gems(3, 5, "LEFT") is True
    # left line from (3,5): (3,4),(3,3) removed; (3,6) stays
    assert m.check_on_gems_tile(3, 4) is False
    assert m.check_on_gems_tile(3, 3) is False
    assert m.check_on_gems_tile(3, 6) is True
    assert m.gems_count() == 1


def test_act35_main15_18_no_unhandled_gem_nodes():
    """The 15-18 boss fight must not hit unhandled Act35Side nodes."""
    sim = Simulator(level_id="level_main_15-18")
    b = sim.battle
    sim.run_ticks(709)
    un = [x for x in b.events.snapshot_events()
          if x["type"] == "buff_node_unhandled"]
    gem_un = [x for x in un if "Act35Side" in str(x.get("data", {}).get("node"))]
    assert not gem_un, [x["data"] for x in gem_un]
    # the gems that the guard summoned during the run are tracked
    snap = b.snapshot()
    assert "act35" in snap


def test_act35_projectile_trace_target_resolves_hit_target():
    """SummonGemsInRange with PROJECTILE_TRACETARGET uses the projectile's
    hit target (the ctx target) instead of falling back to the owner."""
    sim, b = _battle()
    m = b.act35
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b, 2, 3)
    hit = b.spawn_enemy_directive("enemy_1000_gopro_2", 3, 4,
                                  route_index=0)
    ctx = {"bb": {}, "source": e, "target": hit}
    ok = eng._n_Act35SideSummonGemsInRange(
        e, {"$type": "Act35SideSummonGemsInRange",
            "_targetType": "PROJECTILE_TRACETARGET",
            "_gemsType": "Polluted", "_rangeId": "x-5",
            "direction": "UP", "_isCircleRange": False,
            "_rangeRadius": 0.0}, ctx)
    assert ok is True
    # the x-5 range is centered on the hit target (3,4): (3,3),(3,5),(4,4)
    # appear, while the owner's tile (2,3) is not the summon center
    assert any(g in m.gems for g in ((3, 3), (3, 5), (4, 4)))
    assert (2, 3) not in m.gems, \
        "projectile-trace target drives the summon position"


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
