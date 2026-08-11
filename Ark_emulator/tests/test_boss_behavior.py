# -*- coding: utf-8 -*-
"""Boss-level enemy behaviour verification against the real skill data:

- enemy_1505_frstar (frost star): ArcticBlast (cd 8.5s, atk_scale 1.5
  MAGICAL, target attack_speed -50 for 8s) and IceShield (cd 30s).
- enemy_1510_frstar2 (frost star "winter mark"): all five skills resolve
  with their prefabKeys and blackboards.
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
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _essence_battle():
    """进化的本质 (enemy_1519_bgball): three-form evolution boss.  Two
    operators hold it in place; life points are padded so waves leaking
    cannot end the battle before the evolution sequence completes."""
    sim, b = _battle()
    b.life_point = 999
    b.deploy("char_149_scave", 3, 3)
    b.deploy("char_1040_blaze2", 2, 3)
    e = b.spawn_enemy("enemy_1519_bgball", 0, overrides={
        "attributes": {"maxHp": 500000.0, "atk": 300.0, "def": 100.0},
        "row": 3, "col": 4})
    e.state = EnemyState.ATTACK
    return sim, b, e


def test_essence_of_evolution_mode_machine():
    """进化的本质 evolves 初生 -> 进化 -> 完美 and releases the per-form
    蓄力击 chain (AttackWarning -> Effect -> RealAttack) in each form;
    the perfect form rapid-fires.  PRTS: forms deal 900/1000/1200 true
    damage to all operators and the perfect form attacks much faster."""
    sim, b, e = _essence_battle()
    sc = e.skill_controller
    assert sc.mode_index == 0
    # switch skills carry the form anim keys (C1_Die->C2_Idle etc.)
    sw2 = next(s for s in sc.skills if s.prefab_key == "SwitchToMode2")
    assert (sw2.mode_from, sw2.mode_to) == (0, 1)
    sw3 = next(s for s in sc.skills if s.prefab_key == "SwitchToMode3")
    assert (sw3.mode_from, sw3.mode_to) == (1, 2)
    m1r = next(s for s in sc.skills if s.prefab_key == "M1RealAttack")
    assert m1r.mode_skill == 0 and m1r.mode_chain_stage == "real"
    assert m1r.mode_chain_only, "chain stages are not picked standalone"

    casts = []
    switches = []
    b.events.subscribe("skill_cast",
                       lambda ev: casts.append(
                           (ev.tick, (ev.data or {}).get("skill"))))
    b.events.subscribe("enemy_mode_switch",
                       lambda ev: switches.append(
                           (ev.tick, (ev.data or {}).get("mode"))))
    for _ in range(400 * 30):
        b.tick_once()
        if len(switches) >= 2 and sum(
                1 for _, k in casts if k == "M3AttackWarning") >= 2:
            break
    keys = [k for _, k in casts]
    # form 1: 蓄力击 chain in order
    i = keys.index("M1AttackWarning")
    assert keys[i + 1] == "M1Effect" and keys[i + 2] == "M1RealAttack", keys
    # evolution order and perfect-form rapid attack
    assert [m for _, m in switches] == [1, 2], switches
    i2 = keys.index("M2AttackWarning")
    assert keys[i2 + 1] == "M2Effect" and keys[i2 + 2] == "M2RealAttack"
    m3s = [t for t, k in casts if k == "M3AttackWarning"]
    assert len(m3s) >= 2
    assert all(t2 - t1 <= 180 for t1, t2 in zip(m3s, m3s[1:])), m3s
    assert sc.mode_index == 2
    snap = next(o for o in b.snapshot()["enemies"]
                if o.get("instId") == e.inst_id)
    assert snap["modeIndex"] == 2


def test_essence_charged_attack_hits_all_operators():
    """初生形态蓄力击 (M1AttackWarning -> M1Effect -> M1RealAttack) deals
    the prefab's true damage (blackboard damage=600) to EVERY operator
    (PRTS: 900 true to all; data value 600 pending scaling calibration)."""
    sim, b, e = _essence_battle()
    for o in b.operators:
        o.attributes.base["maxHp"] = o.max_hp * 4
        o.max_hp = o.max_hp * 4
        o.hp = o.max_hp
    hp0 = {o.inst_id: o.hp for o in b.operators}
    dmg = []
    b.events.subscribe(
        "damage",
        lambda ev: dmg.append((ev.tick, (ev.data or {}).get("target"),
                               (ev.data or {}).get("type"),
                               (ev.data or {}).get("amount")))
        if (ev.data or {}).get("type") == DamageType.TRUE else None)
    for _ in range(1300):
        b.tick_once()
    # one M1 chain (two casts) -> each operator took 600 pure per cast
    for o in b.operators:
        pure = [d for d in dmg if d[1] == o.inst_id and d[2] == DamageType.TRUE
                and d[3] and d[3] >= 500.0]
        assert len(pure) >= 1, (o.char_id, pure)
        assert all(abs(d[3] - 600.0) < 1e-6 for d in pure), (o.char_id, pure)
        assert hp0[o.inst_id] - o.hp >= 600.0


def test_frost_star_skills_resolve():
    sim, b = _battle()
    e = b.spawn_enemy("enemy_1505_frstar", 0)
    sc = e.skill_controller
    assert sc is not None
    skills = sorted((s.prefab_key, s.priority, s.cooldown)
                    for s in sc.skills)
    assert skills == [("ArcticBlast", 1.0, 8.5),
                      ("IceShield", 2.0, 30.0)]
    ab = next(s for s in sc.skills if s.prefab_key == "ArcticBlast")
    assert ab.blackboard.get("atk_scale") == 1.5
    assert ab.blackboard.get("duration") == 8.0
    assert ab.blackboard.get("attack_speed") == -50.0
    assert ab.blackboard.get("range_radius") == 2.5
    ish = next(s for s in sc.skills if s.prefab_key == "IceShield")
    assert ish.blackboard.get("max_cnt") == 2.0


def test_frost_star_arctic_blast_cast_cycle():
    """ArcticBlast fires every ~8.5s at an in-range operator and lands
    atk x 1.5 MAGICAL damage plus an 8s attack_speed -50 buff."""
    sim, b = _battle()
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    e = b.spawn_enemy("enemy_1505_frstar", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    b.events.log = []
    cast_ticks = []
    buff_ticks = 0
    for i in range(1500):
        b.tick_once()
        cs = sc.casting_state()
        if cs and cs["skill"] == "ArcticBlast":
            cast_ticks.append(b.tick)
        if any(x.get("key") == "arctic_blast" for x in op.buffs):
            buff_ticks += 1
    casts = [x for x in b.events.snapshot_events()
             if x["type"] == "skill_cast"]
    assert len(casts) >= 2
    assert all(x["data"]["skill"] == "ArcticBlast" for x in casts[:2])
    # ~8.5s cooldown (255 ticks) between the first two casts; enemy skills
    # are gated by the attack timer, so the observed interval is the cd
    # plus at most one attack interval + cast duration (255..~345 ticks).
    delta = casts[1]["tick"] - casts[0]["tick"]
    assert 250 <= delta <= 350, delta
    # atk x 1.5 MAGICAL on the operator
    hits = [x["data"] for x in b.events.snapshot_events()
            if x["type"] == "damage" and
            x["data"].get("source") == e.inst_id and
            x["data"].get("target") == op.inst_id and
            abs(x["data"].get("amount", 0.0) - 150.0) < 0.01]
    assert hits, "ArcticBlast must land atk*1.5 damage"
    assert all(h["type"] == DamageType.MAGICAL for h in hits)
    # attack_speed -50 buff lasts 8s = 240 ticks
    assert 230 <= buff_ticks <= 250, buff_ticks


def test_frost_star_ice_shield_casts_after_30s():
    sim, b = _battle()
    b.deploy("char_127_estell", 3, 4)
    e = b.spawn_enemy("enemy_1505_frstar", 0, overrides={
        "attributes": {"atk": 1.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    b.events.log = []
    for i in range(1350):
        b.tick_once()
    casts = [x["data"] for x in b.events.snapshot_events()
             if x["type"] == "skill_cast"]
    shields = [x for x in casts if x["skill"] == "IceShield"]
    assert shields, "IceShield must cast within 45s"
    assert shields[0].get("target") is not None


def test_frost_star_winter_mark_five_skills():
    sim, b = _battle()
    e = b.spawn_enemy("enemy_1510_frstar2", 0)
    sc = e.skill_controller
    assert sc is not None
    keys = sorted(s.prefab_key for s in sc.skills)
    assert keys == ["IceBurst", "IceBurst[Reborn]", "IceShield",
                    "IceShield[Reborn]", "SummonFrosts"], keys
    by = {s.prefab_key: s for s in sc.skills}
    assert by["IceBurst"].blackboard.get("freeze") == 10.0
    assert by["SummonFrosts"].max_trigger_time == 1
    assert by["IceShield[Reborn]"].blackboard.get("max_cnt") == 3.0


def test_frost_star_arctic_blast_aoe_radius():
    """ArcticBlast splash: all operators within range_radius 2.5 of the
    impact take the atk x 1.5 MAGICAL hit; one outside does not."""
    sim, b = _battle()
    b.deploy("char_127_estell", 3, 4)
    op1 = b.operators[0]
    b.deploy("char_149_scave", 3, 3)
    op2 = b.operators[1]
    b.deploy("char_102_texas", 3, 7)
    op3 = b.operators[2]
    e = b.spawn_enemy("enemy_1505_frstar", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    ab = next(s for s in sc.skills if s.prefab_key == "ArcticBlast")
    assert float(ab.blackboard.get("range_radius") or 0.0) == 2.5
    sc._start_cast((ab, op1))
    for _ in range(500):
        b.tick_once()
        if sc.casting is None:
            break
    dmg = [x["data"] for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("source") == e.inst_id and
           abs(x["data"].get("amount", 0.0) - 150.0) < 0.01]
    hit_ids = {d["target"] for d in dmg}
    assert op1.inst_id in hit_ids, hit_ids
    assert op2.inst_id in hit_ids, hit_ids
    assert op3.inst_id not in hit_ids, hit_ids


def test_enemy_mapwide_direct_aoe():
    """Direct-hit skills with range_radius >= 10 (map-wide) hit every
    operator (Punch range_radius 13), not just the primary target."""
    sim, b = _battle()
    b.deploy("char_127_estell", 3, 4)
    op1 = b.operators[0]
    b.deploy("char_149_scave", 3, 3)
    op2 = b.operators[1]
    b.deploy("char_102_texas", 1, 5)
    op3 = b.operators[2]
    e = b.spawn_enemy("enemy_2126_dycyue", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 8})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    pu = next(s for s in sc.skills if s.prefab_key == "Punch")
    assert float(pu.blackboard.get("range_radius") or 0.0) >= 10.0
    sc._start_cast((pu, op1))
    for _ in range(500):
        b.tick_once()
        if sc.casting is None:
            break
    dmg = [x["data"] for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("source") == e.inst_id and
           x["data"].get("amount", 0.0) > 0.0]
    hit_ids = {d["target"] for d in dmg}
    assert {op1.inst_id, op2.inst_id, op3.inst_id} <= hit_ids, hit_ids


def test_talulah_dragonfire_dot_ramps():
    """DragonFire applies dragon_fire to the operator; the DoT deals PURE
    baseDamage + addOnDamage ramping linearly over addOnDuration seconds."""
    sim, b = _battle()
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    for _ in range(30):
        b.tick_once()
    hp0 = op.hp
    e = b.spawn_enemy("enemy_3002_ftrtal_s", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 8})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    df = next(s for s in sc.skills if s.prefab_key == "DragonFire")
    sc._start_cast((df, op))
    b.events.log = []
    guard = 0
    while sc.casting is not None and guard < 400:
        b.tick_once()
        guard += 1
    assert b.buffs.get(op, "dragon_fire") is not None, op.buffs
    for _ in range(120):
        b.tick_once()
    dmg = [x["data"] for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("target") == op.inst_id]
    pure = [d for d in dmg if d.get("type") == 2]   # PURE
    assert len(pure) >= 2, pure
    assert pure[1]["amount"] > pure[0]["amount"], pure   # ramping
    assert op.hp < hp0


def test_enemy_small_radius_attack_aoe():
    """Attack-typed direct skills with a small range_radius splash hit all
    operators within the effect radius of the impact (CombatAoe 1.6)."""
    sim, b = _battle()
    b.deploy("char_127_estell", 3, 4)
    op1 = b.operators[0]
    b.deploy("char_149_scave", 3, 3)
    op2 = b.operators[1]
    b.deploy("char_102_texas", 1, 5)
    op3 = b.operators[2]
    for _ in range(30):
        b.tick_once()
    for o in b.operators:
        o.max_hp = 1e9
        o.hp = 1e9
    e = b.spawn_enemy("enemy_2124_dyjsfg", 0, overrides={
        "attributes": {"atk": 1000.0}, "row": 3, "col": 8})
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    sk = next(s for s in sc.skills if s.prefab_key == "CombatAoe")
    assert float(sk.blackboard.get("range_radius") or 0.0) == 1.6
    sc._start_cast((sk, op1))
    b.events.log = []
    guard = 0
    while sc.casting is not None and guard < 600:
        b.tick_once()
        guard += 1
    dmg = {x["data"]["target"] for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("source") == e.inst_id and
           x["data"].get("amount", 0.0) > 0.0}
    assert op1.inst_id in dmg and op2.inst_id in dmg, dmg
    assert op3.inst_id not in dmg, dmg


def _essence_fragile():
    """进化的本质 with a low maxHp so the HP-threshold evolution can be
    reached quickly in tests."""
    sim, b = _battle()
    b.life_point = 999
    b.deploy("char_149_scave", 3, 3)
    b.deploy("char_1040_blaze2", 2, 3)
    e = b.spawn_enemy("enemy_1519_bgball", 0, overrides={
        "attributes": {"maxHp": 100000.0, "atk": 300.0, "def": 0.0,
                       "magicResistance": 0.0},
        "row": 3, "col": 4})
    e.state = EnemyState.ATTACK
    return sim, b, e


def test_essence_mode_params_from_talent_blackboard():
    """The form machine parameters live in the enemy talentBlackboard
    (previously not loaded at all): mode_1.hp_ratio 0.6, mode_2.hp_ratio
    0.2, evolve_time 100s, side resistances 0.8 left/right, perfect
    self-dot 300, summon cadence 5/3/2s."""
    sim, b, e = _essence_fragile()
    sc = e.skill_controller
    mp = sc.mode_params
    assert abs(mp[0]["hp_ratio"] - 0.6) < 1e-9, mp
    assert abs(mp[1]["hp_ratio"] - 0.2) < 1e-9, mp
    assert abs(mp[0]["evolve_time"] - 100.0) < 1e-9
    assert abs(mp[0]["damage_resistance"] - 0.8) < 1e-9
    assert mp[0]["direction"] == 3.0          # left
    assert mp[1]["direction"] == 1.0          # right
    assert abs(mp[2]["damage_resistance"] - 0.99) < 1e-9
    assert abs(mp[2]["damage"] - 300.0) < 1e-9
    assert abs(mp[0]["summon_interval"] - 5.0) < 1e-9
    assert mp[0]["summon_branch_id"] == "branch_1"


def test_essence_hp_threshold_evolution_and_entry_invincible():
    """PRTS: 初生 switches to 进化 when HP < 60%, 进化 -> 完美 when HP
    < 20%; entering a new form grants 10s invincible
    (invincible_after_skill_duration)."""
    sim, b, e = _essence_fragile()
    sc = e.skill_controller
    op = b.operators[0]
    switches = []
    b.events.subscribe("enemy_mode_switch",
                       lambda ev: switches.append(
                           (ev.tick, (ev.data or {}).get("mode"))))
    # drop below 60% -> SwitchToMode2 (cd 5s) -> 进化 + invincible
    b.apply_damage(e, 45000.0, DamageType.TRUE, source=op)
    for _ in range(600):
        b.tick_once()
        if sc.mode_index == 1:
            break
    assert sc.mode_index == 1, sc.mode_index
    assert e.invincible(), "form entry must grant 10s invincible"
    assert switches and switches[0][1] == 1
    # drop below 20% (current hp <= 55k, need < 20k) -> 完美 + invincible
    e.hp = 15000.0
    for _ in range(600):
        b.tick_once()
        if sc.mode_index == 2:
            break
    assert sc.mode_index == 2, sc.mode_index
    assert e.invincible()


def test_essence_side_damage_resistance():
    """初生/进化 forms reduce physical & magic damage from one side
    (direction 3 = left / direction 1 = right) by 80%; 完美 form reduces
    every non-self physical/magic source by 99%.  True damage passes."""
    sim, b, e = _essence_fragile()
    sc = e.skill_controller
    b.deploy("char_1040_blaze2", 3, 3)     # left of boss (col 3 < 4)
    b.deploy("char_149_scave", 3, 5)       # right of boss (col 5 > 4)
    left = b.operators[-1] if b.operators[-1].col < 4 else b.operators[0]
    right = b.operators[-1] if b.operators[-1].col > 4 else b.operators[0]
    assert left.col < 4 and right.col > 4, (left.col, right.col)
    # mode 1 (进化): sources on the RIGHT (direction 1) are reduced 80%
    sc.mode_index = 1
    hp0 = e.hp
    b.apply_damage(e, 1000.0, DamageType.PHYSICAL, source=left)
    assert abs((hp0 - e.hp) - 1000.0) < 1e-6, (hp0 - e.hp)
    hp1 = e.hp
    b.apply_damage(e, 1000.0, DamageType.PHYSICAL, source=right)
    assert abs((hp1 - e.hp) - 200.0) < 1e-6, (hp1 - e.hp)
    # true damage from the reduced side is unaffected
    hp2 = e.hp
    b.apply_damage(e, 1000.0, DamageType.TRUE, source=right)
    assert abs((hp2 - e.hp) - 1000.0) < 1e-6
    # mode 2 (完美): global 99% physical/magic reduction, any source
    sc.mode_index = 2
    hp3 = e.hp
    b.apply_damage(e, 1000.0, DamageType.PHYSICAL, source=left)
    assert abs((hp3 - e.hp) - 10.0) < 1e-6, (hp3 - e.hp)


def test_essence_perfect_form_self_dot():
    """完美形态: 每秒受到300点真实伤害 (mode_3.interval 1s, mode_3.damage
    300) - the boss drains its own HP."""
    sim, b = _battle()
    b.life_point = 999
    e = b.spawn_enemy("enemy_1519_bgball", 0, overrides={
        "attributes": {"maxHp": 100000.0, "atk": 300.0, "def": 0.0,
                       "magicResistance": 0.0},
        "row": 3, "col": 4})
    e.state = EnemyState.ATTACK
    sc = e.skill_controller
    sc.mode_index = 2
    hp0 = e.hp
    for _ in range(30):      # 1s
        b.tick_once()
    assert abs((hp0 - e.hp) - 300.0) < 1e-6, (hp0 - e.hp)
    hp1 = e.hp
    for _ in range(60):      # 2s more
        b.tick_once()
    assert abs((hp1 - e.hp) - 600.0) < 1e-6, (hp1 - e.hp)
