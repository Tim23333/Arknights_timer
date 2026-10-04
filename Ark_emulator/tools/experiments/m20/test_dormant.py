"""Deferred instance initialization and persistent registration witnesses."""
from copy import deepcopy
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def fixture():
    return {"schemaVersion": 2, "manifest": {"id": "package/dormant_tests", "version": "1", "requires": ["preset/ark_standard"]},
        "entities": [{"id": "unit/npc", "kind": "entity", "tags": ["player", "ground"], "components": {
            "attributes": {"base": {"max_hp": 100, "atk": 20, "def": 0, "mres": 0, "block_count": 1, "move_speed": 2}},
            "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"},
                "sp": {"initial": 0, "capacity": 50, "recovery_rate": 1, "recovery": {"mode": "periodic", "interval_seconds": 1}}},
            "buffs": {"initial": ["buff/start"]}, "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"},
            "abilities": ["ability/ping"], "behavior": {"machine": "behavior/start"},
            "deployable": {"base_cost": 0, "capacity": 1, "terrain": "ground", "cooldown_seconds": 0}}},
            {"id": "unit/deck", "kind": "entity", "components": {"deck": {"on_create": [
                {"op": "modify_resource", "target": "source", "resource": "sp", "delta": 2, "parameters": {"if_resource_present": True}}]}}}],
        "abilities": [{"id": "ability/ping", "kind": "ability", "activation": {"mode": "manual"},
            "timeline": [{"at": 0, "effect": {"op": "emit", "target": "source", "event": "probe.ping"}}]}],
        "buffs": [{"id": "buff/start", "kind": "buff", "duration_seconds": .1, "modifiers": [
            {"attribute": "atk", "layer": "flat", "value": 10}]}],
        "behaviors": [{"id": "behavior/start", "kind": "behavior", "initial": "awake", "states": {"awake": {
            "on_enter": [{"op": "emit", "target": "source", "event": "probe.behavior"}]}}, "transitions": []}],
        "scenarioDraft": {"id": "scenario/dormant_tests", "ruleset": "ruleset/ark_standard", "map": {"rows": 1, "cols": 3},
            "roster": ["unit/deck"], "resources": {"dp": {"initial": 20, "capacity": 99}},
            "initialEntities": [{"definition": "unit/npc", "registration_key": "native-npc", "active": False,
                "position": {"row": 0, "col": 1}, "deployed": True}], "objectives": {},
            "scheduledEffects": [{"at": 90, "effect": {"op": "activate_predefined", "target": "battle", "parameters": {"key": "native-npc"}}}]}}


def test_same_actor_identity_deferred_clock_buff_deck_behavior_and_manual_command():
    sim = Engine.create(Compiler().compile(fixture()), seed=20)
    ref = sim.ctx.state()["predefined_registry"]["native-npc"]
    assert sim.ctx.alive(ref) and not sim.ctx.active(ref)
    assert ref not in sim.checkpoint()["kernel"]["world"]["aliases"].values()
    assert not sim.ctx.get(ref, ("runtime", "deployed"))
    sim.submit({"action": "skill", "source": ref, "ability": "ability/ping"}, at=89)
    sim.submit({"action": "skill", "source": ref, "ability": "ability/ping"}, at=95)
    sim.advance(90)
    assert sim.ctx.resources.current(ref, "sp") == 0
    assert sim.ctx.get(ref, ("buffs", "instances")) == []
    assert not [e for e in sim.session.events if e["type"] in {"entity.created", "deck.effect", "probe.behavior"}]
    sim.advance(1)
    assert sim.ctx.active(ref) and sim.ctx.get(ref, ("runtime", "deployed"))
    assert sim.ctx.resources.current(ref, "sp") == 2
    assert sim.ctx.state()["predefined_registry"]["native-npc"] == ref
    assert sim.ctx.attributes.value(ref, "atk") == 30
    assert [(e["time"], e["payload"]["target"]) for e in sim.session.events if e["type"] == "entity.activated"] == [(90, ref)]
    sim.advance(29)
    assert sim.ctx.resources.current(ref, "sp") == 3
    assert sim.ctx.attributes.value(ref, "atk") == 20
    assert len([e for e in sim.session.events if e["type"] == "command.rejected"]) == 1
    assert len([e for e in sim.session.events if e["type"] == "command.accepted"]) == 1
    assert len([e for e in sim.session.events if e["type"] == "probe.ping"]) == 1


def test_checkpoint_before_activation_and_recorded_commands_replay():
    sim = Engine.create(Compiler().compile(fixture()), seed=21); sim.advance(89)
    checkpoint = sim.checkpoint(); sim.advance(31)
    restored = Engine.restore(sim.program, checkpoint); restored.advance(31)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(restored.session.events)) is None
    replayed = replay(sim.program, sim.export_replay())
    assert first_difference(sim.snapshot(), replayed.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(replayed.session.events)) is None


