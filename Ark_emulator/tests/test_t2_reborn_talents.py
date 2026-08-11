"""Talent-2 wiring tests for phatm2 (??) and blaze2 (??).

Covers:
  - phatm2 T2 ????: field-wide attack_speed -12 on enemies in SANITY
    burst recovery, and 70 SANITY EP to enemies in her attack range on
    each normal attack (spell-on);
  - blaze2 T2 ??????: lethal hit -> downed (hp 1, 6000 barrier, heal-free,
    no attack/block, %maxHp regen), revive at full HP stuns enemies within
    radius 1.7 for 5s, then the talent can trigger again.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import AbnormalFlag, EnemyState


def _battle(char_id, skill_index=0):
    squad = [{"charId": char_id, "phase": 2, "level": 50,
              "skillIndex": skill_index, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _spawn(b, row, col, atk=0.0, hp=50000.0):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": hp, "atk": atk, "def": 0.0,
                       "rangeRadius": 1.5, "attackSpeed": 100.0,
                       "baseAttackTime": 1.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT   # stay put: COMBAT enemies still attack
    return e


def _ep(unit, key):
    rec = [x for x in unit.buffs if x.get("key") == key]
    if not rec:
        return 0.0
    # full-bar model: damage = maxEp(1000) - remaining
    return max(0.0, 1000.0 - rec[-1]["value"])


def test_phatm2_t2_sanity_burst_attack_speed_debuff():
    sim, b = _battle("char_1042_phatm2")
    ok, pid = b.deploy("char_1042_phatm2", 2, 3)
    assert ok, pid
    op = b.operators[0]
    specs = op.talent_system.enemy_aura_specs()
    assert len(specs) == 2, specs
    speed = [x for x in specs if x["kind"] == "phatm2_t2_speed"]
    assert abs(speed[0]["attack_speed"] - (-12.0)) < 1e-9

    e = _spawn(b, 2, 4)            # in her y-2 range
    far = _spawn(b, 5, 4)          # out of range
    sim.run_ticks(1)               # aura sync
    assert b.buffs.get(e, "phatm2_t_2"), "range listener buff missing"
    assert b.buffs.get(far, "phatm2_t_2") is None
    # no debuff before the burst
    assert b.buffs.get(e, "phatm2_t_2[attack_speed]") is None
    atk_spd0 = e.attributes.get("attackSpeed")
    assert abs(atk_spd0 - 100.0) < 1e-9

    # trigger SANITY burst (ep_max = 1000 at level 0)
    b.add_ep(e, 0, 2000.0)
    assert b.buffs.get(e, "ep_burst_cd_0"), "burst cooldown expected"
    sim.run_ticks(1)
    buff = b.buffs.get(e, "phatm2_t_2[attack_speed]")
    assert buff is not None, "attack_speed debuff must appear during burst"
    assert abs(buff["add"] - (-12.0)) < 1e-9
    assert abs(e.attributes.get("attackSpeed") - 88.0) < 1e-6

    # burst ends -> debuff removed by the per-tick aura sync
    b.buffs.remove(e, "ep_burst_cd_0")
    sim.run_ticks(1)
    assert b.buffs.get(e, "phatm2_t_2[attack_speed]") is None
    assert abs(e.attributes.get("attackSpeed") - 100.0) < 1e-6


def test_phatm2_t2_enemy_normal_attack_deals_sanity_ep():
    sim, b = _battle("char_1042_phatm2")
    ok, pid = b.deploy("char_1042_phatm2", 2, 3)
    assert ok, pid
    op = b.operators[0]
    e = _spawn(b, 2, 4, atk=100.0)     # in range, will attack
    sim.run_ticks(1)
    assert b.buffs.get(e, "phatm2_t_2")
    e.attack_timer = 0.0
    # run the AI until the windup starts (spell-on fires immediately)
    for _ in range(60):
        if _ep(e, "ep_neural") >= 70.0:
            break
        b.tick_once()
    got = _ep(e, "ep_neural")
    assert abs(got - 70.0) < 1e-6, got
    assert e._pending_attack is not None, "attack should be winding up"


def test_blaze2_t2_down_regen_revive_stun_and_retrigger():
    sim, b = _battle("char_1040_blaze2")
    ok, bid = b.deploy("char_1040_blaze2", 2, 3)
    assert ok, bid
    op = b.operators[0]
    t2 = [x for x in op.buffs if x.get("key") == "blaze2_t_2"]
    assert t2, "blaze2_t_2 listener buff missing on deploy"
    bb = t2[-1].get("blackboard") or {}
    assert abs(bb["hp_recovery_per_sec_by_max_hp_ratio"] - 0.03) < 1e-9
    assert abs(bb["dynamic"] - 6000.0) < 1e-9
    assert abs(bb["stun"] - 5.0) < 1e-9

    # freeze the level wave scheduler: no further spawns, and the battle
    # cannot end while our COMBAT test enemies are still alive
    try:
        b.waves._idx = len(b.waves.timeline)
        b.waves.finished = True
    except Exception:
        pass

    # lethal hit -> downed, not dead
    near = _spawn(b, 2, 4, atk=0.0)    # within radius 1.7 of (2,3)
    far = _spawn(b, 5, 4, atk=0.0)
    b.apply_damage(op, 99999.0, 0)     # PHYSICAL lethal
    assert op._reborn_state
    assert not op.dead
    assert abs(op.hp - 1.0) < 1e-9, op.hp
    assert abs(op.barrier - 6000.0) < 1e-9, op.barrier
    assert b.buffs.get(op, "blaze2_t_2[reborn_state]")
    assert op.flag(AbnormalFlag.HEAL_FREE)
    assert op.flag(AbnormalFlag.DISARMED)
    assert op.flag(AbnormalFlag.SILENCED)

    # external healing is blocked while downed
    hp0 = op.hp
    b.apply_heal(op, 5000.0, source=None)
    assert abs(op.hp - hp0) < 1e-9

    # CC immunity + counter while downed (stun source reflects back)
    att = _spawn(b, 3, 3, atk=0.0)
    b.add_abnormal(op, AbnormalFlag.STUNNED, 3.0, source=att)
    assert not op.flag(AbnormalFlag.STUNNED)
    assert att.flag(AbnormalFlag.STUNNED), "stun must be countered"
    b.add_abnormal(op, AbnormalFlag.FROZEN, 3.0, source=None)
    assert not op.flag(AbnormalFlag.FROZEN)

    # regen 3% maxHp per second -> revive after ~33s
    guard = 0
    while op._reborn_state and guard < 2500:
        b.tick_once()
        guard += 1
    assert not op._reborn_state, "should have revived"
    assert not op.dead
    assert abs(op.hp - op.max_hp) < 1e-6
    assert abs(op.barrier - 0.0) < 1e-9
    assert not op.flag(AbnormalFlag.HEAL_FREE)
    assert near.flag(AbnormalFlag.STUNNED), "near enemy must be stunned"
    rec = near.abnormal[AbnormalFlag.STUNNED]
    assert abs(rec["ticks"] - 150) <= 2, rec["ticks"]
    assert not far.flag(AbnormalFlag.STUNNED)

    # invincible window during revive animation: wait it out then retrigger
    sim.run_ticks(12)
    b.apply_damage(op, 99999.0, 0)
    assert op._reborn_state, "talent must trigger again after revive"
    assert abs(op.hp - 1.0) < 1e-9
    assert abs(op.barrier - 6000.0) < 1e-9


def test_blaze2_t2_barrier_break_kills_while_down():
    sim, b = _battle("char_1040_blaze2")
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True
    ok, bid = b.deploy("char_1040_blaze2", 2, 3)
    assert ok, bid
    op = b.operators[0]
    _spawn(b, 5, 4, atk=0.0)     # keeps the battle running (no victory)
    b.apply_damage(op, 99999.0, 2)     # PURE lethal -> downed
    assert op._reborn_state and abs(op.barrier - 6000.0) < 1e-9
    sim.run_ticks(12)            # wait out the 0.3s invincible window
    b.apply_damage(op, 6000.0, 2)      # PURE drains the barrier exactly
    assert abs(op.barrier - 0.0) < 1e-9 and not op.dead
    b.apply_damage(op, 6000.0, 2)      # lethal with no barrier -> death
    assert op.dead
    assert op.hp == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
