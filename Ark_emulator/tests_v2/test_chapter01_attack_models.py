"""New after M8 full suite: explicit profiles, no native-client claim."""
from copy import deepcopy
import json
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.build_chapter01_attack_models import build, fixture, IDS, OUT


def sim(key, **kwargs): return Engine.create(Compiler().compile(fixture(key, **kwargs)), seed=721)
def hp(s, alias="first"): return s.ctx.resources.current(alias, "hp")
def block(s, alias="first"): s.ctx.set("enemy", ("runtime", "blocked_by"), s.session.world.resolve(alias))
def damage(s): return [e for e in s.session.events if e["type"] == "damage.accepted"]
def launch(s): return [e for e in s.session.events if e["type"] == "projectile.launched"]


def test_frozen_artifact_and_source_guards_preserve_special_fields():
    d = build(); assert d == json.loads((OUT/"attacks.model.json").read_bytes())
    profiles = d["manifest"]["metadata"]["profiles"]
    p = profiles[IDS[0]]
    assert p["native_combat_fields"]["_splitDamage"] == 1 and p["native_combat_fields"]["_additionalTimes"] == 1
    assert p["split_profile"]["packet_scale"] == .5 and not p["split_profile"]["native_formula_body_recovered"]
    for key in IDS[1:]:
        p = profiles[key]; assert p["native_selector"]["raw"]["_postFilter"] == 4
        assert p["flight_profile"]["native_lifetime"] == 10 and p["model_gap"]
    assert not d["manifest"]["metadata"]["formal_stage_approved"]


def test_split_before_defense_has_two_145_packets_at_independent_source_ticks():
    s = sim(IDS[0]); block(s); s.advance(12); assert hp(s) == 2000
    s.advance(1); assert hp(s) == 1855
    s.advance(10); assert hp(s) == 1855
    s.advance(1); assert hp(s) == 1710
    assert [(e["time"], e["payload"]["amount"]) for e in damage(s)] == [(12, 145), (23, 145)]
    # Splitting post-DEF would instead produce160+160; this model explicitly does not.
    assert hp(s) != 1680


def test_multi_captures_blocker_and_does_not_refresh_after_first_hit():
    s = sim(IDS[0], positions={"first": {"row": 2, "col": 2}, "second": {"row": 2, "col": 2}})
    block(s); s.advance(13); block(s, "second"); s.advance(11)
    assert hp(s) == 1710 and hp(s, "second") == 2000
    assert not s.ctx.get("enemy", ("runtime", "casts"))


def test_unblocked_multi_cannot_select_arbitrary_player():
    s = sim(IDS[0]); s.advance(40); assert hp(s) == 2000 and not damage(s)


def test_multi_target_dies_after_packet_one_second_packet_does_not_hit_dead_or_other():
    s = sim(IDS[0], defender_hp=100, defender_def=0,
        positions={"first": {"row": 2, "col": 2}, "second": {"row": 2, "col": 2}})
    block(s); s.advance(13); assert not s.ctx.alive("first")
    s.advance(11)
    assert len(damage(s)) == 1 and hp(s, "second") == 100
    assert not s.ctx.get("enemy", ("runtime", "casts"))
    assert len([e for e in s.session.events if e["type"] == "combat.kill"]) == 1


def test_multi_source_death_cancels_unlaunched_second_packet():
    s = sim(IDS[0]); block(s); s.advance(13); s.ctx.lifecycle.retire("enemy", "dead"); s.advance(20)
    assert hp(s) == 1855 and len(damage(s)) == 1
    assert not s.ctx.get("enemy", ("runtime", "casts"))


def test_multi_attack_clock_charges_source_once_and_received_damage_clock_twice():
    d = fixture(IDS[0]); d["rules"].append({"id": "rule/probe_event", "kind": "calculation_rule", "contract": "resource.recovery",
        "implementation": {"type": "expression", "expression": "inputs.current + inputs.parameters.amount"}})
    enemy = next(e for e in d["entities"] if e["id"] == "unit/"+IDS[0]); player = d["entities"][-1]
    for e, event, role in [(enemy, "attack.accepted", "source"), (player, "damage.accepted", "target")]:
        e["components"]["resources"]["clock_probe"] = {"initial": 0, "capacity": 10, "recovery_rule": "rule/probe_event",
            "recovery": {"mode": "event", "event": event, "owner_role": role, "amount": 1}}
    s = Engine.create(Compiler().compile(d)); block(s); s.advance(24)
    assert s.ctx.resources.current("enemy", "clock_probe") == 1
    assert s.ctx.resources.current("first", "clock_probe") == 2
    assert [e["time"] for e in s.session.events if e["type"] == "attack.accepted"] == [12]


