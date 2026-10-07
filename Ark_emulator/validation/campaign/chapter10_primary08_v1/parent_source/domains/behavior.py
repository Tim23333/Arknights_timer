"""Declarative state transitions and replaceable behavior plans."""
from ark_sim.rules import evaluate_expression


class BehaviorSystem:
    def __init__(self, context):
        self.ctx = context

    def transition(self, ref, state, cause=None):
        if not self.ctx.get(ref, ('runtime', 'active'), True) and not (getattr(self.ctx,'rebirth',None) is not None and self.ctx.rebirth.effect_allowed(self.ctx.session.world.resolve(ref))):
            raise ValueError('dormant instance cannot enter behavior states before activation')
        component = self.ctx.get(ref, ("behavior",), {})
        definition = self.ctx.program.definitions.get(component.get("machine"), {})
        states = definition.get("states", {})
        if state not in states:
            raise ValueError(f"unknown state {state}")
        old = component.get("state", definition.get("initial", definition.get("initial_state")))
        # Explicit restart callers must stop if a callback retires/rebinds or
        # synchronously restarts this actor. Ordinary transitions retain their
        # historical behavior unless a restart generation has been installed.
        restart_generation = component.get('restart_generation')
        lifecycle = (self.ctx.get(ref, ('runtime','death_generation'),0),
                     self.ctx.get(ref, ('runtime','lifecycle_generation'),0))
        def restart_current():
            return (restart_generation is None or (self.ctx.active(ref) and self.ctx.alive(ref)
                and self.ctx.get(ref, ('behavior','machine'))==component.get('machine')
                and self.ctx.get(ref, ('behavior','restart_generation'))==restart_generation
                and lifecycle==(self.ctx.get(ref, ('runtime','death_generation'),0),
                    self.ctx.get(ref, ('runtime','lifecycle_generation'),0))))
        for effect in states.get(old, {}).get("on_exit", ()):
            self.ctx.effects.execute(ref, [ref], effect, cause=cause)
            if not restart_current():return False
        component["state"] = state
        component["entered_at"] = self.ctx.session.time
        self.ctx.set(ref, ("behavior",), component)
        self.ctx.emit("behavior.transition", {"source": ref, "target": ref, "from": old, "to": state}, cause)
        for effect in states[state].get("on_enter", ()):
            self.ctx.effects.execute(ref, [ref], effect, cause=cause)
            if not restart_current():return False
        return True

    def plan(self, ref):
        if not self.ctx.get(ref, ('runtime', 'active'), True):
            return {'move': False, 'attack': False}
        component = self.ctx.get(ref, ("behavior",), {})
        definition = self.ctx.program.definitions.get(component.get("machine"), {})
        if definition.get('decision'):
            from .behavior_decision import facts
            inputs=facts(self.ctx,ref,definition['decision'],component.get('state',definition.get('initial',definition.get('initial_state'))))
            decision=self.ctx.calc('behavior.decision',inputs,source=ref,owner=ref,rule_id=definition['decision']['rule'])
            if not isinstance(decision,dict) or set(decision)!={'move','attack'} or any(type(x) is not bool for x in decision.values()):
                raise ValueError('behavior decision requires exactly move/attack booleans')
            return decision
        provider = definition.get("provider") or definition.get("implementation", {}).get("provider")
        if provider:
            decision = self.ctx.provider(provider, {"source": self.ctx.entity(ref),
                "blocked_by": self.ctx.spatial.blocked_by(ref)}, definition.get("parameters", {}))
            if not isinstance(decision, dict) or any(type(decision.get(key)) is not bool for key in ("move", "attack")):
                raise ValueError("behavior provider must return boolean move and attack decisions")
            return decision
        return {"move": True, "attack": True}

    def refresh(self, ref):
        component=self.ctx.get(ref,('behavior',),{})
        definition=self.ctx.program.definitions.get(component.get('machine'),{})
        if definition.get('decision') and self.ctx.active(ref):
            decision=self.plan(ref)
            if decision!=self.ctx.get(ref,('runtime','behavior_decision')):
                self.ctx.set(ref,('runtime','behavior_decision'),decision)

    def tick(self, session):
        if self.ctx.state().get("finished"):
            return
        for entity in session.world.entities():
            ref = entity["id"]
            if not getattr(self.ctx, 'active', self.ctx.alive)(ref):
                continue
            component = self.ctx.get(ref, ("behavior",), {})
            definition = self.ctx.program.definitions.get(component.get("machine"), {})
            state = component.get("state", definition.get("initial", definition.get("initial_state")))
            transitions = sorted(enumerate(definition.get("transitions", ())), key=lambda pair: (pair[1].get("priority", 0), pair[0]))
            for _, transition in transitions:
                if transition["from"] not in (state, "*"):
                    continue
                inputs = {"source": self.ctx.entity(ref), "target": self.ctx.entity(ref),
                          "resources": self.ctx.get(ref, ("resources",), {}), "time": session.time,
                          "state": state}
                condition = transition.get("condition", "True")
                matched = evaluate_expression(condition, inputs, transition.get("parameters", {}))
                if transition.get("condition_rule"):
                    matched = self.ctx.calc("behavior.threshold", {"resources": inputs["resources"],
                         "time": {"current":session.time}, "state_parameters": transition.get("parameters", {})},
                         owner=ref, rule_id=transition["condition_rule"])
                if matched:
                    self.transition(ref, transition["to"])
                    for effect in transition.get("effects", ()):
                        self.ctx.effects.execute(ref, [ref], effect)
                    break
            if component.get("machine") and getattr(self.ctx, 'active', self.ctx.alive)(ref):
                decision = self.plan(ref)
                if decision != self.ctx.get(ref, ("runtime", "behavior_decision")):
                    self.ctx.set(ref, ("runtime", "behavior_decision"), decision)
