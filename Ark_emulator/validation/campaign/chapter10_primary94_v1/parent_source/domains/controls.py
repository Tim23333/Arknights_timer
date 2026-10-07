"""Content-driven asynchronous logical controls, independent of actor counts."""
from ark_sim.contracts import thaw


class ControlSystem:
    def __init__(self, context):
        self.ctx = context
        self.handlers = {"domain.control.signal": self.signal}
        self._settling_terminal = False
        self._cancelling = set()

    def _state(self):
        return self.ctx.state().get("controls", {"next_instance": 1, "instances": {}, "aliases": {}})

    def _save(self, state):
        self.ctx.state_update(controls=state)

    def instance(self, reference):
        if not isinstance(reference, str): raise ValueError("control reference must be an instance ID or alias")
        state = self._state(); key = state["aliases"].get(reference, reference)
        if key not in state["instances"]: raise ValueError("unknown control instance")
        return state["instances"][key]

    def _put(self, instance):
        state = self._state(); state["instances"][instance["id"]] = instance; self._save(state)

    def alias_exists(self, alias):
        state = self._state()
        return alias in state["aliases"] or alias in state["instances"]

    def prepare(self, definition, alias, origins):
        with self.ctx.session.atomic():
            if self.ctx.state().get("finished"): raise ValueError("cannot prepare a control after terminal result")
            if self.ctx.program.definitions[definition].get("kind") != "control": raise ValueError("control definition kind required")
            state = self._state(); uid = "control/"+str(state["next_instance"])
            if alias is not None:
                if not isinstance(alias, str) or not alias or alias.startswith("control/"): raise ValueError("invalid/reserved control alias")
                if alias in state["aliases"] or alias in state["instances"]: raise ValueError("duplicate control alias")
                try: self.ctx.session.world.resolve(alias)
                except KeyError: pass
                else: raise ValueError("control alias collides with an actor alias")
                state["aliases"][alias] = uid
            state["next_instance"] += 1
            instance = {"id": uid, "definition": definition, "alias": alias, "status": "pending", "phase": "pending",
                "cursor": 0, "generation": 0, "tasks": {}, "locks": {}, "origins": dict(origins),
                "waiting_step": None, "waiting_key": None, "prepared_at": self.ctx.session.time}
            state["instances"][uid] = instance; self._save(state)
            self.ctx.emit("control.pending", {"control": uid, "definition": definition, "origins": dict(origins)})
            return uid

    def lock_key(self, reference, key, enabled):
        instance = self.instance(reference)
        if instance["status"] not in {"running", "pending"}: raise ValueError("inactive control cannot change an input lock")
        actual = instance["id"]+":"+key
        if enabled: instance["locks"][key] = actual
        else: instance["locks"].pop(key, None)
        self._put(instance)
        return actual

    def track_start_task(self, reference, task):
        instance = self.instance(reference); instance["tasks"]["start"] = task; self._put(instance)

    def _effects(self, reference, effects, *, cancellation=False):
        terminal_at_entry = self.ctx.state().get("finished", False)
        cast = {"control_instance": reference, "control_finalizer": cancellation and terminal_at_entry}
        for effect in effects:
            self.ctx.effects.execute("system/battle", ["system/battle"], thaw(effect), cast=cast)
            if not self.effect_allowed(cast): return False
        return True

    def effect_allowed(self, cast):
        reference = cast["control_instance"]
        instance = self.instance(reference)
        return instance["status"] in {"pending", "running"} and (not self.ctx.state().get("finished") or
            (cast.get("control_finalizer") and reference in self._cancelling))

    def settle_effect(self, cast, operation):
        if operation != "emit" and not self._settling_terminal and not self.ctx.state().get("finished"):
            self._settling_terminal = True
            try:
                self.ctx.lifecycle.tick(self.ctx.session)
            finally:
                self._settling_terminal = False
        return self.effect_allowed(cast)

    def begin(self, reference):
        with self.ctx.session.atomic():
            instance = self.instance(reference)
            if instance["status"] != "pending": raise ValueError("control start requires pending instance")
            if self.ctx.state().get("finished"): raise ValueError("cannot start a control after terminal result")
            instance.update(status="running", phase="effects", started_at=self.ctx.session.time); self._put(instance)
            instance["tasks"].pop("start", None); self._put(instance)
            self.ctx.emit("control.started", {"control": instance["id"], "definition": instance["definition"]})
            if not self._effects(instance["id"], self.ctx.program.definitions[instance["definition"]].get("on_start", ())): return
            self._advance(instance["id"])

    def _advance(self, reference):
        while True:
            instance = self.instance(reference); definition = self.ctx.program.definitions[instance["definition"]]
            if instance["status"] != "running": return
            if instance["cursor"] >= len(definition["steps"]):
                self._complete(reference); return
            step = definition["steps"][instance["cursor"]]
            if step["kind"] == "effects":
                instance["phase"] = "effects"; self._put(instance)
                if not self._effects(reference, step["effects"]): return
                instance = self.instance(reference); instance["cursor"] += 1; self._put(instance)
            elif step["kind"] == "delay":
                ticks = self.ctx.quantize(step["seconds"])
                if not ticks:
                    instance["cursor"] += 1; self._put(instance); continue
                instance.update(phase="delay", generation=instance["generation"]+1,
                    wake_at=self.ctx.session.time+ticks)
                task = self.ctx.session.schedule("domain.control.signal", {"control": reference, "generation": instance["generation"],
                    "cursor": instance["cursor"]}, instance["wake_at"], phase=self.ctx.effect_phase)
                instance["tasks"]["delay"] = task; self._put(instance)
                self.ctx.emit("control.waiting_delay", {"control": reference, "step": instance["cursor"], "wake_at": instance["wake_at"]})
                return
            else:
                if definition["ack_policy"] == "immediate":
                    self.ctx.emit("control.acknowledged", {"control": reference, "step": instance["cursor"], "key": step["key"], "automatic": True})
                    instance["cursor"] += 1; self._put(instance); continue
                instance.update(phase="awaiting_ack", waiting_step=instance["cursor"], waiting_key=step["key"])
                self._put(instance)
                self.ctx.emit("control.awaiting_ack", {"control": reference, "alias": instance["alias"],
                    "step": instance["cursor"], "key": step["key"]})
                return

    def signal(self, session, payload):
        with session.atomic():
            if self.ctx.state().get("finished"):
                self.cancel_all_terminal(); return
            instance = self.instance(payload["control"])
            if instance["status"] != "running" or instance["phase"] != "delay" or instance["generation"] != payload["generation"] or instance["cursor"] != payload["cursor"]:
                return
            instance["tasks"].pop("delay", None); instance.pop("wake_at", None)
            instance["cursor"] += 1; instance["phase"] = "effects"; self._put(instance); self._advance(instance["id"])

    def acknowledge(self, reference, step):
        with self.ctx.session.atomic():
            instance = self.instance(reference)
            if type(step) is not int or instance["status"] != "running" or instance["phase"] != "awaiting_ack" or step != instance["waiting_step"]:
                raise ValueError("control acknowledgement does not match current waiting step/phase")
            if self.ctx.state().get("finished"): raise ValueError("cannot acknowledge terminal control")
            self.ctx.emit("control.acknowledged", {"control": instance["id"], "step": step, "key": instance["waiting_key"], "automatic": False})
            instance.update(cursor=instance["cursor"]+1, phase="effects", waiting_step=None, waiting_key=None)
            self._put(instance); self._advance(instance["id"])
            return instance["id"]

    def _cleanup(self, reference):
        instance = self.instance(reference)
        pending = {task["id"] for task in self.ctx.session.scheduler.pending}
        for task in instance["tasks"].values():
            if task in pending: self.ctx.session.cancel(task)
        keys = set(instance["locks"].values())
        if keys:
            locks = [key for key in self.ctx.state().get("input_locks", []) if key not in keys]
            self.ctx.state_update(input_locks=locks)
            for key in sorted(keys): self.ctx.emit("input.lock_changed", {"source": self.ctx.session.world.resolve("system/battle"),
                "target": self.ctx.session.world.resolve("system/battle"), "key": key, "enabled": False, "control": reference})
        instance.update(tasks={}, locks={}, waiting_step=None, waiting_key=None, generation=instance["generation"]+1)
        instance.pop("wake_at", None); self._put(instance)

    def _complete(self, reference):
        instance = self.instance(reference)
        if not self._effects(reference, self.ctx.program.definitions[instance["definition"]].get("on_complete", ())): return
        self._cleanup(reference); instance = self.instance(reference)
        instance.update(status="completed", phase="completed", completed_at=self.ctx.session.time); self._put(instance)
        self.ctx.emit("control.completed", {"control": reference, "definition": instance["definition"]})
        self.ctx.timeline.control_released(reference, "completed")

    def cancel(self, reference, reason, *, policy):
        with self.ctx.session.atomic():
            if policy not in {"continue", "terminal"}: raise ValueError("control cancellation requires explicit continuation policy")
            if policy == "terminal" and not self.ctx.state().get("finished"): raise ValueError("terminal cancellation requires terminal result")
            instance = self.instance(reference)
            if instance["status"] in {"completed", "cancelled"}: return False
            if instance["id"] in self._cancelling: return False
            self._cancelling.add(instance["id"])
            try:
                self._effects(instance["id"], self.ctx.program.definitions[instance["definition"]].get("on_cancel", ()), cancellation=True)
                self._cleanup(instance["id"]); instance = self.instance(instance["id"])
                policy = "terminal" if self.ctx.state().get("finished") else policy
                instance.update(status="cancelled", phase="cancelled", cancelled_at=self.ctx.session.time, cancel_reason=reason, cancel_policy=policy)
                self._put(instance); self.ctx.emit("control.cancelled", {"control": instance["id"], "reason": reason, "policy": policy})
                self.ctx.timeline.control_released(instance["id"], "cancelled", policy=policy)
                return True
            finally:
                self._cancelling.discard(instance["id"])

    def cancel_all_terminal(self):
        with self.ctx.session.atomic():
            for instance in list(self._state()["instances"].values()):
                if instance["status"] in {"pending", "running"}: self.cancel(instance["id"], "terminal_result", policy="terminal")

    def tick(self, session):
        if self.ctx.state().get("finished"): self.cancel_all_terminal()
