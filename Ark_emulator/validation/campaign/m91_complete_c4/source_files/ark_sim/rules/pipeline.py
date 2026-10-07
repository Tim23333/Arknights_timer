"""Dependency-checked calculation graphs with stable topological evaluation."""
from collections.abc import Mapping

from ark_sim.contracts.models import freeze
from .errors import RuleError
from .expressions import Expression
from .numeric import NumericProfile
from .catalog import check_type


def compile_value(spec):
    if isinstance(spec, str):
        return Expression(spec)
    if isinstance(spec, Mapping):
        if set(spec) == {"expression"}:
            return Expression(spec["expression"])
        if set(spec) == {"literal"}:
            return freeze(spec["literal"])
        return {key: compile_value(value) for key, value in spec.items()}
    if isinstance(spec, (tuple, list)):
        return tuple(compile_value(value) for value in spec)
    return spec


def value_refs(compiled):
    if isinstance(compiled, Expression):
        return set(compiled.node_references)
    if isinstance(compiled, Mapping):
        return set().union(*(value_refs(value) for value in compiled.values())) if compiled else set()
    if isinstance(compiled, tuple):
        return set().union(*(value_refs(value) for value in compiled)) if compiled else set()
    return set()


def evaluate_value(compiled, env):
    if isinstance(compiled, Expression):
        return compiled.evaluate(env)
    if isinstance(compiled, Mapping):
        return {key: evaluate_value(value, env) for key, value in compiled.items()}
    if isinstance(compiled, tuple):
        return tuple(evaluate_value(value, env) for value in compiled)
    return compiled


class CalculationGraph:
    def __init__(self, implementation, catalog=None):
        raw = implementation.get("nodes")
        if not isinstance(raw, (tuple, list)) or not raw:
            raise RuleError("Graph requires a nonempty nodes list")
        self.nodes, dependencies = {}, {}
        for node in raw:
            if not isinstance(node, Mapping) or not isinstance(node.get("id"), str) or not node["id"]:
                raise RuleError("Graph nodes require string IDs")
            name = node["id"]
            if name in self.nodes:
                raise RuleError(f"Duplicate graph node: {name}")
            if sum(key in node for key in ("expression", "rule", "calculation")) != 1:
                raise RuleError(f"Graph node {name} must have exactly expression, rule or calculation")
            if "expression" in node:
                content = Expression(node["expression"])
            else:
                reference = node.get("rule", node.get("calculation"))
                if not isinstance(reference, str):
                    raise RuleError(f"Graph node {name} rule/calculation reference must be an ID")
                if not isinstance(node.get("inputs", {}), Mapping):
                    raise RuleError(f"Graph node {name} inputs must be a mapping")
                if "calculation" in node:
                    if catalog is None or reference not in catalog["contracts"]:
                        raise RuleError(f"Graph node {name} references unknown calculation: {reference}")
                    contract = catalog["contracts"][reference]
                    declarations = contract.get("inputs", ())
                    if isinstance(declarations, Mapping):
                        declarations = ({"name": key, **(dict(spec) if isinstance(spec, Mapping) else {"type": spec})}
                                        for key, spec in declarations.items())
                    for declaration in declarations:
                        field = declaration["name"]
                        if field not in node.get("inputs", {}):
                            if declaration.get("required", True):
                                raise RuleError(f"Graph node {name}: {reference} missing required input {field!r}")
                        else:
                            candidate = compile_value(node["inputs"][field])
                            # Expressions have runtime values. Literal input values
                            # can already be checked against the child contract.
                            if not _contains_expression(candidate):
                                check_type(candidate, declaration, catalog["types"], f"graph.{name}.inputs.{field}")
                content = compile_value(node.get("inputs", {}))
            self.nodes[name] = {"definition": freeze(node), "content": content}
            if node.get("numeric"):
                NumericProfile(node["numeric"])
            explicit = node.get("dependencies", ())
            if not isinstance(explicit, (list, tuple)) or not all(isinstance(dep, str) for dep in explicit):
                raise RuleError(f"Graph node {name} dependencies must be node IDs")
            dependencies[name] = value_refs(content) | set(explicit)
        all_ids = set(self.nodes)
        for name, refs in dependencies.items():
            missing = refs - all_ids
            if missing:
                raise RuleError(f"Graph node {name} references missing nodes: {sorted(missing)}")
        self.output = Expression(implementation.get("output"))
        if self.output.node_references - all_ids:
            raise RuleError(f"Graph output references missing nodes: {sorted(self.output.node_references - all_ids)}")
        self.order, active = [], []

        def visit(name):
            if name in active:
                raise RuleError("Calculation graph cycle: " + " -> ".join(active + [name]))
            if name in self.order:
                return
            active.append(name)
            for other in self.nodes:
                if other in dependencies[name]:
                    visit(other)
            active.pop()
            self.order.append(name)

        for name in self.nodes:
            visit(name)

    @property
    def rule_references(self):
        return tuple(node["definition"]["rule"] for node in self.nodes.values() if "rule" in node["definition"])

    @property
    def calculation_references(self):
        return tuple(node["definition"]["calculation"] for node in self.nodes.values() if "calculation" in node["definition"])

    def evaluate(self, env, evaluate_ref, numeric, context, evaluate_calculation=None):
        values, stages = {}, []
        for name in self.order:
            item = self.nodes[name]
            definition = item["definition"]
            stage_env = {**env, "nodes": freeze(values)}
            if "rule" in definition or "calculation" in definition:
                stage_inputs = evaluate_value(item["content"], stage_env)
                if "calculation" in definition:
                    if evaluate_calculation is None:
                        raise RuleError("Calculation graph needs an active calculation resolver")
                    result = evaluate_calculation(definition["calculation"], stage_inputs,
                                                  scope=context.get("rule_scope"), context=context)
                else:
                    result = evaluate_ref(definition["rule"], stage_inputs, context=context)
                raw = result.value
                stage_trace = result.trace
            else:
                raw = item["content"].evaluate(stage_env)
                stage_trace = {"expression": definition["expression"]}
            value = numeric.normalize(raw, definition.get("numeric"))
            values[name] = freeze(value)
            stages.append({"id": name, "raw": raw, "value": value, "trace": stage_trace})
        raw_output = self.output.evaluate({**env, "nodes": freeze(values)})
        return raw_output, stages


def _contains_expression(compiled):
    if isinstance(compiled, Expression):
        return True
    if isinstance(compiled, Mapping):
        return any(_contains_expression(value) for value in compiled.values())
    if isinstance(compiled, tuple):
        return any(_contains_expression(value) for value in compiled)
    return False
