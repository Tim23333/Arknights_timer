# -*- coding: utf-8 -*-
"""驭械术师 (funnel) floating-drone tests.

Covers: deploy-time drone spawn, the 20%->+15%->110% damage ramp, magical
damage on ground and flying targets, the operator never basic-attacking,
skill drone-count bonuses (S1 +1 / S3 +2), S2 attack-range override, S3
whole-battlefield targeting + sluggish, and snapshot exposure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7     # no natural recovery
    b.battle_cost_add(100.0)
    return sim, b


def _spawn(b, key, row, col, hp=99999.0, atk=0.0, **extra):
    attrs = {"maxHp": hp, "atk": atk, "def": 0.0, "magicResistance": 0.0}
    attrs.update(extra)
    b.spawn_enemy(key, 0, overrides={
        "attributes": attrs, "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _funnel_hits(b, unit_id):
    out = []
    seen = set()
    for x in b.events.log:
        if x.type == "funnel_attack" and x.data.get("unit") == unit_id \
                and x.seq not in seen:
            seen.add(x.seq)
            out.append(x.data)
    return out


def test_funnel_deploy_spawns_drone():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)   # 澄闪, funnel
    op = b.operators[0]
    tr = op.trait_system
    assert tr is not None and tr.is_funnel()
    assert tr.funnel_params() == {"init": 0.2, "delta": 0.15,
                                  "max": 1.1, "max_stack": 6}
    drones = getattr(op, "_funnel_drones", [])
    assert len(drones) == 1
    assert len(op.to_dict()["funnelDrones"]) == 1


def test_funnel_damage_ramp_magical():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    e = _spawn(b, "enemy_1000_gopro_2", 2, 4)
    for _ in range(400):
        b.tick_once()
    hits = _funnel_hits(b, op.inst_id)
    assert len(hits) >= 4, hits
    atk = op.attributes.get("atk")
    expect = [0.2, 0.35, 0.5, 0.65, 0.8, 0.95, 1.1]
    for i, h in enumerate(hits[:4]):
        assert abs(h["atkScale"] - expect[i]) < 1e-6, (i, h)
        assert abs(h["amount"] - atk * expect[i]) < 0.1, h
    dmg = [x for x in b.events.log if x.type == "damage" and
           x.data.get("source") == op.inst_id]
    assert dmg and dmg[-1].data.get("type") == DamageType.MAGICAL


def test_funnel_drone_hits_flying():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    fly = _spawn(b, "enemy_1005_yokai", 1, 4)   # flying, in range
    for _ in range(400):
        b.tick_once()
    hits = [h for h in _funnel_hits(b, op.inst_id)
            if h.get("target") == fly.inst_id]
    assert hits, "drones must be able to hit flying enemies"


def test_funnel_operator_never_basic_attacks():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    _spawn(b, "enemy_1000_gopro_2", 2, 4)
    for _ in range(200):
        b.tick_once()
    launches = [x for x in b.events.log
                if x.type == "attack" and
                x.data.get("type") == "projectile_launch" and
                x.data.get("unit") == op.inst_id]
    assert not launches, "funnel operator should not basic-attack"


def test_funnel_s1_drone_bonus_and_stats():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    sc = op.skill_controller
    atk0 = op.attributes.get("atk")
    as0 = op.attributes.get("attackSpeed")
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    assert len(op._funnel_drones) == 2
    assert abs(op.attributes.get("atk") / atk0 - 1.2) < 1e-6
    assert abs(op.attributes.get("attackSpeed") - (as0 + 20)) < 1e-6


def test_funnel_s2_range_override_and_count():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    sc = op.skill_controller
    base_n = len(op.range_shape)
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    assert len(op._funnel_drones) == 2
    assert len(op.range_shape) > base_n, (base_n, len(op.range_shape))


def test_funnel_s3_whole_field_sluggish_and_count():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    sc = op.skill_controller
    # far away, outside the operator's base range (rows 1-3, cols 3-5)
    far = _spawn(b, "enemy_1000_gopro_2", 6, 9)
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    assert len(op._funnel_drones) == 3
    hit = False
    for _ in range(500):
        b.tick_once()
        if any(h.get("target") == far.inst_id
               for h in _funnel_hits(b, op.inst_id)):
            hit = True
        if hit:
            break
    assert hit, "S3 drones must reach enemies outside the operator range"
    assert any(x.get("key") == "op_sluggish" for x in far.buffs), far.buffs


def test_funnel_rockr_basic():
    sim, b = _battle()
    b.deploy("char_4040_rockr", 2, 3, direction=1)   # 洛洛, funnel
    op = b.operators[0]
    assert op.trait_system.is_funnel()
    e = _spawn(b, "enemy_1000_gopro_2", 2, 4)
    for _ in range(400):
        b.tick_once()
    hits = _funnel_hits(b, op.inst_id)
    assert len(hits) >= 2, hits
    assert abs(hits[0]["atkScale"] - 0.2) < 1e-6
    assert e.hp < e.max_hp


def test_talent_permanent_stats_applied():
    """Deploy-time talent stat modifiers: ?? ?? 15 (E2), ??? ????
    160 (E2), and ?? does NOT get her aura atk as a self stat."""
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    assert op.attributes.get("magicResistPenetrateFixed") == 15.0

    sim2, b2 = _battle()
    b2.deploy("char_130_doberm", 3, 3, direction=1)
    op2 = b2.operators[0]
    assert not any(k == "atk" and any(m[0] == "mul" for m in v)
                   for k, v in dict(op2.attributes._mods).items()),         dict(op2.attributes._mods)

    sim3, b3 = _battle()
    b3.deploy("char_391_rosmon", 2, 3, direction=1)
    op3 = b3.operators[0]
    assert op3.attributes.get("defPenetrateFixed") == 160.0


def test_funnel_destruct_forced():
    """?? talent 1 ?????: at 40 layers the next drone attack
    self-destructs for 3.0 x ATK magical damage on the 3x3 area, resets the
    drone's layers and trait ramp, and requires an active skill."""
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    e1 = _spawn(b, "enemy_1000_gopro_2", 2, 4)
    e2 = _spawn(b, "enemy_1000_gopro_2", 1, 4)
    far = _spawn(b, "enemy_1000_gopro_2", 6, 9)
    d = op._funnel_drones[0]
    d.destruct_layers = 40
    hit = None
    for _ in range(600):
        b.tick_once()
        hit = next((x for x in b.events.log
                    if x.type == "funnel_destruct"), None)
        if hit is not None:
            break
    assert hit is not None, "no self-destruct fired"
    data = hit.data
    assert abs(data["atkScale"] - 3.0) < 1e-6
    assert data["targets"] and far.inst_id not in data["targets"]
    assert abs(data["amount"] - op.attributes.get("atk") * 3.0
               * len(data["targets"])) < 1.0, data
    dmg = [x for x in b.events.log if x.type == "damage" and
           x.data.get("source") == op.inst_id]
    dest_dmg = [x for x in dmg if x.data.get("target") in data["targets"]
                and x.data.get("amount") >= op.attributes.get("atk") * 3.0 - 1.0]
    assert dest_dmg and dest_dmg[-1].data.get("type") == DamageType.MAGICAL
    assert d.destruct_layers == 1 and d.stacks == 0


def test_funnel_destruct_requires_active_skill():
    sim, b = _battle()
    b.deploy("char_377_gdglow", 2, 3, direction=1)
    op = b.operators[0]
    _spawn(b, "enemy_1000_gopro_2", 2, 4)
    for _ in range(300):
        b.tick_once()
    assert not any(x.type == "funnel_destruct" for x in b.events.log)
    assert op._funnel_drones[0].destruct_layers == 1


def test_rockr_s2_overload_raises_cap():
    """?? S2 ??: trait damage cap 1.1 x scale 1.5 = 1.65, ramp stacks
    keep growing past 6 to reach the raised cap."""
    sim, b = _battle()
    b.deploy("char_4040_rockr", 2, 3, direction=1)
    op = b.operators[0]
    sc = op.skill_controller
    _spawn(b, "enemy_1000_gopro_2", 2, 4)
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    for _ in range(900):
        b.tick_once()
    scales = [h["atkScale"] for h in _funnel_hits(b, op.inst_id)]
    assert scales and max(scales) > 1.1, max(scales) if scales else None
    assert abs(max(scales) - 1.65) < 1e-6, max(scales)
