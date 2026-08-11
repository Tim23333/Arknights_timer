# -*- coding: utf-8 -*-
"""Dynamic skill-placed field tiles: Thumpy S3 portable conveyor belt.

Covers tile placement in front of the operator, pull of unblocked
mass<=4 enemies toward the operator, periodic physical + erosion damage,
heavy enemies being unaffected by the pull (but still damaged), and tile
cleanup on withdraw / expiry.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _activate_s3(b):
    b.deploy("char_4235_thumpy", 3, 3)       # 珊比, ground, facing right
    op = b.operators[0]
    sc = op.skill_controller
    idx3 = [i for i, s in enumerate(sc.skills) if "thumpy_3" in s.skill_id][0]
    op.sp = sc.skills[idx3].sp_cost
    ok, msg = sc.activate(idx3)
    assert ok, msg
    return op


def _spawn(b, key, row, col, mass=1.0, hp=5000.0):
    b.spawn_enemy(key, 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": 0.0,
                       "massLevel": mass},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def test_thumpy_s3_places_conveyor_tiles():
    sim, b = _battle()
    op = _activate_s3(b)
    assert sorted(b._skill_tiles.keys()) == [
        (3, 4), (3, 5), (3, 6), (3, 7)], b._skill_tiles.keys()
    evs = [x for x in b.events.snapshot_events()
           if x["type"] == "skill_tile_placed"]
    assert evs and len(evs[-1]["data"]["tiles"]) == 4
    assert evs[-1]["data"]["instId"] == op.inst_id


def test_thumpy_s3_pulls_and_damages_enemy():
    sim, b = _battle()
    _activate_s3(b)
    e = _spawn(b, "enemy_1000_gopro_2", 3, 5, mass=1.0)
    hp0 = e.hp
    for _ in range(90):
        b.tick_once()
    evs = b.events.snapshot_events()
    pulls = [x for x in evs
             if x["type"] == "conveyor_pull" and
             x["data"]["unit"] == e.inst_id]
    assert pulls, "enemy should be pulled toward the operator"
    assert e.col == 3 and e.row == 3, (e.row, e.col)
    assert e.hp < hp0, "belt should deal periodic physical damage"
    # erosion (water) accumulated while standing on the belt
    ep = [x for x in e.buffs if x.get("key") == "ep_water"]
    assert ep and ep[-1].get("value", 0.0) > 0, [x.get("key") for x in e.buffs]
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"].get("source") and
           x["data"]["target"] == e.inst_id]
    phys = [x for x in dmg if x["data"]["type"] == 0]
    assert phys, "periodic physical damage events expected"


def test_thumpy_s3_heavy_enemy_not_pulled_but_damaged():
    sim, b = _battle()
    _activate_s3(b)
    e = _spawn(b, "enemy_1000_gopro_2", 3, 5, mass=6.0)
    hp0 = e.hp
    for _ in range(60):
        b.tick_once()
    evs = b.events.snapshot_events()
    pulls = [x for x in evs
             if x["type"] == "conveyor_pull" and
             x["data"]["unit"] == e.inst_id]
    assert not pulls, "mass>4 enemies must not be pulled"
    assert e.hp < hp0, "heavy enemies still take belt damage"


def test_thumpy_s3_tiles_removed_on_withdraw():
    sim, b = _battle()
    op = _activate_s3(b)
    assert b._skill_tiles
    b.withdraw(op.inst_id)
    assert not b._skill_tiles
    assert any(x["type"] == "skill_tile_removed"
               for x in b.events.snapshot_events())


def test_thumpy_s3_tiles_expire():
    sim, b = _battle()
    _activate_s3(b)
    for rc in list(b._skill_tiles):
        b._skill_tiles[rc]["expiry_tick"] = b.tick + 20
    for _ in range(30):
        b.tick_once()
    assert not b._skill_tiles



def test_thumpy_s3_erosion_burst_extra_def_down():
    """\u73c0\u6bd4 S3: enemies on the belt take a permanent stackable
    -30 DEF each time water erosion bursts (skill bb ep_break_def)."""
    sim, b = _battle()
    op = _activate_s3(b)
    # heavy enemy: not pulled off the belt, so the burst is triggered by the
    # belt's own damage tick (and the s3 mark is present at burst time)
    e = _spawn(b, "enemy_1000_gopro_2", 3, 5, mass=6.0, hp=50000.0)
    # pre-fill water EP near the burst threshold; the belt's erosion ticks
    # (talent ep_damage_ratio) push it over within ~1s.
    b.add_ep(e, 1, 990.0)
    for _ in range(180):
        b.tick_once()
        if any(x["type"] == "thumpy_ep_break"
               for x in b.events.snapshot_events()):
            break
    evs = b.events.snapshot_events()
    breaks = [x for x in evs if x["type"] == "thumpy_ep_break"]
    assert breaks, "belt water burst should apply the S3 extra def debuff"
    assert breaks[-1]["data"]["defDelta"] == -30.0, breaks[-1]
    assert breaks[-1]["data"]["source"] == op.inst_id
    db = [x for x in e.buffs if x.get("key") == "thumpy_ep_break_def"]
    assert db, [x.get("key") for x in e.buffs]
    assert abs(db[-1]["add"] + 30.0) < 1e-6, db[-1]
    assert db[-1]["layers"] >= 1
    assert abs(db[-1]["layers"] * db[-1]["add"] -
               (-30.0 * db[-1]["layers"])) < 1e-6


if __name__ == "__main__":
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
    print("all skill tile tests passed" if not failed
          else f"{failed} failed")
    sys.exit(1 if failed else 0)
