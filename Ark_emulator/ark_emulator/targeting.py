"""Target selection and hate system (MECHANICS §5, docs 07).

Priority chain: blocked -> special priority -> second priority -> hate ->
earliest creation. Hate formulas:
  enemy-side (targets operators):
      hate = 1000 * tauntLevel - pathDistance
  operator-side (targets enemies):
      hate = 10000000 * tauntLevel + clamp(createTime,0,10000)*1000 + sameFrameDeploys
"""

import random

# Ability target-search cadence (dump.cs):
#   SelectorTrigger.SEARCH_TARGET_TICK = 3  (dump.cs:437169) - attack/skill
#     target selectors re-run at most once every 3 logic ticks (0.1s at
#     the 30Hz rough-logic rate), or every _overrideSearchTargetTick when
#     the prefab sets it (>=0); Search(force) bypasses the gate.
#   TileTrigger.SEARCH_TARGET_TICK = 5     (dump.cs:437439) - tile selectors.
SEARCH_TARGET_TICK = 3
TILE_SEARCH_TARGET_TICK = 5


def search_gate(unit, battle, scan, force=False):
    """Run ``scan`` under the ability target-search gate and cache the
    result on the unit (``_ai_target`` / ``_search_tick``).  Between two
    searches (SEARCH_TARGET_TICK ticks) the previous target is kept while
    it is still alive; ``force`` (Search(force)) bypasses the gate.  The
    unit may set ``_search_period`` to override the cadence."""
    last = getattr(unit, "_search_tick", None)
    cur = getattr(unit, "_ai_target", None)
    period = int(getattr(unit, "_search_period",
                         SEARCH_TARGET_TICK) or SEARCH_TARGET_TICK)
    if not force and last is not None and battle.tick - last < period:
        if cur is not None and not getattr(cur, "dead", False):
            return cur
    new = scan()
    unit._ai_target = new
    unit._search_tick = battle.tick
    return new


# Element-bar buff keys and the ep_type -> key mapping (BuffSystem.EP_KEYS).
_EP_BUFF_KEYS = ("ep_neural", "ep_water", "ep_fire", "ep_dark")
_EP_TYPE_TO_KEY = {0: "ep_neural", 1: "ep_water", 2: "ep_fire", 3: "ep_dark"}


def _unit_ep(unit, battle=None):
    """Element damage per EP type (full-bar model: maxEp - remaining;
    no record = full bar = 0 damage)."""
    out = {}
    try:
        mx = battle.buffs.ep_max(unit) if battle is not None else 1000.0
    except Exception:
        mx = 1000.0
    for b in getattr(unit, "buffs", None) or []:
        if b.get("key") in _EP_BUFF_KEYS:
            out[b["key"]] = max(0.0, mx - float(b.get("value") or 0.0))
    return out


def _unit_has_ep(unit, battle=None):
    return any(v > 0.0 for v in _unit_ep(unit, battle).values())


def _unit_ep_severity(unit, battle=None):
    """Most severe element bar: the unit current (last damaged) element,
    else the max damage across all bars."""
    vals = _unit_ep(unit, battle)
    if not vals:
        return 0.0
    last = getattr(unit, "_last_ep_type", None)
    key = _EP_TYPE_TO_KEY.get(last)
    if key and vals.get(key, 0.0) > 0.0:
        return vals[key]
    return max(vals.values())


# Wandermedic (行医) skills whose text says "优先治疗元素损伤最严重的
# 目标" / "以元素损伤最严重的 N 名干员为目标".  PRTS (蜜莓/桑葚/哈洛德
# 分支备注) documents that the game implements this phrase as 元素值最低
# first (NOT most severe first), then lowest HP ratio:
#   - 蜜莓 S1 精神护理 / S2 振奋
#   - 桑葚 S1 治愈云雾 / S2 安全区域
#   - 哈洛德 S2 重症优先
_WM_EP_PRIORITY_SKILLS = frozenset({
    "skchr_glider_1", "skchr_glider_2",
    "skchr_mberry_1", "skchr_mberry_2",
    "skchr_harold_2",
})


def _active_skill_id(op):
    """Skill id of the operator's currently running skill ("" when idle)."""
    active = getattr(getattr(op, "skill_controller", None), "active", None)
    return getattr(getattr(active, "skill", None), "skill_id", "") or ""


