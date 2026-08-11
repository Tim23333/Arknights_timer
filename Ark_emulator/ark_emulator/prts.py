"""Mainline-15 PRTS script manager (Mainline15PrtsManager, dump.cs:10402).

Stage 15-18 drives a scripted "PRTS" enemy (enemy_1564_mpprts) through a
priority queue of actions.  Every action is parsed into a chain of
sub-actions (PrtsSubActionType, dump.cs:402612+):

  MOVE_AND_SPAWNENEMY   -> MOVE_TO_DRAG -> SPAWN -> FOLLOW_BOSS
  MOVE_AND_DRAG_SOURCE  -> MOVE_TO_DRAG -> DRAG -> FOLLOW_BOSS
  MOVE_AND_CREATEBUFF   -> MOVE_TO_CREATE_BUFF -> CREATE_BUFF -> FOLLOW_BOSS

The sub-action sequencing is inferred from the dump.cs signatures plus the
node data observed in data_buff_templates (Main15InsertPrtsAction /
Main15TryNextPrtsAction / Main15FilterPrtsLastSubAction); 【推】 marks the
inferred parts that are not directly visible in the shipped data.
"""

import heapq
from collections import deque


PRTS_ENEMY_KEY = "enemy_1564_mpprts"

# PrtsActionType (dump.cs:402606)
ACT_MOVE_AND_SPAWNENEMY = "MOVE_AND_SPAWNENEMY"
ACT_MOVE_AND_CREATEBUFF = "MOVE_AND_CREATEBUFF"
ACT_MOVE_AND_DRAG_SOURCE = "MOVE_AND_DRAG_SOURCE"
ACTION_TYPES = {
    ACT_MOVE_AND_SPAWNENEMY: 0,
    ACT_MOVE_AND_CREATEBUFF: 1,
    ACT_MOVE_AND_DRAG_SOURCE: 2,
}

# PrtsSubActionType (dump.cs:402612+)
SUB_MOVE_TO_ORIGIN = "MOVE_TO_ORIGIN"
SUB_MOVE_TO_DRAG = "MOVE_TO_DRAG"
SUB_DRAG = "DRAG"
SUB_SPAWN = "SPAWN"
SUB_MOVE_TO_CREATE_BUFF = "MOVE_TO_CREATE_BUFF"
SUB_CREATE_BUFF = "CREATE_BUFF"
SUB_FOLLOW_BOSS = "FOLLOW_BOSS"


def _resolve_enemy_key(battle, value, bb=None, owner=None):
    """Resolve a PRTS spawn enemy key.  Node values such as ``enemy_key``
    are blackboard variable names (the buff carries the concrete key, e.g.
    the dragged enemy); known database keys are used as-is."""
    if not value:
        return None
    if not isinstance(value, str):
        return None
    store = getattr(battle, "store", None)
    # ``enemy_key`` without a blackboard value names the buff owner itself:
    # the drag-on-locate template ([g]mainline15_drag_enemy_on_locate) is
    # carried by the dragged enemy and re-spawns that enemy type when it is
    # located at the drag destination.
    if value == "enemy_key" and owner is not None:
        k = (getattr(owner, "enemy_key", None) or
             getattr(owner, "token_id", None))
        if k:
            return str(k)
    if store is not None:
        try:
            resolved = store.resolve_enemy_key(value)
            if resolved in (store.bundle.get("enemyRoster") or {}) or \
                    resolved in store.enemy_database:
                return resolved
        except Exception:
            pass
    if bb:
        got = bb.get(value)
        if got and got != value:
            if store is not None:
                try:
                    resolved = store.resolve_enemy_key(got)
                    if resolved in (store.bundle.get("enemyRoster") or {}) \
                            or resolved in store.enemy_database:
                        return resolved
                except Exception:
                    pass
            return got
    return value


