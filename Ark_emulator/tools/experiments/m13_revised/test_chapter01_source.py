"""Independent source-flag/barrier expectations using actual chapter-1 rows."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT.parent / "unpack_work/campaign_m13_control_lifecycle_revised_candidate"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent == CANDIDATE / "ark_sim"
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.experiments.m13_revised.build_chapter01_control_profiles import build, story_fixture


def test_native_story_a_blocks_fragment_until_actual_external_ack():
    source, p = build("external")
    item = next(r for r in source["action_templates"] if r["native_action"]["key"].endswith("01-11_a"))
    assert item["template"]["blocks_fragment"] is True and item["template"]["blocks_wave"] is True
    data, alias = story_fixture(p, source, item["native_action"]["key"])
    s = Engine.create(Compiler().compile(data)); s.advance(30)
    assert s.ctx.controls.instance(alias)["waiting_step"] == 5
    assert s.ctx.state()["timeline"]["fragment_index"] == 0
    assert not [e for e in s.session.events if e["type"] == "chapter01.probe.next_fragment"]
    cp = s.checkpoint(); s.submit({"action": "control_ack", "control": alias, "step": 5}); s.advance(2)
    assert s.ctx.controls.instance(alias)["status"] == "completed"
    assert len([e for e in s.session.events if e["type"] == "chapter01.probe.next_fragment"]) == 1
    r = Engine.restore(s.program, cp); r.submit({"action": "control_ack", "control": alias, "step": 5}); r.advance(2)
    assert first_difference(s.snapshot(), r.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_story_b_real_delay_completion_and_source_nonblocking_fragment():
    source, p = build("immediate"); key = "obt/tutorial/level/main_01-11_b"
    item = next(r for r in source["action_templates"] if r["native_action"]["key"] == key)
    assert item["template"]["blocks_fragment"] is False and item["template"]["blocks_wave"] is True
    data, alias = story_fixture(p, source, key); s = Engine.create(Compiler().compile(data)); s.advance(540)
    assert s.ctx.controls.instance(alias)["status"] == "running"
    assert s.ctx.state()["timeline"]["phase"] == "wave_gate"
    assert any(e["type"] == "chapter01.probe.next_fragment" for e in s.session.events)
    s.advance(1); assert s.ctx.controls.instance(alias)["completed_at"] == 540
    s.advance(1); assert s.ctx.state()["timeline"]["phase"] == "complete"
    popups = [e for e in s.session.events if e["type"] == "chapter01.control.source_row_observed" and e["payload"]["native_row"]["command"] == "PopupDialog"]
    assert [e["time"] for e in popups] == [0,120,240,360,480]
    assert not [e for e in s.session.events if e["type"] == "native.story.finished"]


def test_source_control_repeat_flags_and_unimplemented_EMP_are_retained():
    source, p = build("immediate")
    item = next(r for r in source["action_templates"] if r["native_action"]["actionType"] == "DISPLAY_ENEMY_INFO" and r["native_action"]["count"] == 3)
    assert item["template"]["count"] == 3 and item["template"]["interval_seconds"] == 12
    assert item["template"]["managed"] is True and item["template"]["blocks_wave"] is True
    token = source["stages"]["level_main_01-12"]["native_level_document"]["predefines"]["tokenInsts"][0]
    assert token["inst"]["characterKey"] == "trap_002_emp" and token["inst"]["level"] == 10
    assert "trap_002_emp_definition_filter_and_lifecycle" in source["pending"]
    assert p["manifest"]["metadata"]["native_async_UI_and_pause_implemented"] is False