def _wm_ep_metric(unit, battle=None):
    """PRTS "当前损伤元素的元素值最低": the LOWEST value among the unit's
    currently-damaged (nonzero) element bars; 0 when the unit is clean.
    Lower is prioritized first (both for normal attacks and for the
    "优先治疗元素损伤最严重的目标" skills - the game's quirk)."""
    vals = [v for v in _unit_ep(unit, battle).values() if v > 0.0]
    return min(vals) if vals else 0.0


def _wm_ep_full(unit, battle):
    """PRTS "元素值已满": any element bar at/beyond the burst threshold."""
    try:
        mx = battle.buffs.ep_max(unit)
    except Exception:
        mx = 1000.0
    if not mx:
        return False
    return any(v >= float(mx) - 1e-6 for v in _unit_ep(unit, battle).values())


def _unit_ep_max(unit, battle=None):
    """The displayed element bar value: the LARGEST accumulated value across
    all element types.  Multiple element types coexist on one unit; the game
    only shows the most severe one (PRTS CH-6/CH-7), so all
    "元素损伤累计" style conditions judge against this value."""
    vals = _unit_ep(unit, battle).values()
    return max(vals) if vals else 0.0


def _unit_ep_over_half(unit, battle):
    """PRTS 哈洛德 "元素损伤累计超过一半": the unit's displayed element
    bar (largest accumulated type) is strictly above half its burst
    threshold (maxEp / 2, default 1000 -> >500)."""
    try:
        mx = battle.buffs.ep_max(unit)
    except Exception:
        mx = 1000.0
    if not mx:
        return False
    return _unit_ep_max(unit, battle) > float(mx) * 0.5 + 1e-9


