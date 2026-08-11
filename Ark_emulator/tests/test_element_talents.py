"""Element-damage talent wiring tests.

Covers 酒神 T1 形为心役 (every attack attaches SANITY EP + one-time splash
to surrounding enemies) and 烛煌 T1 熔点引爆 (deploy-time blaze2_t_1
listener: any enemy FIRE burst heals her and deals atk*ep_damage_scale
element damage to the bursting enemy via ON_EP_BREAK_START).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


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


def _spawn(b, row, col):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
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


def _ep(unit, key):
    rec = [x for x in unit.buffs if x.get("key") == key]
    if not rec:
        return 0.0
    # full-bar model: damage = maxEp(1000) - remaining
    return max(0.0, 1000.0 - rec[-1]["value"])


def test_ranged_attack_ep_lands_with_projectile_dark():
    """PRTS: 攻击直接附带的元素损伤紧接在当次攻击的伤害后处理 - a ranged
    operator's attack-attached EP must apply on the projectile hit, not at
    launch (折光 S1 镭射穿凿 attack@ep_damage_ratio 0.1)."""
    sim, b = _battle("char_499_kaitou", skill_index=0)
    b.deploy("char_499_kaitou", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    assert pa is not None and pa.get("ranged")
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    assert _ep(e, "ep_dark") == 0.0, \
        "ranged attack EP must not apply at launch"
    for _ in range(90):
        b.tick_once()
        if _ep(e, "ep_dark") > 0:
            break
    atk = op.attributes.get("atk")
    assert abs(_ep(e, "ep_dark") - atk * 0.1) < 1e-6, _ep(e, "ep_dark")
    assert _ep(e, "ep_neural") == 0.0


def test_phatm2_t1_attack_ep_attach_and_splash():
    sim, b = _battle("char_1042_phatm2")
    ok, pid = b.deploy("char_1042_phatm2", 2, 3)
    assert ok, pid
    op = b.operators[0]
    a = _spawn(b, 2, 4)          # primary target
    bb = _spawn(b, 3, 4)         # adjacent -> splash
    cc = _spawn(b, 5, 4)         # far -> no EP
    _land_attack(b, op, a)
    sim.run_ticks(10)            # projectile lands
    atk = op.attributes.get("atk")
    assert abs(_ep(a, "ep_neural") - atk * 0.3) < 1e-6, _ep(a, "ep_neural")
    assert abs(_ep(bb, "ep_neural") - atk * 0.2) < 1e-6, _ep(bb, "ep_neural")
    assert abs(_ep(cc, "ep_neural") - 0.0) < 1e-9


def test_blaze2_t1_deploy_buff_fire_burst_damage_and_heal():
    sim, b = _battle("char_1040_blaze2")
    ok, bid = b.deploy("char_1040_blaze2", 2, 3)
    assert ok, bid
    op = b.operators[0]
    listener = [x for x in op.buffs if x.get("key") == "blaze2_t_1"]
    assert listener, "talent listener buff must be applied on deploy"
    bb = listener[-1].get("blackboard") or {}
    assert abs(bb.get("ep_damage_scale", 0.0) - 3.5) < 1e-9
    op.hp = op.max_hp - 500.0
    hp0 = op.hp
    e = _spawn(b, 3, 4)
    b.add_ep(e, 2, 1000.0)       # FIRE burst
    expect = min(op.max_hp, hp0 + op.max_hp * 0.12)
    assert abs(op.hp - expect) < 1e-6, (op.hp, expect)
    # ON_EP_BREAK_START: atk * 3.5 element damage accumulates for next burst
    got = _ep(e, "ep_fire")
    assert abs(got - op.attributes.get("atk") * 3.5) < 1e-3, got
    assert b.buffs.get(e, "ep_burst_cd_2"), "burst cooldown still active"


def test_kaitou_s1_burst_window_extra_element_damage():
    """折光 S1: while the target is in DARK (凋亡) burst, attacks deal
    extra ELEMENT HP damage = atk * 0.2 (attack@extra_ep_damage_scale).
    Game template kaitou_s_1[ep_damage]: FilterEPBreakRecoveryType DARK
    -> AdvancedApplyDamage ELEMENT.  EP bars are locked during a burst,
    so the bonus is HP damage, not an EP accumulation."""
    sim, b = _battle("char_499_kaitou", skill_index=0)
    b.deploy("char_499_kaitou", 2, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0,
                       "magicResistance": 0.0},
        "row": 2, "col": 5})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    b.add_ep(e, 3, 1000.0)            # DARK (凋亡) burst
    assert b.buffs.get(e, "ep_burst_cd_3"), "target must be in DARK burst"
    hp0 = e.hp
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    for _ in range(90):
        b.tick_once()
        if e.hp < hp0:
            break
    atk = op.attributes.get("atk")
    # normal arts hit (mres 0 -> full atk) + extra ELEMENT damage
    assert abs((hp0 - e.hp) - atk * 1.2) < 1e-6, (hp0 - e.hp, atk * 1.2)
    # burst lock: EP unchanged (bar full after burst, no accumulation)
    assert abs(_ep(e, "ep_dark")) < 1e-9, \
        "burst lock: attack-attached EP must not change"


def test_kaitou_s2_burst_window_extra_element_damage():
    """折光 S2: attacks on DARK-bursting targets deal extra ELEMENT HP
    damage = atk * 0.4 (attack@extra_ep_damage_scale)."""
    sim, b = _battle("char_499_kaitou", skill_index=1)
    b.deploy("char_499_kaitou", 2, 3)
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0,
                       "magicResistance": 0.0},
        "row": 2, "col": 5})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    b.add_ep(e, 3, 1000.0)            # DARK burst
    hp0 = e.hp
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    for _ in range(90):
        b.tick_once()
        if e.hp < hp0:
            break
    atk = op.attributes.get("atk")
    # normal arts hit (mres 0 -> full atk) + extra ELEMENT damage
    assert abs((hp0 - e.hp) - atk * 1.4) < 1e-6, (hp0 - e.hp, atk * 1.4)


def test_warmy_s1_fire_ep():
    """温米 S1: attack-attached EP must be 灼燃 (FIRE/2), not neural."""
    sim, b = _battle("char_4081_warmy", skill_index=0)
    b.deploy("char_4081_warmy", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    b._operator_attack(op, e, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    for _ in range(90):
        b.tick_once()
        if _ep(e, "ep_fire") > 0:
            break
    atk = op.attributes.get("atk")
    assert abs(_ep(e, "ep_fire") - atk * 0.15) < 1e-6, _ep(e, "ep_fire")
    assert _ep(e, "ep_neural") == 0.0


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
