"""Explain the compiled dependency closure and actual rule binding inputs."""
from ..contracts.models import thaw


def explain_dependencies(program):
    edges = thaw(program.metadata.get("dependency_edges", {}))
    incoming = {identifier: [] for identifier in program.dependency_ids}
    for source, dependencies in edges.items():
        for dependency in dependencies:
            incoming.setdefault(dependency, []).append(source)
    return {"scenario": program.scenario["id"], "fingerprint": program.fingerprint,
            "count": len(program.dependency_ids), "providers": thaw(program.metadata.get("providers", {})),
            "definitions": [{"id": identifier, "kind": program.definitions[identifier]["kind"],
                              "requires": edges.get(identifier, []), "required_by": sorted(incoming[identifier])}
                             for identifier in program.dependency_ids]}


def explain_bindings(program):
    scopes = []
    def walk(definition_id, value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"metadata", "parameters", "inputs", "payload"}:
                    continue
                if key == "attribute_rules" and isinstance(child, dict):
                    for attribute, bindings in child.items():
                        scopes.append({"definition": definition_id, "path": f"{path}.attribute_rules.{attribute}", "bindings": bindings})
                elif key == "rules" and isinstance(child, dict):
                    scopes.append({"definition": definition_id, "path": f"{path}.rules", "bindings": child})
                else:
                    walk(definition_id, child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(definition_id, child, f"{path}[{index}]")
    for identifier, definition in program.definitions.items():
        walk(identifier, thaw(definition), identifier)
    return {"ruleset": program.ruleset["id"], "preset": thaw(program.ruleset.get("bindings", {})),
            "scenario": thaw(program.scenario.get("rules", {})),
            "scoped": {identifier: thaw(definition["rules"]) for identifier, definition in program.definitions.items()
                       if definition.get("rules") and identifier != program.scenario["id"]},
            "scopes": scopes}


def inspect_program(program):
    return {"dependencies": explain_dependencies(program), "bindings": explain_bindings(program),
            "packages": thaw(program.metadata.get("packages", [])),
            "numeric_profile": thaw(program.ruleset.get("numeric_profile", {})),
            "system_order": thaw(program.ruleset.get("system_order", []))}
