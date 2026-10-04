"""Independent M11 candidate-only spatial/NoBlock atomicity counterexamples."""
from copy import deepcopy
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT.parent / "unpack_work/campaign_m11_block_sync_candidate"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent == CANDIDATE / "ark_sim"
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.experiments.m11.build_block_sync import scene


def tiny(count=2):
    actor = {"id": "unit/blocker", "kind": "entity", "tags": ["player", "ground"], "components": {
        "attributes": {"base": {"max_hp": 1000, "atk": 10, "def": 0, "mres": 0, "block_count": 2, "block_cost": 1}},
        "resources": {"hp": {"initial": 1000, "capacity": 1000, "role": "health"}}, "spatial": {},
        "lifecycle": {"policy": "policy/ark_lifecycle"}, "deployable": {"policy": "policy/ark_ground_deploy", "terrain": "ground"}}}
    enemy = {"id": "unit/mover", "kind": "entity", "tags": ["enemy", "ground"], "components": {
        "attributes": {"base": {"max_hp": 100, "atk": 0, "def": 0, "mres": 0, "move_speed": 0, "block_cost": 1}},
        "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}}, "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"}}}
    actor["components"]["abilities"] = ["ability/"+name for name in ("no_block", "less", "more")]
    return {"schemaVersion": 2, "manifest": {"id": "package/m11_block_test", "version": "1", "requires": ["preset/ark_standard"]},
        "abilities": [{"id": "ability/"+name, "kind": "ability", "activation": {"mode": "manual", "on_start": [
            {"op": "apply_buff", "target": "source", "buff": "buff/"+name}]}, "timeline": []} for name in ("no_block", "less", "more")],
        "entities": [actor, enemy], "buffs": [
            {"id": "buff/no_block", "kind": "buff", "duration_seconds": .1, "control": {"block": False}},
            {"id": "buff/less", "kind": "buff", "duration_seconds": 1, "modifiers": [{"attribute": "block_count", "layer": "flat", "value": -1}]},
            {"id": "buff/more", "kind": "buff", "duration_seconds": 1, "modifiers": [{"attribute": "block_count", "layer": "flat", "value": 1}]}],
        "scenarioDraft": {"id": "scenario/m11_block_test", "ruleset": "ruleset/ark_standard", "map": {"rows": 5, "cols": 8},
            "initialEntities": [{"definition": "unit/blocker", "instanceAlias": "blocker", "position": {"row": 2, "col": 2}},
                *[{"definition": "unit/mover", "instanceAlias": "enemy"+str(i), "position": {"row": 2, "col": 2},
                    "route": {"motionMode": "WALK", "endPosition": {"row": 2, "col": 6}}} for i in range(count)]]}}


def make(data): return Engine.create(Compiler().compile(data), seed=1101)
def relation(s, ref): return s.ctx.spatial.blocked_by(s.session.world.resolve(ref))


@pytest.mark.parametrize("held", [False, True])
def test_canonical_Myrtle_start_no_stale_enemy_cast(held):
    s = make(scene())
    if held:
        s.advance(1); assert relation(s, "enemy") == s.session.world.resolve("myrtle")
    s.submit({"action": "skill", "source": "myrtle", "ability": "ability/campaign_myrtle_s2"}); s.advance(25)
    assert relation(s, "enemy") is None
    eid = s.session.world.resolve("enemy")
    assert not [e for e in s.session.events if e["type"] == "ability.started" and e["payload"]["source"] == eid]
    assert any(e["type"] == "command.accepted" for e in s.session.events)
    assert not [e for e in s.session.events if e["type"] == "command.rejected"]
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_existing_enemy_cast_is_not_implicitly_cancelled():
    s = make(scene()); s.advance(2)
    eid = s.session.world.resolve("enemy")
    assert [e["time"] for e in s.session.events if e["type"] == "ability.started" and e["payload"]["source"] == eid] == [1]
    s.submit({"action": "skill", "source": "myrtle", "ability": "ability/campaign_myrtle_s2"}); s.advance(24)
    assert relation(s, "enemy") is None
    damage = [e for e in s.session.events if e["type"] == "damage.accepted" and e["payload"]["source"] == eid]
    assert len(damage) == 1 and damage[0]["time"] == 19 and damage[0]["payload"]["amount"] == 9.5
    assert not [e for e in s.session.events if e["type"] == "ability.interrupted" and e["payload"]["source"] == eid]
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_capacity_reduce_and_increase_revalidates_existing_members_once():
    s = make(tiny(3)); s.ctx.spatial.blocking()
    blocker = s.session.world.resolve("blocker")
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker, blocker, None]
    less = s.ctx.buffs.apply("blocker", "blocker", "buff/less")
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker, None, None]
    s.ctx.buffs.remove("blocker", less)
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker, blocker, None]
    s.ctx.buffs.apply("blocker", "blocker", "buff/more")
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker]*3


def test_control_apply_remove_and_half_open_expiry_are_immediate():
    s = make(tiny()); s.ctx.spatial.blocking(); blocker = s.session.world.resolve("blocker")
    uid = s.ctx.buffs.apply("blocker", "blocker", "buff/no_block")
    assert relation(s, "enemy0") is None and relation(s, "enemy1") is None
    s.ctx.buffs.remove("blocker", uid)
    assert relation(s, "enemy0") == blocker and relation(s, "enemy1") == blocker
    s.ctx.buffs.apply("blocker", "blocker", "buff/no_block"); s.advance(3)
    assert relation(s, "enemy0") is None
    cp = s.checkpoint(); restored = Engine.restore(s.program, cp); s.advance(1); restored.advance(1)
    assert relation(s, "enemy0") == blocker and relation(s, "enemy1") == blocker
    assert first_difference(s.snapshot(), restored.snapshot()) is None


