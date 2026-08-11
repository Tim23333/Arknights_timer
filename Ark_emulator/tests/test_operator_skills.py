# -*- coding: utf-8 -*-
"""Operator skill system tests: AUTO cast, cost recovery, damage type,
additive stat buffs."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState, DamageType


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7     # no natural recovery
    b.battle_cost_add(100.0)
    return sim, b


def test_auto_skill_casts_and_gains_cost():
    sim, b = _battle()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    sc = op.skill_controller
    types = [(s.skill_id, s.skill_type) for s in sc.skills]
    assert any(t == 2 for _, t in types), types   # AUTO skill present
    cost_before = b.cost
    fired = None
    for _ in range(2400):
        b.tick_once()
        if sc.active is not None:
            fired = sc.active.skill.skill_id
            break
    assert fired == "skcom_charge_cost[2]", fired
    for _ in range(30):
        b.tick_once()
    assert abs((b.cost - cost_before) - 9.0) < 0.01, b.cost - cost_before


def test_attack_speed_buff_additive():
    sim, b = _battle()
    b.deploy("char_003_kalts", 2, 3)   # ranged -> highland
    op = b.operators[0]
    base = op.attributes.get("attackSpeed")
    op.attributes.add_modifier("attackSpeed", additive=30)
    assert abs(op.attributes.get("attackSpeed") - (base + 30)) < 0.01


def test_physical_skill_damage_type():
    sim, b = _battle()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = 3, 4
    enemy.pos_x, enemy.pos_y = 4.0, 3.0
    enemy.state = EnemyState.COMBAT
    sc = op.skill_controller
    atk0 = op.attributes.get("atk")
    cost0 = b.cost
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    # instant cost gain + multiplicative atk buff (vanguard charge skill)
    assert abs((b.cost - cost0) - 11.0) < 0.01, b.cost - cost0
    assert abs(op.attributes.get("atk") / atk0 - 1.2) < 0.01
    b._operator_attack(op, enemy, 2.0)
    pa = op._pending_attack
    assert pa is not None, "attack windup should start"
    b._resolve_operator_attack(op, pa)
    evs = [e for e in b.events.snapshot_events() if e["type"] == "damage"]
    assert evs, "no damage events"
    # scave is a vanguard (physical)
    assert evs[-1]["data"]["type"] == DamageType.PHYSICAL, evs[-1]


def test_manual_skill_needs_activation():
    sim, b = _battle()
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    sc = op.skill_controller
    # MANUAL skill must not auto-cast even with full SP
    op.sp = sc.skills[1].sp_cost
    for _ in range(120):
        b.tick_once()
    assert sc.active is None, "manual skill auto-cast unexpectedly"


def test_skill_prefab_buff_applied():
    from ark_emulator.operator_skills import _operator_prefab_buffs
    buffs = _operator_prefab_buffs("skchr_mberry_1")
    keys = [b[2].get("buffKey") for b in buffs]
    assert "mberry_s_1" in keys, keys
    sim, b = _battle()
    b.deploy("char_473_mberry", 2, 3)   # ranged -> highland
    op = b.operators[0]
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    for _ in range(10):
        b.tick_once()
    keys = [x["key"] for x in op.buffs]
    assert "mberry_s_1[disable_trait]" in keys, keys


def test_ally_prefixed_stat_buffs():
    sim, b = _battle()
    b.deploy("char_325_bison", 3, 3)       # ??: [self]/[ally] def buffs
    op = b.operators[0]
    b.deploy("char_149_scave", 3, 5)
    ally = b.operators[1]
    sc = op.skill_controller
    idx = [i for i, s_ in enumerate(sc.skills) if "bison_2" in s_.skill_id]
    assert idx
    op.sp = sc.skills[idx[0]].sp_cost
    ok, _ = sc.activate(idx[0])
    assert ok
    for _ in range(10):
        b.tick_once()
    self_buff = [x for x in op.buffs if x["key"] == "op_skill_def"]
    ally_buff = [x for x in ally.buffs if x["key"] == "op_skill_ally_def"]
    assert self_buff and abs(self_buff[0]["mul"] - 0.5) < 0.01
    assert ally_buff and abs(ally_buff[0]["mul"] - 0.15) < 0.01


def test_prefab_owner_buff_on_deploy():
    """Gravel S1 prefab owner buff (gravel_s_1 / def_atten) applies on deploy."""
    sim, b = _battle()
    b.deploy("char_237_gravel", 3, 3)
    op = b.operators[0]
    keys = [x.get("key") for x in op.buffs]
    tpls = [x.get("template_key") for x in op.buffs]
    assert "gravel_s_1" in keys, keys
    assert "def_atten" in tpls, tpls


def test_prefab_target_buff_does_not_self_stun():
    """Texas S2 target stun rides the sword-rain projectile: it lands on
    hit (after cast windup + flight), not at cast, and never hits the caster."""
    from ark_emulator.consts import EnemyState
    sim, b = _battle()
    b.deploy("char_102_texas", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col + 1
    enemy.state = EnemyState.COMBAT
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    assert not enemy.flag(0), "stun must wait for the projectile hit"
    for _ in range(40):
        b.tick_once()
        if enemy.flag(0):
            break
    assert enemy.flag(0), "enemy should be stunned after projectile lands"
    assert not op.flag(0), "operator must not be stunned by own skill"


def test_phased_periodic_sword_rain():
    """Alter Texas S3 phases: appear burst on deploy (2 hits x all
    enemies) + periodic sword rain every 1s (texas2_s_3[sword].interval,
    max 2 targets, 70% atk)."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01", squad=[
        {"charId": "char_1028_texas2", "level": 50, "phase": 2,
         "skillIndex": 2}])
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(100.0)
    for i, rc in enumerate([(3, 4), (3, 5), (4, 4)]):
        b.spawn_enemy("enemy_1000_gopro", i)
        e = b.enemies[i]
        e.row, e.col = rc
        e.state = EnemyState.COMBAT
        e.max_hp = 100000.0
        e.hp = 100000.0
    b.deploy("char_1028_texas2", 3, 3)
    key = "projectile_chr_texas2_s3_sword_rain"
    launches = lambda: [ev for ev in b.events.snapshot_events()
                        if ev["type"] == "attack"
                        and ev["data"].get("type") == "projectile_launch"
                        and ev["data"].get("projectile") == key]
    burst = launches()
    assert len(burst) == 6, len(burst)      # 3 enemies x 2 hits (appear)
    for _ in range(95):
        b.tick_once()
    total = len(launches())
    # 6 burst + 4 per 1s phase at t=30/60/90 (2 targets x 2 hits)
    assert total >= 14, total
    # periodic cadence: at least two further phase volleys after the burst
    ts = [ev["tick"] for ev in launches()]
    gaps = [ts[i+1] - ts[i] for i in range(len(ts)-1)]
    near30 = [g for g in gaps if abs(g - 30) <= 2]
    assert len(near30) >= 2, gaps     # phase fires every 30 ticks


