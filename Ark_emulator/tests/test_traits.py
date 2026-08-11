# -*- coding: utf-8 -*-
"""Operator trait (特性) system tests.

Covers: charger kill cost refund, merchant periodic cost drain + retreat,
slower sluggish on hit, medic healing of wounded allies, sniper air
priority, caster magical basic attacks, and flying enemies being
unblockable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState
from ark_emulator.targeting import HateSystem


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
    attrs = {"maxHp": hp, "atk": atk, "def": 0.0}
    attrs.update(extra)
    b.spawn_enemy(key, 0, overrides={
        "attributes": attrs, "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(b, op, target):
    """Start + resolve an operator attack (projectile still in flight)."""
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_charger_kill_refund_cost():
    sim, b = _battle()
    b.deploy("char_290_vigna", 3, 3)       # 红豆, charger
    op = b.operators[0]
    assert op.trait_system is not None
    assert op.trait_system.kill_cost_bonus() == 1.0
    cost0 = b.cost
    e = _spawn(b, "enemy_1000_gopro_2", 3, 4, hp=1.0)
    b.apply_damage(e, 9999.0, DamageType.PHYSICAL, source=op)
    assert e.dead
    assert abs((b.cost - cost0) - 1.0) < 1e-6, b.cost - cost0
    assert any(x["type"] == "trait_cost_refund"
               for x in b.events.snapshot_events())


def test_pioneer_has_no_kill_refund():
    sim, b = _battle()
    b.deploy("char_149_scave", 3, 3)       # 清道夫, pioneer (no refund)
    op = b.operators[0]
    assert op.trait_system is not None
    assert op.trait_system.kill_cost_bonus() == 0.0


def test_merchant_cost_drain_and_retreat():
    sim, b = _battle()
    b.deploy("char_272_strong", 3, 3)      # 孑, merchant
    op = b.operators[0]
    assert op.trait_system is not None
    assert op.trait_system.cost_drain() == (3.0, 3.0)
    b.cost = 100.0
    for _ in range(140):
        b.tick_once()
    assert any(x["type"] == "trait_cost_drain"
               for x in b.events.snapshot_events())
    assert b.cost < 100.0
    # insufficient cost -> auto retreat
    b.cost = 2.0
    for _ in range(140):
        b.tick_once()
    assert op not in b.operators


def test_slower_attack_applies_sluggish():
    sim, b = _battle()
    b.deploy("char_278_orchid", 2, 3)      # 梓兰, slower (highland)
    op = b.operators[0]
    assert op.trait_system is not None
    assert abs(op.trait_system.hit_sluggish() - 0.8) < 1e-6
    e = _spawn(b, "enemy_1000_gopro_2", 3, 3, hp=9999.0)
    _land_attack(b, op, e)
    for _ in range(30):
        b.tick_once()
    keys = [x.get("key") for x in e.buffs]
    assert "op_sluggish" in keys, keys


def test_medic_heals_wounded_ally():
    sim, b = _battle()
    b.deploy("char_003_kalts", 2, 3)       # 凯尔希, physician (highland)
    b.deploy("char_149_scave", 3, 3)       # wounded melee ally
    medic = b.operators[0]
    ally = b.operators[1]
    assert medic.trait_system is not None and medic.trait_system.is_healer()
    b.apply_damage(ally, 100.0, DamageType.TRUE, source=None)
    wounded = ally.hp
    assert wounded < ally.max_hp
    for _ in range(400):
        b.tick_once()
        if any(x["type"] == "heal" for x in
               b.events.snapshot_events()[-5:]):
            break
    assert ally.hp > wounded, (wounded, ally.hp)


def test_sniper_prefers_air():
    sim, b = _battle()
    b.deploy("char_124_kroos", 2, 3)       # 克洛丝, fastshot
    op = b.operators[0]
    assert op.trait_system is not None and op.trait_system.prefer_air()
    _spawn(b, "enemy_1000_gopro_2", 3, 4, hp=9999.0)
    air = _spawn(b, "enemy_1005_yokai", 3, 5, hp=9999.0)
    assert air.is_flying, "yokai should be detected as flying"
    target = HateSystem(b).operator_target(op)
    assert target is air, (target.inst_id if target is not None else None)


def test_flying_enemy_not_blockable():
    sim, b = _battle()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    air = _spawn(b, "enemy_1005_yokai", 3, 3, hp=9999.0)
    assert air.is_flying
    b._update_blocking()
    assert op.blocked_enemies == []
    assert air.blocked_by is None


def test_caster_basic_attack_magical():
    sim, b = _battle()
    b.deploy("char_002_amiya", 2, 3)       # 阿米娅, corecaster (highland)
    op = b.operators[0]
    e = _spawn(b, "enemy_1000_gopro_2", 3, 3, hp=9999.0)
    _land_attack(b, op, e)
    for _ in range(30):
        b.tick_once()
    dmg = [x for x in b.events.snapshot_events() if x["type"] == "damage"]
    assert dmg, "no damage events"
    assert dmg[-1]["data"]["type"] == DamageType.MAGICAL


def test_hunter_ammo_and_damage_scale():
    sim, b = _battle()
    b.deploy("char_4104_coldst", 2, 3)       # Bingniang, hunter (highland)
    op = b.operators[0]
    assert op.trait_system is not None and op.trait_system.is_hunter()
    assert op.trait_system.hunter_ammo_max() == 8
    assert op._hunter_ammo == 8
    assert abs(op.trait_system.hunter_atk_scale() - 1.2) < 1e-6
    e = _spawn(b, "enemy_1000_gopro_2", 2, 5, hp=20000.0)
    for _ in range(120):
        b.tick_once()
    evs = b.events.snapshot_events()
    ha = [x for x in evs if x["type"] == "hunter_attack"]
    assert ha, "hunter should fire bullets"
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"].get("source") == op.inst_id]
    assert dmg, "no hunter damage"
    expect = op.attributes.get("atk") * 1.2
    assert abs(dmg[-1]["data"]["amount"] - expect) < 0.1, dmg[-1]
    assert 0 <= op._hunter_ammo < 8


def test_hunter_reloads_when_out_of_ammo():
    sim, b = _battle()
    b.deploy("char_4104_coldst", 2, 3)
    op = b.operators[0]
    op._hunter_ammo = 0
    op.attack_timer = 0.0
    e = _spawn(b, "enemy_1000_gopro_2", 2, 5, hp=20000.0)
    for _ in range(120):
        b.tick_once()
    evs = b.events.snapshot_events()
    assert any(x["type"] == "hunter_reload_start"
               for x in evs), "reload should start when out of ammo"
    assert any(x["type"] == "hunter_reload" for x in evs),         "a bullet should be loaded after the reload interval"
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"].get("source") == op.inst_id]
    expect = op.attributes.get("atk") * 1.2
    assert dmg and abs(dmg[-1]["data"]["amount"] - expect) < 0.1, dmg


def test_hunter_state_in_snapshot():
    sim, b = _battle()
    b.deploy("char_4104_coldst", 2, 3)
    op = b.operators[0]
    hunter = op.to_dict()["trait"]["hunter"]
    assert hunter["maxAmmo"] == 8
    assert abs(hunter["atkScale"] - 1.2) < 1e-6
    assert "ammo" in hunter and "reloading" in hunter


def test_incantationmedic_heals_ally_on_hit():
    sim, b = _battle()
    b.deploy("char_494_vendla", 2, 3)      # Cimei, incantationmedic
    op = b.operators[0]
    assert op.trait_system is not None
    assert abs(op.trait_system.incant_heal_scale() - 0.5) < 1e-6
    b.deploy("char_149_scave", 3, 4)       # wounded ally in range
    ally = b.operators[1]
    b.apply_damage(ally, 400.0, DamageType.TRUE, source=None)
    wounded = ally.hp
    e = _spawn(b, "enemy_1000_gopro_2", 3, 3, hp=9999.0)
    for _ in range(150):
        b.tick_once()
    evs = b.events.snapshot_events()
    heals = [x for x in evs if x["type"] == "heal" and
             x["data"].get("target") == ally.inst_id]
    assert heals, "incantationmedic should heal an ally on attack hit"
    expect = op.attributes.get("atk") * 0.5
    assert any(abs(x["data"]["amount"] - expect) < 0.1
               for x in heals), heals
    assert ally.hp > wounded
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"].get("source") == op.inst_id]
    assert dmg and dmg[-1]["data"]["type"] == DamageType.MAGICAL


def test_chainhealer_jump_heal():
    sim, b = _battle()
    b.deploy("char_4071_peper", 2, 3)      # Mingjiao, chainhealer
    op = b.operators[0]
    assert op.trait_system is not None
    assert op.trait_system.chain_heal_params() == (3, 0.75)
    b.deploy("char_149_scave", 3, 4)
    b.deploy("char_123_fang", 3, 2)
    a1 = b.operators[1]
    a2 = b.operators[2]
    b.apply_damage(a1, 500.0, DamageType.TRUE, source=None)
    b.apply_damage(a2, 500.0, DamageType.TRUE, source=None)
    for _ in range(180):
        b.tick_once()
    evs = b.events.snapshot_events()
    hs1 = [x for x in evs if x["type"] == "heal" and
           x["data"].get("target") == a1.inst_id]
    hs2 = [x for x in evs if x["type"] == "heal" and
           x["data"].get("target") == a2.inst_id]
    assert hs1 and hs2, "both allies should receive chain heals"
    atk = op.attributes.get("atk")
    assert any(abs(x["data"]["amount"] - atk) < 0.1 for x in hs2), hs2
    assert any(abs(x["data"]["amount"] - atk * 0.75) < 0.1
               for x in hs1), hs1
def test_healer_far_heal_falloff():
    sim, b = _battle()
    b.deploy("char_385_finlpp", 2, 3)       # \u6e05\u6d41, therapist (facing right)
    op = b.operators[0]
    tr = op.trait_system
    assert tr is not None and tr.sub_profession == "healer"
    assert tr.heal_falloff_scale(None, b) == 1.0
    # inner zone (2-3, facing right): offset (0,2) is inside
    inner = _spawn(b, "enemy_1000_gopro_2", 2, 5, hp=99999.0)
    # offset (0,3) is outside the 2-3 inner zone
    outer = _spawn(b, "enemy_1000_gopro_2", 2, 6, hp=99999.0)
    assert tr.heal_falloff_scale(inner, b) == 1.0
    assert abs(tr.heal_falloff_scale(outer, b) - 0.8) < 1e-6
    # end-to-end through apply_heal (source = the therapist)
    inner.hp = 50000.0
    outer.hp = 50000.0
    got_in = b.apply_heal(inner, 100.0, source=op)
    got_out = b.apply_heal(outer, 100.0, source=op)
    assert abs(got_in - 100.0) < 1e-6, got_in
    assert abs(got_out - 80.0) < 1e-6, got_out
    # facing rotation: tile (1,3) (offset -2,0) is inner when facing up
    op.direction = 0
    up = _spawn(b, "enemy_1000_gopro_2", 0, 3, hp=99999.0)
    assert tr.heal_falloff_scale(up, b) == 1.0
    op.direction = 1
    assert abs(tr.heal_falloff_scale(up, b) - 0.8) < 1e-6
    # snapshot exposes the falloff parameters
    hf = op.to_dict()["trait"]["healFalloff"]
    assert hf["innerRange"] == "2-3"
    assert abs(hf["scale"] - 0.8) < 1e-6


def test_physician_has_no_heal_falloff():
    sim, b = _battle()
    b.deploy("char_003_kalts", 2, 3)        # \u51ef\u5c14\u5e0c, physician (no falloff)
    op = b.operators[0]
    assert op.trait_system is not None
    assert op.trait_system.sub_profession == "physician"
    tgt = _spawn(b, "enemy_1000_gopro_2", 2, 9, hp=99999.0)
    tgt.hp = 50000.0
    got = b.apply_heal(tgt, 100.0, source=op)
    assert abs(got - 100.0) < 1e-6, got


def test_healer_skill_heal_uses_falloff():
    sim, b = _battle()
    b.deploy("char_385_finlpp", 2, 3)       # \u6e05\u6d41, therapist
    op = b.operators[0]
    outer = _spawn(b, "enemy_1000_gopro_2", 2, 6, hp=99999.0)
    outer.hp = 50000.0
    b.apply_heal(outer, 100.0, source=op)
    evs = b.events.snapshot_events()
    hs = [x for x in evs if x["type"] == "heal" and
          x["data"].get("target") == outer.inst_id]
    assert hs and abs(hs[-1]["data"]["amount"] - 80.0) < 1e-6, hs


# ==================== instructor (\u6559\u5b98) ====================

def test_instructor_atk_scale_120():
    """\u6559\u5b98: basic attacks deal ATK x 1.2 (??, trait bb atk_scale)."""
    sim, b = _battle()
    b.deploy("char_130_doberm", 3, 3)       # \u675c\u5bbe, instructor (melee)
    op = b.operators[0]
    tr = op.trait_system
    assert tr is not None and tr.sub_profession == "instructor"
    assert abs(tr.atk_scale() - 1.2) < 1e-6
    e = _spawn(b, "enemy_1000_gopro_2", 3, 4, hp=99999.0)
    _land_attack(b, op, e)
    for _ in range(30):
        b.tick_once()
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and x["data"].get("source") == op.inst_id]
    assert dmg, "instructor should deal damage"
    expect = op.attributes.get("atk") * 1.2
    assert abs(dmg[-1]["data"]["amount"] - expect) < 0.1, dmg[-1]


def test_instructor_trait_in_snapshot():
    sim, b = _battle()
    b.deploy("char_130_doberm", 3, 3)
    op = b.operators[0]
    assert abs(op.to_dict()["trait"]["atkScale"] - 1.2) < 1e-6


# ==================== bombarder (\u6295\u63b7\u624b) ====================

def _bombarder_battle(char_id):
    sim, b = _battle()
    b.deploy(char_id, 2, 3, direction=1)
    return sim, b, b.operators[0]


def _run_until_aftershock(b, guard=400):
    for _ in range(guard):
        b.tick_once()
        evs = b.events.snapshot_events()
        if any(x["type"] == "attack" and x["data"].get("type") == "aftershock"
               for x in evs[-12:]):
            return True
    return False


def _op_damage_by_target(b, op):
    out = {}
    for x in b.events.snapshot_events():
        if x["type"] == "damage" and x["data"].get("source") == op.inst_id:
            out.setdefault(x["data"].get("target"), []).append(
                x["data"]["amount"])
    return out


def test_bombarder_aftershock_splash_ground_only():
    """\u6295\u63b7\u624b: main hit on target, then 50% ATK physical splash to
    ground enemies in the 3x3 area; flying enemies and out-of-splash ground
    enemies take nothing."""
    sim, b, op = _bombarder_battle("char_1027_greyy2")   # \u627f\u66e6\u683c\u96f7\u4f0a
    tr = op.trait_system
    assert tr.is_bombarder() and tr.ground_only()
    assert tr.bombarder_aftershock_count() == 1
    assert abs(tr.bombarder_append_atk_scale() - 0.5) < 1e-6
    tgt = _spawn(b, "enemy_1000_gopro_2", 2, 4, hp=99999.0)
    n1 = _spawn(b, "enemy_1000_gopro_2", 1, 4, hp=99999.0)
    n2 = _spawn(b, "enemy_1000_gopro_2", 3, 4, hp=99999.0)
    n3 = _spawn(b, "enemy_1000_gopro_2", 2, 5, hp=99999.0)
    fly = _spawn(b, "enemy_1005_yokai", 1, 5, hp=99999.0)   # flying, in splash
    out = _spawn(b, "enemy_1000_gopro_2", 2, 6, hp=99999.0)
    assert _run_until_aftershock(b)
    dmg = _op_damage_by_target(b, op)
    atk = op.attributes.get("atk")
    half = atk * 0.5
    assert len(dmg.get(tgt.inst_id, [])) == 2, dmg
    assert abs(dmg[tgt.inst_id][0] - atk) < 0.1
    assert abs(dmg[tgt.inst_id][1] - half) < 0.1
    for e in (n1, n2, n3):
        hs = dmg.get(e.inst_id, [])
        assert len(hs) == 1 and abs(hs[0] - half) < 0.1, (e.inst_id, hs)
    assert fly.inst_id not in dmg, "aftershock must not hit flying enemies"
    assert out.inst_id not in dmg, "out-of-splash enemy must not be hit"
    evs = b.events.snapshot_events()
    ash = [x for x in evs if x["type"] == "attack" and
           x["data"].get("type") == "aftershock"]
    assert ash and ash[-1]["data"]["waves"] == 1
    assert tgt.inst_id in ash[-1]["data"]["targets"]


def test_wisdel_third_attack_two_aftershocks():
    """\u7ef4\u4ec0\u6234\u5c14: enable_third_attack -> 2 aftershock waves
    (main + 2 x 50% on the target, 2 x 50% on splash neighbours)."""
    sim, b, op = _bombarder_battle("char_1035_wisdel")
    assert op.trait_system.bombarder_aftershock_count() == 2
    tgt = _spawn(b, "enemy_1000_gopro_2", 2, 4, hp=99999.0)
    n = _spawn(b, "enemy_1000_gopro_2", 3, 4, hp=99999.0)
    assert _run_until_aftershock(b)
    dmg = _op_damage_by_target(b, op)
    atk = op.attributes.get("atk")
    half = atk * 0.5
    th = dmg.get(tgt.inst_id, [])
    assert len(th) == 3, th
    assert abs(th[0] - atk) < 0.1 and all(abs(v - half) < 0.1 for v in th[1:])
    nh = dmg.get(n.inst_id, [])
    assert len(nh) == 2 and all(abs(v - half) < 0.1 for v in nh), nh


def test_rosmon_single_aftershock():
    """\u8ff7\u8fed\u9999: attack@times=2 means 2 total damage rounds
    (main + 1 aftershock), matching the PRTS base trait."""
    sim, b, op = _bombarder_battle("char_391_rosmon")
    assert op.trait_system.bombarder_aftershock_count() == 1
    tgt = _spawn(b, "enemy_1000_gopro_2", 2, 4, hp=99999.0)
    assert _run_until_aftershock(b)
    th = _op_damage_by_target(b, op).get(tgt.inst_id, [])
    assert len(th) == 2, th


def test_bombarder_ground_only_targeting():
    """\u6295\u63b7\u624b cannot select flying enemies for basic attacks."""
    sim, b, op = _bombarder_battle("char_1027_greyy2")
    assert op.trait_system.ground_only()
    assert not op.trait_system.prefer_air()
    _spawn(b, "enemy_1005_yokai", 2, 4, hp=99999.0)
    assert HateSystem(b).operator_target(op) is None
    g = _spawn(b, "enemy_1000_gopro_2", 2, 5, hp=99999.0)
    assert HateSystem(b).operator_target(op) is g


def test_bombarder_trait_in_snapshot():
    sim, b, op = _bombarder_battle("char_1027_greyy2")
    af = op.to_dict()["trait"]["aftershock"]
    assert af["count"] == 1
    assert abs(af["appendAtkScale"] - 0.5) < 1e-6
    assert abs(af["splashRadius"] - 0.9) < 1e-6
    assert af["groundOnly"] is True