class HateSystem:
    """Computes hate and orders candidate targets."""

    def __init__(self, battle):
        self.battle = battle

    # ---- hate values ----
    def operator_hate(self, op):
        """Hate value of an operator as seen by enemies."""
        taunt = float(op.attributes.get("tauntLevel") or 0)
        create_t = min(max(op.deploy_tick / 30.0, 0.0), 10000.0)
        return 10000000.0 * taunt + create_t * 1000.0

    def enemy_hate(self, enemy):
        """Hate value of an enemy as seen by operators (path distance)."""
        taunt = float(enemy.attributes.get("tauntLevel") or 0)
        dist = enemy.dist_to_final() if hasattr(enemy, "dist_to_final") else 0.0
        return 1000.0 * taunt - dist

    # ---- filters ----
    def apply_filter(self, candidates, filter_id, source=None):
        """Apply a postFilter (id 0-78). Unknown filters fall back to ALL."""
        candidates = list(candidates)
        f = int(filter_id) if filter_id is not None else 0
        if f == 0:
            return candidates                                    # ALL
        if f == 4:
            return sorted(candidates, key=self.enemy_hate, reverse=True)
        if f == 1:
            return sorted(candidates, key=lambda e: e.dist_to_final()
                          if hasattr(e, "dist_to_final") else 0)
        if f in (2, 3):
            rev = (f == 3)
            return sorted(candidates,
                          key=lambda e: (e.hp / e.max_hp if e.max_hp else 1),
                          reverse=rev)
        if f in (8, 9):
            rev = (f == 9)
            return sorted(candidates, key=lambda e: e.attributes.get("def"),
                          reverse=rev)
        if f == 14:
            return candidates                                    # random by caller
        if f in (15, 16):
            rev = (f == 16)
            return sorted(candidates, key=lambda e: e.hp, reverse=rev)
        if f in (17, 18):
            rev = (f == 18)
            return sorted(candidates, key=lambda e: e.attributes.get("atk"),
                          reverse=rev)
        if f in (27, 28):
            rev = (f == 28)
            return sorted(candidates, key=lambda e: e.attributes.get("massLevel"),
                          reverse=rev)
        if f == 42:
            return sorted(candidates, key=lambda e: getattr(e, "block_volume", 1),
                          reverse=True)
        if f == 76:
            if source is None:
                return candidates
            return sorted(candidates, key=lambda e: _dist(e, source))
        import warnings
        warnings.warn(f"postFilter {f} not implemented; fallback to ALL",
                      NotImplementedWarning)
        return candidates

    def select(self, candidates, filter_id, source=None, rng=None):
        """Order candidates by filter; filter 14 (random) returns index."""
        ordered = self.apply_filter(candidates, filter_id, source)
        if int(filter_id or 0) == 14 and ordered:
            if rng is not None:
                return rng.next(len(ordered))
            return random.randrange(len(ordered))
        return ordered

    def enemy_target(self, enemy, range_radius=None, require_in_range=False,
                     filter_id=None):
        """Enemy picks an operator: blocked first, then hate order."""
        ops = [o for o in self.battle.get_operators()
               if not o.dead and not o.in_deploy_anim(self.battle.tick)
               and not _flag(o, 2)]                      # TARGET_FREE excluded
        if not ops:
            return None
        if enemy.blocked_by in ops and not (
                range_radius is not None and require_in_range and
                (_flag(enemy.blocked_by, 9) or
                 _flag(enemy.blocked_by, 17) or _flag(enemy.blocked_by, 4))):
            return enemy.blocked_by
        if range_radius is not None and require_in_range:
            # ranged attackers cannot see invisible / camouflage / hidden
            ops = [o for o in ops
                   if _dist(enemy, o) <= range_radius + 0.001
                   and not _flag(o, 9) and not _flag(o, 17)
                   and not _flag(o, 4)]
        if not ops:
            return None
        ops.sort(key=self.operator_hate, reverse=True)
        return ops[0]

    def _heal_candidates(self, op, ts):
        """Filtered, in-range heal candidates ordered by game priority.
        Wandermedic: hp-ratio > lowest damaged-element value > earlier deploy;
        skills marked "\u4f18\u5148\u6cbb\u7597\u5143\u7d20\u635f\u4f24\u6700\u4e25\u91cd
        \u7684\u76ee\u6807" flip to element value first (still lowest first,
        PRTS documented quirk).  Other medics: lowest hp ratio."""
        _wm = ts is not None and ts.is_wandermedic()
        allies = [u for u in (self.battle.get_operators() +
                              self.battle.get_tokens())
                  if not u.dead
                  and (not ts.is_healer() or u is not op)
                  and (u.hp < u.max_hp - 0.01
                       or (_wm and _unit_has_ep(u, self.battle)))
                  # PRTS: "通常不会治疗生命值已满且元素值已满的单位"
                  and (not _wm or not _wm_ep_full(u, self.battle))
                  and (not _wm or not getattr(
                      u, "heal_free", lambda: False)())
                  and op.range_shape and any(
                      (op.row + dr, op.col + dc) == (u.row, u.col)
                      for dr, dc in op.range_shape)]
        if not allies:
            return []
        if _wm:
            # PRTS branch note (蜜莓/桑葚/纯烬艾雅法拉 shared):
            #   普通攻击: 生命比例最低 > 当前损伤元素的元素值最低 > 更早部署
            #   技能标注"优先治疗元素损伤最严重的目标": 元素值最低 > 生命比例最低
            # The game implements "最严重" as 元素值最低 (documented quirk).
            ep_first = _active_skill_id(op) in _WM_EP_PRIORITY_SKILLS

            def _hpr(u):
                return u.hp / max(u.max_hp, 1e-9)

            def _dt(u):
                return float(getattr(u, "deploy_tick", 0) or 0)

            if ep_first:
                allies.sort(key=lambda u: (_wm_ep_metric(u, self.battle),
                                           _hpr(u), _dt(u)))
            else:
                allies.sort(key=lambda u: (_hpr(u),
                                           _wm_ep_metric(u, self.battle),
                                           _dt(u)))
        else:
            allies.sort(key=lambda u: u.hp / max(u.max_hp, 1e-9))
        return allies

    def operator_targets(self, op, count=1):
        """Top-N in-range heal targets in game priority order (medic
        multi-target skills, e.g. \u871c\u8393 S1/S2).  Returns [] for
        non-heal operators / no candidates."""
        ts = getattr(op, "trait_system", None)
        _heal_mode = (ts is not None and ts.is_healer()) or (
            ts is not None and ts.heal_while_skill()
            and getattr(getattr(op, "skill_controller", None),
                         "active", None) is not None)
        if not _heal_mode:
            return []
        return self._heal_candidates(op, ts)[:max(1, int(count))]

    def operator_target(self, op, candidates=None, filter_id=None, rng=None):
        """Operator picks a target: medics heal the most wounded ally in
        range; melee prefers blocked; ranged uses range shape + hate/filter;
        snipers prefer airborne enemies."""
        ts = getattr(op, "trait_system", None)
        _heal_mode = (ts is not None and ts.is_healer()) or (
            ts is not None and ts.heal_while_skill()
            and getattr(getattr(op, "skill_controller", None),
                         "active", None) is not None)
        if _heal_mode:
            ordered = self._heal_candidates(op, ts)
            return ordered[0] if ordered else None
        enemies = candidates if candidates is not None else \
            [e for e in self.battle.get_enemies() if not e.dead]
        if not enemies:
            return None
        # fog of war: units standing on out-of-view tiles (MarkFogView)
        # cannot be selected as normal attack targets until revealed
        enemies = [e for e in enemies if not self.battle.is_fogged(e)]
        if not enemies:
            return None
        # bombarder (\u6295\u63b7\u624b): basic attacks cannot target air (ground-only)
        if ts is not None and ts.ground_only():
            enemies = [e for e in enemies
                       if not getattr(e, "is_flying", False)]
            if not enemies:
                return None
        if candidates is not None:
            # callers that pass an explicit candidate pool (skill
            # selectors, funnel whole-field S3 drones) own the range
            # decision; skip the operator-range filter here
            pool = enemies
        else:
            blocked = [e for e in enemies if e.blocked_by is op]
            if blocked:
                pool = blocked
            else:
                # token scouting areas (Ray sandbeast) extend effective
                # range and take priority over the operator own range
                area_cells = set()
                try:
                    area_cells = self.battle.token_area_cells(op)
                except Exception:
                    area_cells = set()
                in_range = [e for e in enemies if op.range_shape and
                            any((op.row + dr, op.col + dc) == (e.row, e.col)
                                for dr, dc in op.range_shape)]
                in_area = [e for e in enemies
                           if (e.row, e.col) in area_cells] if area_cells else []
                pool = in_area if in_area else in_range
            if not pool:
                # range-gated targeting: an operator with nothing in
                # range idles (correct game behaviour). Route-aware agent
                # deploys (_plan + _best_direction) keep the scripted
                # policies effective; see docs/TEST_SCOPING.md.
                return None
        if ts is not None and ts.prefer_air():
            air = [e for e in pool if getattr(e, "is_flying", False)]
            if air:
                pool = air
        # ?? S3: prefer enemies NOT in element burst recovery (any type)
        if getattr(op, "prefer_unburst", False):
            _unburst = [e for e in pool
                        if not any(self.battle.buffs.get(e, f"ep_burst_cd_{t}")
                                   for t in range(4))]
            if _unburst:
                pool = _unburst
        ordered = self.apply_filter(pool, filter_id, op)
        if not ordered:
            return None
        if int(filter_id or 0) == 14 and rng is not None:
            return ordered[rng.next(len(ordered))]
        return ordered[0]

    def operator_attack_target(self, op, force=False):
        """Basic-attack target under the ability target-search gate
        (SelectorTrigger.SEARCH_TARGET_TICK=3): the selector re-runs at
        most once every 3 logic ticks, and between refreshes the previous
        target is kept while it is still selectable (alive / in range /
        blocked / healable).  ``force`` (Search(force)) bypasses the gate.
        The unit may set ``_search_period`` to override the cadence."""
        last = getattr(op, "_search_tick", None)
        cur = getattr(op, "_ai_target", None)
        period = int(getattr(op, "_search_period",
                             SEARCH_TARGET_TICK) or SEARCH_TARGET_TICK)
        if not force and last is not None and \
                self.battle.tick - last < period:
            if cur is not None and not getattr(cur, "dead", False) and \
                    self._still_selectable(op, cur):
                return cur
        new = self.operator_target(op)
        op._ai_target = new
        op._search_tick = self.battle.tick
        return new

    def _still_selectable(self, op, cur):
        """Cheap re-check that ``cur`` would still be chosen by the
        operator's normal attack / heal selector."""
        ts = getattr(op, "trait_system", None)
        _heal = (ts is not None and ts.is_healer()) or (
            ts is not None and ts.heal_while_skill()
            and getattr(getattr(op, "skill_controller", None),
                        "active", None) is not None)
        if _heal:
            try:
                cands = self._heal_candidates(op, ts)
            except Exception:
                cands = []
            return cur in cands
        if getattr(cur, "side", 0) != 0 or getattr(cur, "dead", False):
            return False
        if self.battle.is_fogged(cur):
            return False
        if ts is not None and ts.ground_only() and \
                getattr(cur, "is_flying", False):
            return False
        if getattr(cur, "blocked_by", None) is op:
            return True
        area = set()
        try:
            area = self.battle.token_area_cells(op)
        except Exception:
            area = set()
        if area and (cur.row, cur.col) in area:
            return True
        return bool(op.range_shape and any(
            (op.row + dr, op.col + dc) == (cur.row, cur.col)
            for dr, dc in op.range_shape))


def _dist(a, b):
    return ((a.pos_x - b.pos_x) ** 2 + (a.pos_y - b.pos_y) ** 2) ** 0.5


def _flag(unit, flag):
    return unit.flag(flag) if hasattr(unit, "flag") else False
