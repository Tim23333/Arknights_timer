"""Schema-directed references, including bounded dynamic references."""
from collections.abc import Mapping
from .repository import ContentError


REFERENCE_KEYS = {"trigger_selector","attachment", "target_buff", "source_recovery_buff","projectile_definition", "definition", "ability", "buff", "selector", "machine", "policy",
                  "rule", "ruleset", "extends", "prototype", "behavior"}
REFERENCE_LISTS = {"cards","abilities", "requires", "dependencies", "externals", "allowed", "roster", "recovery_freeze_abilities", "interrupt_abilities", "retain_buffs"}


def references(value, path="definition", calculation_bindings=None):
    result = set()
    def visit(item, location, key=None):
        if isinstance(item, Mapping):
            if item.get('op') == 'restart_behavior':
                from ..domains.behavior_restart import validate
                try:options=validate(item)
                except ValueError as error:raise ContentError(location+': '+str(error)) from error
                # An ability may explicitly restart its own owned cast; the
                # enclosing definition is already reachable, not a content cycle.
                result.update(aid for aid in options['abilities'] if aid!=value.get('id'))
            if item.get("op") == "apply_terrain_overlay":
                terrain_rule = item.get("parameters", {}).get("rule")
                if terrain_rule is not None:
                    if not isinstance(terrain_rule, str) or not terrain_rule:
                        raise ContentError(f"{location}.parameters.rule: terrain rule ID required")
                    result.add(terrain_rule)
            if item.get("action", item.get("type")) == "deploy" and isinstance(item.get("entity"), str):
                result.add(item["entity"])
            if "dynamic" in item:
                allowed = item.get("allowed")
                if not isinstance(allowed, list) or not allowed or not all(isinstance(x, str) for x in allowed):
                    raise ContentError(f"{location}: dynamic reference requires a nonempty allowed ID list")
                result.update(allowed)
            metadata = item.get("metadata", {})
            if isinstance(metadata, Mapping):
                required_calculations = metadata.get("calculation_dependencies", [])
                if not isinstance(required_calculations, (list, tuple)) or not all(isinstance(x, str) for x in required_calculations):
                    raise ContentError(f"{location}.metadata.calculation_dependencies: expected calculation IDs")
                for calculation in required_calculations:
                    binding = (calculation_bindings or {}).get(calculation)
                    if binding is None:
                        raise ContentError(f"{location}.metadata.calculation_dependencies: missing default rule binding for {calculation}")
                    result.add(binding)
            for name, child in item.items():
                if name=='ability' and (item.get('op') in {'set_ability_cooldown','interrupt_ability'} or item.get('mode')=='synchronous_interrupt'):
                    # Lifecycle relation requires an already possessed ability,
                    # not a recursive content dependency through its own Buff.
                    continue
                if name=='blackboard' and key=='tiles' and '.map.tiles[' in location:
                    continue
                if key == "timeline" and name == "policy":
                    # Timeline's validated scheduling policy is an enum, unlike
                    # entity/lifecycle/buff policy definition references.
                    continue
                if name == "origin" and (item.get("op") == "no_source_damage" or item.get("type") == "periodic_effect_field"):
                    continue
                if name in {"metadata", "parameters", "payload", "inputs", "expected_blackboard"}:
                    # These are data/expression records, not schema references.
                    # Providers declaring generated content use dependencies or
                    # bounded dynamicReferences instead of accidental key scans.
                    continue
                if name == "initial" and key in {"buffs", "buff_container"}:
                    if not isinstance(child, (list, tuple)) or not all(isinstance(ref, str) for ref in child):
                        raise ContentError(f"{location}.initial: expected Buff ID strings")
                    result.update(child)
                elif name == "calculation" and isinstance(child, str):
                    binding = (calculation_bindings or {}).get(child)
                    if binding is None:
                        raise ContentError(f"{location}.calculation: missing default rule binding for {child}")
                    result.add(binding)
                elif name == "attribute_rules" and isinstance(child, Mapping):
                    for attribute, bindings in child.items():
                        if not isinstance(bindings, Mapping) or not all(isinstance(ref, str) for ref in bindings.values()):
                            raise ContentError(f"{location}.attribute_rules.{attribute}: expected calculation-to-rule bindings")
                        result.update(bindings.values())
                elif name in {"rules", "bindings"} and isinstance(child, Mapping):
                    for contract, rule in child.items():
                        if not isinstance(rule, str):
                            raise ContentError(f"{location}.{name}.{contract}: rule reference must be an ID")
                        result.add(rule)
                elif name in REFERENCE_KEYS or name.endswith("_rule"):
                    if isinstance(child, str):
                        # Remove only the already-instantiated current Buff;
                        # construction/apply edges remain real dependencies.
                        if not (name == "buff" and item.get("op") == "remove_buff" and child == value.get("id") and value.get("kind") == "buff"):
                            result.add(child)
                    elif isinstance(child, Mapping):
                        visit(child, f"{location}.{name}", name)
                    elif child is not None:
                        raise ContentError(f"{location}.{name}: reference must be an ID or declared dynamic reference")
                elif name in REFERENCE_LISTS and isinstance(child, (list, tuple)):
                    for ref in child:
                        if not isinstance(ref, str):
                            raise ContentError(f"{location}.{name}: references must be IDs")
                        result.add(ref)
                else:
                    visit(child, f"{location}.{name}", name)
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                visit(child, f"{location}[{index}]", key)
    visit(value, path)
    return result


def closure(roots, get_definition, calculation_bindings=None):
    visited, active, edges = set(), [], {}
    def walk(identifier):
        if identifier in active:
            index = active.index(identifier)
            raise ContentError("Dependency cycle: " + " -> ".join(active[index:] + [identifier]))
        if identifier in visited:
            return
        active.append(identifier)
        try:
            definition = get_definition(identifier)
        except KeyError as exc:
            raise ContentError("Missing reference: " + " -> ".join(active)) from exc
        dependencies = sorted(references(definition, identifier, calculation_bindings))
        edges[identifier] = dependencies
        for dependency in dependencies:
            walk(dependency)
        active.pop()
        visited.add(identifier)
    for identifier in sorted(set(roots)):
        walk(identifier)
    return tuple(sorted(visited)), edges
