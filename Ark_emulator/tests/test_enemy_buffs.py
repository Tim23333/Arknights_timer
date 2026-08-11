# -*- coding: utf-8 -*-
"""Enemy skill prefab buff -> buff_table/BuffSystem integration tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.buff_templates import (buff_definition, named_buff,
                                         materialise_buff)
from ark_emulator import Simulator
from ark_emulator.consts import EnemyState, AbnormalFlag, DamageType


def test_buff_table_loading():
    stun = named_buff(buff_definition("stun"))
    assert stun["buffKey"] == "stun"
    assert stun["attributes"]["abnormalFlags"] == [0]
    assert stun["durationKey"] == "stun"
    assert stun["maxStackCnt"] == 1

    sluggish = named_buff(buff_definition("sluggish"))
    mods = sluggish["attributes"]["attributeModifiers"]
    assert mods and mods[0]["attributeType"] == 6  # MOVE_SPEED
    assert mods[0]["formulaItem"] == 3             # FINAL_SCALER


def test_materialise_stun_buff():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    data = dict(named_buff(buff_definition("stun")))
    entry = materialise_buff(b, op, data, {"stun": 5.0}, None)
    assert op.flag(AbnormalFlag.STUNNED)
    # duration from blackboard key "stun" = 5s -> 150 ticks
    assert 145 <= entry["remaining_ticks"] <= 155, entry["remaining_ticks"]


def test_materialise_sluggish_modifier():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    data = dict(named_buff(buff_definition("sluggish")))
    entry = materialise_buff(b, op, data, {"sluggish": 3.0}, None)
    # moveSpeed final scaler -0.8 -> 20% speed
    speed = op.attributes.get("moveSpeed")
    assert abs(speed - 0.2) < 0.01, speed


def test_enemy_skill_stun_end_to_end():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_10047_shrknt", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col
    enemy.pos_x, enemy.pos_y = float(op.col), float(op.row)
    enemy.state = EnemyState.COMBAT
    sc = enemy.skill_controller
    chosen = None
    for s in sc.skills:
        if s.prefab_buffs:
            chosen = (s, op)
            break
    assert chosen is not None
    sc._start_cast(chosen)
    # M0SplashCannon: damage/stun lands at the spine hit frame (5.0s)
    for _ in range(220):
        sc.update(1 / 30)
        b.tick_once()
    assert op.flag(AbnormalFlag.STUNNED), op.abnormal


def test_enemy_skill_self_buff_applies_to_enemy():
    """BuffToOwnerDuringAbility prefab buffs go on the caster, not the target."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_10003_trwlpl", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col
    enemy.pos_x, enemy.pos_y = float(op.col), float(op.row)
    enemy.state = EnemyState.COMBAT
    sc = enemy.skill_controller
    assert sc is not None
    s = None
    for sk in sc.skills:
        win = [sb for sb in sk.self_buffs if sb.get("remove_on_end")]
        if win:
            s = sk
            break
    assert s is not None, "no skill with window self buffs"
    keys = [sb["data"].get("buffKey")
            for sb in s.self_buffs if sb.get("remove_on_end")]
    assert keys
    sc._start_cast((s, op))
    # wait=1 abilities apply their window self buffs at the first calibrated
    # OnAttack frame (spell_on), not at cast start
    guard = 0
    while guard < 300:
        sc.update(1 / 30)
        b.tick_once()
        guard += 1
        if all(b.buffs.get(enemy, k) is not None for k in keys):
            break
    for k in keys:
        assert b.buffs.get(enemy, k) is not None, \
            f"self buff {k} not applied to enemy"
        assert b.buffs.get(op, k) is None, f"self buff {k} wrongly on operator"
    # window buffs are removed when the cast ends
    guard = 0
    while sc.casting is not None and guard < 300:
        sc.update(1 / 30)
        b.tick_once()
        guard += 1
    for k in keys:
        assert b.buffs.get(enemy, k) is None, \
            f"window self buff {k} not removed at cast end"


