"""Wave schedulers driven by ``LevelData.waves``.

``build_wave_timeline`` produces an action-only earliest forecast. The
runtime scheduler loads waves/fragments one at a time (MECHANICS §11):

  - waves are SEQUENTIAL. After its final fragment, a wave waits for its
    managed enemies to leave (or its positive maxTimeWaitingForNextWave)
    before post/pre-delay and loading the next wave.
  - fragments inside a wave are SEQUENTIAL: a fragment begins after the
    preceding fragment's action queue has finished, then waits its own
    preDelay.  Each action begins at fragment_start + action.preDelay and
    repeats `count` times at `interval` seconds.
  - intra-tick order ("no two enemies exist at the same instant"):
    deterministic sort key (t, wave, fragment, action, seq).

A precomputed bundle waveTimeline remains supported for legacy levels and
synthetic/branch timelines.
"""

from .consts import TIME_ROUGH_LOGIC_RATE


def _action_type_name(at):
    if isinstance(at, dict):
        return at.get("name") or at.get("value") or "SPAWN"
    return at or "SPAWN"


def _delay(value):
    """Level data uses null/-1 as no delay."""
    return max(0.0, float(value or 0.0))


def build_wave_timeline(waves, rng=None):
    """Flatten LevelData.waves into a deterministic absolute-time event list.

    Returns events {t, key, routeIndex, actionType, hiddenGroup, groupKey,
    packKey, weight, isEmpty, seq, wave, fragment, action} sorted by
    (t, wave, fragment, action, seq).

    Random spawn groups (2026-08-08 MECHANICS docs / RandomGroupSchedulerPreprocessor):
    actions carrying randomSpawnGroupKey form a mutually-exclusive weighted
    group per (wave, fragment, key). When ``rng`` is supplied (the battle's
    key RNG) each group is resolved at build time -- one candidate is drawn
    by weight and only the winning candidate (plus its
    randomSpawnGroupPackKey companions) stays in the timeline, so the
    chained wave timing is computed from the resolved actions. Without an
    ``rng`` the raw candidates are all kept (static/unresolved view).
    """
    events = []
    wave_t = 0.0
    for wi, w in enumerate(waves or []):
        wave_start = wave_t + _delay(w.get("preDelay"))
        wave_end = wave_start
        # Native Scheduler._DealWave yields _DealFragment one by one, and
        # _DealFragment yields ExecuteActionQueue before it returns.  Thus a
        # fragment's preDelay starts only after the preceding action queue
        # has drained.  Treating every preDelay as wave-relative made later
        # fragments run out of order (main_05-10 spawned Faust at 11s).
        fragment_cursor = wave_start
        for fi, fr in enumerate(w.get("fragments") or []):
            actions = fr.get("actions") or []
            frag_start = fragment_cursor + _delay(fr.get("preDelay"))
            fragment_end = frag_start
            keep = _resolve_fragment_random_groups(actions, rng)
            for ai, a in enumerate(actions):
                if not keep(ai, a):
                    continue
                t0 = frag_start + (a.get("preDelay") or 0.0)
                interval = a.get("interval") or 0.0
                count = int(a.get("count") or 1)
                for i in range(max(1, count)):
                    t = round(t0 + i * interval, 3)
                    events.append({
                        "t": t,
                        "key": a.get("key"),
                        "routeIndex": (a.get("routeIndex")
                                       if a.get("routeIndex") is not None
                                       else 0),
                        "actionType": _action_type_name(a.get("actionType")),
                        "hiddenGroup": a.get("hiddenGroup") or None,
                        "groupKey": a.get("randomSpawnGroupKey") or None,
                        "packKey": a.get("randomSpawnGroupPackKey") or None,
                        "weight": a.get("weight"),
                        "isEmpty": a.get("key") is None,
                        "managedByScheduler": a.get(
                            "managedByScheduler") is not False,
                        "dontBlockWave": bool(a.get("dontBlockWave")),
                        "blockFragment": bool(a.get("blockFragment")),
                        "forceBlockWaveInBranch": bool(
                            a.get("forceBlockWaveInBranch")),
                        "isUnharmfulAndAlwaysCountAsKilled": bool(a.get(
                            "isUnharmfulAndAlwaysCountAsKilled")),
                        "notCountInTotal": bool(a.get("notCountInTotal")),
                        "seq": i,
                        "wave": wi,
                        "fragment": fi,
                        "action": ai,
                        "waveStart": round(wave_start, 3),
                        "fragmentStart": round(frag_start, 3),
                    })
                    if t > fragment_end:
                        fragment_end = t
            fragment_cursor = fragment_end
            if fragment_end > wave_end:
                wave_end = fragment_end
        # chain: next wave starts after this wave's last event + postDelay
        wave_t = wave_end + _delay(w.get("postDelay"))
    events.sort(key=lambda e: (e["t"], e.get("wave", 0),
                               e.get("fragment", 0), e.get("action", 0),
                               e.get("seq", 0)))
    return events


