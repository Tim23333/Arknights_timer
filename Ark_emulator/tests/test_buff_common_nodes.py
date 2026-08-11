"""Generic buff-template nodes: HealToken / CopyHealth / UnlockHiddenArea."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 1000.0
    b.cost_increase_time = 1e7
    for (r, c) in [(3, 3), (2, 3), (3, 2), (1, 3)]:
        ok = b.deploy("char_452_bstalk", r, c)
        if ok[0]:
            break
    op = b.operators[0]
    ok, pid = b.spawn_token_forced("token_10014_bstalk_crab", 3, 4,
                                   owner=op)
    assert ok, pid
    crab = [t for t in b.tokens if not t.dead][-1]
    return sim, b, op, crab


def _run(b, node, owner, source=None, target=None, bb=None):
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    handler = getattr(eng, "_n_" + node.split("+")[-1].split(",")[0])
    return handler(owner, {"$type": node,
                           "_healByRatio": True,
                           **({"ignore_heal_free": True}
                              if "Heal" in node else {})},
                   {"bb": bb or {}, "source": source, "target": target,
                    "owner": owner})


def test_heal_token():
    sim, b, op, crab = _battle()
    crab.hp = crab.max_hp * 0.5
    hp0 = crab.hp
    _run(b, "Torappu.Battle.Action.Nodes+HealToken",
         op, bb={"hp_ratio": 0.2})
    healed = crab.hp - hp0
    assert abs(healed - crab.max_hp * 0.2) < 0.5, healed
    print("OK HealToken", round(healed, 1))


def test_copy_health():
    sim, b, op, crab = _battle()
    op.hp = op.max_hp * 0.3
    _run(b, "Torappu.Battle.Action.Nodes+CopyHealth",
         op, source=op, target=crab,
         bb={})
    # 用显式 source/target 类型（测试直接传 target=crab）
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    eng._n_CopyHealth(op, {"$type":
                           "Torappu.Battle.Action.Nodes+CopyHealth",
                           "_sourceType": "BUFF_SOURCE",
                           "_targetType": "TARGET"},
                      {"bb": {}, "source": op, "target": crab,
                       "owner": op})
    assert abs(crab.hp - op.hp) < 0.01, (crab.hp, op.hp)
    print("OK CopyHealth", crab.hp)


def test_unlock_hidden_area():
    sim, b, op, crab = _battle()
    b._fog_view = {(2, 3): False}
    _run(b, "Torappu.Battle.Action.Nodes+UnlockHiddenArea", op)
    assert b._fog_view == {}
    print("OK UnlockHiddenArea")


def _eng(b):
    from ark_emulator.buff_templates import BuffTemplateEngine
    return BuffTemplateEngine(b)


def test_main15_speed_and_prts():
    sim, b, op, crab = _battle()
    eng = _eng(b)
    eng._n_Main15ForceSetBattleSpeedLevel(
        op, {"$type": "Main15ForceSetBattleSpeedLevel",
             "_enable": True}, {"bb": {}})
    assert b._main15_force_speed is True
    eng._n_Main15InsertPrtsAction(
        op, {"$type": "Main15InsertPrtsAction",
             "_actionType": "MOVE_AND_SPAWNENEMY", "_priority": 110},
        {"bb": {}})
    assert any(x["type"] == "main15_insert_prts"
               for x in b.events.snapshot_events())
    print("OK Main15 speed + PRTS")


def test_main16_shadow():
    sim, b, op, crab = _battle()
    eng = _eng(b)
    eng._n_Main16ChangeTileShadowViaRange(
        op, {"$type": "Main16ChangeTileShadowViaRange",
             "_beginPosition": {"row": 0, "col": 0},
             "_endPosition": {"row": 2, "col": 2}}, {"bb": {}})
    assert (1, 1) in b._main16_shadow
    assert (3, 3) not in b._main16_shadow
    crab.row, crab.col = 1, 1
    ok = eng._n_Main16CheckTargetInShadowStateTile(
        op, {"$type": "Main16CheckTargetInShadowStateTile",
             "_target": "TARGET"}, {"bb": {}, "source": op, "target": crab})
    assert ok
    print("OK Main16 shadow")


def test_mainline17_click_counter():
    sim, b, op, crab = _battle()
    eng = _eng(b)
    eng._n_Mainline17CreateBossClickCounterButton(
        op, {"$type": "Mainline17CreateBossClickCounterButton",
             "_requiredClickCount": 15,
             "_successBuffKey": "enemy_musnake[click_success]"},
        {"bb": {}})
    assert b._main17_click_required == 15
    assert b._main17_click_success_buff == "enemy_musnake[click_success]"
    print("OK Mainline17 click counter")


if __name__ == "__main__":
    test_heal_token()
    test_copy_health()
    test_unlock_hidden_area()
    test_main15_speed_and_prts()
    test_main16_shadow()
    test_mainline17_click_counter()
