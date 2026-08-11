# -*- coding: utf-8 -*-
"""Extra node handlers: ApplyFixedElementDamage / converter gate /
LegionModeOnlyAssignCardCntToBB (the last unhandled nodes in playable
content: sandbox1_19 + act34side_07)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(200.0)
    return sim, b


def _enemy(b, row=3, col=4):
    return b.spawn_enemy_directive("enemy_1000_gopro_2", row, col,
                                   route_index=0)


def test_apply_fixed_element_damage():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b)
    ctx = {"bb": {"ep_damage_fixed": 200}, "source": e, "target": e}
    ok = eng._n_ApplyFixedElementDamage(
        e, {"$type": "ApplyFixedElementDamage", "_elementType": "FIRE",
            "_sourceType": "BUFF_SOURCE", "_targetType": "BUFF_OWNER",
            "_damageValueKey": "ep_damage_fixed", "_damageScaleKey": None,
            "_allowNoSourceDamage": True, "_isEnvDamage": True}, ctx)
    assert ok is True
    from ark_emulator.targeting import _unit_ep
    ep = _unit_ep(e, b)
    assert abs(ep.get("ep_fire", 0.0) - 200.0) < 1.0, ep
    # scale key multiplies
    e2 = _enemy(b, 3, 6)
    ctx = {"bb": {"cached_atk": 100, "ep_damage_ratio_token": 0.5},
           "source": e2, "target": e2}
    ok = eng._n_ApplyFixedElementDamage(
        e2, {"$type": "ApplyFixedElementDamage", "_elementType": "SANITY",
             "_sourceType": "BUFF_SOURCE", "_targetType": "BUFF_OWNER",
             "_damageValueKey": "cached_atk",
             "_damageScaleKey": "ep_damage_ratio_token",
             "_allowNoSourceDamage": True, "_isEnvDamage": False}, ctx)
    assert ok is True
    ep = _unit_ep(e2, b)
    assert abs(ep.get("ep_neural", 0.0) - 50.0) < 1.0, ep


def test_check_buff_attribute_modifier_changed():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    e = _enemy(b)
    e.attributes.base["atk"] = 100.0
    entry = {"key": "test_conv", "stat": "atk", "final_add": 0.0}
    ctx = {"bb": {"_buff_entry": entry}, "source": e, "target": e}
    node = {"$type": "CheckBuffAttributeModifierChanged",
            "_sourceType": "BUFF_SOURCE", "_sourceAttributeType": "ATK",
            "_buffAttributeType": "ATK", "_formulaType": "FINAL_ADDITION",
            "_useFirstDerivedBuff": True}
    assert eng._n_CheckBuffAttributeModifierChanged(e, node, ctx) is True, \
        "first check reports changed"
    assert eng._n_CheckBuffAttributeModifierChanged(e, node, ctx) is False, \
        "unchanged attribute reports False"
    assert entry["final_add"] == 100.0
    e.attributes.base["atk"] = 150.0
    assert eng._n_CheckBuffAttributeModifierChanged(e, node, ctx) is True
    assert entry["final_add"] == 150.0


def test_legion_mode_assign_card_cnt_to_bb():
    sim, b = _battle()
    from ark_emulator.buff_templates import BuffTemplateEngine
    eng = BuffTemplateEngine(b)
    b._legion_hand = ["trap_755_cdsoul", "trap_999_other"]
    ctx = {"bb": {}, "source": None, "target": None}
    ok = eng._n_LegionModeOnlyAssignCardCntToBB(
        None, {"$type": "LegionModeOnlyAssignCardCntToBB",
               "_cardKey": "cdsoul_cnt", "_cardId": "trap_755_cdsoul",
               "_onlyInHand": True, "_cardLibraryType": "USING"}, ctx)
    assert ok is True
    assert ctx["bb"].get("cdsoul_cnt") == 1


def test_special_levels_no_unhandled():
    """sandbox1_19 + act34side_07 must not hit unhandled nodes."""
    from ark_emulator import Simulator as S
    for lid in ("level_sandbox1_19", "level_act34side_07"):
        sim = S(level_id=lid)
        b = sim.battle
        sim.run_ticks(900)
        un = [x for x in b.events.snapshot_events()
              if x["type"] == "buff_node_unhandled"]
        assert not un, (lid, [x["data"] for x in un])


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
