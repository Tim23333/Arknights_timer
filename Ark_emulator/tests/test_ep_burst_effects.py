"""Side-split element burst effects (PRTS element page, 2026-04-07 rule).

Covers: enemy/operator burst effects for all four element types, the
global EP lock during burst cooldown, per-type cooldown durations (neural
10s / erosion 10s player & 8s enemy / burning 10s / decay 15s), decaying
enemy decay-weaken, the operator decay DoT (SP drain + magic per second),
and full EP restore when the burst ends.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import AbnormalFlag, DamageType, EnemyState


def _battle():
    squad = [{"charId": "char_149_scave", "phase": 2, "level": 50,
              "skillIndex": 0, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    ok, pid = b.deploy("char_149_scave", 3, 3)
    assert ok, pid
    op = b.operators[-1]
    op.hp = op.max_hp
    return sim, b, op


def _spawn(b, row, col, hp=50000.0):
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _ep(unit, key):
    rec = [x for x in unit.buffs if x.get("key") == key]
    return rec[-1]["value"] if rec else 0.0


def test_enemy_sanity_burst_paralysis_no_hp_damage():
    sim, b, op = _battle()
    e = _spawn(b, 2, 4)
    hp0 = e.hp
    b.add_ep(e, 0, 2000.0)                 # SANITY burst
    assert e.flag(AbnormalFlag.PALSY), "enemy burst must paralyse"
    rec = e.abnormal.get(AbnormalFlag.PALSY)
    assert rec["layers"] == 3
    assert abs(rec["ticks"] - 15 * 30) < 2, rec["ticks"]
    assert abs(hp0 - e.hp) < 1e-9, \
        "6000 element damage hits the locked bar -> no HP loss"
    cd = b.buffs.get(e, "ep_burst_cd_0")
    assert cd and abs(cd["remaining_ticks"] - 10 * 30) < 2


def test_operator_sanity_burst_stun_and_true_damage():
    sim, b, op = _battle()
    op.hp = op.max_hp
    hp0 = op.hp
    b.add_ep(op, 0, 2000.0)                # SANITY burst (player side)
    assert op.flag(AbnormalFlag.STUNNED), "operator burst must stun 10s"
    rec = op.abnormal.get(AbnormalFlag.STUNNED)
    assert abs(rec["ticks"] - 10 * 30) < 2
    assert abs((hp0 - op.hp) - 1000.0) < 1e-6, hp0 - op.hp
    cd = b.buffs.get(op, "ep_burst_cd_0")
    assert cd and abs(cd["remaining_ticks"] - 10 * 30) < 2


def test_enemy_erosion_burst_def_stack_and_8s_cooldown():
    sim, b, op = _battle()
    e = _spawn(b, 2, 4)
    b.add_ep(e, 1, 2000.0)                 # WATER burst (enemy side)
    rec = b.buffs.get(e, "ep_erosion_def")
    assert rec is not None and rec["add"] == -120.0 and rec["layers"] == 1
    cd = b.buffs.get(e, "ep_burst_cd_1")
    assert cd and abs(cd["remaining_ticks"] - 8 * 30) < 2, \
        "enemy erosion burst lasts 8s"
    b.buffs.remove(e, "ep_burst_cd_1")
    b.add_ep(e, 1, 2000.0)                 # second burst stacks -120 DEF
    rec = b.buffs.get(e, "ep_erosion_def")
    assert rec["layers"] == 2
    assert abs(e.attributes.get("def") - (-240.0)) < 1e-6


def test_operator_erosion_burst_def100_and_phys_damage():
    sim, b, op = _battle()
    op.attributes.base["def"] = 0.0
    op.hp = op.max_hp
    hp0 = op.hp
    b.add_ep(op, 1, 2000.0)                # WATER burst (player side)
    rec = b.buffs.get(op, "ep_erosion_def")
    assert rec is not None and rec["add"] == -100.0
    assert abs((hp0 - op.hp) - 800.0) < 1e-6, hp0 - op.hp
    cd = b.buffs.get(op, "ep_burst_cd_1")
    assert cd and abs(cd["remaining_ticks"] - 10 * 30) < 2


def test_enemy_fire_burst_mres_debuff_10s():
    sim, b, op = _battle()
    e = _spawn(b, 2, 4)
    base_mres = e.attributes.get("magicResistance")
    b.add_ep(e, 2, 2000.0)                 # FIRE burst (enemy side)
    rec = b.buffs.get(e, "ep_fire_mres")
    assert rec is not None and rec["add"] == -20.0
    assert abs(rec["remaining_ticks"] - 10 * 30) < 2
    assert abs(e.attributes.get("magicResistance")
               - (base_mres - 20.0)) < 1e-6


def test_operator_fire_burst_magic_damage_benefits_mres_debuff():
    sim, b, op = _battle()
    op.attributes.base["magicResistance"] = 30.0
    op.hp = op.max_hp
    hp0 = op.hp
    b.add_ep(op, 2, 2000.0)                # FIRE burst (player side)
    rec = b.buffs.get(op, "ep_fire_mres")
    assert rec is not None
    assert abs(op.attributes.get("magicResistance") - 10.0) < 1e-6
    assert abs((hp0 - op.hp) - 1200.0 * 0.9) < 1e-6, hp0 - op.hp


def test_enemy_dark_burst_weaken_decays_and_scales_damage():
    sim, b, op = _battle()
    e = _spawn(b, 2, 4)
    b.add_ep(e, 3, 2000.0)                 # DARK burst (enemy side)
    wk = b.buffs.get(e, "ep_dark_weaken")
    assert wk is not None and abs(wk["mul"] - (-0.5)) < 1e-9
    cd = b.buffs.get(e, "ep_burst_cd_3")
    assert cd and abs(cd["remaining_ticks"] - 15 * 30) < 2
    # at burst start the weakened enemy deals 50% true damage
    op.hp = op.max_hp
    hp0 = op.hp
    b.apply_damage(op, 200.0, DamageType.TRUE, source=e)
    assert abs((hp0 - op.hp) - 100.0) < 1e-6, hp0 - op.hp
    # 5s later the weaken decays to 50% x (10s/15s) = ~33%
    sim.run_ticks(150)
    assert -0.36 < wk["mul"] < -0.31, wk["mul"]
    hp0 = op.hp
    b.apply_damage(op, 200.0, DamageType.TRUE, source=e)
    assert abs((hp0 - op.hp) - 200.0 * (1.0 + wk["mul"])) < 1e-6


def test_operator_dark_burst_silence_sp_drain_and_dot():
    sim, b, op = _battle()
    op.sp = 10.0
    op.hp = op.max_hp
    hp0 = op.hp
    b.add_ep(op, 3, 2000.0)                # DARK burst (player side)
    assert op.flag(AbnormalFlag.SILENCED)
    assert op.flag(AbnormalFlag.SP_RECOVER_STOPPED)
    assert b.buffs.get(op, "ep_dark_dot") is not None
    sim.run_ticks(91)                      # 3s: -3 SP, 3 x 100 magic
    assert abs(op.sp - 7.0) < 1e-6, op.sp
    assert abs((hp0 - op.hp) - 300.0) < 1e-6, hp0 - op.hp


def test_burst_cooldown_locks_all_ep_and_end_restores_full():
    sim, b, op = _battle()
    e = _spawn(b, 2, 4)
    b.add_ep(e, 1, 500.0)                  # water bar 500/1000
    b.add_ep(e, 0, 2000.0)                 # neural burst
    assert b.buffs.get(e, "ep_burst_cd_0")
    assert b.add_ep(e, 1, 100.0) is False, "locked: no new burst"
    assert abs(_ep(e, "ep_water") - 500.0) < 1e-9, \
        "all EP bars locked during burst cooldown"
    assert b.add_ep(e, 2, 100.0) is False
    assert b.add_ep(e, 3, 100.0) is False
    sim.run_ticks(300)                     # neural cooldown = 10s
    assert b.buffs.get(e, "ep_burst_cd_0") is None
    assert any(x["type"] == "ep_burst_end"
               for x in b.events.snapshot_events())
    assert abs(_ep(e, "ep_water") - 1000.0) < 1e-9, \
        "burst end restores every element bar to max (full=1000)"
    b.add_ep(e, 1, 100.0)
    assert abs(_ep(e, "ep_water") - 900.0) < 1e-9, \
        "EP deducts again after the cooldown (1000 - 100)"


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
