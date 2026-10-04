"""Independent expectations for the replaceable rule substrate."""
import json
from pathlib import Path

import pytest

from ark_sim.rules import (RuleRuntime, RuleError, RuleTypeError, MissingRuleError,
                           ExpressionError, BindingConflictError, DEFAULT_CATALOG,
                           validate_rule, evaluate_expression)
from ark_sim.contracts.models import thaw


def formula(rule_id, contract, expression, parameters=None, **extra):
    return {"id": rule_id, "kind": "calculation_rule", "contract": contract,
            "implementation": {"type": "expression", "expression": expression},
            "parameters": parameters or {}, **extra}


def provider(rule_id, contract, name):
    return {"id": rule_id, "contract": contract,
            "implementation": {"type": "provider", "provider": name}}


def mitigation_inputs(**overrides):
    return {"power": 100, "defense": 80, "resistance": 0, "damage_type": "physical", **overrides}


def damage_rules():
    return [formula("rule/half", "damage.mitigation", "max(inputs.power - inputs.defense * params.factor, inputs.power * 0.01)", {"factor": 0.5}),
            formula("rule/full", "damage.mitigation", "max(inputs.power - inputs.defense, inputs.power * 0.01)"),
            formula("rule/proportional", "damage.mitigation", "inputs.power * 100 / (100 + inputs.defense)")]


def test_catalog_has_91_contracts_and_is_immutable():
    assert len(DEFAULT_CATALOG["contracts"]) == 91
    assert {"damage.request", "random.check", "movement.transition", "movement.checkpoint_position", "resource.recovery_freeze"} <= {c["id"] for c in DEFAULT_CATALOG["contracts"]}
    with pytest.raises(TypeError):
        DEFAULT_CATALOG["types"]["number"] = {}


def test_entire_formula_is_replaceable_not_only_parameters():
    runtime = RuleRuntime(damage_rules(), {"damage.mitigation": "rule/half"})
    assert runtime.evaluate("damage.mitigation", mitigation_inputs()).value == 60
    assert runtime.evaluate("damage.mitigation", mitigation_inputs(), rule_id="rule/full").value == 20
    assert runtime.evaluate_ref("rule/proportional", mitigation_inputs()).value == pytest.approx(55.55555555555556)
    result = runtime.evaluate("damage.mitigation", mitigation_inputs())
    assert result.trace["binding"]["owner"] == "target"
    assert result.trace["stages"][0]["raw"] == 60
    assert result.trace["inputs"]["defense"] == 80


def test_architecture_design_formula_preview_cases():
    path = Path(__file__).parents[3] / "docs/v2_examples/custom_guard.json"
    sample = json.loads(path.read_text(encoding="utf-8"))
    runtime = RuleRuntime(sample["rules"])
    for case in sample["formulaPreviewCases"]:
        assert runtime.evaluate_ref(case["rule"], case["inputs"]).value == case["expected"]


def test_scope_uses_target_ownership_and_explicit_order():
    runtime = RuleRuntime(damage_rules(), {"damage.mitigation": "rule/half"})
    scope = {"source": {"damage.mitigation": "rule/full"}}
    assert runtime.evaluate("damage.mitigation", mitigation_inputs(), scope).value == 60
    scope["target"] = {"damage.mitigation": "rule/full"}
    assert runtime.evaluate("damage.mitigation", mitigation_inputs(), scope).value == 20
    scope["effect"] = {"damage.mitigation": "rule/proportional"}
    scope["invocation"] = {"damage.mitigation": "rule/half"}
    result = runtime.evaluate("damage.mitigation", mitigation_inputs(), scope)
    assert result.value == 60 and result.trace["binding"]["origin"] == "invocation"
    assert runtime.evaluate("damage.mitigation", mitigation_inputs(), scope, rule_id="rule/full").value == 20


