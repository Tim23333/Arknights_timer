"""Independent expectations for the declared model, not native Scheduler proof."""
from copy import deepcopy
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay


def spawn(alias, delay=0, blocks_wave=True, blocks_fragment=False, managed=True):
    return {"kind": "spawn", "delay_seconds": delay, "count": 1, "interval_seconds": 0,
        "managed": managed, "blocks_wave": blocks_wave, "blocks_fragment": blocks_fragment,
        "spawn": {"definition": "unit/timeline", "instanceAlias": alias, "position": {"row": 1, "col": 0}}}


def control(name, delay=0):
    return {"kind": "effects", "count": 1, "delay_seconds": delay, "interval_seconds": 0,
        "managed": False, "blocks_wave": False, "blocks_fragment": False,
        "effects": [{"op": "emit", "target": "battle", "event": "review.control", "payload": {"name": name}}]}


def wave(actions, pre=0, fragment_pre=0, post=0, timeout=-1):
    return {"pre_delay_seconds": pre, "post_delay_seconds": post, "max_wait_seconds": timeout,
        "fragments": [{"pre_delay_seconds": fragment_pre, "actions": actions}]}


def data(waves, policy="managed_clear", negative="wait_for_clear"):
    return {"schemaVersion": 2, "entities": [{"id": "unit/timeline", "kind": "entity", "tags": ["enemy"],
        "components": {"attributes": {"base": {"max_hp": 100, "move_speed": 1, "block_cost": 1,
            "atk": 100, "def": 0, "magic_resistance": 0}},
            "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}},
            "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}}}],
        "scenarioDraft": {"id": "scenario/timeline_review", "ruleset": "ruleset/ark_standard",
            "resources": {"dp": {"initial": 0, "capacity": 99}},
            "map": {"rows": 3, "cols": 5}, "timeline": {"policy": policy,
                "negative_timeout_policy": negative, "waves": waves}}}


def sim(waves, **kwargs):
    return Engine.create(Compiler().compile(data(waves, **kwargs)), seed=818)


def controls(s):
    return [(e["time"], e["payload"]["name"]) for e in s.session.events if e["type"] == "review.control"]


def test_relative_origins_and_repeats_preserve_first_action_time():
    a = spawn("repeat", 3, blocks_wave=False)
    a.update(count=2, interval_seconds=1)
    s = sim([wave([a, control("later", 5)], pre=1, fragment_pre=2)])
    s.advance(211)
    for alias in ("repeat/0", "repeat/1"):
        assert s.ctx.get(alias, ("spatial", "timing_origins")) == {
            "play_start": 0, "wave_start": 0, "fragment_start": 90, "action_start": 180}
    assert controls(s) == []  # t240 is still future
    assert s.ctx.state()["pending_waves"] == 0
    s.advance(30)
    assert controls(s) == [(240, "later")]
    assert s.ctx.state()["timeline"]["phase"] == "complete"


@pytest.mark.parametrize("reason", ["dead", "escaped", "withdrawn"])
def test_managed_retirement_alias_releases_wave_then_postdelay(reason):
    s = sim([wave([spawn("hold")], post=1), wave([control("next")], fragment_pre=2)])
    s.advance(61)
    assert controls(s) == []
    with s.session.atomic():
        s.ctx.lifecycle.retire("hold", reason)
    s.advance(91)
    assert controls(s) == [(151, "next")]
    released = [e for e in s.session.events if e["type"] == "timeline.member_released"]
    assert len(released) == 1 and released[0]["payload"]["reason"] == reason
    assert released[0]["payload"]["target"] == s.session.world.resolve("hold")


def test_fragment_block_holds_next_fragment_without_holding_wave_flag():
    w = wave([spawn("fragment_hold", blocks_wave=False, blocks_fragment=True)])
    w["fragments"].append({"pre_delay_seconds": 1, "actions": [control("fragment_next")]})
    s = sim([w]); s.advance(40)
    assert controls(s) == []
    s.ctx.lifecycle.retire("fragment_hold", "dead")
    s.advance(31)
    assert controls(s) == [(70, "fragment_next")]


@pytest.mark.parametrize("policy,negative", [("time_only", "wait_for_clear"), ("managed_clear", "skip_wait")])
def test_explicit_nonblocking_policy_can_advance_with_living_member(policy, negative):
    s = sim([wave([spawn("alive")]), wave([control("next")])], policy=policy, negative=negative)
    s.advance(1)
    assert controls(s) == [(0, "next")]
    assert s.ctx.alive("alive")


def test_positive_timeout_is_from_final_action_not_wave_origin():
    s = sim([wave([spawn("alive", 2), control("last", 4)], timeout=3), wave([control("next")])])
    s.advance(210)
    assert controls(s) == [(120, "last")]
    s.advance(1)
    assert controls(s) == [(120, "last"), (210, "next")]


def test_early_clear_invalidates_timeout_wake_without_skipping_next_delay():
    s = sim([wave([spawn("hold")], timeout=5), wave([control("next")], fragment_pre=8)])
    s.advance(31); s.ctx.lifecycle.retire("hold", "dead"); s.advance(241)
    assert controls(s) == [(271, "next")]


def test_control_only_tail_prevents_early_objective_finish():
    s = sim([wave([control("tail", 2)])])
    s.advance(60)
    assert not s.ctx.state()["finished"] and s.ctx.state()["pending_waves"] == 0
    s.advance(1)
    assert controls(s) == [(60, "tail")]
    assert s.ctx.state()["timeline"]["done"]


def test_actual_hp_death_releases_member_not_foreign_actor():
    s = sim([wave([spawn("hold")]), wave([control("next")])]); s.advance(1)
    s.ctx.lifecycle.create("unit/timeline", alias="foreign")
    s.ctx.lifecycle.retire("foreign", "dead")
    assert len(s.ctx.state()["timeline"]["members"]) == 1
    s.ctx.effects.execute("foreign", ["hold"], {"op": "damage", "damage_type": "true", "scale": 1})
    s.advance(1)
    assert not s.ctx.alive("hold") and controls(s) == [(1, "next")]


def test_fragment_deadline_s_plus_30_is_not_arrival_plus_30():
    a = spawn("walker", 3, blocks_wave=False)
    a["spawn"]["route"] = {"motionMode": "WALK", "startPosition": {"row": 1, "col": 0},
        "endPosition": {"row": 1, "col": 4}, "checkpoints": [
            {"type": "WAIT_CURRENT_FRAGMENT_TIME", "time": 30, "position": {"row": 0, "col": 0}}]}
    s = sim([wave([a], fragment_pre=2)])
    s.advance(151)
    assert s.ctx.get("walker", ("spatial", "timing_origins", "fragment_start")) == 60
    assert s.ctx.get("walker", ("spatial", "movement", "wait_until")) == 960
    s.advance(809)
    assert s.ctx.get("walker", ("spatial", "position")) == {"row": 1, "col": 0}
    s.advance(2)
    assert s.ctx.get("walker", ("spatial", "position"))["col"] > 0


def test_checkpoint_and_full_replay_waiting_membership_and_control_origins():
    s = sim([wave([spawn("hold")], timeout=2), wave([control("next")], fragment_pre=1)])
    s.advance(31); cp = s.checkpoint(); s.advance(61)
    expected = s.snapshot()
    restored = Engine.restore(s.program, cp); restored.advance(61)
    assert restored.snapshot() == expected
    assert replay(s.program, s.export_replay()).snapshot() == expected


def test_spawn_failure_rolls_back_world_pending_and_random_and_fail_stops():
    d = data([wave([spawn("bad")])])
    d["entities"][0]["components"]["resources"]["hp"]["initial"] = 200
    d["entities"][0]["components"]["resources"]["hp"]["bounds_rule"] = "rule/reject"
    d["rules"] = [{"id": "rule/reject", "kind": "calculation_rule", "extends": "rule/ark_resource_bounds", "parameters": {"mode": "reject"}}]
    d["rules"].append({"id": "rule/placement", "kind": "calculation_rule", "contract": "spawn.position",
        "implementation": {"type": "provider", "provider": "ark.spawn.uniform_rect"}})
    a = d["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"][0]
    a["spawn"]["placement"] = {"rule": "rule/placement", "stream": "spawn", "sample_axes": ["col", "row"],
        "sample_zero_range": False, "random_range": {"row": .1, "col": .1}, "offset": {"row": 0, "col": 0}}
    s = Engine.create(Compiler().compile(d), seed=818)
    # First signal prepares fragment actions before the failing create transaction.
    with pytest.raises(ValueError): s.advance(1)
    assert s.ctx.state()["pending_waves"] == 1
    assert s.ctx.state()["timeline"]["remaining_actions"] == 1
    assert not s.ctx.state()["timeline"]["members"]
    with pytest.raises(KeyError): s.session.world.resolve("bad")
    assert not s.session.random.samples
    with pytest.raises(RuntimeError): s.advance(1)


def test_effect_action_failure_rolls_back_controls_events_and_progress_fail_stop():
    a = control("rolled_back")
    a["effects"] = [{"op": "input_lock", "target": "battle", "parameters": {"key": "bad", "enabled": True}},
        *a["effects"], {"op": "modify_resource", "target": "battle", "resource": "absent", "amount": 1}]
    s = sim([wave([a])])
    with pytest.raises(ValueError): s.advance(1)
    assert controls(s) == [] and not s.ctx.state().get("input_locks")
    assert s.ctx.state()["timeline"]["remaining_actions"] == 1
    assert not s.ctx.state()["finished"]
    with pytest.raises(RuntimeError): s.advance(1)


def test_actual_exit_releases_and_late_movement_phase_advances_next_tick():
    a = spawn("exit")
    a["spawn"]["route"] = {"motionMode": "WALK", "startPosition": {"row": 1, "col": 0},
        "endPosition": {"row": 1, "col": .01}, "checkpoints": []}
    s = sim([wave([a]), wave([control("after_exit")])]); s.advance(3)
    retired = [e for e in s.session.events if e["type"] == "timeline.member_released"]
    assert len(retired) == 1
    assert controls(s) == [(retired[0]["time"]+1, "after_exit")]


def test_actual_withdraw_command_releases_in_phase_zero_same_tick():
    a = spawn("withdraw")
    a["spawn"]["components"] = {"deployable": {"cost": 0, "refund_ratio": 0}}
    s = sim([wave([a]), wave([control("after_withdraw")])]); s.advance(1)
    s.submit({"action": "withdraw", "source": "withdraw"}); s.advance(1)
    assert controls(s) == [(1, "after_withdraw")]
    assert not s.ctx.alive("withdraw")


def test_empty_waves_zero_counts_and_post_delay_finish_finitely():
    zero = spawn("never"); zero["count"] = 0
    s = sim([{"pre_delay_seconds": 0, "post_delay_seconds": 1, "max_wait_seconds": -1, "fragments": []},
        wave([zero, control("present")])])
    s.advance(31)
    assert controls(s) == [(30, "present")]
    with pytest.raises(KeyError): s.session.world.resolve("never")
    assert s.ctx.state()["timeline"]["done"]


@pytest.mark.parametrize("mutation", ["policy", "negative", "unmanaged_block", "both", "unknown_kind"])
def test_strict_declarations_reject_ambiguous_policies_and_flags(mutation):
    d = data([wave([spawn("one")])]); t = d["scenarioDraft"]["timeline"]
    if mutation == "policy": t.pop("policy")
    elif mutation == "negative": t.pop("negative_timeout_policy")
    elif mutation == "unmanaged_block": t["waves"][0]["fragments"][0]["actions"][0]["managed"] = False
    elif mutation == "both": d["scenarioDraft"]["waves"] = [{"at": 0, "definition": "unit/timeline"}]
    elif mutation == "unknown_kind": t["waves"][0]["fragments"][0]["actions"][0]["kind"] = "native_magic"
    with pytest.raises(ValueError): Compiler().compile(d)


def test_native_00_11_builder_inventory_origins_and_controls_remain_relative():
    from tools.build_m8_mainline_00_11 import build
    d = build(); t = d["scenarioDraft"]["timeline"]
    assert "waves" not in d["scenarioDraft"] and "scheduledEffects" not in d["scenarioDraft"]
    assert len(t["waves"]) == 3
    actions = [a for w in t["waves"] for f in w["fragments"] for a in f["actions"]]
    assert sum(a["count"] for a in actions if a["kind"] == "spawn") == 37
    assert sum(a["count"] for a in actions if a["kind"] == "effects") == 3
    assert t["waves"][2]["fragments"][0]["pre_delay_seconds"] == 2
    first = t["waves"][2]["fragments"][0]["actions"][0]
    assert first["delay_seconds"] == 3 and first["spawn"]["parameters"]["native_route_index"] == 13
    assert first["spawn"]["route"]["checkpoints"][1]["type"] == "WAIT_CURRENT_FRAGMENT_TIME"
    assert first["spawn"]["route"]["checkpoints"][1]["time"] == 30
    assert [a["delay_seconds"] for a in t["waves"][1]["fragments"][0]["actions"] if a["kind"] == "effects"] == [27, 28]
    assert not d["scenarioDraft"]["metadata"]["formal_mainline_approved"]


def test_defeat_stops_future_births_resource_effects_and_input_locks_without_failure():
    lethal = control("life_exhausted")
    lethal["effects"].append({"op": "modify_resource", "target": "battle", "resource": "life", "amount": -1})
    future = control("must_not_run", 1)
    future["effects"].extend([
        {"op": "modify_resource", "target": "battle", "resource": "dp", "amount": 9},
        {"op": "input_lock", "target": "battle", "parameters": {"key": "late", "enabled": True}}])
    d = data([wave([lethal, future, spawn("unborn", 2)])])
    d["scenarioDraft"]["resources"]["life"] = {"initial": 1, "capacity": 1}
    d["scenarioDraft"]["objectives"] = {"type": "waves", "life_resource": "life", "defeat_threshold": 0}
    s = Engine.create(Compiler().compile(d), seed=818)
    s.advance(1)
    assert s.ctx.state()["finished"] and s.ctx.state()["result"] == "defeat"
    assert s.ctx.state()["pending_waves"] == 1
    cp = s.checkpoint()
    s.advance(91)
    assert controls(s) == [(0, "life_exhausted")]
    assert s.ctx.get("system/battle", ("resources", "dp", "current")) == 0
    assert not s.ctx.state().get("input_locks")
    assert s.ctx.state()["result"] == "defeat" and s.ctx.state()["pending_waves"] == 1
    assert s.ctx.state()["timeline"]["phase"] == "stopped"
    assert s.ctx.state()["timeline"]["remaining_actions"] == 2
    with pytest.raises(KeyError): s.session.world.resolve("unborn")
    assert not [t for t in s.session.scheduler.pending if t["kind"].startswith("domain.timeline.")]
    restored = Engine.restore(s.program, cp); restored.advance(91)
    assert restored.snapshot() == s.snapshot()
    assert replay(s.program, s.export_replay()).snapshot() == s.snapshot()


@pytest.mark.parametrize("retire_tick,fragment_pre,expected_tick", [(6, 0, 63), (42, 0, 63), (72, 1, 93)])
@pytest.mark.parametrize("policy", ["managed_clear", "time_only"])
def test_old_wave_retirement_cannot_bypass_post_wave_pre_or_fragment_pre_delay(retire_tick, fragment_pre, expected_tick, policy):
    s = sim([wave([spawn("old")], timeout=.1, post=1),
        wave([control("scheduled")], pre=1, fragment_pre=fragment_pre)], policy=policy)
    if policy == "time_only": expected_tick -= 3
    s.advance(retire_tick)
    assert controls(s) == []
    s.ctx.lifecycle.retire("old", "dead")
    s.advance(110-retire_tick)
    assert controls(s) == [(expected_tick, "scheduled")]
    released = [e for e in s.session.events if e["type"] == "timeline.member_released"]
    assert len(released) == 1 and released[0]["time"] == retire_tick
