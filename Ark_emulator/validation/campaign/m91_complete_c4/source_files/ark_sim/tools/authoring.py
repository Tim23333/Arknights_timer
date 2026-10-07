"""Python authoring produces the exact JSON accepted by the compiler."""
import json
from copy import deepcopy
from pathlib import Path
from collections.abc import Mapping
from ..content.compiler import Compiler, _default_providers
from ..contracts.models import thaw


class DefinitionBuilder:
    def __init__(self, identifier, kind, **fields):
        self.definition = {"id": identifier, "kind": kind, **deepcopy(fields)}

    def extends(self, identifier):
        self.definition["extends"] = identifier
        return self

    def bind(self, calculation_id, rule_id):
        self.definition.setdefault("rules", {})[calculation_id] = rule_id
        return self

    def set(self, key, value):
        self.definition[key] = deepcopy(value)
        return self

    def build(self):
        return deepcopy(self.definition)


class EntityBuilder(DefinitionBuilder):
    def __init__(self, identifier, tags=None, **fields):
        components = fields.pop("components", {})
        super().__init__(identifier, "entity", components=deepcopy(components), **fields)
        if tags is not None:
            self.definition["tags"] = list(tags)

    def attributes(self, values=None, **attributes):
        self.definition["components"].setdefault("attributes", {}).setdefault("base", {}).update({**(values or {}), **attributes})
        return self

    def resource(self, name, initial=0, **fields):
        self.definition["components"].setdefault("resources", {})[name] = {"initial": initial, **deepcopy(fields)}
        return self

    def abilities(self, *identifiers):
        self.definition["components"]["abilities"] = list(identifiers)
        return self

    def component(self, name, value):
        self.definition["components"][name] = deepcopy(value)
        return self


class AbilityBuilder(DefinitionBuilder):
    def __init__(self, identifier, mode="manual", selector=None):
        super().__init__(identifier, "ability", activation={"mode": mode}, timeline=[])
        if selector is not None:
            self.definition["selector"] = selector

    def cost(self, resource, amount, **fields):
        self.definition["activation"].setdefault("costs", []).append({"resource": resource, "amount": amount, **fields})
        return self

    def activation(self, **fields):
        self.definition["activation"].update(deepcopy(fields))
        return self

    def effect(self, at_seconds, effect, repeat=None):
        item = {"at_seconds": at_seconds, "effect": deepcopy(effect)}
        if repeat is not None:
            item["repeat"] = deepcopy(repeat)
        self.definition["timeline"].append(item)
        return self


class BuffBuilder(DefinitionBuilder):
    def __init__(self, identifier, duration_seconds, stacking="refresh"):
        super().__init__(identifier, "buff", duration_seconds=duration_seconds,
                         stacking={"mode": stacking}, modifiers=[])

    def modifier(self, attribute, value, layer="flat"):
        self.definition["modifiers"].append({"attribute": attribute, "layer": layer, "value": value})
        return self


class PackageBuilder:
    def __init__(self, identifier="package/custom", version="0.1.0", requires=()):
        self.manifest = {"id": identifier, "version": version, "requires": list(requires)}
        self.definitions = []
        self.scenario_definition = None

    def add(self, definition):
        self.definitions.append(definition)
        return self

    def rule(self, identifier, contract, expression=None, parameters=None, implementation=None):
        if implementation is None:
            implementation = {"type": "expression", "expression": expression}
        return self.add({"id": identifier, "kind": "calculation_rule", "contract": contract,
                         "implementation": deepcopy(implementation), "parameters": deepcopy(parameters or {})})

    def scenario(self, identifier="scenario/custom", **fields):
        self.scenario_definition = {"id": identifier, **deepcopy(fields)}
        return self

    def build(self):
        result = {"schemaVersion": 2, "manifest": deepcopy(self.manifest),
                  "definitions": [d.build() if isinstance(d, DefinitionBuilder) else deepcopy(d) for d in self.definitions]}
        if self.scenario_definition is not None:
            result["scenarioDraft"] = deepcopy(self.scenario_definition)
        return result

    def write(self, path):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return target

    def compile(self, scenario=None, providers=None, catalog=None, **options):
        package = self.build()
        compiler = Compiler(providers=providers, catalog=catalog)
        if scenario is None:
            return compiler.compile(package, **options)
        return compiler.compile(scenario, packages=[package], **options)


def validate_package(package, scenario=None, providers=None, catalog=None, **options):
    compiler = Compiler(providers=providers, catalog=catalog)
    if scenario is None:
        return compiler.compile(package, **options)
    return compiler.compile(scenario, packages=package, **options)


def preview_calculation(program, calculation_id, inputs, scope=None, rule_id=None, providers=None, catalog=None):
    from ..rules import RuleRuntime
    runtime = RuleRuntime(program.rules, bindings=program.ruleset.get("bindings", {}),
                          numeric_profile=program.ruleset.get("numeric_profile"),
                          providers=_default_providers() if providers is None else providers,
                          catalog=catalog if catalog is not None else program.metadata.get("catalog"))
    return runtime.evaluate(calculation_id, inputs, scope=scope, rule_id=rule_id)


def preview_rule(program, rule_id, inputs, providers=None, catalog=None, scope=None):
    return preview_calculation(program, program.rules[rule_id]["contract"], inputs,
                               rule_id=rule_id, providers=providers, catalog=catalog, scope=scope)
