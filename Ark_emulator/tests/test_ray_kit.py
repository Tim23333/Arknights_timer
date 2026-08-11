# -*- coding: utf-8 -*-
"""Ray (莱伊) hunter ammo-linkage kit tests.

Covers the hunter trait's skill-scale override (S3 attack@atk_scale),
talent 入神 same-target ATK stacks, S1 脱身矢 special bullet (no ammo,
kill -> next-reload bonus), S3 bind on hit + kill SP refund, and the
UNMOVABLE (束缚) movement lock.
"""
import os
import sys
import traceback

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


def _deploy_ray(b, row=2, col=3):
    b.deploy("char_4117_ray", row, col)
    op = b.operators[0]
    assert op.trait_system is not None and op.trait_system.is_hunter()
    return op


def _spawn(b, key, row, col, hp=50000.0, move_speed=0.0):
    b.spawn_enemy(key, 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": 0.0,
                       "massLevel": 1.0, "moveSpeed": move_speed},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _skill_index(op, tail):
    return [i for i, s in enumerate(op.skill_controller.skills)
            if tail in s.skill_id][0]


def test_ray_hunter_trait_basics():
    sim, b = _battle()
    op = _deploy_ray(b)
    tr = op.trait_system
    assert tr.hunter_ammo_max() == 8, tr.hunter_ammo_max()  # E2: 8 rounds
    assert op._hunter_ammo == 8
    assert abs(tr.hunter_atk_scale() - 1.2) < 1e-6
    assert "healFalloff" not in tr.to_dict()


def test_ray_s3_scale_override_and_bind():
    sim, b = _battle()
    op = _deploy_ray(b)
    sc = op.skill_controller
    i3 = _skill_index(op, "ray_3")
    op.sp = sc.skills[i3].sp_cost
    ok, _ = sc.activate(i3)
    assert ok
    assert op._hunter_ammo == 0, "S3 should stop attacking until reloaded"
    assert abs(op.trait_system.hunter_atk_scale() - 1.9) < 1e-6, (
        "S3 should override the hunter attack scale to attack@atk_scale")
    e = _spawn(b, "enemy_1000_gopro_2", 3, 5)
    for _ in range(240):
        b.tick_once()
        if any(x["type"] == "damage" and x["data"]["target"] == e.inst_id
               for x in b.events.snapshot_events()):
            break
    evs = b.events.snapshot_events()
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"]["target"] == e.inst_id]
    assert dmg, "S3 should fire after refilling the magazine"
    atk = op.attributes.get("atk")
    expect = atk * 1.9 * 1.08      # attack@atk_scale x 入神 1 stack
    assert abs(dmg[0]["data"]["amount"] - expect) < expect * 0.15, (
        dmg[0], expect)
    assert e.flag(13), "S3 hit should bind (束缚/UNMOVABLE) the enemy"


def test_ray_s1_special_bullet_no_ammo_and_kill_bonus():
    sim, b = _battle()
    op = _deploy_ray(b)
    sc = op.skill_controller
    i1 = _skill_index(op, "ray_1")
    e = _spawn(b, "enemy_1000_gopro_2", 2, 5, hp=1000.0)
    ammo0 = op._hunter_ammo
    op.sp = sc.skills[i1].sp_cost
    ok, _ = sc.activate(i1)
    assert ok
    evs = b.events.snapshot_events()
    dmg = [x for x in evs if x["type"] == "damage" and
           x["data"]["target"] == e.inst_id]
    assert dmg, "S1 should fire the special bullet instantly"
    atk = op.attributes.get("atk")
    expect = atk * 2.2
    assert abs(dmg[0]["data"]["amount"] - expect) < expect * 0.15, (
        dmg[0], expect)
    assert op._hunter_ammo == ammo0, "S1 special bullet must not consume ammo"
    assert e.dead and op._hunter_next_reload_bonus == 1, (
        op._hunter_next_reload_bonus)
    assert any(x["type"] == "hunter_reload_bonus"
               for x in b.events.snapshot_events())


def test_ray_focus_stacks_same_target():
    sim, b = _battle()
    op = _deploy_ray(b)
    tr = op.trait_system
    e1 = _spawn(b, "enemy_1000_gopro_2", 3, 5)
    e2 = _spawn(b, "enemy_1000_gopro_2", 3, 6)
    mults = []
    for _ in range(4):
        mults.append(tr.hunter_focus_multiplier(e1))
    assert [round(m, 6) for m in mults] == [1.08, 1.16, 1.24, 1.24], mults
    assert tr.hunter_focus_multiplier(e2) == 1.08, "switch target resets"


def test_non_ray_hunter_has_no_focus():
    sim, b = _battle()
    b.deploy("char_4104_coldst", 2, 3)       # Bingniang, hunter
    op = b.operators[0]
    e = _spawn(b, "enemy_1000_gopro_2", 3, 5)
    assert op.trait_system.hunter_focus_multiplier(e) == 1.0


def test_bind_blocks_enemy_movement():
    sim, b = _battle()
    e = _spawn(b, "enemy_1000_gopro_2", 3, 5, move_speed=1.0)
    b.add_abnormal(e, 13, 5.0)               # UNMOVABLE / 束缚
    before = (e.pos_x, e.pos_y)
    for _ in range(60):
        b.tick_once()
    assert (e.pos_x, e.pos_y) == before, "bound enemy must not move"


