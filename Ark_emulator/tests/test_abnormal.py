# -*- coding: utf-8 -*-
"""Abnormal state behaviours: DISARMED / DOZE / FEARED / INVISIBLE."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState
from ark_emulator.targeting import HateSystem


def _setup():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.battle_cost_add(200)
    b.deploy("char_149_scave", 3, 3)
    return sim, b


def test_disarmed_blocks_normal_attack():
    sim, b = _setup()
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e = b.enemies[0]
    e.row, e.col = op.row, op.col + 1
    e.pos_x, e.pos_y = float(e.col), float(e.row)
    e.state = EnemyState.MOVE
    for _ in range(10):
        b.tick_once()
    hp0 = op.hp
    e.set_flag(11, 60)
    for _ in range(30):
        b.tick_once()
    assert abs((hp0 - op.hp)) < 0.5, hp0 - op.hp


def test_doze_stops_and_wakes():
    sim, b = _setup()
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e = b.enemies[-1]
    e.pos_x, e.pos_y = 3.0, 5.0
    e.row, e.col = 5, 3
    e.state = EnemyState.MOVE
    e.set_flag(43, 300)
    pos0 = (e.pos_x, e.pos_y)
    for _ in range(30):
        b.tick_once()
    assert (e.pos_x, e.pos_y) == pos0, "doze enemy must not move"
    b.apply_damage(e, 10, 0, source=op)
    assert not e.flag(43), "damage should wake the sleeper"


def test_feared_flees_toward_spawn():
    sim, b = _setup()
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e = b.enemies[-1]
    start = b.routes[0].get("startPosition") or {"row": 0, "col": 0}
    e.pos_x, e.pos_y = 5.0, 3.0
    e.row, e.col = 3, 5
    e.state = EnemyState.MOVE
    e.set_flag(33, 300)
    before = ((e.pos_x - start.get("col", 0)) ** 2 +
              (e.pos_y - start.get("row", 0)) ** 2) ** 0.5
    for _ in range(60):
        b.tick_once()
    after = ((e.pos_x - start.get("col", 0)) ** 2 +
             (e.pos_y - start.get("row", 0)) ** 2) ** 0.5
    assert after < before - 0.5, (before, after)


def test_invisible_ranged_exclusion():
    sim, b = _setup()
    op = b.operators[0]
    b.spawn_enemy("enemy_1007_slime_2", 0)
    e = b.enemies[0]
    e.pos_x, e.pos_y = 3.0, 3.0
    e.row, e.col = 3, 3
    h = HateSystem(b)
    for _ in range(30):
        b.tick_once()
    op.set_flag(9, 300)
    # melee may still target/block an invisible unit
    t_melee = h.enemy_target(e, range_radius=None, require_in_range=False)
    assert t_melee is op
    # ranged attackers cannot see it
    t_ranged = h.enemy_target(e, range_radius=5.0, require_in_range=True)
    assert t_ranged is None
    op.clear_flag(9)
    t2 = h.enemy_target(e, range_radius=5.0, require_in_range=True)
    assert t2 is op


def test_attracted_moves_toward_source():
    sim, b = _setup()
    op = b.operators[0]
    b.spawn_enemy("enemy_1000_gopro_2", 0)
    e = b.enemies[-1]
    e.pos_x, e.pos_y = 6.0, 3.0
    e.row, e.col = 3, 6
    e.state = EnemyState.MOVE
    b.add_abnormal(e, 41, 5.0, source=op)
    before = abs(e.pos_x - op.pos_x)
    for _ in range(60):
        b.tick_once()
    after = abs(e.pos_x - op.pos_x)
    assert after < before - 0.5, (before, after)


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
    print("all abnormal tests passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)



def _stun_battle(char_id="char_172_svrash", row=3, col=3):
    from ark_emulator import Simulator
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy(char_id, row, col)
    op = b.operators[-1]
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0},
        "row": row, "col": col + 1})
    b.enemies[-1].state = EnemyState.COMBAT
    return sim, b, op


def test_stunned_operator_stops_attacking():
    """A stunned operator cannot attack; after the stun ends normal
    attacking resumes."""
    from ark_emulator.consts import DamageType
    sim, b, op = _stun_battle()
    b.add_abnormal(op, 0, 3.0)
    dmg_in = 0
    for _ in range(120):
        b.tick_once()
        if b.tick <= 115:
            for ev in b.events.snapshot_events():
                if ev["type"] == "damage" and \
                        ev["data"].get("source") == op.inst_id:
                    dmg_in += 1
        b.events.log = []
    assert dmg_in == 0, dmg_in
    dmg_after = 0
    for _ in range(120):
        b.tick_once()
        for ev in b.events.snapshot_events():
            if ev["type"] == "damage" and \
                    ev["data"].get("source") == op.inst_id:
                dmg_after += 1
        b.events.log = []
    assert dmg_after > 0, "attack must resume after stun"


def test_sustained_skill_pauses_output_not_timer():
    """A sustained skill's timer keeps running while the operator is
    stunned, but no skill damage is dealt during the stun."""
    sim, b, op = _stun_battle()
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    rem0 = sc.active.remaining
    b.add_abnormal(op, 0, 3.0)
    dmg = 0
    for _ in range(120):
        b.tick_once()
        if b.tick <= 115:
            for ev in b.events.snapshot_events():
                if ev["type"] == "damage" and \
                        ev["data"].get("source") == op.inst_id:
                    dmg += 1
        b.events.log = []
    assert dmg == 0, dmg
    # timer elapsed ~4s (not paused by the stun)
    rem = sc.active.remaining if sc.active else 0.0
    assert abs(rem - (rem0 - 4.0)) < 0.3, (rem0, rem)



def test_buff_provided_abnormal_immunity():
    """abnormalImmunes carried by a buff prevent the named abnormal flags
    (stun/freeze), while other flags still apply."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    b.add_buff(e, {"key": "test_immune", "remaining_ticks": 1000,
                   "layers": 1,
                   "abnormalImmunes": ["STUNNED", "FROZEN"]})
    assert b.add_abnormal(e, 0, 3.0) is False     # stun immune
    assert not e.flag(0)
    assert b.add_abnormal(e, 16, 3.0) is False    # freeze immune
    assert not e.flag(16)
    assert b.add_abnormal(e, 12, 3.0) is True     # silence still applies
    assert e.flag(12)


