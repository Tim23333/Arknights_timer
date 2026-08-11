"""Gym-style agent environment for Arknights battle analysis.

Wraps the Simulator so an AI (RL / LLM / search) can "play" a level:

    from ark_emulator.agent_env import AgentEnv
    env = AgentEnv(level_id="level_main_01-01",
                   squad=[{"charId": "char_002_amiya", "skillIndex": 2}])
    obs, info = env.reset(seed=123)
    obs, reward, done, info = env.step({"type": "deploy",
                                        "charId": "char_002_amiya",
                                        "row": 3, "col": 4,
                                        "direction": 1})

Observation = full battle snapshot (t, cost, lifePoint, deployed, enemies,
tokens, projectiles, events since the previous step, stats, ...).
Reward is configurable and defaults to:
    +kill_reward per enemy killed, -leak_penalty per leak,
    -deploy_penalty per deploy, -skill_penalty per skill cast,
    +victory_bonus on victory / -defeat_penalty on defeat.
"""
import time

from .api import Simulator


class AgentEnv:
    def __init__(self, level_id="level_main_01-01", squad=None,
                 custom_enemies=None, custom_level=None, data_dir=None,
                 kill_reward=10.0, leak_penalty=20.0, deploy_penalty=0.5,
                 skill_penalty=0.1, victory_bonus=100.0,
                 defeat_penalty=-50.0, damage_reward=0.0,
                 damage_taken_penalty=0.0, time_penalty=0.0,
                 max_steps=None, seed=None):
        self.level_id = level_id
        self.squad = list(squad or [])
        self.custom_enemies = list(custom_enemies or [])
        self.custom_level = custom_level
        self.data_dir = data_dir
        self.kill_reward = float(kill_reward)
        self.leak_penalty = float(leak_penalty)
        self.deploy_penalty = float(deploy_penalty)
        self.skill_penalty = float(skill_penalty)
        self.victory_bonus = float(victory_bonus)
        self.defeat_penalty = float(defeat_penalty)
        self.damage_reward = float(damage_reward)
        self.damage_taken_penalty = float(damage_taken_penalty)
        self.time_penalty = float(time_penalty)
        self.max_steps = max_steps
        self.seed = seed
        self.sim = None
        self._last_seq = 0
        self._prev_stats = {}
        self._last_cost = None
        self._last_life = None
        self._last_deploys = 0
        self._last_skills = 0
        self._prev_tick = 0
        self._done = False

    # ---- lifecycle ----
    def reset(self, seed=None, level_id=None, squad=None,
              custom_enemies=None):
        """(Re)create the simulator; returns (obs, info)."""
        self.level_id = level_id or self.level_id
        if squad is not None:
            self.squad = list(squad)
        if custom_enemies is not None:
            self.custom_enemies = list(custom_enemies)
        if seed is not None:
            self.seed = seed
        self.sim = Simulator(
            level_id=self.level_id,
            data_dir=self.data_dir,
            squad=self.squad,
            custom_enemies=self.custom_enemies,
            custom_level=self.custom_level,
            seed=self.seed,
        )
        self._last_seq = 0
        self._prev_stats = dict(self.sim.battle.stats)
        self._last_cost = self.sim.battle.cost
        self._last_life = self.sim.battle.life_point
        self._last_deploys = int(self.sim.battle.stats.get(
            "deployments", 0))
        self._last_skills = int(self.sim.battle.stats.get("skillCasts", 0))
        self._prev_tick = self.sim.tick
        self._done = False
        obs = self.sim.snapshot(since_seq=self._last_seq)
        self._last_seq = obs["events"][-1]["seq"] if obs["events"] else 0
        return obs, self.info()

    def step(self, action):
        """Apply one action and advance a bounded number of ticks.

        Returns (obs, reward, done, info). ``action`` is a dict with a
        ``type`` field; invalid actions return a zero reward with
        info["invalid"] set instead of crashing."""
        if self.sim is None or self._done:
            return self.observe(), 0.0, True, self.info()
        info = self.info()
        if action is None:
            info["ok"] = True
            info["actionResult"] = "wait"
            info["invalid"] = False
        else:
            atype = action.get("type")
            if atype in ("deploy", "withdraw", "skill", "deploy_summon",
                         "deploy_token", "pause", "resume", "step_ticks"):
                info["ok"], info["actionResult"] = self._apply(action)
                info["invalid"] = not info["ok"]
            else:
                info["ok"] = False
                info["invalid"] = True
                info["actionResult"] = "unknown_action"
        return self._observe_reward(info)

    def _apply(self, action):
        atype = action.get("type")
        try:
            if atype == "deploy":
                return self.sim.deploy(
                    action.get("charId"), action.get("row", 0),
                    action.get("col", 0), action.get("direction", 1))
            if atype == "withdraw":
                return self.sim.withdraw(action.get("instId"))
            if atype == "skill":
                return self.sim.activate_skill(
                    action.get("instId"), action.get("skillIndex", 0))
            if atype == "deploy_summon":
                return self.sim.deploy_summon(
                    action.get("charId"), action.get("row", 0),
                    action.get("col", 0), action.get("direction", 1))
            if atype == "deploy_token":
                return self.sim.deploy_token(
                    action.get("tokenKey"), action.get("row", 0),
                    action.get("col", 0), action.get("direction", 1))
            if atype == "pause":
                self.sim.pause()
                return True, "paused"
            if atype == "resume":
                self.sim.resume()
                return True, "resumed"
            if atype == "step_ticks":
                n = int(action.get("ticks", 1))
                self.sim.run_ticks(n)
                return True, n
        except Exception as e:
            return False, str(e)
        return False, "unknown_action"

    def _observe_reward(self, info):
        """Advance the simulation until the next AI decision point (one
        logic tick), then compute reward from the deltas."""
        if not self.sim.battle.paused:
            self.sim.tick_once()
        reward = self._reward_delta()
        obs = self.observe()
        done = self.sim.battle.finished
        if done:
            if self.sim.battle.result == "victory":
                reward += self.victory_bonus
            elif self.sim.battle.result == "defeat":
                reward += self.defeat_penalty
        if self.max_steps and self.sim.tick >= self.max_steps:
            done = True
        self._done = done
        info.update(self.info())          # refresh state, keep action fields
        info["reward"] = round(reward, 4)
        info["done"] = done
        return obs, round(reward, 4), done, info

    def observe(self):
        """Latest snapshot with events since the previous observation."""
        obs = self.sim.snapshot(since_seq=self._last_seq)
        if obs["events"]:
            self._last_seq = obs["events"][-1]["seq"]
        return obs

    def _reward_delta(self):
        st = self.sim.battle.stats
        dk = int(st.get("kills", 0)) - int(self._prev_stats.get("kills", 0))
        dl = int(st.get("leaks", 0)) - int(self._prev_stats.get("leaks", 0))
        dd = int(st.get("deployments", 0)) - self._last_deploys
        ds = int(st.get("skillCasts", 0)) - self._last_skills
        dmg = float(st.get("playerDamageDealt", 0.0)) - float(
            self._prev_stats.get("playerDamageDealt", 0.0))
        dtaken = float(st.get("playerDamageTaken", 0.0)) - float(
            self._prev_stats.get("playerDamageTaken", 0.0))
        dtick = max(0, self.sim.tick - self._prev_tick)
        life = self.sim.battle.life_point
        dlife = (self._last_life or 0) - life
        self._prev_stats = dict(st)
        self._last_deploys += dd
        self._last_skills += ds
        self._last_life = life
        self._last_cost = self.sim.battle.cost
        self._prev_tick = self.sim.tick
        return (dk * self.kill_reward - dl * abs(self.leak_penalty) -
                dd * abs(self.deploy_penalty) -
                ds * abs(self.skill_penalty) + dlife * 0.0 +
                dmg * self.damage_reward -
                dtaken * abs(self.damage_taken_penalty) -
                dtick * abs(self.time_penalty))

    # ---- helpers for planners ----
    def deployable_chars(self):
        """Squad chars (ids) not currently deployed (max one per char)."""
        if self.sim is None:
            return []
        deployed = {o.char_id for o in self.sim.battle.operators
                    if not o.dead}
        return [c for c in self.squad_ids() if c not in deployed]

    def squad_ids(self):
        out = []
        for m in self.squad:
            cid = m.get("charId") if isinstance(m, dict) else m
            if cid:
                out.append(cid)
        return out

    def legal_actions(self, include_directions=False, max_cells=64):
        """Currently-executable player actions (deploy/skill/withdraw).

        Waiting is implicit (every step advances one tick), so no explicit
        wait action is returned. Deploys are validated against cost,
        redeploy cooldown, character limit and occupancy; skills against SP
        readiness and the equipped-skill rule; withdraws for alive units.
        """
        acts = []
        b = self.sim.battle
        if b is None or b.finished:
            return acts
        # ---- deploys ----
        deployed_ids = {o.char_id for o in b.operators if not o.dead}
        if len(b.operators) < b.character_limit:
            for cid in self.squad_ids():
                if cid in deployed_ids:
                    continue
                data = b._char_base(cid)
                if not data:
                    continue
                attrs = b._squad_attrs(cid, data)
                if b.cost < attrs.get("cost", 0):
                    continue
                if b.tick < b._redeploy_until.get(cid, 0):
                    continue
                dirs = (0, 1, 2, 3) if include_directions else (1,)
                count = 0
                for r in range(b.map.rows):
                    for c in range(b.map.cols):
                        if b.map.buildable(r, c, 1) is not True:
                            continue
                        if any((o.row, o.col) == (r, c)
                               for o in b.operators):
                            continue
                        for d in dirs:
                            acts.append({"type": "deploy", "charId": cid,
                                         "row": r, "col": c, "direction": d})
                            count += 1
                            if count >= max_cells:
                                break
                        if count >= max_cells:
                            break
                    if count >= max_cells:
                        break
        # ---- skills / withdraws ----
        for o in b.operators:
            if o.dead:
                continue
            acts.append({"type": "withdraw", "instId": o.inst_id})
            sc = getattr(o, "skill_controller", None)
            if sc is None:
                continue
            for i, s in enumerate(sc.skills):
                if s.sp_type in (0, 8):
                    continue
                if sc.equipped_index is not None and \
                        i != sc.equipped_index:
                    continue
                if s.on_cooldown or o.sp < s.sp_cost:
                    continue
                acts.append({"type": "skill", "instId": o.inst_id,
                             "skillIndex": i})
        return acts

    def buildable_cells(self, char_id=None):
        """Ground/high tiles an operator could be deployed on."""
        if self.sim is None:
            return []
        m = self.sim.battle.map
        cells = []
        for r in range(m.rows):
            for c in range(m.cols):
                t = m.tile(r, c)
                if t is not None and t.buildable_type:
                    cells.append((r, c))
        return cells

    def info(self):
        out = {
            "levelId": self.level_id,
            "tick": self.sim.tick if self.sim else 0,
            "t": round((self.sim.tick if self.sim else 0) / 30.0, 3),
            "result": self.sim.battle.result if self.sim else None,
            "finished": self.sim.battle.finished if self.sim else False,
            "stats": dict(self.sim.battle.stats) if self.sim else {},
            "lifePoint": self.sim.battle.life_point if self.sim else 0,
            "cost": self.sim.battle.cost if self.sim else 0,
        }
        return out


