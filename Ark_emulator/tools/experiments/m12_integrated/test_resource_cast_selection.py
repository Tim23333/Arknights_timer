"""M10-only runtime: precise resource freeze and selector interruption."""
from pathlib import Path
from copy import deepcopy
import sys
import pytest

PRIMARY = Path(__file__).resolve().parents[3]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m12_projection_candidate"
sys.path.insert(0, str(CANDIDATE)); sys.path.insert(1, str(PRIMARY))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
assert Path(ark_sim.__file__).resolve().is_relative_to(CANDIDATE.resolve())


def scene(freeze=True, mode="event"):
    sp = {"initial": 5, "capacity": 20, "recovery_rule": "rule/gain",
        "recovery": {"mode": "event", "event": "attack.accepted", "owner_role": "source", "amount": 1}}
    if freeze: sp["recovery_freeze_abilities"] = ["ability/selected"]
    if mode != "event":
        sp["recovery"] = {"mode": mode, **({"interval_seconds": .1} if mode == "periodic" else {})}
        sp["recovery_rule"] = "rule/ark_resource_recovery"; sp["recovery_rate"] = 1
    return {"schemaVersion": 2, "entities": [{"id": "unit/source", "kind": "entity", "tags": ["player"], "components": {
        "attributes": {"base": {"max_hp": 100, "atk": 10, "def": 0, "mres": 0, "attack_interval": 100, "attack_speed_ratio": 1}},
        "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}, "sp": sp}, "spatial": {},
        "abilities": ["ability/normal", "ability/selected"], "buffs": {"initial": ["buff/talent"]}}},
        {"id": "unit/target", "kind": "entity", "tags": ["enemy"], "components": {
            "attributes": {"base": {"max_hp": 100, "def": 0, "mres": 0}}, "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}}, "spatial": {}}}],
        "selectors": [{"id": "selector/target", "kind": "selector", "region": {"type": "all"}, "filters": [{"tag": "enemy"}], "limit": 1},
            {"id": "selector/owned", "kind": "selector", "region": {"type": "all"}, "filters": [{"tag": "token"}, {"owner": "source"}, {"state": "alive"}]}],
        "abilities": [{"id": "ability/normal", "kind": "ability", "activation": {"mode": "automatic_attack"}, "selector": "selector/target",
            "timeline": [{"at": t, "effect": {"op": "damage", "damage_type": "true", "scale": 1}} for t in (0, 1)]},
            {"id": "ability/selected", "kind": "ability", "activation": {"mode": "manual", "costs": [{"resource": "sp", "amount": 5}]},
             "timeline": [{"at": 1, "effect": {"op": "emit", "target": "source", "event": "talent.pulse"}}]}],
        "buffs": [{"id": "buff/talent", "kind": "buff", "events": [{"event": "talent.pulse", "effects": [
            {"op": "modify_resource", "target": "source", "resource": "sp", "amount": 1, "parameters": {"respect_recovery_freeze": True}}]}]}],
        "rules": [{"id": "rule/gain", "kind": "calculation_rule", "contract": "resource.recovery", "implementation": {"type": "expression",
            "expression": "inputs.current + inputs.parameters.amount"}}],
        "scenarioDraft": {"id": "scenario/resource_precision", "ruleset": "ruleset/ark_standard", "map": {"rows": 2, "cols": 2},
            "initialEntities": [{"definition": "unit/source", "instanceAlias": "source"}, {"definition": "unit/target", "instanceAlias": "target"}]}}


def sim(d=None): return Engine.create(Compiler().compile(d or scene()), seed=47)
def sp(s): return s.ctx.resources.current("source", "sp")
def custom(d, expression):
    d["rules"].append({"id": "rule/freeze", "kind": "calculation_rule", "contract": "resource.recovery_freeze",
        "implementation": {"type": "expression", "expression": expression},
        "metadata": {"recovery_freeze_authority": "final_override"}})
    d["entities"][0]["components"]["resources"]["sp"]["recovery_freeze_rule"] = "rule/freeze"
    return d


def test_selected_freeze_emission_precedes_finish_and_normal_two_hits_only_one_gain():
    s = sim(); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(2)
    assert sp(s) == 0 and not s.ctx.get("source", ("runtime", "casts"))
    s.advance(2); assert sp(s) == 1
    assert len([e for e in s.session.events if e["type"] == "attack.accepted"]) == 1
    assert len([e for e in s.session.events if e["type"] == "damage.accepted"]) == 2


@pytest.mark.parametrize("mode", ["continuous", "periodic"])
def test_continuous_and_periodic_driver_obey_selected_cast_only(mode):
    d = scene(mode=mode); d["abilities"][1]["timeline"][0]["at"] = 10
    s = sim(d); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(6)
    assert sp(s) == 0
    s.ctx.abilities.interrupt("source", "test_interrupt"); s.advance(4)
    assert sp(s) > 0


def test_active_modify_resource_positive_suppressed_negative_allowed():
    d = scene(); d["abilities"][1]["timeline"][0]["at"] = 10
    s = sim(d); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(1)
    s.ctx.effects.execute("source", ["source"], {"op": "modify_resource", "resource": "sp", "amount": 5,
        "parameters": {"respect_recovery_freeze": True}}); assert sp(s) == 0
    s.ctx.resources.adjust("source", "sp", value=5)
    s.ctx.effects.execute("source", ["source"], {"op": "modify_resource", "resource": "sp", "amount": -2,
        "parameters": {"respect_recovery_freeze": True}}); assert sp(s) == 3


def test_custom_boolean_can_override_legacy_and_does_not_domain_emit_recurse():
    d = custom(scene(), "False"); d["entities"][0]["components"]["resources"]["sp"]["parameters"] = {"freeze_while_cast": True}
    s = sim(d); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(2)
    assert sp(s) == 1
    freeze = [e for e in s.session.events if e["type"] == "calculation" and e["payload"]["calculation_id"] == "resource.recovery_freeze"]
    assert 0 < len(freeze) < 20


def test_custom_rule_failure_rolls_back_composed_health_sp_rng_tasks_and_events():
    d = custom(scene(), "1 / 0"); s = sim(d); before = s.session.checkpoint()
    with pytest.raises(ValueError, match="zero"):
        with s.session.atomic():
            s.session.random.sample("probe"); s.ctx.resources.adjust("target", "hp", -20)
            s.session.schedule("future", {}, 10)
            s.ctx.emit("talent.pulse", {"source": s.session.world.resolve("source"), "target": s.session.world.resolve("source")})
    assert s.session.checkpoint() == before


def test_old_no_configuration_produces_no_new_calculation_events():
    s = sim(scene(freeze=False)); s.advance(2)
    assert sp(s) == 6
    assert not [e for e in s.session.events if e["type"] == "calculation" and e["payload"]["calculation_id"] == "resource.recovery_freeze"]


def test_empty_freeze_list_does_not_freeze_normal_or_disable_legacy():
    d = scene(); d["entities"][0]["components"]["resources"]["sp"]["recovery_freeze_abilities"] = []
    s = sim(d); s.advance(2); assert sp(s) == 6
    d["entities"][0]["components"]["resources"]["sp"]["parameters"] = {"freeze_while_cast": True}
    t = sim(d); t.advance(2); assert sp(t) == 5


@pytest.mark.parametrize("bad", ["missing", "foreign", "wrongkind", "dynamic", "wrongcontract", "authority", "noselector", "badmode", "override"])
def test_strict_compile_reference_contract_and_ownership_rejections(bad):
    d = scene(); spec = d["entities"][0]["components"]["resources"]["sp"]
    if bad == "missing": spec["recovery_freeze_abilities"] = ["ability/missing"]
    elif bad == "foreign":
        d["abilities"].append({"id": "ability/foreign", "kind": "ability", "activation": {"mode": "manual"}, "timeline": []})
        spec["recovery_freeze_abilities"] = ["ability/foreign"]
    elif bad == "wrongkind": spec["recovery_freeze_abilities"] = ["buff/talent"]
    elif bad == "dynamic": spec["recovery_freeze_abilities"] = [{"allowed": ["ability/selected"]}]
    elif bad == "wrongcontract": spec["recovery_freeze_rule"] = "rule/gain"
    elif bad == "authority": custom(d, "True"); d["rules"][-1].pop("metadata")
    elif bad == "noselector": spec["recovery"]["interrupt_abilities"] = ["ability/selected"]
    elif bad == "badmode": spec["recovery"].update(selector="selector/owned", interrupt_when_empty=True, interrupt_cast_modes=["fake"])
    elif bad == "override": d["scenarioDraft"]["initialEntities"][0]["components"] = {"resources": {"sp": {"recovery_freeze_abilities": ["ability/foreign"]}}};d["abilities"].append({"id":"ability/foreign","kind":"ability","activation":{"mode":"manual"},"timeline":[]})
    with pytest.raises(ValueError): Compiler().compile(d)


def test_selector_gate_interrupts_selected_skill_but_preserves_normal_cast():
    d = scene(); d["entities"][0]["components"]["resources"]["sp"]["recovery"].update(selector="selector/owned",
        interrupt_when_empty=True, interrupt_abilities=["ability/selected"])
    s = sim(d); s.advance(2)
    assert len([e for e in s.session.events if e["type"] == "damage.accepted"]) == 2
    t = sim(d); t.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); t.advance(1)
    assert any(e["type"] == "ability.interrupted" and e["payload"]["ability"] == "ability/selected" for e in t.session.events)


def test_checkpoint_replay_same_tick_emission_and_finish():
    s = sim(); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(1)
    cp = s.checkpoint(); s.advance(3)
    restored = Engine.restore(s.program, cp); restored.advance(3)
    assert restored.snapshot() == s.snapshot() and replay(s.program, s.export_replay()).snapshot() == s.snapshot()


def test_rule_can_explicitly_choose_half_open_boundary_and_must_return_bool():
    d = custom(scene(), "inputs.configured_frozen and inputs.time < params.end_tick")
    d["rules"][-1]["parameters"] = {"end_tick": 1}
    s = sim(d); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(2)
    assert sp(s) == 1  # Explicit authorized final rule解除 the membership freeze at t1.
    bad = sim(custom(scene(), "0"))
    with pytest.raises(ValueError, match="boolean|Boolean"): bad.advance(1)


def test_instance_only_rule_is_detected_for_atomic_domain_emission():
    d = custom(scene(), "1 / 0")
    spec = d["entities"][0]["components"]["resources"]["sp"]
    d["scenarioDraft"]["initialEntities"][0]["components"] = {"resources": {"sp": {"recovery_freeze_rule": spec.pop("recovery_freeze_rule")}}}
    s = sim(d); assert s.ctx.resources.has_custom_freeze_rules
    before = s.session.checkpoint()
    with pytest.raises(ValueError, match="zero"):
        s.ctx.emit("talent.pulse", {"source": s.session.world.resolve("source"), "target": s.session.world.resolve("source")})
    assert s.session.checkpoint() == before


def test_interrupt_lists_intersect_modes_and_empty_list_intentionally_interrupts_none():
    for ids, modes in [([], None), (["ability/selected"], ["automatic_attack"])]:
        d = scene(); driver = d["entities"][0]["components"]["resources"]["sp"]["recovery"]
        driver.update(selector="selector/owned", interrupt_when_empty=True, interrupt_abilities=ids)
        if modes is not None: driver["interrupt_cast_modes"] = modes
        d["abilities"][1]["timeline"][0]["at"] = 10
        s = sim(d); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(2)
        assert s.ctx.get("source", ("runtime", "casts"))
        assert not [e for e in s.session.events if e["type"] == "ability.interrupted"]


def test_owned_token_expiry_releases_only_selected_cast_and_replay_matches():
    d = scene(); driver = d["entities"][0]["components"]["resources"]["sp"]["recovery"]
    driver.update(selector="selector/owned", interrupt_when_empty=True, interrupt_abilities=["ability/selected"])
    d["abilities"][1]["timeline"][0]["at"] = 10
    token = {"id": "unit/token", "kind": "entity", "tags": ["token"], "components": {"spatial": {}}}
    d["entities"].append(token); d["scenarioDraft"]["initialEntities"].append({"definition": "unit/token", "instanceAlias": "token",
        "parameters": {"lifetime_seconds": .1}, "components": {"ownership": {"owner": "source"}}})
    s = sim(d); s.submit({"action": "skill", "source": "source", "ability": "ability/selected"}); s.advance(2)
    cp = s.checkpoint(); s.advance(4)
    interrupted = [e for e in s.session.events if e["type"] == "ability.interrupted"]
    assert len(interrupted) == 1 and interrupted[0]["time"] == 3 and interrupted[0]["payload"]["ability"] == "ability/selected"
    assert len([e for e in s.session.events if e["type"] == "damage.accepted"]) == 2
    restored = Engine.restore(s.program, cp); restored.advance(4)
    assert restored.snapshot() == s.snapshot() and replay(s.program, s.export_replay()).snapshot() == s.snapshot()


def test_canonical_chen_119_skill_120_talent_freezes_without_manual_world_writes():
    from tools.experiments.m12_integrated.canonical_probes import chen_scene
    s = sim(chen_scene()); s.advance(120); cp = s.checkpoint(); s.advance(2)
    assert s.ctx.resources.current("chen", "sp") == 0
    restored = Engine.restore(s.program, cp); restored.advance(2)
    assert restored.snapshot() == s.snapshot() and replay(s.program, s.export_replay()).snapshot() == s.snapshot()


def test_canonical_kalts_foreign_mon_wound_in_initial_data_heals_without_owned_token():
    from tools.experiments.m12_integrated.canonical_probes import kalts_scene
    s = sim(kalts_scene()); s.advance(40)
    heals = [e for e in s.session.events if e["type"] == "healing.accepted" and e["payload"]["source"] == s.session.world.resolve("host")]
    assert heals and s.ctx.resources.current("foreign_mon", "hp") > 3000
    assert replay(s.program, s.export_replay()).snapshot() == s.snapshot()


def test_filtered_interrupt_emission_rule_failure_restores_cast_tasks_and_resources():
    d = custom(scene(), "1 / 0")
    d["buffs"][0]["events"][0]["event"] = "ability.interrupted"
    d["abilities"][1]["timeline"][0]["at"] = 10
    s = sim(d); s.ctx.abilities.start("source", "ability/selected")
    before = s.session.checkpoint()
    with pytest.raises(ValueError, match="zero"):
        s.ctx.abilities.interrupt("source", "test", ability_ids=["ability/selected"])
    assert s.session.checkpoint() == before