def test_aura_applies_and_removes():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    b.spawn_enemy("enemy_10077_mpbarr", 0)
    aura_enemy = b.enemies[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    friend = b.enemies[1]
    friend.row, friend.col = aura_enemy.row + 1, aura_enemy.col
    friend.pos_x, friend.pos_y = float(friend.col), float(friend.row)
    friend.attributes.base["moveSpeed"] = 0.0
    assert aura_enemy.auras, "mpbarr should carry an aura"
    for _ in range(60):
        b.tick_once()
    assert any(x["key"] == "enemy_mpprme_spawn_mark"
               for x in friend.buffs), friend.buffs
    # leave range -> remove_when_leave clears the buff
    friend.row, friend.col = aura_enemy.row + 5, aura_enemy.col
    friend.pos_x, friend.pos_y = float(friend.col), float(friend.row)
    for _ in range(35):
        b.tick_once()
    assert not any(x["key"] == "enemy_mpprme_spawn_mark"
                   for x in friend.buffs), friend.buffs


def test_string_enum_normalisation():
    """buff attributeType/formulaItem may be enum-name strings ('ATK',
    'MULTIPLIER'); the emulator must normalise them."""
    from ark_emulator.buff_templates import _attr_type_int, _formula_int
    assert _attr_type_int("ATK") == 1
    assert _attr_type_int("MAX_HP") == 0
    assert _formula_int("MULTIPLIER") == 1
    assert _formula_int("FINAL_SCALER") == 3
    # end-to-end: a CreateBuff node with string enums must not crash
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    node = {"$type": "Torappu.Battle.Action.Nodes+CreateBuff, Assembly-CSharp",
            "_buffOwner": "BUFF_OWNER",
            "_buff": {"buffKey": "t_str_enum", "lifeTime": 5.0,
                      "maxStackCnt": 1,
                      "attributes": {"attributeModifiers": [
                          {"attributeType": "ATK",
                           "formulaItem": "MULTIPLIER", "value": 0.2}]}}}
    eng.run_actions(op, [node], {"owner": op, "source": op, "target": op,
                                 "damage": None, "bb": {}}, 0)
    atk0 = op.attributes.get("atk") / 1.2
    assert abs(op.attributes.get("atk") - atk0 * 1.2) < 0.01


def test_enemy_decaying_attribute_buff():
    """Shared buff engine: RemainingRatioToAttributeModifier decays on
    enemy units too (def_atten template)."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    b.spawn_enemy("enemy_1000_gopro", 0,
                  overrides={"attributes": {"def": 200.0}})
    enemy = b.enemies[0]
    base = enemy.attributes.base["def"]
    assert base == 200.0, base
    data = {"buffKey": "test_def_atten", "templateKey": "def_atten",
            "attributes": {"attributeModifiers": []},
            "waitFirstTriggerInterval": 0}
    entry = materialise_buff(b, enemy, data, {"def": 2.0, "duration": 3.0},
                             source=None)
    b.add_buff(enemy, entry)
    vals = [enemy.attributes.get("def")]
    for _ in range(3):
        for _ in range(30):
            b.tick_once()
        vals.append(enemy.attributes.get("def"))
    # +200% -> decay to base over 3s (1s granularity triggers)
    assert abs(vals[0] - base * 3.0) < 1.0, vals[0]
    assert abs(vals[-1] - base) < 1.0, vals[-1]
    assert vals[1] > vals[2] > vals[3], vals


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
    print("all enemy buff tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)


def test_behavior_buffkeys_self_buff_applied():
    """Behavior-catalog buffKeys attach self-oriented buffs to the caster
    (Shine -> enemy_trtrsl_s), which the shared prefab components omit."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_10002_trtrsl", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col
    enemy.pos_x, enemy.pos_y = float(op.col), float(op.row)
    enemy.state = EnemyState.COMBAT
    sc = enemy.skill_controller
    sh = next(s for s in sc.skills if s.prefab_key == "Shine")
    assert any(sb["data"].get("buffKey") == "enemy_trtrsl_s"
               for sb in sh.self_buffs), sh.self_buffs
    sc._start_cast((sh, op))
    guard = 0
    while guard < 120:
        b.tick_once()
        guard += 1
        if b.buffs.get(enemy, "enemy_trtrsl_s") is not None:
            break
    assert b.buffs.get(enemy, "enemy_trtrsl_s") is not None, enemy.buffs


def test_behavior_buffkeys_skips_target_debuffs():
    """Target-debuff buffKeys (ArcticBlast -> arctic_blast) are NOT attached
    to the caster; they reach the target through the skill effects."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_127_estell", 3, 4)
    op = b.operators[0]
    b.spawn_enemy("enemy_1505_frstar", 0, overrides={
        "attributes": {"atk": 100.0}, "row": 3, "col": 6})
    enemy = b.enemies[0]
    enemy.state = EnemyState.COMBAT
    sc = enemy.skill_controller
    ab = next(s for s in sc.skills if s.prefab_key == "ArcticBlast")
    keys = [sb["data"].get("buffKey") for sb in ab.self_buffs]
    assert "arctic_blast" not in keys, keys
    sc._start_cast((ab, op))
    for _ in range(150):
        b.tick_once()
    assert b.buffs.get(enemy, "arctic_blast") is None


def test_behavior_self_buff_not_duplicated_to_target():
    """A caster's own buff (enemy_trwlpl_s) is applied to the enemy and is
    NOT also cast onto the operator as a target buff."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_10003_trwlpl", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = op.row, op.col
    enemy.pos_x, enemy.pos_y = float(op.col), float(op.row)
    enemy.state = EnemyState.COMBAT
    sc = enemy.skill_controller
    eat = next(s for s in sc.skills if s.prefab_key == "Eat")
    assert "enemy_trwlpl_s" in [x["data"].get("buffKey")
                                for x in eat.self_buffs]
    assert "enemy_trwlpl_s" not in [x.get("buffKey")
                                    for x in eat.prefab_buffs]
    sc._start_cast((eat, op))
    guard = 0
    while guard < 300:
        b.tick_once()
        guard += 1
        if b.buffs.get(enemy, "enemy_trwlpl_s") is not None:
            break
    assert b.buffs.get(enemy, "enemy_trwlpl_s") is not None
    assert b.buffs.get(op, "enemy_trwlpl_s") is None


def test_enemy_heal_via_max_hp_ratio():
    """Enemy heal buffs heal the caster by hp_ratio x maxHp on buff start
    (Heallarva hp_ratio 0.02; HealViaMaxHpRatio reads hp_ratio)."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1268_nhnrs", 0)
    enemy = b.enemies[0]
    enemy.row, enemy.col = 3, 4
    enemy.pos_x, enemy.pos_y = 4.0, 3.0
    enemy.state = EnemyState.COMBAT
    b.apply_damage(enemy, enemy.max_hp * 0.5, DamageType.TRUE, source=None)
    hp0 = enemy.hp
    sc = enemy.skill_controller
    hl = next(s for s in sc.skills if s.prefab_key == "Heallarva")
    assert hl.blackboard.get("hp_ratio") == 0.02
    assert any(sb["data"].get("buffKey") == "enemy_nhnrs_t[healtrap]"
               for sb in hl.self_buffs)
    sc._start_cast((hl, None))
    for _ in range(90):
        b.tick_once()
    assert abs((enemy.hp - hp0) - enemy.max_hp * 0.02) < 0.01, \
        (hp0, enemy.hp, enemy.max_hp * 0.02)


def test_enemy_healer_heals_allies_in_range():
    """RangeHeal (hlsprt) heals up to max_target allied enemies within
    range_radius by atk x heal_scale; out-of-range allies and operators
    are untouched."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_10089_hlsprt", 0)
    healer = b.enemies[0]
    healer.row, healer.col = 3, 3
    healer.pos_x, healer.pos_y = 3.0, 3.0
    healer.state = EnemyState.COMBAT
    b.spawn_enemy("enemy_1000_gopro", 0)
    near = b.enemies[1]
    near.row, near.col = 3, 4
    near.pos_x, near.pos_y = 4.0, 3.0
    near.state = EnemyState.MOVE
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    far = b.enemies[2]
    far.row, far.col = 3, 7
    far.pos_x, far.pos_y = 7.0, 3.0
    far.state = EnemyState.MOVE
    for u in (near, far):
        b.apply_damage(u, u.max_hp * 0.5, DamageType.TRUE, source=None)
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 4, 4)
    op = b.operators[0]
    b.apply_damage(op, op.max_hp * 0.5, DamageType.TRUE, source=None)
    n0, f0, o0 = near.hp, far.hp, op.hp
    sc = healer.skill_controller
    rh = next(s for s in sc.skills if s.prefab_key == "RangeHeal")
    sc._start_cast((rh, None))
    for _ in range(200):
        b.tick_once()
        if sc.casting is None:
            break
    assert near.hp == near.max_hp, (n0, near.hp)      # healed to full
    assert abs(far.hp - f0) < 0.01, (f0, far.hp)      # out of range
    assert abs(op.hp - o0) < 0.01, (o0, op.hp)        # operators untouched