class BatchEnv:
    """Synchronous vector environment over N AgentEnvs (same level).

    reset_all(seeds) / step_all(actions) / info_all() operate on the whole
    batch so a planner can evaluate many seeds in one sweep.
    """

    def __init__(self, n, level_id="level_main_01-01", seed=None, **kwargs):
        self.n = int(n)
        self.seed = seed
        self.envs = [AgentEnv(level_id=level_id, **kwargs)
                     for _ in range(self.n)]

    def reset_all(self, seeds=None):
        if seeds is None:
            base = self.seed if self.seed is not None else 0
            seeds = [base + i for i in range(self.n)]
        return [e.reset(seed=s) for e, s in zip(self.envs, seeds)]

    def step_all(self, actions):
        return [e.step(a) for e, a in zip(self.envs, actions)]

    def info_all(self):
        return [e.info() for e in self.envs]

    def legal_all(self, **kw):
        return [e.legal_actions(**kw) for e in self.envs]

    def done_all(self):
        return [e.info()["finished"] for e in self.envs]


def play_random(env, steps=300, seed=0):
    """Trivial random policy demo: returns (score, result, history len)."""
    import random
    rng = random.Random(seed)
    obs, info = env.reset(seed=seed)
    total = 0.0
    for _ in range(steps):
        chars = env.deployable_chars()
        cells = env.buildable_cells()
        acts = [{"type": "step_ticks", "ticks": rng.randint(10, 60)}]
        if chars and cells:
            acts.append({"type": "deploy",
                         "charId": rng.choice(chars),
                         "row": cells[rng.randrange(len(cells))][0],
                         "col": cells[rng.randrange(len(cells))][1],
                         "direction": rng.randint(0, 3)})
        a = rng.choice(acts)
        obs, reward, done, info = env.step(a)
        total += reward
        if done:
            break
    return total, info["result"], info["tick"]
