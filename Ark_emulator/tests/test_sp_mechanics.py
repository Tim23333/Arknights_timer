# -*- coding: utf-8 -*-
"""Precise SP mechanics tests (MECHANICS section 4.1).

Covers: 1s cooldown-slot auto recovery, pause-on-full with remainder
retention, spType bitmask (6/7 attack-or-hit), SP blocking while a skill
is active (zuhui), charging (maxSp = cost x charges), ammo skills,
deploy-triggered skills (spType=8) and the swordmaster double-attack
attack-recovery exception.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.operator_skills import OperatorSkillController
from ark_emulator.consts import DamageType


def _fake_skill(sp_type, sp_cost=10.0, init_sp=0.0, skill_type=1,
                duration=2.0, max_charge=1, duration_type=0, blackboard=None):
    return {"skillId": "fake_%s" % sp_type, "levels": [{
        "name": "fake", "skillType": skill_type,
        "spData": {"spType": sp_type, "spCost": sp_cost, "initSp": init_sp,
                   "increment": 1.0, "maxChargeTime": max_charge},
        "duration": duration, "durationType": duration_type,
        "blackboard": blackboard or [],
    }]}


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.battle_cost_add(100.0)
    return sim, b


def _deployed_op():
    sim, b = _battle()
    b.deploy("char_149_scave", 3, 3)
    # exit the 0.5s deploy-animation window so skill/SP ticking is live
    for _ in range(16):
        b.tick_once()
    return sim, b, b.operators[0]


def _swap_controller(op, battle, fake_skill):
    op.skill_controller = OperatorSkillController(op, battle, [fake_skill])
    return op.skill_controller


def test_auto_recovery_cooldown_slot():
    """Auto recovery grants exactly +1 per second (no fractional SP)."""
    sim, b, op = _deployed_op()
    sc = op.skill_controller
    # deploy pre-charge: min initSp across selectable skills (8 for scave)
    assert op.sp == 8.0, op.sp
    op.sp = 0.0
    op._sp_cooldown_remaining = 1.0
    for _ in range(29):
        b.tick_once()
    assert op.sp == 0.0, op.sp            # no fractional points
    b.tick_once()                          # exactly 1.0s elapsed
    assert op.sp == 1.0, op.sp
    for _ in range(30):
        b.tick_once()
    assert op.sp == 2.0, op.sp


def test_auto_recovery_pauses_when_full_keeps_remainder():
    sim, b, op = _deployed_op()
    # manual fake skill: no AUTO cast can consume the bar during the test
    sc = _swap_controller(op, b, _fake_skill(1, sp_cost=40))
    op.sp = op.sp_max                     # full
    op._sp_cooldown_remaining = 0.37
    for _ in range(120):
        b.tick_once()
    assert op.sp == op.sp_max
    assert abs(op._sp_cooldown_remaining - 0.37) < 1e-6   # paused, kept
    # after consuming, recovery resumes from the retained remainder
    op.sp = op.sp_max - 1.0
    b.tick_once()
    assert op.sp == op.sp_max - 1.0       # 0.37s still not elapsed
    for _ in range(12):                    # 12/30 = 0.4s > 0.37s
        b.tick_once()
    assert op.sp == op.sp_max


def test_sp_type_bitmask():
    sim, b, op = _deployed_op()
    # spType=6 = attack OR damage
    sc = _swap_controller(op, b, _fake_skill(6))
    op.sp = 0.0
    sc.recover_sp(2)
    assert op.sp == 1.0, op.sp
    op.sp = 0.0
    sc.recover_sp(4)
    assert op.sp == 1.0, op.sp
    # spType=7 = all sources
    sc = _swap_controller(op, b, _fake_skill(7))
    op.sp = 0.0
    assert sc.recover_sp(2) == 1.0
    op.sp = 0.0
    assert sc.recover_sp(4) == 1.0
    # spType=1 (auto) must NOT gain from attacks
    sc = _swap_controller(op, b, _fake_skill(1))
    op.sp = 0.0
    assert sc.recover_sp(2) == 0.0
    assert sc.recover_sp(4) == 0.0


def test_zuhui_block_while_active():
    sim, b, op = _deployed_op()
    sc = _swap_controller(op, b, _fake_skill(6, sp_cost=10, duration=2.0))
    op.sp = 10.0
    ok, _ = sc.activate(0)
    assert ok and sc.active is not None
    assert op.sp == 0.0
    assert sc.recover_sp(2) == 0.0
    assert sc.recover_sp(4) == 0.0
    for _ in range(60):                    # 2s active window
        b.tick_once()
    assert sc.active is None
    assert op.sp == 0.0                    # no recovery leaked during zuhui
    assert sc.recover_sp(4) == 1.0         # resumes after expiry


def test_charging_max_sp():
    sim, b, op = _deployed_op()
    sc = _swap_controller(op, b, _fake_skill(2, sp_cost=10, max_charge=2))
    assert op.sp_max == 20.0, op.sp_max
    op.sp = 0.0
    for _ in range(25):
        sc.recover_sp(2)
    assert op.sp == 20.0, op.sp           # capped at cost x charges
    for _ in range(60):
        b.tick_once()
    assert op.sp == 20.0                   # full -> auto recovery paused


def test_ammo_skill():
    sim, b, op = _deployed_op()
    sc = _swap_controller(op, b, _fake_skill(
        1, sp_cost=5, duration_type=1, blackboard=[{"key": "cnt", "value": 3}]))
    op.sp = 5.0
    ok, _ = sc.activate(0)
    assert ok and sc.active is not None
    assert sc.active.is_ammo and sc.active.ammo == 3
    assert sc.active.remaining > 60
    sc.on_ammo_attack()
    assert sc.active is not None and sc.active.ammo == 2
    sc.on_ammo_attack()
    assert sc.active.ammo == 1
    sc.on_ammo_attack()
    assert sc.active is None               # ended when ammo hit 0


def test_deploy_skill_fires_on_deploy_no_sp():
    sim, b, op = _deployed_op()
    sc = _swap_controller(op, b, _fake_skill(
        8, duration=5.0, blackboard=[{"key": "def", "value": 2.0}]))
    assert op.sp_max == 0.0
    assert op.sp == 0.0
    ok, why = sc.activate(0)
    assert (ok, why) == (False, "deploy_skill")
    assert sc.trigger_on_deploy() == 1
    assert sc.active is not None
    assert any(x["key"] == "op_skill_def" for x in op.buffs)
    for _ in range(150):                   # 5s duration
        b.tick_once()
    assert sc.active is None
    assert not any(x["key"] == "op_skill_def" for x in op.buffs)


def test_blackboard_duration_fallback():
    """LevelData duration == -1 -> use blackboard duration (deploy skills)."""
    sim, b, op = _deployed_op()
    sc = _swap_controller(op, b, _fake_skill(
        8, duration=-1.0, blackboard=[{"key": "duration", "value": 6.0}]))
    sc.trigger_on_deploy()
    assert sc.active is not None
    assert abs(sc.active.remaining - 6.0) < 1e-6, sc.active.remaining


def test_swordmaster_attack_recovery_exception():
    sim, b, op = _deployed_op()
    sc = _swap_controller(op, b, _fake_skill(2, sp_cost=10))
    op.sub_profession_id = "sword"         # ?? double attack
    op.sp = 0.0
    sc.on_attack_landed(2)
    assert op.sp == 1.0, op.sp             # +1 total, not +2
    op.sub_profession_id = "pioneer"
    op.sp = 0.0
    sc.on_attack_landed(2)
    assert op.sp == 2.0, op.sp             # combo hits each give SP


def _two_skill_controller(op, battle, equipped_index):
    skills = [
        {"skillId": "skcom_charge_cost[2]", "levels": [{
            "name": "a", "skillType": 2,
            "spData": {"spType": 1, "spCost": 39, "initSp": 8,
                       "increment": 1.0, "maxChargeTime": 1},
            "duration": None, "blackboard": []}]},
        {"skillId": "skchr_scave_2", "levels": [{
            "name": "b", "skillType": 1,
            "spData": {"spType": 1, "spCost": 40, "initSp": 13,
                       "increment": 1.0, "maxChargeTime": 1},
            "duration": 2.0, "blackboard": []}]},
    ]
    return OperatorSkillController(op, battle, skills,
                                   equipped_index=equipped_index)


def test_equipped_skill_defines_sp_bar():
    """Equipped skill owns the SP bar (maxSp/initSp)."""
    sim, b, op = _deployed_op()
    op.skill_controller = _two_skill_controller(op, b, 0)
    assert op.sp_max == 39.0, op.sp_max
    assert op.sp == 8.0, op.sp
    op.skill_controller = _two_skill_controller(op, b, 1)
    assert op.sp_max == 40.0, op.sp_max
    assert op.sp == 13.0, op.sp
    assert op.skill_controller.equipped_index == 1


def test_equipped_blocks_other_skill_activation():
    sim, b, op = _deployed_op()
    op.skill_controller = _two_skill_controller(op, b, 0)
    sc = op.skill_controller
    op.sp = 39.0
    ok, why = sc.activate(1)              # non-equipped S2
    assert (ok, why) == (False, "not_equipped"), (ok, why)
    op.sp = 39.0
    ok, why = sc.activate(0)              # equipped S1
    assert ok, (ok, why)


def test_squad_skill_index_wires_equipped():
    from ark_emulator import Simulator as S
    sim = S("level_main_01-01", squad=[
        {"charId": "char_149_scave", "phase": 2, "level": 50,
         "skillIndex": 1}])
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.battle_cost_add(100.0)
    b.deploy("char_149_scave", 3, 3)
    op = b.operators[0]
    sc = op.skill_controller
    assert sc.equipped_index == 1
    assert op.sp_max == 40.0, op.sp_max     # skchr_scave_2
    assert op.sp == 13.0, op.sp             # its initSp
    ok, why = sc.activate(0)
    assert (ok, why) == (False, "not_equipped"), (ok, why)


def test_no_hit_recovery_damage_flag():
    sim, b, op = _deployed_op()
    sc = _swap_controller(op, b, _fake_skill(4, sp_cost=10))
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    enemy = b.enemies[0]
    hp0 = op.hp
    b.apply_damage(op, 1.0, DamageType.PHYSICAL, source=enemy,
                   no_hit_recovery=True)
    assert op.sp == 0.0, op.sp             # flagged damage: no SP
    b.apply_damage(op, 1.0, DamageType.PHYSICAL, source=enemy)
    assert op.sp == 1.0, op.sp             # normal damage: +1 hit SP
    # element damage never triggers hit recovery, even with a source
    b.apply_damage(op, 1.0, DamageType.ELEMENT, source=enemy)
    assert op.sp == 1.0, op.sp
    assert op.hp < hp0


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
    print("all SP mechanics tests passed" if not failed
          else "%d failed" % failed)
    sys.exit(1 if failed else 0)
