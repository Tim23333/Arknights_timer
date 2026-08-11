# -*- coding: utf-8 -*-
"""Continuous-skill timing: buff stats stay for the full duration window
and are removed exactly at expiry (volcano 15s, double-chant 25s)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(10)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_180_amgoat", 2, 3)
    return sim, b, b.operators[-1]


def test_volcano_15s_window():
    sim, b, op = _battle()
    sc = op.skill_controller
    atk0 = float(op.attributes.get("atk"))
    int0 = op.attributes.attack_interval()
    op.sp = sc.skills[2].sp_cost
    sc.activate(2)
    start = b.tick
    assert abs(op.attributes.get("atk") - atk0 * 1.55) < 0.5
    # hold through the 15s window (450 ticks)
    for _ in range(449):
        b.tick_once()
    assert abs(op.attributes.get("atk") - atk0 * 1.55) < 0.5
    assert abs(op.attributes.attack_interval() - max(0.05, int0 - 1.1)) \
        < 0.01
    # expiry restores the base stats
    for _ in range(15):
        b.tick_once()
    assert abs(op.attributes.get("atk") - atk0) < 0.5, \
        op.attributes.get("atk")
    assert abs(op.attributes.attack_interval() - int0) < 0.01
    assert sc.active is None


def test_double_chant_25s_window():
    sim, b, op = _battle()
    sc = op.skill_controller
    atk0 = float(op.attributes.get("atk"))
    aspd0 = float(op.attributes.get("attackSpeed"))
    op.sp = sc.skills[0].sp_cost
    sc.activate(0)
    assert abs(op.attributes.get("atk") - atk0 * 1.3) < 0.5
    for _ in range(700):              # hold ~23s
        b.tick_once()
    assert abs(op.attributes.get("atk") - atk0 * 1.3) < 0.5
    assert abs(float(op.attributes.get("attackSpeed")) - 130.0) < 1e-9
    for _ in range(60):               # past 25s
        b.tick_once()
    assert abs(op.attributes.get("atk") - atk0) < 0.5
    assert abs(float(op.attributes.get("attackSpeed")) - aspd0) < 1e-9
    assert sc.active is None



def test_tinman_s1_dot_tick_timing():
    """Tinman S1 alchemy zone: the tinman_s_1[dot] buff ticks every 1s
    (30 ticks) with cached_atk = atk x 0.3, and the zone expires after
    projectile_delay_time (8s)."""
    from ark_emulator.consts import EnemyState
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.deploy("char_4151_tinman", 2, 3)
    op = b.operators[0]
    sc = op.skill_controller
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 500000.0, "atk": 0.0, "def": 0.0,
                       "magicResistance": 0.0},
        "row": 2, "col": 5})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    op.sp = sc.skills[0].sp_cost
    sc.activate(0)
    sc.skills[0].sp_cost = 9999.0       # block auto re-cast of S1
    for _ in range(40):
        b.tick_once()
    dot = next((x for x in e.buffs if x.get("key") == "tinman_s_1[dot]"),
               None)
    assert dot is not None, "zone DoT buff must land on the enemy"
    assert dot.get("_trigger_interval") == 30, dot.get("_trigger_interval")
    atk = float(op.attributes.get("atk"))
    cached = (dot.get("blackboard") or {}).get("cached_atk")
    assert abs(float(cached) - atk * 0.3) < 0.01, cached
    # zone lifetime = projectile_delay_time 8s (240 ticks from hit); the
    # projectile flight already consumed some ticks before our check
    start_remaining = dot.get("remaining_ticks")
    assert 180 <= start_remaining <= 240, start_remaining
    b.events.log = []
    for _ in range(90):          # 3s -> 3 ticks of the dot
        b.tick_once()
    dot_dmg = [x for x in b.events.snapshot_events()
               if x["type"] == "damage" and
               x["data"].get("target") == e.inst_id and
               abs(x["data"].get("amount", 0.0) - float(cached)) < 0.5]
    assert len(dot_dmg) >= 2, len(dot_dmg)
    # run out the rest of the zone: buff must be removed once 8s elapses
    for _ in range(200):
        b.tick_once()
    assert not any(x.get("key") == "tinman_s_1[dot]"
                   for x in e.buffs), \
        [x.get("key") for x in e.buffs if "tinman" in str(x.get("key"))]
