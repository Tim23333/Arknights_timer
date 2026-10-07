"""Explicit precedence and ownership, independent of module/import order."""
from collections.abc import Mapping

from .errors import BindingConflictError, MissingRuleError, RuleError


def merge_layer(value, label):
    if value is None:
        return {}
    if isinstance(value, Mapping):
        # {'bindings': ...} is a useful entity/scenario view.
        if "bindings" in value and isinstance(value["bindings"], (Mapping, list, tuple)):
            value = value["bindings"]
        else:
            merged = dict(value)
            if not all(isinstance(key, str) and isinstance(rule, str) and rule for key, rule in merged.items()):
                raise RuleError(f"{label}: bindings require calculation IDs and nonempty rule IDs")
            return merged
    if isinstance(value, (tuple, list)):
        merged = {}
        for overlay in value:
            if not isinstance(overlay, Mapping):
                raise RuleError(f"{label}: rule overrides must be mappings")
            for calculation, rule in overlay.items():
                if not isinstance(calculation, str) or not isinstance(rule, str) or not rule:
                    raise RuleError(f"{label}: bindings require calculation IDs and nonempty rule IDs")
                if calculation in merged and merged[calculation] != rule:
                    raise BindingConflictError(f"{label}: conflicting overrides for {calculation}: {merged[calculation]} vs {rule}")
                merged[calculation] = rule
        return merged
    raise RuleError(f"{label}: bindings must be mappings or mapping lists")


class BindingResolver:
    def __init__(self, bindings, catalog):
        self.bindings = merge_layer(bindings, "preset")
        self.catalog = catalog["contracts"]

    def resolve(self, calculation, scope=None, explicit=None):
        if calculation not in self.catalog:
            raise MissingRuleError(f"Unknown calculation contract: {calculation}")
        owner = self.catalog[calculation].get("owner", "owner")
        layers = [("preset", self.bindings)]
        if scope is not None:
            if not isinstance(scope, Mapping):
                raise RuleError("scope must be a mapping")
            layers.append(("scenario", merge_layer(scope.get("scenario"), "scenario")))
            if owner in ("source", "target", "owner"):
                layers.append((owner, merge_layer(scope.get(owner, scope.get("owner_entity")), owner)))
            for name in ("component", "attribute_or_resource", "ability", "effect", "invocation"):
                layers.append((name, merge_layer(scope.get(name), name)))
        selected, origin, overrides = None, None, []
        for name, mapping in layers:
            if calculation in mapping:
                selected, origin = mapping[calculation], name
                overrides.append({"scope": name, "rule_id": selected})
        if explicit is not None:
            selected, origin = explicit, "explicit"
            overrides.append({"scope": "explicit", "rule_id": selected})
        if not isinstance(selected, str) or not selected:
            raise MissingRuleError(f"No rule bound for required calculation: {calculation}")
        return selected, {"owner": owner, "origin": origin, "overrides": overrides}