def test_on_owner_killed_buff_fires_on_death():
    """Death-triggered buff templates fire ON_OWNER_KILLED (die_to_add_cost
    -> +5 deployment cost when the enemy dies)."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1000.0
    b.cost = 10.0
    b.cost_increase_time = 1e7
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    bd = {"buffKey": "die_to_add_cost", "templateKey": "die_to_add_cost",
          "attributes": {}, "maxStackCnt": 1, "lifeTimeType": 0,
          "lifeTime": 0.0}
    entry = materialise_buff(b, e, bd, {"cost": 5.0}, None)
    b.add_buff(e, entry)
    b.apply_damage(e, e.max_hp + 1.0, DamageType.TRUE, source=None)
    assert e.dead
    assert abs(b.cost - 15.0) < 1e-6, b.cost


def test_death_spawn_skips_falldown():
    """Death-spawn buffs (enemy_dcolle_bonore[action]) summon on normal
    kills but not when the owner dies by FALLDOWN (hole)."""
    bd = {"buffKey": "enemy_dcolle_bonore[action]",
          "templateKey": "enemy_dcolle_bonore[action]",
          "attributes": {}, "maxStackCnt": 1, "lifeTimeType": 0,
          "lifeTime": 0.0}
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[0]
    e.state = EnemyState.COMBAT
    b.add_buff(e, materialise_buff(b, e, dict(bd), {}, None))
    n0 = len(b.enemies)
    b.apply_damage(e, e.max_hp + 1.0, DamageType.TRUE, source=None)
    assert len(b.enemies) == n0 + 1, [x.enemy_key for x in b.enemies]
    assert any(x.enemy_key == "enemy_1367_dseed" for x in b.enemies)

    sim2 = Simulator(level_id="level_main_01-01")
    sim2.run_ticks(15)
    b2 = sim2.battle
    b2.spawn_enemy("enemy_1000_gopro", 0)
    e2 = b2.enemies[0]
    e2.state = EnemyState.COMBAT
    b2.add_buff(e2, materialise_buff(b2, e2, dict(bd), {}, None))
    e2._death_reason = "FALLDOWN"
    n1 = len(b2.enemies)
    b2.apply_damage(e2, e2.max_hp + 1.0, DamageType.TRUE, source=None)
    assert len(b2.enemies) == n1, len(b2.enemies)


def test_enemy_empty_blackboard_entry_spawn():
    """enemy_10101_crgun biu carries [{}] blackboard entries - spawning
    must not raise KeyError (skills.py blackboard key guard)."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_473_mberry", 2, 3)
    b.spawn_enemy("enemy_10101_crgun", 0)
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    assert e.skill_controller is not None
    assert any(s.prefab_key == "biu" for s in e.skill_controller.skills)
    # force-cast biu without crashing
    sk = next(s for s in e.skill_controller.skills if s.prefab_key == "biu")
    e.sp = 5.0
    e.skill_controller._start_cast((sk, b.operators[0] if b.operators else None))
    for _ in range(60):
        e.skill_controller.update(1.0 / 30.0)

