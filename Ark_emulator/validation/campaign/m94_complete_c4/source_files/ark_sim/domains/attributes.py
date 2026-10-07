"""Attribute growth and layers delegate numeric results to rule contracts."""
from ark_sim.contracts.models import FrozenMapping, digest


class _ViewIdentity:
    """Identity comparison that also retains the immutable view."""
    __slots__ = ("view",)

    def __init__(self, view):
        self.view = view

    def __hash__(self):
        return id(self.view)

    def __eq__(self, other):
        return type(other) is _ViewIdentity and self.view is other.view


class AttributeSystem:
    def __init__(self, context):
        self.ctx = context
        self.cache = {}
        self._cache_time = None
        self._cache_epoch = None

    def initialize(self, definition, components, instance_rules=None):
        attrs = components.setdefault("attributes", {"base": {}})
        attrs.setdefault("base", {})
        attrs.setdefault("modifiers", [])
        growth = definition.get("growth", attrs.get("growth", {}))
        prototype = {"definition_id": definition["id"], "components": components}
        owner_rules = {**definition.get("rules", {}), **(instance_rules or {})}
        for stat, spec in growth.items():
            attrs["base"][stat] = self.ctx.calc("attributes.growth", {
                "base": attrs["base"][stat], "level": spec["level"],
                "growth_parameters": spec.get("parameters", {})}, rule_id=spec.get("rule"),
                component=attrs.get("rules", {}), local=attrs.get("attribute_rules", {}).get(stat, {}),
                scope_extra={"owner": owner_rules},
                extra={"attribute": stat, "owner_definition": definition,
                       "owner": prototype, "source": prototype})

    def value(self, ref, stat, *, ability=None, effect=None, snapshot=None):
        now, epoch = self.ctx.session.time, getattr(self.ctx.session, "cache_epoch", 0)
        if self._cache_time != now or self._cache_epoch != epoch:
            self.cache.clear()
            self._cache_time, self._cache_epoch = now, epoch
        live = self.ctx.entity(ref)
        entity = snapshot if snapshot is not None else live
        # Caller-owned mutable historical dictionaries are never memoized.
        # Live views come from World's isolated snapshot API. Own deep-frozen
        # historical views can safely share identity across repeated reads.
        reusable = snapshot is None or snapshot is live or type(snapshot) is FrozenMapping
        scope_key = digest({"ability": ability or {}, "effect": effect or {}}) if ability or effect else None
        key = (_ViewIdentity(entity), _ViewIdentity(live), stat, scope_key, self.ctx.rules.fingerprint)
        if reusable and key in self.cache:
            value, original_event = self.cache[key]
            self.ctx.session.emit("calculation.cached", {"calculation_id": "attributes.effective",
                "owner": live.get("id"), "attribute": stat, "value": value,
                "source_event_id": original_event}, cause=original_event)
            return value
        component = entity["components"].get("attributes", {})
        base = component.get("base", {})
        if stat not in base:
            raise ValueError(f"attribute {stat!r} is absent on {entity['definition_id']}")
        modifiers = [m for m in component.get("modifiers", ()) if m["attribute"] == stat]
        layers = component["layers"] if "layers" in component else self.ctx.program.ruleset.get("attribute_layers", ())
        value = self.ctx.calc("attributes.effective", {"base": base[stat],
             "modifier_layers": modifiers, "order": [{"layer": layer} for layer in layers]}, owner=ref,
             component=component.get("rules", {}), local=component.get("attribute_rules", {}).get(stat, {}),
             ability=ability, effect=effect,
             extra={"owner": entity, "source": entity, "attribute": stat,
                    "attribute_sample_time": entity.get("sampled_at", now)})
        if reusable:
            self.cache[key] = (value, getattr(self.ctx, "last_calculation_event_id", None))
        return value

    def values(self, ref, *, ability=None, effect=None, snapshot=None):
        entity = snapshot or self.ctx.entity(ref)
        return {key: self.value(ref, key, ability=ability, effect=effect, snapshot=entity)
                for key in entity["components"].get("attributes", {}).get("base", {})}
