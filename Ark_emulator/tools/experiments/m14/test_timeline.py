"""Independent native-population and actual managed-delay counterexamples."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT.parent / "unpack_work/campaign_m12_projection_candidate"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent == CANDIDATE / "ark_sim"
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_m14_mainline_00_10 import build, INPUT, NATIVE, encoded


def test_native_structure_count_flags_origins_and_unchanged_canonical_sections():
    p = build(); native = json.loads(NATIVE.read_bytes()); base = json.loads(INPUT.read_bytes())
    for key in set(base)-{"manifest", "scenarioDraft", "status"}: assert encoded(base[key]) == encoded(p[key])
    assert p["scenarioDraft"]["map"] == base["scenarioDraft"]["map"]
    for key in ("roster", "resources", "rules", "parameters", "objectives", "seed"): assert p["scenarioDraft"][key] == base["scenarioDraft"][key]
    used = set(); counts = {}; total = 0
    for wi, (source_wave, wave) in enumerate(zip(native["waves"], p["scenarioDraft"]["timeline"]["waves"])):
        assert [wave[k] for k in ("pre_delay_seconds", "post_delay_seconds", "max_wait_seconds")] == [source_wave[k] for k in ("preDelay", "postDelay", "maxTimeWaitingForNextWave")]
        for fi, (source_fragment, fragment) in enumerate(zip(source_wave["fragments"], wave["fragments"])):
            assert fragment["pre_delay_seconds"] == source_fragment["preDelay"]
            assert len(fragment["actions"]) == len(source_fragment["actions"])
            for ai, (source, action) in enumerate(zip(source_fragment["actions"], fragment["actions"])):
                assert action["metadata"]["native_action"] == source
                assert (action["delay_seconds"], action["count"], action["interval_seconds"]) == (source["preDelay"], source["count"], source["interval"])
                if source["actionType"] == "SPAWN":
                    assert action["kind"] == "spawn" and action["managed"] == source["managedByScheduler"]
                    assert action["blocks_wave"] == (not source["dontBlockWave"]) and action["blocks_fragment"] == source["blockFragment"]
                    used.add(source["routeIndex"]); total += source["count"]
                    counts[source["key"]] = counts.get(source["key"], 0)+source["count"]
                else: assert action["metadata"]["zero_lifetime_member_elision"] is True
    assert total == 35 and len(used) == 17 and len(counts) == 5
    options = native["options"]; scene = p["scenarioDraft"]
    assert scene["parameters"]["deploy_capacity"] == options["characterLimit"]
    assert scene["resources"]["life"]["initial"] == scene["resources"]["life"]["capacity"] == options["maxLifePoint"]
    assert scene["resources"]["dp"]["initial"] == options["initialCost"]
    assert scene["resources"]["dp"]["capacity"] == options["maxCost"]
    assert scene["resources"]["dp"]["recovery"]["interval_seconds"] == options["costIncreaseTime"]
    assert scene["resources"]["dp"]["recovery_rate"] == 1/options["costIncreaseTime"]
    speed = next(r for r in p["rules"] if r["id"] == scene["rules"]["movement.speed"])
    assert speed["parameters"]["multiplier"] == options["moveMultiplier"]
    assert options["steeringEnabled"] and all(e["components"]["spatial"].get("steering") for e in p["entities"] if "enemy" in e.get("tags", []))
    inactive = {"reachableCheckIgnoreStartTile":False,"isTrainingLevel":False,"isHardTrainingLevel":False,
        "isPredefinedCardsSelectable":False,"displayRestTime":False,"maxPlayTime":-1,"functionDisableMask":"NONE","configBlackBoard":None}
    assert all(options[k] == value for k,value in inactive.items())


def managed_fixture(block_fragment=False, ui=False):
    p = {"schemaVersion": 2, "manifest": {"id": "package/m14_gate_probe", "version": "1", "requires": ["preset/ark_standard"]},
        "entities": [{"id": "unit/probe_enemy", "kind": "entity", "tags": ["enemy"], "components": {
            "attributes": {"base": {"max_hp": 100, "atk": 0, "def": 0, "mres": 0}},
            "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}}, "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"}}}],
        "scenarioDraft": {"id": "scenario/m14_gate_probe", "ruleset": "ruleset/ark_standard", "map": {"rows": 4, "cols": 5},
            "resources": {"dp": {"initial": 0, "capacity": 99}}, "timeline": {"policy": "managed_clear", "negative_timeout_policy": "wait_for_clear",
                "waves": [{"max_wait_seconds": -1, "post_delay_seconds": 1, "fragments": [{"actions": [
                    {"kind": "spawn", "managed": True, "blocks_wave": True, "blocks_fragment": block_fragment,
                        "spawn": {"definition": "unit/probe_enemy", "instanceAlias": "first", "position": {"row": 1, "col": 1}}}]},
                    {"actions": [{"kind": "effects", "effects": [{"op": "emit", "target": "battle", "event": "same_wave_fragment"}]}]}]},
                {"pre_delay_seconds": 1, "fragments": [{"actions": [{"kind": "spawn", "managed": False, "blocks_wave": False,
                    "spawn": {"definition": "unit/probe_enemy", "instanceAlias": "second", "position": {"row": 1, "col": 2}}}]}]}]}}}
    if ui:
        p["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"].insert(0, {"kind": "effects", "effects": [
            {"op": "input_lock", "target": "battle", "parameters": {"key": "ui", "enabled": True}},
            {"op": "emit", "target": "battle", "event": "ui.started"},
            {"op": "emit", "target": "battle", "event": "ui.commands"},
            {"op": "input_lock", "target": "battle", "parameters": {"key": "ui", "enabled": False}},
            {"op": "emit", "target": "battle", "event": "ui.ack_finished"}]})
    return p


def test_actual_alive_managed_holds_next_wave_and_preserves_delays_after_release():
    s = Engine.create(Compiler().compile(managed_fixture())); s.advance(60)
    assert s.ctx.state()["timeline"]["phase"] == "wave_gate" and s.ctx.state()["pending_waves"] == 1
    assert any(e["type"] == "same_wave_fragment" for e in s.session.events)
    assert not [e for e in s.session.world.entities() if e["definition_id"] == "unit/probe_enemy" and e["id"] != s.session.world.resolve("first")]
    s.submit({"action": "withdraw", "source": "first"}); s.advance(60)
    assert s.ctx.state()["pending_waves"] == 1 # release at60 + post30 + next pre30 =>120
    cp = s.checkpoint(); s.advance(1); r = Engine.restore(s.program, cp); r.advance(1)
    assert s.session.world.resolve("second") and s.ctx.state()["pending_waves"] == 0
    assert s.ctx.get("second", ("spatial", "timing_origins")) == {"play_start": 0, "wave_start": 90, "fragment_start": 120, "action_start": 120}
    assert first_difference(s.snapshot(), r.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_block_fragment_true_is_real_gate_and_zero_lifetime_ui_is_equivalent():
    snapshots = []
    for ui in (False, True):
        s = Engine.create(Compiler().compile(managed_fixture(block_fragment=True, ui=ui))); s.advance(2)
        assert not [e for e in s.session.events if e["type"] == "same_wave_fragment"]
        assert not s.ctx.state().get("input_locks")
        s.submit({"action": "withdraw", "source": "first"}); s.advance(62)
        born = [e["time"] for e in s.session.events if e["type"] == "entity.created" and e["payload"]["definition"] == "unit/probe_enemy"]
        snapshots.append((born, s.ctx.state()["pending_waves"]))
        if ui:
            events = [e for e in s.session.events if e["type"].startswith("ui.")]
            assert [e["type"] for e in events] == ["ui.started", "ui.commands", "ui.ack_finished"] and {e["time"] for e in events} == {0}
    assert snapshots[0] == snapshots[1]


def test_new_content_short_prefix_old_commands_actual_CP_and_replay():
    p = build(); s = Engine.create(Compiler().compile(p), seed=123)
    commands = json.loads((ROOT / "validation/campaign/m12_primary_00_10_full_20261002.commands.json").read_bytes())
    for command in commands:
        if command["at"] >= 300: continue
        action = dict(command); at = action.pop("at"); s.submit(action, at=at)
    s.advance(150); r = Engine.restore(s.program, s.checkpoint()); s.advance(150); r.advance(150)
    assert first_difference(s.snapshot(), r.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
    assert not [e for e in s.session.events if e["type"] == "command.rejected"]
    starts = [e for e in s.session.events if e["type"] == "m14.ui.started"]
    ends = [e for e in s.session.events if e["type"] == "m14.ui.ack_finished"]
    assert len(starts) == len(ends) == 1 and starts[0]["time"] == ends[0]["time"] == 0
    assert not s.ctx.state().get("input_locks")
