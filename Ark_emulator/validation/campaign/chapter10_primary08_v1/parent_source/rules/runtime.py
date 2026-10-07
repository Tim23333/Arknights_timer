"""Pure, typed calculations and replaceable policy providers."""
import hashlib
import inspect
from collections.abc import Mapping

from ark_sim.contracts.models import EvaluationResult, digest, freeze, thaw
from .catalog import load_catalog, check_inputs, check_type
from .errors import MissingRuleError, RuleError
from .expressions import Expression
from .numeric import NumericProfile, validate_data
from .pipeline import CalculationGraph
from .resolver import BindingResolver
from .context import ProviderContext

RULE_RUNTIME_VERSION = 1


def validate_rule(definition, catalog=None):
    """Compile one definition without requiring provider registration."""
    loaded = load_catalog(catalog)
    if not isinstance(definition, Mapping) or not isinstance(definition.get("id"), str):
        raise RuleError("Rule definitions require string IDs")
    contract_id = definition.get("contract")
    if contract_id not in loaded["contracts"]:
        raise MissingRuleError(f"{definition['id']}: unknown contract {contract_id!r}")
    implementation = definition.get("implementation")
    if not isinstance(implementation, Mapping):
        raise RuleError(f"{definition['id']}: implementation mapping required")
    kind = implementation.get("type")
    allowed = loaded["contracts"][contract_id].get("implementations", ("expression", "graph", "provider"))
    if kind not in allowed:
        raise RuleError(f"{contract_id} does not allow implementation {kind!r}")
    validate_data(definition.get("parameters", {}), "parameters")
    if not isinstance(definition.get("parameters", {}), Mapping):
        raise RuleError("Rule parameters must be a mapping")
    if definition.get("numeric"):
        NumericProfile(definition["numeric"])
    if kind == "expression":
        return Expression(implementation.get("expression"))
    if kind == "graph":
        return CalculationGraph(implementation, loaded)
    if kind == "provider":
        if not isinstance(implementation.get("provider"), str) or not implementation["provider"]:
            raise RuleError("Provider implementation requires a provider name")
        return implementation["provider"]
    raise RuleError(f"Implementation {kind!r} is declared but unavailable in this runtime")


