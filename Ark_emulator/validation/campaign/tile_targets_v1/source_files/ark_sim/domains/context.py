"""Read-only evaluations and atomic write helpers shared by domain systems."""
from ark_sim.contracts import Intent, thaw, freeze
from ark_sim.rules import RuleRuntime
from .providers import BUILTIN_PROVIDERS
from collections.abc import Mapping
from ark_sim.contracts.models import FrozenMapping, FrozenTuple


def compact_trace(value, memo=None):
    """Keep operands and results while avoiding repeated causal snapshots."""
    memo = {} if memo is None else memo
    if isinstance(value, (Mapping, list, tuple)) and id(value) in memo:
        return memo[id(value)]
    if isinstance(value, Mapping):
        result = {}
        for key, child in value.items():
            if key in ("source_snapshot", "target_snapshots", "launch_snapshot", "launch_target_snapshots"):
                continue
            if key == "context" and isinstance(child, Mapping):
                result[key] = {name: compact_trace(item, memo) for name, item in child.items()
                    if name not in ("source", "target", "owner", "entity_states")}
                for name in ("source", "target", "owner"):
                    if isinstance(child.get(name), Mapping):
                        result[key][name+"_id"] = child[name].get("id")
            else:
                result[key] = compact_trace(child, memo)
        unchanged = type(value) is FrozenMapping and len(result) == len(value) and all(result[k] is child for k, child in value.items())
        output = value if unchanged else freeze(result)
        memo[id(value)] = output
        return output
    if isinstance(value, (list, tuple)):
        items = [compact_trace(item, memo) for item in value]
        unchanged = type(value) is FrozenTuple and all(new is old for new, old in zip(items, value))
        output = value if unchanged else freeze(items)
        memo[id(value)] = output
        return output
    return value


class DomainError(ValueError):
    pass


