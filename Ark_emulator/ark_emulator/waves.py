"""Wave scheduler driven by LevelData.waves.

The runtime timeline is computed from the raw level's waves (chained-wave
model, MECHANICS §11):

  - waves are SEQUENTIAL: wave i starts after wave i-1's last event time
    plus wave i-1's postDelay and wave i's preDelay. (Concurrent waves
    would contradict real gameplay; all observed wave preDelays are ~0
    while wave durations are tens of seconds.)
  - fragments inside a wave are CONCURRENT streams: every fragment's
    preDelay is relative to the wave start, and its actions begin at
    fragment_start + action.preDelay and repeat `count` times at
    `interval` seconds.
  - intra-tick order ("no two enemies exist at the same instant"):
    deterministic sort key (t, wave, fragment, action, seq).

A precomputed bundle waveTimeline (older additive model) is accepted as a
fallback for levels without parsed raw waves; it is still re-sorted by the
same deterministic key so same-tick spawns keep a stable order.
"""

from .consts import TIME_ROUGH_LOGIC_RATE


def _action_type_name(at):
    if isinstance(at, dict):
        return at.get("name") or at.get("value") or "SPAWN"
    return at or "SPAWN"


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
        wave_start = wave_t + (w.get("preDelay") or 0.0)
        wave_end = 0.0
        for fi, fr in enumerate(w.get("fragments") or []):
            actions = fr.get("actions") or []
            frag_start = wave_start + (fr.get("preDelay") or 0.0)
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
                        "seq": i,
                        "wave": wi,
                        "fragment": fi,
                        "action": ai,
                    })
                    if t > wave_end:
                        wave_end = t
        # chain: next wave starts after this wave's last event + postDelay
        wave_t = wave_end + (w.get("postDelay") or 0.0)
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
        battle = self.battle
        now = battle.tick / TIME_ROUGH_LOGIC_RATE
        spawned = []
        while self._idx < len(self.timeline):
            ev = self.timeline[self._idx]
            if ev.get("t", 0.0) > now + 1e-6:
                break
            self._idx += 1
            atype = ev.get("actionType")
            hg = ev.get("hiddenGroup")
            if hg and not self._hidden_group_allowed(hg):
                battle.emit(battle.tick, "hidden_group_action_skipped",
                            {"type": atype, "key": ev.get("key"),
                             "hiddenGroup": hg, "t": ev.get("t")})
                continue
            if not ev.get("key") and atype in (
                    "SPAWN", "ACTIVATE_PREDEFINED", "TRIGGER_PREDEFINED",
                    "WITHDRAW_PREDEFINED"):
                # random-group "empty" candidate: a valid pick that spawns
                # nothing (e.g. weight-only no-enemy outcomes in rogue maps)
                battle.emit(battle.tick, "random_group_empty",
                            {"type": atype, "groupKey": ev.get("groupKey"),
                             "packKey": ev.get("packKey"),
                             "t": ev.get("t")})
                continue
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
        if self._idx >= len(self.timeline):
            self.finished = True
        return spawned

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