def test_composite_ability_projectile_resolution():
    """Alter Texas S3's projectile rides a CompositeAbility sub-ability
    (EmitSword reachable via _extraAbilities), resolved through the
    component pathID graph, not just the top-level prefab."""
    from ark_emulator.operator_skills import _operator_prefab_params
    p = _operator_prefab_params("skchr_texas2_3")
    assert p.get("_projectileKey") == \
        "projectile_chr_texas2_s3_sword_rain", p
    assert p.get("_damageType") == 2, p          # MAGICAL (game enum)
    # end-to-end: S3 is deploy-triggered (spType 8); equipping it and
    # deploying spawns the resolved sword-rain projectile
    from ark_emulator import Simulator
    sim = Simulator(level_id="level_main_01-01", squad=[
        {"charId": "char_1028_texas2", "level": 50, "phase": 2,
         "skillIndex": 2}])
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(100.0)
    from ark_emulator.consts import EnemyState
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.row, e.col = 3, 4
    e.state = EnemyState.COMBAT
    b.deploy("char_1028_texas2", 3, 3)
    assert any(p_.key == "projectile_chr_texas2_s3_sword_rain"
               for p_ in b.projectiles), \
        [p_.key for p_ in b.projectiles]


def test_texas_s2_sword_rain_projectile():
    """Texas S2 spawns two delayed sword-rain projectiles (prefab
    _additionalTimes=1, _preDelay=0.5s) that deal MAGICAL damage on hit."""
    from ark_emulator.consts import EnemyState, DamageType
    sim, b = _battle()
    b.deploy("char_102_texas", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col + 1
    enemy.state = EnemyState.COMBAT
    atk = op.attributes.get("atk")
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    hp0 = enemy.hp
    ok, _ = sc.activate(1)
    assert ok
    # two projectiles, still in cast windup (0.5s = 15 ticks), no damage yet
    assert len(b.projectiles) == 2, len(b.projectiles)
    assert all(p.key == "projectile_sword_rain" for p in b.projectiles)
    assert all(p.delay_ticks == 15 for p in b.projectiles)
    assert abs(enemy.hp - hp0) < 0.01, "damage must wait for the projectile hit"
    for _ in range(90):
        b.tick_once()
        if not b.projectiles:
            break
    assert not b.projectiles, "projectiles should have landed"
    hits = [e for e in b.events.snapshot_events()
            if e["type"] == "damage" and e["data"]["source"] == op.inst_id
            and e["data"]["target"] == enemy.inst_id]
    sword = [h for h in hits if h["data"]["type"] == DamageType.MAGICAL]
    assert len(sword) == 2, len(sword)
    # two hits of atk * 1.05 vs gobo 20% magic resistance
    expected = 2.0 * atk * 1.05 * 0.8
    total = sum(h["data"]["amount"] for h in sword)
    assert abs(total - expected) < 0.01, (total, expected)
    assert enemy.hp < hp0, "enemy should have taken damage"


def test_gravel_def_atten_decays_exactly():
    """Gravel S1 def +200% decays linearly to 0 over the 6s duration."""
    sim, b = _battle()
    b.deploy("char_237_gravel", 3, 3)
    op = b.operators[0]
    # effective DEF includes the permanent E2 talent (+6%, cond.cost met)
    raw = op.attributes.base["def"]
    talent_mul = 1.0
    for m in op.attributes._mods.get("def", []):
        if m[0] == "mul" and str(m[2] or "").startswith("talent:"):
            talent_mul *= (1.0 + m[1])
    base = raw * talent_mul
    vals = []
    for _ in range(7):
        vals.append(op.attributes.get("def"))
        for _ in range(30):
            b.tick_once()
    assert abs(vals[0] - base * 3.0) < 1.0, vals[0]   # +200% at cast
    assert abs(vals[3] - base * 2.0) < 1.0, vals[3]   # +100% at 3s
    assert abs(vals[6] - base) < 0.5, vals[6]         # base at 6s


def test_amiya_s3_no_immediate_withdraw():
    """Amiya S3 suicide buff is end-of-skill: no withdraw at cast."""
    sim, b = _battle()
    b.deploy("char_002_amiya", 2, 3)   # ranged -> highland
    op = b.operators[0]
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok and sc.active is not None
    assert not op.retreating and op.hp > 0
    keys = [x.get("key") for x in op.buffs]
    assert "amiya_s_3" in keys, keys


def test_mberry_heal_buff_goes_to_allies():
    """ep_heal_all (heal-type target buff) applies to allies, not enemies."""
    sim, b = _battle()
    b.deploy("char_473_mberry", 2, 3)   # ranged -> highland
    op = b.operators[0]
    b.deploy("char_149_scave", 3, 5)
    ally = b.operators[1]
    b.spawn_enemy("enemy_1000_gopro", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = 3, 6
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    ally_keys = [x.get("key") for x in ally.buffs]
    enemy_keys = [x.get("key") for x in enemy.buffs]
    assert "mberry_s_1" in ally_keys, ally_keys
    assert "mberry_s_1" not in enemy_keys, enemy_keys


def test_charge_cost_target_buff_skipped():
    """Non-abnormal non-heal target buffs (charge_cost) are not misapplied."""
    from ark_emulator.consts import EnemyState
    sim, b = _battle()
    b.deploy("char_102_texas", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col + 1
    enemy.state = EnemyState.COMBAT
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    assert not any(x.get("key") == "charge_cost" for x in op.buffs)
    assert not any(x.get("key") == "charge_cost" for x in enemy.buffs)


def test_prefab_damage_type_overrides_heuristic():
    """Texas S2 sword rain is MAGICAL per its prefab _damageType."""
    from ark_emulator.consts import DamageType
    import ark_emulator.operator_skills as OS
    OS._operator_prefab_params("x")
    OS._PREFAB_STORE._op_prefabs = None
    from ark_emulator.operator_skills import _operator_prefab_params
    p = _operator_prefab_params("skchr_texas_2")
    assert p.get("_damageType") == 2, p
    sim, b = _battle()
    b.deploy("char_102_texas", 3, 3)
    op = b.operators[0]
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    assert sc.active._resolve_dmg_type() == DamageType.MAGICAL


def test_cast_end_buff_applies_on_expire(monkeypatch):
    """BuffAbility runActionOnEvent=3 (cast end): target debuff applies when
    the skill finishes, not at cast."""
    from ark_emulator.consts import EnemyState
    from ark_emulator.loader import DataStore
    import ark_emulator.operator_skills as _os_mod
    fake_comp = {
        "class": "BuffAbility",
        "_runActionOnEvent": 3,
        "_buffs": [{"buffKey": "stun", "templateKey": "empty",
                    "attributes": {"abnormalFlags": [0]},
                    "durationKey": "stun"}],
    }
    monkeypatch.setattr(
        _os_mod, "_operator_prefab_buffs",
        lambda sid: [("BuffAbility", "_buffs",
                      fake_comp["_buffs"][0], fake_comp)])
    sim, b = _battle()
    b.deploy("char_102_texas", 3, 3)
    op = b.operators[0]
    fake = {"skillId": "fake_cast_end", "levels": [{
        "name": "f", "skillType": 1,
        "spData": {"spType": 1, "spCost": 10, "initSp": 10,
                   "increment": 1.0, "maxChargeTime": 1},
        "duration": 1.0, "blackboard": []}]}
    from ark_emulator.operator_skills import OperatorSkillController
    op.skill_controller = OperatorSkillController(op, b, [fake])
    sc = op.skill_controller
    b.spawn_enemy("enemy_1000_gopro", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col + 1
    enemy.state = EnemyState.COMBAT
    op.sp = 10.0
    ok, _ = sc.activate(0)
    assert ok
    assert not enemy.flag(0), "cast-end buff must not apply at cast"
    # skill duration 1s (30 ticks) starts at cast even during the deploy
    # animation; the cast-end stun (30 ticks) must be visible shortly after
    for _ in range(45):
        b.tick_once()
    assert sc.active is None
    assert enemy.flag(0), "cast-end buff should apply on skill finish"


def test_silverash_s3_zhen_yin_zhan():
    """Silverash S3 zhen-yin-zhan: +110% ATK, -70% DEF, and basic attacks
    hit up to attack@max_target (3) in-range enemies while active."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_172_svrash", 3, 3)
    op = b.operators[-1]
    sc = op.skill_controller
    atk0 = float(op.attributes.get("atk"))
    def0 = float(op.attributes.get("def"))
    # two enemies in melee range, two out of range
    for dc in (1, 2, 3, 4):
        b.spawn_enemy("enemy_1000_gopro", 0, overrides={
            "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
            "row": 3, "col": 3 + dc})
        b.enemies[-1].state = EnemyState.COMBAT
    s3 = sc.skills[2]
    op.sp = s3.sp_cost
    ok, _ = sc.activate(2)
    assert ok
    assert abs(op.attributes.get("atk") - atk0 * 2.1) < 0.5
    assert abs(op.attributes.get("def") - def0 * 0.3) < 0.5
    b._operator_attack(op, b.enemies[0], op.attributes.attack_interval())
    pa = op._pending_attack
    tg = pa.get("targets") or [pa.get("target")]
    ids = [getattr(t, "inst_id", None) for t in tg if t is not None]
    assert len(ids) == 2, ids          # two in-range enemies only
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("source") == op.inst_id]
    assert len(dmg) == 2, dmg
    for d in dmg:
        assert abs(d["data"]["amount"] - atk0 * 2.1) < 0.5, d



def test_chen_s3_zhen_ying_ten_hits():
    """Chen S3 zhen-ying: on activation the next attack lands 10 hits of
    atk x 2.0 (a burst, not a plain-attack replacement)."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_010_chen", 3, 3)
    op = b.operators[-1]
    sc = op.skill_controller
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("target") == e.inst_id]
    per = op.attributes.get("atk") * 2.0
    assert len(dmg) == 11, len(dmg)      # 10 combo hits + the plain attack
    assert all(abs(d["data"]["amount"] - per) < 0.5 for d in dmg[:10])


def test_exusiai_s3_overload_five_shot_combo():
    """Exusiai S3 overload: the basic attack is replaced by 5 hits of
    atk x 1.0 (attack@times / attack@atk_scale switch attack)."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_103_angel", 2, 3)
    op = b.operators[-1]
    sc = op.skill_controller
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0},
        "row": 2, "col": 5})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("target") == e.inst_id]
    per = op.attributes.get("atk")
    assert len(dmg) == 5, len(dmg)       # plain hit replaced by the combo
    assert all(abs(d["data"]["amount"] - per) < 0.5 for d in dmg)



def test_amgoat_s3_volcano():
    """Eyjafjalla S3 volcano: +55% ATK, attack interval -1.1s, and the
    basic attack hits up to attack@max_target (3) in-range enemies."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_180_amgoat", 2, 3)
    op = b.operators[-1]
    sc = op.skill_controller
    atk0 = float(op.attributes.get("atk"))
    int0 = op.attributes.attack_interval()
    for pos in ((2, 4), (2, 5), (3, 4)):
        b.spawn_enemy("enemy_1000_gopro", 0, overrides={
            "attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0},
            "row": pos[0], "col": pos[1]})
        b.enemies[-1].state = EnemyState.COMBAT
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    assert abs(op.attributes.get("atk") - atk0 * 1.55) < 0.5
    assert abs(op.attributes.attack_interval() - max(0.05, int0 - 1.1)) \
        < 0.01
    b._operator_attack(op, b.enemies[0], op.attributes.attack_interval())
    pa = op._pending_attack
    tg = pa.get("targets") or [pa.get("target")]
    ids = [getattr(t, "inst_id", None) for t in tg if t is not None]
    assert len(ids) == 3, ids


def test_saria_s2_heal_scale():
    """Saria S2 drug-configuration heals the lowest-HP ally for
    heal_scale (0.8) x ATK."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_202_demkni", 3, 3)
    b.deploy("char_127_estell", 3, 4)
    saria = b.operators[0]
    est = b.operators[1]
    est.hp = est.max_hp * 0.5
    hp0 = float(est.hp)
    sc = saria.skill_controller
    s2 = sc.skills[1]
    saria.sp = s2.sp_cost
    ok, _ = sc.activate(1)
    assert ok
    expect = saria.attributes.get("atk") * 0.8
    assert abs(est.hp - hp0 - expect) < 0.5, (est.hp - hp0, expect)



def test_amgoat_s1_double_chant_stats():
    """Eyjafjalla S1 double-chant: phase-prefixed blackboard keys
    (amgoat_s_1[a|b].attack_speed / .atk) grant +30 attack speed and
    +30% ATK during the skill window."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_180_amgoat", 2, 3)
    op = b.operators[-1]
    sc = op.skill_controller
    atk0 = float(op.attributes.get("atk"))
    int0 = op.attributes.attack_interval()
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    assert abs(op.attributes.get("atk") - atk0 * 1.3) < 0.5
    assert abs(op.attributes.get("attackSpeed") - 130.0) < 1e-9
    assert abs(op.attributes.attack_interval() - int0 * 100.0 / 130.0) \
        < 0.01