def _resolve_fragment_random_groups(actions, rng):
    """Return ``keep(ai, a)`` after random-spawn-group resolution.

    Group identity is (wave, fragment, randomSpawnGroupKey); candidates are
    the actions carrying that key. With an ``rng`` one candidate is drawn
    per group via ``rng.next(total_weight)`` (weights None -> 0; all-zero
    groups fall back to uniform). Packs (randomSpawnGroupPackKey) whose
    candidate lost are removed together with their companions; a pack
    survives when any of its candidates wins, and pack-only actions that
    belong to no group are always kept. Without an ``rng`` everything is
    kept (static view).
    """
    groups = {}               # groupKey -> [(action_index, action)]
    pack_candidates = set()   # pack keys referenced by some candidate
    for ai, a in enumerate(actions):
        gk = a.get("randomSpawnGroupKey")
        pk = a.get("randomSpawnGroupPackKey")
        if gk:
            groups.setdefault(gk, []).append((ai, a))
        if gk and pk:
            pack_candidates.add(pk)
    if not groups or rng is None:
        return lambda ai, a: True
    # deterministic RNG consumption order: first-appearance of group keys
    order = []
    for ai, a in enumerate(actions):
        gk = a.get("randomSpawnGroupKey")
        if gk and gk not in order:
            order.append(gk)
    winners = {}              # groupKey -> winning action index
    for gk in order:
        cands = groups[gk]
        weights = []
        total = 0
        for ai, a in cands:
            w = a.get("weight")
            w = int(w) if w is not None else 0
            w = max(0, w)
            weights.append((ai, w))
            total += w
        if total <= 0:
            weights = [(ai, 1) for ai, _ in cands]
            total = len(cands)
        roll = rng.next(total)
        acc = 0
        winner = cands[-1][0]
        for ai, w in weights:
            acc += w
            if roll < acc:
                winner = ai
                break
        winners[gk] = winner
    win_packs = {actions[w].get("randomSpawnGroupPackKey")
                 for w in winners.values()}

    def keep(ai, a):
        gk = a.get("randomSpawnGroupKey")
        pk = a.get("randomSpawnGroupPackKey")
        if gk:
            return winners.get(gk) == ai
        if pk:
            if pk not in pack_candidates:
                return True
            return pk in win_packs
        return True

    return keep


