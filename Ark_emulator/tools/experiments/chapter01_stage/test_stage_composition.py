"""Source conservation and actual control/NPC execution for partial chapter 1."""
from collections import Counter
from copy import deepcopy
import json

import pytest

from ark_sim import Compiler, Engine
from ark_sim.content.compiler import CompileError
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_chapter01_stage_models import build, require_complete, StageModelGap, ROOT


@pytest.mark.parametrize("level,expected", [("level_main_01-11", 45), ("level_main_01-12", 30)])
def test_every_source_action_keeps_repeat_gate_route_and_origin(level, expected):
    package = build(level)
    native = json.loads((ROOT/"packages/campaign/chapter01_sources/native.reference.json").read_bytes())["stages"][level]
    doc = native["native_level_document"]; scene = package["scenarioDraft"]
    population = 0; controls = Counter()
    assert len(scene["roster"]) == 12 == len(set(scene["roster"]))
    assert scene["seed"] == doc["randomSeed"]
    assert len(scene["timeline"]["waves"]) == len(doc["waves"])
    for wi, (actual_wave, source_wave) in enumerate(zip(scene["timeline"]["waves"], doc["waves"])):
        assert actual_wave["pre_delay_seconds"] == source_wave["preDelay"]
        assert actual_wave["post_delay_seconds"] == source_wave["postDelay"]
        assert actual_wave["max_wait_seconds"] == source_wave["maxTimeWaitingForNextWave"]
        for fi, (actual_frag, source_frag) in enumerate(zip(actual_wave["fragments"], source_wave["fragments"])):
            assert actual_frag["pre_delay_seconds"] == source_frag["preDelay"]
            assert len(actual_frag["actions"]) == len(source_frag["actions"])
            for ai, (actual, source) in enumerate(zip(actual_frag["actions"], source_frag["actions"])):
                assert actual["metadata"]["native_action"] == source
                assert (actual["metadata"]["native_wave"], actual["metadata"]["native_fragment"], actual["metadata"]["native_action_index"]) == (wi, fi, ai)
                assert (actual["count"], actual["delay_seconds"], actual["interval_seconds"]) == (source["count"], source["preDelay"], source["interval"])
                assert (actual["managed"], actual["blocks_wave"], actual["blocks_fragment"]) == (source["managedByScheduler"], not source["dontBlockWave"], source["blockFragment"])
                if source["actionType"] == "SPAWN":
                    population += actual["count"]
                    route = actual["spawn"]["route"]; raw = doc["routes"][source["routeIndex"]]
                    assert actual["spawn"]["parameters"]["native_route_index"] == source["routeIndex"]
                    for key in ("spawnOffset", "spawnRandomRange", "allowDiagonalMove", "visitEveryTileCenter", "visitEveryNodeCenter", "visitEveryCheckPoint"):
                        assert route[key] == raw[key]
                    assert len(route.get("checkpoints") or []) == len(raw.get("checkpoints") or [])
                    for a, b in zip(route.get("checkpoints") or [], raw.get("checkpoints") or []):
                        for key in ("type", "time", "reachOffset", "randomizeReachOffset", "reachDistance"):
                            assert a[key] == b[key]
                else:
                    assert actual["kind"] == "control"
                    controls[source["actionType"]] += source["count"]
    assert population == expected == native["dependency_plan"]["spawn_count"]
    assert dict(controls) == native["control_counts"]


def test_training_cards_and_hidden_npc_do_not_disappear_or_claim_native_deck():
    p = build("level_main_01-11"); meta = p["manifest"]["metadata"]
    assert len(meta["native_predefines"]["characterCards"]) == 12
    assert meta["native_predefines"]["characterInsts"][0]["hidden"] is True
    assert meta["fixed12_profile"]["test_roster_substitution"] is True
    assert meta["fixed12_profile"]["native_training_deck_legal"] is False
    assert all("probe" not in e["id"] for e in p["entities"])
    with pytest.raises(StageModelGap, match="hidden_dormant_registry"):
        require_complete(p)


def test_teleport_tiles_reject_as_unknown_instead_of_silent_floor_conversion():
    p = build("level_main_01-12")
    tile_keys = {t["tileKey"] for t in p["scenarioDraft"]["map"]["tiles"]}
    assert "tile_telin" in tile_keys and "tile_telout" in tile_keys
    assert p["scenarioDraft"]["initialEntities"][0]["position"] == {"row": 5, "col": 5}
    with pytest.raises(CompileError, match="unsupported tile mechanic 'tile_telin'"):
        Compiler().compile(p)


def test_actual_full_source_prefix_control_npc_and_checkpoint_replay():
    p = build("level_main_01-11"); program = Compiler().compile(p)
    sim = Engine.create(program)
    sim.advance(95)
    births = [e for e in sim.session.events if e["type"] == "entity.created"]
    # Native action preDelay=2.99 quantizes to tick90; W and STORY_b begin tick90.
    assert [(e["time"], e["payload"]["definition"]) for e in births if e["payload"].get("definition") in ("unit/chapter01_w", "unit/ch1_predefined_adnach_e0_l20")] == [
        (90, "unit/chapter01_w"), (90, "unit/ch1_predefined_adnach_e0_l20")]
    state = sim.ctx.state()
    assert state["pending_waves"] == 44
    # STORY_b blocks the wave but not this fragment: next fragment preDelay is20s.
    assert state["timeline"]["fragment_index"] == 2
    assert state["timeline"]["wake_at"] == 690
    assert any(c["status"] == "running" for c in state["controls"]["instances"].values())
    checkpoint = sim.checkpoint()
    sim.advance(5); wanted = sim.snapshot(); events = tuple(sim.session.events)
    restored = Engine.restore(program, checkpoint); restored.advance(5)
    assert first_difference(wanted, restored.snapshot()) is None
    assert first_difference(events, tuple(restored.session.events)) is None
    replayed = replay(program, sim.export_replay())
    assert first_difference(wanted, replayed.snapshot()) is None
    assert first_difference(events, tuple(replayed.session.events)) is None

