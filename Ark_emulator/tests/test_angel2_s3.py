"""Angelina2 (新约能天使) S3 "使命必达！":

  - 50 ammo, 5 ammo consumed per attack, skill ends at 0
  - every attack is a 5-hit combo (each atk * attack@atk_scale)
  - with a delivery coordinate (token_10056_angel2_target): cannon
    splash atk * attack@cannon_atk_scale on it + deploy the ground
    operator with the longest redeploy timer there + attack@sp SP
  - talent "火力电台": damage inside the delivery area is amplified
    (damage_scale, existing generic token-area logic)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _setup(with_scave=True):
    squad = [
        {"charId": "char_1041_angel2", "phase": 2, "level": 50,
         "skillIndex": 2, "skillLevels": [1, 1, 1]},
    ]
    if with_scave:
        squad.append({"charId": "char_149_scave", "phase": 2, "level": 50,
                      "skillIndex": 0, "skillLevels": [1, 1, 1]})
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    for (r, c) in [(2, 3), (1, 3), (2, 2)]:
        ok = b.deploy("char_1041_angel2", r, c)
        if ok[0]:
            break
    op = b.operators[0]
    if with_scave:
        for (r, c) in [(3, 4), (3, 3), (4, 4), (4, 3)]:
            ok = b.deploy("char_149_scave", r, c)
            if ok[0]:
                break
    return sim, b, op


def _activate(op):
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    ok, why = sc.activate(2)
    assert ok, why
    return sc


def _land_attack(sim, b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    for _ in range(12):
        b.tick_once()
        if not any(not p.dead for p in getattr(b, "projectiles", [])):
            break


def _damage_calls(sim, b, op, e):
    calls = []
    orig = b.apply_damage

    def traced(target, amt, dtype, **kw):
        r = orig(target, amt, dtype, **kw)
        calls.append(round(float(getattr(r, "amount", r)), 1))
        return r

    b.apply_damage = traced
    try:
        _land_attack(sim, b, op, e)
    finally:
        b.apply_damage = orig
    return calls


def test_angel2_s3_ammo_and_combo():
    """S3：50 发弹药、每次攻击 5 连击、消耗 5 发."""
    sim, b, op = _setup(with_scave=False)
    sc = _activate(op)
    assert sc.active.ammo == 50
    atk = op.attributes.get("atk")
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": op.row, "col": op.col + 2})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    calls = _damage_calls(sim, b, op, e)
    # 无投递坐标：弹道普攻 1 + 5 连击 = 6 次 atk×1.0（无区域增伤）
    assert len(calls) == 6, calls
    assert all(abs(x - atk) < 0.5 for x in calls), calls
    sc.on_ammo_attack()
    assert sc.active.ammo == 45
    print("OK angel2 S3 combo+ammo:", calls)


def test_angel2_s3_delivery_deploy_and_sp():
    """S3 投递：溅射 + 部署再部署最久干员 + 6 SP + 区域增伤."""
    sim, b, op = _setup(with_scave=True)
    sc = _activate(op)
    scave = [o for o in b.operators if o.char_id == "char_149_scave"][-1]
    b.withdraw(scave.inst_id)
    assert "char_149_scave" in b._redeploy_until
    ok, pid = b.spawn_token_forced("token_10056_angel2_target",
                                   op.row + 1, op.col + 1, owner=op)
    assert ok, pid
    dest = [t for t in b.tokens if not t.dead][-1]
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": dest.row, "col": dest.col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    atk = op.attributes.get("atk")
    calls = _damage_calls(sim, b, op, e)
    # 投递区域内：弹道 1 + 5 连击 + 溅射 2.5 倍，全被天赋 ×2.5
    assert len(calls) == 7, calls
    assert all(abs(x - atk * 2.5) < 1.0 for x in calls[:6]), calls[:6]
    assert abs(calls[-1] - atk * 2.5 * 2.5) < 1.0, calls[-1]
    scave2 = [o for o in b.operators if o.char_id == "char_149_scave"]
    assert scave2, "scave must be redeployed to the delivery coordinate"
    assert (scave2[-1].row, scave2[-1].col) == (dest.row, dest.col)
    assert abs(scave2[-1].sp - 14.0) < 0.01   # initSp 8 + attack@sp 6
    print("OK angel2 S3 delivery deploy+sp, dmg calls:", calls)


if __name__ == "__main__":
    test_angel2_s3_ammo_and_combo()
    test_angel2_s3_delivery_deploy_and_sp()