@pytest.mark.parametrize("key,expected", [(IDS[1], 1850), (IDS[2], 1780)])
def test_ranged_exact_launch22_distance_one_flight6_impact28(key, expected):
    s = sim(key); s.advance(22); assert not launch(s) and hp(s) == 2000
    s.advance(1); assert len(launch(s)) == 1 and launch(s)[0]["payload"]["flight_seconds"] == .2
    assert not s.ctx.get("enemy", ("runtime", "casts"))  # native waitForProjectileInvalid0
    s.advance(5); assert hp(s) == 2000
    s.advance(1); assert hp(s) == expected
    assert [e["time"] for e in damage(s)] == [28]


def test_ranged_priority_is_declared_newest_id_and_limits_one_ground_target():
    s = sim(IDS[1], positions={"near": {"row": 2, "col": 2.1}, "far_recent": {"row": 2, "col": 3}})
    s.advance(29)
    assert hp(s, "near") == 2000 and hp(s, "far_recent") == 1850
    assert len(damage(s)) == 1


def test_stage_melee_behavior_must_be_replaced_by_declared_ranged_override():
    d = fixture(IDS[1]); enemy = next(e for e in d["entities"] if e["id"] == "unit/"+IDS[1])
    enemy["components"]["behavior"] = {"machine": "behavior/ground_melee"}
    wrong = Engine.create(Compiler().compile(d)); wrong.advance(29)
    assert not damage(wrong) and hp(wrong) == 2000
    enemy["components"]["behavior"] = deepcopy(d["manifest"]["metadata"]["integration"]["behavior_overrides"][enemy["id"]])
    right = Engine.create(Compiler().compile(d)); right.advance(29)
    assert hp(right) == 1850 and right.ctx.get("enemy", ("runtime", "behavior_decision"))["attack"]


@pytest.mark.parametrize("distance,launches", [(1.75, 1), (1.7501, 0)])
def test_ranged_range_inclusive_boundary(distance, launches):
    s = sim(IDS[1], positions={"first": {"row": 2, "col": 2+distance}}); s.advance(34)
    assert len(launch(s)) == launches
    assert hp(s) == (1850 if launches else 2000)


def test_ranged_air_actor_excluded_even_if_more_recent():
    d = fixture(IDS[1], positions={"ground": {"row": 2, "col": 3}})
    air = deepcopy(d["entities"][-1]); air["id"] = "unit/air_probe"; air["tags"] = ["player", "air"]
    d["entities"].append(air)
    d["scenarioDraft"]["initialEntities"].append({"definition": air["id"], "instanceAlias": "air", "position": {"row": 2, "col": 3}})
    s = Engine.create(Compiler().compile(d)); s.advance(29)
    assert hp(s, "ground") == 1850 and hp(s, "air") == 2000


def test_ranged_target_retire_after_launch_discards_impact_without_retarget():
    s = sim(IDS[1], positions={"other": {"row": 2, "col": 3}, "first": {"row": 2, "col": 3}})
    s.advance(23); s.ctx.lifecycle.retire("first", "withdrawn"); s.advance(7)
    assert not damage(s) and hp(s, "other") == 2000
    assert not [t for t in s.session.scheduler.pending if t["kind"] == "domain.effect"]


def test_source_retire_before_launch_cancels_but_after_launch_packet_survives():
    before = sim(IDS[1]); before.advance(10); before.ctx.lifecycle.retire("enemy", "dead"); before.advance(30)
    assert not launch(before) and hp(before) == 2000
    after = sim(IDS[1]); after.advance(23); after.ctx.lifecycle.retire("enemy", "dead"); after.advance(6)
    assert hp(after) == 1850 and len(damage(after)) == 1


def test_actual_hp_death_after_launch_discards_target_packet_without_retarget():
    s = sim(IDS[1], positions={"other": {"row": 2, "col": 3}, "first": {"row": 2, "col": 3}})
    s.advance(23)
    s.ctx.effects.execute("other", ["first"], {"op": "damage", "damage_type": "true", "scale": 1})
    assert not s.ctx.alive("first") and hp(s) == 0
    s.advance(7)
    assert not [e for e in damage(s) if e["payload"]["ability"] == f"ability/{IDS[1]}/ch1_model_normal"]
    assert hp(s, "other") == 2000
    assert not [t for t in s.session.scheduler.pending if t["kind"] == "domain.effect"]