def test_source_and_scenario_owner_are_different():
    contracts = {"source_value": {"id": "source_value", "owner": "source", "inputs": [], "outputType": "number"},
                 "scene_value": {"id": "scene_value", "owner": "scenario", "inputs": [], "outputType": "number"}}
    runtime = RuleRuntime([formula("s1", "source_value", "1"), formula("s2", "source_value", "2"),
                           formula("c1", "scene_value", "3"), formula("c2", "scene_value", "4")],
                          {"source_value": "s1", "scene_value": "c1"}, contracts)
    scope = {"scenario": {"scene_value": "c2"}, "source": {"source_value": "s2", "scene_value": "c1"},
             "target": {"source_value": "s1", "scene_value": "c1"}}
    assert runtime.evaluate("source_value", {}, scope).value == 2
    assert runtime.evaluate("scene_value", {}, scope).value == 4


def test_same_scope_conflict_rejected_but_identical_overrides_allowed():
    runtime = RuleRuntime(damage_rules(), {"damage.mitigation": "rule/half"})
    with pytest.raises(BindingConflictError, match="conflicting"):
        runtime.evaluate("damage.mitigation", mitigation_inputs(), {"target": [
            {"damage.mitigation": "rule/half"}, {"damage.mitigation": "rule/full"}]})
    assert runtime.evaluate("damage.mitigation", mitigation_inputs(), {"target": [
        {"damage.mitigation": "rule/full"}, {"damage.mitigation": "rule/full"}]}).value == 20


def test_calculation_graph_topological_sort_nested_rules_and_trace():
    graph = {"id": "rule/graph", "contract": "damage.base", "implementation": {"type": "graph", "nodes": [
        {"id": "result", "rule": "rule/multiply", "inputs": {
            "attack": "nodes.boosted", "scale": "inputs.scale", "additions": 0}},
        {"id": "boosted", "expression": "inputs.attack + inputs.additions"}], "output": "nodes.result"}}
    runtime = RuleRuntime([graph, formula("rule/multiply", "damage.base", "inputs.attack * inputs.scale")])
    result = runtime.evaluate_ref("rule/graph", {"attack": 10, "scale": 3, "additions": 5})
    assert result.value == 45
    assert [stage["id"] for stage in result.trace["stages"]] == ["boosted", "result"]
    assert result.trace["stages"][1]["trace"]["rule_id"] == "rule/multiply"


@pytest.mark.parametrize("nodes,output,match", [
    ([{"id": "a", "expression": "nodes.b"}, {"id": "b", "expression": "nodes.a"}], "nodes.a", "cycle"),
    ([{"id": "a", "expression": "nodes.missing"}], "nodes.a", "missing"),
    ([{"id": "a", "expression": "1"}], "nodes.missing", "missing"),
    ([{"id": "a", "expression": "1"}, {"id": "a", "expression": "2"}], "nodes.a", "Duplicate"),
    ([{"id": "a", "expression": "nodes[inputs.dynamic]"}], "nodes.a", "literal"),
])
def test_invalid_graphs_fail_before_execution(nodes, output, match):
    with pytest.raises(RuleError, match=match):
        validate_rule({"id": "rule/g", "contract": "damage.base", "implementation": {
            "type": "graph", "nodes": nodes, "output": output}})


def test_recursive_rule_graph_and_missing_rule_fail():
    def graph(rule_id, reference):
        return {"id": rule_id, "contract": "damage.base", "implementation": {"type": "graph",
            "nodes": [{"id": "stage", "rule": reference, "inputs": {"attack": "inputs.attack", "scale": "inputs.scale", "additions": "inputs.additions"}}],
            "output": "nodes.stage"}}
    with pytest.raises(RuleError, match="Recursive rule graph"):
        RuleRuntime([graph("a", "b"), graph("b", "a")])
    with pytest.raises(MissingRuleError, match="Missing graph rule"):
        RuleRuntime([graph("a", "absent")])


@pytest.mark.parametrize("expression", [
    "__import__('os').system('echo unsafe')", "inputs.__class__", "inputs.get('power')",
    "(lambda: 1)()", "[x for x in inputs.values]", "open('secret')", "globals()",
    "params['__class__']", "2 ** 1000000",
])
def test_unsafe_or_unbounded_expressions_rejected(expression):
    with pytest.raises(ExpressionError):
        evaluate_expression(expression, {"power": 1})


