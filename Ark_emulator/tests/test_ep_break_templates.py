"""Generic ON_BEFORE_EP_BREAK_START template dispatch tests.

Covers the element-burst pipeline firing buff templates before the built-in
burst effect: 烛煌 blaze2_t_1 global fire-burst self-heal, thumpy water
break detect (source DEF + shield), and 酒神 S3 phatm2_s_3[token] mad-cage
spawn / refresh on the bursting enemy's tile.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle():
    squad = [{"charId": "char_1040_blaze2", "phase": 2, "level": 1},
             {"charId": "char_1042_phatm2", "phase": 2, "level": 1}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy(b):
    ok, bid = b.deploy("char_1040_blaze2", 2, 3)      # high ground
    assert ok, bid
    ok, pid = b.deploy("char_1042_phatm2", 2, 4)      # high ground
    assert ok, pid
    by_id = {o.inst_id: o for o in b.operators}
    return by_id[bid], by_id[pid]


def _spawn(b, row, col, hp=50000.0):
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _add_detect(buff_key, unit, source, bb=None):
    unit.buffs.append({
        "key": buff_key, "template_key": buff_key,
        "remaining_ticks": 3600 * 30, "layers": 1, "source": source,
        "blackboard": dict(bb or {}),
    })


def test_blaze2_global_fire_burst_heals_source():
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    # the talent listener buff is auto-applied on deploy (deploy_buffs)
    assert any(x.get("key") == "blaze2_t_1" for x in blaze2.buffs)
    blaze2.hp = blaze2.max_hp - 500.0
    hp0 = blaze2.hp
    e = _spawn(b, 3, 4)
    b.add_ep(e, 2, 1000.0)          # FIRE burst
    expect = min(blaze2.max_hp, hp0 + blaze2.max_hp * 0.12)
    assert abs(blaze2.hp - expect) < 1e-6, (blaze2.hp, expect)
    evs = b.events.snapshot_events()
    assert any(x["type"] == "ep_burst" and x["data"]["type"] == 2
               for x in evs)


def test_blaze2_ignores_non_fire_burst():
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    _add_detect("blaze2_t_1", blaze2, blaze2, {"ratio": 0.12})
    blaze2.hp = blaze2.max_hp - 500.0
    hp0 = blaze2.hp
    e = _spawn(b, 3, 4)
    b.add_ep(e, 0, 1000.0)          # SANITY (neural) burst
    assert abs(blaze2.hp - hp0) < 1e-9, "only FIRE bursts heal blaze2"


def test_thumpy_water_break_detect_grants_def_and_shield():
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    e = _spawn(b, 3, 4)
    _add_detect("thumpy[water_break_detect]", e, blaze2, {"def": 30.0})
    b.add_ep(e, 1, 1000.0)          # WATER burst
    ddef = [x for x in blaze2.buffs if x.get("key") == "thumpy[def]"]
    stat = [x for x in ddef if x.get("stat") == "def"]
    assert stat and abs(stat[-1].get("add", 0.0) - 30.0) < 1e-9, ddef
    shield = [x for x in blaze2.buffs if x.get("key") == "thumpy[shield]"]
    assert shield, [x.get("key") for x in blaze2.buffs]


def test_phatm2_neural_burst_spawns_cage():
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    e = _spawn(b, 3, 4)
    _add_detect("phatm2_s_3[token]", e, phatm2)
    b.add_ep(e, 0, 1000.0)          # SANITY burst -> cage on the enemy tile
    cages = [t for t in b.tokens if t.token_id == "token_10055_phatm2_mndclv"]
    assert len(cages) == 1, cages
    cage = cages[0]
    assert (cage.row, cage.col) == (3, 4)
    assert cage.owner is phatm2


def test_phatm2_existing_cage_refresh():
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    e = _spawn(b, 3, 4)
    _add_detect("phatm2_s_3[token]", e, phatm2)
    b.add_ep(e, 0, 1000.0)
    cages = [t for t in b.tokens if t.token_id == "token_10055_phatm2_mndclv"]
    assert len(cages) == 1
    cage = cages[0]
    cage.hp = 1.0                     # damaged cage
    # clear the burst cooldown so the same enemy can burst again
    e.buffs = [x for x in e.buffs if x.get("key") != "ep_burst_cd_0"]
    b.add_ep(e, 0, 1000.0)
    cages = [t for t in b.tokens if t.token_id == "token_10055_phatm2_mndclv"]
    assert len(cages) == 1, "refresh must not duplicate the cage"
    assert abs(cages[0].hp - cages[0].max_hp) < 1e-9, "HP reset on refresh"
    trig = [x for x in cages[0].buffs
            if x.get("key") == "phatm2_s_3[token][trigger]"]
    assert trig, [x.get("key") for x in cages[0].buffs]


def _plain_operator_battle():
    """Single operator with no elemental talents (ep threshold checks)."""
    squad = [{"charId": "char_149_scave", "phase": 2, "level": 50,
              "skillIndex": 0}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    ok, pid = b.deploy("char_149_scave", 3, 3)
    assert ok, pid
    return sim, b, b.operators[-1]


def test_operator_ep_threshold_default_1000():
    """Operator element bars burst at the game default 1000 (NOT level-
    scaled: the old heuristic gave level-50 operators 2000)."""
    sim, b, op = _plain_operator_battle()
    assert b.buffs.ep_max(op) == 1000.0
    b.add_ep(op, 0, 999.0)
    assert not any(x["type"] == "ep_burst"
                   for x in b.events.snapshot_events())
    b.add_ep(op, 0, 1.0)
    assert any(x["type"] == "ep_burst" and x["data"]["type"] == 0
               for x in b.events.snapshot_events())


def test_ep_max_attribute_override():
    """Units with a maxEp attribute burst at that threshold, not 1000."""
    sim, b, op = _plain_operator_battle()
    op.attributes.base["maxEp"] = 2000.0
    assert b.buffs.ep_max(op) == 2000.0
    b.add_ep(op, 0, 1000.0)
    assert not any(x["type"] == "ep_burst"
                   for x in b.events.snapshot_events())
    b.add_ep(op, 0, 1000.0)
    assert any(x["type"] == "ep_burst" and x["data"]["type"] == 0
               for x in b.events.snapshot_events())


def _enemy_spawn(b, row, col, level_type=0, hp=50000.0):
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    e.level_type = level_type
    return e


def _burst_count(b, ep_type):
    return [x for x in b.events.snapshot_events()
            if x["type"] == "ep_burst" and x["data"]["type"] == ep_type]


def _burst_delta(b, ep_type, before):
    return len(_burst_count(b, ep_type)) - before


def test_normal_elite_enemy_ep_threshold_1000():
    """Ordinary and elite enemies burst at the game default 1000
    (PRTS: MAX_EP = 1000 for normal/elite; only leaders get +1000)."""
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    for lv in (0, 1):
        e = _enemy_spawn(b, 3 + lv, 4, level_type=lv)
        assert b.buffs.ep_max(e) == 1000.0, lv
        before = len(_burst_count(b, 0))
        b.add_ep(e, 0, 999.0)
        assert _burst_delta(b, 0, before) == 0, \
            f"level_type={lv} must not burst at 999"
        b.add_ep(e, 0, 1.0)
        assert _burst_delta(b, 0, before) == 1, \
            f"level_type={lv} must burst at 1000"


def test_leader_enemy_ep_threshold_2000():
    """Leader-class (BOSS) enemies burst at 2000 (1000 + 1000 leader
    bonus), per PRTS element page / CH-7."""
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    e = _enemy_spawn(b, 3, 4, level_type=2)
    assert b.buffs.ep_max(e) == 2000.0
    b.add_ep(e, 0, 1999.0)
    assert not _burst_count(b, 0), "leader must not burst at 1999"
    b.add_ep(e, 0, 1.0)
    assert len(_burst_count(b, 0)) == 1, "leader must burst at 2000"


def test_leader_ep_threshold_respects_maxep_attribute():
    """A unit-level maxEp attribute overrides the leader +1000 rule."""
    sim, b = _battle()
    blaze2, phatm2 = _deploy(b)
    e = _enemy_spawn(b, 3, 4, level_type=2)
    e.attributes.base["maxEp"] = 1500.0
    assert b.buffs.ep_max(e) == 1500.0
    b.add_ep(e, 0, 1499.0)
    assert not _burst_count(b, 0)
    b.add_ep(e, 0, 1.0)
    assert len(_burst_count(b, 0)) == 1


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
