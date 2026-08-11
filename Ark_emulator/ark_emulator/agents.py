"""Scripted agents for the Arknights AgentEnv (AI battle analysis).

GreedyDefender is a lightweight heuristic policy that demonstrates the
reset/step/legal_actions loop: deploy vanguards for DP, a blocker on the
route, medic + DPS behind it, activate ready skills, retreat low-HP
operators, otherwise wait. It is deliberately simple - the point is a
working agent harness, not a competitive strategy.
"""
import os
import sys

from .agent_env import AgentEnv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _nearest(obs, cells, to_row, to_col):
    best, bd = None, None
    for (r, c) in cells:
        d = abs(r - to_row) + abs(c - to_col)
        if bd is None or d < bd:
            best, bd = (r, c), d
    return best


class GreedyDefender:
    """Heuristic policy over AgentEnv.legal_actions().

    Deploys along a role plan (vanguard -> blockers -> medic -> DPS),
    covering both a straight mid-row flow and a vertical flow; fires ready
    skills (DPS first), retreats low-HP operators, otherwise waits.
    """

    def __init__(self, vanguards=("char_149_scave", "char_151_myrtle",
                                  "char_102_texas"),
                 blockers=("char_150_snakek", "char_122_beagle"),
                 medic="char_128_plosis",
                 dps=("char_002_amiya", "char_124_kroos"),
                 early_dps=("char_002_amiya",),
                 early_blocker=None):
        self.vanguards = list(vanguards)
        self.blockers = list(blockers)
        self.medic = medic
        self.dps = list(dps)
        self.early_dps = list(early_dps)
        self.early_blocker = early_blocker
        self.stage = 0

    @staticmethod
    def _route_cells(routes):
        """All passable-ish cells covered by routes (start/end/checkpoints
        + Manhattan gaps) for choke-point blocker placement."""
        cells = set()

        def _add(a, b):
            if None in a or None in b:
                return
            r1, c1 = a
            r2, c2 = b
            rr, cc = r1, c1
            cells.add((rr, cc))
            while (rr, cc) != (r2, c2):
                if rr != r2:
                    rr += 1 if r2 > rr else -1
                elif cc != c2:
                    cc += 1 if c2 > cc else -1
                cells.add((rr, cc))

        for rt in routes or []:
            pts = []
            sp = rt.get("startPosition") or {}
            if sp.get("row") is not None:
                pts.append((sp["row"], sp["col"]))
            for cp in rt.get("checkpoints") or []:
                p = cp.get("position") or {}
                if p.get("row") is not None:
                    pts.append((p["row"], p["col"]))
            ep = rt.get("endPosition") or {}
            if ep.get("row") is not None:
                pts.append((ep["row"], ep["col"]))
            for p in pts:
                cells.add(p)
            for a, b in zip(pts, pts[1:]):
                _add(a, b)
        return cells

    def _plan(self, rows, cols, routes=None):
        """Role plan: (char_id, target_row, target_col).

        When route data is available, blockers sit on real route cells near
        the exits (choke points) instead of hard-coded mid-row cells.
        """
        mid_r = rows // 2
        mid_c = cols // 2
        plan = []
        route_cells = sorted(self._route_cells(routes)) if routes else []
        exits = []
        if routes:
            for rt in routes:
                ep = rt.get("endPosition") or {}
                if ep.get("row") is not None:
                    exits.append((ep["row"], ep["col"]))
        # an early vertical blocker stops the fast top-exit flow first
        if self.early_blocker:
            plan.append((self.early_blocker, min(rows - 1, mid_r + 2),
                         mid_c))
        # early DPS shoots down the main lane while blockers arrive.
        # With range-gated targeting (operators idle when nothing is in
        # range) the DPS must actually cover the route, so deploy near the
        # route cell closest to the map centre when route data exists.
        for i, cid in enumerate(self.early_dps):
            if route_cells:
                target = min(route_cells,
                             key=lambda p: (abs(p[0] - mid_r) +
                                            abs(p[1] - mid_c)))
                plan.append((cid, target[0], target[1]))
            else:
                plan.append((cid, mid_r, min(cols - 1, mid_c + 2)))
        for i, cid in enumerate(self.vanguards):
            if route_cells:
                # vanguards block the first enemies: sit on a route cell
                # near the route start (range-gated targeting needs actual
                # coverage)
                starts = []
                for rt in routes or []:
                    sp = rt.get("startPosition") or {}
                    if sp.get("row") is not None:
                        starts.append((sp["row"], sp["col"]))
                if starts:
                    target = min(route_cells,
                                 key=lambda p: min(
                                     abs(p[0] - s[0]) + abs(p[1] - s[1])
                                     for s in starts))
                else:
                    target = min(route_cells,
                                 key=lambda p: (abs(p[0] - mid_r) +
                                                abs(p[1] - mid_c)))
                plan.append((cid, target[0], target[1]))
            else:
                plan.append((cid, mid_r, 1 + i))
        for i, bid in enumerate(self.blockers):
            if route_cells and exits:
                if i == 0:
                    # choke: route cell nearest any exit
                    target = min(route_cells,
                                 key=lambda p: min(
                                     abs(p[0] - e[0]) + abs(p[1] - e[1])
                                     for e in exits))
                else:
                    # second blocker: route cell farthest from the first
                    first = plan[-1][1:]
                    target = max(route_cells,
                                 key=lambda p: abs(p[0] - first[0]) +
                                               abs(p[1] - first[1]))
                plan.append((bid, target[0], target[1]))
            else:
                if i == 0:
                    plan.append((bid, mid_r, mid_c + 1))
                else:
                    plan.append((bid, min(rows - 1, mid_r + 2), mid_c))
        if self.medic:
            plan.append((self.medic, max(0, mid_r - 1), mid_c - 1))
        for i, cid in enumerate(self.dps):
            plan.append((cid, mid_r + (0 if i == 0 else -1),
                         min(cols - 1, mid_c + 2)))
        # opening order: cheap first vanguard (blocks the first mid enemy)
        # -> early blocker (stops the fast vertical flow) -> rest
        mids = [(c, r, c2) for c, r, c2 in plan if c in self.blockers]
        tail = [(c, r, c2) for c, r, c2 in plan
                if c not in self.vanguards and c not in self.blockers]
        out = []
        if self.vanguards:
            first_v = next((c, r, c2) for c, r, c2 in plan
                           if c == self.vanguards[0])
            out.append(first_v)
        if self.early_blocker:
            out.append((self.early_blocker, min(rows - 1, mid_r + 2),
                        mid_c))
        for i, cid in enumerate(self.vanguards[1:], 1):
            out.append((cid, mid_r, 1 + i))
        out += mids + tail
        # de-duplicate (early_dps may also appear in tail)
        return list(dict.fromkeys(out))

    def act(self, env, obs, info):
        rows = obs["map"]["rows"]
        cols = obs["map"]["cols"]
        ops = obs["deployed"]
        legal = env.legal_actions(max_cells=512)
        # 1. retreat operators below 30% HP
        for o in ops:
            if o.get("dead"):
                continue
            if o.get("hp", 0) < 0.3 * o.get("maxHp", 1):
                return {"type": "withdraw", "instId": o["instId"]}
        # 2. fire ready skills (DPS first, then anyone)
        for a in legal:
            if a["type"] == "skill":
                oid = a["instId"]
                o = next((x for x in ops if x["instId"] == oid), None)
                if o and o["charId"] in self.dps:
                    return a
        for a in legal:
            if a["type"] == "skill":
                return a
        # 3. deploy along the role plan (nearest buildable cell to target).
        # Fresh (never-deployed) chars take priority over redeploys so a
        # withdrawn vanguard does not starve the blocker slots.
        deployed_ids = {o["charId"] for o in ops if not o.get("dead")}
        self._ever = getattr(self, "_ever", set())
        self._ever |= deployed_ids
        # fresh chars only: do not waste DP on redeploys while a new role
        # (blocker/DPS) is still missing
        remaining = [(c, tr, tc)
                     for c, tr, tc in self._plan(rows, cols,
                                                 obs.get("routes"))
                     if c not in deployed_ids and c not in self._ever]
        # strategic wait: hold DP until the early blocker is affordable
        if remaining and remaining[0][0] == self.early_blocker:
            has = any(a["type"] == "deploy" and
                      a["charId"] == self.early_blocker for a in legal)
            if not has:
                return None
        for cid, tr, tc in remaining:
            best = None
            best_d = None
            for a in legal:
                if a["type"] == "deploy" and a["charId"] == cid:
                    d = abs(a["row"] - tr) + abs(a["col"] - tc)
                    if best_d is None or d < best_d:
                        best, best_d = a, d
            if best is not None:
                if self._is_ranged(cid):
                    _battle = getattr(getattr(env, "sim", None), "battle",
                                      None)
                    direction = self._best_direction(
                        _battle, cid, best["row"], best["col"],
                        obs.get("routes"))
                    best = dict(best)
                    best["direction"] = direction
                return best
        return None

    @staticmethod
    def _is_ranged(cid):
        try:
            from ark_emulator.loader import DataStore
            store = DataStore()
            data = store.characters.get(cid) or {}
            return int(data.get("position") or 0) == 2
        except Exception:
            return False

    @staticmethod
    def _best_direction(b, cid, row, col, routes):
        """Facing that covers the most route cells (range-gated)."""
        try:
            from ark_emulator.battle import range_offsets_rotated
            from ark_emulator.loader import DataStore
            store = DataStore()
            data = store.characters.get(cid) or {}
            range_id = None
            for ph in (data.get("phases") or []):
                rid = ph.get("rangeId")
                if rid:
                    range_id = rid
                    break
            if not range_id:
                return 1
            cells = set()
            for rt in routes or []:
                for p in (rt.get("startPosition"), rt.get("endPosition")):
                    if p and p.get("row") is not None:
                        cells.add((p["row"], p["col"]))
                for cp in rt.get("checkpoints") or []:
                    p = cp.get("position") or {}
                    if p.get("row") is not None:
                        cells.add((p["row"], p["col"]))
            if not cells:
                return 1
            best_dir, best_cnt = 1, -1
            for d in range(4):
                shape = range_offsets_rotated(range_id, d)
                cnt = sum(1 for (dr, dc) in shape
                          if (row + dr, col + dc) in cells)
                if cnt > best_cnt:
                    best_cnt, best_dir = cnt, d
            return best_dir
        except Exception:
            return 1