def test_ray_s3_kill_refunds_sp_at_end():
    sim, b = _battle()
    op = _deploy_ray(b)
    sc = op.skill_controller
    i3 = _skill_index(op, "ray_3")
    op.sp = sc.skills[i3].sp_cost
    ok, _ = sc.activate(i3)
    assert ok
    e = _spawn(b, "enemy_1000_gopro_2", 2, 5, hp=1000.0)
    for _ in range(600):
        b.tick_once()
        if op.sp >= 10.0:
            break
    # S3 kill-refund flows through the ray_s_3[sp] buff template
    # (ON_TARGET_KILLED marks, ON_BUFF_FINISH ModifySp at skill end)
    assert op.sp >= 10.0 - 1e-6 and op.sp < 11.5, op.sp



def test_ray_sandbeast_deploy_and_lifetime():
    """\u5de1\u54e8\u4f19\u4f34: sandbeast deploys in Ray's range, lasts
    the talent duration (25s at E2), then expires on its own."""
    sim, b = _battle()
    op = _deploy_ray(b)
    ok, _ = b.deploy_summon("char_4117_ray", 2, 5, owner=op)
    assert ok
    tok = b.tokens[-1]
    assert tok.token_id == "token_10034_ray_sndbst"
    assert tok.expire_tick == b.tick + 25 * 30, (tok.expire_tick, b.tick)
    for _ in range(25 * 30 + 5):
        b.tick_once()
    assert tok not in b.tokens
    assert any(x["type"] == "token_expire"
               for x in b.events.snapshot_events())


def test_ray_sandbeast_area_priority_extends_range():
    """\u6c99\u5730\u517d scouting area extends Ray's effective range and
    takes targeting priority (enemy only reachable through the area)."""
    sim, b = _battle()
    op = _deploy_ray(b)
    ok, _ = b.deploy_summon("char_4117_ray", 2, 5, owner=op)
    assert ok
    # x-4 scouting area is a real 3x3 (PRTS: "\u5468\u56f4 8 \u683c");
    # sandbeast sits at (2,5) -> area rows 1..3 cols 4..6; (1,6) is in
    # the area yet outside Ray own 3-12 range (row -1 only covers +0/+1)
    e = _spawn(b, "enemy_1000_gopro_2", 1, 6)
    for _ in range(300):
        b.tick_once()
        if any(x["type"] == "damage" and x["data"]["target"] == e.inst_id
               for x in b.events.snapshot_events()):
            break
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and x["data"]["target"] == e.inst_id]
    assert dmg, "Ray should hit enemies in the sandbeast area"
    tok = b.tokens[-1]
    assert tok._recover_bullets >= 1, "area hits should be recorded"


def test_ray_sandbeast_area_damage_bonus():
    """Enemies inside the scouted area take +15% physical damage (E2)."""
    sim, b = _battle()
    op = _deploy_ray(b)
    ok, _ = b.deploy_summon("char_4117_ray", 2, 5, owner=op)
    assert ok
    e = _spawn(b, "enemy_1000_gopro_2", 2, 6)   # in area and own range
    for _ in range(300):
        b.tick_once()
        if any(x["type"] == "damage" and x["data"]["target"] == e.inst_id
               for x in b.events.snapshot_events()):
            break
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and x["data"]["target"] == e.inst_id]
    assert dmg
    atk = op.attributes.get("atk")
    expect = atk * 1.2 * 1.08 * 1.15    # trait x \u5165\u795e 1 stack x area
    assert abs(dmg[0]["data"]["amount"] - expect) < expect * 0.15, (
        dmg[0], expect)


def test_ray_sandbeast_retreat_refunds_ammo():
    """\u5e7f\u57df\u8b66\u89c9 passive: sandbeast retreat refunds bullets
    that hit its scouted area."""
    sim, b = _battle()
    op = _deploy_ray(b)
    ok, _ = b.deploy_summon("char_4117_ray", 2, 5, owner=op)
    assert ok
    tok = b.tokens[-1]
    e = _spawn(b, "enemy_1000_gopro_2", 2, 6, hp=500000.0)
    for _ in range(360):
        b.tick_once()
    assert tok._recover_bullets >= 1, tok._recover_bullets
    ammo0 = op._hunter_ammo
    b.withdraw_token(tok.inst_id)
    evs = b.events.snapshot_events()
    rec = [x for x in evs if x["type"] == "ray_sandbeast_ammo_recover"]
    assert rec, "withdrawing the sandbeast should refund bullets"
    assert op._hunter_ammo == ammo0 + rec[-1]["data"]["amount"]
    assert rec[-1]["data"]["amount"] >= 1
    assert op._hunter_ammo <= 8


def test_ray_s2_range_expand_and_respawn_reduction():
    """\u5e7f\u57df\u8b66\u89c9: range 4-10 while active; sandbeast respawn
    time reduced (10% at level 1)."""
    sim, b = _battle()
    op = _deploy_ray(b)
    sc = op.skill_controller
    i2 = _skill_index(op, "ray_2")
    op.sp = sc.skills[i2].sp_cost
    ok, _ = sc.activate(i2)
    assert ok
    from ark_emulator.battle import range_offsets_rotated
    expect = sorted(range_offsets_rotated("4-10", 1))
    assert sorted(op.range_shape) == expect, "S2 should expand the range"
    ok2, _ = b.deploy_summon("char_4117_ray", 2, 5, owner=op)
    assert ok2
    tok = b.tokens[-1]
    assert abs(tok.respawn_time - 30.0 * 0.9) < 1e-6, tok.respawn_time


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
    print("all ray kit tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
