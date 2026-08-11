"""Chain-healer trait jump wiring:
- base jump params come from the trait blackboard (attack@chain.max_target
  3 / attack@chain.atk_scale 0.75);
- an active skill can add extra jumps (attack@chain.extra_value, e.g.
  莎草 S2 / 明椒 S2 / 乌啾 S1 / Mon3tr S1) or replace the jump count
  (attack@chain.max_target)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


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


def _deploy(b, char_id, row, col):
    ok, pid = b.deploy(char_id, row, col)
    assert ok, (char_id, pid)
    return b.operators[-1]


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    op._pending_attack = None
    op.attack_timer = 1e6


def test_papyrs_s2_chain_heal_extra_jump():
    """莎草 S2: 每次治疗的跳跃次数 +1 (attack@chain.extra_value 1) - a
    heal reaches 4 allies (primary + 3 jumps) instead of the base 3."""
    sim, b = _battle("char_4139_papyrs", skill_index=1)
    papyrs = _deploy(b, "char_4139_papyrs", 2, 4)
    allies = [
        _deploy(b, "char_149_scave", 3, 3),
        _deploy(b, "char_149_scave", 3, 4),
        _deploy(b, "char_149_scave", 3, 5),
        _deploy(b, "char_149_scave", 1, 5),
    ]
    # all four allies are inside the medic range and wounded to 50%
    shape = set(papyrs.range_shape or [])
    for a in allies:
        assert (a.row - papyrs.row, a.col - papyrs.col) in shape, \
            (a.row, a.col)
        a.hp = a.max_hp * 0.5
    sc = papyrs.skill_controller
    papyrs.sp = sc.skills[1].sp_cost
    ok, why = sc.activate(1)
    assert ok, why
    # active skill params: base 3 + extra 1 = 4 targets
    max_target, scale = papyrs.trait_system.chain_heal_params()
    assert max_target == 4, max_target
    assert abs(scale - 0.75) < 1e-9
    primary = min(allies, key=lambda a: a.hp / a.max_hp)
    _land_attack(b, papyrs, primary)
    healed = [a for a in allies if a.hp > a.max_hp * 0.5 + 0.01]
    assert len(healed) == 4, \
        "S2 extra jump must heal 4 allies, got %d" % len(healed)


def test_chain_heal_base_jump_count():
    """Without an active skill the chain-healer trait heals base
    max_target=3 allies (primary + 2 jumps)."""
    sim, b = _battle("char_4139_papyrs", skill_index=0)
    papyrs = _deploy(b, "char_4139_papyrs", 2, 4)
    allies = [
        _deploy(b, "char_149_scave", 3, 3),
        _deploy(b, "char_149_scave", 3, 4),
        _deploy(b, "char_149_scave", 3, 5),
        _deploy(b, "char_149_scave", 1, 5),
    ]
    for a in allies:
        a.hp = a.max_hp * 0.5
    assert papyrs.trait_system.chain_heal_params()[0] == 3
    primary = min(allies, key=lambda a: a.hp / a.max_hp)
    _land_attack(b, papyrs, primary)
    healed = [a for a in allies if a.hp > a.max_hp * 0.5 + 0.01]
    assert len(healed) == 3, \
        "base chain heal must reach 3 allies, got %d" % len(healed)


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
