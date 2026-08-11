"""Periodic buff trigger precision tests.

Real BuffData carries triggerInterval (0.05~5s), firstTriggerInterval and
triggerCnt; the engine previously hardcoded a 1s fallback and ignored the
first-trigger delay / trigger cap. These tests verify the data-driven
interval is preserved and the timeline is exact.
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
    b.battle_cost_add(100.0)
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return sim, b, e


def test_trigger_interval_first_delay_and_cap():
    sim, b, e = _battle()
    fired = []
    orig_fire = b.buffs._fire

    def traced(unit, entry, event, **kw):
        if event == "ON_BUFF_TRIGGER" and \
                (entry or {}).get("key") == "test_periodic":
            fired.append(b.tick)
        return orig_fire(unit, entry, event, **kw)
    b.buffs._fire = traced

    b.add_buff(e, {
        "key": "test_periodic",
        "template_key": "cannon_t_1",   # template with ON_BUFF_TRIGGER
        "remaining_ticks": 300,
        "layers": 1,
        "_trigger_interval": 6,          # 0.2s
        "_first_trigger_interval": 15,   # 0.5s first-trigger delay
        "_trigger_max": 3,
        "wait_first_trigger": 1,
        "blackboard": {},
    })
    entry = b.buffs.get(e, "test_periodic")
    assert entry["_trigger_interval"] == 6
    assert entry["_first_trigger_remaining"] == 15
    assert entry["_trigger_max"] == 3

    for _ in range(60):
        b.tick_once()
    # buff applied at tick 15: 0.5s first delay (15 ticks) then 0.2s
    # interval (6 ticks). The first accumulator tick overlaps the delay-end
    # tick, so fires land at 34, 40, 46 and stop after the cap of 3.
    assert fired == [34, 40, 46], fired
    assert len(fired) == 3


def test_materialise_buff_carries_trigger_fields():
    from ark_emulator.buff_templates import materialise_buff
    sim, b, e = _battle()
    entry = materialise_buff(b, e, {
        "buffKey": "test_doT",
        "templateKey": "cannon_t_1",
        "lifeTimeType": 1,
        "lifeTime": 3.0,
        "maxStackCnt": 1,
        "triggerLifeType": 1,
        "triggerInterval": 0.1,
        "firstTriggerInterval": 0.3,
        "triggerCnt": 4,
        "waitFirstTriggerInterval": 1,
        "blackboard": [],
    }, {}, e)
    assert entry["_trigger_interval"] == 3, entry    # 0.1s * 30
    assert entry["_first_trigger_interval"] == 9, entry  # 0.3s * 30
    assert entry["_trigger_max"] == 4, entry
    # apply() must preserve them (not the 1s template fallback)
    b.add_buff(e, entry)
    stored = b.buffs.get(e, "test_doT")
    assert stored["_trigger_interval"] == 3, stored
    assert stored["_first_trigger_remaining"] == 9, stored
    assert stored["_trigger_max"] == 4, stored


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
