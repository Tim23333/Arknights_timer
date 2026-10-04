"""Independent original419b counterexamples and nested terminal boundaries."""
from copy import deepcopy
import pytest
from tools.experiments.m13_revised.test_controls import scene, make, emit, lock
from ark_sim.tools.compare import first_difference
from ark_sim import Engine
from ark_sim.tools.replay import replay


def setup(where):
    p = scene()
    p["scenarioDraft"]["resources"]["credit"] = {"initial": 0, "capacity": 99}
    fatal = {"op": "modify_resource", "target": "battle", "resource": "lives", "value": 0}
    credit = {"op": "modify_resource", "target": "battle", "resource": "credit", "delta": 2}
    if where == "on_start": p["controls"][0]["on_start"] += [fatal, credit]
    elif where == "on_complete": p["controls"][0]["on_complete"] += [fatal, credit]
    elif where == "step": p["controls"][0]["steps"] = [{"kind": "effects", "effects": [fatal, credit]}, {"kind": "effects", "effects": [emit("later_step")]}]
    elif where == "nested": p["controls"][0]["on_start"] += [{"op": "emit", "target": "battle", "event": "before_nested", "effects": [fatal, credit]}]
    elif where == "random": p["controls"][0]["on_start"] += [{"op": "random", "stream": "imp", "probability": 1, "on_success": [fatal, credit]}]
    return p


@pytest.mark.parametrize("alias", [7, "", False, []])
def test_invalid_alias_error_before_checkpoint_mutation(alias):
    s = make(scene()); s.advance(1); before = s.checkpoint()
    with pytest.raises(ValueError, match="alias"): s.ctx.lifecycle.create("unit/enemy", position={"row": 1, "col": 1}, alias=alias)
    assert first_difference(before, s.checkpoint()) is None


@pytest.mark.parametrize("where", ["on_start", "step", "on_complete", "nested", "random"])
def test_real_terminal_rule_stops_current_sequence_and_never_overwrites_cancelled(where):
    s = make(setup(where)); s.advance(1)
    if where == "on_complete":
        assert not s.ctx.state()["finished"]
        s.submit({"action": "control_ack", "control": "story/test", "step": 0}); s.advance(1)
    assert s.ctx.state()["finished"] and s.ctx.state()["result"] == "defeat"
    assert s.ctx.controls.instance("story/test")["status"] == "cancelled"
    assert s.ctx.resources.current("system/battle", "credit") == 0
    assert s.ctx.state()["pending_waves"] == 1
    assert not [e for e in s.session.events if e["type"] in {"control.completed", "later_step"}]
    assert not [t for t in s.session.scheduler.pending if t["kind"] in {"domain.control.signal", "domain.timeline.signal", "domain.timeline.action"}]
    assert s.ctx.controls._settling_terminal is False and not s.ctx.controls._cancelling
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_nonterminal_on_cancel_becoming_terminal_is_not_recursive_and_stops_remainder():
    p = setup("on_start")
    p["controls"][0]["on_start"] = [lock(True)]
    p["controls"][0]["on_cancel"] = [{"op": "modify_resource", "target": "battle", "resource": "lives", "value": 0},
        {"op": "modify_resource", "target": "battle", "resource": "credit", "delta": 2}]
    s = make(p); s.advance(1); s.ctx.controls.cancel("story/test", "explicit_cancel", policy="continue")
    assert s.ctx.state()["finished"] and s.ctx.controls.instance("story/test")["cancel_policy"] == "terminal"
    assert s.ctx.resources.current("system/battle", "credit") == 0 and not s.ctx.state().get("input_locks")
    assert s.ctx.controls._settling_terminal is False and not s.ctx.controls._cancelling


def test_terminal_on_cancel_failure_rolls_back_fatal_effect_and_entire_controller_start():
    from ark_sim.rules.errors import RuleError
    p = setup("on_start")
    p["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"][0]["delay_seconds"] = 1
    p["rules"] = [{"id": "rule/fatal_cancel_error", "kind": "calculation_rule", "contract": "resource.recovery", "implementation": {"type": "expression", "expression": "1 / 0"}}]
    p["controls"][0]["on_cancel"] = [{"op": "random", "stream": "imp", "probability": 1, "on_success": [emit("cancel_draw")]},
        {"op": "modify_resource", "target": "battle", "resource": "lives", "amount_rule": "rule/fatal_cancel_error"}]
    s = make(p); s.advance(1); before = s.checkpoint()
    with pytest.raises(RuleError, match="division by zero"): s.ctx.controls.begin("story/test")
    assert first_difference(before, s.checkpoint()) is None
    assert not s.ctx.state()["finished"] and s.ctx.controls.instance("story/test")["status"] == "pending"
    assert s.ctx.controls._settling_terminal is False and not s.ctx.controls._cancelling
