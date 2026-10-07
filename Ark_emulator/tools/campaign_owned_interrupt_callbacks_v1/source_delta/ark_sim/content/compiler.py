"""Compile author content into an immutable, isolated simulation program."""
import ast
import inspect
import json
from copy import deepcopy
from pathlib import Path
from collections.abc import Mapping
from ..contracts.models import SimulationProgram, digest, thaw
from .repository import ContentError, Repository, load_sources
from .overlays import merge
from .dependencies import closure, references
from .schemas import validate_definition, DEFAULT_CAPABILITIES
from .capabilities import capability_preflight


class CompileError(ContentError):
    pass


PRESET_PATH = Path(__file__).with_name("presets") / "ark_standard.json"


def _default_providers():
    try:
        from ..domains.providers import BUILTIN_PROVIDERS
        return dict(BUILTIN_PROVIDERS)
    except ModuleNotFoundError as exc:
        if exc.name in {"ark_sim.domains", "ark_sim.domains.providers"}:
            return {}
        raise


def _provider_names(definition):
    result = set()
    def walk(value, location=()):
        if isinstance(value, Mapping):
            if isinstance(value.get("provider"), str):
                result.add(value["provider"])
            for key, child in value.items():
                if key == "origin" and (value.get("op") == "no_source_damage" or value.get("type") == "periodic_effect_field"): continue
                if key=='blackboard' and location[-3:]==('map','tiles','[]'):
                    continue
                if key not in {"metadata", "parameters", "payload", "inputs", "expected_blackboard"}:
                    walk(child,location+(key,))
        elif isinstance(value, (tuple, list)):
            for child in value:
                walk(child,location+('[]',))
    walk(definition)
    parameters = definition.get("parameters", {})
    for name in ("aggregator", "aggregators"):
        declared = parameters.get(name, {})
        if isinstance(declared, Mapping):
            if isinstance(declared.get("provider"), str):
                result.add(declared["provider"])
            elif name == "aggregators":
                for candidate in declared.values():
                    if isinstance(candidate, str):
                        result.add(candidate)
                    elif isinstance(candidate, Mapping) and isinstance(candidate.get("provider"), str):
                        result.add(candidate["provider"])
    declared_dependencies = parameters.get("provider_dependencies", [])
    if isinstance(declared_dependencies, (list, tuple)):
        result.update(declared_dependencies)
    if definition.get("kind") == "selector" and not result:
        result.add("ark.selector.grid")
    return result