class PrtsManager:
    """Priority-queue PRTS script engine (Mainline15PrtsManager)."""

    def __init__(self, battle):
        self.battle = battle
        self.spawn_check_dist = 0.05
        self.config = None
        self.prts_enemy_key = PRTS_ENEMY_KEY
        self._config_tried = False
        self.pending = []            # heap: (-priority, seq, action)
        self._seq = 0
        self.sub_queue = deque()     # PrtsSubAction dicts in doing
        self.prts_enemy = None
        self.dragged = None
        self.drag_offset = (0.0, 0.0)
        self.last_sub_action = None
        self.last_main_action = None
        self.force_battle_speed = False
        self.active = False
        self.started_count = 0
        self.finished_count = 0
        self.spawn_count = 0
        self.following_boss = False

    def _ensure_config(self):
        """Lazily load the env-system config (env_v060_mainline15_prtsCtrl).
        The battle populates ``env_systems`` from level runes after the
        manager is constructed, so the lookup runs on first use."""
        if self.config is not None or self._config_tried:
            return
        self._config_tried = True
        try:
            for es in (getattr(self.battle, "env_systems", None) or []):
                cfg = self.battle.store.env_system_config(es.get("key"))
                if cfg:
                    self.config = cfg
                    self.prts_enemy_key = cfg.get("_prtsEnemyKey") or \
                        PRTS_ENEMY_KEY
                    self.spawn_check_dist = float(
                        cfg.get("_prtsSpawnCheckDistance")
                        or self.spawn_check_dist)
                    break
        except Exception:
            pass

    # ------------------------------------------------------------------
    # action queue
    # ------------------------------------------------------------------
    def _push_action(self, action):
        action["_seq"] = self._seq
        self._seq += 1
        heapq.heappush(
            self.pending,
            (-int(action.get("priority") or 0), action["_seq"], action))
        self.active = True

    def TryMoveAndCreateBuff(self, priority, target_pos, buff_data,
                             blackboard=None):
        """Insert a MOVE_AND_CREATEBUFF action (dump.cs:7EA3F0)."""
        if target_pos is None:
            return False
        self._push_action({
            "priority": int(priority or 0),
            "actionType": ACT_MOVE_AND_CREATEBUFF,
            "targetPos": (float(target_pos[0]), float(target_pos[1])),
            "buffData": buff_data,
            "blackboard": dict(blackboard or {}),
        })
        return True

    def TryMoveAndDragSource(self, priority, source, target_pos,
                             buff_data=None, blackboard=None):
        """Insert a MOVE_AND_DRAG_SOURCE action (dump.cs:7EA5A0)."""
        if source is None or getattr(source, "dead", False):
            return False
        self._push_action({
            "priority": int(priority or 0),
            "actionType": ACT_MOVE_AND_DRAG_SOURCE,
            "source": source,
            "targetPos": (float(target_pos[0]), float(target_pos[1])),
            "buffData": buff_data,
            "blackboard": dict(blackboard or {}),
        })
        return True

    def TrySpawnEnemyOnMostSurround(self, target_tile, priority,
                                    enemy_key_fly=None, enemy_key_hl=None,
                                    enemy_key_ll=None):
        """Insert a MOVE_AND_SPAWNENEMY action at a target tile
        (dump.cs:7EB070)."""
        if target_tile is None:
            return False
        r, c = self.battle.map.rc(int(target_tile.index))
        self._push_action({
            "priority": int(priority or 0),
            "actionType": ACT_MOVE_AND_SPAWNENEMY,
            "targetTile": (r, c),
            "targetPos": (float(c), float(r)),
            "enemyKeyFly": enemy_key_fly,
            "enemyKeyHL": enemy_key_hl,
            "enemyKeyLL": enemy_key_ll,
        })
        return True

    def insert_from_node(self, owner, node, ctx):
        """Main15InsertPrtsAction Execute (dump.cs:105B8E0): parse the
        node fields and push the corresponding action."""
        battle = self.battle
        at = node.get("_actionType") or ACT_MOVE_AND_SPAWNENEMY
        priority = node.get("_priority") or 0
        bb = dict(ctx.get("bb") or {})
        source = ctx.get("source") or owner
        if at == ACT_MOVE_AND_DRAG_SOURCE:
            if source is None or getattr(source, "dead", False):
                return False
            target_pos = (float(source.pos_x), float(source.pos_y))
            return self.TryMoveAndDragSource(
                priority, source, target_pos,
                node.get("_buffData"), bb)
        tile = self._node_target_tile(node, source)
        if tile is None:
            return False
        if at == ACT_MOVE_AND_CREATEBUFF:
            r, c = self.battle.map.rc(int(tile.index))
            return self.TryMoveAndCreateBuff(
                priority, (float(c), float(r)),
                node.get("_buffData"), bb)
        # MOVE_AND_SPAWNENEMY
        fly = _resolve_enemy_key(battle, node.get("_enemyKeyFly"), bb,
                                 owner=source)
        high = _resolve_enemy_key(battle, node.get("_enemyKeyHL"), bb,
                                  owner=source)
        low = _resolve_enemy_key(battle, node.get("_enemyKeyLL"), bb,
                                 owner=source)
        return self.TrySpawnEnemyOnMostSurround(
            tile, priority, fly, high, low)

    def _node_target_tile(self, node, source):
        """Choose the action's target tile: most-character surround,
        most-enemy surround, the source's tile, or the node's explicit
        position."""
        b = self.battle
        if node.get("_chooseMostCharSurroud"):
            return self.FindMostCharacterSurroundTile()
        if node.get("_chooseMostEnemySurroud"):
            return self.FindMostEnemySurroundTile()
        if node.get("_chooseSource"):
            if source is None or getattr(source, "dead", False):
                return None
            try:
                return b.map.tile(int(source.row), int(source.col))
            except Exception:
                return None
        pos = node.get("_targetPos") or node.get("targetPos")
        if pos is None:
            return None
        try:
            return b.map.tile(int(pos.get("row", pos.get("y", 0))),
                              int(pos.get("col", pos.get("x", 0))))
        except Exception:
            return None

    # ------------------------------------------------------------------
    # surround-count tile selection (dump.cs:7E9460 / 7E9870)
    # ------------------------------------------------------------------
    def _surround_counts(self, units):
        m = self.battle.map
        counts = {}
        for u in units:
            if getattr(u, "dead", False):
                continue
            r = int(getattr(u, "row", 0) or 0)
            c = int(getattr(u, "col", 0) or 0)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    if m.idx(r + dr, c + dc) < 0:
                        continue
                    counts[(r + dr, c + dc)] = \
                        counts.get((r + dr, c + dc), 0) + 1
        return counts

    def _best_surround_tile(self, counts):
        """Pick the tile with the max surround count; ties resolve to the
        lowest row/col (deterministic).  Start/end route tiles are
        excluded unless nothing else qualifies."""
        m = self.battle.map
        cand = []
        for (r, c), n in counts.items():
            if m.idx(r, c) < 0:
                continue
            t = m.tile(r, c)
            if t is None or t.tile_key in ("tile_forbidden", "tile_wall",
                                           "tile_start", "tile_end"):
                continue
            if self._is_start_end(r, c):
                continue
            cand.append((n, r, c))
        if not cand:
            return None
        n, r, c = max(cand, key=lambda x: (x[0], -x[1], -x[2]))
        return m.tile(r, c)

    def FindMostCharacterSurroundTile(self):
        return self._best_surround_tile(
            self._surround_counts(self.battle.get_operators()))

    def FindMostEnemySurroundTile(self):
        return self._best_surround_tile(
            self._surround_counts(self.battle.get_enemies()))

    def _is_start_end(self, r, c):
        for route in (self.battle.routes or []):
            if not isinstance(route, dict):
                continue
            st = route.get("startPosition") or {}
            if int(st.get("row", -1)) == r and int(st.get("col", -1)) == c:
                return True
            cps = route.get("checkpoints") or []
            if cps:
                last = cps[-1]
                if int(last.get("position", {}).get("row", -1)) == r and \
                        int(last.get("position", {}).get("col", -1)) == c:
                    return True
        return False

    # ------------------------------------------------------------------
    # pipeline: pick -> parse -> sub-actions
    # ------------------------------------------------------------------
    def TryPickNextAction(self):
        """Pop the highest-priority pending action and parse it into
        sub-actions (dump.cs:7EAB40)."""
        if not self.pending:
            return False
        _prio, _seq, action = heapq.heappop(self.pending)
        self.last_main_action = action.get("actionType")
        self.active = True
        self.started_count += 1
        self._emit("prts_action_start", {
            "action": self.last_main_action,
            "priority": action.get("priority"),
            "key": action.get("key"),
        })
        for sub in self._parse_action(action):
            self.sub_queue.append(sub)
        cur = self._current()
        if cur is not None:
            self._start_sub(cur)
        return True

    def _parse_action(self, action):
        at = action.get("actionType")
        if at == ACT_MOVE_AND_SPAWNENEMY:
            tile = action.get("targetTile")
            return [
                {"type": SUB_MOVE_TO_DRAG, "mainActionType": at,
                 "targetPos": action.get("targetPos"),
                 "checkDist": self.spawn_check_dist},
                {"type": SUB_SPAWN, "mainActionType": at,
                 "targetTile": tile,
                 "enemyKey": self._choose_spawn_key(action, tile)},
                {"type": SUB_FOLLOW_BOSS, "mainActionType": at},
            ]
        if at == ACT_MOVE_AND_DRAG_SOURCE:
            src = action.get("source")
            src_pos = (float(src.pos_x), float(src.pos_y)) \
                if src is not None else action.get("targetPos")
            return [
                {"type": SUB_MOVE_TO_DRAG, "mainActionType": at,
                 "targetPos": src_pos,
                 "checkDist": self.spawn_check_dist},
                {"type": SUB_DRAG, "mainActionType": at,
                 "source": src,
                 "targetPos": action.get("targetPos"),
                 "buffData": action.get("buffData"),
                 "blackboard": action.get("blackboard")},
                {"type": SUB_FOLLOW_BOSS, "mainActionType": at},
            ]
        return [
            {"type": SUB_MOVE_TO_CREATE_BUFF, "mainActionType": at,
             "targetPos": action.get("targetPos"),
             "checkDist": self.spawn_check_dist},
            {"type": SUB_CREATE_BUFF, "mainActionType": at,
             "buffData": action.get("buffData"),
             "blackboard": action.get("blackboard"),
             "source": action.get("source")},
            {"type": SUB_FOLLOW_BOSS, "mainActionType": at},
        ]

    def _choose_spawn_key(self, action, tile):
        fly = action.get("enemyKeyFly")
        high = action.get("enemyKeyHL")
        low = action.get("enemyKeyLL")
        resolved = self._config_spawn_key(tile)
        if resolved:
            return resolved
        if fly and str(fly) not in ("enemy_fly", "enemy_key"):
            return fly
        if tile is not None and self._tile_is_high(tile):
            return high or low
        return low or high

    def _config_spawn_key(self, tile):
        """Resolve the fly/highland/lowland placeholder keys through the
        env-system trap pairs by the target tile height.  When the tile
        carries a pre-placed trap the matching pair is used; otherwise the
        first pair of that height."""
        self._ensure_config()
        cfg = self.config or {}
        pairs = cfg.get("_enemyTrapKeyPairs") or []
        if not pairs or tile is None:
            return None
        height = self._tile_height(tile)
        cands = [p for p in pairs
                 if int(p.get("tileHeightType", 0)) == height]
        if not cands:
            cands = pairs
        trap_at = self._trap_on_tile(tile)
        for p in cands:
            if p.get("trap") == trap_at:
                return p.get("enemyKey")
        return cands[0].get("enemyKey")

    def _tile_height(self, tile):
        h = getattr(tile, "height_type", None)
        if h is None:
            return 0
        s = str(h).upper()
        if s in ("1", "HIGHLAND", "HIGH"):
            return 1
        if s in ("2", "FLY", "FLYING"):
            return 2
        return 0

    def _trap_on_tile(self, tile):
        try:
            r, c = self.battle.map.rc(int(tile.index))
            for t in (self.battle.predefines.get("tokenInsts") or []):
                if isinstance(t, dict) and \
                        int(t.get("row", -1)) == r and \
                        int(t.get("col", -1)) == c:
                    return t.get("characterKey") or t.get("alias")
        except Exception:
            pass
        return None

    def _tile_is_high(self, tile):
        try:
            return int(getattr(tile, "buildable_type",
                               getattr(tile, "buildableType", 1)) or 1) == 2
        except Exception:
            return False

    # ------------------------------------------------------------------
    # sub-action execution
    # ------------------------------------------------------------------
    def _current(self):
        return self.sub_queue[0] if self.sub_queue else None

    def _start_sub(self, sub):
        self.last_sub_action = sub["type"]
        st = sub["type"]
        if st in (SUB_MOVE_TO_ORIGIN, SUB_MOVE_TO_DRAG,
                  SUB_MOVE_TO_CREATE_BUFF):
            self._set_prts_target(sub.get("targetPos"),
                                  sub.get("checkDist"))
        elif st == SUB_DRAG:
            self._begin_drag(sub)
        elif st == SUB_SPAWN:
            self._do_spawn(sub)
        elif st == SUB_CREATE_BUFF:
            self._do_create_buff(sub)
        elif st == SUB_FOLLOW_BOSS:
            self.following_boss = True
        self._emit("prts_sub_start",
                   {"sub": st, "action": sub.get("mainActionType")})

    def _set_prts_target(self, pos, check_dist=None):
        e = self.prts_enemy
        if e is None or getattr(e, "dead", False) or pos is None:
            return
        e._trace_pos = (float(pos[0]), float(pos[1]))
        e._trace_reach = max(0.0,
                             float(check_dist or self.spawn_check_dist))

    def _begin_drag(self, sub):
        src = sub.get("source")
        if src is None or getattr(src, "dead", False):
            return
        self.dragged = src
        src._prts_dragged = True
        if self.prts_enemy is not None:
            self.drag_offset = (
                float(src.pos_x) - float(self.prts_enemy.pos_x),
                float(src.pos_y) - float(self.prts_enemy.pos_y))
        self._set_prts_target(sub.get("targetPos"), 0.2)
        self._emit("prts_drag_start", {
            "source": getattr(src, "inst_id", None),
            "target": sub.get("targetPos"),
        })

    def _end_drag(self, sub):
        d = self.dragged
        if d is not None:
            d._prts_dragged = False
            bd = sub.get("buffData")
            if bd:
                self._apply_buff_to(d, bd, sub.get("blackboard") or {})
            self._emit("prts_drag_end", {
                "source": getattr(d, "inst_id", None)})
        self.dragged = None
        self.drag_offset = (0.0, 0.0)

    def _do_spawn(self, sub):
        b = self.battle
        key = sub.get("enemyKey")
        tile = sub.get("targetTile")
        if not key or tile is None:
            return
        r, c = int(tile[0]), int(tile[1])
        if not self._spawn_tile_valid(r, c):
            b.emit(b.tick, "prts_spawn_failed",
                   {"key": key, "row": r, "col": c, "reason": "tile"})
            return
        try:
            e = b.spawn_enemy_directive(key, r, c, route_index=0)
        except Exception as ex:  # noqa: BLE001
            b.emit(b.tick, "prts_spawn_failed",
                   {"key": key, "row": r, "col": c,
                    "error": repr(ex)[:120]})
            return
        self.spawn_count += 1
        b.emit(b.tick, "prts_spawn_enemy", {
            "key": key, "row": r, "col": c,
            "instId": getattr(e, "inst_id", None),
        })

    def _spawn_tile_valid(self, r, c):
        m = self.battle.map
        if m.idx(r, c) < 0:
            return False
        t = m.tile(r, c)
        if t is None or t.tile_key in ("tile_forbidden", "tile_wall",
                                       "tile_start", "tile_end"):
            return False
        for e in self.battle.get_enemies():
            if e is self.prts_enemy:
                continue          # the PRTS itself stands on the tile
            if not getattr(e, "dead", False) and \
                    (int(e.row), int(e.col)) == (r, c):
                return False
        return True

    def _do_create_buff(self, sub):
        b = self.battle
        bd = sub.get("buffData")
        if not bd:
            return
        target = sub.get("source") or self.prts_enemy
        if target is None or getattr(target, "dead", False):
            return
        self._apply_buff_to(target, bd, sub.get("blackboard") or {})
        self._emit("prts_create_buff", {
            "buff": bd.get("buffKey"),
            "unit": getattr(target, "inst_id", None),
        })

    def _apply_buff_to(self, unit, buff_data, bb):
        try:
            from .buff_templates import materialise_buff
            entry = materialise_buff(self.battle, unit, buff_data, bb, unit)
            if entry and entry.get("key"):
                self.battle.add_buff(unit, entry)
                return True
        except Exception:
            return False
        return False

    def _check_current(self):
        sub = self._current()
        if sub is None:
            return False
        st = sub["type"]
        if st in (SUB_MOVE_TO_ORIGIN, SUB_MOVE_TO_DRAG,
                  SUB_MOVE_TO_CREATE_BUFF):
            e = self.prts_enemy
            if e is None or getattr(e, "dead", False):
                return True
            return getattr(e, "_trace_pos", None) is None
        if st == SUB_DRAG:
            e = self.prts_enemy
            if e is None or getattr(e, "dead", False):
                return True
            return getattr(e, "_trace_pos", None) is None
        # SPAWN / CREATE_BUFF / FOLLOW_BOSS complete in the same tick
        return True

    def _finish_current(self):
        sub = self.sub_queue.popleft()
        st = sub["type"]
        if st == SUB_DRAG:
            self._end_drag(sub)
        elif st == SUB_FOLLOW_BOSS:
            self.following_boss = False
        self._emit("prts_sub_finish",
                   {"sub": st, "action": sub.get("mainActionType")})
        if not self.sub_queue:
            self._on_action_finish()

    def _on_action_finish(self):
        self.finished_count += 1
        cfg = self.config or {}
        buff_key = cfg.get("_buffToPrtsWhenActionFinish")
        if buff_key and self.prts_enemy is not None and \
                not getattr(self.prts_enemy, "dead", False):
            try:
                from .buff_templates import materialise_buff
                entry = materialise_buff(
                    self.battle, self.prts_enemy,
                    {"buffKey": buff_key, "templateKey": buff_key},
                    {}, self.prts_enemy)
                if entry:
                    self.battle.add_buff(self.prts_enemy, entry)
            except Exception:
                pass
        self._emit("prts_action_finish", {
            "action": self.last_main_action,
            "count": self.finished_count,
        })

    def TryNextSubAction(self, do_next_when_success=True, force_next=False):
        """Advance the sub-action pipeline (dump.cs:7EA750).  ``force_next``
        finishes the current sub-action immediately; otherwise the current
        sub-action must report success.  Returns whether a sub/action is in
        flight afterwards."""
        if self._current() is not None and \
                (force_next or self._check_current()):
            self._finish_current()
            nxt = self._current()
            if nxt is not None:
                self._start_sub(nxt)
                return True
            return self.TryPickNextAction()
        if self._current() is None:
            return self.TryPickNextAction()
        return False

    def SkipPrtsAction(self, action_type):
        """Skip the current action (or all pending actions of a type)."""
        if self._current() is not None and \
                self.last_main_action == action_type:
            while self.sub_queue:
                self.sub_queue.popleft()
            self._on_action_finish()
            return True
        before = len(self.pending)
        self.pending = [h for h in self.pending
                        if h[2].get("actionType") != action_type]
        heapq.heapify(self.pending)
        return len(self.pending) != before

    def FilterCurrenSubAction(self, sub_action_type):
        return self.last_sub_action == sub_action_type

    def FilterCurrentAction(self, action_type):
        return self.last_main_action == action_type

    def CreateBuffToPrts(self, buff_data, blackboard=None):
        """Main15CreateBuffToPrts: apply a buff to the PRTS enemy."""
        if self.prts_enemy is None or not buff_data:
            return False
        return self._apply_buff_to(self.prts_enemy, buff_data,
                                   dict(blackboard or {}))

    def SetForceBattleSpeed(self, enable):
        self.force_battle_speed = bool(enable)
        try:
            self.battle._main15_force_speed = self.force_battle_speed
        except Exception:
            pass
        self._emit("main15_force_speed", {"enable": self.force_battle_speed})

    # ------------------------------------------------------------------
    # binding / per-tick
    # ------------------------------------------------------------------
    def bind_enemy(self, enemy):
        if enemy is None:
            return
        self._ensure_config()
        if (enemy.enemy_key or "").split("#", 1)[0] != self.prts_enemy_key:
            return
        if self.prts_enemy is not None and self.prts_enemy is not enemy:
            return                      # keep the first bound driver
        self.prts_enemy = enemy
        self.active = True
        enemy._prts_bound = True
        self._emit("prts_bound", {"instId": enemy.inst_id})

    def on_tick(self, dt):
        b = self.battle
        if not self.active and not self.pending and not self.sub_queue:
            return
        if self.prts_enemy is None or getattr(self.prts_enemy, "dead", False):
            for e in b.get_enemies():
                if not getattr(e, "dead", False) and \
                        (e.enemy_key or "").split("#", 1)[0] == \
                        self.prts_enemy_key:
                    self.bind_enemy(e)
                    break
            else:
                self.prts_enemy = None
                self.dragged = None
                if not self.pending and not self.sub_queue:
                    return
        if self.dragged is not None:
            self._update_drag(dt)
        guard = 0
        while self._current() is not None and guard < 16:
            guard += 1
            if not self._check_current():
                break
            self._finish_current()
            nxt = self._current()
            if nxt is not None:
                self._start_sub(nxt)
        if not self.sub_queue:
            self.TryPickNextAction()

    def _update_drag(self, dt):
        e = self.prts_enemy
        d = self.dragged
        if e is None or d is None or getattr(d, "dead", False):
            return
        d.pos_x = float(e.pos_x) + self.drag_offset[0]
        d.pos_y = float(e.pos_y) + self.drag_offset[1]
        try:
            d._sync_tile()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _emit(self, event, payload):
        try:
            self.battle.emit(self.battle.tick, event, payload)
        except Exception:
            pass

    def to_dict(self):
        self._ensure_config()
        return {
            "active": self.active,
            "prtsEnemy": getattr(self.prts_enemy, "inst_id", None),
            "forceBattleSpeed": self.force_battle_speed,
            "pending": [{
                "priority": h[2].get("priority"),
                "actionType": h[2].get("actionType"),
                "key": h[2].get("key"),
            } for h in sorted(self.pending,
                              key=lambda h: (h[0], h[1]))],
            "subQueue": [s.get("type") for s in self.sub_queue],
            "lastSubAction": self.last_sub_action,
            "lastMainAction": self.last_main_action,
            "dragged": getattr(self.dragged, "inst_id", None),
            "started": self.started_count,
            "finished": self.finished_count,
            "spawned": self.spawn_count,
        }
