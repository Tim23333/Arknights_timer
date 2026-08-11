"""酒神 S3 (skchr_phatm2_3 空剧场) end-to-end tests.

Covers the expanded range, the per-second sanity DoT mark applied to enemies
酒神 deals sanity damage to, the mad-cage detect buff on all enemies in
range (+50% EP burst cooldown recovery), the burst-triggered cage spawn,
prefer-unburst targeting, and cleanup when the skill ends.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState
from ark_emulator.targeting import HateSystem


def _battle():
    squad = [{"charId": "char_1042_phatm2", "phase": 2, "level": 50,
              "skillIndex": 2, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _spawn(b, row, col, key="enemy_1000_gopro_2"):
    b.spawn_enemy(key, 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def test_phatm2_s3_range_detect_and_cooldown_speed():
    sim, b = _battle()
    ok, pid = b.deploy("char_1042_phatm2", 2, 3)
    assert ok, pid
    op = b.operators[0]
    base_range = len(op.range_shape)
    op.sp = op.sp_max
    ok, _ = b.activate_skill(op.inst_id, 2)
    assert ok
    assert len(op.range_shape) > base_range, "S3 must expand the range"
    e = _spawn(b, 2, 4)
    sim.run_ticks(20)
    assert b.buffs.get(e, "phatm2_s_3[token]"), "detect buff must be applied"
    # burst cooldown ticks 1.5x faster while the detect buff is active
    b.add_buff(e, {"key": "ep_burst_cd_0", "remaining_ticks": 300,
                   "layers": 1, "source": None})
    cd = b.buffs.get(e, "ep_burst_cd_0")
    t0 = cd["remaining_ticks"]
    sim.run_ticks(10)
    assert abs((t0 - cd["remaining_ticks"]) - 15.0) < 1e-9, \
        (t0, cd["remaining_ticks"])


def test_phatm2_s3_sanity_mark_dot_and_cage():
    sim, b = _battle()
    ok, pid = b.deploy("char_1042_phatm2", 2, 3)
    assert ok, pid
    op = b.operators[0]
    op.sp = op.sp_max
    b.activate_skill(op.inst_id, 2)
    e = _spawn(b, 3, 4)          # ground tile: cage can only spawn on lowland
    sim.run_ticks(20)
    # 酒神 deals sanity element damage -> per-second DoT mark
    b.add_ep(e, 0, op.attributes.get("atk") * 0.2, source=op)
    mark = b.buffs.get(e, "phatm2_s_3[trigger]")
    assert mark, [x.get("key") for x in e.buffs]
    ep0 = [x for x in e.buffs if x.get("key") == "ep_neural"]
    v0 = ep0[-1]["value"] if ep0 else 0.0
    sim.run_ticks(31)      # >= 1s: one DoT tick (atk * 0.1 sanity EP)
    ep1 = [x for x in e.buffs if x.get("key") == "ep_neural"]
    v1 = ep1[-1]["value"] if ep1 else 0.0
    # DoT contributes atk*0.1/s; ??'s talent-1 attack EP (+atk*0.3) and
    # talent-2 (\u5760\u68a6: enemies in her range take 70 sanity EP on a
    # normal attack, +70) may each add one attack within the window
    atk = op.attributes.get("atk")
    # full-bar model: value = remaining, damage delta = v0 - v1
    assert atk * 0.1 - 1.0 <= (v0 - v1) <= atk * 0.4 + 70.0 + 1.0, \
        (v0, v1, atk)
    # push EP over the threshold -> burst -> cage on the enemy tile
    b.add_ep(e, 0, 1000.0, source=op)
    cages = [t for t in b.tokens
             if t.token_id == "token_10055_phatm2_mndclv"]
    assert len(cages) == 1 and (cages[0].row, cages[0].col) == (3, 4)


def test_phatm2_s3_prefer_unburst_targeting():
    sim, b = _battle()
    ok, pid = b.deploy("char_1042_phatm2", 2, 3)
    assert ok, pid
    op = b.operators[0]
    op.sp = op.sp_max
    b.activate_skill(op.inst_id, 2)
    e1 = _spawn(b, 2, 4)
    e2 = _spawn(b, 3, 4)
    b.add_buff(e1, {"key": "ep_burst_cd_0", "remaining_ticks": 600,
                    "layers": 1, "source": None})
    sim.run_ticks(20)
    tgt = HateSystem(b).operator_target(op, candidates=[e1, e2])
    assert tgt is e2, "must prefer the enemy not in burst recovery"


def test_phatm2_s3_cleanup_on_expire():
    # no-wave custom level; verify cleanup by force-ending the skill
    from ark_emulator.custom_levels import build_level
    lv = build_level(rows=6, cols=10, route_row=3, enemies=[])
    lv["waveTimeline"] = []
    cols = lv["map"]["cols"]
    for c in range(cols):
        t = lv["map"]["tiles"][2 * cols + c]
        t["buildableType"] = 2
        t["heightType"] = 2
    sim = Simulator(level_id="custom", custom_level=lv)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    ok, pid = b.deploy("char_1042_phatm2", 2, 3)
    assert ok, pid
    op = b.operators[0]
    op.sp = op.sp_max
    b.activate_skill(op.inst_id, 2)
    e = _spawn(b, 3, 4, key="enemy_1000_gopro")   # no summon-adds
    e.state = EnemyState.REACH_EXIT
    sim.run_ticks(20)
    assert b.buffs.get(e, "phatm2_s_3[token]")
    sc = op.skill_controller
    sc.active.remaining = 0.01     # force the skill to expire
    sim.run_ticks(3)
    assert sc.active is None, "skill must expire"
    assert not b.buffs.get(e, "phatm2_s_3[token]"), \
        "detect buff must be removed when the skill ends"
    assert not getattr(op, "prefer_unburst", False)


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
