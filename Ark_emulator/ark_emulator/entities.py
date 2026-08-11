"""Battle entities: Unit base, Enemy (with route cursor state machine),
Operator (deployable), Token (neutral devices / summons).

Buff storage contract (used by skills/buffs modules):
    buffs: list[dict] with keys
      key, remaining_ticks, layers, add, mul, final_add, final_mul,
      source, tick_applied
    abnormal: dict[flag:int] -> {"ticks": int, "layers": int}
"""

import itertools

from .attributes import Attributes
from .consts import AbnormalFlag, EnemyState, STATE_NAMES, UPDATE_POS_TICK

_inst_ids = itertools.count(1)


def next_inst_id():
    return next(_inst_ids)


def _json_safe(value):
    """Recursively convert snapshot values to JSON-safe primitives: unit
    references (inst_id) become their id, nested dicts/lists are walked."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "inst_id"):
        return value.inst_id
    return value


class Unit:
    """Common base for enemies, operators and tokens."""

    def __init__(self, attributes=None, row=0, col=0, pos_x=None, pos_y=None):
        self.inst_id = next_inst_id()
        self.attributes = attributes if attributes is not None else Attributes()
        self.max_hp = max(1.0, self.attributes.get("maxHp"))
        self.hp = self.max_hp
        self.sp = 0.0
        self.sp_max = 0.0
        self.row = row
        self.col = col
        self.pos_x = pos_x if pos_x is not None else float(col)
        self.pos_y = pos_y if pos_y is not None else float(row)
        self.buffs = []
        # card / deck state (CreateCardBuff / CreateDeckBuff): each entry
        # {uid, key, lifeType, hidden, inHand, layers, isDeck}
        self.cards = []
        self.abnormal = {}
        self.side = 0            # 0=enemy, 1=player (consts side)
        self._pre_abnormal_state = None   # restore target after stun/freeze
        self.dead = False
        self.barrier = 0.0       # absorption pool (Barrier / \u5c4f\u969c)
        self._barrier_absorbed = 0.0
        # Doctor (\u533b\u751f) talent 2 "sympathetic nerve activation":
        # overheal converts to a decaying shield that absorbs BEFORE the
        # generic barrier pool (game: priority +1000 buff, single stack).
        self._rdoc_shield = 0.0
        self._rdoc_shield_cap = 0.0
        self._rdoc_decay_rate = 0.0     # per-0.1s ratio (0.02 E1 / 0.01 E2)
        self._rdoc_next_decay_tick = None
        # overlap (RewardTiles): source ids (trap keys) that this unit
        # explicitly allows to share its tile with it
        self._overlap_source_ids = set()
        # SetSpineSkin / free-summon-from-deck runtime cosmetic flags
        self._spine_skin = None
        self._freely_spawned_from_deck = False
        self._respawn_cnt = 0
        self._dont_occupy_deploy_cnt = False
        self._force_face_default = False
        self._graphic_hidden = False
        self._spine_color = None
        self._shadow_enabled = False
        self._animator_face_front = False
        self._hud_disabled = False
        self._spine_height_offset = 0.0
        self._last_move_direction = None
        self._manually_spawned = False

    # ---- damage / heal ----
    def absorb_rdoc_shield(self, amount):
        """Absorb from the doctor-overheal shield first (highest priority
        barrier in game). Returns the absorbed amount."""
        if self.dead or self._rdoc_shield <= 0 or amount <= 0:
            return 0.0
        absorbed = min(self._rdoc_shield, amount)
        self._rdoc_shield -= absorbed
        if self._rdoc_shield <= 1e-9:
            self._rdoc_shield = 0.0
        return absorbed

    def take_damage(self, amount):
        """Apply raw damage amount (post-formula). Returns actual HP dealt;
        the barrier pool absorbs damage first (game: Barrier absorbs before
        HP, element damage bypasses it)."""
        if self.dead or self.invincible():
            return 0.0
        self._barrier_absorbed = 0.0
        if self.barrier and self.barrier > 0:
            self._barrier_absorbed = min(self.barrier, amount)
            self.barrier -= self._barrier_absorbed
            amount -= self._barrier_absorbed
            if amount <= 0:
                return 0.0
        self.hp -= amount
        dealt = amount
        if self.hp <= 0:
            if self.undeadable():
                self.hp = 1.0
            else:
                self.hp = 0.0
                self.dead = True
        return dealt

    def heal(self, amount, ignore_heal_free=False):
        if self.dead or (not ignore_heal_free and self.heal_free()):
            return 0.0
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    # ---- abnormal flags ----
    def flag(self, flag):
        return flag in self.abnormal and self.abnormal[flag]["ticks"] > 0

    def set_flag(self, flag, ticks, layers=1, source=None):
        if ticks <= 0:
            self.abnormal.pop(flag, None)
            return
        rec = {"ticks": int(ticks), "layers": max(1, layers)}
        if source is not None:
            rec["source"] = source
        self.abnormal[flag] = rec

    def clear_flag(self, flag):
        self.abnormal.pop(flag, None)

    def _immune(self, name):
        try:
            return self.attributes.get_bool(name)
        except Exception:
            return False

    def invincible(self):
        if self.flag(AbnormalFlag.INVINCIBLE):
            return True
        return self._immune("invincible")

    def undeadable(self):
        if self.flag(AbnormalFlag.UNDEADABLE):
            return True
        return self._immune("undeadable")

    def heal_free(self):
        if self.flag(AbnormalFlag.HEAL_FREE):
            return True
        return self._immune("healFree")

    def is_dead(self):
        return self.dead

    # ---- snapshot ----
    def base_to_dict(self):
        a = self.attributes
        return {
            "instId": self.inst_id,
            "row": self.row,
            "col": self.col,
            "pos": {"x": round(self.pos_x, 4), "y": round(self.pos_y, 4)},
            "hp": round(self.hp, 3),
            "maxHp": round(self.max_hp, 3),
            "barrier": round(self.barrier, 3),
            "rdocShield": round(self._rdoc_shield, 3),
            "atk": round(a.get("atk"), 3),
            "def": round(a.get("def"), 3),
            "mres": round(a.get("magicResistance"), 3),
            "attackSpeed": round(a.get("attackSpeed"), 3),
            "blockCnt": int(a.get("blockCnt") or 0),
            "sp": round(self.sp, 3),
            "spMax": round(self.sp_max, 3),
            "buffs": [_json_safe(dict(b)) for b in self.buffs],
            "elements": self._element_snapshot(),
            "cards": [dict(c) for c in self.cards],
            "spineSkin": getattr(self, "_spine_skin", None),
            "spineColor": getattr(self, "_spine_color", None),
            "graphicHidden": bool(getattr(self, "_graphic_hidden", False)),
            "animatorFaceFront": bool(getattr(self, "_animator_face_front",
                                               False)),
            "hudDisabled": bool(getattr(self, "_hud_disabled", False)),
            "spineHeightOffset": round(float(
                getattr(self, "_spine_height_offset", 0.0) or 0.0), 4),
            "respawnCnt": int(getattr(self, "_respawn_cnt", 0) or 0),
            "abnormal": {str(k): dict(v) for k, v in self.abnormal.items()},
            "dead": self.dead,
        }

    def _element_snapshot(self):
        """Element bars (ep_neural/ep_water/ep_fire/ep_dark) and the
        burst types currently in cooldown (ep_burst_cd_{t})."""
        out = {}
        burst = []
        for b in getattr(self, "buffs", None) or []:
            k = b.get("key") or ""
            if k in ("ep_neural", "ep_water", "ep_fire", "ep_dark"):
                out[k] = round(float(b.get("value") or 0.0), 3)
            elif k.startswith("ep_burst_cd_"):
                try:
                    burst.append(int(k.rsplit("_", 1)[1]))
                except (TypeError, ValueError):
                    pass
        if burst:
            out["burst"] = sorted(burst)
        return out

    def to_dict(self):
        return self.base_to_dict()


class Enemy(Unit):
    """Enemy walking a route with a flow-field cursor."""

    def __init__(self, enemy_key, attributes, route_index=0, row=0, col=0,
                 level=0, route=None, game_map=None):
        super().__init__(attributes=attributes, row=row, col=col)
        self.side = 0
        self.enemy_key = enemy_key
        self.level = level
        self.route_index = route_index
        self.route = route or {}
        self.game_map = game_map
        self.state = EnemyState.BORN
        self.blocked_by = None
        self.block_volume = 1
        self.is_flying = False      # airborne (sniper priority, no block)
        # set when the next flow-field cell is held by a full blocker
        # (game: extra enemies queue behind instead of passing through)
        self.blocked_wait = False
        self.move_speed = 1.0
        self.attack_timer = 0.0
        self._pending_attack = None   # windup: damage lands at hit frame
        self.skill_controller = None
        self.life_point_reduce = 1
        self._death_reason = None
        self.can_not_exit = False
        self.is_unharmful = False
        # enemy talent parameters (EnemyData.talentBlackboard, e.g.
        # 进化的本质 mode_1.hp_ratio / mode_1_summon.interval / 蔓德拉
        # Reborn.branch_id).  The talent LOGIC lives on prefab Talent /
        # BasicTalent components; this dict exposes the numeric params.
        self.talent_blackboard = {}
        self.level_type = 0          # 0 \u666e\u901a / 1 \u7cbe\u82f1 / 2 \u9886\u8896
        self.spawned_tick = 0
        self._cursor = 0
        self._checkpoint_idx = 0
        self._wait_remaining = 0.0
        self._patrol = None            # {a, b, target, remaining, total}
        self._next_map = None
        self._dist_map = None
        self._motion_mode = 0
        self._born_ticks = 0
        self._born_delay = 0.5          # seconds; serialised _delayToBorn
        self.spawn_direction = None
        self.reach_exit = False
        self.hit_frame_ratio = 0.5      # OnAttack / anim duration (spine)
        self.displacement = None         # {dr, dc, remaining, speed, source}
        # EnemyForceTracePosition: chase a forced target/position instead
        # of the route until reached (or the target dies)
        self._trace_target = None
        self._trace_pos = None
        self._trace_reach = 0.0
        self._trace_ox = 0.0
        self._trace_oy = 0.0
        self._stop_trace_on_no_target = True
        # DisableEnemySwitchFaceByMove / ReleaseEnemyFromCurrentWave flags
        self._disable_face_switch = False
        self._released_from_wave = False
        self._track_next_wave = False
        # ModifyAttributeDataRangeOverride: min moveSpeed clamp (0 = none)
        self._move_speed_min = 0.0
        # IgnoreAllButMoveCp: ignore every checkpoint type except MOVE
        self._ignore_all_but_move_cp = False
        # EnemySkipWaitCheckPoint: skip WAIT checkpoints instead of waiting
        self._skip_wait_checkpoint = False

    # ---- lifecycle ----
    def init_route(self, game_map):
        self.game_map = game_map
        self._next_map, self._dist_map, self._motion_mode = \
            game_map.build_route_field(self.route)

    def _target_idx(self):
        end = self.route.get("endPosition") or {}
        return self.game_map.idx(end.get("row", 0), end.get("col", 0)) \
            if self.game_map else -1

    def dist_to_final(self):
        if not self.game_map:
            return 0.0
        i = self.game_map.idx(self.row, self.col)
        if i < 0 or self._dist_map is None:
            return 0.0
        d = self._dist_map[i]
        return d if d != float("inf") else 0.0

    # ---- state machine ----
    def set_state(self, state, reason=None):
        old = self.state
        self.state = state
        return old

    def _combat_ready(self):
        return (self.state in (EnemyState.MOVE, EnemyState.ATTACK,
                               EnemyState.COMBAT))

    def controllable_state(self):
        return self.state not in (EnemyState.STUN, EnemyState.FROZEN,
                                  EnemyState.LEVITATE, EnemyState.PALSY,
                                  EnemyState.DEAD, EnemyState.REACH_EXIT)

    # ---- per-tick update ----
    def update_born(self, dt):
        self._born_ticks += 1
        if self._born_ticks * (1.0 / 30.0) >= self._born_delay:
            self.state = EnemyState.MOVE

    def update_movement(self, dt):
        """Advance along route using flow field. dt = 1/30.
        Returns True if enemy reached the end this tick."""
        if self.state != EnemyState.MOVE:
            return False
        if self.blocked_by is not None:
            return False
        if self.blocked_wait:
            return False
        if not self._combat_ready_abnormal():
            return False
        if self.flag(43):                    # DOZE: cannot move
            return False
        if self.flag(13):                    # UNMOVABLE / \u675f\u7f1a: cannot move
            return False
        speed = self.attributes.get("moveSpeed") * self.move_speed
        if speed <= 0:
            return False
        _ms_min = float(getattr(self, "_move_speed_min", 0.0) or 0.0)
        if _ms_min > 0 and speed < _ms_min:
            speed = _ms_min
        if self._ignore_all_but_move_cp:
            # ignore WAIT/PATROL/DISAPPEAR checkpoints: jump straight to
            # the flow-field advance (MOVE-type behaviour)
            self._checkpoint_idx = len(
                (self.route or {}).get("checkpoints") or [])
        if self.flag(33):                    # FEARED: flee toward spawn
            return self._update_flee(dt, speed)
        if self.flag(41):                    # ATTRACTED: move to source
            src = self.abnormal.get(41, {}).get("source")
            if src is not None and not getattr(src, "dead", False):
                return self._update_toward(src.pos_x, src.pos_y, dt, speed)
        # EnemyForceTracePosition: chase the forced trace target / position
        tt = self._trace_target
        if tt is not None:
            if getattr(tt, "dead", False) or getattr(tt, "retreating", False):
                if self._stop_trace_on_no_target:
                    self._trace_target = None
                return False
            if self._trace_toward(tt.pos_x + self._trace_ox,
                                  tt.pos_y + self._trace_oy, dt, speed):
                self._trace_target = None
            return False
        if self._trace_pos is not None:
            tx, ty = self._trace_pos
            if self._trace_toward(tx, ty, dt, speed):
                self._trace_pos = None
            return False
        # checkpoint handling (types from extract_level_data.CHECKPOINT_TYPE)
        cps = self.route.get("checkpoints") or []
        if self._checkpoint_idx < len(cps):
            cp = cps[self._checkpoint_idx]
            ctype = (cp.get("type") or {})
            if isinstance(ctype, dict):
                ctype = ctype.get("value", 0)
            if ctype == 1 or ctype == 3:  # WAIT_FOR_SECONDS /
                                           # WAIT_CURRENT_FRAGMENT_TIME
                if self._skip_wait_checkpoint:
                    self._checkpoint_idx += 1
                    return False
                t = cp.get("time") or 0.0
                if self._wait_remaining <= 0:
                    self._wait_remaining = t
                self._wait_remaining -= dt
                if self._wait_remaining > 0:
                    return False
                self._checkpoint_idx += 1
            elif ctype == 4:  # WAIT_CURRENT_WAVE_TIME (absolute sim time)
                if self._skip_wait_checkpoint:
                    self._checkpoint_idx += 1
                    return False
                t = float(cp.get("time") or 0.0)
                if self.battle_time() < t:
                    return False
                self._checkpoint_idx += 1
            elif ctype == 8:  # PATROL_MOVE: walk + patrol back and forth
                if self._patrol is None:
                    prev = self._prev_checkpoint_position(cps,
                                                         self._checkpoint_idx)
                    a = (self.row, self.col)
                    b = ((cp.get("position") or {}).get("row", self.row),
                         (cp.get("position") or {}).get("col", self.col))
                    total = float(cp.get("time") or 6.0)  # default 6s patrol
                    self._patrol = {"a": a, "b": b, "target": b,
                                    "remaining": total, "total": total}
                return self._update_patrol(dt, speed)
            elif ctype in (5, 6):  # DISAPPEAR / APPEAR_AT_POS
                if ctype == 5:
                    self.state = EnemyState.DISAPPEAR
                    return False
                pos = cp.get("position") or {}
                self.row = pos.get("row", self.row)
                self.col = pos.get("col", self.col)
                self.pos_x = float(self.col)
                self.pos_y = float(self.row)
                self._checkpoint_idx += 1
            else:  # MOVE(0) / ALERT(7) / others: advance
                self._checkpoint_idx += 1
        if self._next_map is None:
            return False
        idx = self.game_map.idx(self.row, self.col)
        if idx < 0:
            return False
        target = self._target_idx()
        if idx == target and self.game_map.tiles[idx].is_end:
            return True
        nxt = self._next_map[idx]
        if nxt < 0 or nxt == idx:
            return False
        tr, tc = self.game_map.rc(nxt)
        dr = tr - self.row
        dc = tc - self.col
        step = speed * dt
        # move toward next tile centre
        tx = float(tc)
        ty = float(tr)
        dx = tx - self.pos_x
        dy = ty - self.pos_y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= step or dist < 1e-6:
            self.pos_x, self.pos_y = tx, ty
            self.row, self.col = tr, tc
            if nxt == target and self.game_map.tiles[nxt].is_end:
                return True
        else:
            self.pos_x += dx / dist * step
            self.pos_y += dy / dist * step
        # refresh current tile every UPDATE_POS_TICK (5)
        if self.spawned_tick % UPDATE_POS_TICK == 0:
            self._sync_tile()
        return False

    def _update_flee(self, dt, speed):
        """FEARED: run toward the route start (away from the front line)."""
        start = self.route.get("startPosition") or {"row": 0, "col": 0}
        tx = float(start.get("col", 0))
        ty = float(start.get("row", 0))
        return self._update_toward(tx, ty, dt, speed)

    def battle_time(self):
        """Simulation time in seconds (for absolute-time checkpoints)."""
        return self.spawned_tick / 30.0

    def _prev_checkpoint_position(self, cps, idx):
        for i in range(idx - 1, -1, -1):
            pos = cps[i].get("position") or {}
            if pos:
                return (pos.get("row", 0), pos.get("col", 0))
        return (self.row, self.col)

    def _update_patrol(self, dt, speed):
        """Walk between two patrol waypoints until the patrol time elapses."""
        p = self._patrol
        if p["remaining"] > 0:
            p["remaining"] -= dt
        tx, ty = float(p["target"][1]), float(p["target"][0])
        dx = tx - self.pos_x
        dy = ty - self.pos_y
        dist = (dx * dx + dy * dy) ** 0.5
        step = speed * dt
        if dist <= step:
            self.pos_x, self.pos_y = tx, ty
            self._sync_tile()
            # reached the patrol point: turn around
            p["target"] = p["a"] if p["target"] == p["b"] else p["b"]
        else:
            self.pos_x += dx / dist * step
            self.pos_y += dy / dist * step
            if self.spawned_tick % UPDATE_POS_TICK == 0:
                self._sync_tile()
        if p["remaining"] <= 0:
            self._patrol = None
            self._checkpoint_idx += 1
            return False
        return False

    def _update_toward(self, tx, ty, dt, speed):
        """Move straight toward a target position (fear / attract)."""
        tx = float(tx)
        ty = float(ty)
        dx = tx - self.pos_x
        dy = ty - self.pos_y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= 1e-6:
            return False
        step = speed * dt
        if dist <= step:
            self.pos_x, self.pos_y = tx, ty
        else:
            self.pos_x += dx / dist * step
            self.pos_y += dy / dist * step
        if self.spawned_tick % UPDATE_POS_TICK == 0:
            self._sync_tile()
        return False

    def _trace_toward(self, tx, ty, dt, speed):
        """Move toward a forced trace position; returns True when the
        enemy is within the reach radius (EnemyForceTracePosition)."""
        tx = float(tx)
        ty = float(ty)
        dx = tx - self.pos_x
        dy = ty - self.pos_y
        dist = (dx * dx + dy * dy) ** 0.5
        reach = float(getattr(self, "_trace_reach", 0.0) or 0.0)
        if dist <= reach + 1e-6:
            self._sync_tile()
            return True
        step = speed * dt
        if dist <= step:
            self.pos_x, self.pos_y = tx, ty
        else:
            self.pos_x += dx / dist * step
            self.pos_y += dy / dist * step
        if self.spawned_tick % UPDATE_POS_TICK == 0:
            self._sync_tile()
        return False

    def _sync_tile(self):
        if self.game_map:
            r = int(round(self.pos_y))
            c = int(round(self.pos_x))
            if self.game_map.idx(r, c) >= 0:
                self.row, self.col = r, c

    def _combat_ready_abnormal(self):
        return not any(self.flag(f) for f in (0, 16, 25, 39, 13))

    def update_displacement(self, dt):
        """Slide along the displacement vector with constant deceleration
        (v(t) = 2*remaining/t_remaining); returns True when done.

        Game model (PRTS ??????): push gives an instant impulse and the
        rigid body decelerates until its speed falls below the exit threshold;
        pull keeps applying force for the bound duration.  The endpoint is the
        PRTS ideal distance, so a decelerating profile reproduces both the
        final position and the ~1s slide time.
        The enemy cannot attack/block while being displaced."""
        d = self.displacement
        if d is None:
            return False
        t = float(d.get("duration_remaining", d["total"]))
        rem = d["remaining"]
        if t > 0:
            step = 2.0 * rem / t * dt
        else:
            step = rem
        t -= dt
        rem -= step
        d["remaining"] = max(0.0, rem)
        d["duration_remaining"] = max(0.0, t)
        tx = d["dest_x"]
        ty = d["dest_y"]
        dx = tx - self.pos_x
        dy = ty - self.pos_y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= step or rem <= 0 or t <= 0:
            self.pos_x, self.pos_y = tx, ty
            self._sync_tile()
            self.displacement = None
            return True
        nx = self.pos_x + dx / dist * step
        ny = self.pos_y + dy / dist * step
        # stop before entering an impassable tile (walls / cliffs)
        if self.game_map is not None:
            tr = int(round(ny))
            tc = int(round(nx))
            tile = self.game_map.tile(tr, tc)
            if tile is not None and not tile.passable(
                    getattr(self, "_motion_mode", 0)) and not tile.is_hole:
                self.displacement = None
                self._sync_tile()
                return True
        self.pos_x, self.pos_y = nx, ny
        if self.spawned_tick % UPDATE_POS_TICK == 0:
            self._sync_tile()
        return False

    def on_spawn(self, tick):
        self.spawned_tick = tick
        self.state = EnemyState.BORN
        try:
            from .attack_timing import hit_frame_ratio
            r = hit_frame_ratio(self.enemy_key, "Attack")
            if 0 < r < 1:
                self.hit_frame_ratio = r
        except Exception:
            pass

    # ---- snapshot ----
    def to_dict(self):
        d = self.base_to_dict()
        sc = getattr(self, "skill_controller", None)
        d.update({
            "key": self.enemy_key,
            "level": self.level,
            "state": STATE_NAMES.get(self.state, str(self.state)),
            "stateId": self.state,
            "routeIndex": self.route_index,
            "blockedBy": self.blocked_by.inst_id if self.blocked_by else None,
            "moveSpeed": round(self.attributes.get("moveSpeed") * self.move_speed, 4),
            "attackTimer": round(self.attack_timer, 4),
            "massLevel": float(self.attributes.get("massLevel") or 0.0),
            "rangeRadius": (float(self.attributes.get("rangeRadius"))
                            if self.attributes.get("rangeRadius")
                            is not None else None),
            "hitFrameRatio": round(self.hit_frame_ratio, 4),
            "pendingAttack": ({
                "target": self._pending_attack["target"].inst_id,
                "remaining": self._pending_attack["remaining"],
                "ranged": bool(self._pending_attack.get("ranged")),
            } if self._pending_attack else None),
            "distToFinal": round(self.dist_to_final(), 4),
            "lifePointReduce": self.life_point_reduce,
            "modeIndex": sc.mode_index if sc else 0,
            "skills": sc.skill_states() if sc else [],
            "casting": sc.casting_state() if sc else None,
            "displacement": self._displacement_snapshot(),
            "talentBlackboard": dict(
                getattr(self, "talent_blackboard", {}) or {}),
        })
        return d

    def _displacement_snapshot(self):
        d = self.displacement
        if d is None:
            return None
        return {
            "dr": d["dr"], "dc": d["dc"],
            "remaining": round(d["remaining"], 4),
            "total": round(d["total"], 4),
            "remainingSeconds": round(d.get("duration_remaining", 0.0), 4),
            "totalSeconds": round(d.get("duration_total", 0.0), 4),
            "kind": d.get("kind", "effect"),
            "forceLevel": d.get("force_level"),
            "dest": {"x": round(d["dest_x"], 4), "y": round(d["dest_y"], 4)},
            "source": d.get("source").inst_id if d.get("source") else None,
        }


class Operator(Unit):
    """Player operator / deployable unit."""

    def __init__(self, char_id, attributes, row=0, col=0, direction=1,
                 deploy_tick=0, skills=None):
        super().__init__(attributes=attributes, row=row, col=col)
        self.side = 1
        self.char_id = char_id
        self.direction = direction          # 0 up 1 right 2 down 3 left
        self.deploy_tick = deploy_tick
        self.deploy_animation_ticks = 15    # 0.5s 不可选中
        self.skills = skills or []          # list of dicts from skills.json
        self.skill_controller = None        # OperatorSkillController (optional)
        self.talent_system = None           # TalentSystem (optional)
        self.attack_timer = 0.0
        self._pending_attack = None         # windup: damage at hit frame
        self.hit_frame_ratio = 0.5          # OnAttack / anim duration
        self.range_shape = []               # list of (dr, dc) offsets
        self.position = 1                  # 1 melee / 2 ranged (deploy)
        self.cost = float(attributes.get("cost") or 0)
        self.respawn_time = float(attributes.get("respawnTime") or 70.0)
        self.blocked_enemies = []
        self.retreating = False
        self._reborn_state = False   # \u70db\u714c T2 \u7edd\u5904\u91cd\u71c3 downed state

    def add_blockee(self, enemy):
        if enemy not in self.blocked_enemies:
            self.blocked_enemies.append(enemy)

    def remove_blockee(self, enemy):
        if enemy in self.blocked_enemies:
            self.blocked_enemies.remove(enemy)

    def in_deploy_anim(self, tick):
        return tick - self.deploy_tick < self.deploy_animation_ticks

    def to_dict(self):
        d = self.base_to_dict()
        d.update({
            "charId": self.char_id,
            "direction": self.direction,
            "blockedEnemies": [e.inst_id for e in self.blocked_enemies],
            "attackTimer": round(self.attack_timer, 4),
            "cost": self.cost,
            "hitFrameRatio": round(self.hit_frame_ratio, 4),
            "pendingAttack": ({
                "target": self._pending_attack["target"].inst_id,
                "remaining": self._pending_attack["remaining"],
                "ranged": bool(self._pending_attack.get("ranged")),
            } if self._pending_attack else None),
            "talents": self.talent_system.to_dict()
            if self.talent_system else [],
            "trait": self.trait_system.to_dict()
            if getattr(self, "trait_system", None) is not None else None,
            "profession": getattr(self, "profession", None),
            "subProfession": getattr(self, "sub_profession_id", None),
            "doll": bool(getattr(self, "_doll_state", False)),
            "funnelDrones": [d.to_dict() for d in
                             getattr(self, "_funnel_drones", [])],
            "skills": self.skill_controller.skill_states()
            if self.skill_controller else [],
            "alias": getattr(self, "alias", None),
            "reborn": bool(getattr(self, "_reborn_state", False)),
            "visionLost": bool(getattr(self, "_vision_lost", False)),
            "module": getattr(self, "module", None),
            "trust": int(getattr(self, "trust", 0) or 0),
        })
        sc = self.skill_controller
        act = getattr(sc, "active", None) if sc is not None else None
        if act is not None:
            d["activeSkill"] = {
                "skillId": getattr(getattr(act, "skill", None),
                                   "skill_id", None),
                "remaining": round(getattr(act, "remaining", 0.0), 3),
                "ammo": int(getattr(act, "ammo", 0) or 0),
                "buffs": [b.get("key") for b in
                          (getattr(act, "buffs", None) or [])],
            }
        else:
            d["activeSkill"] = None
        return d


class FunnelDrone:
    """\u9a6b\u68b0\u672f\u5e08 (funnel) floating unit.

    Not a Unit: it cannot be damaged/blocked and follows its owner. It
    attacks enemies (incl. flying) with magical damage ramping from
    init x ATK by +delta per consecutive hit on the same target, capped
    at max (PRTS 20% -> +15% -> 110%). Stacks reset when the target
    changes or dies, or when the owner is redeployed.
    """

    def __init__(self, owner, attack_timer=0.0):
        self.inst_id = next_inst_id()
        self.owner = owner
        self.target = None
        self.stacks = 0          # increments after each fired attack
        self.attack_timer = attack_timer
        self.destruct_layers = 1  # Goldenglow talent 1 self-destruct stack

    def to_dict(self):
        return {
            "instId": self.inst_id,
            "owner": self.owner.inst_id if self.owner else None,
            "target": self.target.inst_id if self.target else None,
            "stacks": self.stacks,
            "destructLayers": self.destruct_layers,
            "attackTimer": round(self.attack_timer, 4),
        }


class Token(Unit):
    """Neutral devices / summons (Lancet-2, obstacles, mines, summons)."""

    def __init__(self, token_id, attributes, row=0, col=0, owner=None,
                 is_deployable=True, skill_ref=None):
        super().__init__(attributes=attributes, row=row, col=col)
        self.side = 1
        self.token_id = token_id
        self.owner = owner
        self.is_deployable = is_deployable
        self.skill_ref = skill_ref
        self.attack_timer = 0.0
        self._pending_attack = None         # windup: damage at hit frame
        self.range_shape = []
        self.position = 1                  # 1 melee / 2 ranged (deploy)
        self.hit_frame_ratio = 0.5
        self.blocked_enemies = []
        self.respawn_time = 35.0
        self.expire_tick = None          # optional lifetime (Ray sandbeast)
        self._recover_bullets = 0        # Ray S2: bullets refunded on retreat

    def add_blockee(self, enemy):
        if enemy not in self.blocked_enemies:
            self.blocked_enemies.append(enemy)

    def remove_blockee(self, enemy):
        if enemy in self.blocked_enemies:
            self.blocked_enemies.remove(enemy)

    def to_dict(self):
        d = self.base_to_dict()
        d.update({
            "tokenId": self.token_id,
            "owner": self.owner.inst_id if self.owner else None,
            "respawnTime": self.respawn_time,
            "expireTick": self.expire_tick,
            "hitFrameRatio": round(self.hit_frame_ratio, 4),
            "pendingAttack": ({
                "target": self._pending_attack["target"].inst_id,
                "remaining": self._pending_attack["remaining"],
                "ranged": bool(self._pending_attack.get("ranged")),
            } if self._pending_attack else None),
            "alias": getattr(self, "alias", None),
        })
        return d
