"""3-tick target-search cadence (SelectorTrigger.SEARCH_TARGET_TICK=3,
dump.cs:437169).

In the game an ability re-runs its target selector at most once every 3
logic ticks (0.1s at the 30Hz rough-logic rate; TileTrigger uses 5), and
Search(force) bypasses the gate.  Between refreshes the previous target is
kept while still selectable, so a new higher-priority target only wins at
the next search boundary.  The simulator applies the gate to basic-attack
target selection for operators (incl. healers) and enemies.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(200.0)
    return sim, b


def _deploy(b, cid, row, col):
    ok, pid = b.deploy(cid, row, col)
    assert ok, pid
    return next(o for o in b.operators if o.inst_id == pid)


def _spawn(b, row, col, **attrs):
    over = {"attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0,
                           "rangeRadius": 4.0, **attrs},
            "row": row, "col": col}
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides=over)
    e = b.enemies[-1]
    e.state = EnemyState.ATTACK
    return e


def test_search_gate_keeps_cached_target_until_period():
    from ark_emulator.targeting import search_gate
    sim, b = _battle()
    op = _deploy(b, "char_149_scave", 3, 3)
    calls = []

    def scan():
        calls.append(b.tick)
        return len(calls)

    first = search_gate(op, b, scan)
    assert first == 1 and calls == [b.tick]
    # within the 3-tick window the cached result is kept (no re-scan)
    assert search_gate(op, b, scan) == first
    assert search_gate(op, b, scan) == first
    assert len(calls) == 1
    # force bypasses the gate
    assert search_gate(op, b, scan, force=True) == 2
    assert len(calls) == 2
    # after the period elapses the next search re-runs
    for _ in range(3):
        b.tick_once()
    assert search_gate(op, b, scan) == 3
    assert len(calls) == 3


def test_medic_keeps_heal_target_between_search_ticks():
    sim, b = _battle()
    medic = _deploy(b, "char_120_hibisc", 2, 3)
    ally1 = _deploy(b, "char_149_scave", 3, 3)
    ally2 = _deploy(b, "char_1040_blaze2", 2, 4)
    sim.run_ticks(30)                     # deploy animations finish
    ally1.hp = ally1.max_hp * 0.5
    ally2.hp = ally2.max_hp * 0.7
    from ark_emulator.targeting import HateSystem
    hate = HateSystem(b)
    first = hate.operator_attack_target(medic)
    assert first is ally1, "most wounded ally first"
    # ally2 becomes more wounded inside the search window
    ally2.hp = ally2.max_hp * 0.3
    assert hate.operator_attack_target(medic) is ally1, \
        "healer keeps the cached target within 3 ticks"
    for _ in range(3):
        b.tick_once()
    assert hate.operator_attack_target(medic) is ally2, \
        "new search boundary switches to the new most wounded"


def test_enemy_keeps_nearest_target_between_search_ticks():
    from ark_emulator.ai import _start_normal_attack
    sim, b = _battle()
    far = _deploy(b, "char_149_scave", 3, 3)
    sim.run_ticks(30)
    e = _spawn(b, 3, 5)                   # dist to far = 2.0
    e.state = EnemyState.STUN              # keep the real AI inert; we
                                           # drive the search manually
    _start_normal_attack(e, b, 1.0)
    assert e._ai_target is far, "first scan locks the nearest operator"
    # a closer operator deploys inside the search window
    closer = _deploy(b, "char_1040_blaze2", 2, 4)   # dist to e = 1.414
    sim.run_ticks(1)
    _start_normal_attack(e, b, 1.0)
    assert e._ai_target is far, \
        "enemy keeps the cached nearest within 3 ticks"
    assert e._pending_attack is not None
    assert e._pending_attack["target"] is far
    # wait out the deploy animation (15 ticks) so the closer operator is
    # attackable again; the search boundary has long since passed
    sim.run_ticks(16)
    _start_normal_attack(e, b, 1.0)
    assert e._ai_target is closer, "search boundary switches to the closer"
    assert e._pending_attack["target"] is closer


def test_operator_attack_target_force_rescans():
    sim, b = _battle()
    op = _deploy(b, "char_149_scave", 3, 3)
    e1 = _spawn(b, 3, 4)
    e2 = _spawn(b, 3, 5)
    sim.run_ticks(30)
    from ark_emulator.targeting import HateSystem
    hate = HateSystem(b)
    t = hate.operator_attack_target(op)
    assert t is e1, "first in-range enemy (spawn order) locked"
    # force bypasses the 3-tick gate
    assert hate.operator_attack_target(op, force=True) is e1
    assert getattr(op, "_search_tick", None) == b.tick


def test_enemy_sanity_burst_paralysis_preserves_search_target():
    """The burst-effect rewrite (enemy paralysis) must not disturb the
    3-tick target cache: a controlled enemy keeps its locked target."""
    sim, b = _battle()
    op = _deploy(b, "char_149_scave", 3, 3)
    sim.run_ticks(30)
    e = _spawn(b, 3, 4)
    from ark_emulator.ai import _start_normal_attack
    _start_normal_attack(e, b, 1.0)
    assert e._ai_target is op
    b.add_ep(e, 0, 2000.0)                # SANITY burst -> paralysis
    assert e.flag(39)
    assert getattr(e, "_ai_target", None) is op, \
        "burst control keeps the cached search target"


def _skill_enemy(b, row, col):
    over = {"attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0,
                           "rangeRadius": 4.0},
            "row": row, "col": col}
    b.spawn_enemy("enemy_1571_mirbst", 0, overrides=over)
    return b.enemies[-1]


def test_enemy_skill_target_search_respects_gate():
    """Enemy skill target selectors run under the same 3-logic-tick gate
    as normal attacks: a higher-priority operator that appears inside the
    window does not steal the cached skill target; after the boundary the
    next search picks it up."""
    sim, b = _battle()
    far = _deploy(b, "char_149_scave", 3, 3)
    near = _deploy(b, "char_1040_blaze2", 2, 4)
    sim.run_ticks(20)
    e = _skill_enemy(b, 3, 5)
    sc = e.skill_controller
    skill = next(s for s in sc.skills if s.prefab_key == "ThrowStone")
    first = sc._find_target(skill)
    assert first is near, "nearest operator locked by the first search"
    # teleport the enemy next to `far` inside the 3-tick window: the cached
    # target is kept, a fresh search only happens at the next boundary
    e.pos_x, e.pos_y = 3.0, 3.0
    assert sc._find_target(skill) is near, \
        "skill keeps the cached target within 3 ticks"
    for _ in range(3):
        b.tick_once()
    assert sc._find_target(skill) is far, \
        "new search boundary switches the skill target"


def test_enemy_skill_force_rescans_when_cached_target_invalid():
    """A dead cached target forces the skill search to re-run immediately
    (Search(force)), even inside the 3-tick window."""
    sim, b = _battle()
    far = _deploy(b, "char_149_scave", 3, 3)
    near = _deploy(b, "char_1040_blaze2", 2, 4)
    sim.run_ticks(20)
    e = _skill_enemy(b, 3, 5)
    sc = e.skill_controller
    skill = next(s for s in sc.skills if s.prefab_key == "ThrowStone")
    assert sc._find_target(skill) is near
    near.dead = True
    assert sc._find_target(skill) is far, \
        "invalid cached target force-rescans immediately"


def test_enemy_skill_blocked_target_bypasses_gate():
    """The blocked-target fast path stays ungated: a newly blocking
    operator takes over the skill target inside the search window."""
    sim, b = _battle()
    blocker = _deploy(b, "char_149_scave", 3, 3)
    other = _deploy(b, "char_1040_blaze2", 2, 4)
    sim.run_ticks(20)
    e = _skill_enemy(b, 3, 5)
    sc = e.skill_controller
    skill = next(s for s in sc.skills if s.prefab_key == "ThrowStone")
    assert sc._find_target(skill) is other
    e.blocked_by = blocker          # inside the 3-tick window
    assert sc._find_target(skill) is blocker, \
        "blocked enemy skills always target the blocker"


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