def _provider_record(name, value):
    descriptor = dict(value) if isinstance(value, Mapping) else {}
    function = descriptor.get("callable", descriptor.get("evaluate")) if descriptor else value
    if not callable(function) and hasattr(function, "evaluate"):
        function = function.evaluate
    if not callable(function):
        raise RuleError(f"Provider {name} must be callable or declare a callable")
    version = descriptor.get("version", getattr(value, "version", None))
    module = getattr(function, "__module__", type(function).__module__)
    qualname = getattr(function, "__qualname__", type(function).__qualname__)
    try:
        source = inspect.getsource(function)
    except (OSError, TypeError):
        code = getattr(function, "__code__", None)
        source = (code.co_code.hex() + repr(code.co_consts)) if code else module + ":" + qualname
    fingerprint = {"name": name, "module": module, "qualname": qualname, "version": version,
                   "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()}
    # Explicit provider config changes are part of runtime identity.
    metadata = {key: item for key, item in descriptor.items() if key not in ("callable", "evaluate")}
    validate_data(metadata, f"provider.{name}.descriptor")
    metadata = freeze(metadata)
    fingerprint["descriptor"] = metadata
    return function, metadata, freeze(fingerprint)


class RuleRuntime:
    def __init__(self, rules, bindings=None, catalog=None, numeric_profile=None, providers=None):
        self.catalog = load_catalog(catalog)
        if isinstance(rules, Mapping):
            rule_map = dict(rules)
        elif isinstance(rules, (tuple, list)):
            rule_map = {}
            for definition in rules:
                if definition.get("id") in rule_map:
                    raise RuleError(f"Duplicate rule ID: {definition.get('id')}")
                rule_map[definition.get("id")] = definition
        else:
            raise RuleError("rules must be ID mapping or definition sequence")
        for key, definition in rule_map.items():
            if not isinstance(definition, Mapping) or definition.get("id") != key:
                raise RuleError(f"Rule ID differs from mapping key: {key}")
        validate_data(rule_map, "rules")
        self.rules = freeze(rule_map)
        self.compiled = {key: validate_rule(value, self.catalog) for key, value in self.rules.items()}
        self.numeric = NumericProfile(numeric_profile)
        self.resolver = BindingResolver(bindings, self.catalog)
        self.providers = {name: _provider_record(name, value) for name, value in (providers or {}).items()}
        for key, compiled in self.compiled.items():
            if isinstance(compiled, str) and compiled not in self.providers:
                raise MissingRuleError(f"{key}: provider {compiled!r} is not registered")
            if isinstance(compiled, str) and "parameters_schema" in self.providers[compiled][1]:
                check_type(self.rules[key].get("parameters", {}), self.providers[compiled][1]["parameters_schema"],
                           self.catalog["types"], f"{key}.parameters")
        for calculation, rule in self.resolver.bindings.items():
            self._ensure_binding(calculation, rule)
        self._validate_rule_dependencies()
        self.rule_fingerprints = {}
        for rule in self.rules:
            self._fingerprint_rule(rule)
        self.fingerprint = digest({"runtime_version": RULE_RUNTIME_VERSION, "rules": self.rules, "bindings": self.resolver.bindings,
                                   "catalog": self.catalog, "numeric": self.numeric.definition,
                                   "providers": {name: data[2] for name, data in self.providers.items()}})
        self._evaluation_stack = []
        self._provider_stack = []

    def _fingerprint_rule(self, rule):
        if rule in self.rule_fingerprints:
            return self.rule_fingerprints[rule]
        compiled = self.compiled[rule]
        dependencies = {}
        provider = None
        if isinstance(compiled, CalculationGraph):
            dependencies = {reference: self._fingerprint_rule(reference) for reference in compiled.rule_references}
        elif isinstance(compiled, str):
            provider = self.providers[compiled][2]
        fingerprint = digest({"runtime_version": RULE_RUNTIME_VERSION, "definition": self.rules[rule],
                              "contract": self.catalog["contracts"][self.rules[rule]["contract"]],
                              "numeric": self.numeric.definition, "provider": provider, "dependencies": dependencies})
        self.rule_fingerprints[rule] = fingerprint
        return fingerprint

    def validate_rule(self, definition):
        return validate_rule(definition, self.catalog)

    def _call_provider(self, name, inputs, params, context, child_stages):
        if name not in self.providers:
            raise MissingRuleError(f"Provider {name!r} is not registered")
        if name in self._provider_stack:
            raise RuleError("Pure provider cycle: " + " -> ".join(self._provider_stack + [name]))
        if not isinstance(inputs, Mapping) or not isinstance(params, Mapping):
            raise RuleError("Provider inputs and parameters must be data mappings")
        validate_data(inputs, f"provider.{name}.inputs")
        validate_data(params, f"provider.{name}.parameters")
        function, descriptor, fingerprint = self.providers[name]
        if "parameters_schema" in descriptor:
            check_type(params, descriptor["parameters_schema"], self.catalog["types"], f"provider.{name}.parameters")

        def calculate(calculation_id, calculation_inputs, rule_id):
            result = self.evaluate(calculation_id, calculation_inputs,
                                   scope=context.get("rule_scope"), rule_id=rule_id, context=context)
            child_stages.append({"id": f"calculation:{calculation_id}", "kind": "calculation",
                                 "calculation_id": calculation_id, "rule_id": result.rule_id,
                                 "value": result.value, "trace": result.trace})
            return result

        def invoke(child_name, child_inputs, child_params):
            descendants = []
            raw = self._call_provider(child_name, child_inputs, child_params or {}, context, descendants)
            value = self.numeric.normalize(raw)
            child_stages.append({"id": f"provider:{child_name}", "kind": "provider",
                                 "provider": self.providers[child_name][2], "inputs": child_inputs,
                                 "parameters": child_params or {}, "raw": raw, "value": value,
                                 "stages": descendants})
            return freeze(value)

        read_context = ProviderContext(context, calculate, invoke)
        self._provider_stack.append(name)
        try:
            raw = function(freeze(inputs), freeze(params), read_context)
            validate_data(raw, f"provider.{name}.output")
            if "output_schema" in descriptor:
                check_type(raw, descriptor["output_schema"], self.catalog["types"], f"provider.{name}.output")
            return raw
        finally:
            self._provider_stack.pop()

    def _ensure_binding(self, calculation, rule):
        if calculation not in self.catalog["contracts"]:
            raise MissingRuleError(f"Unknown calculation contract: {calculation}")
        if rule not in self.rules:
            raise MissingRuleError(f"{calculation}: missing rule {rule!r}")
        if self.rules[rule]["contract"] != calculation:
            raise RuleError(f"Binding {calculation} references {rule} with contract {self.rules[rule]['contract']}")

    def _validate_rule_dependencies(self):
        done, active = set(), []

        def visit(rule):
            if rule not in self.compiled:
                raise MissingRuleError("Missing graph rule reference: " + " -> ".join(active + [rule]))
            if rule in active:
                raise RuleError("Recursive rule graph: " + " -> ".join(active + [rule]))
            if rule in done:
                return
            active.append(rule)
            compiled = self.compiled[rule]
            if isinstance(compiled, CalculationGraph):
                for reference in compiled.rule_references:
                    visit(reference)
            active.pop()
            done.add(rule)

        for rule in self.compiled:
            visit(rule)

    def evaluate(self, calculation_id, inputs, scope=None, rule_id=None, context=None):
        selected, binding_trace = self.resolver.resolve(calculation_id, scope, rule_id)
        self._ensure_binding(calculation_id, selected)
        if context is not None and not isinstance(context, Mapping):
            raise RuleError("Calculation context must be a data mapping")
        read_context = dict(context or {})
        read_context["rule_scope"] = scope if scope is not None else read_context.get("rule_scope", {})
        result = self.evaluate_ref(selected, inputs, read_context)
        return EvaluationResult(result.value, {**result.trace, "binding": binding_trace}, selected)

    def evaluate_ref(self, rule_id, inputs, context=None):
        if rule_id in self._evaluation_stack:
            raise RuleError("Dynamic rule binding cycle: " + " -> ".join(self._evaluation_stack + [rule_id]))
        self._evaluation_stack.append(rule_id)
        try:
            return self._evaluate_ref(rule_id, inputs, context)
        finally:
            self._evaluation_stack.pop()

    def _evaluate_ref(self, rule_id, inputs, context=None):
        if rule_id not in self.rules:
            raise MissingRuleError(f"Missing rule: {rule_id}")
        definition = self.rules[rule_id]
        contract = self.catalog["contracts"][definition["contract"]]
        check_inputs(inputs, contract, self.catalog["types"])
        if context is None:
            context = {}
        if not isinstance(context, Mapping):
            raise RuleError("Calculation context must be a data mapping")
        validate_data(context, "context")
        inputs, context = freeze(inputs), freeze(context)
        params = definition.get("parameters", freeze({}))
        implementation, compiled = definition["implementation"], self.compiled[rule_id]
        env = {"inputs": inputs, "params": params, "context": context, "ctx": context, "nodes": freeze({})}
        provider_trace = None
        try:
            if isinstance(compiled, Expression):
                raw = compiled.evaluate(env)
                stages = [{"id": "expression", "expression": compiled.source, "raw": raw}]
            elif isinstance(compiled, CalculationGraph):
                raw, stages = compiled.evaluate(env, self.evaluate_ref, self.numeric, context, self.evaluate)
            else:
                function, descriptor, provider_trace = self.providers[compiled]
                stages = []
                raw = self._call_provider(compiled, inputs, params, context, stages)
                stages.append({"id": "provider", "provider": compiled, "raw": raw})
        except RuleError:
            raise
        except Exception as exc:
            raise RuleError(f"{rule_id}: provider/calculation failed: {exc}") from exc
        output_schema = contract.get("outputSchema", {"type": contract.get("outputType", "record")})
        check_type(raw, output_schema, self.catalog["types"], f"{rule_id}.raw_output")
        value = self.numeric.normalize(raw, definition.get("numeric"))
        check_type(value, output_schema, self.catalog["types"], f"{rule_id}.output")
        trace = {"calculation_id": definition["contract"], "rule_id": rule_id,
                 "contract_version": contract.get("contractVersion", 1),
                 "rule_fingerprint": self.rule_fingerprints[rule_id], "runtime_fingerprint": self.fingerprint,
                 "inputs": inputs, "parameters": params, "context": context,
                 "stages": stages, "raw": raw, "value": value,
                 "numeric": {**self.numeric.definition, **thaw(definition.get("numeric", {}))}}
        if provider_trace:
            trace["provider"] = provider_trace
        return EvaluationResult(value, trace, rule_id)
