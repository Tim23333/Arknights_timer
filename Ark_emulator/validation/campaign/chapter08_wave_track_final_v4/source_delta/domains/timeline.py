"""Declarative action origins and explicit model wave-clear policy.

The scheduler policy is content, not a claim about any client's scheduler body.
All mutable progress lives in World, including managed membership and wake tokens.
"""
from ark_sim.contracts import thaw
from collections.abc import Mapping


def validate_finish_request(effect):
    fields={'op','target','parameters','metadata'}
    options={'finish_and_skip':False,'track_source_at_next_wave':False,'track_source_wave_delta':0,'track_all_managed_at_next_wave':False}
    if set(effect)-fields or effect.get('target') not in ('source','self') or not isinstance(effect.get('parameters'),Mapping) or set(effect['parameters'])!=set(options):raise ValueError('Explicit finite actor-source timeline finish request required')
    for key,value in options.items():
        if type(effect['parameters'][key]) is not type(value) or (key!='track_source_at_next_wave' and effect['parameters'][key]!=value):raise ValueError('Unimplemented timeline finish flag combination')


class TimelineSystem:
    def __init__(self, context):
        self.ctx = context
        self.handlers = {"domain.timeline.signal": self.signal,
                         "domain.timeline.action": self.action}

    @property
    def config(self):
        return self.ctx.program.scenario["timeline"]

    def _state(self):
        return self.ctx.state()["timeline"]

    def _save(self, state):
        self.ctx.state_update(timeline=state)

    def _stop_if_finished(self, state):
        battle = self.ctx.state()
        if not battle.get("finished"):
            return False
        for task in self.ctx.session.scheduler.pending:
            if task["kind"] in self.handlers:
                self.ctx.session.cancel(task["id"])
        if not state["done"]:
            # Canceled births/actions are not successful completion. Keep counts
            # and membership as evidence of work interrupted by the terminal result.
            state.update(phase="stopped", done=True, wake_at=None,
                         terminal_result=battle.get("result"))
            state["wake_token"] += 1
            for row in state.get('tracking_requests',{}).values():
                if row['status']=='pending':row.update(status='terminal_cancelled',ended_at=self.ctx.session.time)
            self.ctx.emit("timeline.stopped", {"result": battle.get("result"),
                "pending_waves": battle["pending_waves"], "remaining_actions": state["remaining_actions"]})
            self._save(state)
        return True

    def _schedule(self, state, at):
        # A late-phase retirement cannot insert a phase-0 task into the past.
        session = self.ctx.session
        key = session._active_key
        if at == session.time and key is not None and key[1:3] > (session.scheduler.rank(0), 0):
            at += 1
        if state.get("wake_at") is not None and state["wake_at"] <= at:
            return
        state["wake_token"] += 1
        state["wake_at"] = at
        session.schedule("domain.timeline.signal", {"token": state["wake_token"]}, at, phase=0)

    def start(self):
        with self.ctx.session.atomic():
            if "timeline" in self.ctx.state():
                raise ValueError("timeline already started")
            config = self.config
            count = sum(a.get("count", 1) for w in config["waves"] for f in w["fragments"]
                        for a in f["actions"] if a["kind"] == "spawn")
            state = {"phase": "wave_entry", "wave_index": 0, "fragment_index": 0,
                     "members": {}, "remaining_actions": 0, "wake_token": 0,
                     "wake_at": None, "done": False, "play_start": self.ctx.session.time}
            self.ctx.state_update(pending_waves=self.ctx.state()["pending_waves"]+count)
            self._schedule(state, self.ctx.session.time)
            self._save(state)

    def _blocked(self, state, fragment=False):
        released = str(state['wave_index']) in state.get('finish_requests',{})
        return any(m["wave"] == state["wave_index"] and
                   (not fragment or m["fragment"] == state["fragment_index"]) and
                   m["blocks_fragment" if fragment else "blocks_wave"]
                   for m in (*(state["members"].values() if fragment or not released else ()), *state.get("control_members", {}).values()))

    def finish_current(self,source,effect,cause=None):
        validate_finish_request(effect)
        with self.ctx.session.atomic():
            source=self.ctx.session.world.resolve(source);state=self._state()
            if self.ctx.state().get('finished') or state['done']:raise ValueError('Timeline already terminal')
            member=state['members'].get(str(source))
            if not self.ctx.alive(source) or member is None or member['wave']!=state['wave_index']:
                self.ctx.emit('timeline.finish_rejected',{'source':source,'wave':state['wave_index'],'reason':'not_current_managed_source'},cause)
                return False
            if state['phase'] in ('wave_post','wave_entry'):return False
            key=str(state['wave_index'])
            existing=state.get('finish_requests',{}).get(key)
            if existing is not None:
                if not effect['parameters']['track_source_at_next_wave'] or existing['parameters']['track_source_at_next_wave']:return False
                incarnation=self._incarnation(source)
                if type(existing.get('source')) is not int or existing['source']!=source or type(existing.get('wave')) is not int or existing['wave']!=state['wave_index'] or type(existing.get('lifecycle_generation')) is not int or existing['lifecycle_generation']!=incarnation['lifecycle_generation']:
                    self.ctx.emit('timeline.finish_rejected',{'source':source,'wave':state['wave_index'],'reason':'tracking_upgrade_source_identity'},cause)
                    return False
                if type(member['wave']) is not int or type(state['wave_index']) is not int:raise ValueError('Tracking wave identity must be an integer')
                existing['parameters']['track_source_at_next_wave']=True
                existing['tracking_upgraded_at']=self.ctx.session.time
                state.setdefault('tracking_requests',{})[key]={'source':source,'origin_wave':state['wave_index'],'target_wave':state['wave_index']+1,'incarnation':incarnation,'requested_at':self.ctx.session.time,'status':'pending','membership':thaw(member)}
                self._save(state)
                self.ctx.emit('timeline.source_tracking_requested',{'source':source,'wave':state['wave_index'],'incarnation':incarnation,'upgrade':True},cause)
                state=self._state()
                if state['phase']=='wave_gate':self._schedule(state,self.ctx.session.time)
                self._save(state)
                return True
            request={'source':source,'wave':state['wave_index'],'lifecycle_generation':self.ctx.get(source,('runtime','lifecycle_generation'),0),'requested_at':self.ctx.session.time,'phase':state['phase'],'parameters':thaw(effect['parameters'])}
            state.setdefault('finish_requests',{})[key]=request
            tracking=effect['parameters']['track_source_at_next_wave']
            if tracking:
                incarnation=self._incarnation(source)
                if type(member['wave']) is not int or type(state['wave_index']) is not int:raise ValueError('Tracking wave identity must be an integer')
                state.setdefault('tracking_requests',{})[key]={'source':source,'origin_wave':state['wave_index'],'target_wave':state['wave_index']+1,'incarnation':incarnation,'requested_at':self.ctx.session.time,'status':'pending','membership':thaw(member)}
                # Synchronous callbacks must see this actual request, never stale local facts.
                self._save(state)
            self.ctx.emit('timeline.finish_requested',request,cause)
            if tracking:state=self._state()
            if state['phase']=='wave_gate':self._schedule(state,self.ctx.session.time)
            self._save(state)
            return True

    def _incarnation(self,source):
        stamp={k:self.ctx.get(source,('runtime',k),0) for k in ('lifecycle_generation','death_generation')}
        if any(type(v) is not int or v<0 for v in stamp.values()):raise ValueError('Tracking requires strict actual lifecycle generations')
        return stamp

    def _tracking_entry(self,state,final=False):
        for key in list(state.get('tracking_requests',{})):
            row=state['tracking_requests'][key]
            if not isinstance(row,Mapping) or type(row.get('source')) is not int or row['source']<=0 or any(type(row.get(k)) is not int or row[k]<0 for k in ('origin_wave','target_wave','requested_at')) or row['target_wave']!=row['origin_wave']+1:raise ValueError('Invalid persisted tracking identity')
            stamp=row.get('incarnation')
            if not isinstance(stamp,Mapping) or set(stamp)!={'lifecycle_generation','death_generation'} or any(type(v) is not int or v<0 for v in stamp.values()):raise ValueError('Invalid persisted tracking incarnation')
            if row['status']!='pending' or row['target_wave']!=state['wave_index']:continue
            source=row['source'];member=state['members'].get(str(source))
            if final:
                row.update(status='no_next_wave',ended_at=self.ctx.session.time)
                self._save(state);self.ctx.emit('timeline.source_tracking_finished',{'source':source,'from_wave':row['origin_wave'],'reason':'no_next_wave'});state=self._state();continue
            if not self.ctx.alive(source) or self._incarnation(source)!=row['incarnation'] or member is None or member['wave']!=row['origin_wave']:
                row.update(status='source_invalidated',ended_at=self.ctx.session.time)
                self._save(state);self.ctx.emit('timeline.source_tracking_finished',{'source':source,'from_wave':row['origin_wave'],'reason':'source_invalidated'});state=self._state();continue
            # This is the old actor, not a birth or a newly managed fragment action.
            state['members'][str(source)]={**member,'wave':state['wave_index'],'fragment':-1,'tracking_origin_wave':row['origin_wave'],'tracking_incarnation':thaw(row['incarnation'])}
            row.update(status='transferred',transferred_at=self.ctx.session.time)
            self._save(state);self.ctx.emit('timeline.source_transferred',{'source':source,'from_wave':row['origin_wave'],'to_wave':state['wave_index'],'incarnation':thaw(row['incarnation'])});state=self._state()
            if self.ctx.state().get('finished'):break
        return state

    def signal(self, session, payload):
        with session.atomic():
            state = self._state()
            if self._stop_if_finished(state):
                return
            if payload["token"] != state["wake_token"] or state["done"]:
                return
            state["wake_at"] = None
            waves = self.config["waves"]
            # Empty fragments/waves are finite; each pass advances an index or waits.
            while True:
                phase = state["phase"]
                if phase == "wave_entry":
                    if state["wave_index"] >= len(waves):
                        if state.get('tracking_requests'):state=self._tracking_entry(state,final=True)
                        state.update(phase="complete", done=True)
                        self.ctx.emit("timeline.finished", {"waves": len(waves)})
                        break
                    if state.get('tracking_requests'):
                        state=self._tracking_entry(state)
                        if self._stop_if_finished(state):break
                    state["wave_start"] = session.time
                    state["fragment_index"] = 0
                    state["phase"] = "fragment_entry"
                    at = session.time+self.ctx.quantize(waves[state["wave_index"]].get("pre_delay_seconds", 0))
                    if at > session.time:
                        self._schedule(state, at)
                        break
                elif phase == "fragment_entry":
                    wave = waves[state["wave_index"]]
                    if state["fragment_index"] >= len(wave["fragments"]):
                        state.update(phase="wave_gate", gate_start=session.time)
                        continue
                    fragment = wave["fragments"][state["fragment_index"]]
                    state["phase"] = "fragment_start"
                    at = session.time+self.ctx.quantize(fragment.get("pre_delay_seconds", 0))
                    if at > session.time:
                        self._schedule(state, at)
                        break
                elif phase == "fragment_start":
                    state["fragment_start"] = session.time
                    fragment = waves[state["wave_index"]]["fragments"][state["fragment_index"]]
                    state["remaining_actions"] = sum(a.get("count", 1) for a in fragment["actions"])
                    state["phase"] = "fragment_wait"
                    for index, action in enumerate(fragment["actions"]):
                        first = session.time+self.ctx.quantize(action.get("delay_seconds", 0))
                        for repeat in range(action.get("count", 1)):
                            at = session.time+self.ctx.quantize(action.get("delay_seconds", 0)+repeat*action.get("interval_seconds", 0))
                            payload = {"wave": state["wave_index"],
                                "fragment": state["fragment_index"], "action": index,
                                "repeat": repeat, "action_start": first}
                            if action["kind"] == "control":
                                alias = action.get("instanceAlias")
                                if alias is not None and action.get("count", 1) > 1: alias += f"/{repeat}"
                                origins = {name: state[name] for name in ("play_start", "wave_start", "fragment_start")}
                                origins["action_start"] = first
                                payload["control"] = self.ctx.controls.prepare(action["definition"], alias, origins)
                                state.setdefault("control_pending", {})[payload["control"]] = {"wave": state["wave_index"], "fragment": state["fragment_index"]}
                            task = session.schedule("domain.timeline.action", payload, at, phase=0)
                            if action["kind"] == "control": self.ctx.controls.track_start_task(payload["control"], task)
                    if state["remaining_actions"]:
                        break
                elif phase == "fragment_wait":
                    if state["remaining_actions"] or self._blocked(state, fragment=True):
                        break
                    state["fragment_index"] += 1
                    state["phase"] = "fragment_entry"
                elif phase == "wave_gate":
                    wave = waves[state["wave_index"]]
                    timeout = wave.get("max_wait_seconds", -1)
                    wait = self.config["policy"] == "managed_clear" and self._blocked(state)
                    if timeout < 0:
                        wait = wait and self.config["negative_timeout_policy"] == "wait_for_clear"
                    else:
                        deadline = state["gate_start"]+self.ctx.quantize(timeout)
                        wait = wait and session.time < deadline
                        if wait:
                            self._schedule(state, deadline)
                    if wait:
                        break
                    self.ctx.emit("timeline.wave_completed", {"wave": state["wave_index"],
                        "remaining_managed": sum(m["wave"] == state["wave_index"] for m in state["members"].values()),
                        "policy": self.config["policy"]})
                    state["phase"] = "wave_post"
                    at = session.time+self.ctx.quantize(wave.get("post_delay_seconds", 0))
                    if at > session.time:
                        self._schedule(state, at)
                        break
                elif phase == "wave_post":
                    state["wave_index"] += 1
                    state["phase"] = "wave_entry"
                else:
                    raise ValueError(f"unknown timeline phase {phase}")
            self._save(state)

    def action(self, session, payload):
        with session.atomic():
            state = self._state()
            if self._stop_if_finished(state):
                return
            if state["phase"] != "fragment_wait" or (payload["wave"], payload["fragment"]) != (state["wave_index"], state["fragment_index"]):
                raise ValueError("timeline action has stale origin")
            action = self.config["waves"][payload["wave"]]["fragments"][payload["fragment"]]["actions"][payload["action"]]
            origins = {name: state[name] for name in ("play_start", "wave_start", "fragment_start")}
            origins["action_start"] = payload["action_start"]
            if action["kind"] == "spawn":
                spawn = thaw(action["spawn"])
                if action.get("count", 1) > 1 and spawn.get("instanceAlias"):
                    spawn["instanceAlias"] += f"/{payload['repeat']}"
                spawn.setdefault("parameters", {})["timing_origins"] = origins
                ref = self.ctx.lifecycle.spawn_wave(session, spawn, count_pending=False)
                if ref is None:
                    raise ValueError("timeline spawn did not create an entity")
                # create can synchronously cause retirement; never enroll dead actors.
                state = self._state()
                if action.get("managed", True) and self.ctx.alive(ref):
                    state["members"][str(ref)] = {"wave": payload["wave"], "fragment": payload["fragment"],
                        "blocks_wave": action.get("blocks_wave", True), "blocks_fragment": action.get("blocks_fragment", False)}
                self.ctx.state_update(pending_waves=self.ctx.state()["pending_waves"]-1)
            elif action["kind"] == "effects":
                for effect in action["effects"]:
                    self.ctx.effects.execute("system/battle", ["system/battle"], thaw(effect))
                state = self._state()
            elif action["kind"] == "control":
                ref = payload["control"]
                state.get("control_pending", {}).pop(ref, None)
                if action.get("managed", True):
                    state.setdefault("control_members", {})[ref] = {"wave": payload["wave"], "fragment": payload["fragment"],
                        "blocks_wave": action.get("blocks_wave", True), "blocks_fragment": action.get("blocks_fragment", False)}
                state["remaining_actions"] -= 1
                self._save(state)
                self.ctx.controls.begin(ref)
                state = self._state()
            else:
                raise ValueError("unknown timeline action kind")
            if action["kind"] != "control": state["remaining_actions"] -= 1
            self.ctx.emit("timeline.action", {**payload, "origins": origins, "kind": action["kind"]})
            if not (self.ctx.controls is not None and self.ctx.state().get("finished")):
                self._schedule(state, session.time)
            self._save(state)

    def control_released(self, reference, reason, policy=None):
        with self.ctx.session.atomic():
            state = self._state()
            pending = state.get("control_pending", {}).pop(reference, None)
            member = state.get("control_members", {}).pop(reference, None)
            if pending is not None and policy == "continue":
                if (pending["wave"], pending["fragment"]) != (state["wave_index"], state["fragment_index"]):
                    raise ValueError("pending control cancellation has stale fragment origin")
                state["remaining_actions"] -= 1
            if member is None and pending is None: return
            member = member or {**pending, "blocks_wave": False, "blocks_fragment": policy == "continue"}
            self.ctx.emit("timeline.control_released", {"control": reference, "reason": reason, **member})
            releases = member["wave"] == state["wave_index"] and ((state["phase"] == "wave_gate" and member["blocks_wave"]) or
                (state["phase"] == "fragment_wait" and member["blocks_fragment"] and member["fragment"] == state["fragment_index"]))
            if not self.ctx.state().get("finished") and not state["done"] and releases: self._schedule(state, self.ctx.session.time)
            self._save(state)

    def entity_retired(self, ref, reason):
        with self.ctx.session.atomic():
            if "timeline" not in self.ctx.state():
                return
            state = self._state()
            if self._stop_if_finished(state):
                return
            ref = self.ctx.session.world.resolve(ref)
            member = state["members"].pop(str(ref), None)
            for row in state.get('tracking_requests',{}).values():
                if row['source']==ref and row['status'] in ('pending','transferred'):row.update(status='retired',ended_at=self.ctx.session.time,reason=reason)
            if member is None:
                if state.get('tracking_requests'):self._save(state)
                return
            self.ctx.emit("timeline.member_released", {"target": ref, "reason": reason, **member})
            releases_current_gate = member["wave"] == state["wave_index"] and (
                (state["phase"] == "wave_gate" and member["blocks_wave"]) or
                (state["phase"] == "fragment_wait" and member["blocks_fragment"] and
                 member["fragment"] == state["fragment_index"]))
            # Membership can outlive a timed-out wave. Releasing such a member
            # must not invalidate a post/pre-delay wake belonging to another phase.
            if not state["done"] and releases_current_gate:
                self._schedule(state, self.ctx.session.time)
            self._save(state)
