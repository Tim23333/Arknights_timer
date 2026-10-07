"""Public V2 runtime: immutable program plus independently owned session."""
import copy
import hashlib
from pathlib import Path
from ark_sim.contracts import Intent, digest, thaw
from ark_sim.kernel import Session
from ark_sim.domains.context import RuntimeContext
from ark_sim.domains.attributes import AttributeSystem
from ark_sim.domains.resources import ResourceSystem
from ark_sim.domains.effects import EffectSystem
from ark_sim.domains.buffs import BuffSystem
from ark_sim.domains.abilities import AbilitySystem
from ark_sim.domains.behavior import BehaviorSystem
from ark_sim.domains.movement import SpatialSystem, MovementSystem
from ark_sim.domains.lifecycle import LifecycleSystem
from ark_sim.domains.timeline import TimelineSystem
from ark_sim.domains.controls import ControlSystem
from ark_sim.domains.terrain import TerrainSystem
from ark_sim.domains.projectiles import ProjectileSystem


def implementation_digest():
    root = Path(__file__).resolve().parents[1]
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(root.rglob("*.py"))})


class Simulation:
    def __init__(self, program, seed=0, providers=None, random_factory=None, random_registry=None, random_algorithm=None):
        self.program, self.seed = program, seed
        self.session = Session(quantum=program.ruleset["quantum"], seed=seed,
                               reaction_budget=program.ruleset.get("reaction_budget", 10000),
                               random_factory=random_factory, random_registry=random_registry, random_algorithm=random_algorithm)
        self.ctx = RuntimeContext(program, self.session, providers)
        self.ctx.attributes = AttributeSystem(self.ctx)
        self.ctx.resources = ResourceSystem(self.ctx)
        self.ctx.effects = EffectSystem(self.ctx)
        self.ctx.buffs = BuffSystem(self.ctx)
        self.ctx.abilities = AbilitySystem(self.ctx)
        self.ctx.behavior = BehaviorSystem(self.ctx)
        self.ctx.spatial = SpatialSystem(self.ctx)
        def uses_terrain(value):
            if isinstance(value, dict) or hasattr(value, "items"):
                return "terrain_overlays" in value or value.get("op") in {"apply_terrain_overlay", "remove_terrain_overlay"} or any(uses_terrain(v) for v in value.values())
            return isinstance(value, (list, tuple)) and any(uses_terrain(v) for v in value)
        if uses_terrain(program.definitions):
            self.ctx.terrain = TerrainSystem(self.ctx)
            self.ctx.spatial.grid.tile_reader = self.ctx.terrain.tile
        self.ctx.movement = MovementSystem(self.ctx)
        self.ctx.lifecycle = LifecycleSystem(self.ctx)
        def uses_rebirth(value):
            if isinstance(value,dict) or hasattr(value,"items"):
                return "rebirth" in value.get("components",{}) or value.get("op")=="instant_kill" or any(uses_rebirth(v) for k,v in value.items() if k not in {"metadata","parameters","payload"})
            return isinstance(value,(list,tuple)) and any(uses_rebirth(v) for v in value)
        if uses_rebirth(program.definitions) or uses_rebirth(program.scenario):
            from ark_sim.domains.rebirth import RebirthSystem
            self.ctx.rebirth=RebirthSystem(self.ctx)
        if any(p.get("type")=="contact_lifecycle" for p in self.ctx.spatial.grid.tile_mechanics.values()):
            from ark_sim.domains.tile_contacts import TileContactSystem
            self.ctx.tile_contacts=TileContactSystem(self.ctx)
        if any(d.get("kind") == "projectile" for d in program.definitions.values()):
            self.ctx.projectiles = ProjectileSystem(self.ctx)
        if program.scenario.get("timeline") is not None:
            self.ctx.timeline = TimelineSystem(self.ctx)
            if any(a["kind"] == "control" for w in program.scenario["timeline"]["waves"] for f in w["fragments"] for a in f["actions"]):
                self.ctx.controls = ControlSystem(self.ctx)
        if any(p.get('type')=='periodic_effect_field' for p in self.ctx.spatial.grid.tile_mechanics.values()):
            from ark_sim.domains.periodic_fields import PeriodicFieldSystem
            self.ctx.periodic_fields=PeriodicFieldSystem(self.ctx)
        self._commands = []
        self._register()
        self.runtime_fingerprint = digest({"implementation": implementation_digest(), "rules": self.ctx.rules.fingerprint,
                                          "random": self.session.random.fingerprint})
        resources = thaw(program.scenario.get("resources", {}))
        self.session.world.create("system/battle", {
            "attributes": {"base": {}, "modifiers": []},
            "resources": {key: {"current": spec.get("initial", 0), "spec": spec} for key, spec in resources.items()},
            "state": {"finished": False, "result": "running", "pending_waves": len(program.scenario.get("waves", ())),
                      "kills": 0, "leaks": 0, "damage_dealt": 0, "deployments": {}, "command_results": {}},
            "runtime": {"alive": True, "casts": {}}, "buffs": {"instances": []}}, tags=("system",), alias="system/battle")
        for item in program.scenario.get("initialEntities", ()):
            self.ctx.lifecycle.create(item["definition"], item.get("position"), item.get("facing", "right"),
                                      item.get("route"), item.get("instanceAlias"), parameters=item.get("parameters"), deployed=item.get("deployed", False),
                                      component_overrides=item.get("components"), rule_overrides=item.get("rules"), tags=item.get("tags"),
                                      active=item.get('active', True), registration_key=item.get('registration_key'))
        from ark_sim.domains.tile_fields import initialize as initialize_tile_fields
        initialize_tile_fields(self.ctx)
        if self.ctx.periodic_fields is not None:self.ctx.periodic_fields.initialize()
        for entry in program.scenario.get("scheduledEffects", ()):
            at = entry.get("at")
            if at is None:
                at = self.ctx.quantize(entry.get("at_seconds", 0))
            self.session.schedule("domain.effect", {"source": None if entry["effect"].get("op") == "no_source_damage" else "system/battle", "targets": [],
                "effect": thaw(entry["effect"])}, at, phase=0)
        for wave in program.scenario.get("waves", ()):
            at = wave.get("at")
            if at is not None and "at_seconds" in wave:
                raise ValueError("a spawn wave must choose at or at_seconds")
            if at is None:
                at = self.ctx.quantize(wave.get("at_seconds", 0))
            self.session.schedule("domain.wave", thaw(wave), at, phase=0)
        if self.ctx.timeline is not None:
            self.ctx.timeline.start()
        for command in program.scenario.get("commands", ()):
            action = thaw(command)
            at = action.pop("at", None)
            seconds = action.pop("at_seconds", None)
            if at is not None and seconds is not None:
                raise ValueError("a scenario command must choose at or at_seconds")
            if at is None:
                at = self.ctx.quantize(0 if seconds is None else seconds)
            self._submit(action, at, record=False)

    def _register(self):
        handlers = {"domain.command": self._command, "domain.wave": self.ctx.lifecycle.spawn_wave,
                    "domain.effect": self.ctx.effects.handle, "event_reaction": self.ctx.react,
                    "domain.ability.effect": self.ctx.abilities.handle_effect,
                    "domain.ability.finish": self.ctx.abilities.finish,
                    "domain.buff.expire": self.ctx.buffs.expire, "domain.buff.periodic": self.ctx.buffs.periodic,
                    "domain.entity.expire": self.ctx.lifecycle.expire,
                    "domain.movement.forced_step": self.ctx.movement.forced_step}
        for name, handler in handlers.items():
            self.session.register_handler(name, handler)
        if self.ctx.periodic_fields is not None:
            self.session.register_handler('domain.field.pulse',self.ctx.periodic_fields.pulse)
            self.session.register_handler('domain.field.packet',self.ctx.periodic_fields.packet)
            self.session.add_system(self.ctx.periodic_fields.tick,phase=0)
        if self.ctx.timeline is not None:
            for name, handler in self.ctx.timeline.handlers.items():
                self.session.register_handler(name, handler)
        if self.ctx.projectiles is not None:
            for name,handler in self.ctx.projectiles.handlers.items(): self.session.register_handler(name,handler)
            self.session.add_system(self.ctx.projectiles.tick, phase=0)
        if self.ctx.controls is not None:
            for name, handler in self.ctx.controls.handlers.items(): self.session.register_handler(name, handler)
            self.session.add_system(self.ctx.controls.tick, phase=0)
        if self.ctx.terrain is not None:
            self.session.add_system(self.ctx.terrain.tick, phase=0)
        self.session.add_system(self.ctx.lifecycle.prune_expired, phase=0)
        if getattr(self.ctx,"rebirth",None) is not None:
            for name,handler in self.ctx.rebirth.handlers.items():self.session.register_handler(name,handler)
            self.session.add_system(self.ctx.rebirth.tick,phase=0)
        if self.ctx.buffs.has_buffs:
            # Registered before initial waves and input tasks: expiry at t is
            # removed before phase-0 commands can capture an at_cast snapshot.
            self.session.add_system(self.ctx.buffs.tick, phase=0)
            if self.ctx.buffs.applicability.enabled:
                self.session.add_boundary_system(self.ctx.buffs.tick)
        if self.ctx.tile_contacts is not None:
            self.session.add_system(self.ctx.tile_contacts.tick, phase=0)
        systems = {"commands": lambda s: None, "resources": self.ctx.resources.tick,
                   "behavior": self.ctx.behavior.tick, "abilities": self.ctx.abilities.tick,
                   "movement": self._movement_tick, "lifecycle": self.ctx.lifecycle.tick}
        for index, name in enumerate(self.program.ruleset.get("system_order", ())):
            if name not in systems:
                raise ValueError(f"unsupported system {name}")
            if name != "commands":
                self.session.add_system(systems[name], phase=index+1)

    def _movement_tick(self, session):
        self.ctx.movement.tick(session)
        self.ctx.buffs.reconcile()

    def _submit(self, action, at, record=True):
        if not isinstance(action, dict):
            raise ValueError("command must be an object")
        action = copy.deepcopy(action)
        with self.session._lock:
            task_id = self.session.schedule("domain.command", {"action": action}, at, phase=0)
            if record:
                self._commands.append({"order": len(self._commands)+1, "submitted_at": self.session.time,
                                       "at": at, "action": action})
        return task_id

    def submit(self, action, at=None):
        return self._submit(action, self.session.time if at is None else at)

    def _command(self, session, payload):
        action = payload["action"]
        try:
            with session.atomic():
                result = self._execute_command(action)
            session.emit("command.accepted", {"action": action, "result": result})
        except (ValueError, KeyError) as exc:
            session.emit("command.rejected", {"action": action, "reason": str(exc)})

    def _execute_command(self, action):
        session = self.session
        if self.ctx.state()["finished"]:
            raise ValueError("scenario already finished")
        kind = action.get("action", action.get("type"))
        if kind == "control_ack":
            if (self.ctx.controls is None or set(action)-{"action", "type", "control", "step"}
                    or action.get("type", "control_ack") != "control_ack"):
                raise ValueError("control_ack requires only active control reference and waiting step")
            return self.ctx.controls.acknowledge(action.get("control"), action.get("step"))
        if self.ctx.state().get("input_locks"):
            raise ValueError("scenario input locked")
        if kind in ("activate_ability", "skill"):
            ref = session.world.resolve(action["source"])
            result = self.ctx.abilities.start(ref, action["ability"], event_payload=action.get("payload"))
        elif kind == "deploy":
            result = self._deploy(action)
        elif kind in ("withdraw", "retreat"):
            ref = session.world.resolve(action["source"])
            if not self.ctx.active(ref):
                raise ValueError("entity is not deployed")
            spec = self.ctx.get(ref, ("deployable",), {})
            refund_parameters = {"ratio": spec.get("refund_ratio", 0.5)}
            if "refund_cap_raw_ratio" in spec.get("parameters", {}):
                refund_parameters.update(raw_cost=spec.get("base_cost", spec.get("cost", self.ctx.role_value(ref, "deploy_cost"))),
                    raw_cap_ratio=spec["parameters"]["refund_cap_raw_ratio"])
            refund = self.ctx.calc("deploy.refund", {"paid_cost": spec.get("paid_cost", 0), "reason": {"type": "withdraw"},
                "refund_parameters": refund_parameters}, source=ref,
                component=spec.get("rules", {}))
            resource = self.program.ruleset.get("parameters", {}).get("deployment_resource")
            if resource:
                self.ctx.resources.adjust("system/battle", resource, refund)
            self.ctx.lifecycle.retire(ref, "withdrawn")
            result = ref
        else:
            raise ValueError(f"unsupported command {kind}")
        return result

    def _deploy(self, action):
        definition_id = action.get("entity", action.get("definition"))
        if "roster" in self.program.scenario and definition_id not in self.program.scenario["roster"]:
            raise ValueError("definition is not in the selected scenario roster")
        from ark_sim.domains.deployment import prepare, record
        position = action.get("position") or {"row": action.get("row"), "col": action.get("col")}
        plan = prepare(self.ctx, definition_id, position, action.get("facing", "right"))
        if plan["resource"]:
            actual_paid=self.ctx.resources.adjust("system/battle", plan["resource"], -plan["cost"])
            if actual_paid!=-plan["cost"]:raise ValueError("deployment cost payment must be exact")
        ref = self.ctx.lifecycle.create(definition_id, position, plan["facing"], alias=action.get("alias"), deployed=True)
        record(self.ctx, ref, plan)
        return ref

    def advance(self, ticks):
        self.session.advance(ticks)
        return self.snapshot()

    def snapshot(self):
        return {"time": self.session.time, "seconds": self.session.time*self.session.quantum,
                "scenario": self.program.scenario["id"], "program_fingerprint": self.program.fingerprint,
                "runtime_fingerprint": self.runtime_fingerprint,
                "entities": [thaw(e) for e in self.session.world.entities()], "state": self.ctx.state(),
                "events": thaw(self.session.events)}

    def checkpoint(self):
        return {"schema": "ark-sim/session-checkpoint/v2", "program_fingerprint": self.program.fingerprint,
                "runtime_fingerprint": self.runtime_fingerprint, "kernel": self.session.checkpoint(),
                "commands": copy.deepcopy(self._commands)}

    def export_replay(self):
        return {"schema": "ark-sim/replay/v2", "program_fingerprint": self.program.fingerprint,
                "runtime_fingerprint": self.runtime_fingerprint, "seed": self.seed,
                "random_algorithm": self.session.random.algorithm,
                "until": self.session.time, "commands": copy.deepcopy(self._commands)}

    def explain(self, event_id):
        return next((thaw(e) for e in self.session.events if e["id"] == event_id), None)


class Engine:
    @staticmethod
    def create(program, seed=None, **kwargs):
        seed = program.scenario.get("seed", 0) if seed is None else seed
        return Simulation(program, seed, **kwargs)

    @staticmethod
    def restore(program, checkpoint, **kwargs):
        if checkpoint.get("schema") != "ark-sim/session-checkpoint/v2" or checkpoint.get("program_fingerprint") != program.fingerprint:
            raise ValueError("checkpoint program identity mismatch")
        kwargs.setdefault("random_algorithm", checkpoint["kernel"]["random"]["algorithm"])
        simulation = Simulation(program, seed=checkpoint["kernel"]["random"]["seed"], **kwargs)
        if checkpoint["runtime_fingerprint"] != simulation.runtime_fingerprint:
            raise ValueError("checkpoint runtime identity mismatch")
        simulation.session.restore(checkpoint["kernel"])
        simulation._commands = copy.deepcopy(checkpoint.get("commands", []))
        return simulation
