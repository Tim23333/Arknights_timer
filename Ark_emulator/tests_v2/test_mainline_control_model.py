"""Actual story/control conservation, with explicit model timing boundary."""
import json
from copy import deepcopy
from ark_sim import Compiler, Engine
from tools.build_mainline_control_model import build, OUTPUT
from test_campaign_acceptance import scene


def test_exact_native_controls_execute_story_sequence_and_preview_route():
    model = build()
    assert json.loads(OUTPUT.read_text(encoding="utf8")) == model
    assert model["native_control_counts"] == {"STORY": 1, "DISPLAY_ENEMY_INFO": 1}
    data = scene()
    data["scenarioDraft"]["scheduledEffects"] = deepcopy(model["scheduledEffects"])
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(max(sim.ctx.quantize(e["at_seconds"]) for e in model["scheduledEffects"])+1)
    events = [e for e in sim.session.events if e["type"].startswith("story.")]
    assert [e["type"] for e in events] == ["story.started", *["story.command"]*5, "story.finished"]
    assert len({e["time"] for e in events}) == 1
    assert [e["payload"]["command"] for e in events if e["type"] == "story.command"] == [
        "HEADER", "PopupDialog", "PopupDialog", "PopupDialog", "Blocker"]
    assert sim.ctx.state()["input_locks"] == []
    info = [e for e in sim.session.events if e["type"] == "enemy.info_displayed"]
    assert len(info) == 1
    assert info[0]["payload"]["native_action"]["key"] == "enemy_1030_wteeth"
    assert info[0]["payload"]["native_preview_route"]
    assert not model["client_validated"] and not model["formal_stage_approved"]
