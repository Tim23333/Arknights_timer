"""Attribute steal mechanics (StealAttributeAbility, dump.cs:543106).

Covers the generic engine (per-cast amount, target floor, source budget)
and the operator skills wired through it: 伊内丝 S2 / 薇薇安娜 S2
(attack@steal_atk_speed), 寻澜 S2 洞悉 (def_steal), 新约能天使 S2
(cast-time ally attack-speed steal).  Stolen buffs are reclaimed on skill
end and on the source's retreat/death.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle(squad):
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(300.0)
    return sim, b


def _deploy(b, cid, row, col):
    ok, pid = b.deploy(cid, row, col)
    assert ok, pid
    return next(o for o in b.operators if o.inst_id == pid)


def _spawn(b, row, col, **attrs):
    base = {"maxHp": 50000.0, "atk": 0.0, "def": 0.0, "attackSpeed": 300.0}
    base.update(attrs)
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": base, "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _activate(b, op, index=1):
    sc = op.skill_controller
    op.sp = sc.skills[index].sp_cost
    ok, _ = sc.activate(index)
    assert ok
    return sc.active


def _hit(b, op, enemy, interval=2.0):
    b._operator_attack(op, enemy, interval)
    pa = op._pending_attack
    assert pa is not None
    b._resolve_operator_attack(op, pa)


def test_ines_s2_steals_attack_speed_per_hit_capped():
    sim, b = _battle([{"charId": "char_4087_ines", "phase": 2,
                       "level": 50, "skillIndex": 1}])
    op = _deploy(b, "char_4087_ines", 3, 3)
    e = _spawn(b, 3, 4, attackSpeed=300.0)
    sim.run_ticks(30)
    act = _activate(b, op)
    assert act.skill.skill_id == "skchr_ines_2"
    as0 = op.attributes.get("attackSpeed")
    es0 = e.attributes.get("attackSpeed")
    for _ in range(5):                     # 5 hits x 4 = 20
        _hit(b, op, e)
    assert abs(e.attributes.get("attackSpeed") - (es0 - 20.0)) < 1e-6
    assert abs(op.attributes.get("attackSpeed") - (as0 + 20.0)) < 1e-6
    for _ in range(10):                    # capped at 40 total
        _hit(b, op, e)
    assert abs(e.attributes.get("attackSpeed") - (es0 - 40.0)) < 1e-6
    assert abs(op.attributes.get("attackSpeed") - (as0 + 40.0)) < 1e-6
    evs = [x for x in b.events.snapshot_events() if x["type"] == "steal"]
    assert evs and abs(evs[-1]["data"]["total"] - 40.0) < 1e-9


def test_surfer_s2_steals_def_per_hit_capped():
    sim, b = _battle([{"charId": "char_4052_surfer", "phase": 2,
                       "level": 50, "skillIndex": 1}])
    op = _deploy(b, "char_4052_surfer", 3, 3)
    e = _spawn(b, 3, 4, **{"def": 300.0})
    sim.run_ticks(30)
    act = _activate(b, op)
    assert act.skill.skill_id == "skchr_surfer_2"
    d0 = op.attributes.get("def")
    ed0 = e.attributes.get("def")
    for _ in range(3):                     # 3 hits x 10 = 30
        _hit(b, op, e)
    assert abs(e.attributes.get("def") - (ed0 - 30.0)) < 1e-6
    assert abs(op.attributes.get("def") - (d0 + 30.0)) < 1e-6
    for _ in range(10):                    # capped at 100
        _hit(b, op, e)
    assert abs(e.attributes.get("def") - (ed0 - 100.0)) < 1e-6
    assert abs(op.attributes.get("def") - (d0 + 100.0)) < 1e-6


def test_vvana_s2_steals_20_once():
    sim, b = _battle([{"charId": "char_4098_vvana", "phase": 2,
                       "level": 50, "skillIndex": 1}])
    op = _deploy(b, "char_4098_vvana", 3, 3)
    e = _spawn(b, 3, 4, attackSpeed=300.0)
    sim.run_ticks(30)
    act = _activate(b, op)
    assert act.skill.skill_id == "skchr_vvana_2"
    as0 = op.attributes.get("attackSpeed")
    es0 = e.attributes.get("attackSpeed")
    _hit(b, op, e)
    assert abs(e.attributes.get("attackSpeed") - (es0 - 20.0)) < 1e-6
    assert abs(op.attributes.get("attackSpeed") - (as0 + 20.0)) < 1e-6
    _hit(b, op, e)                         # already capped at 20
    assert abs(e.attributes.get("attackSpeed") - (es0 - 20.0)) < 1e-6


def test_angel2_s2_steals_ally_aspeed_and_reverts_on_skill_end():
    sim, b = _battle([
        {"charId": "char_149_scave", "phase": 2, "level": 50,
         "skillIndex": 0},
        {"charId": "char_1041_angel2", "phase": 2, "level": 50,
         "skillIndex": 1}])
    ally = _deploy(b, "char_149_scave", 3, 3)
    op = _deploy(b, "char_1041_angel2", 2, 3)   # ranged, ally in range
    sim.run_ticks(30)
    a0 = ally.attributes.get("attackSpeed")
    o0 = op.attributes.get("attackSpeed")
    act = _activate(b, op)
    assert act.skill.skill_id == "skchr_angel2_2"
    assert abs(ally.attributes.get("attackSpeed") - (a0 - 70.0)) < 1e-6
    assert abs(op.attributes.get("attackSpeed") - (o0 + 70.0)) < 1e-6
    # skill ends -> stolen ASPD returns
    act.on_expire()
    assert abs(ally.attributes.get("attackSpeed") - a0) < 1e-6
    assert abs(op.attributes.get("attackSpeed") - o0) < 1e-6


def test_retreat_clears_stolen_buffs():
    sim, b = _battle([{"charId": "char_4087_ines", "phase": 2,
                       "level": 50, "skillIndex": 1}])
    op = _deploy(b, "char_4087_ines", 3, 3)
    e = _spawn(b, 3, 4, attackSpeed=300.0)
    sim.run_ticks(30)
    _activate(b, op)
    es0 = e.attributes.get("attackSpeed")
    _hit(b, op, e)
    assert abs(e.attributes.get("attackSpeed") - (es0 - 4.0)) < 1e-9
    b.withdraw(op.inst_id)
    assert abs(e.attributes.get("attackSpeed") - es0) < 1e-9, \
        "retreat returns the stolen attribute"
    assert not [x for x in e.buffs if str(x.get("key", "")).startswith("steal[")]


def test_steal_attribute_engine_floor_and_budget():
    sim, b = _battle([{"charId": "char_149_scave", "phase": 2,
                       "level": 50, "skillIndex": 0}])
    op = _deploy(b, "char_149_scave", 3, 3)
    e = _spawn(b, 3, 4, **{"def": 5.0})
    # target floor at 1: only 4 can be stolen
    got = b.steal_attribute(op, e, "def", 10.0, max_total=100.0, key="t")
    assert abs(got - 4.0) < 1e-9, got
    assert abs(e.attributes.get("def") - 1.0) < 1e-9
    # budget exhausted: second steal returns 0
    got2 = b.steal_attribute(op, e, "def", 10.0, max_total=4.0, key="t")
    assert abs(got2) < 1e-9
    # dead target steals nothing
    e.hp = 0.0
    e.dead = True
    assert b.steal_attribute(op, e, "def", 10.0, key="t2") == 0.0


def test_mlvss_wtrman_token_steals_atk_def_per_hit():
    """缪尔赛思流形 token talent: 近战每次攻击偷取 10 攻/10 防（各上限 250）。
    The token is deployable through the gained-token inventory."""
    sim, b = _battle([])
    b._gained_tokens["token_10030_mlyss_wtrman"] = 1
    ok, res = b.deploy_gained_token("token_10030_mlyss_wtrman", 3, 4)
    assert ok, res
    tok = b.tokens[-1]
    assert tok.token_steal_bb.get("steal_atk") == 10.0
    assert tok.token_steal_bb.get("steal_def") == 10.0
    e = _spawn(b, 3, 5, **{"atk": 300.0, "def": 300.0})
    a0, d0 = tok.attributes.get("atk"), tok.attributes.get("def")
    ea0, ed0 = e.attributes.get("atk"), e.attributes.get("def")
    for _ in range(3):
        b._token_attack(tok, e)
        pa = tok._pending_attack
        assert pa is not None
        b._resolve_operator_attack(tok, pa)
    assert abs(e.attributes.get("atk") - (ea0 - 30.0)) < 1e-6
    assert abs(e.attributes.get("def") - (ed0 - 30.0)) < 1e-6
    assert abs(tok.attributes.get("atk") - (a0 + 30.0)) < 1e-6
    assert abs(tok.attributes.get("def") - (d0 + 30.0)) < 1e-6


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
