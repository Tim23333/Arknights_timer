"""Generic Buff instances, timers, modifiers and queued event reactions."""
from ark_sim.contracts import Intent, thaw
import math
from ark_sim.rules.expressions import evaluate_expression


class BuffSystem:
    def __init__(self, context):
        self.ctx = context
        from .applicability import ApplicabilitySystem
        self.applicability=ApplicabilitySystem(context,self)
        from .toggles import ToggleSystem
        self.toggles = ToggleSystem(context, self)
        self._reconciling = False
        self._removal_depth = 0
        self._reconcile_requested = False
        self.has_auras = any(d.get("kind") == "buff" and d.get("aura")
                             for d in context.program.definitions.values())
        self.has_buffs = any(d.get("kind") == "buff" for d in context.program.definitions.values())
        self.recovery_events = set()
        def uses_frozen_recovery(value):
            if isinstance(value, dict):
                return bool(value.get("parameters", {}).get("respect_recovery_freeze")) or any(uses_frozen_recovery(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return any(uses_frozen_recovery(v) for v in value)
            return False
        for definition in context.program.definitions.values():
            if definition.get("kind") == "buff":
                for subscription in definition.get("events", []):
                    if uses_frozen_recovery(thaw(subscription.get("effects", []))):
                        self.recovery_events.add(subscription["event"])

    def recovery_snapshot(self, event):
        if event not in self.recovery_events:
            return None
        return [{"owner": e["id"], "resource": key, "frozen": self.ctx.resources._recovery_frozen(e, data["spec"], key)}
            for e in self.ctx.session.world.entities() if e['components'].get('runtime', {}).get('active', True)
            for key, data in e["components"].get("resources", {}).items()]

    def _instances(self, target):
        return self.ctx.get(target, ("buffs", "instances"), [])

    def controls(self, target):
        """Independent control restrictions compose over active Buff instances."""
        result = {"move": True, "attack": True, "abilities": True, "block": True}
        now = self.ctx.session.time
        for instance in self._instances(target):
            if instance.get("expires_at") is not None and now >= instance["expires_at"]:
                continue
            if not self.applicability.control(instance):continue
            controls = self.ctx.program.definitions[instance["definition"]].get("control", {})
            for key in result:
                result[key] = result[key] and controls.get(key, True)
        return result

    def _pending(self):
        return {task["id"] for task in self.ctx.session.scheduler.pending}

    def _cancel_intents(self, instances):
        pending = self._pending()
        return [Intent("cancel", data={"task_id": task}) for item in instances
                for task in item.get("tasks", {}).values() if task in pending]

    def _modifiers(self, target, instances):
        modifiers = [item for item in self.ctx.get(target, ("attributes", "modifiers"), [])
                     if "buff_instance" not in item]
        for instance in instances:
            if instance.get("expires_at") is not None and self.ctx.session.time >= instance["expires_at"]: continue
            if not self.applicability.active(instance):continue
            definition = self.ctx.program.definitions[instance["definition"]]
            for modifier in definition.get("modifiers", ()):
                modifiers.append({**thaw(modifier), "buff_instance": instance["id"],
                                  "stacks": instance["stacks"], "source": instance["source"]})
        return modifiers

    def _sync_blocking(self, definitions):
        """Reconcile spatial membership when a declared Buff can change it.

        Lightweight isolated contexts need not implement a spatial domain.
        The caller's transaction owns every calculation/event/state change.
        """
        callback = getattr(getattr(self.ctx, "spatial", None), "blocking", None)
        if callback is None:
            return
        role = getattr(self.ctx, "attribute_role", None)
        attributes = {role("block_capacity") if role else "block_count",
                      role("block_occupancy") if role else "block_cost"}
        from .block_status import required
        uses_status=required(self.ctx)
        if any((uses_status and definition.get("selection_flags")) or "block" in definition.get("control", {}) or any(
                item.get("attribute") in attributes for item in definition.get("modifiers", ()))
                for definition in definitions):
            callback()

    def apply(self, source, target, buff_id, stacks=1, *, aura_parent=None, toggle_parent=None, duration_override=None):
        with self.ctx.session.atomic():
            source, target = self.ctx.session.world.resolve(source), self.ctx.session.world.resolve(target)
            if type(stacks) is not int or stacks < 1:
                raise ValueError("Incoming Buff stacks must be a positive integer")
            definition = self.ctx.program.definitions[buff_id]
            if definition.get("kind") != "buff":
                raise ValueError(f"Not a Buff definition: {buff_id}")
            policy = definition.get("stacking", {})
            if policy.get("policy"):
                raise ValueError("Custom Buff stacking policy requires an implemented policy adapter")
            mode = policy.get("mode", "refresh")
            if mode not in {"refresh", "independent", "add", "extend", "max"}:
                raise ValueError(f"Unsupported Buff stacking mode: {mode}")
            instances = self._instances(target)
            identity = policy.get("identity", ("definition", "source", "target"))
            incoming = {"definition": buff_id, "source": source, "target": target}
            if set(identity) - set(incoming):
                raise ValueError("Buff identity supports definition/source/target only")
            existing = None if mode == "independent" else next((item for item in instances
                if all(item.get(key) == incoming[key] for key in identity)), None)
            if existing and definition.get("movement_damage"):
                self._flush_movement_damage(target, existing)
                if not getattr(self.ctx, 'active', self.ctx.alive)(target):
                    return None
                instances = self._instances(target)
                existing = next((i for i in instances if i["id"] == existing["id"]), None)
            current = existing["stacks"] if existing else 0
            amount = self.ctx.calc("buff.stack_amount", {"current_stacks": current,
                "incoming": {"count": stacks, "mode": mode},
                "stack_parameters": {"max_stacks": policy.get("max_stacks", current + stacks), "mode": mode}},
                source=source, target=target, owner=target, local=definition.get("rules", {}), rule_id=policy.get("rule"))
            if type(amount) not in (int, float) or isinstance(amount, bool) or int(amount) != amount or amount < 1:
                raise ValueError("Buff stacking rule must return a positive integer stack amount")
            attrs = self.ctx.attributes.values(source)
            params = {**thaw(definition.get("parameters", {})), "duration_seconds": definition.get("duration_seconds", 0),
                      "interval_seconds": definition.get("interval_seconds", 0)}
            duration = self.ctx.calc("buff.duration", {"attributes": attrs, "buff_parameters": params},
                    source=source, target=target, local=definition.get("rules", {}), rule_id=definition.get("duration_rule"))
            interval = self.ctx.calc("buff.interval", {"attributes": attrs, "buff_parameters": params},
                    source=source, target=target, local=definition.get("rules", {}), rule_id=definition.get("interval_rule"))
            if duration_override is not None:
                if type(duration_override) not in (int, float) or not math.isfinite(duration_override) or duration_override < 0: raise ValueError("Invalid duration override")
                duration = duration_override
            if duration < 0 or interval < 0:
                raise ValueError("Buff duration and interval must be nonnegative")
            duration_units, interval_units = self.ctx.quantize(duration), self.ctx.quantize(interval)
            if definition.get("movement_damage") and interval_units < 1:
                raise ValueError("movement damage interval must advance logical time")
            next_instance = self.ctx.get(target, ("buffs", "next_instance_id"), 1)
            uid = existing["id"] if existing else f"buff/{target}/{next_instance}"
            generation = existing.get("generation", 0) + 1 if existing else 1
            expires = self.ctx.session.time + duration_units
            permanent = duration_override is None and duration_units == 0 and "duration_seconds" not in definition and not definition.get("duration_rule")
            if permanent:
                expires = None
            elif existing and mode == "extend" and existing.get("expires_at") is not None:
                expires = existing["expires_at"] + duration_units
            elif existing and mode == "max" and existing.get("expires_at") is not None:
                expires = max(existing["expires_at"], expires)
            instance = {**incoming, "id": uid, "stacks": int(amount), "started_at": self.ctx.session.time,
                        "expires_at": expires, "interval_units": interval_units, "generation": generation,
                        "tasks": {}, "blackboard": thaw(existing.get("blackboard", {})) if existing else {}}
            if aura_parent is not None:
                instance["aura_parent"] = aura_parent
            if definition.get("movement_damage"):
                instance["blackboard"]["distance_cursor"] = self.ctx.get(target, ("spatial", "distance_travelled"), 0)
            if toggle_parent is not None:
                instance["toggle_parent"] = toggle_parent
            if definition.get("toggle") and existing and existing.get("toggle_state"):
                instance["toggle_state"] = existing["toggle_state"]
            if definition.get("aura"):
                instance["aura_members"] = thaw(existing.get("aura_members", {})) if existing else {}
            next_task = self.ctx.session.scheduler.next_task_id
            scheduled = []
            for kind, at in (("expire", expires), ("periodic", self.ctx.session.time + interval_units if interval_units else None)):
                if at is None or (kind == "periodic" and expires is not None and at >= expires):
                    continue
                instance["tasks"][kind] = next_task
                next_task += 1
                scheduled.append(Intent("schedule", data={"kind": f"domain.buff.{kind}", "at": at,
                    "phase": self.ctx.effect_phase, "payload": {"target": target, "instance": uid, "generation": generation}}))
            replacement = [item for item in instances if existing is None or item["id"] != existing["id"]] + [instance]
            capacities_before = self.ctx.resources.capacity_snapshot(target)
            intents = self._cancel_intents([existing] if existing else [])
            intents.extend([Intent("set", target, ("buffs", "instances"), replacement),
                            Intent("set", target, ("attributes", "modifiers"), self._modifiers(target, replacement))])
            if existing is None:
                intents.append(Intent("set", target, ("buffs", "next_instance_id"), next_instance + 1))
            self.ctx.session.commit(intents + scheduled)
            self.applicability.reconcile()
            self.ctx.resources.sync_capacities(target, capacities_before, "buff_applied")
            self._sync_blocking([definition])
            current=next((x for x in self._instances(target) if x["id"]==uid),None)
            if definition.get("control", {}).get("interrupt") and current is not None and self.applicability.control(current) and (current["expires_at"] is None or self.ctx.session.time < current["expires_at"]):
                self.ctx.abilities.interrupt(target, "control_buff")
            self.ctx.emit("buff.applied", {"source": source, "target": target, "buff": buff_id,
                                          "instance": uid, "stacks": int(amount)})
            if interval_units == 0 and current is not None and self.applicability.active(current) and (current["expires_at"] is None or self.ctx.session.time < current["expires_at"]):
                for effect in definition.get("effects", ()):
                    current=next((x for x in self._instances(target) if x["id"]==uid),None)
                    if self.applicability.enabled and (current is None or not self.applicability.active(current)):break
                    self.ctx.effects.execute(source, [target], thaw(effect))
            # Normal owned-child installation is already part of this pass.
            # Its real effects can separately request another reconciliation.
            if not (self._reconciling and aura_parent is not None):self.reconcile()
            return uid

    def remove(self, target, buff_or_instance, *, _from_aura=False):
        with self.ctx.session.atomic():
            self._removal_depth += 1
            try:
                removed = self._remove(target, buff_or_instance)
            finally:
                self._removal_depth -= 1
            if removed:
                if self._reconciling and not _from_aura:self._reconcile_requested = True
                if self._removal_depth == 0 and not (self._reconciling and _from_aura):self.reconcile()
            return removed

    def _remove(self, target, buff_or_instance):
        with self.ctx.session.atomic():
            target = self.ctx.session.world.resolve(target)
            instances = self._instances(target)
            removed = [item for item in instances if item["id"] == buff_or_instance or item["definition"] == buff_or_instance]
            if not removed:
                return 0
            wanted = {i["id"] for i in removed}
            for item in removed:
                self._flush_movement_damage(target, item)
            removed = [i for i in self._instances(target) if i["id"] in wanted]
            if not removed:
                return 0
            for item in removed:
                self.toggles.remove(target, item)
                for member, child in item.get("aura_members", {}).items():
                    self.remove(int(member), child, _from_aura=True)
            removed_ids = {item["id"] for item in removed}
            remaining = [item for item in self._instances(target) if item["id"] not in removed_ids]
            capacities_before = self.ctx.resources.capacity_snapshot(target)
            intents = self._cancel_intents(removed) + [Intent("set", target, ("buffs", "instances"), remaining),
                Intent("set", target, ("attributes", "modifiers"), self._modifiers(target, remaining))]
            self.ctx.session.commit(intents)
            self.ctx.resources.sync_capacities(target, capacities_before, "buff_removed")
            self._sync_blocking([self.ctx.program.definitions[item["definition"]] for item in removed])
            for item in removed:
                cause = self.ctx.emit("buff.removed", {"source": item["source"], "target": target,
                    "buff": item["definition"], "instance": item["id"]})
                for effect in self.ctx.program.definitions[item["definition"]].get("on_remove", ()):
                    self.ctx.effects.execute(item["source"], [target], thaw(effect), cause=cause)
            return len(removed)

    def _live_parent(self, center, uid):
        return next((p for p in self._instances(center) if p["id"] == uid), None)

    def _parent_active(self, center, parent):
        return (getattr(self.ctx, 'active', self.ctx.alive)(center)
                and getattr(self.ctx, 'active', self.ctx.alive)(parent["source"])
                and (parent["expires_at"] is None or self.ctx.session.time < parent["expires_at"]))

    def _clear_orphan_children(self, parent_id):
        # Instance identity includes the center, so this does not touch other
        # parents with the same definition or sources sharing a target.
        for entity in self.ctx.session.world.entities():
            for child in self._instances(entity["id"]):
                if child.get("aura_parent") == parent_id:
                    self.remove(entity["id"], child["id"], _from_aura=True)

    def _publish_owned_members(self, center, parent_id):
        parent = self._live_parent(center, parent_id)
        if parent is None:
            self._clear_orphan_children(parent_id)
            return
        members = {}
        for entity in self.ctx.session.world.entities():
            for child in self._instances(entity["id"]):
                if child.get("aura_parent") == parent_id:
                    key = str(entity["id"])
                    if key in members:raise ValueError("aura parent owns duplicate children on one target")
                    members[key] = child["id"]
        if members != parent.get("aura_members", {}):
            parents = self._instances(center)
            for item in parents:
                if item["id"] == parent_id:item["aura_members"] = members
            self.ctx.set(center, ("buffs", "instances"), parents)

    def _reconcile_pass(self):
        for entity in self.ctx.session.world.entities():
            center = entity["id"]
            for captured in self._instances(center):
                parent = self._live_parent(center, captured["id"])
                if parent is None:continue
                definition = self.ctx.program.definitions[parent["definition"]]
                aura = definition.get("aura")
                if not aura:continue
                if not self._parent_active(center, parent):
                    self.remove(center, parent["id"], _from_aura=True)
                    self._clear_orphan_children(parent["id"])
                    continue
                available = self.applicability.active(parent) and self.ctx.aura_available(center) and self.ctx.aura_available(parent["source"])
                desired = set(self.ctx.spatial.select(center, aura["selector"])) if available else set()
                desired = {ref for ref in desired if getattr(self.ctx, 'active', self.ctx.alive)(ref)}
                members = dict(parent.get("aura_members", {}))
                invalid = False
                for member, child in list(members.items()):
                    if int(member) not in desired:
                        self.remove(int(member), child, _from_aura=True)
                        members.pop(member, None)
                        current = self._live_parent(center, parent["id"])
                        if current is None or not self._parent_active(center, current):
                            if current is not None:self.remove(center, current["id"], _from_aura=True)
                            self._clear_orphan_children(parent["id"])
                            invalid = True
                            break
                        if current["source"] != parent["source"]:
                            self._reconcile_requested = True
                            invalid = True
                            break
                        if self._reconcile_requested:
                            self._publish_owned_members(center, parent["id"])
                            return
                if invalid:continue
                for member in sorted(desired):
                    current = self._live_parent(center, parent["id"])
                    if current is None or not self._parent_active(center, current):
                        if current is not None:self.remove(center, current["id"], _from_aura=True)
                        self._clear_orphan_children(parent["id"])
                        invalid = True
                        break
                    if not getattr(self.ctx, 'active', self.ctx.alive)(member):continue
                    key = str(member)
                    if key not in members or not any(i["id"] == members[key] for i in self._instances(member)):
                        members[key] = self.apply(current["source"], member, aura["buff"], aura_parent=parent["id"])
                        fresh = self._live_parent(center, parent["id"])
                        if fresh is None or not self._parent_active(center, fresh):
                            if fresh is not None:self.remove(center, fresh["id"], _from_aura=True)
                            self._clear_orphan_children(parent["id"])
                            invalid = True
                            break
                        if self._reconcile_requested:
                            self._publish_owned_members(center, parent["id"])
                            return
                current = self._live_parent(center, parent["id"])
                if invalid or current is None:continue
                if not self._parent_active(center, current):
                    self.remove(center, current["id"], _from_aura=True)
                    self._clear_orphan_children(parent["id"])
                    continue
                if members != current.get("aura_members", {}):
                    parents = self._instances(center)
                    for item in parents:
                        if item["id"] == current["id"]:item["aura_members"] = members
                    self.ctx.set(center, ("buffs", "instances"), parents)

    def reconcile(self, session=None):
        self.applicability.reconcile()
        self.toggles.reconcile()
        if not self.has_auras:return
        if self._reconciling:
            self._reconcile_requested = True
            return
        if self._removal_depth:return
        self._reconciling = True
        try:
            with self.ctx.session.atomic():
                budget = self.ctx.session.reaction_budget
                while True:
                    self._reconcile_requested = False
                    self._reconcile_pass()
                    if not self._reconcile_requested:break
                    budget -= 1
                    if budget <= 0:raise ValueError("aura callbacks exceed reconciliation budget")
        finally:
            self._reconciling = False
            self._reconcile_requested = False

    def prune_expired(self):
        """Apply half-open lifetime before command/cast snapshot sampling."""
        if not self.has_buffs:
            return
        with self.ctx.session.atomic():
            now = self.ctx.session.time
            for entity in self.ctx.session.world.entities():
                for instance in self._instances(entity["id"]):
                    if instance["expires_at"] is not None and now >= instance["expires_at"]:
                        self.remove(entity["id"], instance["id"])

    def tick(self, session):
        self.prune_expired()
        self.reconcile()

    def _active(self, payload):
        try:
            instances = self._instances(payload["target"])
        except KeyError:
            return None
        return next((item for item in instances if item["id"] == payload["instance"]
                     and item["generation"] == payload["generation"]), None)

    def _flush_movement_damage(self, target, instance):
        spec = self.ctx.program.definitions[instance["definition"]].get("movement_damage")
        if not spec:
            return
        total = self.ctx.get(target, ("spatial", "distance_travelled"), 0)
        if not self.applicability.active(instance):
            values=self._instances(target)
            for item in values:
                if item["id"]==instance["id"]:item["blackboard"]["distance_cursor"]=total
            self.ctx.set(target,("buffs","instances"),values)
            return
        cursor = instance["blackboard"].get("distance_cursor", total)
        delta = total-cursor
        if delta < -1e-12:
            raise ValueError("movement ledger cannot move backwards")
        if delta <= 0:
            return
        items = self._instances(target)
        active = next((i for i in items if i["id"] == instance["id"]), None)
        if active is None:
            return
        # Commit the cursor before settlement: a fatal hit may recursively
        # retire/remove the instance, which must not settle the same tail twice.
        active["blackboard"]["distance_cursor"] = total
        self.ctx.set(target, ("buffs", "instances"), items)
        effect = {**thaw(spec["effect"]), "distance": delta}
        cause = self.ctx.emit("buff.movement_sample", {"source": instance["source"], "target": target,
            "instance": instance["id"], "distance": delta, "total": total})
        self.ctx.effects.execute(instance["source"], [target], effect, cause=cause)

    def expire(self, session, payload):
        if self._active(payload):
            self.remove(payload["target"], payload["instance"])

    def periodic(self, session, payload):
        instance = self._active(payload)
        if not instance:
            return
        if instance["interval_units"] < 1:
            return
        definition = self.ctx.program.definitions[instance["definition"]]
        try:
            session.world.resolve(instance["source"])
        except KeyError:
            self.remove(instance["target"], instance["id"])
            return
        if not getattr(self.ctx, 'active', self.ctx.alive)(instance["target"]) and definition.get("removal", {}).get("on_target_death", "remove") == "remove":
            self.remove(instance["target"], instance["id"])
            return
        active=self.applicability.active(instance)
        cause = self.ctx.emit("buff.periodic", {"source": instance["source"], "target": instance["target"],
                              "buff": instance["definition"], "instance": instance["id"]}) if active else None
        self._flush_movement_damage(instance["target"], instance)
        for effect in definition.get("effects", ()):
            current=self._active(payload)
            if self.applicability.enabled and (current is None or not self.applicability.active(current)):break
            self.ctx.effects.execute(instance["source"], [instance["target"]], thaw(effect), cause=cause)
        instance = self._active(payload)
        if not instance:
            return
        at = session.time + instance["interval_units"]
        if instance["expires_at"] is not None and at >= instance["expires_at"]:
            return
        instances = self._instances(instance["target"])
        for item in instances:
            if item["id"] == instance["id"]:
                item["tasks"]["periodic"] = session.scheduler.next_task_id
        session.commit([Intent("set", instance["target"], ("buffs", "instances"), instances),
                        Intent("schedule", data={"kind": "domain.buff.periodic", "at": at,
                            "phase": self.ctx.effect_phase, "payload": payload})])

    def notify(self, event, payload, cause=None, recovery_snapshot=None):
        for entity in self.ctx.session.world.entities():
            target = entity["id"]
            for instance in self._instances(target):
                definition = self.ctx.program.definitions[instance["definition"]]
                removal = definition.get("removal", {})
                try:
                    source_alive = getattr(self.ctx, 'active', self.ctx.alive)(instance["source"])
                except KeyError:
                    self.remove(target, instance["id"])
                    continue
                if not getattr(self.ctx, 'active', self.ctx.alive)(target) and removal.get("on_target_death", "remove") == "remove":
                    self.remove(target, instance["id"])
                    continue
                if not source_alive and removal.get("on_source_death", "retain") == "remove":
                    self.remove(target, instance["id"])
                    continue
                if not self.applicability.active(instance):continue
                for subscription in definition.get("events", ()):
                    if subscription["event"] != event:
                        continue
                    condition = subscription.get("condition")
                    context = {"time": self.ctx.session.time, "owner": self.ctx.entity(target),
                               "source": self.ctx.entity(instance["source"]), "target": self.ctx.entity(target)}
                    if condition and not evaluate_expression(condition, {"event": event, "payload": payload, "buff": instance},
                            subscription.get("parameters", {}), context):
                        continue
                    for effect in subscription.get("effects", ()):
                        current=next((x for x in self._instances(target) if x["id"]==instance["id"]),None)
                        if self.applicability.enabled and (current is None or not self.applicability.active(current)):break
                        recipient = payload.get("source") if subscription.get("target") == "event_source" else payload.get("target") if subscription.get("target") == "event_target" else target
                        if recipient is None:
                            continue
                        try:
                            recipient = self.ctx.session.world.resolve(recipient)
                        except (ValueError, KeyError):
                            continue
                        cast = {"recovery_snapshot": recovery_snapshot} if recovery_snapshot is not None else None
                        self.ctx.effects.execute(instance["source"], [recipient], thaw(effect), cast=cast, cause=cause)
