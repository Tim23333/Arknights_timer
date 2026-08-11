"""Ritualist (\u5deb\u5f79) talent tests.

Covers the attack-attached element EP suite:
  - Threye T1: every damage output attaches decay EP = atk * ep_damage_ratio
    (game template threye_t_2 -> ApplyElementDamage DARK).
  - Pact support (pithst) T1: attack attaches neural + burning + decay EP,
    each atk * ep_damage_ratio (game template pithst_t_1).
  - PhonoR-0 T1: fixed decay EP per attack, only within the 40s deploy
    window (game phonor_t_1[effector]).
  - Bobb T1: the FIRST attack against each enemy applies a burning-EP DoT
    (atk * ep_damage_ratio_talent per second for 5s, game bobb_t_1[damage]).
  - Cello T1: enemies in range take atk * ep_damage_ratio decay EP every
    second plus a 0.2s sluggish (game cello_t_1 -> cello_t_1[core]).
  - Botany T1: any WATER (erosion) burst stacks attack speed up to 3
    (game botany_t_1, template has no range gate).
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


def _deploy(b, char_id):
    ok, pid = b.deploy(char_id, 2, 3)
    assert ok, pid
    return b.operators[0]


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
    # clear the stale pending attack and suppress the natural timer so the
    # forced hit is the only one (the op loop re-resolves a leftover entry)
    op._pending_attack = None
    op.attack_timer = 1e6


def _ep(unit, key):
    rec = [x for x in unit.buffs if x.get("key") == key]
    if not rec:
        return 0.0
    # full-bar model: damage = maxEp(1000) - remaining
    return max(0.0, 1000.0 - rec[-1]["value"])


def test_threye_attack_attaches_decay_ep():
    sim, b = _battle("char_4102_threye")
    op = _deploy(b, "char_4102_threye")
    ratio = float(op.talent_system.bb("ep_damage_ratio"))
    assert ratio > 0.0
    a = _spawn(b, 2, 4)
    _land_attack(b, op, a)
    sim.run_ticks(20)          # projectile lands -> ON_OUTPUT_DAMAGE
    atk = op.attributes.get("atk")
    got = _ep(a, "ep_dark")
    assert abs(got - atk * ratio) < 1e-3, (got, atk, ratio)


def test_pithst_attack_attaches_triple_ep():
    sim, b = _battle("char_616_pithst")
    op = _deploy(b, "char_616_pithst")
    ratio = float(op.talent_system.bb("ep_damage_ratio"))
    a = _spawn(b, 2, 4)
    _land_attack(b, op, a)
    sim.run_ticks(20)
    atk = op.attributes.get("atk")
    for key in ("ep_neural", "ep_fire", "ep_dark"):
        got = _ep(a, key)
        assert abs(got - atk * ratio) < 1e-3, (key, got, atk, ratio)


def test_phonor_fixed_dark_ep_within_deploy_window():
    sim, b = _battle("char_4136_phonor")
    op = _deploy(b, "char_4136_phonor")
    fixed = float(op.talent_system.bb("attack@dark_damage_value"))
    assert fixed > 0.0
    a = _spawn(b, 2, 4)
    _land_attack(b, op, a)
    sim.run_ticks(20)
    assert abs(_ep(a, "ep_dark") - fixed) < 1e-3, _ep(a, "ep_dark")
    # after the 40s deploy window the attach stops
    op.deploy_tick = b.tick - 1201
    bb = _spawn(b, 2, 5)
    _land_attack(b, op, bb)
    sim.run_ticks(20)
    assert _ep(bb, "ep_dark") == 0.0


def test_bobb_first_hit_burning_dot():
    sim, b = _battle("char_487_bobb")
    op = _deploy(b, "char_487_bobb")
    ratio = float(op.talent_system.bb("attack@ep_damage_ratio_talent"))
    assert ratio > 0.0
    atk = op.attributes.get("atk")
    a = _spawn(b, 2, 4)
    _land_attack(b, op, a)
    sim.run_ticks(40)          # projectile lands, DoT starts
    first = _ep(a, "ep_fire")
    assert first > 0.0
    sim.run_ticks(180)         # ~6s: per-second burning applications
    total = _ep(a, "ep_fire")
    apps = total / (atk * ratio)
    assert 5.0 <= apps <= 7.0, apps
    # a second attack on the same enemy does not restart a new DoT
    _land_attack(b, op, a)
    sim.run_ticks(90)
    assert len(op.talent_system._bobb_marked) == 1
    assert abs(_ep(a, "ep_fire") - total) < atk * ratio * 0.5
    # a different enemy gets its own DoT
    cc = _spawn(b, 2, 5)
    _land_attack(b, op, cc)
    sim.run_ticks(40)
    assert _ep(cc, "ep_fire") > 0.0


def test_cello_range_decay_aura_and_sluggish():
    sim, b = _battle("char_245_cello")
    op = _deploy(b, "char_245_cello")
    ratio = float(op.talent_system.bb("ep_damage_ratio"))
    slow = op.talent_system.bb("sluggish")
    assert ratio > 0.0
    a = _spawn(b, 2, 4)        # inside range
    far = _spawn(b, 7, 5)      # outside range
    sim.run_ticks(90)          # two 1s aura applications after deploy anim
    atk = op.attributes.get("atk")
    apps = _ep(a, "ep_dark") / (atk * ratio)
    assert 1.5 <= apps <= 2.5, apps
    assert _ep(far, "ep_dark") == 0.0
    if slow:
        # force the next 1s boundary and sample inside the 0.2s slow window
        op.talent_system._cello_acc = 0.99
        sim.run_ticks(2)
        rec = [x for x in a.buffs if x.get("key") == "op_sluggish"]
        assert rec, "in-range enemy must be slowed"
        assert _ep(a, "ep_dark") / (atk * ratio) >= apps + 0.5


def test_botany_erosion_burst_stacks_attack_speed():
    sim, b = _battle("char_4223_botany")
    op = _deploy(b, "char_4223_botany")
    aspd = float(op.talent_system.bb("attack_speed"))
    maxst = int(float(op.talent_system.bb("max_stack_cnt") or 3.0))
    base = op.attributes.get("attackSpeed")
    e = _spawn(b, 3, 4)
    for _ in range(6):
        b.add_ep(e, 1, 2000.0)     # WATER burst
        b.buffs.remove(e, "ep_burst_cd_1")
    rec = b.buffs.get(op, "botany_t_1[attack_speed]")
    assert rec is not None
    assert rec["layers"] == maxst
    assert abs(op.attributes.get("attackSpeed") - base - aspd * maxst) < 1e-6


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