class Compiler:
    """Every authoring entry point uses this compiler and the same contracts.

    A provider registry is a capability declaration backed by actual callables,
    not a list of names. Unused definitions do not enter the compiled program.
    """
    def __init__(self, providers=None, catalog=None, capabilities=None):
        self.providers = providers
        self.catalog = catalog
        self.capabilities = deepcopy(capabilities or DEFAULT_CAPABILITIES)

    def compile(self, scenario, packages=None, ruleset=None, overrides=None):
        try:
            return self._compile(scenario, packages, ruleset, overrides)
        except CompileError:
            raise
        except (ContentError, ValueError, TypeError, KeyError) as exc:
            raise CompileError(str(exc)) from exc

    def _compile(self, scenario, packages, ruleset, overrides):
        sources = load_sources(PRESET_PATH) + load_sources(packages)
        if isinstance(scenario, (str, Path)) and Path(str(scenario)).exists():
            scenario_sources = load_sources(scenario)
            sources += scenario_sources
            scenario = None
        elif isinstance(scenario, Mapping) and ("scenarioDraft" in scenario or "manifest" in scenario or "scenarios" in scenario):
            sources += load_sources(scenario)
            scenario = None
        repository = Repository(sources)
        if scenario is None:
            candidates = repository.drafts or [key for key, value in repository.raw.items() if value.get("kind") == "scenario"]
            if len(candidates) != 1:
                raise CompileError(f"Select exactly one scenario ID; found {candidates}")
            scenario_id = candidates[0]
        elif isinstance(scenario, Mapping):
            value = thaw(scenario)
            value.setdefault("kind", "scenario")
            if value.get("id") in repository.raw:
                if repository.raw[value["id"]].get("kind") != "scenario":
                    raise CompileError(f"{value['id']}: explicit scenario ID conflicts with a different definition kind")
                # Selecting an explicit scenario object is an intentional edit,
                # unlike duplicate definitions in imported packages.
                repository.raw[value["id"]] = value
            else:
                repository.add(value)
            scenario_id = value["id"]
        elif isinstance(scenario, str):
            scenario_id = scenario
        else:
            raise CompileError("scenario must be an ID, definition, package, or JSON path")

        resolved, resolving = {}, []
        def resolve(identifier):
            if identifier in resolved:
                return resolved[identifier]
            if identifier in resolving:
                raise CompileError("Inheritance cycle: " + " -> ".join(resolving + [identifier]))
            definition = deepcopy(repository.raw[identifier])
            resolving.append(identifier)
            parent_id = definition.get("extends")
            if parent_id:
                if not isinstance(parent_id, str):
                    raise CompileError(f"{identifier}.extends must be one parent ID")
                try:
                    parent = resolve(parent_id)
                except KeyError as exc:
                    raise CompileError(f"{identifier}.extends: missing parent {parent_id}") from exc
                if definition.get("kind", parent.get("kind")) != parent.get("kind"):
                    raise CompileError(f"{identifier}: cannot inherit a different definition kind")
                definition = merge(parent, definition)
                definition["id"] = identifier
            resolving.pop()
            validate_definition(definition, self.capabilities)
            resolved[identifier] = definition
            return definition

        try:
            selected_scene = deepcopy(resolve(scenario_id))
        except KeyError as exc:
            raise CompileError(f"Missing scenario {scenario_id}") from exc
        if selected_scene.get("kind") != "scenario":
            raise CompileError(f"{scenario_id}: expected a scenario definition")
        selection = ruleset or selected_scene.get("ruleset", "ruleset/ark_standard")
        if isinstance(selection, Mapping):
            rule_set = thaw(selection)
            rule_set.setdefault("kind", "ruleset")
            rule_set.setdefault("id", "ruleset/compiled_custom")
            identifier = rule_set["id"]
            if identifier in repository.raw and repository.raw[identifier].get("kind") != "ruleset":
                raise CompileError(f"{identifier}: explicit ruleset ID conflicts with a different definition kind")
            # Passing a ruleset object is an explicit replacement, not import order.
            repository.raw[identifier] = rule_set
            repository.origins[identifier] = "<explicit ruleset>"
            resolved.pop(identifier, None)
        else:
            identifier = selection
        selected_scene["ruleset"] = identifier
        try:
            selected_ruleset = resolve(identifier)
        except KeyError as exc:
            raise CompileError(f"Missing ruleset {identifier}") from exc
        if selected_ruleset.get("kind") != "ruleset":
            raise CompileError(f"{identifier}: expected a ruleset")

        explicit_bindings = self._overrides(overrides)
        if explicit_bindings:
            selected_scene["rules"] = merge(selected_scene.get("rules", {}), explicit_bindings)
        resolved[scenario_id] = selected_scene
        for origin, manifest in repository.manifests:
            for field in ("requires", "externals"):
                for reference in manifest.get(field, []):
                    package_ids = {entry.get("id") for _, entry in repository.manifests}
                    if reference not in repository.raw and reference not in package_ids:
                        raise CompileError(f"{origin}.manifest.{field}: missing dependency {reference}")
        calculation_bindings = {**selected_ruleset.get("bindings", {}), **selected_scene.get("rules", {})}
        dependency_ids, edges = closure([scenario_id, identifier], resolve, calculation_bindings)
        definitions = {key: deepcopy(resolve(key)) for key in dependency_ids}
        for key, definition in definitions.items():
            validate_definition(definition, self.capabilities)
            self._validate_implemented_references(definition, key)
            self._validate_content_expressions(definition, key)
        rules = {key: definition for key, definition in definitions.items()
                 if definition.get("kind") in {"rule", "calculation_rule"}}

        providers = dict(self.providers) if self.providers is not None else _default_providers()
        required_providers = sorted(set().union(*(_provider_names(d) for d in definitions.values())))
        provider_lock = {}
        for name in required_providers:
            if name not in providers:
                raise CompileError(f"Required provider is not implemented or registered: {name}")
            declaration = providers[name]
            callback = declaration.get("callable", declaration.get("evaluate")) if isinstance(declaration, Mapping) else declaration
            if not callable(callback) and hasattr(callback, "evaluate"):
                callback = callback.evaluate
            if not callable(callback):
                raise CompileError(f"Provider {name}: declaration has no callable implementation")
            try:
                source_hash = digest(inspect.getsource(callback))
            except (OSError, TypeError):
                source_hash = digest({"module": getattr(callback, "__module__", ""), "name": getattr(callback, "__qualname__", type(callback).__name__)})
            provider_lock[name] = {"version": declaration.get("version", getattr(callback, "version", "unversioned")) if isinstance(declaration, Mapping) else getattr(declaration, "version", getattr(callback, "version", "unversioned")), "implementation": source_hash}

        runtime = self._validate_rules(rules, definitions, selected_ruleset,
                                       {name: providers[name] for name in required_providers})
        self._validate_reference_kinds(definitions)
        self._validate_entity_abilities(definitions, selected_scene)
        from ..domains.behavior_restart import validate_content as validate_restarts
        validate_restarts(definitions,selected_scene)
        from ..domains.tile_fields import validate_definitions as validate_tile_fields
        validate_tile_fields(definitions,selected_scene)
        from ..domains.periodic_fields import validate_content as validate_periodic_fields
        validate_periodic_fields(definitions,selected_scene)
        from ..domains.deploy_connectivity import validate_scenario as validate_connectivity
        validate_connectivity(definitions,selected_scene)
        registered = {item['registration_key'] for item in selected_scene.get('initialEntities', ()) if item.get('registration_key')}
        def validate_activation(value):
            if isinstance(value, dict):
                if value.get('op') == 'activate_predefined' and value.get('parameters', {}).get('key') not in registered:
                    raise CompileError('activate_predefined references an unknown initial registration key')
                for key, child in value.items():
                    if key not in {'metadata', 'payload', 'parameters', 'manifest'}: validate_activation(child)
            elif isinstance(value, (list, tuple)):
                for child in value: validate_activation(child)
        validate_activation(definitions)
        required_calculations = capability_preflight(selected_scene, definitions, selected_ruleset, rules, runtime.catalog)
        origins = {repository.origins[key] for key in dependency_ids}
        package_lock = sorted([{"id": manifest.get("id", "anonymous"), "version": manifest.get("version", "0")}
                               for origin, manifest in repository.manifests if origin in origins and manifest], key=lambda x: (x["id"], x["version"]))
        metadata = {"schema_version": 2, "compiler_version": "1.0.0", "packages": package_lock,
                    "providers": provider_lock, "dependency_edges": edges,
                    "catalog": thaw(runtime.catalog), "required_calculations": required_calculations,
                    "rule_runtime_fingerprint": runtime.fingerprint,
                    "binding_origins": {"preset": dict(selected_ruleset.get("bindings", {})),
                                        "scenario": dict(selected_scene.get("rules", {}))},
                    "capabilities": {key: sorted(value) for key, value in self.capabilities.items()}}
        payload = {"scenario": selected_scene, "definitions": definitions,
                   "ruleset": selected_ruleset, "rules": rules, "metadata": metadata}
        return SimulationProgram(selected_scene, definitions, selected_ruleset, rules,
                                 dependency_ids, digest(payload), metadata)

    @staticmethod
    def _overrides(overrides):
        if overrides is None:
            return {}
        entries = [overrides] if isinstance(overrides, Mapping) else overrides
        result = {}
        for item in entries:
            if not isinstance(item, Mapping):
                raise CompileError("Each binding overlay must be an object")
            for key, value in item.items():
                if key in result:
                    raise CompileError(f"Conflicting overrides in one scope for {key}")
                if not isinstance(value, str):
                    raise CompileError(f"Override {key}: expected a rule ID")
                result[key] = value
        return result

    def _validate_rules(self, rules, definitions, ruleset, providers):
        from ..rules import RuleRuntime
        runtime = RuleRuntime(rules, bindings=ruleset.get("bindings", {}), catalog=self.catalog,
                              numeric_profile=ruleset.get("numeric_profile"), providers=providers)
        for identifier, definition in rules.items():
            runtime.validate_rule(definition)
            self._validate_expression_fields(definition, runtime.catalog)
        def bindings(value, path):
            if isinstance(value, Mapping):
                for key, child in value.items():
                    if key in {"metadata", "parameters", "payload", "inputs", "expected_blackboard"}:
                        continue
                    if key == "attribute_rules" and isinstance(child, Mapping):
                        for attribute, overrides in child.items():
                            bindings({"rules": overrides}, f"{path}.attribute_rules.{attribute}")
                    elif key in {"rules", "bindings"} and isinstance(child, Mapping):
                        for calculation_id, rule_id in child.items():
                            if rule_id not in rules:
                                raise CompileError(f"{path}.{key}.{calculation_id}: reference {rule_id} is not a calculation rule")
                            if rules[rule_id].get("contract") != calculation_id:
                                raise CompileError(f"{path}.{key}.{calculation_id}: rule {rule_id} belongs to {rules[rule_id].get('contract')}")
                    else:
                        bindings(child, f"{path}.{key}")
            elif isinstance(value, (list, tuple)):
                for child in value:
                    bindings(child, path)
        for key, definition in definitions.items():
            bindings(definition, key)
        return runtime

    @staticmethod
    def _validate_implemented_references(value, path):
        if isinstance(value, Mapping):
            if "dynamic" in value:
                raise CompileError(f"{path}: dynamic reference execution is unsupported in this runtime; declare dependencies with dynamicReferences and use a fixed reference")
            for key, child in value.items():
                if key == "origin" and (value.get("op") == "no_source_damage" or value.get("type") == "periodic_effect_field"): continue
                if key not in {"dynamicReferences", "metadata", "parameters", "payload", "inputs"}:
                    Compiler._validate_implemented_references(child, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                Compiler._validate_implemented_references(child, f"{path}[{index}]")

    @staticmethod
    def _validate_content_expressions(value, path):
        from ..rules import Expression
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == "origin" and (value.get("op") == "no_source_damage" or value.get("type") == "periodic_effect_field"): continue
                if key == "condition" and isinstance(child, str):
                    Expression(child)
                elif key not in {"metadata", "parameters", "dynamicReferences", "payload", "inputs"}:
                    Compiler._validate_content_expressions(child, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                Compiler._validate_content_expressions(child, f"{path}[{index}]")

    @staticmethod
    def _validate_expression_fields(definition, catalog):
        """Catch misspelled declared input/parameter names before simulation."""
        contract = catalog["contracts"][definition["contract"]]
        declarations = contract.get("inputs", [])
        input_names = set(declarations) if isinstance(declarations, Mapping) else {entry["name"] for entry in declarations}
        parameter_names = set(definition.get("parameters", {}))
        def check(expression):
            tree = ast.parse(expression, mode="eval")
            for node in ast.walk(tree):
                name, field = None, None
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    name, field = node.value.id, node.attr
                elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and isinstance(node.slice, ast.Constant):
                    name, field = node.value.id, node.slice.value
                if name == "inputs" and field not in input_names:
                    raise CompileError(f"{definition['id']}: expression references undeclared input {field!r}")
                if name == "params" and field not in parameter_names:
                    raise CompileError(f"{definition['id']}: expression references undeclared parameter {field!r}")
        implementation = definition["implementation"]
        if implementation["type"] == "expression":
            check(implementation["expression"])
        elif implementation["type"] == "graph":
            def check_input(value):
                if isinstance(value, str):
                    check(value)
                elif isinstance(value, Mapping):
                    if set(value) == {"literal"}:
                        return
                    for child in value.values():
                        check_input(child)
                elif isinstance(value, (list, tuple)):
                    for child in value:
                        check_input(child)
            for node in implementation.get("nodes", []):
                if "expression" in node:
                    check(node["expression"])
                for value in node.get("inputs", {}).values():
                    check_input(value)
            check(implementation["output"])

    @staticmethod
    def _validate_reference_kinds(definitions):
        expected = {"attachment": {"attachment"}, "target_buff": {"buff"}, "source_recovery_buff": {"buff"}, "projectile_definition": {"projectile"}, "definition": {"entity"}, "ability": {"ability"}, "buff": {"buff"},
                    "trigger_selector": {"selector"}, "selector": {"selector"}, "machine": {"behavior"}, "policy": {"policy", "rule", "calculation_rule"},
                    "ruleset": {"ruleset"}, "exit_rule": {"rule", "calculation_rule"}, "recovery_rule": {"rule", "calculation_rule"},
                    "interval_rule": {"rule", "calculation_rule"}, "duration_rule": {"rule", "calculation_rule"},
                    "rule": {"rule", "calculation_rule"}, "amount_rule": {"rule", "calculation_rule"}}
        def walk(value, path, root_kind=None, location=()):
            if isinstance(value, Mapping):
                if value.get("op") in {"set_ability_cooldown", "interrupt_ability"} or value.get("mode")=="synchronous_interrupt":
                    ident = value.get("ability")
                    if ident not in definitions or definitions[ident].get("kind") != "ability":
                        raise CompileError(path+": lifecycle relation requires an already reachable possessed ability")
                if value.get("op") == "buff_application":
                    for ident in value["allowed"]:
                        if definitions[ident].get("kind") != "buff": raise CompileError(path+": allowed application ID must be Buff")
                    if definitions[value["application_rule"]].get("contract") != "buff.application": raise CompileError(path+": incompatible application contract")
                for key, child in value.items():
                    if key == "origin" and (value.get("op") == "no_source_damage" or value.get("type") == "periodic_effect_field"): continue
                    if key=='blackboard' and location[-3:]==('map','tiles','[]'):
                        continue
                    if key in {"metadata", "parameters", "payload", "inputs", "expected_blackboard"}:
                        continue
                    if key in expected and isinstance(child, str) and child in definitions:
                        wanted = {"control"} if key == "definition" and value.get("kind") == "control" and "op" not in value else expected[key]
                        if definitions[child].get("kind") not in wanted:
                            raise CompileError(f"{path}.{key}: {child} has incompatible kind {definitions[child].get('kind')}")
                    elif key in {"abilities", "recovery_freeze_abilities", "interrupt_abilities"} and isinstance(child, (list, tuple)):
                        for reference in child:
                            if definitions[reference].get("kind") != "ability":
                                raise CompileError(f"{path}.abilities: {reference} is not an ability")
                    elif key == "initial" and path.endswith((".buffs", ".buff_container")) and isinstance(child, (list, tuple)):
                        for reference in child:
                            if definitions[reference].get("kind") != "buff":
                                raise CompileError(f"{path}.initial: {reference} is not a Buff definition")
                    if key == "growth" and isinstance(child, Mapping):
                        for attribute, spec in child.items():
                            reference = spec.get("rule")
                            if reference in definitions and definitions[reference].get("contract") != "attributes.growth":
                                raise CompileError(f"{path}.growth.{attribute}: rule {reference} is not an attributes.growth rule")
                    expected_contracts = {"exit_rule": "lifecycle.exit", "active_rule": "buff.applicability", "control_rule": "buff.applicability", "recovery_freeze_rule": "resource.recovery_freeze", "recovery_rule": "resource.recovery", "amount_rule": "resource.recovery", "capacity_rule": "resource.capacity", "bounds_rule": "resource.bounds", "interval_rule": "buff.interval" if root_kind == "buff" else "time.interval", "duration_rule": "buff.duration" if root_kind == "buff" else "ability.duration"}
                    if value.get('op')=='elemental_damage':expected_contracts['amount_rule']='elemental.packet'
                    if key in expected_contracts and isinstance(child, str) and child in definitions:
                        if definitions[child].get("contract") != expected_contracts[key]:
                            raise CompileError(f"{path}.{key}: rule {child} belongs to {definitions[child].get('contract')}, expected {expected_contracts[key]}")
                    walk(child, f"{path}.{key}", root_kind,location+(key,))
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child, path, root_kind,location+('[]',))
        for identifier, definition in definitions.items():
            walk(definition, identifier, definition.get("kind"))
            if definition.get("kind") == "buff" and definition.get("aura"):
                member = definitions[definition["aura"]["buff"]]
                if member.get("aura") or "duration_seconds" in member or member.get("duration_rule"):
                    raise CompileError(f"{identifier}.aura: member must be a permanent non-emitter Buff")
                if definition['aura'].get('lease_policy'):
                    policy=member.get('stacking',{})
                    lease_stacks=definition['aura']['lease_policy'].get('modifier_stacks')
                    allowed=(policy.get('mode')=='add' and policy.get('max_stacks')==lease_stacks['maximum']) if lease_stacks else (policy.get('mode','refresh')=='refresh' and type(policy.get('max_stacks',1)) is int and policy.get('max_stacks',1)==1)
                    if not allowed or policy.get('policy') or ('duration_seconds' in member.get('parameters',{}) and member['parameters']['duration_seconds']!=0):
                        raise CompileError(f"{identifier}.aura: shared child must be nonstacking permanent refresh max1")
                elif member.get("stacking", {}).get("mode") != "independent":
                    raise CompileError(f"{identifier}.aura: member requires independent stacking")

    @staticmethod
    def _validate_entity_abilities(definitions, scenario=None):
        from .schemas import validate_recovery
        def check_freeze(resources, owned, path):
            for name, spec in resources.items():
                validate_recovery(spec, path+".resources."+name)
                freeze_rule = spec.get("recovery_freeze_rule") or spec.get("rules", {}).get("resource.recovery_freeze")
                if freeze_rule and definitions[freeze_rule].get("metadata", {}).get("recovery_freeze_authority") != "final_override":
                    raise CompileError(f"{path}.resources.{name}: freeze rule must declare metadata.recovery_freeze_authority=final_override")
                for field, entries in (("recovery_freeze_abilities", spec.get("recovery_freeze_abilities", [])),
                                       ("interrupt_abilities", spec.get("recovery", {}).get("interrupt_abilities", []))):
                    for identifier in entries:
                        if identifier not in owned:
                            raise CompileError(f"{path}.resources.{name}.{field}: actor does not own {identifier}")
        for identifier, entity in definitions.items():
            if entity.get("kind") != "entity":
                continue
            resources = entity.get("components", {}).get("resources", {})
            stock=entity.get("components",{}).get("deployable",{}).get("stock")
            if stock is not None:
                if stock["resource"] not in (scenario or {}).get("resources",{}):raise CompileError(identifier+": deployment stock resource is absent")
                if stock.get("rule") and definitions[stock["rule"]].get("contract")!="resource.cost":raise CompileError(identifier+": stock rule must implement resource.cost")
            check_freeze(resources, entity.get("components", {}).get("abilities", []), identifier)
            if "rebirth" in entity.get("components",{}):
                from ..domains.rebirth import validate
                validate(entity["components"]["rebirth"],entity["components"],definitions)
            for ability_id in entity.get("components", {}).get("abilities", []):
                ability = definitions[ability_id]
                recovery = ability.get("activation", {}).get("parameters", {})
                legacy_resource = recovery.get("sp_resource")
                if legacy_resource and recovery.get("recovery_per_attack"):
                    driver = resources.get(legacy_resource, {}).get("recovery", {})
                    if (driver.get("mode") == "event" and driver.get("event") == "attack.accepted"
                            and driver.get("owner_role", "source") in ("source", "any")):
                        raise CompileError(f"{identifier} -> {ability_id}: duplicate legacy and event attack recovery for {legacy_resource}")
                for cost in ability.get("activation", {}).get("costs", []):
                    if cost.get("owner", "source") == "source" and cost["resource"] not in resources:
                        raise CompileError(f"{identifier} -> {ability_id}: ability cost uses undefined resource {cost['resource']}")
                    if cost.get("owner") == "battle" and cost["resource"] not in (scenario or {}).get("resources", {}):
                        raise CompileError(f"{identifier} -> {ability_id}: battle cost uses undefined resource {cost['resource']}")
                    if "rule" in cost and definitions[cost["rule"]].get("contract") != "resource.cost":
                        raise CompileError(f"{identifier} -> {ability_id}: cost rule {cost['rule']} does not implement resource.cost")
                visited_buffs = set()
                def check_effect(effect):
                    if effect.get("op") == "modify_resource" and effect.get("target", "selected") in ("source", "self"):
                        if effect["resource"] not in resources:
                            raise CompileError(f"{identifier} -> {ability_id}: source effect uses undefined resource {effect['resource']}")
                    if effect.get("op") == "apply_buff" and effect.get("target", "selected") in ("source", "self"):
                        buff_id = effect["buff"]
                        if buff_id not in visited_buffs:
                            visited_buffs.add(buff_id)
                            for child in definitions[buff_id].get("on_remove", ()):
                                check_effect(child)
                    for key in ("on_success", "on_failure", "effects"):
                        for child in effect.get(key, []):
                            check_effect(child)
                    if "effect" in effect:
                        check_effect(effect["effect"])
                for entry in ability.get("timeline", []):
                    if "effect" in entry:
                        check_effect(entry["effect"])
                    for effect in entry.get("effects", []):
                        check_effect(effect)
                for effect in ability.get("activation", {}).get("on_start", []):
                    check_effect(effect)
        scene = scenario or {}
        check_freeze(scene.get("resources", {}), [], scene.get("id", "scenario"))
        instances = list(scene.get("initialEntities", []))+list(scene.get("waves", []))
        for wave in scene.get("timeline", {}).get("waves", []):
            for fragment in wave["fragments"]:
                instances.extend(a["spawn"] for a in fragment["actions"] if a["kind"] == "spawn")
        for item in instances:
            base = definitions[item["definition"]].get("components", {})
            actual = merge(base, item.get("components", {}))
            from ..domains.deployment import cooldown_start
            cooldown_start(actual.get('deployable',{}))
            if "selection_state" in actual:
                from ..domains.selection import validate_state
                validate_state(actual["selection_state"], (item.get("instanceAlias") or item["definition"])+".selection_state")
            check_freeze(actual.get("resources", {}), actual.get("abilities", []), item.get("instanceAlias") or item["definition"])
            if "rebirth" in actual:
                from ..domains.rebirth import validate
                validate(actual["rebirth"],actual,definitions)
