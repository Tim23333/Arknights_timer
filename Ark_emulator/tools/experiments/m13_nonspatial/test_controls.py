"""New candidate-only asynchronous control lifecycle counterexamples."""
from copy import deepcopy
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT.parent / "unpack_work/campaign_m13_control_nonspatial_candidate"
sys.path.insert(0, str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent == CANDIDATE / "ark_sim"
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def emit(event): return {"op": "emit", "target": "battle", "event": event}
def lock(enabled): return {"op": "input_lock", "target": "battle", "parameters": {"key": "same_story_key", "enabled": enabled}}


def scene(steps=None, ack="external", actions=None, next_fragment=True):
    definition = {"id": "control/test", "kind": "control", "clock_policy": "logical", "ack_policy": ack,
        "on_start": [lock(True)], "on_complete": [lock(False)], "steps": steps or [{"kind": "ack", "key": "dialog"}]}
    action = {"kind": "control", "definition": definition["id"], "instanceAlias": "story/test", "managed": True,
        "blocks_fragment": True, "blocks_wave": True}
    fragments = [{"actions": actions or [action]}]
    if next_fragment: fragments.append({"actions": [{"kind": "spawn", "spawn": {"definition": "unit/enemy", "instanceAlias": "enemy", "position": {"row": 2, "col": 2}}, "managed": False, "blocks_wave": False}]})
    return {"schemaVersion": 2, "manifest": {"id": "package/m13_control_test", "version": "1", "requires": ["preset/ark_standard"]},
        "controls": [definition], "entities": [{"id": "unit/enemy", "kind": "entity", "tags": ["enemy"], "components": {
            "attributes": {"base": {"max_hp": 100, "atk": 0, "def": 0, "mres": 0}}, "spatial": {},
            "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}}, "lifecycle": {"policy": "policy/ark_lifecycle"}}}],
        "scenarioDraft": {"id": "scenario/m13_control_test", "ruleset": "ruleset/ark_standard", "map": {"rows": 4, "cols": 5},
            "resources": {"lives": {"initial": 3, "capacity": 3}}, "objectives": {"type": "waves", "life_resource": "lives"},
            "timeline": {"policy": "managed_clear", "negative_timeout_policy": "wait_for_clear", "waves": [{"fragments": fragments}]}}}


def make(p): return Engine.create(Compiler().compile(p), seed=1301)


def test_external_ack_real_fragment_gate_and_spawn_conservation_replay():
    s = make(scene()); s.advance(3)
    i = s.ctx.controls.instance("story/test")
    assert i["status"] == "running" and i["phase"] == "awaiting_ack"
    assert s.ctx.state()["pending_waves"] == 1 and not [e for e in s.session.world.entities() if "enemy" in e["tags"]]
    cp = s.checkpoint(); r = Engine.restore(s.program, cp)
    for v in (s, r): v.submit({"action": "control_ack", "control": "story/test", "step": 0}); v.advance(2)
    assert s.ctx.controls.instance("story/test")["status"] == "completed"
    assert s.ctx.state()["pending_waves"] == 0 and len([e for e in s.session.world.entities() if "enemy" in e["tags"]]) == 1
    assert s.ctx.state()["kills"] == 0 and s.ctx.state()["leaks"] == 0
    assert first_difference(s.snapshot(), r.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_pending_control_and_real_logical_delay_then_immediate_completion():
    action = {"kind": "control", "definition": "control/test", "delay_seconds": 1, "blocks_fragment": True}
    s = make(scene(steps=[{"kind": "delay", "seconds": 1}, {"kind": "ack", "key": "auto"}], ack="immediate", actions=[action])); s.advance(30)
    assert s.ctx.controls.instance("control/1")["status"] == "pending" and s.ctx.state()["pending_waves"] == 1
    s.advance(1); assert s.ctx.controls.instance("control/1")["status"] == "running"
    s.advance(30); assert s.ctx.controls.instance("control/1")["status"] == "completed"
    s.advance(2); assert s.ctx.state()["pending_waves"] == 0


def test_two_overlapping_control_locks_cannot_unlock_one_another():
    actions = [{"kind": "control", "definition": "control/test", "instanceAlias": "first", "blocks_fragment": False},
        {"kind": "control", "definition": "control/test", "instanceAlias": "second", "blocks_fragment": False}]
    s = make(scene(actions=actions, next_fragment=False)); s.advance(2)
    assert len(s.ctx.state()["input_locks"]) == 2
    s.submit({"action": "control_ack", "control": "first", "step": 0}); s.advance(1)
    assert len(s.ctx.state()["input_locks"]) == 1 and s.ctx.controls.instance("second")["status"] == "running"
    assert s.ctx.state()["timeline"]["phase"] == "wave_gate"
    s.submit({"action": "control_ack", "control": "second", "step": 0}); s.advance(2)
    assert not s.ctx.state()["input_locks"] and s.ctx.state()["timeline"]["phase"] == "complete"
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_wrong_step_phase_duplicate_and_borrowed_ack_fields_rejected():
    s = make(scene()); s.advance(2)
    for command in [{"action": "control_ack", "control": "story/test", "step": True},
        {"action": "control_ack", "control": "story/test", "step": 9},
        {"action": "control_ack", "control": "missing", "step": 0},
        {"action": "control_ack", "control": "story/test", "step": 0, "ability": "fake"}]:
        s.submit(command); s.advance(1)
    assert len([e for e in s.session.events if e["type"] == "command.rejected"]) == 4
    assert s.ctx.controls.instance("story/test")["status"] == "running"
    s.submit({"action": "control_ack", "control": "story/test", "step": 0}); s.advance(2)
    s.submit({"action": "control_ack", "control": "story/test", "step": 0}); s.advance(1)
    assert len([e for e in s.session.events if e["type"] == "command.rejected"]) == 5


@pytest.mark.parametrize("field,value", [("clock_policy", "wall"), ("clock_policy", None), ("ack_policy", "native"), ("ack_policy", False)])
def test_invalid_clock_or_ack_policy_compile_rejected(field, value):
    p = scene(); p["controls"][0][field] = value
    with pytest.raises(ValueError): Compiler().compile(p)


def test_wrong_definition_kind_duplicate_suffix_and_actor_alias_rejected():
    p = scene(); p["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"][0]["definition"] = "unit/enemy"
    with pytest.raises(ValueError, match="incompatible kind"): Compiler().compile(p)
    p = scene(actions=[{"kind": "control", "definition": "control/test", "instanceAlias": "dup", "count": 2},
        {"kind": "control", "definition": "control/test", "instanceAlias": "dup/1"}])
    with pytest.raises(ValueError, match="alias"): Compiler().compile(p)
    p = scene(); p["scenarioDraft"]["initialEntities"] = [{"definition": "unit/enemy", "instanceAlias": "story/test", "position": {"row": 0, "col": 0}}]
    with pytest.raises(ValueError, match="alias"): Compiler().compile(p)


def test_emit_completed_cannot_release_control_barrier():
    s = make(scene()); s.advance(2)
    s.ctx.effects.execute("system/battle", ["system/battle"], emit("control.completed")); s.advance(3)
    assert s.ctx.controls.instance("story/test")["status"] == "running" and s.ctx.state()["pending_waves"] == 1


def test_wave_flag_holds_next_wave_but_not_same_wave_fragment():
    p = scene(actions=[{"kind": "control", "definition": "control/test", "instanceAlias": "story/test", "blocks_fragment": False, "blocks_wave": True}])
    p["scenarioDraft"]["timeline"]["waves"].append({"fragments": [{"actions": [{"kind": "effects", "effects": [emit("next_wave")]}]}]})
    s = make(p); s.advance(3)
    assert s.ctx.state()["pending_waves"] == 0 and s.ctx.state()["timeline"]["phase"] == "wave_gate"
    assert not [e for e in s.session.events if e["type"] == "next_wave"]
    s.submit({"action": "control_ack", "control": "story/test", "step": 0}); s.advance(2)
    assert len([e for e in s.session.events if e["type"] == "next_wave"]) == 1


@pytest.mark.parametrize("pending", [False, True])
def test_cancel_continue_releases_only_own_locks_jobs_and_is_not_completed(pending):
    action = {"kind": "control", "definition": "control/test", "instanceAlias": "story/test", "blocks_fragment": True, "delay_seconds": 1 if pending else 0}
    s = make(scene(actions=[action])); s.advance(2)
    assert s.ctx.controls.instance("story/test")["status"] == ("pending" if pending else "running")
    s.ctx.controls.cancel("story/test", "explicit_model_cancel", policy="continue"); s.advance(35)
    assert s.ctx.controls.instance("story/test")["status"] == "cancelled"
    assert not s.ctx.state().get("input_locks") and s.ctx.state()["pending_waves"] == 0
    assert not [e for e in s.session.events if e["type"] == "control.completed"]
    assert not [t for t in s.session.scheduler.pending if t["kind"] in {"domain.control.signal", "domain.timeline.action"}]


@pytest.mark.parametrize("mode", ["pending", "ack", "delay"])
def test_terminal_cancels_controls_without_counting_cancelled_future_spawns(mode):
    steps = [{"kind": "delay", "seconds": 2}] if mode == "delay" else [{"kind": "ack", "key": "dialog"}]
    action = {"kind": "control", "definition": "control/test", "instanceAlias": "story/test", "delay_seconds": 1 if mode == "pending" else 0, "blocks_fragment": True}
    p = scene(steps=steps, actions=[action]); p["scenarioDraft"]["scheduledEffects"] = [{"at": 2,
        "effect": {"op": "modify_resource", "target": "battle", "resource": "lives", "value": 0}}]
    s = make(p); s.advance(5)
    assert s.ctx.state()["finished"] and s.ctx.state()["result"] == "defeat"
    assert s.ctx.controls.instance("story/test")["status"] == "cancelled"
    assert s.ctx.state()["pending_waves"] == 1 and s.ctx.state()["kills"] == 0 and s.ctx.state()["leaks"] == 0
    assert not s.ctx.state().get("input_locks")
    assert not [t for t in s.session.scheduler.pending if t["kind"] in {"domain.control.signal", "domain.timeline.action", "domain.timeline.signal"}]
    s.advance(100); assert not [e for e in s.session.events if e["type"] == "control.completed"]
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_overlapping_cancel_does_not_remove_other_control_or_global_lock():
    actions = [{"kind": "control", "definition": "control/test", "instanceAlias": name, "blocks_fragment": False} for name in ("first", "second")]
    p = scene(actions=actions, next_fragment=False); p["scenarioDraft"]["scheduledEffects"] = [{"at": 0, "effect": lock(True)}]
    s = make(p); s.advance(2); assert len(s.ctx.state()["input_locks"]) == 3
    s.ctx.controls.cancel("first", "model_only", policy="continue"); assert len(s.ctx.state()["input_locks"]) == 2
    assert s.ctx.controls.instance("second")["status"] == "running"
    s.ctx.controls.acknowledge("second", 0); assert s.ctx.state()["input_locks"] == ["same_story_key"]


def test_ack_during_delay_rejected_and_on_complete_expression_failure_atomic():
    from ark_sim.rules.errors import RuleError
    p = scene(steps=[{"kind": "delay", "seconds": .1}, {"kind": "ack", "key": "dialog"}])
    p["rules"] = [{"id": "rule/control_fail", "kind": "calculation_rule", "contract": "resource.recovery", "implementation": {"type": "expression", "expression": "1 / 0"}}]
    p["controls"][0]["on_complete"] = [{"op": "random", "stream": "imp", "probability": 1,
        "on_success": [{"op": "modify_resource", "target": "battle", "resource": "lives", "delta": -1}]},
        {"op": "modify_resource", "target": "battle", "resource": "lives", "amount_rule": "rule/control_fail"}]
    s = make(p); s.advance(2)
    with pytest.raises(ValueError, match="phase"): s.ctx.controls.acknowledge("story/test", 0)
    s.advance(2); before = s.checkpoint()
    with pytest.raises(RuleError, match="division by zero"): s.ctx.controls.acknowledge("story/test", 1)
    assert first_difference(before, s.checkpoint()) is None
    assert s.ctx.controls.instance("story/test")["status"] == "running" and s.ctx.state()["pending_waves"] == 1


def test_failed_start_restores_pending_instance_members_resources_RNG_and_jobs():
    p = scene(actions=[{"kind": "control", "definition": "control/test", "instanceAlias": "story/test", "delay_seconds": 1, "blocks_fragment": True}])
    p["controls"][0]["on_start"] += [{"op": "random", "stream": "imp", "probability": 1,
        "on_success": [{"op": "modify_resource", "target": "battle", "resource": "lives", "delta": -1}]},
        {"op": "modify_resource", "target": "battle", "resource": "missing", "delta": 1}]
    s = make(p); s.advance(1); before = s.checkpoint()
    with pytest.raises(ValueError): s.ctx.controls.begin("story/test")
    assert first_difference(before, s.checkpoint()) is None
    assert s.ctx.controls.instance("story/test")["status"] == "pending"


def test_terminal_on_cancel_rule_failure_restores_finished_and_prior_cancellation():
    from ark_sim.rules.errors import RuleError
    p = scene(next_fragment=False)
    second = deepcopy(p["controls"][0]); second["id"] = "control/failing_cancel"
    second["on_cancel"] = [{"op": "random", "stream": "imp", "probability": 1, "on_success": [emit("cancel_sampled")]},
        {"op": "modify_resource", "target": "battle", "resource": "lives", "amount_rule": "rule/cancel_fail"}]
    p["controls"].append(second)
    p["rules"] = [{"id": "rule/cancel_fail", "kind": "calculation_rule", "contract": "resource.recovery", "implementation": {"type": "expression", "expression": "1 / 0"}}]
    p["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"].append({"kind": "control", "definition": second["id"], "instanceAlias": "second", "blocks_fragment": True})
    s = make(p); s.advance(2)
    s.ctx.effects.execute("system/battle", ["system/battle"], {"op": "modify_resource", "target": "battle", "resource": "lives", "value": 0})
    before = s.checkpoint()
    with pytest.raises(RuleError, match="division by zero"): s.ctx.lifecycle.tick(s.session)
    assert first_difference(before, s.checkpoint()) is None
    assert not s.ctx.state()["finished"] and len(s.ctx.state()["input_locks"]) == 2
    assert s.ctx.controls.instance("story/test")["status"] == "running"


def test_control_start_handler_failure_fail_stop_and_valid_checkpoint_restore():
    p = scene(actions=[{"kind": "control", "definition": "control/test", "instanceAlias": "story/test", "delay_seconds": 1}])
    p["controls"][0]["on_start"].append({"op": "modify_resource", "target": "battle", "resource": "missing", "delta": 1})
    s = make(p); s.advance(30); before = s.checkpoint()
    with pytest.raises(ValueError): s.advance(1)
    assert s.ctx.controls.instance("story/test")["status"] == "pending" and not s.ctx.state().get("input_locks")
    assert first_difference(before["kernel"]["world"], s.checkpoint()["kernel"]["world"]) is None
    assert s.checkpoint()["kernel"]["failure"] is not None
    with pytest.raises(Exception): s.advance(1)
    restored = Engine.restore(s.program, before)
    assert first_difference(before, restored.checkpoint()) is None


def test_reserved_control_namespace_and_schedule_jobs_strictly_rejected():
    p = scene(); p["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"][0]["instanceAlias"] = "control/1"
    with pytest.raises(ValueError, match="reserved"): Compiler().compile(p)
    p = scene(); p["controls"][0]["steps"] = [{"kind": "effects", "effects": [{"op": "schedule", "delay_seconds": 1, "effect": emit("unowned")}]}]
    with pytest.raises(ValueError, match="delay steps"): Compiler().compile(p)
    p = scene(); p["controls"][0]["on_start"] = [{"op": "spawn", "kind": "control", "definition": "control/test", "position": {"row": 1, "col": 1}}]
    with pytest.raises(ValueError): Compiler().compile(p)