def test_numeric_abnormal_immunity():
    from ark_emulator import Simulator
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[-1]
    b.add_buff(e, {"key": "t2", "remaining_ticks": 1000, "layers": 1,
                   "abnormalImmunes": [0]})
    assert b.add_abnormal(e, 0, 2.0) is False
    assert not e.flag(0)



def test_element_burst_respects_abnormal_immunity():
    """Enemy-side SANITY burst grants 3 layers of paralysis (15s total,
    PRTS: 麻痹每5秒流失1层) unless the unit is palsy-immune; the 6000
    element damage lands on the bursting enemy whose EP is locked, so it
    deals no HP damage."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 2, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    b.add_buff(e, {"key": "palsy_immune", "remaining_ticks": 1000,
                   "layers": 1, "abnormalImmunes": ["PALSY"]})
    hp0 = e.hp
    b.add_ep(e, 0, 2000.0)
    assert not e.flag(39), "paralysis must be skipped by immunity"
    assert abs(hp0 - e.hp) < 1e-9, \
        "locked EP makes the 6000 element damage a no-op"
    # non-immune control group still gets paralysed (3 layers, 15s)
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e2 = b.enemies[-1]
    e2.state = EnemyState.COMBAT
    b.add_ep(e2, 0, 2000.0)
    assert e2.flag(39), "enemy SANITY burst must paralyse (3 layers)"
    rec = e2.abnormal.get(39)
    assert rec is not None and rec["layers"] == 3
    assert abs(rec["ticks"] - 15 * 30) < 2, rec["ticks"]



def test_abnormal_state_priority_and_sequential_expiry():
    """With stun+freeze together the enemy state follows STUN (higher
    priority); when the stun expires first it falls to FROZEN, and after
    the freeze expires it returns to the pre-abnormal COMBAT state."""
    from ark_emulator import Simulator
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 2, "col": 5})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    b.add_abnormal(e, 0, 2.0)       # stun 60 ticks
    b.add_abnormal(e, 16, 3.0)      # freeze 90 ticks
    got = []
    for _ in range(150):
        b.tick_once()
        if b.tick in (20, 70, 100, 140):
            got.append((b.tick, e.state, e.flag(0), e.flag(16)))
    by_tick = {t: s for t, s, _, _ in got}
    assert by_tick[20] == EnemyState.STUN, by_tick[20]      # stun wins
    assert by_tick[70] == EnemyState.FROZEN, by_tick[70]    # stun ended
    assert by_tick[100] == EnemyState.COMBAT, by_tick[100]  # both ended
    assert by_tick[140] == EnemyState.COMBAT
