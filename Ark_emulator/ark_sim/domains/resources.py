"""Generic named resources and atomic multi-resource payment plans."""
import math
import ast
from collections.abc import Mapping
from ark_sim.contracts import Intent, digest
from ark_sim.contracts.models import FrozenTuple
from ark_sim.rules import evaluate_expression
from ark_sim.rules import MissingRuleError


class ResourceSystem:
    def __init__(self, context):
        self.ctx = context
        self._capacity_parameter_rules = {}
        def configured(value):
            if isinstance(value, Mapping):
                if value.get("recovery_freeze_rule") or "resource.recovery_freeze" in value.get("rules", {}): return True
                return any(configured(v) for k, v in value.items() if k not in {"metadata", "parameters", "payload"})
            return isinstance(value, (list, tuple, FrozenTuple)) and any(configured(v) for v in value)
        self.has_custom_freeze_rules = configured(getattr(context.program, "definitions", {})) or configured(getattr(context.program, "scenario", {}))

    def current(self, ref, resource):
        value = self.ctx.get(ref, ("resources", resource))
        if value is None:
            raise ValueError(f"resource {resource!r} is absent on {ref}")
        return value["current"]

    def capacity_snapshot(self, ref):
        return {key: self.capacity(ref, key) for key in self.ctx.get(ref, ("resources",), {})}

    @staticmethod
    def _dynamic_capacity(spec):
        return bool(spec.get("capacity_attribute") or spec.get("capacity_rule") or "resource.capacity" in spec.get("rules", {}))

    def _capacity_poll_required(self, ref, spec):
        scope = self._capacity_scope(ref, spec)
        rule_id = spec.get("capacity_rule") or self.ctx.rules.resolver.resolve("resource.capacity", scope)[0]
        implementation = self.ctx.rules.rules[rule_id]["implementation"]
        if implementation["type"] != "expression":
            return True
        if rule_id not in self._capacity_parameter_rules:
            tree = ast.parse(implementation["expression"], mode="eval")
            parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
            parameter_only = True
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in {"context", "ctx"}:
                    parameter_only = False
                if isinstance(node, ast.Name) and node.id == "inputs":
                    parent = parents.get(node)
                    known = isinstance(parent, ast.Attribute) and parent.value is node and parent.attr == "capacity_parameters"
                    known |= isinstance(parent, ast.Subscript) and parent.value is node and isinstance(parent.slice, ast.Constant) and parent.slice.value == "capacity_parameters"
                    parameter_only &= known
            self._capacity_parameter_rules[rule_id] = parameter_only
        if not self._capacity_parameter_rules[rule_id]:
            return True
        stat = spec.get("capacity_attribute")
        if not stat:
            return False
        attributes = self.ctx.get(ref, ("attributes",), {})
        scope.update(component=attributes.get("rules", {}),
                     attribute_or_resource=attributes.get("attribute_rules", {}).get(stat, {}))
        attribute_rule = self.ctx.rules.resolver.resolve("attributes.effective", scope)[0]
        effective = self.ctx.rules.rules[attribute_rule]["implementation"]
        if effective["type"] != "provider":
            return True
        descriptor = self.ctx.rules.providers[effective["provider"]][1]
        if descriptor.get("attribute_time_dependency") != "modifiers":
            return True
        aggregator = self.ctx.rules.rules[attribute_rule].get("parameters", {}).get("aggregator", {}).get("provider")
        if aggregator is None or self.ctx.rules.providers[aggregator][1].get("time_dependency") != "static":
            return True
        child_id = self.ctx.rules.resolver.resolve("attributes.modifier_layer", scope)[0]
        child = self.ctx.rules.rules[child_id]["implementation"]
        if child["type"] != "expression" or any(isinstance(n, ast.Name) and n.id in {"context", "ctx"}
                for n in ast.walk(ast.parse(child["expression"], mode="eval"))):
            return True
        return any(m.get("attribute") == stat and m.get("parameters", {}).get("time_curve")
                   for m in attributes.get("modifiers", []))

    def _capacity_signature(self, ref, spec):
        entity = self.ctx.entity(ref)
        attributes = entity["components"].get("attributes", {})
        stat = spec.get("capacity_attribute")
        return digest({"capacity": spec.get("capacity"), "capacity_attribute": stat,
            "capacity_rule": spec.get("capacity_rule"), "rules": spec.get("rules", {}),
            "parameters": spec.get("parameters", {}),
            "base": attributes.get("base", {}).get(stat),
            "modifiers": [m for m in attributes.get("modifiers", []) if m.get("attribute") == stat],
            "owner_rules": self._owner_bindings(ref), "attribute_rules": attributes.get("rules", {}),
            "local_rules": attributes.get("attribute_rules", {}).get(stat, {}),
            "layers": attributes.get("layers", self.ctx.program.ruleset.get("attribute_layers", ())),
            "attribute_parameters": attributes.get("parameters", {})})

    def _owner_bindings(self, ref):
        callback = getattr(self.ctx, "definition_bindings", None)
        return callback(ref) if callback else {}

    def _capacity_scope(self, ref, spec):
        return {"scenario": getattr(self.ctx.program, "scenario", {}).get("rules", {}),
                "owner": self._owner_bindings(ref), "attribute_or_resource": spec.get("rules", {})}

    def _set_resource_state(self, ref, key, field, value):
        self.ctx.session.commit([Intent("set", self.ctx.session.world.resolve(ref), ("resources", key, field), value)])

    def initialize_capacities(self, ref):
        for key, capacity in self.capacity_snapshot(ref).items():
            self._set_resource_state(ref, key, "observed_capacity", capacity)
            self._set_resource_state(ref, key, "capacity_signature", self._capacity_signature(ref, self._spec(ref, key)))

    def sync_capacities(self, ref, previous=None, reason="attributes_changed"):
        with self.ctx.session.atomic():
            self._sync_capacities(ref, previous, reason)

    def _sync_capacities(self, ref, previous, reason):
        for key, data in self.ctx.get(ref, ("resources",), {}).items():
            spec = data["spec"]
            new = self.capacity(ref, key)
            old = (previous or {}).get(key, data.get("observed_capacity", new))
            signature = self._capacity_signature(ref, spec)
            if data.get("capacity_signature") != signature:
                self._set_resource_state(ref, key, "capacity_signature", signature)
            if old == new and data["current"] <= new:
                continue
            try:
                bound = spec.get("capacity_change_rule") or self.ctx.rules.resolver.resolve("resource.capacity_change", self._capacity_scope(ref, spec))[0]
            except MissingRuleError:
                if spec.get("capacity_change_rule") or "capacity_change_mode" in spec.get("parameters", {}):
                    raise
                bound = None
            if bound is None:
                # A minimal ruleset can keep absolute values through its own
                # existing bounds rule. Explicit alternative profiles require
                # a capacity-change binding during capability preflight.
                value = data["current"]
            else:
                value = self.ctx.calc("resource.capacity_change", {"current": data["current"],
                    "old_capacity": old, "new_capacity": new, "parameters": spec.get("parameters", {}),
                    "reason": {"type": reason, "initializing": self.ctx.get(ref, ("runtime", "initializing"), False)}},
                    owner=ref, target=ref, local=spec.get("rules", {}), rule_id=spec.get("capacity_change_rule"))
            self._set_resource_state(ref, key, "observed_capacity", new)
            actual = self.adjust(ref, key, value=value)
            self.ctx.emit("resource.capacity_changed", {"source": ref, "target": ref, "resource": key,
                "old_capacity": old, "new_capacity": new, "delta": actual, "value": self.current(ref, key), "reason": reason})

    def _spec(self, ref, resource):
        data = self.ctx.get(ref, ("resources", resource))
        if data is None:
            raise ValueError(f"resource {resource!r} is absent on {ref}")
        return data["spec"]

    def capacity(self, ref, resource, *, source=None, ability=None, effect=None):
        spec = self._spec(ref, resource)
        attributes = self.ctx.attributes.values(ref, ability=ability, effect=effect)
        parameters = dict(spec.get("parameters", {}))
        if "capacity_attribute" in spec:
            parameters["capacity"] = attributes[spec["capacity_attribute"]]
        elif "capacity" in spec:
            parameters["capacity"] = spec["capacity"]
        # A custom capacity formula may use attributes alone. Missing capacity
        # remains missing, so a preset needing it produces an explicit error.
        return self.ctx.calc("resource.capacity", {"attributes": attributes, "capacity_parameters": parameters},
                            source=source, target=ref, owner=ref, ability=ability, effect=effect,
                            local=spec.get("rules", {}), rule_id=spec.get("capacity_rule"),
                            extra={"resource": resource})

    def change_plan(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):
        current = self.current(ref, resource)
        if value is None and delta is None:
            raise ValueError("resource change requires value or delta")
        if value is not None and delta is not None:
            raise ValueError("resource change must specify only value or delta")
        candidate = value if value is not None else current + delta
        spec = self._spec(ref, resource)
        settlement = self.ctx.calc("resource.bounds", {"candidate": candidate,
                    "capacity": self.capacity(ref, resource, source=source, ability=ability, effect=effect),
                    "bounds_parameters": spec.get("parameters", {})},
                    source=source, target=ref, owner=ref, local=spec.get("rules", {}),
                    ability=ability, effect=effect, rule_id=spec.get("bounds_rule"), extra={"resource": resource})
        if not settlement["accepted"]:
            raise ValueError(f"resource update rejected: {ref}.{resource}")
        actual = settlement["value"] - current
        intent = Intent("set", self.ctx.session.world.resolve(ref), ("resources", resource, "current"), settlement["value"])
        return [intent], actual

    def adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None, settlement_context=None):
        if getattr(getattr(getattr(self.ctx,'buffs',None),'applicability',None),'enabled',False):
            with self.ctx.session.atomic():return self._adjust_applicability(ref,resource,delta,value=value,source=source,ability=ability,effect=effect,settlement_context=settlement_context)
        return self._adjust_applicability(ref,resource,delta,value=value,source=source,ability=ability,effect=effect,settlement_context=settlement_context)

    def _adjust_applicability(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None, settlement_context=None):
        canonical=self.ctx.session.world.resolve(ref)
        rebirth=getattr(self.ctx,"rebirth",None)
        if self.ctx.get(canonical,("lifecycle","death_projectiles")) or (rebirth is not None and (self.ctx.get(canonical,("rebirth",)) is not None or canonical in rebirth._requests)):
            with self.ctx.session.atomic():return self._adjust(canonical,resource,delta,value=value,source=source,ability=ability,effect=effect,settlement_context=settlement_context)
        return self._adjust(canonical,resource,delta,value=value,source=source,ability=ability,effect=effect,settlement_context=settlement_context)

    def _adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None, settlement_context=None):
        ref = self.ctx.session.world.resolve(ref)
        source = self.ctx.session.world.resolve(source) if source is not None else None
        intents, actual = self.change_plan(ref, resource, delta, value=value, source=source, ability=ability, effect=effect)
        self._commit_change(ref, resource, intents, actual, source, settlement_context)
        return actual

    def _commit_change(self, ref, resource, intents, actual, source, settlement_context=None):
        ref = self.ctx.session.world.resolve(ref)
        source = self.ctx.session.world.resolve(source) if source is not None else None
        event={"operation":"resource_change","source":source,"target":ref,"resource":resource,"delta":actual}
        if settlement_context is not None:
            if (not isinstance(settlement_context,dict) or set(settlement_context)!={"operation","source","target","resource","ability","cast"}
                or settlement_context["operation"]!="damage" or type(settlement_context["target"]) is not int
                or (settlement_context["source"] is not None and type(settlement_context["source"]) is not int)
                or settlement_context["source"]!=source or settlement_context["target"]!=ref or settlement_context["resource"]!=resource
                or any(settlement_context[k] is not None and (type(settlement_context[k]) is not str or not settlement_context[k]) for k in ("ability","cast"))
                or actual>0):raise ValueError("damage settlement context must match actual depletion source/target/resource")
            event.update(settlement_context)
        self.ctx.session.commit(intents)
        self.ctx.emit("resource.changed", {"source": source, "target": ref, "resource": resource,
                                         "delta": actual, "value": self.current(ref, resource)})
        if self.ctx.lifecycle:self.ctx.lifecycle.check(ref,event)

    def payment_plan(self, ref, costs, *, ability=None, effect=None, source=None):
        costs = tuple(costs)
        if not costs:
            return []
        totals = {}
        source = ref if source is None else source
        attributes = self.ctx.attributes.values(source, ability=ability, effect=effect)
        for cost in costs:
            resource = cost["resource"]
            spec = self._spec(ref, resource)
            parameters = {**spec.get("parameters", {}), **cost.get("parameters", {})}
            if "amount" in cost:
                parameters["amount"] = cost["amount"]
            amount = self.ctx.calc("resource.cost", {"ability": dict(ability or {}), "attributes": attributes,
                 "cost_parameters": parameters}, source=source, owner=ref, local=spec.get("rules", {}),
                 ability=ability, effect=effect, rule_id=cost.get("rule"), extra={"resource": resource})
            totals[resource] = totals.get(resource, 0) + amount
        for key, amount in totals.items():
            if self.current(ref, key) < amount:
                raise ValueError(f"insufficient resource {key}")
        intents = []
        for key, amount in totals.items():
            planned, _ = self.change_plan(ref, key, -amount, source=source, ability=ability, effect=effect)
            intents.extend(planned)
        return intents

    def _recovery_frozen(self, entity, spec, resource=None):
        frozen = self._legacy_recovery_frozen(entity, spec)
        abilities = spec.get("recovery_freeze_abilities", ())
        rule = spec.get("recovery_freeze_rule") or spec.get("rules", {}).get("resource.recovery_freeze")
        if not abilities and not rule:
            return frozen
        casts = entity["components"].get("runtime", {}).get("casts", {})
        frozen = frozen or any(cast.get("ability") in abilities for cast in casts.values())
        if not rule:
            return frozen
        if resource is None:
            keys = [key for key, data in entity["components"].get("resources", {}).items() if data.get("spec") == spec]
            if len(keys) != 1: raise ValueError("custom freeze evaluation requires explicit resource identity")
            resource = keys[0]
        # calc emits only kernel calculation records, not another domain event
        # snapshot. This evaluation cannot recurse through RuntimeContext.emit.
        with self.ctx.session.atomic():
            result = self.ctx.calc("resource.recovery_freeze", {"owner": entity, "resource": resource,
                "casts": casts, "time": self.ctx.session.time, "configured_frozen": frozen,
                "parameters": spec.get("parameters", {})}, owner=entity["id"], local=spec.get("rules", {}), rule_id=rule)
            if type(result) is not bool: raise ValueError("resource recovery freeze rule must return Boolean")
            return result

    def _legacy_recovery_frozen(self, entity, spec):
        parameters = spec.get("parameters", {})
        enabled = parameters.get("freeze_while_cast", False)
        if not isinstance(enabled, bool):
            raise ValueError("freeze_while_cast must be boolean")
        if not enabled:
            return False
        casts = entity["components"].get("runtime", {}).get("casts", {})
        if not casts:
            return False
        modes = parameters.get("freeze_cast_modes")
        if modes is None:
            return True
        if not isinstance(modes, (list, tuple)) or not all(isinstance(mode, str) for mode in modes):
            raise ValueError("freeze_cast_modes must be a list of activation modes")
        for cast in casts.values():
            mode = cast.get("activation_mode")
            if mode is None:
                definition = self.ctx.program.definitions.get(cast.get("ability"), {})
                mode = definition.get("activation", {}).get("mode")
            if mode is None:
                raise ValueError(f"Cannot determine active cast mode: {cast.get('id', cast.get('ability'))}")
            if mode in modes:
                return True
        return False

    def _recovery_model(self, spec):
        configuration = spec.get("recovery", {})
        if not isinstance(configuration, Mapping):
            raise ValueError("recovery must be a model definition")
        mode = configuration.get("mode", "continuous")
        allowed = ({"mode"} if mode == "continuous" else {"mode", "interval_seconds"}) | {
            "selector", "empty_value", "selector_interval_seconds", "interrupt_when_empty", "interrupt_abilities", "interrupt_cast_modes"}
        if mode not in ("continuous", "periodic"):
            raise ValueError(f"unimplemented recovery mode: {mode}")
        if set(configuration) - allowed:
            raise ValueError(f"unsupported {mode} recovery fields: {sorted(set(configuration) - allowed)}")
        if mode == "continuous":
            return mode, None, None
        interval = configuration.get("interval_seconds")
        if (isinstance(interval, bool) or not isinstance(interval, (int, float))
                or not math.isfinite(interval) or interval <= 0):
            raise ValueError("periodic recovery interval_seconds must be a positive finite number")
        units = self.ctx.quantize(interval)
        if type(units) is not int or units < 1:
            raise ValueError("periodic recovery interval must advance logical time")
        return mode, interval, units

    def _recover(self, ref, resource, spec, delta_seconds):
        parameters = dict(spec.get("parameters", {}))
        if "recovery_rate" in spec:
            parameters["rate"] = spec["recovery_rate"]
        return self.ctx.calc("resource.recovery", {"current": self.current(ref, resource),
            "delta_seconds": delta_seconds, "attributes": self.ctx.attributes.values(ref),
            "parameters": parameters}, source=ref, owner=ref, local=spec.get("rules", {}),
            rule_id=spec.get("recovery_rule"), extra={"resource": resource})

    def event_snapshot(self, event, payload):
        """Capture eligibility before later same-time tasks finish a cast."""
        rows = []
        if event == "damage.accepted" and payload.get("damage_flags", {}).get("ignore_for_sp") is True:
            return rows
        if event == "damage.accepted" and payload.get("source_policy") == "none" and payload.get("ignore_for_sp") is True:
            return rows
        for entity in self.ctx.session.world.entities():
            if not getattr(self.ctx, 'active', self.ctx.alive)(entity["id"]):
                continue
            for key, data in entity["components"].get("resources", {}).items():
                driver = data["spec"].get("recovery", {})
                if driver.get("mode") != "event" or driver.get("event") != event:
                    continue
                role = driver.get("owner_role", "source")
                if role != "any" and payload.get(role) != entity["id"]:
                    continue
                if driver.get("selector") and not self.ctx.spatial.select(entity["id"], driver["selector"]):
                    continue
                if not self._recovery_frozen(entity, data["spec"], key):
                    rows.append({"owner": entity["id"], "resource": key})
        return rows

    def notify(self, event, payload, cause, recipients):
        for recipient in recipients:
            ref, key = recipient["owner"], recipient["resource"]
            if not getattr(self.ctx, 'active', self.ctx.alive)(ref):
                continue
            spec = self._spec(ref, key)
            driver = spec.get("recovery", {})
            if driver.get("mode") != "event" or driver.get("event") != event:
                continue
            if spec.get("parameters", {}).get("pause_at_full") and self.current(ref, key) >= self.capacity(ref, key):
                continue
            condition = driver.get("condition")
            if condition and not evaluate_expression(condition, {"event": payload, "owner": self.ctx.entity(ref)},
                                                       spec.get("parameters", {}), {"time": self.ctx.session.time}):
                continue
            with self.ctx.session.atomic():
                current = self.current(ref, key)
                refs = {}
                for role in ("source", "target"):
                    try:
                        refs[role] = self.ctx.session.world.resolve(payload.get(role))
                    except (ValueError, KeyError):
                        refs[role] = None
                value = self.ctx.calc("resource.recovery", {"current": current, "delta_seconds": 0,
                    "attributes": self.ctx.attributes.values(ref),
                    "parameters": {**spec.get("parameters", {}), "amount": driver.get("amount", 1)}},
                    owner=ref, source=refs["source"], target=refs["target"],
                    local=spec.get("rules", {}), rule_id=spec["recovery_rule"], extra={"resource": key, "event": payload})
                self.adjust(ref, key, value=value)
                self.ctx.emit("resource.event_recovered", {"source": ref, "target": ref, "resource": key,
                    "trigger": event, "delta": self.current(ref, key)-current}, cause)

    def _selector_enabled(self, ref, key, spec):
        driver = spec.get("recovery", {})
        if not driver.get("selector"):
            return True
        now = self.ctx.session.time
        state = self.ctx.get(ref, ("resources", key, "selector_state"), {})
        if now < state.get("next_check", 0):
            return state["enabled"]
        with self.ctx.session.atomic():
            enabled = bool(self.ctx.spatial.select(ref, driver["selector"]))
            interval = max(1, self.ctx.quantize(driver.get("selector_interval_seconds", 0)))
            self.ctx.set(ref, ("resources", key, "selector_state"), {"enabled": enabled, "next_check": now+interval})
            if not enabled:
                if driver.get("interrupt_when_empty") and self.ctx.get(ref, ("runtime", "casts"), {}):
                    self.ctx.abilities.interrupt(ref, "recovery_selector_empty",
                        ability_ids=driver.get("interrupt_abilities"), modes=driver.get("interrupt_cast_modes"))
                if "empty_value" in driver and self.current(ref, key) != driver["empty_value"]:
                    self.adjust(ref, key, value=driver["empty_value"], source=ref)
            return enabled

    def tick(self, session):
        if self.ctx.state().get("finished"):
            return
        for entity in session.world.entities():
            ref = entity["id"]
            if not getattr(self.ctx, 'active', self.ctx.alive)(ref):
                continue
            if any(d.get("capacity_signature") != self._capacity_signature(ref, d["spec"]) or self._capacity_poll_required(ref, d["spec"])
                   for d in entity["components"].get("resources", {}).values()):
                self.sync_capacities(ref, reason="capacity_tick")
                if not getattr(self.ctx, 'active', self.ctx.alive)(ref):
                    continue
                entity = self.ctx.entity(ref)
            for key, data in entity["components"].get("resources", {}).items():
                spec = data["spec"]
                if not self._selector_enabled(ref, key, spec):
                    continue
                if spec.get("recovery", {}).get("mode") == "event":
                    continue
                rule = spec.get("recovery_rule")
                if (rule is None and "resource.recovery" not in spec.get("rules", {})
                        and "recovery_rate" not in spec and "recovery" not in spec):
                    continue
                if self._recovery_frozen(entity, spec, key):
                    continue
                pause = spec.get("parameters", {}).get("pause_at_full", False)
                if not isinstance(pause, bool):
                    raise ValueError("pause_at_full must be boolean")
                if pause and self.current(ref, key) >= self.capacity(ref, key):
                    continue
                mode, interval, interval_units = self._recovery_model(spec)
                if mode == "continuous":
                    self.adjust(ref, key, value=self._recover(ref, key, spec, session.quantum), source=ref)
                    continue
                timing = dict(data.get("timing", {}))
                elapsed = timing.get("elapsed_units", 0)
                if type(elapsed) is not int or elapsed < 0:
                    raise ValueError("periodic elapsed_units must be a nonnegative integer")
                elapsed += 1
                cycles, remainder = divmod(elapsed, interval_units)
                timing["elapsed_units"] = remainder
                timer_intent = Intent("set", ref, ("resources", key, "timing"), timing)
                if not cycles:
                    session.commit([timer_intent])
                    continue
                if cycles > session.reaction_budget:
                    raise ValueError("periodic recovery catch-up exceeds reaction budget")
                for _ in range(cycles):
                    if not getattr(self.ctx, 'active', self.ctx.alive)(ref):
                        break
                    recovered = self._recover(ref, key, spec, interval)
                    plan, actual = self.change_plan(ref, key, value=recovered, source=ref)
                    # A failed calculation or settlement cannot advance this
                    # period's timer without applying its resource change.
                    self._commit_change(ref, key, plan + [timer_intent], actual, ref)