def test_conditional_short_circuit_pure_math_and_structured_literals():
    assert evaluate_expression("inputs.x if inputs.safe and inputs.x > 0 else 0", {"x": 5, "safe": True}) == 5
    assert evaluate_expression("0 if inputs.safe else 1 / 0", {"safe": True}) == 0
    assert evaluate_expression("sum([1, 2, 3]) + sqrt(16) + ceil(0.1) + floor(1.9)", {}) == 12
    assert thaw(evaluate_expression("{'value': clamp(inputs.x, 0, 10), 'accepted': True}", {"x": 20})) == {"value": 10, "accepted": True}


def test_providers_receive_deeply_read_only_inputs_params_and_context():
    captures = []
    def pure(inputs, params, context):
        captures.append((inputs, params, context))
        return inputs["attack"] + context["world"]["bonus"]
    runtime = RuleRuntime([provider("r", "damage.base", "custom")], providers={"custom": {"callable": pure, "version": "1"}})
    result = runtime.evaluate_ref("r", {"attack": 10, "scale": 1, "additions": 0}, {"world": {"bonus": 3}})
    assert result.value == 13
    with pytest.raises(TypeError):
        captures[0][0]["attack"] = 20
    with pytest.raises(TypeError):
        captures[0][2]["world"]["bonus"] = 20
    with pytest.raises(TypeError):
        result.trace["value"] = 20
    assert result.trace["provider"]["version"] == "1"


def test_provider_cannot_write_context_or_return_nan():
    def mutation(inputs, params, context):
        context["value"] = 123
    runtime = RuleRuntime([provider("r", "damage.base", "mutate")], providers={"mutate": mutation})
    with pytest.raises(RuleError, match="failed"):
        runtime.evaluate_ref("r", {"attack": 1, "scale": 1, "additions": 0}, {"value": 0})
    nan_runtime = RuleRuntime([provider("r", "damage.base", "nan")], providers={"nan": lambda i, p, c: float("nan")})
    with pytest.raises(RuleTypeError, match="nonfinite"):
        nan_runtime.evaluate_ref("r", {"attack": 1, "scale": 1, "additions": 0})


def test_provider_record_output_fields_are_required_and_typed():
    rule = provider("r", "resource.bounds", "bounds")
    inputs = {"proposed": 30, "capacity": 20, "minimum": 0, "overflow_policy": {}}
    # Read the catalog to prevent this test from depending on guessed fields.
    contract = next(item for item in DEFAULT_CATALOG["contracts"] if item["id"] == "resource.bounds")
    inputs = {item["name"]: ({} if item["type"] in ("record", "value_map") else 20) for item in contract["inputs"]}
    runtime = RuleRuntime([rule], providers={"bounds": lambda i, p, c: {"value": 20, "overflow": 10, "accepted": True}})
    assert runtime.evaluate_ref("r", inputs).value["overflow"] == 10
    invalid = RuleRuntime([rule], providers={"bounds": lambda i, p, c: {"value": 20, "accepted": "yes"}})
    with pytest.raises(RuleTypeError):
        invalid.evaluate_ref("r", inputs)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), object()])
def test_non_data_context_rejected(bad):
    runtime = RuleRuntime(damage_rules())
    with pytest.raises(RuleTypeError):
        runtime.evaluate_ref("rule/half", mitigation_inputs(), {"nested": [bad]})


def test_missing_contract_rule_provider_and_required_input_fail_explicitly():
    runtime = RuleRuntime(damage_rules())
    with pytest.raises(MissingRuleError, match="No rule bound"):
        runtime.evaluate("damage.mitigation", mitigation_inputs())
    with pytest.raises(MissingRuleError, match="Unknown calculation"):
        runtime.evaluate("invented", {})
    with pytest.raises(MissingRuleError, match="not registered"):
        RuleRuntime([provider("r", "damage.base", "not_supplied")])
    with pytest.raises(RuleTypeError, match="required input"):
        runtime.evaluate_ref("rule/half", {"power": 100})
    with pytest.raises(RuleTypeError, match="expected damage_amount"):
        runtime.evaluate_ref("rule/half", mitigation_inputs(power=True))
    with pytest.raises(RuleError, match="does not allow"):
        validate_rule(formula("r", "lifecycle.death", "True"))