def test_dormant_not_selected_or_blocking_then_immediate_activation_blocking():
    p = fixture(); p['entities'][1]['components']['deck']['on_create'][0]['parameters'] = {'if_resource_present': True}
    p["entities"].append({"id": "unit/enemy", "kind": "entity", "tags": ["enemy", "ground"], "components": {
        "attributes": {"base": {"max_hp": 100, "atk": 1, "def": 0, "mres": 0, "block_cost": 1, "move_speed": 0}},
        "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}}, "spatial": {}}})
    p["scenarioDraft"]["initialEntities"].append({"definition": "unit/enemy", "position": {"row": 0, "col": 1}, "instanceAlias": "enemy",
        "route": {"motionMode": "WALK", "startPosition": {"row": 0, "col": 1}, "endPosition": {"row": 0, "col": 2}, "checkpoints": []}})
    p["selectors"] = [{"id": "selector/players", "kind": "selector", "region": {"type": "all"}, "filters": [{"tag": "player"}]}]
    p["abilities"].append({"id": "ability/query", "kind": "ability", "selector": "selector/players", "activation": {"mode": "manual"}, "timeline": []})
    p["entities"][-1]["components"]["abilities"] = ["ability/query"]
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()["predefined_registry"]["native-npc"]
    sim.advance(90)
    assert sim.ctx.spatial.select("enemy", "selector/players") == []
    assert sim.ctx.spatial.blocked_by("enemy") is None
    sim.advance(1)
    assert sim.ctx.spatial.select("enemy", "selector/players") == [ref]
    assert sim.ctx.spatial.blocked_by("enemy") == ref


def test_deferred_initialization_failure_restores_registry_actor_rng_and_events():
    p = fixture(); p["entities"][1]["components"]["deck"]["on_create"] = [
        {"op": "random", "target": "source", "stream": "imp", "on_success": [{"op": "emit", "event": "probe.random"}]},
        {"op": "modify_resource", "target": "source", "resource": "absent", "delta": 1}]
    p["scenarioDraft"].pop("scheduledEffects")
    sim = Engine.create(Compiler().compile(p)); checkpoint = sim.checkpoint()
    with pytest.raises(ValueError, match="absent"):
        sim.ctx.lifecycle.activate_predefined("native-npc")
    assert first_difference(checkpoint, sim.checkpoint()) is None


def test_double_activation_and_retired_registration_reject_without_new_actor():
    p = fixture(); p["scenarioDraft"].pop("scheduledEffects")
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.lifecycle.activate_predefined("native-npc")
    checkpoint = sim.checkpoint()
    with pytest.raises(ValueError, match="living dormant"):
        sim.ctx.lifecycle.activate_predefined("native-npc")
    assert first_difference(checkpoint, sim.checkpoint()) is None


def test_lifetime_clock_starts_on_activation_and_owns_only_one_expiry():
    p = fixture(); p['scenarioDraft']['initialEntities'][0]['parameters'] = {'lifetime_seconds': .1}
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()['predefined_registry']['native-npc']
    assert not any(t['kind'] == 'domain.entity.expire' for t in sim.session.scheduler.pending)
    sim.advance(93)
    assert sim.ctx.alive(ref)
    assert [t['at'] for t in sim.session.scheduler.pending if t['kind'] == 'domain.entity.expire'] == [93]
    sim.advance(1)
    assert not sim.ctx.alive(ref)
    assert len([e for e in sim.session.events if e['type'] == 'entity.expired']) == 1
    assert first_difference(sim.snapshot(), replay(sim.program, sim.export_replay()).snapshot()) is None


def test_existing_aura_joins_only_on_activation_and_dormant_owner_cannot_patch_tile():
    p = fixture(); p['entities'].append({'id': 'unit/aura_owner', 'kind': 'entity', 'tags': ['ally'], 'components': {
        'attributes': {'base': {'max_hp': 50, 'atk': 0, 'def': 0, 'mres': 0}},
        'resources': {'hp': {'initial': 50, 'capacity': 50, 'role': 'health'}},
        'spatial': {}, 'buffs': {'initial': ['buff/aura']}}})
    p['buffs'] += [{'id': 'buff/aura', 'kind': 'buff', 'aura': {'selector': 'selector/player', 'buff': 'buff/member'}},
        {'id': 'buff/member', 'kind': 'buff', 'stacking': {'mode': 'independent'}, 'modifiers': [{'attribute': 'atk', 'layer': 'flat', 'value': 5}]}]
    p['selectors'] = [{'id': 'selector/player', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'player'}]}]
    p['scenarioDraft']['initialEntities'].append({'definition': 'unit/aura_owner', 'position': {'row': 0, 'col': 0}})
    p['abilities'].append({'id': 'ability/terrain', 'kind': 'ability', 'activation': {'mode': 'manual'}, 'timeline': [{'at': 0,
        'effect': {'op': 'apply_terrain_overlay', 'target': 'source', 'parameters': {'key': 'npc', 'priority': 0, 'values': {'passableMask': 0}}}}]})
    p['entities'][0]['components']['abilities'].append('ability/terrain')
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()['predefined_registry']['native-npc']
    checkpoint = sim.checkpoint()
    with pytest.raises(ValueError, match='active living'):
        sim.ctx.terrain.apply(ref, {'key': 'early', 'priority': 0, 'values': {'passableMask': 0}})
    assert first_difference(checkpoint, sim.checkpoint()) is None
    sim.advance(90); assert sim.ctx.get(ref, ('buffs', 'instances')) == []
    sim.advance(1); assert sim.ctx.attributes.value(ref, 'atk') == 35
    assert len([b for b in sim.ctx.get(ref, ('buffs', 'instances')) if b['definition'] == 'buff/member']) == 1


def test_event_recovery_ignores_dormant_recipient_then_runs_after_activation():
    p = fixture()
    p['entities'][0]['components']['resources']['sp'].update(recovery_rule='rule/event_sp',
        recovery={'mode': 'event', 'event': 'probe.sp', 'owner_role': 'target', 'amount': 4})
    p['rules'] = [{'id': 'rule/event_sp', 'kind': 'calculation_rule', 'contract': 'resource.recovery',
        'implementation': {'type': 'expression', 'expression': 'inputs.current + inputs.parameters.amount'}}]
    for tick in (89, 91):
        p['scenarioDraft']['scheduledEffects'].append({'at': tick, 'effect': {'op': 'emit', 'target': 2, 'event': 'probe.sp'}})
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()['predefined_registry']['native-npc']
    sim.advance(90); assert sim.ctx.resources.current(ref, 'sp') == 0
    sim.advance(2); assert sim.ctx.resources.current(ref, 'sp') == 6
    assert first_difference(sim.snapshot(), replay(sim.program, sim.export_replay()).snapshot()) is None


def test_dormant_does_not_occupy_deployment_cell_or_slot_active_instance_does():
    p = fixture(); p['entities'].append({'id': 'unit/card', 'kind': 'entity', 'tags': ['player'], 'components': {
        'attributes': {'base': {'max_hp': 10, 'atk': 0, 'def': 0, 'mres': 0, 'block_count': 0}},
        'resources': {'hp': {'initial': 10, 'capacity': 10, 'role': 'health'}}, 'spatial': {},
        'deployable': {'base_cost': 0, 'terrain': 'ground', 'capacity': 1, 'cooldown_seconds': 0}}})
    p['scenarioDraft']['roster'].append('unit/card'); p['scenarioDraft']['parameters'] = {'deploy_capacity': 1}
    sim = Engine.create(Compiler().compile(p))
    sim.submit({'action': 'deploy', 'definition': 'unit/card', 'alias': 'early', 'position': {'row': 0, 'col': 1}}, at=1)
    sim.submit({'action': 'withdraw', 'source': 'early'}, at=2)
    sim.submit({'action': 'deploy', 'definition': 'unit/card', 'alias': 'late', 'position': {'row': 0, 'col': 0}}, at=91)
    sim.advance(92)
    assert len([e for e in sim.session.events if e['type'] == 'command.accepted']) == 2
    rejected = [e for e in sim.session.events if e['type'] == 'command.rejected']
    assert len(rejected) == 1 and rejected[0]['payload']['reason'] == 'capacity'
    assert first_difference(sim.snapshot(), replay(sim.program, sim.export_replay()).snapshot()) is None
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()["predefined_registry"]["native-npc"]
    sim.ctx.lifecycle.retire(ref, "expired"); checkpoint = sim.checkpoint()
    with pytest.raises(ValueError, match="living dormant"):
        sim.ctx.lifecycle.activate_predefined("native-npc")
    assert first_difference(checkpoint, sim.checkpoint()) is None


@pytest.mark.parametrize("change", ["nonbool", "empty", "duplicate", "unknown", "target", "selector"])
def test_invalid_registration_and_activation_fail_compile(change):
    p = fixture()
    if change == "nonbool": p["scenarioDraft"]["initialEntities"][0]["active"] = 0
    elif change == "empty": p["scenarioDraft"]["initialEntities"][0]["registration_key"] = ""
    elif change == "duplicate": p["scenarioDraft"]["initialEntities"].append(deepcopy(p["scenarioDraft"]["initialEntities"][0]))
    elif change == "unknown": p["scenarioDraft"]["scheduledEffects"][0]["effect"]["parameters"]["key"] = "unknown"
    elif change == "target": p["scenarioDraft"]["scheduledEffects"][0]["effect"]["target"] = "source"
    else: p["scenarioDraft"]["scheduledEffects"][0]["effect"]["selector"] = "selector/undefined"
    with pytest.raises(ValueError): Compiler().compile(p)

