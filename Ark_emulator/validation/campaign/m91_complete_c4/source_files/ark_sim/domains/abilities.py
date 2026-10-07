"""Definition-driven abilities and atomic resource/timeline activation."""
from ark_sim.contracts import Intent, thaw
from ark_sim.rules.expressions import evaluate_expression


class ActivationRejected(ValueError):
    """A valid ability is temporarily unable to activate."""


class AbilitySystem:
    def __init__(self, context):
        self.ctx = context

    def _definition(self, ability_id):
        definition = self.ctx.program.definitions[ability_id]
        if definition.get("kind") != "ability":
            raise ValueError(f"Not an ability: {ability_id}")
        return thaw(definition)

    def _params(self, ability):
        return {**ability.get("parameters", {}), **ability.get("activation", {}).get("parameters", {})}

    def _condition(self, condition, source, ability, payload=None):
        return not condition or bool(evaluate_expression(condition,
            {"source": self.ctx.entity(source), "payload": payload or {},
             "resources": self.ctx.get(source, ("resources",), {})}, self._params(ability),
            {"source": self.ctx.entity(source), "time": self.ctx.session.time, "ability": ability}))

    def _seconds(self, calculation, source, ability, parameter, seconds):
        attrs = self.ctx.attributes.values(source)
        return self.ctx.calc(calculation, {"attributes": attrs, "animation": {}, parameter: {"seconds": seconds}},
                             source=source, ability=ability)

    def _cost_groups(self, source, ability):
        groups = {}
        for cost in ability.get("activation", {}).get("costs", []):
            owner_kind = cost.get("owner", "source")
            holder = source if owner_kind == "source" else self.ctx.session.world.resolve("system/battle") if owner_kind == "battle" else self.ctx.get(source, ("ownership", "owner"))
            if holder is None:
                raise ValueError("owned resource cost requires an owner relationship")
            groups.setdefault(holder, []).append(cost)
        return groups

    def start(self, source, ability_id, automatic=False, event_payload=None, cause=None):
        with self.ctx.session.atomic():
            source = self.ctx.session.world.resolve(source)
            if 'tile_field_owner' in self.ctx.definition(source).get('tags',[]):
                raise ActivationRejected('Static tile field is not an ability source')
            self.ctx.buffs.prune_expired()
            ability = self._definition(ability_id)
            if ability_id not in self.ctx.get(source, ("abilities",), []):
                raise ValueError(f"Entity does not possess ability: {ability_id}")
            if not getattr(self.ctx, 'active', self.ctx.alive)(source) or self.ctx.state().get("finished"):
                raise ActivationRejected("Ability source is not active")
            runtime = self.ctx.get(source, ("runtime",), {})
            now = self.ctx.session.time
            if runtime.get("cooldowns", {}).get(ability_id, 0) > now:
                raise ActivationRejected("Ability is on cooldown")
            params, activation = self._params(ability), ability.get("activation", {})
            forbidden = activation.get("forbidden_source_flags", [])
            if forbidden:
                from .selection import DEFAULT_STATE
                if set(forbidden) & set(self.ctx.spatial.selection_state(source, DEFAULT_STATE)["abnormal_flags"]):
                    raise ActivationRejected("Ability source has a forbidden status")
            if params.get("cancel_pending_attacks"):
                pending = {t["id"] for t in self.ctx.session.scheduler.pending}
                old = [key for key, value in runtime.get("casts", {}).items() if value.get("activation_mode") == "automatic_attack"]
                for key in old:
                    previous = runtime["casts"].pop(key)
                    for task in previous["tasks"]:
                        if task in pending:
                            self.ctx.session.cancel(task)
                    self.ctx.emit("ability.interrupted", {"source": source, "ability": previous["ability"], "cast": key, "reason": "attack_mode_changed"})
            if params.get("reset_attack_clock"):
                runtime["next_attack"] = now
            if params.get("cancel_pending_attacks") or params.get("reset_attack_clock"):
                self.ctx.set(source, ("runtime",), runtime)
            if self.ctx.route_hidden(source):
                raise ActivationRejected("Ability source is route-hidden")
            if params.get("auto_only") and not automatic:
                raise ActivationRejected("Automatic-only ability cannot be activated by a player command")
            if not self._condition(activation.get("condition"), source, ability, event_payload):
                raise ActivationRejected("Ability activation condition rejected")
            mode = activation.get("mode", "manual")
            if not self.ctx.buffs.controls(source)["abilities"]:
                raise ActivationRejected("Ability source is controlled")
            if mode == "automatic_attack" and not self.ctx.buffs.controls(source)["attack"]:
                raise ActivationRejected("Attack source is controlled")
            if mode in {"passive", "automatic_attack", "on_deploy"} and not automatic:
                raise ActivationRejected("Automatic abilities activate only through their registered systems/events")
            policy = ability.get("interrupt_policy", {})
            if policy.get("refund", "none") != "none" or policy.get("on_source_death", "cancel_remaining") != "cancel_remaining":
                raise ValueError("Ability interrupt policy requires an implemented refund/continuation adapter")
            blocks = params.get("blocks_attacks", mode != "passive")
            casts = runtime.get("casts", {})
            if blocks and any(cast.get("blocks_attacks", True) for cast in casts.values()):
                raise ActivationRejected("Another blocking ability is active")
            if any(cast["ability"] == ability_id for cast in casts.values()):
                raise ActivationRejected("Ability is already active")
            targets = self.ctx.spatial.select(source, ability["selector"], ability=ability) if ability.get("selector") else [source]
            requires_targets = mode == "automatic_attack" or params.get("replace_attack") or params.get("requires_targets", False)
            if requires_targets and not targets:
                raise ActivationRejected("No legal ability target")
            # Payment planning validates all resource costs before touching state.
            groups = self._cost_groups(source, ability)
            resources_before = {(holder, cost["resource"]): self.ctx.resources.current(holder, cost["resource"])
                for holder, costs in groups.items() for cost in costs}
            try:
                payment = [intent for holder, costs in groups.items()
                           for intent in self.ctx.resources.payment_plan(holder, costs, ability=ability, source=source)]
            except ValueError as exc:
                if str(exc).startswith("insufficient resource"):
                    raise ActivationRejected(str(exc)) from exc
                raise
            attrs = self.ctx.attributes.values(source)
            prepared = []
            pre_delay = activation.get("parameters", {}).get("windup_seconds", params.get("pre_delay_seconds", 0))
            last_delay = 0
            for entry in ability.get("timeline", ()):
                if "at" in entry and "at_seconds" in entry:
                    raise ValueError("Ability timeline must choose either at or at_seconds")
                if "at" in entry:
                    if type(entry["at"]) is not int or entry["at"] < 0:
                        raise ValueError("Ability timeline at must be a nonnegative integer logic offset")
                    offset_seconds = entry["at"] * self.ctx.session.quantum
                else:
                    offset_seconds = entry.get("at_seconds", 0)
                delay = self._seconds("ability.windup", source, ability, "timing_parameters", pre_delay + offset_seconds)
                if delay < 0:
                    raise ValueError("Ability windup rule returned a negative delay")
                repeat = entry.get("repeat", {})
                plan = self.ctx.calc("ability.repeat", {"attributes": attrs,
                        "repeat_parameters": {**thaw(repeat.get("parameters", {})), "count": repeat.get("count", 1),
                                              "interval_seconds": repeat.get("interval_seconds", 0)}},
                        source=source, ability=ability, rule_id=repeat.get("rule"))
                if type(plan.get("count")) is not int or not 0 <= plan["count"] <= 10000:
                    raise ValueError("Repeat rule must return a bounded nonnegative integer count")
                if plan["interval"] < 0:
                    raise ValueError("Repeat interval cannot be negative")
                delay_units = self.ctx.quantize(delay)
                repeat_units = self.ctx.quantize(plan["interval"])
                effects = entry.get("effects", ()) or ([entry["effect"]] if "effect" in entry else [])
                for index in range(plan["count"]):
                    relative = delay_units + index * repeat_units
                    last_delay = max(last_delay, relative)
                    for effect in effects:
                        prepared.append({"at": now + relative, "effect": thaw(effect), "condition": entry.get("condition")})
            duration = self.ctx.calc("ability.duration", {"attributes": attrs,
                    "duration_parameters": {"seconds": ability.get("duration_seconds", activation.get("duration_seconds", 0))}},
                    source=source, ability=ability)
            if duration < 0:
                raise ValueError("Ability duration cannot be negative")
            finish_at = now + max(last_delay, self.ctx.quantize(duration))
            recovery = self._seconds("ability.recovery", source, ability, "recovery_parameters",
                ability.get("cooldown_seconds", activation.get("cooldown_seconds", params.get("cooldown_seconds", 0))))
            if recovery < 0:
                raise ValueError("Ability recovery cannot be negative")
            sequence = runtime.get("next_cast_id", 1)
            cast_id = f"cast/{source}/{sequence}"
            next_task = self.ctx.session.scheduler.next_task_id
            cast = {"id": cast_id, "source": source, "ability": ability_id, "targets": targets,
                    "activation_mode": mode,
                    "source_snapshot": getattr(self.ctx, "capture_view", self.ctx.entity)(source),
                    "started_at": now, "finish_at": finish_at,
                    "target_snapshots": {str(target): getattr(self.ctx, "capture_view", self.ctx.entity)(target) for target in targets},
                    "tasks": [], "blocks_attacks": bool(blocks), "automatic": bool(automatic),
                    "parameters": params, "generation": sequence}
            if event_payload:
                cast["event_payload"] = thaw(event_payload)
            if ability.get("wait_for_channels"):
                cast["pending_channels"] = 0
                cast["channel_recovery_units"] = self.ctx.quantize(recovery)
            if params.get("wait_for_projectiles"):
                cast["pending_projectiles"] = 0
                cast["recovery_units"] = self.ctx.quantize(recovery)
            schedule = []
            for prepared_effect in prepared:
                cast["tasks"].append(next_task)
                next_task += 1
                schedule.append(Intent("schedule", data={"kind": "domain.ability.effect", "at": prepared_effect["at"],
                    "phase": self.ctx.effect_phase, "payload": {"source": source, "cast": cast_id,
                        "effect": prepared_effect["effect"], "condition": prepared_effect["condition"]}}))
            cast["tasks"].append(next_task)
            schedule.append(Intent("schedule", data={"kind": "domain.ability.finish", "at": finish_at,
                "phase": self.ctx.effect_phase, "payload": {"source": source, "cast": cast_id}}))
            runtime.setdefault("casts", {})[cast_id] = cast
            runtime["next_cast_id"] = sequence + 1
            runtime.setdefault("cooldowns", {})[ability_id] = finish_at + self.ctx.quantize(recovery)
            if mode == "automatic_attack" or params.get("replace_attack"):
                interval = self.ctx.calc("time.interval", {"base_interval": activation.get("interval_seconds",
                    self.ctx.role_value(source, "attack_interval")), "speed": self.ctx.role_value(source, "attack_speed_ratio"),
                    "adjustments": []}, source=source, ability=ability, rule_id=activation.get("interval_rule"))
                interval_units = self.ctx.quantize(interval)
                if interval_units < 1:
                    raise ValueError("Automatic attack interval must advance logical time")
                runtime["next_attack"] = now + interval_units
            self.ctx.session.commit(payment + [Intent("set", source, ("runtime",), runtime)] + schedule)
            cast["payments"] = [{"holder": holder, "resource": resource,
                "amount": max(0, before-self.ctx.resources.current(holder, resource)), "allocated": 0}
                for (holder, resource), before in resources_before.items()]
            self.ctx.set(source, ("runtime", "casts", cast_id), cast)
            started_event = self.ctx.emit("ability.started", {"source": source, "ability": ability_id, "cast": cast_id, "targets": targets}, cause=cause)
            if ability.get("wait_for_channels"):
                self.ctx.set(source, ("runtime", "casts", cast_id, "started_event"), started_event)
            for (holder, resource), before in resources_before.items():
                current = self.ctx.resources.current(holder, resource)
                event = {"source": source, "target": holder, "resource": resource,
                         "delta": current - before, "value": current, "ability": ability_id, "cast": cast_id,
                         "reason": "ability_cost"}
                self.ctx.emit("resource.changed", event, cause=started_event)
                if self.ctx.lifecycle is not None:
                    self.ctx.lifecycle.check(holder, event)
            if activation.get("on_start") and getattr(self.ctx, 'active', self.ctx.alive)(source) and self._active(source, cast_id):
                for effect in activation.get("on_start", ()):
                    self.ctx.effects.execute(source, targets, thaw(effect), ability, cast, started_event)
                if getattr(self.ctx, 'active', self.ctx.alive)(source) and self._active(source, cast_id):
                    active = self.ctx.get(source, ("runtime", "casts", cast_id))
                    active["source_snapshot"] = getattr(self.ctx, "capture_view", self.ctx.entity)(source)
                    active["target_snapshots"] = {str(target): getattr(self.ctx, "capture_view", self.ctx.entity)(target) for target in targets}
                    self.ctx.set(source, ("runtime", "casts", cast_id), active)
            if getattr(self.ctx,'behavior',None) is not None:
                self.ctx.behavior.refresh(source)
            return cast_id

    def _active(self, source, cast_id):
        try:
            return self.ctx.get(source, ("runtime", "casts"), {}).get(cast_id)
        except KeyError:
            return None

    def handle_effect(self, session, payload):
        source, cast_id = payload["source"], payload["cast"]
        cast = self._active(source, cast_id)
        if not cast or not getattr(self.ctx, 'active', self.ctx.alive)(source):
            return
        ability = self._definition(cast["ability"])
        if not self._condition(payload.get("condition"), source, ability):
            return
        targets = cast["targets"]
        if ability.get("target_capture") == "each_hit" and ability.get("selector"):
            targets = self.ctx.spatial.select(source, ability["selector"], ability=ability, effect=payload["effect"])
        self.ctx.effects.execute(source, targets, payload["effect"], ability=ability, cast=cast)

    def bind_buff(self, source, cast_id, target, instance):
        if instance is None:
            return
        cast = self._active(source, cast_id)
        if cast is None:
            raise ValueError('Cast-bound buff requires an active owned cast')
        row = {'target': self.ctx.session.world.resolve(target), 'instance': instance}
        for other in self.ctx.get(source, ('runtime', 'casts'), {}).values():
            if other['id'] != cast_id and row in other.get('owned_buffs', []):
                raise ValueError('Buff lease cannot be shared across active casts')
        owned = cast.setdefault('owned_buffs', [])
        if row not in owned:
            owned.append(row)
            self.ctx.set(source, ('runtime', 'casts', cast_id), cast)

    def _release_cast_buffs(self, source, cast):
        for row in cast.get('owned_buffs', []):
            self.ctx.buffs.remove(row['target'], row['instance'])

    def channel_started(self, source, cast_id):
        cast = self._active(source, cast_id)
        if cast is None or 'pending_channels' not in cast:
            raise ValueError('Owned channel requires explicit wait_for_channels')
        cast['pending_channels'] += 1
        self.ctx.set(source, ('runtime', 'casts', cast_id), cast)

    def channel_finished(self, source, cast_id):
        cast = self._active(source, cast_id)
        if cast is None:
            return
        if cast.get('pending_channels', 0) < 1:
            raise ValueError('Channel completion has no pending owner')
        cast['pending_channels'] -= 1
        self.ctx.set(source, ('runtime', 'casts', cast_id), cast)
        if cast.get('finish_requested') and not cast['pending_channels'] and not cast.get('pending_projectiles', 0):
            self.finish(self.ctx.session, {'source': source, 'cast': cast_id})

    def finish(self, session, payload):
        cast = self._active(payload["source"], payload["cast"])
        if cast and ("owned_buffs" in cast or "pending_channels" in cast):
            with session.atomic():
                return self._finish(session, payload)
        return self._finish(session, payload)

    def _finish(self, session, payload):
        source, cast_id = payload["source"], payload["cast"]
        cast = self._active(source, cast_id)
        if not cast:
            return
        if cast.get("pending_projectiles", 0) or cast.get("pending_channels", 0):
            cast["finish_requested"] = True
            self.ctx.set(source, ("runtime", "casts", cast_id), cast)
            return
        casts = self.ctx.get(source, ("runtime", "casts"), {})
        del casts[cast_id]
        self.ctx.set(source, ("runtime", "casts"), casts)
        self._release_cast_buffs(source, cast)
        if "pending_channels" in cast:
            self.ctx.set(source, ("runtime", "cooldowns", cast["ability"]), session.time+cast["channel_recovery_units"])
        if cast["parameters"].get("wait_for_projectiles"):
            self.ctx.set(source, ("runtime", "cooldowns", cast["ability"]), session.time+cast["recovery_units"])
        self.ctx.emit("ability.finished", {"source": source, "ability": cast["ability"], "cast": cast_id})

    def projectile_started(self, source, cast_id):
        cast = self._active(source, cast_id)
        if cast is None:
            raise ValueError("waiting projectile requires an active cast")
        cast["pending_projectiles"] += 1
        self.ctx.set(source, ("runtime", "casts", cast_id), cast)

    def projectile_finished(self, source, cast_id):
        cast = self._active(source, cast_id)
        if cast is None:
            return  # An interrupted source does not own the in-flight packet.
        if cast["pending_projectiles"] < 1:
            raise ValueError("projectile completion without a pending packet")
        cast["pending_projectiles"] -= 1
        self.ctx.set(source, ("runtime", "casts", cast_id), cast)
        if cast.get("finish_requested") and not cast["pending_projectiles"]:
            self.finish(self.ctx.session, {"source": source, "cast": cast_id})

    def interrupt(self, source, reason, ability_ids=None, modes=None):
        with self.ctx.session.atomic():
            source = self.ctx.session.world.resolve(source)
            casts = self.ctx.get(source, ("runtime", "casts"), {})
            selected = {key: cast for key, cast in casts.items()
                if (ability_ids is None or cast["ability"] in ability_ids) and (modes is None or
                    cast.get("activation_mode", self._definition(cast["ability"]).get("activation", {}).get("mode")) in modes)}
            pending = {task["id"] for task in self.ctx.session.scheduler.pending}
            intents = [Intent("cancel", data={"task_id": task_id}) for cast in selected.values()
                       for task_id in cast["tasks"] if task_id in pending]
            intents.append(Intent("set", source, ("runtime", "casts"), {key: cast for key, cast in casts.items() if key not in selected}))
            self.ctx.session.commit(intents)
            for cast in selected.values():
                if getattr(self.ctx, "attachments", None) is not None: self.ctx.attachments.cancel_cast(source, cast["id"])
                self._release_cast_buffs(source, cast)
                self.ctx.emit("ability.interrupted", {"source": source, "ability": cast["ability"],
                                                      "cast": cast["id"], "reason": reason})
            return len(selected)

    def tick(self, session):
        if self.ctx.state().get("finished"):
            return
        for entity in session.world.entities():
            source = entity["id"]
            if not getattr(self.ctx, 'active', self.ctx.alive)(source):
                continue
            runtime = self.ctx.get(source, ("runtime",), {})
            abilities = [self._definition(identifier) for identifier in entity["components"].get("abilities", ())]
            replace_ready = None
            for ability in abilities:
                mode = ability.get("activation", {}).get("mode")
                params = self._params(ability)
                if mode == "manual" and (params.get("auto_when_ready") or params.get("automatic")):
                    if params.get("replace_attack"):
                        try:
                            for holder, costs in self._cost_groups(source, ability).items():
                                self.ctx.resources.payment_plan(holder, costs, ability=ability, source=source)
                        except ValueError as exc:
                            if str(exc).startswith("insufficient resource"):
                                continue
                            raise
                        replace_ready = ability
                    else:
                        try:
                            self.start(source, ability["id"], automatic=True)
                        except ActivationRejected:
                            pass
            runtime = self.ctx.get(source, ("runtime",), {})
            if runtime.get("behavior_decision", {}).get("attack") is False:
                continue
            if not self.ctx.buffs.controls(source)["attack"]:
                continue
            if runtime.get("next_attack", 0) > session.time:
                continue
            for ability in abilities:
                if ability.get("activation", {}).get("mode") != "automatic_attack":
                    continue
                selected = replace_ready or ability
                try:
                    cast_id = self.start(source, selected["id"], automatic=True)
                except ActivationRejected:
                    if replace_ready:
                        try:
                            self.start(source, ability["id"], automatic=True)
                        except ActivationRejected:
                            continue
                        break
                    continue
                break

    def notify(self, event, payload, cause=None):
        for entity in self.ctx.session.world.entities():
            source = entity["id"]
            if not getattr(self.ctx, 'active', self.ctx.alive)(source):
                continue
            for ability_id in entity["components"].get("abilities", ()):
                ability = self._definition(ability_id)
                for subscription in ability.get("events", ()):
                    if subscription["event"] != event:
                        continue
                    context = {"owner": self.ctx.entity(source), "source": self.ctx.entity(source),
                               "time": self.ctx.session.time, "ability": ability}
                    condition = subscription.get("condition")
                    if condition and not evaluate_expression(condition, {"event": event, "payload": payload},
                            {**self._params(ability), **subscription.get("parameters", {})}, context):
                        continue
                    target = payload.get("target")
                    try:
                        selected = [self.ctx.session.world.resolve(target)] if target is not None else [source]
                    except (KeyError, ValueError):
                        selected = [source]
                    for effect in subscription.get("effects", ()):
                        self.ctx.effects.execute(source, selected, thaw(effect), ability=ability, cause=cause)
                activation = ability.get("activation", {})
                events = activation.get("events", ()) or [activation.get("event")]
                mode = activation.get("mode")
                if mode == "on_deploy" and not activation.get("event") and not activation.get("events"):
                    events = ("entity.deployed", "unit.deployed", "deploy")
                if mode not in {"passive", "on_deploy"} or event not in events:
                    continue
                if mode == "on_deploy" and source not in (payload.get("source"), payload.get("target"), payload.get("entity")):
                    continue
                if not self._condition(activation.get("condition"), source, ability, payload):
                    continue
                try:
                    self.start(source, ability_id, automatic=True, event_payload=payload, cause=cause)
                except ActivationRejected:
                    continue