def test_silverash_s1_strong_strike():
    """Silverash S1 strong-strike: activation lands a burst of
    atk x atk_scale (1.9) on the in-range enemy."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_172_svrash", 3, 3)
    op = b.operators[-1]
    sc = op.skill_controller
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    atk0 = float(op.attributes.get("atk"))
    op.sp = sc.skills[0].sp_cost
    b.events.log = []
    ok, _ = sc.activate(0)
    assert ok
    for _ in range(40):
        b.tick_once()
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("target") == e.inst_id]
    assert any(abs(d["data"]["amount"] - atk0 * 1.9) < 0.5 for d in dmg), \
        dmg



def _deploy_ranged(b, cid):
    for r in range(b.map.rows):
        for c in range(b.map.cols):
            if b.map.buildable(r, c, 2) is not False:
                ok, res = b.deploy(cid, r, c)
                if ok:
                    return b.operators[-1]
    return None


def _spawn_def(b, row, col, **kw):
    over = {"attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0,
                           "magicResistance": 0.0}, "row": row, "col": col}
    over["attributes"].update(kw)
    b.spawn_enemy("enemy_1000_gopro", 0, overrides=over)
    e = b.enemies[-1]
    from ark_emulator.consts import EnemyState
    e.state = EnemyState.COMBAT
    return e


def _ranged_damage(b, op, e, ticks=120):
    b.events.log = []
    b._operator_attack(op, e, op.attributes.attack_interval())
    first = None
    for _ in range(ticks):
        b.tick_once()
        if first is None:
            for x in b.events.snapshot_events():
                if x["type"] == "damage" and \
                        x["data"].get("target") == e.inst_id:
                    first = x
                    break
        if first is not None:
            break
    return [first] if first else []


def test_executor_def_penetrate_on_projectile():
    """Executor (send-ren) fixed def penetration must apply to ranged
    projectile hits exactly once (and not double-count)."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    op = _deploy_ranged(b, "char_279_excu")
    assert op is not None
    e = _spawn_def(b, op.row, op.col + 2, **{"def": 200.0})
    atk = float(op.attributes.get("atk"))
    pen = float(op.attributes.get("defPenetrateFixed") or 0.0)
    # executor is reaperrange: front-row enemies take 150%
    expect = atk * 1.5 - max(0.0, 200.0 - pen)
    dmg = _ranged_damage(b, op, e)
    assert len(dmg) == 1, dmg
    assert abs(dmg[0]["data"]["amount"] - expect) < 0.5, dmg