class RuntimeContext:
    def __init__(self, program, session, providers=None):
        self.program, self.session = program, session
        self.providers = dict(BUILTIN_PROVIDERS, **(providers or {}))
        required = set(program.metadata.get("providers", {}))
        if "providers" in program.metadata:
            self.providers = {key: self.providers[key] for key in required}
        self.rules = RuleRuntime(program.rules, program.ruleset.get("bindings", {}),
                                 catalog=program.metadata.get("catalog"),
                                 numeric_profile=program.ruleset.get("numeric_profile"),
                                 providers=self.providers)
        expected = program.metadata.get("rule_runtime_fingerprint")
        if expected and expected != self.rules.fingerprint:
            raise DomainError("compiled provider/rule identity differs from runtime; recompile with the chosen providers")
        self._base_effect_phase = len(program.ruleset.get("system_order", ())) + 1
        self.attributes = self.resources = self.effects = self.abilities = self.buffs = self.spatial = self.behavior = self.lifecycle = self.timeline = self.terrain = None
        self.controls = None
        self._notifying = 0
        self.last_calculation_event_id = None
        self.projectiles = None
        self.tile_contacts = None
        self.periodic_fields = None
        self.attachments = None

    @property
    def effect_phase(self):
        # Numeric packet stages are opt-in. Ordinary no-profile execution retains
        # exactly its original phase; no source=None relaxation is added here.
        base = self._base_effect_phase
        if self.periodic_fields is not None and self.session._active_key is not None:
            return max(base, self.session._active_key[1])
        return base

    @effect_phase.setter
    def effect_phase(self, value):
        self._base_effect_phase = value

    def entity(self, ref):
        return self.session.world.get(ref)

    def capture_view(self, ref):
        view = thaw(self.entity(ref))
        view["sampled_at"] = self.session.time
        runtime = view["components"].get("runtime", {})
        for cast in runtime.get("casts", {}).values():
            for key in ("source_snapshot", "target_snapshots", "launch_snapshot", "launch_target_snapshots"):
                cast.pop(key, None)
        return view

    def definition(self, ref):
        return self.program.definitions.get(self.entity(ref)["definition_id"], {})

    def get(self, ref, path, default=None):
        value = self.entity(ref)["components"]
        for part in path:
            if not isinstance(value, Mapping) or part not in value:
                return default
            value = value[part]
        return thaw(value)

    def set(self, ref, path, value):
        if path and path[0]=="selection_state" and self.buffs is not None and self.buffs.applicability.enabled:
            with self.session.atomic():
                result=self.session.commit([Intent("set",self.session.world.resolve(ref),tuple(path),value)])
                self.buffs.reconcile();return result
        return self.session.commit([Intent("set", self.session.world.resolve(ref), tuple(path), value)])

    def route_hidden(self, ref):
        return bool(self.get(ref, ("spatial", "route_hidden"), False))

    def visibility_policy(self, ref):
        return self.get(ref, ("spatial", "route", "transition_policy", "parameters"), {})

    def active(self, ref):
        return self.alive(ref) and bool(self.get(ref, ('runtime', 'active'), True))

    def selectable(self, ref):
        if 'tile_field_owner' in self.entity(ref)['tags'] or self.get(ref,("tile_occupancy","targetable"),True) is False:
            return False
        return self.active(ref) and not self.route_hidden(ref)

    def effect_target_available(self, ref):
        if 'tile_field_owner' in self.entity(ref)['tags'] or self.get(ref,("tile_occupancy","targetable"),True) is False:
            return False
        return bool(self.get(ref, ('runtime', 'active'), True)) and (not self.route_hidden(ref) or self.visibility_policy(ref).get("hidden_effects", "reject") == "allow")

    def aura_available(self, ref):
        return bool(self.get(ref, ('runtime', 'active'), True)) and (not self.route_hidden(ref) or self.visibility_policy(ref).get("hidden_auras", "suspend") == "retain")

    def state(self):
        return self.get("system/battle", ("state",))

    def state_update(self, **values):
        state = self.state()
        state.update(values)
        self.set("system/battle", ("state",), state)

    def definition_bindings(self, ref):
        return {**dict(self.definition(ref).get("rules", {})),
                **self.get(ref, ("runtime", "rule_bindings"), {})} if ref is not None else {}

    def calc(self, calculation, inputs, *, source=None, target=None, owner=None,
             ability=None, effect=None, component=None, local=None, rule_id=None, extra=None, scope_extra=None):
        scope = {"scenario": self.program.scenario.get("rules", {}),
                 "source": self.definition_bindings(source),
                 "target": self.definition_bindings(target),
                 "owner": self.definition_bindings(owner),
                 "component": component or {}, "attribute_or_resource": local or {},
                 "ability": (ability or {}).get("rules", {}),
                 "effect": (effect or {}).get("rules", {})}
        scope.update(scope_extra or {})
        context = {"time": self.session.time, "seconds": self.session.time*self.session.quantum,
                   "quantum": self.session.quantum,
                   "source": self.entity(source) if source is not None else {},
                   "target": self.entity(target) if target is not None else {},
                   "owner": self.entity(owner) if owner is not None else {},
                   **(extra or {})}
        result = self.rules.evaluate(calculation, inputs, scope=scope, rule_id=rule_id, context=context)
        if self.program.ruleset.get("parameters", {}).get("trace_mode", "compact") == "full":
            trace = result.trace
        else:
            trace = compact_trace(result.trace)
        self.last_calculation_event_id = self.session.emit("calculation", {"calculation_id": calculation, "rule_id": result.rule_id,
                         "source": source, "target": target, "value": result.value,
                         "trace": trace})
        return thaw(result.value)

    def quantize(self, seconds):
        return self.calc("time.quantize", {"seconds": seconds, "quantum": self.session.quantum,
                         "rounding": {"mode": "ceil"}})

    def provider(self, name, inputs, params=None, context=None):
        record = self.providers.get(name)
        if record is None:
            raise DomainError(f"unavailable provider {name}")
        function = record.get("callable") if isinstance(record, dict) else record
        output = function(freeze(inputs), freeze(params or {}), freeze(context or {}))
        trace = {"provider": name, "inputs": inputs, "output": output}
        if self.program.ruleset.get("parameters", {}).get("trace_mode", "compact") != "full":
            trace = compact_trace(trace)
        self.session.emit("policy", trace)
        return thaw(output)

    def emit(self, event, payload, cause=None):
        if (self.resources is not None and self.resources.has_custom_freeze_rules) or (self.buffs is not None and (self.buffs.toggles.enabled or self.buffs.applicability.enabled)):
            with self.session.atomic():
                return self._emit_domain(event, payload, cause)
        return self._emit_domain(event, payload, cause)

    def _emit_domain(self, event, payload, cause=None):
        if self.buffs is not None:self.buffs.applicability.reconcile()
        event_id = self.session.emit(event, payload, cause=cause)
        if self.buffs is not None:self.buffs.toggles.pulse(event, payload)
        if self.buffs is not None:
            recipients = self.resources.event_snapshot(event, payload) if self.resources is not None else []
            self.session.schedule("event_reaction", {"event": event, "payload": payload, "cause": event_id,
                                  "resource_recipients": recipients, "buff_recovery_snapshot": self.buffs.recovery_snapshot(event)},
                                  self.session.time, phase=self.effect_phase)
        return event_id

    def react(self, session, payload):
        if self.periodic_fields is not None or self.attachments is not None:
            with session.atomic():
                return self._react(session, payload)
        return self._react(session, payload)

    def _react(self, session, payload):
        self.resources.notify(payload["event"], payload["payload"], payload["cause"], payload.get("resource_recipients", []))
        self.buffs.notify(payload["event"], payload["payload"], payload["cause"], payload.get("buff_recovery_snapshot"))
        self.abilities.notify(payload["event"], payload["payload"], payload["cause"])

    def alive(self, ref):
        return bool(self.get(ref, ("runtime", "alive"), True))

    def attribute_role(self, role):
        return self.program.ruleset.get("parameters", {}).get("attribute_roles", {}).get(role, role)

    def role_value(self, ref, role):
        key = self.attribute_role(role)
        base = self.get(ref, ("attributes", "base"), {})
        if key not in base:
            defaults = self.program.ruleset.get("parameters", {}).get("attribute_defaults", {})
            if key not in defaults:
                raise DomainError(f"{ref} has no attribute for {role}: {key}")
            return defaults[key]
        return self.attributes.value(ref, key)

    def health_resource(self, ref):
        specs = self.get(ref, ("resources",), {})
        for key, value in specs.items():
            if value.get("spec", {}).get("role") == "health":
                return key
        configured = self.program.ruleset.get("parameters", {}).get("health_resource")
        if configured in specs:
            return configured
        raise DomainError(f"{ref} has no declared health resource")