class WaveScheduler:
    def __init__(self, timeline, battle):
        # deterministic intra-tick order: (t, wave, fragment, action, seq)
        self.timeline = sorted(timeline or [], key=lambda x: (
            x.get("t", 0.0), x.get("wave", 0), x.get("fragment", 0),
            x.get("action", 0), x.get("seq", 0)))
        self.battle = battle
        self._idx = 0
        self.spawned = 0
        self.finished = False
        # resolved random-spawn-group winners (one entry per group)
        self.random_groups = []
        seen = set()
        for ev in self.timeline:
            gk = ev.get("groupKey")
            if not gk:
                continue
            gid = (ev.get("wave"), ev.get("fragment"), gk)
            if gid in seen:
                continue
            seen.add(gid)
            self.random_groups.append({
                "wave": ev.get("wave"),
                "fragment": ev.get("fragment"),
                "groupKey": gk,
                "key": ev.get("key"),
                "packKey": ev.get("packKey"),
                "weight": ev.get("weight"),
                "isEmpty": ev.get("isEmpty", False),
            })

    def update(self):
        """Advance scheduler by one tick; returns list of spawned enemy keys."""
        now = self.battle.tick / TIME_ROUGH_LOGIC_RATE
        spawned = []
        while self._idx < len(self.timeline):
            ev = self.timeline[self._idx]
            if ev.get("t", 0.0) > now + 1e-6:
                break
            self._idx += 1
            self._execute_event(ev, spawned)
        if self._idx >= len(self.timeline):
            self.finished = True
        return spawned

    def _execute_event(self, ev, spawned):
        battle = self.battle
        atype = ev.get("actionType")
        hg = ev.get("hiddenGroup")
        if hg and not self._hidden_group_allowed(hg):
            battle.emit(battle.tick, "hidden_group_action_skipped",
                        {"type": atype, "key": ev.get("key"),
                         "hiddenGroup": hg, "t": ev.get("t")})
            return
        if not ev.get("key") and atype in (
                "SPAWN", "ACTIVATE_PREDEFINED", "TRIGGER_PREDEFINED",
                "WITHDRAW_PREDEFINED"):
            battle.emit(battle.tick, "random_group_empty",
                        {"type": atype, "groupKey": ev.get("groupKey"),
                         "packKey": ev.get("packKey"),
                         "t": ev.get("t")})
            return
        if atype == "SPAWN":
            enemy = battle.spawn_enemy(
                key=ev.get("key"), route_index=ev.get("routeIndex"),
                source_ev=ev)
            if enemy is not None:
                spawned.append(ev.get("key"))
                self.spawned += 1
        elif atype == "ACTIVATE_PREDEFINED":
            battle.activate_predefined(ev.get("key"))
        elif atype == "TRIGGER_PREDEFINED":
            battle.trigger_predefined(ev.get("key"))
        elif atype == "WITHDRAW_PREDEFINED":
            battle.withdraw_predefined(ev.get("key"))
        else:
            battle.emit(battle.tick, "action",
                        {"type": atype, "key": ev.get("key"),
                         "t": ev.get("t")})

    def _hidden_group_allowed(self, group):
        """Hidden-group actions only fire when a level rune enables their
        group for the current difficulty (level_hidden_group_enable), unless
        a level_hidden_group_disable rune hides it again."""
        battle = self.battle
        if battle is None:
            return False
        hg = getattr(battle, "_rune_hidden_groups", None)
        if not hg:
            return False
        g = str(group)
        return g in hg.get("enable", set()) and \
            g not in hg.get("disable", set())

    def finish_current_wave(self):
        """Skip all remaining events of the current wave (game
        FinishCurrentWave action node); later waves still spawn."""
        if self._idx >= len(self.timeline):
            self.finished = True
            return
        cur = self.timeline[self._idx].get("wave", 0)
        while self._idx < len(self.timeline) and \
                self.timeline[self._idx].get("wave", 0) == cur:
            self._idx += 1
        if self._idx >= len(self.timeline):
            self.finished = True

    def remaining(self):
        return len(self.timeline) - self._idx

    def next_spawn_at(self):
        """Seconds until the next SPAWN event (None if none left)."""
        for ev in self.timeline[self._idx:]:
            if ev.get("actionType") == "SPAWN":
                return round(float(ev.get("t", 0.0)) -
                             self.battle.tick / TIME_ROUGH_LOGIC_RATE, 3)
        return None

    def status(self):
        """Runtime state exposed to API/UI in legacy timeline mode."""
        return {
            "mode": "timeline",
            "phase": "finished" if self.finished else "actions",
            "currentWave": None,
            "totalWaves": None,
            "currentFragment": None,
            "totalFragments": None,
            "waveLoadedAt": None,
            "waveStartedAt": None,
            "fragmentStartedAt": None,
            "nextTransitionAt": None,
            "waitingEnemies": 0,
        }