def test_pith_magic_resist_penetrate():
    """Pith fixed magic-resist penetration reduces the target mres before
    the damage formula."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    op = _deploy_ranged(b, "char_509_acast")
    assert op is not None
    e = _spawn_def(b, op.row, op.col + 2, **{"magicResistance": 50.0})
    atk = float(op.attributes.get("atk"))
    pen = float(op.attributes.get("magicResistPenetrateFixed") or 0.0)
    expect = atk * max(0.0, 1.0 - max(0.0, 50.0 - pen) / 100.0)
    dmg = _ranged_damage(b, op, e)
    assert len(dmg) == 1, dmg
    assert abs(dmg[0]["data"]["amount"] - expect) < 0.5, dmg



def test_laios_percent_def_penetrate():
    """Laios percent def penetration (0.4) reduces the target def before
    the physical damage formula."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    ok = False
    for r in range(b.map.rows):
        for c in range(b.map.cols):
            if b.map.buildable(r, c, 1) is not False:
                ok, res = b.deploy("char_4142_laios", r, c)
                if ok:
                    break
        if ok:
            break
    op = b.operators[-1]
    e = _spawn_def(b, op.row, op.col + 1, **{"def": 200.0})
    atk = float(op.attributes.get("atk"))
    pr = float(op.attributes.get("defPenetrate") or 0.0)
    expect = atk - max(0.0, 200.0 * (1 - pr))
    b.events.log = []
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("target") == e.inst_id]
    assert len(dmg) == 1, dmg
    assert abs(dmg[0]["data"]["amount"] - expect) < 0.5, dmg


def test_penetrate_and_fragility_multiply():
    """Percent def penetration and physical fragility compose: damage =
    (atk - def*(1-pen)) x fragility_scale."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    ok = False
    for r in range(b.map.rows):
        for c in range(b.map.cols):
            if b.map.buildable(r, c, 1) is not False:
                ok, res = b.deploy("char_4142_laios", r, c)
                if ok:
                    break
        if ok:
            break
    op = b.operators[-1]
    e = _spawn_def(b, op.row, op.col + 1, **{"def": 200.0})
    b.add_buff(e, {"key": "weak[phy]", "remaining_ticks": 1000,
                   "layers": 1,
                   "blackboard": {"damage_scale": 1.25}})
    atk = float(op.attributes.get("atk"))
    pr = float(op.attributes.get("defPenetrate") or 0.0)
    expect = (atk - max(0.0, 200.0 * (1 - pr))) * 1.25
    b.events.log = []
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and
           x["data"].get("target") == e.inst_id]
    assert len(dmg) == 1, dmg
    assert abs(dmg[0]["data"]["amount"] - expect) < 0.5, dmg