def failure_provider(inputs, params, context):
    if inputs["attributes"]["block_count"] > 2:
        raise ValueError("independent blocking provider failure")
    return inputs["attributes"]["block_count"]


def test_custom_blocking_failure_rolls_back_everything_and_reentry_guard():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    providers = dict(BUILTIN_PROVIDERS); providers["test/block_capacity"] = failure_provider
    data = tiny(); data["rules"] = [{"id": "rule/block_capacity_test", "kind": "calculation_rule", "contract": "blocking.capacity",
        "implementation": {"type": "provider", "provider": "test/block_capacity"}}]
    data["scenarioDraft"]["rules"] = {"blocking.capacity": "rule/block_capacity_test"}
    hp = data["entities"][0]["components"]["resources"]["hp"]
    hp.pop("capacity"); hp.update(capacity_attribute="max_hp", parameters={"capacity_change_mode": "preserve_missing"})
    data["buffs"][2]["modifiers"] += [{"attribute": "max_hp", "layer": "flat", "value": 100},
        {"attribute": "atk", "layer": "flat", "value": 10}]
    # Actual RNG draw and HP mutation occur before the failing Buff; outer
    # ability atomicity must undo these as well as its cast and queued events.
    data["abilities"][2]["activation"]["on_start"].insert(0, {"op": "random", "stream": "imp", "probability": 1,
        "on_success": [{"op": "modify_resource", "target": "source", "resource": "hp", "delta": -5}]})
    s = Engine.create(Compiler(providers=providers).compile(data), providers=providers); s.ctx.spatial.blocking(); before = s.checkpoint()
    with pytest.raises(ValueError, match="independent blocking provider failure"):
        s.ctx.abilities.start("blocker", "ability/more")
    assert first_difference(before, s.checkpoint()) is None
    assert s.ctx.spatial._blocking_reconciling is False
    # A subsequent valid operation must not be skipped by a leaked guard.
    s.ctx.buffs.apply("blocker", "blocker", "buff/no_block")
    assert relation(s, "enemy0") is None


def test_isolated_context_with_no_spatial_keeps_compatibility():
    from ark_sim.domains.buffs import BuffSystem
    instance = object.__new__(BuffSystem); instance.ctx = object()
    instance._sync_blocking([{"control": {"block": False}, "modifiers": [{"attribute": "block_count", "value": -1}]}])


def test_custom_attribute_role_triggers_same_generic_reconcile():
    import json
    data = tiny(3)
    ruleset = deepcopy(json.loads((CANDIDATE / "ark_sim/content/presets/ark_standard.json").read_bytes())["rulesets"][0])
    ruleset["id"] = "ruleset/m11_custom_roles"
    ruleset["parameters"]["attribute_roles"]["block_capacity"] = "holding_capacity"
    data["rulesets"] = [ruleset]; data["scenarioDraft"]["ruleset"] = ruleset["id"]
    attrs = data["entities"][0]["components"]["attributes"]["base"]
    attrs["holding_capacity"] = attrs.pop("block_count")
    for buff in data["buffs"]:
        for modifier in buff.get("modifiers", []): modifier["attribute"] = "holding_capacity"
    s = make(data); s.ctx.spatial.blocking(); blocker = s.session.world.resolve("blocker")
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker, blocker, None]
    s.ctx.buffs.apply("blocker", "blocker", "buff/less")
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker, None, None]


def test_recorded_capacity_changes_expiry_full_checkpoint_and_replay():
    s = make(tiny(3)); s.submit({"action": "skill", "source": "blocker", "ability": "ability/more"}); s.advance(1)
    blocker = s.session.world.resolve("blocker")
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker]*3
    s.submit({"action": "skill", "source": "blocker", "ability": "ability/less"}); s.advance(4)
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker, blocker, None]
    restored = Engine.restore(s.program, s.checkpoint()); s.advance(31); restored.advance(31)
    assert first_difference(s.snapshot(), restored.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
    assert [relation(s, "enemy"+str(i)) for i in range(3)] == [blocker, blocker, None]


def test_actual_expression_rule_failure_restores_HP_RNG_tasks_events_and_identity():
    from ark_sim.rules.errors import RuleError
    data = tiny()
    data["rules"] = [{"id": "rule/m11_expression_failure", "kind": "calculation_rule", "contract": "blocking.capacity",
        "implementation": {"type": "expression", "expression": "inputs.attributes.block_count if inputs.attributes.block_count <= 2 else 1 / 0"}}]
    data["scenarioDraft"]["rules"] = {"blocking.capacity": "rule/m11_expression_failure"}
    data["abilities"][2]["activation"]["on_start"].insert(0, {"op": "random", "stream": "imp", "probability": 1,
        "on_success": [{"op": "modify_resource", "target": "source", "resource": "hp", "delta": -5}]})
    s = make(data); s.ctx.spatial.blocking()
    before = s.checkpoint(); before_program = s.program.fingerprint; before_runtime = s.runtime_fingerprint
    with pytest.raises(RuleError, match="division by zero"):
        s.ctx.abilities.start("blocker", "ability/more")
    assert s.ctx.resources.current("blocker", "hp") == 1000
    assert first_difference(before, s.checkpoint()) is None
    assert s.program.fingerprint == before_program and s.runtime_fingerprint == before_runtime
    assert s.ctx.spatial._blocking_reconciling is False
