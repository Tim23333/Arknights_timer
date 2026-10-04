"""Composable effects: collect rule results, then submit state intents."""
import math
from contextlib import nullcontext
from ark_sim.contracts import Intent, thaw
from ark_sim.rules import evaluate_expression


class EffectSystem:
    def __init__(self, context):
        self.ctx = context

    def targets(self, source, targets, mode):
        if mode in ("source", "self"):
            return [source]
        if mode in ("scenario", "battle"):
            return [self.ctx.session.world.resolve("system/battle")]
        if mode in ("selected", "target"):
            return list(targets)
        if isinstance(mode, int):
            return [self.ctx.session.world.resolve(mode)]
        raise ValueError(f"unsupported effect target {mode}")

    def execute(self, source, targets, effect, ability=None, cast=None, cause=None):
        with self.ctx.session.atomic():
            return self._execute(source, targets, effect, ability, cast, cause)

    def _execute(self, source, targets, effect, ability=None, cast=None, cause=None):
        if effect.get('op') == 'restart_behavior':
            from .behavior_restart import validate
            validate(effect)
        if effect.get('op') == 'no_source_damage':
            from .no_source_damage import execute
            return execute(self, source, targets, effect, ability, cast, cause)
        if effect.get("op") == "begin_attachment" or "damage_flags" in effect or "bind_to_cast" in effect or "selection_projection" in effect:
            from ark_sim.content.schemas import validate_effect, DEFAULT_CAPABILITIES
            validate_effect(effect, "runtime.explicit_owned_effect", DEFAULT_CAPABILITIES)
        source = self.ctx.session.world.resolve(source)
        ability, cast = ability or {}, cast or {}
        if cast.get('terminal_lifecycle'):
            from .terminal_lifecycle import cast_valid
            if not cast_valid(self.ctx,source,cast):
                projectiles=getattr(self.ctx,'projectiles',None)
                if projectiles is None or not targets or not all(projectiles.retained_payload_allowed(source,target,cast) for target in targets):return
        if cast.get('waiting_action') and (not self.ctx.waiting_actions.cast_allowed(source,cast) or self.ctx.waiting_actions.current(source,cast.get('ability'))!=cast['waiting_action']):return
        if getattr(self.ctx,"rebirth",None) is not None and not self.ctx.rebirth.callback_allowed():return
        if (not self.ctx.get(source, ('runtime', 'active'), True) and self.ctx.get(source, ('runtime', 'state')) == 'dormant'
                and effect['op'] not in {'activate_predefined', 'retire', 'emit', 'remove_buff', 'remove_terrain_overlay'}):
            self.ctx.emit('effect.source_inactive_rejected', {'source': source, 'targets': list(targets), 'operation': effect['op']}, cause)
            return
        if cast.get("control_instance") and not self.ctx.controls.effect_allowed(cast): return
        if (cast.get("projectile_impact") and getattr(self.ctx, "route_hidden", lambda ref: False)(source) and
                self.ctx.visibility_policy(source).get("launched_source_effects", "retain") == "discard"):
            return
        condition = effect.get("condition")
        if condition and not evaluate_expression(condition, {"source": self.ctx.entity(source) if source is not None else {},
                "targets": [self.ctx.entity(t) for t in targets], "time": self.ctx.session.time}, effect.get("parameters", {})):
            return
        if effect["op"] == "finish_timeline_wave":
            if getattr(self.ctx,'timeline',None) is None:raise ValueError('Timeline finish request requires an actual timeline')
            self.ctx.timeline.finish_current(source,effect,cause)
            return
        if effect["op"] == "advance_branch":
            if getattr(self.ctx,"branches",None) is None:raise ValueError("branch program feature not loaded")
            self.ctx.branches.advance(effect["parameters"]["branch"],source,cause)
            return
        if effect["op"] == "spawn_on_tiles":
            from .tile_targets import spawn_on_tiles
            spawn_on_tiles(self.ctx, source, effect, ability, cast, cause)
            return
        if effect.get("selector"):
            targets = self.ctx.spatial.select(source, effect["selector"], ability=ability, effect=effect,
                primary=effect.get("parameters", {}).get("primary_target"))
        selected = self.targets(source, targets, effect.get("target", "selected"))
        for target in selected:
            if cast.get("control_instance") and not self.ctx.controls.effect_allowed(cast): return
            target = self.ctx.session.world.resolve(target)
            operation = effect["op"]
            waiting_self_area=operation=='area' and effect.get('center','target')=='source' and target==source and getattr(self.ctx,'waiting_actions',None) is not None and self.ctx.waiting_actions.source_allowed(source)
            if (not waiting_self_area and operation not in {'activate_predefined', 'retire', 'emit', 'remove_buff', 'remove_terrain_overlay'}
                    and not (operation == 'area' and effect.get('center_position') is not None)
                    and not self.ctx.get(target, ('runtime', 'active'), True)
                    and operation != "instant_kill"
                    and not (getattr(self.ctx,"rebirth",None) is not None and self.ctx.rebirth.effect_allowed(target))):
                self.ctx.emit('effect.inactive_rejected', {'source': source, 'target': target, 'operation': operation}, cause)
                continue
            health_delta = operation == "modify_resource" and (
                self.ctx.get(target, ("resources", effect.get("resource"), "spec", "role")) == "health" or
                effect.get("resource") == self.ctx.program.ruleset.get("parameters", {}).get("health_resource"))
            if not waiting_self_area and not (operation == "area" and effect.get("center_position") is not None) and (health_delta or operation in {"damage", "heal", "regenerate", "apply_buff", "area", "push", "move", "displace", "trigger_ability", "set_motion_mode"}) and not getattr(self.ctx, "effect_target_available", lambda ref: True)(target) and not (getattr(self.ctx,"rebirth",None) is not None and self.ctx.rebirth.effect_allowed(target)):
                self.ctx.emit("effect.visibility_rejected", {"source": source, "target": target, "operation": operation}, cause)
                continue
            if operation == "instant_kill":
                if getattr(self.ctx,"rebirth",None) is None:raise ValueError("instant_kill feature not compiled")
                self.ctx.rebirth.instant_kill(source,target,effect["parameters"],ability,cast,cause)
            elif operation == 'activate_predefined':
                if target != self.ctx.session.world.resolve('system/battle'):
                    raise ValueError('predefined activation effect targets battle registry')
                self.ctx.lifecycle.activate_predefined(effect['parameters']['key'])
            elif operation == "random":
                sample = self.ctx.session.random.sample(effect["stream"])
                accepted = self.ctx.calc("random.check", {"sample": sample, "probability": effect.get("probability", 1)},
                    source=source, target=target, ability=ability, effect=effect)
                event = self.ctx.emit("random.branch", {"source": source, "target": target, "stream": effect["stream"],
                    "value": sample, "accepted": accepted}, cause)
                for child in effect.get("on_success" if accepted else "on_failure", ()):
                    child = thaw(child)
                    child.setdefault("parameters", {})["random_sample"] = sample
                    self.execute(source, [target], child, ability, cast, event)
                    if cast.get("control_instance") and not self.ctx.controls.effect_allowed(cast): return
                continue
            elif operation == "area":
                if self._projectile(source, target, effect, ability, cast, cause):
                    continue
                center = source if effect.get("center", "target") == "source" else target
                position = effect.get("center_position") or self.ctx.get(center, ("spatial", "position"))
                members = []
                if effect.get("membership_rule"):
                    candidates = [entity for entity in self.ctx.session.world.entities()
                        if entity["components"].get("spatial", {}).get("position") is not None
                        and getattr(self.ctx, "selectable", self.ctx.alive)(entity["id"])
                        and self.ctx.spatial.available(source,entity["id"],ability=ability,effect=effect,observable=True)
                        and not any("tag" in f and f["tag"] not in entity["tags"] for f in effect.get("filters", []))]
                    area_extra = {"ability": ability, "effect": effect}
                    member_rule = self.ctx.rules.rules[effect["membership_rule"]]
                    if member_rule["implementation"].get("provider") == "ark.area.qualified_cell_offsets":
                        from .qualified_areas import projection
                        options = {**thaw(member_rule.get("parameters", {})), **thaw(effect.get("parameters", {}))}
                        area_extra["area_selection_states"] = projection(self.ctx, source, candidates, options)
                    if member_rule['implementation'].get('provider')=='model.area.qualified_radius':
                        from .death_projectiles import radius_projection
                        options={**thaw(member_rule.get('parameters',{})),**thaw(effect.get('parameters',{}))}
                        area_extra['area_selection_states']=radius_projection(self.ctx,source,candidates,options)
                    if effect.get('selection_projection'):
                        defaults=effect['selection_projection']['defaults']
                        area_extra['area_selection_states']={
                            'source':self.ctx.spatial.selection_state(source,defaults),
                            'candidates':{str(actor['id']):self.ctx.spatial.selection_state(actor['id'],defaults) for actor in candidates}}
                    result = self.ctx.calc("area.members", {"center_position": position,
                        "candidates": candidates, "parameters": thaw(effect.get("parameters", {}))},
                        source=source, target=target, owner=source, ability=ability, effect=effect, rule_id=effect["membership_rule"], extra=area_extra)
                    members = thaw(result)
                    allowed = {entity["id"] for entity in candidates}
                    if not isinstance(members, list) or any(type(ref) is not int or ref not in allowed for ref in members) or len(members)!=len(set(members)):
                        raise ValueError("area.members must return unique allowed integer candidate IDs")
                for entity in (() if effect.get("membership_rule") else self.ctx.session.world.entities()):
                    pos = entity["components"].get("spatial", {}).get("position")
                    if pos is None or not getattr(self.ctx, "selectable", self.ctx.alive)(entity["id"]):
                        continue
                    if not self.ctx.spatial.available(source,entity["id"],ability=ability,effect=effect,observable=True):
                        continue
                    if math.hypot(pos["row"]-position["row"], pos["col"]-position["col"]) > effect["radius"]:
                        continue
                    if any("tag" in f and f["tag"] not in entity["tags"] for f in effect.get("filters", [])):
                        continue
                    members.append(entity["id"])
                area_cause = self.ctx.emit("area.resolved", {"source": source, "target": target, "center": position,
                    "members": members, **({"membership_rule": effect["membership_rule"], "parameters": thaw(effect.get("parameters", {}))}
                    if effect.get("membership_rule") else {"radius": effect["radius"]})}, cause)
                projectile=getattr(self.ctx,"projectiles",None)
                scope=projectile.payload_area(source,cast,members) if projectile is not None else nullcontext()
                with scope:
                    for child in effect["effects"]:
                        self.execute(source, members, child, ability, cast, area_cause)
                continue
            elif operation in ("damage", "heal", "regenerate"):
                if not self.ctx.alive(target):
                    continue
                if self._projectile(source, target, effect, ability, cast, cause):
                    continue
                actual = self._settle(source, target, effect, ability, cast, cause)
                if actual is None:
                    continue
                for child in effect.get("on_success", ()):
                    self.execute(source, [target], child, ability, cast, cause)
                sp = ability.get("activation", {}).get("parameters", {}).get("sp_resource")
                recovery = ability.get("activation", {}).get("parameters", {}).get("recovery_per_attack", 0)
                params = ability.get("activation", {}).get("parameters", {})
                is_attack = (ability.get("activation", {}).get("mode") == "automatic_attack" or
                             params.get("replace_attack") or params.get("counts_as_attack") or recovery)
                if operation == "damage" and is_attack and effect.get("damage_flags", {}).get("source_attack_type", "NORMAL") == "NORMAL" and self.ctx.alive(source) and not cast.get("attack_recovery_claimed"):
                    with self.ctx.session.atomic():
                        if self._claim_attack_recovery(source, cast):
                            if sp and recovery:
                                self.ctx.resources.adjust(source, sp, recovery, source=source, ability=ability, effect=effect)
                            self.ctx.emit("attack.accepted", {"source": source, "target": target,
                                "ability": ability.get("id"), "cast": cast.get("id"), "amount": actual}, cause)
                            cast["attack_recovery_claimed"] = True
            elif operation == "modify_resource":
                if effect.get("parameters", {}).get("if_resource_present") and effect["resource"] not in self.ctx.get(target, ("resources",), {}):
                    continue
                value = effect.get("value")
                if effect.get("amount_rule"):
                    value = self.ctx.calc("resource.recovery", {"current": self.ctx.resources.current(target, effect["resource"]),
                        "delta_seconds": 0, "attributes": self.ctx.attributes.values(target), "parameters": thaw(effect.get("parameters", {}))},
                        source=source, target=target, owner=target, ability=ability, effect=effect, rule_id=effect["amount_rule"])
                if effect.get("parameters", {}).get("respect_recovery_freeze"):
                    current = self.ctx.resources.current(target, effect["resource"])
                    gain = (value if value is not None else current+effect.get("delta", effect.get("amount", 0))) > current
                    captured = cast.get("recovery_snapshot")
                    frozen = self.ctx.resources._recovery_frozen(self.ctx.entity(target), self.ctx.resources._spec(target, effect["resource"]), effect["resource"]) if captured is None else next((row["frozen"] for row in captured if row["owner"] == target and row["resource"] == effect["resource"]), True)
                    if gain and frozen:
                        self.ctx.emit("resource.recovery_suppressed", {"source": source, "target": target, "resource": effect["resource"], "reason": "active_cast"}, cause)
                        continue
                self.ctx.resources.adjust(target, effect["resource"], effect.get("delta", effect.get("amount")),
                    value=value, source=source, ability=ability, effect=effect)
            elif operation == "begin_attachment":
                if self.ctx.attachments is None: raise ValueError("Attachment capability was not loaded")
                self.ctx.attachments.begin(source, target, effect["attachment"], ability, cast, cause)
            elif operation == "buff_application":
                from .buff_application import execute
                execute(self, source, target, effect, cause, cast=cast)
            elif operation == "apply_buff":
                if effect.get("bind_to_cast") and not self.ctx.abilities._active(source, cast.get("id")):
                    raise ValueError("Cast-bound buff has no active owner")
                if effect.get("bind_to_cast"):
                    self.ctx.abilities.apply_cast_buff(source, cast.get("id"), target, effect["buff"], effect.get("stacks", 1))
                else:
                    self.ctx.buffs.apply(source, target, effect["buff"], effect.get("stacks", 1))
            elif operation == "remove_buff":
                if effect.get("remove_all"):
                    for item in self.ctx.get(target, ("buffs", "instances"), []):
                        self.ctx.buffs.remove(target, item["id"])
                else:
                    self.ctx.buffs.remove(target, effect.get("buff"))
            elif operation == "emit":
                self.ctx.emit(effect.get("event", effect.get("type", "custom")),
                    {**effect.get("payload", {}), "source": source, "target": target}, cause)
            elif operation == "apply_terrain_overlay":
                if self.ctx.terrain is None:
                    raise ValueError("terrain overlay capability was not loaded by this program")
                self.ctx.terrain.apply(target, effect["parameters"])
            elif operation == "remove_terrain_overlay":
                if self.ctx.terrain is None:
                    raise ValueError("terrain overlay capability was not loaded by this program")
                self.ctx.terrain.remove(target, effect["parameters"]["key"])
            elif operation == "retire":
                if target == self.ctx.session.world.resolve("system/battle"):
                    raise ValueError("retire effects cannot remove the reserved battle entity")
                self.ctx.lifecycle.retire(target, effect["parameters"]["reason"])
            elif operation == "input_lock":
                options = effect["parameters"]
                key = options["key"]
                if cast.get("control_instance"):
                    key = self.ctx.controls.lock_key(cast["control_instance"], key, options["enabled"])
                elif getattr(self.ctx, "controls", None) is not None and key.startswith("control/"):
                    raise ValueError("control/ input-lock keys are reserved for control ownership")
                locks = self.ctx.state().get("input_locks", [])
                locks = [item for item in locks if item != key]
                if options["enabled"]:
                    locks.append(key)
                self.ctx.state_update(input_locks=locks)
                self.ctx.emit("input.lock_changed", {"source": source, "target": target,
                    "key": key, "enabled": options["enabled"]}, cause)
            elif operation in ("state", "transition"):
                self.ctx.behavior.transition(target, effect["state"], cause=cause)
            elif operation == 'restart_behavior':
                from .behavior_restart import execute
                execute(self.ctx, source, target, effect, cause)
            elif operation == "set_motion_mode":
                self.ctx.movement.set_motion_mode(source,target,effect["value"])
            elif operation in ("move", "displace"):
                self.ctx.movement.displace(source, target, effect, ability)
            elif operation == "push":
                self.ctx.movement.push(source, target, effect, ability)
            elif operation == "spawn":
                owner = source if effect.get("owner") == "source" else target if effect.get("owner") == "target" else None
                maximum = effect.get("parameters", {}).get("max_owned")
                if maximum is not None and owner is not None:
                    count = sum(e["definition_id"] == effect["definition"] and self.ctx.alive(e["id"])
                        and e["components"].get("ownership", {}).get("owner") == owner for e in self.ctx.session.world.entities())
                    if count >= maximum:
                        raise ValueError("owned spawn capacity exceeded")
                position, facing = effect.get("position"), effect.get("facing")
                deployment = None
                if effect.get("parameters", {}).get("position_from_payload"):
                    position = cast.get("event_payload", {}).get("position")
                    facing = cast.get("event_payload", {}).get("facing", facing)
                    if not isinstance(position, dict) or set(position) != {"row", "col"} or any(type(position[k]) is not int for k in ("row", "col")):
                        raise ValueError("owned deployment requires explicit integer payload.position")
                    if not self.ctx.spatial.grid.inside(position["row"], position["col"]):
                        raise ValueError("owned deployment position outside map")
                    if facing is not None and facing not in {"right", "left", "up", "down"}:
                        raise ValueError("owned deployment requires a declared facing")
                    from .deployment import prepare
                    facing = facing or (self.ctx.get(owner, ("spatial", "facing"), "right") if owner is not None else "right")
                    deployment = prepare(self.ctx, effect["definition"], position, facing, owner, paid=True)
                ref = self.ctx.lifecycle.create(effect["definition"], position or
                    (self.ctx.get(owner, ("spatial", "position")) if owner is not None else None),
                    facing or (self.ctx.get(owner, ("spatial", "facing"), "right") if owner is not None else "right"),
                    owner=owner, lifetime_seconds=effect.get("lifetime_seconds"),
                    deployed=deployment is not None,
                    on_owner_retire=effect.get("parameters", {}).get("on_owner_retire", "retain"))
                if deployment is not None:
                    from .deployment import record
                    paid = self._claim_deployment_payment(source, cast, effect, deployment["resource"])
                    record(self.ctx, ref, deployment, paid_cost=paid)
            elif operation == "trigger_ability":
                self.ctx.abilities.start(target, effect["ability"], automatic=True, cause=cause)
            elif operation == "schedule":
                self.ctx.session.schedule("domain.effect", {"source": source, "targets": [target],
                    "effect": thaw(effect["effect"]), "ability": thaw(ability), "cast": thaw(cast), "cause": cause},
                    self.ctx.session.time + self.ctx.quantize(effect.get("delay_seconds", effect.get("at_seconds", 0))),
                    phase=self.ctx.effect_phase)
            else:
                raise ValueError(f"unimplemented effect {operation}")
            if getattr(self.ctx,"rebirth",None) is not None:self.ctx.rebirth.settle_callback(operation)
            if cast.get("control_instance") and not self.ctx.controls.settle_effect(cast, operation): return
            for child in effect.get("effects", ()):
                self.execute(source, [target], child, ability, cast, cause)

    def _claim_deployment_payment(self, source, cast, effect, resource):
        amount = effect.get("parameters", {}).get("deployment_payment_amount", 0)
        if not amount:
            return 0
        active = self.ctx.get(source, ("runtime", "casts", cast.get("id")), {})
        battle = self.ctx.session.world.resolve("system/battle")
        payment = next((p for p in active.get("payments", [])
                        if p["holder"] == battle and p["resource"] == resource), None)
        if payment is None or payment["amount"]-payment["allocated"] < amount:
            raise ValueError("owned deployment exceeds actual unallocated cast payment")
        payment["allocated"] += amount
        self.ctx.set(source, ("runtime", "casts", cast["id"]), active)
        self.ctx.emit("deployment.payment_allocated", {"source": source, "cast": cast["id"],
            "resource": resource, "amount": amount})
        return amount

    def _claim_attack_recovery(self, source, cast):
        """Claim one accepted attack, across targets, repeat tasks and projectiles.

        Persist active/in-flight cast claims in World so checkpoint and atomic
        rollback preserve them. Direct effect calls share their local cast view.
        The next claim prunes finished groups once no scheduled work refers to
        them, keeping long scenes bounded by outstanding attacks.
        """
        if cast.get("attack_recovery_claimed"):
            return False
        cast_id = cast.get("id")
        if cast_id is not None:
            runtime = self.ctx.get(source, ("runtime",), {})
            claims = runtime.get("attack_recovery_claims", [])
            if cast_id in claims:
                return False
            outstanding = set(runtime.get("casts", {}))
            if getattr(self.ctx, "projectiles", None) is not None:
                outstanding.update(self.ctx.projectiles.active_casts(source))
            for task in self.ctx.session.scheduler.pending:
                payload = task.get("payload", {})
                if payload.get("source") != source:
                    continue
                pending_cast = payload.get("cast")
                if isinstance(pending_cast, str):
                    outstanding.add(pending_cast)
                elif hasattr(pending_cast, "get") and pending_cast.get("id"):
                    outstanding.add(pending_cast["id"])
            runtime["attack_recovery_claims"] = [key for key in claims if key in outstanding] + [cast_id]
            self.ctx.session.commit([Intent("set", source, ("runtime",), runtime)])
        return True

    def handle(self, session, payload):
        with session.atomic():
            self.execute(payload["source"], payload["targets"], payload["effect"],
                         payload.get("ability"), payload.get("cast"), payload.get("cause"))
            cast = payload.get("cast", {})
            if payload.get("projectile_completion") and payload.get("ability", {}).get("parameters", {}).get("wait_for_projectiles"):
                self.ctx.abilities.projectile_finished(payload["source"], cast.get("id"))

    def _projectile(self, source, target, effect, ability, cast, cause):
        if effect.get("projectile_definition"):
            self.ctx.projectiles.launch(source,target,effect,ability,cast,cause)
            return True
        parameters = ability.get("parameters", {})
        speed = parameters.get("projectile_speed", 0)
        if not speed or cast.get("projectile_impact"):
            return False
        a = self.ctx.get(source, ("spatial", "position"))
        b = self.ctx.get(target, ("spatial", "position"))
        distance = math.hypot(a["row"]-b["row"], a["col"]-b["col"])
        velocity = self.ctx.calc("projectile.speed", {"projectile": parameters, "attributes": {},
                    "parameters": {"speed": speed}}, source=source, target=target, ability=ability, effect=effect)
        duration = self.ctx.calc("projectile.flight_time", {"distance": distance, "speed": velocity,
                    "timing_parameters": {}}, source=source, target=target, ability=ability, effect=effect)
        launched = dict(cast, projectile_impact=True)
        launched["launch_snapshot"] = self.ctx.capture_view(source)
        launched["launch_target_snapshots"] = {str(target): self.ctx.capture_view(target)}
        if parameters.get("wait_for_projectiles"):
            self.ctx.abilities.projectile_started(source, cast.get("id"))
        self.ctx.session.schedule("domain.effect", {"source": source, "targets": [target],
            "effect": thaw(effect), "ability": thaw(ability), "cast": launched, "cause": cause, "projectile_completion": True},
            self.ctx.session.time+self.ctx.quantize(duration), phase=self.ctx.effect_phase)
        self.ctx.emit("projectile.launched", {"source": source, "target": target,
                      "ability": ability.get("id"), "flight_seconds": duration}, cause)
        return True

    def _settle(self, source, target, effect, ability, cast, cause):
        was_alive = self.ctx.alive(target)
        death_generation = self.ctx.get(target,('runtime','death_generation'),0)
        mode = effect.get("read_mode", {}).get("source_attributes", "at_hit")
        snapshot = cast.get("source_snapshot") if mode == "at_cast" else cast.get("launch_snapshot") if mode == "at_launch" else None
        resource = effect.get("resource") or self.ctx.health_resource(target)
        if effect["op"] in ("heal", "regenerate"):
            spec = self.ctx.resources._spec(target, resource)
            if effect["op"] == "heal" and not spec.get("parameters", {}).get("healing_allowed", True) and not (
                    effect.get("parameters", {}).get("ignore_heal_immunity") or ability.get("parameters", {}).get("ignore_heal_immunity")):
                self.ctx.emit("healing.rejected", {"source": source, "target": target, "resource": resource, "reason": "resource_healing_disabled"}, cause)
                return None
            attack_key = self.ctx.attribute_role("attack")
            attack = self.ctx.attributes.value(source, attack_key, ability=ability, effect=effect, snapshot=snapshot)
            amount = self.ctx.calc("healing.base", {"attack": attack, "scale": effect.get("scale", 1),
                 "additions": effect.get("additions", 0)}, source=source, target=target, ability=ability, effect=effect)
            actual = self.ctx.resources.adjust(target, resource, amount, source=source, ability=ability, effect=effect)
            event = "regeneration.accepted" if effect["op"] == "regenerate" else "healing.accepted"
            self.ctx.emit(event, {"source": source, "target": target, "amount": actual}, cause)
            return actual
        scope = {"scenario": self.ctx.program.scenario.get("rules", {}) if hasattr(self.ctx.program, "scenario") else {},
                 "ability": ability.get("rules", {}), "effect": effect.get("rules", {})}
        if hasattr(self.ctx, "definition_bindings"):
            scope.update(source=self.ctx.definition_bindings(source), target=self.ctx.definition_bindings(target))
        rule_id, _ = self.ctx.rules.resolver.resolve("damage.pipeline", scope)
        rule = self.ctx.rules.rules[rule_id]
        request = {**thaw(effect), "scale": effect.get("scale", 1),
                   "additions": effect.get("additions", 0),
                   "damage_type": effect.get("damage_type", "physical")}
        bindings = rule.get("metadata", {}).get("input_bindings", {})
        for name, binding in bindings.items():
            source_role = binding["entity"] == "source"
            ref = source if source_role else target
            mode_key = "source_attributes" if source_role else "target_attributes"
            read_mode = effect.get("read_mode", {}).get(mode_key, "at_hit")
            if source_role:
                view = snapshot
            else:
                field = "target_snapshots" if read_mode == "at_cast" else "launch_target_snapshots" if read_mode == "at_launch" else None
                view = cast.get(field, {}).get(str(target)) if field else None
            role = binding.get("attribute_role")
            key = binding.get("attribute") or self.ctx.attribute_role(role)
            base = (view or self.ctx.entity(ref))["components"].get("attributes", {}).get("base", {})
            if key in base:
                request[name] = self.ctx.attributes.value(ref, key, ability=ability, effect=effect, snapshot=view)
            else:
                defaults = self.ctx.program.ruleset.get("parameters", {}).get("attribute_defaults", {})
                if key not in defaults:
                    raise ValueError(f"required pipeline attribute {key} is missing")
                request[name] = defaults[key]
        request, extras, accepted = self._damage_hooks("before", source, source, target, request, ability, cast, snapshot)
        if not accepted:
            self.ctx.emit("damage.rejected", {"source": source, "target": target, "reason": "source_hook"}, cause)
            return None
        settlement = self.ctx.calc("damage.pipeline", {"source": self.ctx.entity(source) if source is not None else {},
             "target": self.ctx.entity(target), "effect": request, "samples": [], "states": {}},
             source=source, target=target, ability=ability, effect=effect)
        settlement = self._canonical_settlement(settlement, source, target)
        post_request = {**request, "settlement": settlement}
        post_request, _, accepted = self._damage_hooks("after", target, source, target, post_request, ability, cast, snapshot)
        settlement = post_request["settlement"]
        if not accepted:
            settlement = {**settlement, "accepted": False}
        if not settlement["accepted"]:
            self.ctx.emit("damage.rejected", {"source": source, "target": target, "reason": "pipeline_or_target_hook"}, cause)
            for child in effect.get("on_failure", ()):
                self.execute(source, [target], child, ability, cast, cause)
            return None
        if settlement.get("allocations"):
            intents, notifications, actual = [], [], 0
            totals = {}
            for allocation in settlement["allocations"]:
                recipient = allocation.get("target", target)
                recipient = self.ctx.session.world.resolve(target if recipient == "target" else source if recipient == "source" else recipient)
                if not getattr(self.ctx, "effect_target_available", lambda ref: True)(recipient):
                    self.ctx.emit("effect.visibility_rejected", {"source": source, "target": recipient, "operation": "damage_allocation"}, cause)
                    continue
                key = allocation.get("resource", resource)
                change = allocation.get("delta", -allocation.get("amount", 0))
                group = (recipient, key)
                totals[group] = totals.get(group, 0)+change
            for (recipient, key), change in totals.items():
                plan, delta = self.ctx.resources.change_plan(recipient, key, change, source=source, ability=ability, effect=effect)
                intents.extend(plan)
                notifications.append((recipient, key, delta))
                if recipient == target and key == resource:
                    actual -= delta
            self.ctx.session.commit(intents)
            for recipient, key, delta in notifications:
                self.ctx.emit("resource.changed", {"source": source, "target": recipient, "resource": key, "delta": delta})
                self.ctx.lifecycle.check(recipient, {"operation":"damage","source":source,"target":recipient,"resource":key,"delta":delta,"ability":ability.get("id"),"cast":cast.get("id")})
        else:
            actual = -self.ctx.resources.adjust(target, resource, -settlement["amount"], source=source, ability=ability, effect=effect, settlement_context={"operation":"damage","source":source,"target":target,"resource":resource,"ability":ability.get("id"),"cast":cast.get("id")})
        state = self.ctx.state()
        state["damage_dealt"] = state.get("damage_dealt", 0)+actual
        self.ctx.state_update(**state)
        self.ctx.emit("damage.accepted", {"source": source, "target": target,
                     "amount": actual, "ability": ability.get("id"), "resource": resource,
                     **({"damage_flags": thaw(effect["damage_flags"])} if "damage_flags" in effect else {})}, cause)
        if was_alive and not self.ctx.alive(target) and self.ctx.get(target, ("runtime", "state")) == "dead":
            self.ctx.lifecycle.claim_combat_kill(target, {"source": source, "target": target, "ability": ability.get("id"),
                "cast": cast.get("id"), "target_tags": list(self.ctx.entity(target)["tags"])}, cause, generation=death_generation+1)
        for event in settlement.get("events", ()):
            self.ctx.emit(event["type"], event.get("payload", {}), cause)
        for extra in extras:
            self.execute(source, [target], extra, ability, cast, cause)
        return actual

    def _canonical_settlement(self, settlement, source, target):
        settlement = thaw(settlement)
        for allocation in settlement.get("allocations", []):
            recipient = allocation.get("target", target)
            allocation["target"] = self.ctx.session.world.resolve(
                target if recipient == "target" else source if recipient == "source" else recipient)
        return settlement

    def _damage_hooks(self, phase, holder, source, target, request, ability, cast, snapshot):
        extras = []
        locked = set(request.get("parameters", {}).get("damage_hook_locks", []))
        grouped = set()
        hooks = []
        for instance in self.ctx.get(holder, ("buffs", "instances"), []):
            if instance["definition"] in locked or (instance["expires_at"] is not None and self.ctx.session.time >= instance["expires_at"]):
                continue
            if getattr(getattr(self.ctx,'buffs',None),'applicability',None) is not None and not self.ctx.buffs.applicability.active(instance):continue
            definition = self.ctx.program.definitions[instance["definition"]]
            for hook in definition.get("damage_hooks", []):
                if hook["phase"] == phase:
                    hooks.append((hook, instance))
        hooks.sort(key=lambda pair: -pair[0].get("priority", 0))
        for hook, instance in hooks:
                group = hook.get("group")
                if group is not None and group in grouped:
                    continue
                context = {"owner": self.ctx.entity(holder), "source": self.ctx.entity(source) if source is not None else {},
                    "target": self.ctx.entity(target), "time": self.ctx.session.time, "buff": instance}
                def active_ids(ref):
                    if ref is None: return []
                    return [i["definition"] for i in self.ctx.get(ref, ("buffs", "instances"), [])
                        if i["expires_at"] is None or self.ctx.session.time < i["expires_at"]]
                from .selection import DEFAULT_STATE
                source_selection_state = self.ctx.spatial.selection_state(source, DEFAULT_STATE) if source is not None else {}
                target_selection_state = self.ctx.spatial.selection_state(target, DEFAULT_STATE)
                context.update(source_selection_state=source_selection_state, target_selection_state=target_selection_state, source_buff_ids=active_ids(source), target_buff_ids=active_ids(target), owner_buff_ids=active_ids(holder))
                if hook.get("condition") and not evaluate_expression(hook["condition"], {"effect": request,
                    "source": self.ctx.entity(source) if source is not None else {}, "target": self.ctx.entity(target)}, {}, context):
                    continue
                if group is not None:
                    grouped.add(group)
                rule = self.ctx.program.definitions[hook["rule"]]
                for name, binding in rule.get("metadata", {}).get("input_bindings", {}).items():
                    ref = source if binding["entity"] == "source" else target
                    if ref is None: raise ValueError("Target hook cannot bind absent source attributes")
                    view = snapshot if ref == source else None
                    key = binding.get("attribute") or self.ctx.attribute_role(binding["attribute_role"])
                    request[name] = self.ctx.attributes.value(ref, key, ability=ability, effect=request, snapshot=view)
                sampling = hook.get("samples", {})
                samples = [{"value": self.ctx.session.random.sample(sampling["stream"])}
                    for _ in range(sampling.get("count", 1))] if sampling else []
                result = self.ctx.calc("damage.request" if phase == "before" else "damage.pipeline", {
                    "source": self.ctx.entity(source) if source is not None else {}, "target": self.ctx.entity(target), "effect": request,
                    "samples": samples, "states": {"source_selection_state": source_selection_state, "target_selection_state": target_selection_state, "buff": instance, "source_buff_ids": context["source_buff_ids"],
                        "target_buff_ids": context["target_buff_ids"], "owner_buff_ids": context["owner_buff_ids"]}}, source=source, target=target, owner=holder,
                    ability=ability, effect=request, rule_id=hook["rule"], extra={"buff": instance, "owner": self.ctx.entity(holder)})
                if phase == "before":
                    if not result["accepted"]:
                        return request, extras, False
                    request = result["effect"]
                    for child in result["effects"]:
                        child = thaw(child)
                        child.setdefault("parameters", {})["primary_target"] = target
                        child["parameters"]["damage_hook_locks"] = sorted(locked |
                            set(child["parameters"].get("damage_hook_locks", [])) | {instance["definition"]})
                        extras.append(child)
                else:
                    request = {**request, "settlement": self._canonical_settlement(result, source, target)}
                    if not result["accepted"]:
                        return request, extras, False
        return request, extras, True