def test_output_type_is_checked_and_wrong_contract_binding_rejected():
    runtime = RuleRuntime([formula("r", "damage.base", "True")])
    with pytest.raises(RuleTypeError, match="expected damage_amount"):
        runtime.evaluate_ref("r", {"attack": 10, "scale": 1, "additions": 0})
    with pytest.raises(RuleError, match="contract"):
        RuleRuntime([formula("r", "damage.base", "1")], {"damage.mitigation": "r"})


def test_numeric_quantization_has_explicit_trace_and_no_implicit_clamp():
    rules = [formula("r", "damage.base", "inputs.attack / 3")]
    inputs = {"attack": 10, "scale": 1, "additions": 0}
    rounded = RuleRuntime(rules, numeric_profile={"precision": 2, "rounding": "floor"})
    result = rounded.evaluate_ref("r", inputs)
    assert result.value == 3.33 and result.trace["raw"] == pytest.approx(10 / 3)
    step = RuleRuntime(rules, numeric_profile={"quantum": 0.25, "rounding": "ceil"})
    assert step.evaluate_ref("r", inputs).value == 3.5
    plain = RuleRuntime([formula("r", "damage.base", "-2")])
    assert plain.evaluate_ref("r", inputs).value == -2
    clamped = RuleRuntime([formula("r", "damage.base", "-2", numeric={"minimum": 0})])
    assert clamped.evaluate_ref("r", inputs).value == 0


def test_numeric_backend_invalid_and_fingerprint_changes_with_provider_version():
    with pytest.raises(RuleError, match="Unsupported numeric backend"):
        RuleRuntime([], numeric_profile={"backend": "decimal"})
    with pytest.raises(RuleError, match="positive finite"):
        RuleRuntime([], numeric_profile={"quantum": 0})
    rules = [provider("r", "damage.base", "p")]
    function = lambda i, p, c: 1
    first = RuleRuntime(rules, providers={"p": {"callable": function, "version": "1"}})
    second = RuleRuntime(rules, providers={"p": {"callable": function, "version": "2"}})
    assert first.fingerprint != second.fingerprint
    assert first.rule_fingerprints["r"] != second.rule_fingerprints["r"]
    assert first.fingerprint == RuleRuntime(rules, providers={"p": {"callable": function, "version": "1"}}).fingerprint


def test_custom_catalog_type_and_provider_parameter_schema_are_validated_at_construction():
    catalog = {"contracts": [{"id": "custom.scalar", "owner": "owner", "inputs": [{"name": "x", "type": "integer"}],
                "outputSchema": {"type": "custom_result"}}],
                "types": {"custom_result": {"representation": "record", "fields": {"value": "number", "accepted": "boolean"}}}}
    rule = provider("r", "custom.scalar", "p")
    rule["parameters"] = {"scale": 2}
    declaration = {"callable": lambda i, p, c: {"value": i["x"] * p["scale"], "accepted": True},
                   "version": "1", "parameters_schema": {"type": "record", "fields": {"scale": "number"}}}
    runtime = RuleRuntime([rule], catalog=catalog, providers={"p": declaration})
    assert runtime.evaluate_ref("r", {"x": 6}).value["value"] == 12
    rule["parameters"] = {"scale": "wrong"}
    with pytest.raises(RuleTypeError, match="parameters.scale"):
        RuleRuntime([rule], catalog=catalog, providers={"p": declaration})


def test_binding_schema_and_graph_stage_numeric_configuration_fail_early():
    with pytest.raises(RuleError, match="nonempty rule IDs"):
        RuleRuntime(damage_rules(), bindings={"damage.mitigation": ["rule/half"]})
    with pytest.raises(RuleError, match="rounding mode"):
        validate_rule({"id": "g", "contract": "damage.base", "implementation": {"type": "graph", "nodes": [
            {"id": "n", "expression": "1", "numeric": {"rounding": "invented"}}], "output": "nodes.n"}})


