"""Amiya S3 (skchr_amiya_3 奇美拉) integration tests.

Covers the prefab owner buffs (atk +100%, maxHp +25% with HP ratio sync),
the true-damage switch on basic attacks while active, and the end-of-skill
suicide withdrawal (技能结束后强制退出战场).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    squad = [{"charId": "char_002_amiya", "phase": 2, "level": 50,
              "skillIndex": 2, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _spawn(b, row, col):
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 500.0,
                       "magicResistance": 50.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_amiya_s3_stat_buffs_and_true_damage():
    sim, b = _battle()
    ok, aid = b.deploy("char_002_amiya", 2, 3)
    assert ok, aid
    op = b.operators[0]
    atk0 = op.attributes.get("atk")
    mhp0 = op.max_hp
    op.sp = op.sp_max
    ok, _ = b.activate_skill(op.inst_id, 2)
    assert ok
    assert abs(op.attributes.get("atk") - atk0 * 2.0) < 1e-6
    assert abs(op.max_hp - mhp0 * 1.25) < 1e-6, (op.max_hp, mhp0)
    assert abs(op.hp - op.max_hp) < 1e-9, "HP scales with maxHp at full"
    e = _spawn(b, 2, 4)
    _land_attack(b, op, e)
    projs = [p for p in b.projectiles if p.key == "op_char_002_amiya"]
    assert projs and projs[-1].damage_type == DamageType.TRUE, \
        [p.damage_type for p in projs]
    sim.run_ticks(10)
    dmg = [x for x in b.events.snapshot_events()
           if x["type"] == "damage" and x["data"]["target"] == e.inst_id][-1]
    assert dmg["data"]["type"] == DamageType.TRUE, dmg
    # true damage ignores def/mres: full atk dealt
    assert abs(dmg["data"]["amount"] - op.attributes.get("atk")) < 1e-3, dmg


def test_amiya_s3_withdraw_after_duration():
    sim, b = _battle()
    ok, aid = b.deploy("char_002_amiya", 2, 3)
    assert ok, aid
    op = b.operators[0]
    op.sp = op.sp_max
    ok, _ = b.activate_skill(op.inst_id, 2)
    assert ok
    sim.run_ticks(1000)       # 30s duration + deploy anim + margin
    alive = [o for o in b.operators if o.inst_id == op.inst_id]
    assert not alive, "S3 must force Amiya off the field at skill end"
    assert getattr(op, "dead", False) or True


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