class BeamAgent(GreedyDefender):
    """GreedyDefender + short rollout beam search over deployment cells.

    While fewer than ``beam_deploys`` operators are out, every candidate
    deploy (top-N cells nearest each role target) is rolled forward for
    ``rollout_seconds`` using a fresh base greedy policy; the candidate with
    the best accumulated environment reward is executed. This exploits the
    environment's determinism to discover early DP/blocking trade-offs the
    hand-written heuristic misses (e.g. deploy the second vanguard before
    the expensive vertical blocker).
    """

    def __init__(self, decide_every=10.0, rollout_seconds=12.0,
                 beam_cells=4, beam_deploys=4, **kw):
        super().__init__(**kw)
        self.decide_every = float(decide_every)
        self.rollout_ticks = int(float(rollout_seconds) * 30)
        self.beam_cells = int(beam_cells)
        self.beam_deploys = int(beam_deploys)
        self._next_decision_t = 0.0
        self._decisions = 0
        self._rollout_agent = GreedyDefender(**kw)

    def act(self, env, obs, info):
        import copy
        t = obs["tick"] / 30.0
        base = super().act(env, obs, info)
        if base is not None and base["type"] in ("withdraw", "skill"):
            return base
        deployed = [o for o in obs["deployed"] if not o.get("dead")]
        if len(deployed) >= self.beam_deploys or t < self._next_decision_t:
            return base
        self._next_decision_t = t + self.decide_every
        self._decisions += 1
        legal = env.legal_actions(max_cells=512)
        deploys = [a for a in legal if a["type"] == "deploy"]
        if not deploys:
            return base
        rows, cols = obs["map"]["rows"], obs["map"]["cols"]
        targets = {c: (r, c2)
                   for c, r, c2 in self._plan(rows, cols, obs.get("routes"))}
        cand = []
        for a in deploys:
            tr, tc = targets.get(a["charId"], (rows // 2, 1))
            cand.append((abs(a["row"] - tr) + abs(a["col"] - tc), a))
        cand.sort(key=lambda x: x[0])
        cand = [a for _, a in cand[:self.beam_cells]]
        best_a, best_s = None, None
        for a in cand:
            try:
                e2 = copy.deepcopy(env)
            except Exception:
                continue
            o2, i2 = e2.observe(), e2.info()
            _, r2, d2, i3 = e2.step(a)
            score = r2
            for _ in range(self.rollout_ticks):
                if d2:
                    break
                o2, r2, d2, i3 = e2.step(self._rollout_agent.act(e2, o2, i3))
                score += r2
                if d2:
                    break
            if best_s is None or score > best_s:
                best_s, best_a = score, a
        return best_a if best_a is not None else base


def play_episode(env, agent, max_steps=100000):
    """Run one episode; returns (reward, result, tick)."""
    obs, info = env.reset()
    total = 0.0
    for _ in range(max_steps):
        if info.get("finished"):
            break
        action = agent.act(env, obs, info)
        obs, reward, done, info = env.step(action)
        total += reward
        if done:
            break
    return total, info["result"], info["tick"]


def evaluate(level_ids, seeds=(0, 1, 2), agent=None, squad=None,
             max_steps=100000, n_envs=None, custom_levels=None):
    """Sweep levels x seeds with BatchEnv; returns per-level stats."""
    from .agent_env import BatchEnv
    if agent is None:
        agent = GreedyDefender()
    out = {}
    for lid in level_ids:
        batch = BatchEnv(len(seeds), level_id=lid, squad=squad or [],
                         custom_level=(custom_levels or {}).get(lid))
        batch.reset_all(seeds=list(seeds))
        rewards = [0.0] * len(seeds)
        results = []
        steps = 0
        while steps < max_steps:
            infos = batch.info_all()
            if all(i["finished"] for i in infos):
                break
            obss = [e.observe() for e in batch.envs]
            actions = [agent.act(e, o, i)
                       for e, o, i in zip(batch.envs, obss, infos)]
            rs = batch.step_all(actions)
            for k, (o, r, d, i) in enumerate(rs):
                rewards[k] += r
                if d:
                    results.append((k, i["result"], i["tick"]))
            steps += 1
        out[lid] = {
            "seeds": list(seeds),
            "rewards": [round(r, 1) for r in rewards],
            "results": [next((res[1] for res in results if res[0] == k),
                             "running") for k in range(len(seeds))],
        }
    return out