def test_actual_source_hp_death_after_launch_keeps_already_launched_effect():
    s = sim(IDS[1]); s.advance(23)
    s.ctx.effects.execute("first", ["enemy"], {"op": "damage", "damage_type": "true", "scale": 1})
    assert not s.ctx.alive("enemy") and s.ctx.resources.current("enemy", "hp") == 0
    s.advance(6)
    assert hp(s) == 1850
    assert len([e for e in damage(s) if e["payload"]["ability"] == f"ability/{IDS[1]}/ch1_model_normal"]) == 1


def test_launch_fixed_flight_is_not_rescheduled_for_target_movement():
    s = sim(IDS[1]); s.advance(23)
    s.ctx.effects.execute("first", ["first"], {"op": "move", "position": {"row": 4, "col": 5}})
    s.advance(6); assert hp(s) == 1850 and [e["time"] for e in damage(s)] == [28]


def test_prelaunch_far_movement_uses_explicit_lifetime_cap_and_force_hit_profile():
    d = fixture(IDS[1]); d["scenarioDraft"]["map"]["cols"] = 100
    s = Engine.create(Compiler().compile(d)); s.advance(10)
    s.ctx.effects.execute("first", ["first"], {"op": "move", "position": {"row": 2, "col": 62}})
    s.advance(13)
    assert launch(s)[0]["payload"]["flight_seconds"] == 10  # distance60/speed5=12, source lifetime10
    s.advance(299); assert hp(s) == 2000
    s.advance(1); assert hp(s) == 1850 and [e["time"] for e in damage(s)] == [322]


def test_pure_flight_profile_is_replaceable_without_kernel_changes():
    d = fixture(IDS[1]); rule = next(r for r in d["rules"] if r["id"] == "rule/ch1_launch_distance_flight")
    rule["implementation"]["expression"] = "inputs.distance / inputs.speed + 0.1"
    s = Engine.create(Compiler().compile(d)); s.advance(31); assert hp(s) == 2000
    s.advance(1); assert hp(s) == 1850 and [e["time"] for e in damage(s)] == [31]


def test_rogue_full_replay_with_actual_automatic_blocking_mid_combo():
    d = fixture(IDS[0], positions={"first": {"row": 2, "col": 2}})
    player = d["entities"][-1]
    player["components"]["attributes"]["base"]["block_count"] = 1
    player["components"]["deployable"] = {"cost": 0, "terrain": "ground"}
    d["scenarioDraft"]["initialEntities"][0]["route"] = {"motionMode": "WALK", "startPosition": {"row": 2, "col": 2},
        "endPosition": {"row": 2, "col": 5}, "checkpoints": []}
    s = Engine.create(Compiler().compile(d), seed=721); s.advance(19)
    assert s.ctx.get("enemy", ("runtime", "blocked_by")) == s.session.world.resolve("first")
    cp = s.checkpoint(); s.advance(22)
    assert [(e["time"], e["payload"]["amount"]) for e in damage(s)] == [(13, 145), (24, 145)]
    restored = Engine.restore(s.program, cp); restored.advance(22)
    assert restored.snapshot() == s.snapshot()
    assert replay(s.program, s.export_replay()).snapshot() == s.snapshot()


def test_per_packet_defense_is_live_and_source_at_hit_is_live():
    s = sim(IDS[0]); block(s); s.advance(13)
    s.ctx.set("first", ("attributes", "base", "def"), 100)
    s.advance(11); assert hp(s) == 1780  # first145, then175-100=75
    r = sim(IDS[1]); r.advance(23); r.ctx.set("enemy", ("attributes", "base", "atk"), 300)
    r.advance(6); assert hp(r) == 1730


@pytest.mark.parametrize("key,ticks", [(IDS[0], 19), (IDS[1], 24), (IDS[2], 24)])
def test_checkpoint_all_and_complete_replay_ranged_mid_flight(key, ticks):
    s = sim(key)
    if key == IDS[0]:
        # This explicit test setup is in the checkpoint; command replay cannot
        # recreate an unrecorded World mutation, so replay scope is ranged here.
        block(s)
    s.advance(ticks); cp = s.checkpoint(); s.advance(20)
    restored = Engine.restore(s.program, cp); restored.advance(20)
    assert restored.snapshot() == s.snapshot()
    if key != IDS[0]: assert replay(s.program, s.export_replay()).snapshot() == s.snapshot()
