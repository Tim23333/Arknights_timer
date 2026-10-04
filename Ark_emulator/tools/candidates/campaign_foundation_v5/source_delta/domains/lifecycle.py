"""Creation and lifecycle changes follow definitions and rule decisions."""
from ark_sim.contracts import Intent, thaw
from collections.abc import Mapping
import math


class LifecycleSystem:
    def __init__(self, context):
        self.ctx = context

    def create(self, *args, **kwargs):
        definition_id=args[0] if args else kwargs.get('definition_id')
        definition=self.ctx.program.definitions.get(definition_id,{})
        has_connectivity=('connectivity' in definition.get('components',{}).get('deployable',{}) or
            'connectivity' in (kwargs.get('component_overrides') or {}).get('deployable',{}))
        from .ability_timing import requires_atomic
        has_initial_clocks=requires_atomic(self.ctx,definition,kwargs.get("component_overrides") or {})
        from .ability_arbitration import requires_atomic as needs_arbitration_atomic
        has_initial_clocks=has_initial_clocks or needs_arbitration_atomic(definition,kwargs.get("component_overrides") or {})
        if not has_initial_clocks and "tile_occupancy" not in definition.get("components",{}) and "tile_occupancy" not in (kwargs.get("component_overrides") or {}) and not has_connectivity and self.ctx.terrain is None and self.ctx.tile_contacts is None and kwargs.get('active', True) and kwargs.get('registration_key') is None:
            return self._create(*args, **kwargs)
        with self.ctx.session.atomic():
            ref=self._create(*args, **kwargs)
            if has_connectivity and self.ctx.active(ref):
                from .deploy_connectivity import inspect
                inspect(self.ctx,self.ctx.definition(ref),self.ctx.get(ref,('spatial','position')),self.ctx.get(ref,('deployable',)),entity=self.ctx.entity(ref),phase='created')
            return ref

    def _create(self, definition_id, position=None, facing="right", route=None, alias=None, parameters=None,
               deployed=False, component_overrides=None, rule_overrides=None, tags=None,
               owner=None, lifetime_seconds=None, on_owner_retire="retain", *, active=True, registration_key=None):
        if type(active) is not bool:
            raise ValueError('initial active state must be boolean')
        if not active and type(deployed) is not bool:
            raise ValueError('dormant deployed state must be boolean')
        if registration_key is not None:
            if not isinstance(registration_key, str) or not registration_key:
                raise ValueError('registration key must be a nonempty string')
            if registration_key in self.ctx.state().get('predefined_registry', {}):
                raise ValueError('duplicate registration key')
        if alias is not None and (not isinstance(alias, str) or not alias):
            raise ValueError("entity alias must be a nonempty string or null")
        controls = getattr(self.ctx, "controls", None)
        if alias is not None and controls is not None and (alias.startswith("control/") or controls.alias_exists(alias)):
            raise ValueError("actor alias collides with a control alias")
        definition = self.ctx.program.definitions[definition_id]
        if 'tile_field_owner' in definition.get('tags',[]) and route is not None:
            raise ValueError('static tile field route argument is forbidden')
        if definition.get("kind") != "entity":
            raise ValueError(f"{definition_id} is not an entity definition")
        components = thaw(definition.get("components", {}))
        def merge(base, overrides):
            for key, value in overrides.items():
                if isinstance(value, dict) and isinstance(base.get(key), dict):
                    merge(base[key], value)
                else:
                    base[key] = thaw(value)
        merge(components, thaw(component_overrides or {}))
        if "ability_arbitration" in components:
            from .ability_arbitration import validate as validate_arbitration
            validate_arbitration(components["ability_arbitration"],components.get("abilities",[]),self.ctx.program.definitions)
        if 'death_projectiles' in components.get('lifecycle',{}):
            from .death_projectiles import validate_effective
            validate_effective(self.ctx,components)
        if "rebirth" in components:
            from .rebirth import validate
            validate(components["rebirth"],components,self.ctx.program.definitions)
            if getattr(self.ctx,"rebirth",None) is None:raise ValueError("rebirth feature was not compiled into runtime")
        connectivity=components.get('deployable',{})
        if 'connectivity' in connectivity:
            from .deploy_connectivity import validate_profile
            validate_profile(connectivity['connectivity'])
        from .deployment import cooldown_start
        cooldown_start(components.get('deployable',{}))
        parameters = parameters or {}
        ownership = components.get("ownership", {})
        owner = owner if owner is not None else parameters.get("owner", ownership.get("owner"))
        if owner is not None:
            components["ownership"] = {"owner": self.ctx.session.world.resolve(owner),
                "on_owner_retire": ownership.get("on_owner_retire", on_owner_retire)}
        lifetime_seconds = lifetime_seconds if lifetime_seconds is not None else parameters.get("lifetime_seconds")
        from .tile_fields import validate_effective_owner
        validate_effective_owner(self.ctx.program.definitions,definition,components,
                                 definition.get('tags',[]) if tags is None else tags)
        if not active and lifetime_seconds is not None and (type(lifetime_seconds) not in (int, float) or not math.isfinite(lifetime_seconds) or lifetime_seconds < 0):
            raise ValueError('dormant lifetime must be nonnegative finite seconds')
        self.ctx.attributes.initialize(definition, components, instance_rules=rule_overrides)
        resources = components.get("resources", {})
        components["resources"] = {key: {"current": spec.get("initial", 0), "spec": spec} for key, spec in resources.items()}
        spatial = components.setdefault("spatial", {})
        spatial["position"] = dict(position or spatial.get("position", {"row": 0, "col": 0}))
        spatial["facing"] = facing
        if "tile_occupancy" in components:
            from .tile_targets import validate_placement
            validate_placement(self.ctx, components["tile_occupancy"], spatial["position"])
        if active and 'connectivity' in components.get('deployable',{}):
            from .deploy_connectivity import inspect
            inspect(self.ctx,definition,spatial['position'],components['deployable'],phase='create')
        if route is not None:
            spatial["route"] = thaw(route)
        if "motion_mode" in spatial:
            if type(spatial["motion_mode"]) is not int or spatial["motion_mode"] not in (0,1):raise ValueError("explicit spatial motion mode WALK0/FLY1 required")
            if spatial.get("route"):spatial["route"]["motionMode"]=spatial["motion_mode"]
        if parameters.get("timing_origins") is not None:
            origins = parameters["timing_origins"]
            if not isinstance(origins, Mapping) or any(type(value) is not int or value < 0 for value in origins.values()):
                raise ValueError("timing origins must contain nonnegative logical ticks")
            spatial["timing_origins"] = thaw(origins)
        components["runtime"] = {"alive": True, "state": "alive", "deployed": deployed,
                                 "initializing": True,
                                 "casts": {}, "cooldowns": {}, "next_attack": 0, "blocked_by": None,
                                 "rule_bindings": thaw(rule_overrides or {})}
        buff_config = components.get("buffs", components.pop("buff_container", {}))
        components["buffs"] = {**buff_config, "instances": [], "next_instance_id": 1}
        ref = self.ctx.session.commit([Intent("create", data={"definition_id": definition_id,
              "components": components, "tags": list(definition.get("tags", ()) if tags is None else tags), "alias": alias})])[0]
        if registration_key is not None:
            registry = self.ctx.state().get('predefined_registry', {})
            registry[registration_key] = ref
            self.ctx.state_update(predefined_registry=registry)
        if not active:
            self.ctx.set(ref, ('runtime', 'active'), False)
            self.ctx.set(ref, ('runtime', 'state'), 'dormant')
            self.ctx.set(ref, ('runtime', 'deployed'), False)
            self.ctx.set(ref, ('runtime', 'initializing'), False)
            self.ctx.set(ref, ('runtime', 'activation_plan'), {'deployed': deployed, 'lifetime_seconds': lifetime_seconds})
            self.ctx.emit('entity.registered', {'source': ref, 'target': ref, 'definition': definition_id, 'registration_key': registration_key, 'active': False})
            return ref
        return self._initialize_created(ref, components, resources, buff_config, lifetime_seconds, deployed)

    def _initialize_created(self, ref, components, resources, buff_config, lifetime_seconds, deployed):
        definition_id = self.ctx.entity(ref)['definition_id']
        from .ability_arbitration import initialize as initialize_arbitration
        initialize_arbitration(self.ctx,ref,components)
        from .ability_timing import initialize
        initialize(self.ctx,ref,components)
        for overlay in components.get("terrain_overlays", ()):
            self.ctx.terrain.apply(ref, overlay)
        if lifetime_seconds is not None:
            if type(lifetime_seconds) not in (int, float) or lifetime_seconds < 0:
                raise ValueError("entity lifetime must be nonnegative")
            at = self.ctx.session.time+self.ctx.quantize(lifetime_seconds)
            task = self.ctx.session.schedule("domain.entity.expire", {"target": ref}, at, phase=self.ctx.effect_phase)
            self.ctx.set(ref, ("runtime", "lifetime"), {"expires_at": at, "task": task})
        for key in resources:
            self.ctx.resources.adjust(ref, key, value=components["resources"][key]["current"])
        self.ctx.resources.initialize_capacities(ref)
        for roster_id in self.ctx.program.scenario.get("roster", []):
            for effect in self.ctx.program.definitions[roster_id].get("components", {}).get("deck", {}).get("on_create", []):
                cause = self.ctx.emit("deck.effect", {"source": ref, "target": ref, "definition": roster_id})
                self.ctx.effects.execute(ref, [ref], thaw(effect), cause=cause)
        for identifier in buff_config.get("initial", ()):
            self.ctx.buffs.apply(ref, ref, identifier)
        behavior = components.get("behavior", {})
        machine = self.ctx.program.definitions.get(behavior.get("machine"), {})
        if machine.get("states"):
            initial = machine.get("initial", machine.get("initial_state"))
            behavior["state"] = initial
            self.ctx.set(ref, ("behavior",), behavior)
            for effect in machine["states"][initial].get("on_enter", ()):
                self.ctx.effects.execute(ref, [ref], effect)
        # A phase-0 wave/deploy follows the periodic membership pass. Newly
        # created actors must join existing live auras before their first tick.
        self.ctx.buffs.reconcile()
        self.ctx.set(ref, ("runtime", "initializing"), False)
        self.ctx.emit("entity.created", {"source": ref, "target": ref, "definition": definition_id})
        if deployed:
            self.ctx.emit("entity.deployed", {"source": ref, "target": ref})
        if self.ctx.tile_contacts is not None:self.ctx.tile_contacts.inspect(ref,"born")
        return ref

    def activate_predefined(self, key):
        if key in self.ctx.state().get('predefined_reactivation',{}):
            from .predefined_reactivation import activate
            return activate(self,key)
        return self._activate_predefined_once(key)

    def _activate_predefined_once(self, key):
        with self.ctx.session.atomic():
            if not isinstance(key, str) or not key:
                raise ValueError('activation requires nonempty registration key')
            registry = self.ctx.state().get('predefined_registry', {})
            if key not in registry:
                raise ValueError('unknown predefined registration key')
            ref = registry[key]
            if not self.ctx.alive(ref) or self.ctx.get(ref, ('runtime', 'active'), True):
                raise ValueError('predefined actor is not a living dormant instance')
            if self.ctx.get(ref, ('runtime', 'state')) != 'dormant':
                raise ValueError('predefined actor has incompatible activation state')
            deployable=self.ctx.get(ref,('deployable',),{})
            if 'connectivity' in deployable:
                from .deploy_connectivity import inspect
                inspect(self.ctx,self.ctx.definition(ref),self.ctx.get(ref,('spatial','position')),deployable,entity=self.ctx.entity(ref),phase='activate')
            if self.ctx.get(ref,("tile_occupancy",)) is not None:
                from .tile_targets import validate_placement
                validate_placement(self.ctx,self.ctx.get(ref,("tile_occupancy",)),self.ctx.get(ref,("spatial","position")),exclude=ref)
            plan = self.ctx.get(ref, ('runtime', 'activation_plan'))
            self.ctx.set(ref, ('runtime', 'active'), True)
            self.ctx.set(ref, ('runtime', 'state'), 'alive')
            self.ctx.set(ref, ('runtime', 'initializing'), True)
            self.ctx.set(ref, ('runtime', 'deployed'), plan['deployed'])
            self.ctx.set(ref, ('runtime', 'activation_plan'), None)
            components = self.ctx.get(ref, ())
            resources = {name: data['spec'] for name, data in components.get('resources', {}).items()}
            buff_config = components.get('buffs', {})
            self._initialize_created(ref, components, resources, buff_config, plan['lifetime_seconds'], plan['deployed'])
            if 'connectivity' in deployable and self.ctx.active(ref):
                inspect(self.ctx,self.ctx.definition(ref),self.ctx.get(ref,('spatial','position')),self.ctx.get(ref,('deployable',)),entity=self.ctx.entity(ref),phase='activated')
            self.ctx.emit('entity.activated', {'source': ref, 'target': ref, 'registration_key': key})
            self.ctx.spatial.blocking()
            return ref

    def prune_expired(self, session):
        for entity in session.world.entities():
            lifetime = entity["components"].get("runtime", {}).get("lifetime")
            if lifetime and session.time >= lifetime["expires_at"] and self.ctx.alive(entity["id"]):
                self.retire(entity["id"], "expired")

    def expire(self, session, payload):
        if self.ctx.alive(payload["target"]):
            self.retire(payload["target"], "expired")

    def check(self, ref, event):
        if not self.ctx.get(ref, ('runtime', 'active'), True) and self.ctx.get(ref, ('runtime', 'state')) == 'dormant':
            return
        rebirth=getattr(self.ctx,"rebirth",None)
        if rebirth is not None and rebirth.consume(ref,event):return
        lifecycle = self.ctx.get(ref, ("lifecycle",), {})
        if not lifecycle.get("policy"):
            return
        policy = self.ctx.program.definitions[lifecycle["policy"]]
        parameters = {**thaw(policy.get("parameters", {})), **lifecycle.get("parameters", {})}
        plan = self.ctx.calc("lifecycle.death", {"resources": self.ctx.get(ref, ("resources",), {}),
               "damage_event": event, "states": self.ctx.get(ref, ("runtime",), {})}, target=ref,
               component=lifecycle.get("rules", {}), extra={"lifecycle_parameters": parameters})
        if plan["action"] == "death" and self.ctx.alive(ref):
            if event.get("source_policy") == "none":
                self.retire(ref, "dead", damage_attribution=event)
            else:
                self.retire(ref, "dead")
        elif plan["action"] == "revive":
            self.ctx.set(ref, ("runtime", "lifecycle_generation"), self.ctx.get(ref, ("runtime", "lifecycle_generation"), 0)+1)
            if 'active' in self.ctx.get(ref, ('runtime',)):
                self.ctx.set(ref, ('runtime', 'active'), True)
            self.ctx.set(ref, ("runtime", "alive"), True)
            self.ctx.set(ref, ("runtime", "state"), plan.get("state", "alive"))
            resource = plan["resource"]
            self.ctx.set(ref, ("resources", resource, "current"), plan["value"])
            self.ctx.emit("entity.revived", {"source": ref, "target": ref})

    def retire(self, ref, reason, *, damage_attribution=None):
        if self.ctx.terrain is None and not self.ctx.get(ref,("lifecycle","death_projectiles")) and getattr(self.ctx, "attachments", None) is None:
            return self._retire(ref, reason, damage_attribution=damage_attribution)
        with self.ctx.session.atomic():
            return self._retire(ref, reason, damage_attribution=damage_attribution)

    def _retire(self, ref, reason, *, damage_attribution=None):
        ref = self.ctx.session.world.resolve(ref)
        if not self.ctx.alive(ref):
            return
        if reason=='dead' and self.ctx.get(ref,('lifecycle','death_projectiles')):
            from .death_projectiles import emit
            if self.ctx.get(ref,('runtime','death_emission_in_progress'),False):return
            self.ctx.set(ref,('runtime','death_emission_in_progress'),True)
            try:emit(self.ctx,ref)
            finally:self.ctx.set(ref,('runtime','death_emission_in_progress'),False)
            if not self.ctx.alive(ref):return
        rebirth=getattr(self.ctx,"rebirth",None)
        if rebirth is not None:rebirth.cancel(ref,reason)
        if reason == 'dead':
            generation=self.ctx.get(ref,('runtime','death_generation'),0)+1
            self.ctx.set(ref,('runtime','death_generation'),generation)
        self.ctx.set(ref, ("runtime", "alive"), False)
        if 'active' in self.ctx.get(ref, ('runtime',)):
            self.ctx.set(ref, ('runtime', 'active'), False)
        self.ctx.set(ref, ("runtime", "state"), reason)
        if self.ctx.terrain is not None:
            self.ctx.terrain.remove(ref)
        self.ctx.abilities.interrupt(ref, reason)
        if getattr(self.ctx, "attachments", None) is not None: self.ctx.attachments.target_invalid(ref)
        lifetime = self.ctx.get(ref, ("runtime", "lifetime"))
        if lifetime and lifetime["task"] in {t["id"] for t in self.ctx.session.scheduler.pending}:
            self.ctx.session.cancel(lifetime["task"])
        for entity in self.ctx.session.world.entities():
            ownership = entity["components"].get("ownership", {})
            if ownership.get("owner") == ref and ownership.get("on_owner_retire", "retain") == "remove" and self.ctx.alive(entity["id"]):
                self.retire(entity["id"], "owner_retired")
        self.ctx.set(ref, ("runtime", "blocked_by"), None)
        self.ctx.buffs.reconcile()
        event = "entity.died" if reason == "dead" else "entity."+reason
        self.ctx.emit(event, {"source": ref, "target": ref} if damage_attribution is None else {**damage_attribution, "source": None, "target": ref}, damage_attribution.get("cause") if damage_attribution is not None else None)
        state = self.ctx.state()
        if reason == "dead" and "enemy" in self.ctx.entity(ref)["tags"]:
            state["kills"] += 1
        self.ctx.state_update(**state)
        deployable = self.ctx.get(ref, ("deployable",))
        from .deployment import cooldown_start
        if deployable and cooldown_start(deployable)=='retire':
            cooldown = deployable["cooldown_seconds"] if "cooldown_seconds" in deployable else self.ctx.role_value(ref, "redeploy_time")
            seconds = self.ctx.calc("deploy.cooldown", {"attributes": self.ctx.attributes.values(ref), "reason": {"type": reason},
                       "cooldown_parameters": {"seconds": cooldown}}, source=ref,
                       component=deployable.get("rules", {}))
            history = self.ctx.state()["deployments"]
            key = deployable.get("parameters", {}).get("history_key", self.ctx.entity(ref)["definition_id"])
            entry = history.setdefault(key, {"count": 0})
            entry["ready_at"] = self.ctx.session.time+self.ctx.quantize(seconds)
            self.ctx.state_update(deployments=history)
        timeline = getattr(self.ctx, "timeline", None)
        if timeline is not None:
            timeline.entity_retired(ref, reason)

    def claim_combat_kill(self, ref, payload, cause=None, *, generation=None):
        """Claim one real death transition before dispatching its reaction event."""
        with self.ctx.session.atomic():
            ref=self.ctx.session.world.resolve(ref)
            current=self.ctx.get(ref,('runtime','death_generation'),0)
            if generation is not None and (type(generation) is not int or generation<=0):
                raise ValueError('combat death generation must be positive integer')
            if self.ctx.alive(ref) or self.ctx.get(ref,('runtime','state'))!='dead' or current<=0 or (generation is not None and generation!=current):return None
            prior=self.ctx.get(ref,('runtime','combat_death_claim'),{})
            if prior.get('generation')==current:return None
            if not isinstance(payload,Mapping):raise ValueError('combat kill attribution payload must be record')
            value=thaw(payload);source=value.get('source')
            if value.get('source_policy')=='none' and source is not None:raise ValueError('source-free combat kill cannot claim actor source')
            value['source']=self.ctx.session.world.resolve(source) if source is not None else None
            value['target']=ref;value['target_tags']=list(self.ctx.entity(ref)['tags'])
            self.ctx.set(ref,('runtime','combat_death_claim'),{'generation':current,'at':self.ctx.session.time,'payload':value,'cause':cause})
            return self.ctx.emit('combat.kill',value,cause)

    def exit(self, ref):
        if self.ctx.get(ref, ("lifecycle", "exit_rule")):
            from .exit_accounting import execute
            return execute(self, ref)
        params = self.ctx.get(ref, ("lifecycle",), {})
        loss = self.ctx.calc("lifecycle.leak_loss", {"entity": self.ctx.entity(ref), "exit": {},
                "leak_parameters": {"loss": params.get("leak_loss", 1)}})
        resource = self.ctx.program.scenario.get("objectives", {}).get("life_resource")
        if resource:
            self.ctx.resources.adjust("system/battle", resource, -loss)
        state = self.ctx.state()
        state["leaks"] += 1
        self.ctx.state_update(**state)
        self.retire(ref, "exited")

    def tick(self, session):
        if getattr(self.ctx, "controls", None) is None and getattr(self.ctx,"rebirth",None) is None and getattr(self.ctx, "attachments", None) is None:
            return self._tick(session)
        with session.atomic():
            return self._tick(session)

    def _tick(self, session):
        state = self.ctx.state()
        if state.get("finished") or not self.ctx.program.scenario.get("objectives"):
            return
        waves = {"pending": state["pending_waves"]}
        timeline = getattr(self.ctx, "timeline", None)
        if timeline is not None:
            waves["timeline_complete"] = state.get("timeline", {}).get("phase") == "complete"
        result = self.ctx.calc("lifecycle.result", {"waves": waves,
             "entities": [e["id"] for e in session.world.entities()],
             "resources": self.ctx.get("system/battle", ("resources",), {}), "objectives": thaw(self.ctx.program.scenario["objectives"])},
             extra={"objectives": thaw(self.ctx.program.scenario["objectives"]),
                    "entity_states": [thaw(e) for e in session.world.entities()]})
        if result["finished"] and result.get("result") == "victory" and getattr(self.ctx, "attachments", None) is not None and self.ctx.attachments.completion_pending():
            return
        if result['finished'] and result['result']=='victory' and self.ctx.projectiles is not None:
            if self.ctx.projectiles.completion_pending():return
        if result["finished"] and result.get("result")=="victory" and getattr(self.ctx,"branches",None) is not None:
            if any(row["phase"]=="running" for row in self.ctx.branches.state().values()):return
        if result["finished"]:
            self.ctx.state_update(finished=True, result=result["result"], finished_at=session.time)
            if getattr(self.ctx, "attachments", None) is not None: self.ctx.attachments.terminate_all()
            if getattr(self.ctx,"branches",None) is not None:self.ctx.branches.cancel_terminal()
            if getattr(self.ctx,"rebirth",None) is not None:self.ctx.rebirth.cancel_all("battle_terminal")
            if getattr(self.ctx, "controls", None) is not None:
                self.ctx.controls.cancel_all_terminal()
                timeline = self.ctx.timeline._state()
                self.ctx.timeline._stop_if_finished(timeline)
            elif getattr(self.ctx, "timeline", None) is not None and self.ctx.timeline._state().get('tracking_requests'):
                # This opt-in tracking ledger must stop on the actual terminal result,
                # including scenes without any acknowledgement/control subsystem.
                timeline = self.ctx.timeline._state()
                self.ctx.timeline._stop_if_finished(timeline)
            if self.ctx.periodic_fields is not None:self.ctx.periodic_fields.tick(session)
            self.ctx.emit("scenario.finished", result)

    def spawn_wave(self, session, wave, count_pending=True):
        with session.atomic():
            return self._spawn_wave(session, wave, count_pending)

    def _spawn_wave(self, session, wave, count_pending=True):
        if self.ctx.state().get("finished"):
            return
        position = wave.get("position")
        placement = wave.get("placement")
        if placement:
            samples = [{"axis": axis, "value": session.random.sample(placement["stream"])}
                       for axis in placement["sample_axes"]
                       if placement.get("sample_zero_range", False) or placement["random_range"][axis] > 0]
            position = self.ctx.calc("spawn.position", {"anchor": position, "offset": placement["offset"],
                "random_range": placement["random_range"], "samples": samples}, rule_id=placement["rule"])
            self.ctx.spatial.grid._cell(position)
            self.ctx.emit("spawn.position_resolved", {"definition": wave["definition"], "anchor": wave["position"],
                "position": position, "samples": samples, "stream": placement["stream"], "rule": placement["rule"]})
        ref = self.create(wave["definition"], position, wave.get("facing", "left"),
                    wave.get("route"), wave.get("instanceAlias"), wave.get("parameters"),
                    component_overrides=wave.get("components"), rule_overrides=wave.get("rules"), tags=wave.get("tags"))
        if count_pending:
            self.ctx.state_update(pending_waves=self.ctx.state()["pending_waves"]-1)
        return ref