class RuntimeWaveScheduler(WaveScheduler):
    """Stateful native-style loader for parsed LevelData waves.

    A fragment is loaded only after the preceding fragment action queue has
    drained. A later wave is loaded only after the preceding wave's managed
    enemies have cleared, unless a positive maximum wait expires.
    """

    def __init__(self, waves, battle, rng=None):
        self.raw_waves = list(waves or [])
        super().__init__(build_wave_timeline(self.raw_waves, rng=rng), battle)
        self._events_by_fragment = {}
        self._forecast_wave_start = {}
        self._forecast_fragment_start = {}
        for source in self.timeline:
            wi = int(source.get("wave", 0))
            fi = int(source.get("fragment", 0))
            ev = dict(source)
            ev["_fragmentOffset"] = round(
                float(ev.get("t", 0.0)) -
                float(ev.get("fragmentStart", 0.0)), 6)
            self._events_by_fragment.setdefault((wi, fi), []).append(ev)
            self._forecast_wave_start.setdefault(
                wi, float(ev.get("waveStart", 0.0)))
            self._forecast_fragment_start.setdefault(
                (wi, fi), float(ev.get("fragmentStart", 0.0)))

        self._wave_idx = -1
        self._fragment_idx = -1
        self._phase = "init"
        self._deadline = None
        self._wave_loaded_at = None
        self._wave_started_at = None
        self._fragment_started_at = None
        self._queue = []
        self._queue_idx = 0
        self._queue_end_at = None
        self._wave_shift = 0.0
        self._wait_started_at = None
        self.finished = not self.raw_waves
        if self.raw_waves:
            self._load_wave(0, self._now())

    def _now(self):
        return self.battle.tick / TIME_ROUGH_LOGIC_RATE

    def _emit_state(self, type_, **data):
        data.setdefault("wave", self._wave_idx)
        data.setdefault("fragment", self._fragment_idx)
        self.battle.emit(self.battle.tick, type_, data)

    def _load_wave(self, wi, base):
        if wi >= len(self.raw_waves):
            self._phase = "finished"
            self.finished = True
            self._deadline = None
            self._wave_idx = len(self.raw_waves)
            self._fragment_idx = -1
            return
        self._wave_idx = wi
        self._fragment_idx = -1
        self._wave_loaded_at = float(base)
        self._wave_started_at = float(base) + _delay(
            self.raw_waves[wi].get("preDelay"))
        self._wave_shift = self._wave_started_at - \
            self._forecast_wave_start.get(wi, 0.0)
        self._phase = "wave_pre_delay"
        self._deadline = self._wave_started_at
        self._wait_started_at = None
        for enemy in getattr(self.battle, "enemies", []):
            if not getattr(enemy, "dead", False) and \
                    getattr(enemy, "_track_next_wave", False):
                enemy._wave_index = wi
                enemy._released_from_wave = False
                enemy._track_next_wave = False
        self._emit_state("wave_loaded", loadedAt=round(float(base), 3),
                         startsAt=round(self._wave_started_at, 3))

    def _start_fragment_delay(self, fi, base):
        fragments = self.raw_waves[self._wave_idx].get("fragments") or []
        if fi >= len(fragments):
            self._start_wave_clear_wait(base)
            return
        self._fragment_idx = fi
        self._fragment_started_at = float(base) + _delay(
            fragments[fi].get("preDelay"))
        self._phase = "fragment_pre_delay"
        self._deadline = self._fragment_started_at

    def _load_fragment_queue(self, base):
        self._fragment_started_at = float(base)
        forecast = self._forecast_fragment_start.get(
            (self._wave_idx, self._fragment_idx), float(base))
        self._wave_shift = float(base) - forecast
        self._queue = []
        for source in self._events_by_fragment.get(
                (self._wave_idx, self._fragment_idx), []):
            ev = dict(source)
            ev["t"] = round(float(base) + ev.pop("_fragmentOffset"), 6)
            ev["waveStart"] = round(float(self._wave_started_at or 0.0), 6)
            ev["fragmentStart"] = round(float(base), 6)
            self._queue.append(ev)
        self._queue.sort(key=lambda x: (
            x.get("t", 0.0), x.get("action", 0), x.get("seq", 0)))
        self._queue_idx = 0
        self._queue_end_at = max(
            [float(e.get("t", base)) for e in self._queue] or [float(base)])
        self._phase = "actions"
        self._deadline = (float(self._queue[0]["t"])
                          if self._queue else self._queue_end_at)
        self._emit_state("fragment_loaded", startsAt=round(float(base), 3),
                         actions=len(self._queue))

    def _fragment_blockers(self):
        return [e for e in getattr(self.battle, "enemies", [])
                if not getattr(e, "dead", False)
                and getattr(e, "_managed_by_scheduler", False)
                and getattr(e, "_wave_index", None) == self._wave_idx
                and getattr(e, "_fragment_index", None) == self._fragment_idx
                and getattr(e, "_block_fragment", False)
                and not getattr(e, "_released_from_wave", False)]

    def _wave_blockers(self):
        return [e for e in getattr(self.battle, "enemies", [])
                if not getattr(e, "dead", False)
                and getattr(e, "_managed_by_scheduler", False)
                and getattr(e, "_wave_index", None) == self._wave_idx
                and not getattr(e, "_dont_block_wave", False)
                and not getattr(e, "_released_from_wave", False)]

    def _finish_fragment_queue(self, base):
        # Native blockFragment waits for the asynchronous action executor's
        # completion callback, not for the spawned enemy to die. Emulator
        # action executors above are synchronous, so a drained queue means
        # every blockFragment callback has completed as well.
        self._advance_fragment(base)

    def _advance_fragment(self, base):
        self._wait_started_at = None
        self._start_fragment_delay(self._fragment_idx + 1, base)

    def _start_wave_clear_wait(self, base):
        self._phase = "waiting_wave_clear"
        self._wait_started_at = float(base)
        max_wait = float(self.raw_waves[self._wave_idx].get(
            "maxTimeWaitingForNextWave") or -1.0)
        self._deadline = (float(base) + max_wait if max_wait > 0 else None)
        self._emit_state("wave_waiting", enemies=len(self._wave_blockers()),
                         timeoutAt=(round(self._deadline, 3)
                                    if self._deadline is not None else None))

    def _start_post_delay(self, base, timed_out=False):
        self._phase = "wave_post_delay"
        self._deadline = float(base) + _delay(
            self.raw_waves[self._wave_idx].get("postDelay"))
        self._emit_state("wave_finished", finishedAt=round(float(base), 3),
                         timedOut=bool(timed_out))

    def update(self):
        if self.finished:
            return []
        now = self._now()
        spawned = []
        # One tick can cross several zero-duration transitions.
        for _ in range(4096):
            if self._phase == "wave_pre_delay":
                if now + 1e-6 < self._deadline:
                    break
                self._start_fragment_delay(0, self._deadline)
                continue
            if self._phase == "fragment_pre_delay":
                if now + 1e-6 < self._deadline:
                    break
                self._load_fragment_queue(self._deadline)
                continue
            if self._phase == "actions":
                while self._queue_idx < len(self._queue) and \
                        float(self._queue[self._queue_idx].get("t", 0.0)) \
                        <= now + 1e-6:
                    ev = self._queue[self._queue_idx]
                    self._queue_idx += 1
                    self._idx += 1
                    self._execute_event(ev, spawned)
                if self._queue_idx < len(self._queue):
                    self._deadline = float(
                        self._queue[self._queue_idx].get("t", now))
                    break
                self._finish_fragment_queue(self._queue_end_at)
                continue
            if self._phase == "waiting_fragment_clear":
                if self._fragment_blockers():
                    break
                self._advance_fragment(now)
                continue
            if self._phase == "waiting_wave_clear":
                blockers = self._wave_blockers()
                timed_out = self._deadline is not None and \
                    now + 1e-6 >= self._deadline
                if blockers and not timed_out:
                    break
                base = self._deadline if timed_out else now
                self._start_post_delay(base, timed_out=timed_out)
                continue
            if self._phase == "wave_post_delay":
                if now + 1e-6 < self._deadline:
                    break
                self._load_wave(self._wave_idx + 1, self._deadline)
                continue
            break
        return spawned

    def finish_current_wave(self):
        if self.finished or self._wave_idx >= len(self.raw_waves):
            self.finished = True
            self._phase = "finished"
            return
        while self._idx < len(self.timeline) and \
                int(self.timeline[self._idx].get("wave", 0)) == self._wave_idx:
            self._idx += 1
        self._queue_idx = len(self._queue)
        self._start_wave_clear_wait(self._now())

    def next_spawn_at(self):
        if self.finished or self._wave_idx < 0:
            return None
        now = self._now()
        for ev in self.timeline[self._idx:]:
            if int(ev.get("wave", -1)) != self._wave_idx:
                break  # the next wave's load time depends on enemy clearance
            if ev.get("actionType") == "SPAWN":
                due = float(ev.get("t", 0.0)) + self._wave_shift
                return round(max(0.0, due - now), 3)
        return None

    def status(self):
        fragments = []
        if 0 <= self._wave_idx < len(self.raw_waves):
            fragments = self.raw_waves[self._wave_idx].get("fragments") or []
        waiting = 0
        if self._phase == "waiting_fragment_clear":
            waiting = len(self._fragment_blockers())
        elif self._phase == "waiting_wave_clear":
            waiting = len(self._wave_blockers())
        return {
            "mode": "runtime",
            "phase": self._phase,
            "currentWave": (self._wave_idx + 1
                            if 0 <= self._wave_idx < len(self.raw_waves)
                            else None),
            "totalWaves": len(self.raw_waves),
            "currentFragment": (self._fragment_idx + 1
                                if self._fragment_idx >= 0 else None),
            "totalFragments": len(fragments),
            "waveLoadedAt": (round(self._wave_loaded_at, 3)
                             if self._wave_loaded_at is not None else None),
            "waveStartedAt": (round(self._wave_started_at, 3)
                              if self._wave_started_at is not None else None),
            "fragmentStartedAt": (
                round(self._fragment_started_at, 3)
                if self._fragment_started_at is not None else None),
            "nextTransitionAt": (round(self._deadline, 3)
                                 if self._deadline is not None else None),
            "waitingEnemies": waiting,
        }