def damage_pipeline(rule_id="pipeline", *, raw_output=False):
    nodes = [{"id": "power", "calculation": "damage.base", "inputs": {
        "attack": "inputs.source.attributes.attack", "scale": "inputs.effect.scale", "additions": 0}}]
    if not raw_output:
        nodes.append({"id": "mitigated", "calculation": "damage.mitigation", "inputs": {
            "power": "nodes.power", "defense": "inputs.target.attributes.defense",
            "resistance": 0, "damage_type": {"literal": "physical"}}})
    amount = "nodes.power" if raw_output else "nodes.mitigated"
    return {"id": rule_id, "contract": "damage.pipeline", "implementation": {"type": "graph", "nodes": nodes,
        "output": "{'accepted': True, 'amount': " + amount + ", 'allocations': [], 'events': []}"}}


def pipeline_inputs():
    return {"source": {"attributes": {"attack": 100}}, "target": {"attributes": {"defense": 80}},
            "effect": {"scale": 1}, "samples": [], "states": {}}


def test_calculation_graph_preserves_scope_and_whole_pipeline_can_bypass_stages():
    rules = damage_rules() + [formula("power", "damage.base", "inputs.attack * inputs.scale"),
        formula("double_power", "damage.base", "inputs.attack * inputs.scale * 2"),
        damage_pipeline(), damage_pipeline("raw_pipeline", raw_output=True)]
    runtime = RuleRuntime(rules, bindings={"damage.base": "power", "damage.mitigation": "rule/half", "damage.pipeline": "pipeline"})
    assert runtime.evaluate("damage.pipeline", pipeline_inputs()).value["amount"] == 60
    scope = {"target": {"damage.mitigation": "rule/full"}}
    result = runtime.evaluate("damage.pipeline", pipeline_inputs(), scope=scope)
    assert result.value["amount"] == 20
    stage_trace = result.trace["stages"][1]["trace"]
    assert stage_trace["binding"]["origin"] == "target"
    assert stage_trace["context"]["rule_scope"]["target"]["damage.mitigation"] == "rule/full"
    scope["source"] = {"damage.base": "double_power"}
    assert runtime.evaluate("damage.pipeline", pipeline_inputs(), scope=scope).value["amount"] == 120
    scope["effect"] = {"damage.pipeline": "raw_pipeline"}
    assert runtime.evaluate("damage.pipeline", pipeline_inputs(), scope=scope).value["amount"] == 200


def test_graph_calculation_contract_and_required_inputs_checked_statically():
    rule = damage_pipeline()
    rule["implementation"]["nodes"][0]["calculation"] = "absent.contract"
    with pytest.raises(RuleError, match="unknown calculation"):
        validate_rule(rule)
    rule = damage_pipeline()
    del rule["implementation"]["nodes"][0]["inputs"]["attack"]
    with pytest.raises(RuleError, match="missing required input 'attack'"):
        validate_rule(rule)
    rule = damage_pipeline()
    rule["implementation"]["nodes"][0]["inputs"]["attack"] = True
    with pytest.raises(RuleTypeError, match="expected attribute_value"):
        validate_rule(rule)


def test_graph_dynamic_binding_cycle_rejected_and_stack_cleared():
    graph = {"id": "loop", "contract": "damage.base", "implementation": {"type": "graph", "nodes": [
        {"id": "same", "calculation": "damage.base", "inputs": {"attack": "inputs.attack", "scale": "inputs.scale", "additions": "inputs.additions"}}],
        "output": "nodes.same"}}
    runtime = RuleRuntime([graph, formula("constant", "damage.base", "7")], bindings={"damage.base": "loop"})
    inputs = {"attack": 1, "scale": 1, "additions": 0}
    with pytest.raises(RuleError, match="Dynamic rule binding cycle: loop -> loop"):
        runtime.evaluate("damage.base", inputs)
    assert runtime.evaluate("damage.base", inputs, rule_id="constant").value == 7
    assert runtime._evaluation_stack == []
