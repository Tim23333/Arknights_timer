"""BattleController - the frame-driven simulation core.

Per-tick order (MECHANICS §11 + docs):
  1. wave scheduler (spawn)
  2. enemy updates (skill controller + AI: move/attack)
  3. operator updates (targeting + attack + SP)
  4. blocking / reach-exit resolution
  5. buff expiry + abnormal ticks
  6. cost / life recovery
  7. end conditions
"""

import io
import json
import os

from .attributes import Attributes
from .buffs import BuffSystem
from .consts import (AbnormalFlag, DamageType, EnemyState,
                     TIME_ROUGH_LOGIC_RATE)
from .damage import DamageResult, calculate_damage, roll_damage
from .entities import Enemy, Operator, Token
from .events import EventBus, EventType
from .loader import DataStore, merged_map, merged_routes
from .map import GameMap, TileData, materialize_tiles
from .rng import SystemRandomClone
from .waves import WaveScheduler


_PRTS_TEMPLATE_KEYS = None


def _prts_template_keys():
    """Buff template keys whose action graphs contain Main15* nodes
    (computed once per process).  These are the PRTS-driving templates
    mounted from the Mainline-15 enemies' base prefabs."""
    global _PRTS_TEMPLATE_KEYS
    if _PRTS_TEMPLATE_KEYS is None:
        try:
            from .buff_templates import load_templates
            tpls = load_templates()
            _PRTS_TEMPLATE_KEYS = frozenset(
                k for k, v in tpls.items()
                if isinstance(v, dict) and
                "Main15" in json.dumps(v, ensure_ascii=False))
        except Exception:
            _PRTS_TEMPLATE_KEYS = frozenset()
    return _PRTS_TEMPLATE_KEYS


class BattleController:
    """Owns the world state and advances it tick by tick."""

    def __init__(self, level_id, store=None, seed=None, squad=None,
                 char_data=None, custom_enemies=None, custom_level=None,
                 rune_difficulty=1):
        self.store = store if store is not None else DataStore()
        self.level_id = level_id
        self.custom_level = custom_level
        if custom_level is not None:
            from .custom_levels import normalize
            cl = normalize(custom_level)
            self.sim = {
                "options": cl.get("options"),
                "enemyDbRefs": cl.get("enemyDbRefs") or [],
                "routes": cl.get("routes") or [],
                "map": cl.get("map"),
                "waveTimeline": cl.get("waveTimeline") or [],
                "randomSeed": cl.get("randomSeed", 1),
                "globalBuffs": cl.get("globalBuffs") or [],
            }
            self.raw = {
                "mapData": {"tiles": cl["map"]["tiles"]},
                "routes": cl.get("routes") or [],
                "globalBuffs": cl.get("globalBuffs") or [],
                "branches": {},
                "predefines": {"characterInsts": [], "tokenInsts": []},
            }
        else:
            self.sim = self.store.sim_level(level_id)
            if self.sim is None:
                raise KeyError(f"level {level_id} not in stage_sim_bundle")
            self.raw = self.store.raw_level(level_id)
        self.seed = seed if seed is not None else (self.sim.get("randomSeed")
                                                   or 0)
        self.rng = SystemRandomClone(self.seed)
        self.events = EventBus()
        from .prts import PrtsManager
        self.prts = PrtsManager(self)
        from .act35 import Act35GemsManager
        self.act35 = Act35GemsManager(self)
        from .act31 import Act31PolluteManager
        self.act31 = Act31PolluteManager(self)
        self._tick = 0
        self.paused = False
        self.finished = False
        self.result = None

        # map
        if custom_level is not None:
            mm = self.sim["map"]
            self.map = GameMap(mm["rows"], mm["cols"],
                               [TileData(i, t) for i, t in enumerate(
                                   mm["tiles"] or [])])
            self.routes = self.sim.get("routes") or []
        else:
            mm = merged_map(self.store, level_id)
            self.map = GameMap(mm["rows"], mm["cols"],
                               materialize_tiles(mm["rows"], mm["cols"],
                                                 mm["tiles"], mm["cells"]))
            self.routes = merged_routes(self.store, level_id)

        # options
        opt = self.sim.get("options") or {}
        self.max_life_point = int(opt.get("maxLifePoint", 3))
        self.life_point = self.max_life_point
        self.initial_cost = float(opt.get("initialCost", 10))
        self.max_cost = float(opt.get("maxCost", 99))
        self.cost = self.initial_cost
        self.cost_increase_time = float(opt.get("costIncreaseTime", 1.0))
        self._cost_acc = 0.0
        # precise cost timer (MECHANICS §10): effective period =
        # base x product(cost-timer modifiers) x negative-recovery factor;
        # timer pauses while cost full or increment locked
        self._cost_base_increase_time = self.cost_increase_time
        self._cost_timer_modifiers = []   # {mul, priority, source}
        self._cost_locked = False
        self._cost_lock_reason = 0
        self._negative_recovery_multiplier = 0.5
        self.character_limit = int(opt.get("characterLimit", 8))
        self.move_multiplier = float(opt.get("moveMultiplier", 1.0))
        self.max_play_time = float(opt.get("maxPlayTime", -1.0))

        # level runes (stage tags / crisis contracts) - parsed once here;
        # global ones (life point / cost / recovery) apply immediately,
        # per-unit ones are stored for spawn/deploy time application.
        self._rune_difficulty = rune_difficulty or 1   # NORMAL default
        self._apply_level_runes()

        # entities
        self.enemies = []
        self.operators = []
        self.tokens = []
        self.buffs = BuffSystem(self)
        self.squad = squad or []
        self.char_data = char_data
        if char_data is None:
            try:
                self.char_data = self.store.characters
            except AttributeError:
                self.char_data = None

        # predefined level tokens/characters (predefines)
        self._predefined_pending = []
        self.predefines = {}
        try:
            if custom_level is not None:
                self._spawn_predefines()
            else:
                from .predefines import (parse_level_predefines,
                                         predefines_from_raw)
                self.predefines = parse_level_predefines(level_id)
                if not (self.predefines.get("characterInsts")
                        or self.predefines.get("tokenInsts")):
                    # official gamedata levels have no binary asset; their
                    # parsed JSON carries the full predefine section
                    self.predefines = predefines_from_raw(self.raw)
                self._spawn_predefines()
        except Exception:
            pass

        # scheduler: prefer the raw level waves (chained-wave model); the
        # bundle's precomputed timeline uses an older additive model that
        # collapses multi-wave levels onto t=0
        raw_waves = self.raw.get("waves")
        if raw_waves:
            from .waves import RuntimeWaveScheduler
            # Parsed official levels use the native-style runtime loader:
            # fragment queues are loaded sequentially and later waves wait
            # for the preceding wave's managed enemies to clear.
            self.waves = RuntimeWaveScheduler(
                raw_waves, self, rng=self.rng)
        else:
            timeline = self.sim.get("waveTimeline") or []
            self.waves = WaveScheduler(timeline, self)
        # level branches (Nodes.MoveNextLevelBranch / PickRandomBranchPhase):
        # per-branch phase cursor + active phase schedulers (BranchRuntime)
        self._branch_cursors = {}
        self._branch_random_used = {}
        self._branch_phases = []
        # custom enemies (user-defined extra spawns)
        if custom_enemies:
            from .custom_enemies import CustomEnemyScheduler
            self.custom_waves = CustomEnemyScheduler(self, custom_enemies)
        else:
            self.custom_waves = None
        # in-flight projectiles
        self.projectiles = []
        self._aura_applied = set()   # talent aura buffs currently applied
        # units carrying doctor-overheal shields (inst_id -> Unit)
        self._rdoc_shield_units = {}
        # terrain effects (tile_effects.py) + per-tile blackboard
        from .tile_effects import TileEffectSystem
        self.tile_effects = TileEffectSystem(self)
        # dynamic skill-placed field tiles (Thumpy S3 conveyor belt ...)
        self._skill_tiles = {}
        self._skill_tile_seq = 0
        self._tile_bb = {}
        self._global_bb = {}
        self._char_shared_bb = {}
        self._tile_modes = {}      # (row, col) -> dynamicBuff mode
        # redeploy cooldowns: char_id -> tick when redeploy allowed
        self._redeploy_until = {}
        # player-side gained-token inventory (GainToken: act36side /
        # multi-fortress event tokens): token_key -> count gained
        self._gained_tokens = {}
        self._gained_token_timings = {}
        # steal-attribute accumulator (AssignStealAttributeAbilityTotal-
        # ValueToBB): (inst_id, ability) -> current stolen / cap
        self._steal_values = {}
        self._steal_max = {}
        # rally-point rebirth (SwitchRallyPointCategory / RallyPointReborn):
        # current category + units serving as rally points per category
        self._rally_category = "CHARACTER"
        self._rally_points = {}          # category -> [unit inst_id, ...]
        # fog-of-war view state (MarkFogView): (row, col) -> inView bool
        self._fog_view = {}
        # deck-card exclusions (ExcludeDeckCardFromBattle)
        self._excluded_deck_cards = set()
        # score counters (UpdateScoreManually / GameCityUpdateScore)
        self._scores = {}
        # half-idle loot drops (HalfIdleDropResource / HalfIdleDropBattleItem)
        self._dropped_loot = {}
        # Act27sideModifyTileCachedSideType: (row, col) -> ALLY/ENEMY side
        self._tile_side_cache = {}
        # rally category switch counter (CheckFirstRallyPointMode)
        self._rally_switch_count = 0
        # extra battle-info log (LogExtraBattleInfoWithNoTarget ...)
        self._extra_log = {}
        # football / fever env state
        self._fever = {}                 # feverKey -> 0..1
        self._fever_active = False
        self._football_pos = None        # (row, col)
        self._football_stopped = False
        # legion-mode state (gold / hand cards / traps / danger level)
        self._legion_gold = 0
        self._legion_hand = []
        self._legion_pending = []
        self._wdslm_stands = {}        # ability_name -> [Enemy stands]
        self._durbus_passengers = {}   # ability_name -> [Enemy passengers]
        self._sandbox_weather = None
        self._sandbox_node_type = None
        self._sandbox_season = None
        self._sandbox_build_mode = False
        self._sandbox_stats = {}       # stat name -> value
        self._sandbox_res = 0
        self._sandbox_items = {}       # item_id -> count
        self._sandbox_unit_states = {} # inst_id -> recorded state
        self._act49_tile_types = {}    # (r,c) -> tile type string
        self._act49_print_progress = 0.0
        self._ro4dlc2_seal_tiles = set()
        self._progress_buffs = []      # registered progress buff keys
        self._electric_work = {}       # work type -> count
        self._coop_scores = {}         # score id -> value
        self._gather_listeners = []    # gather listeners (unit, type)
        self._legion_hand_max = 8
        self._rogue_zone_type = None
        self._rogue_duel_stage = None
        self._rogue_deify_stage = None
        self._rogue_shield = 0
        self._rogue_dice_log = []
        self._rogue_exp_use = {}       # trap id -> total exp used
        self._legion_traps = set()
        self._legion_profession_levels = {}
        self._legion_danger_level = 0
        # roguelike state
        self._rogue_exp = 0
        self._rogue_dice = None
        # dynamic-buff-tile exclusions + tile holding effects
        self._dynamic_tile_excludes = set()
        self._tile_holding_effects = {}
        self._buff_dispatch_depth = 0
        # battle statistics (AI strategy evaluation)
        self.stats = {
            "kills": 0, "leaks": 0, "lifeLost": 0,
            "playerDamageDealt": 0.0, "playerDamageTaken": 0.0,
            "operatorDeaths": 0, "skillCasts": 0, "deployments": 0,
        }
        # summon registry: char_id -> [{tokenKey, source, skillIndex}]
        self._summons = {}
        # deployed summon instance ids by token_key
        self._summon_insts = {}
        # level global buffs (e.g. night_map_default) - from sim bundle or
        # the original level asset (which carries globalBuffs)
        self.global_buffs = self.sim.get("globalBuffs") or []
        if not self.global_buffs:
            raw_gb = self.raw.get("globalBuffs") or []
            self.global_buffs = raw_gb
        # track buffs applied to newly spawned units
        self._global_buff_applied = set()

    # ================= accessors (skills/buffs modules) =================
    def get_enemies(self):
        return self.enemies

    def get_operators(self):
        return self.operators

    def get_tokens(self):
        return self.tokens

    def token_area_cells(self, op):
        """All (row, col) cells covered by tokens owned by ``op`` (used
        by Ray's sandbeast scouting area)."""
        cells = set()
        for tok in self.tokens:
            if tok.owner is not op or tok.dead:
                continue
            for dr, dc in (tok.range_shape or []):
                cells.add((tok.row + dr, tok.col + dc))
        return cells

    def get_projectiles(self):
        return self.projectiles

    def get_tile(self, row, col):
        return self.map.tile(row, col)

    def path_distance(self, row, col, motion_mode=0):
        return self.map.path_distance(row, col, motion_mode)

    def tile_blackboard(self, row, col):
        """Per-tile blackboard: dynamic tile effects merged over the tile
        prefab defaults, then level rune overrides (map_tile_blackb_mul /
        add / assign) applied by tile type or location."""
        t = self.map.tile(row, col)
        key = t.tile_key if t is not None else ""
        out = dict(self._tile_bb.get((row, col)) or {})
        if not out and key:
            try:
                from .tile_effects import tile_blackboard_defaults
                out.update(tile_blackboard_defaults(key))
            except Exception:
                pass
        rb = getattr(self, "_rune_tile_bb", None)
        if not rb:
            return out
        # multipliers first, then additives, then hard assign
        def _apply(target, mode):
            d = rb.get(mode, {}).get(target)
            if not d:
                return
            if mode == "mul":
                for k, v in d.items():
                    cur = out.get(k)
                    try:
                        cur = float(cur) if cur is not None else 0.0
                    except (TypeError, ValueError):
                        cur = 0.0
                    out[k] = cur * v if cur else v
            elif mode == "add":
                for k, v in d.items():
                    try:
                        out[k] = float(out.get(k, 0.0) or 0.0) + v
                    except (TypeError, ValueError):
                        out[k] = v
            else:
                out.update(d)
        _apply(("tile", key), "mul")
        _apply(("tile", key), "add")
        _apply(("tile", key), "assign")
        _apply(("loc", (row, col)), "mul")
        _apply(("loc", (row, col)), "add")
        _apply(("loc", (row, col)), "assign")
        return out
    def tile_mode(self, row, col):
        """Current dynamic-buff mode index of a tile (default 0)."""
        return self._tile_modes.get((row, col), 0)

    def switch_tiles_mode(self, operation=None, mode_index=None,
                          tile_type=None, specify=False, source=None):
        """Switch dynamic buff tile modes (e.g. reed -> flaming).

        INDEX sets the mode to mode_index; FLIP_BOOL toggles it.
        Returns the number of tiles changed."""
        rows, cols = self.map.rows, self.map.cols
        changed = 0
        for r in range(rows):
            for c in range(cols):
                t = self.map.tile(r, c)
                if t is None:
                    continue
                tk = t.tile_key or ""
                if specify and tile_type:
                    if tile_type == "REED_TILE" and \
                            not tk.startswith("tile_reed"):
                        continue
                    if tile_type != "REED_TILE" and \
                            tile_type.lower() not in tk:
                        continue
                cur = self.tile_mode(r, c)
                if operation == "FLIP_BOOL":
                    nxt = 1 - cur
                else:
                    nxt = int(mode_index if mode_index is not None else 1)
                if nxt == cur:
                    continue
                self._tile_modes[(r, c)] = nxt
                self._refresh_tile_buffs(r, c)
                self.emit(self.tick, "tile_mode_switch", {
                    "row": r, "col": c, "mode": nxt,
                    "tileKey": tk})
                changed += 1
        return changed

    def _refresh_tile_buffs(self, row, col):
        """Drop this tile's buffs from units standing on it; the
        per-tick effects pass reapplies the new mode's buffs."""
        try:
            from .tile_effects import tile_buff_keys
            t = self.map.tile(row, col)
            if t is None:
                return
            keys = tile_buff_keys(t.tile_key or "")
            for u in (list(self.get_operators()) +
                      list(self.get_enemies()) +
                      list(self.get_tokens())):
                if not getattr(u, "dead", False) and \
                        (u.row, u.col) == (row, col):
                    for k in keys:
                        try:
                            self.buffs.remove(u, k)
                        except Exception:
                            pass
        except Exception:
            pass


    def emit(self, tick, type_, data=None):
        return self.events.emit(tick, type_, data)

    # ================= damage / heal / buff =================
    def apply_damage(self, target, amount, dmg_type, source=None,
                     atk_scale=1.0, no_hit_recovery=False,
                     element_as_hp=False):
        """Settles damage through the formula pipeline.

        Buff templates can modify damage pre-calc (ON_CALCULATE_DAMAGE:
        BlockDamage / DamageScale) and observe it post-hit (ON_TAKE_DAMAGE
        on the target, ON_OUTPUT_DAMAGE on the source).

        ``element_as_hp`` only matters for DamageType.ELEMENT: the
        emulator's default ELEMENT semantic is EP accumulation (old
        model), but current-game 元素伤害 is a HP damage type that
        ignores DEF/RES and bypasses barrier (e.g. 本源术师 burst-window
        bonus damage - game template kaitou_s_1[ep_damage]:
        AdvancedApplyDamage ELEMENT).  With this flag the amount is
        subtracted directly from HP instead of accumulating EP; the
        shared modifier chain / stats / death tail still runs.
        """
        if target.dead or target.invincible():
            return DamageResult(0.0, dmg_type, source=source, target=target)
        # weaken (e.g. DARK element burst on enemies: 50% decaying 虚弱)
        # reduces all damage DEALT by the weakened source.
        _weak = self._weaken_scale(source)
        if _weak != 1.0:
            amount = float(amount) * _weak
        # form-machine damage reduction (talentBlackboard
        # mode_{n}.damage_resistance, e.g. 进化的本质: side-based 80% in
        # 初生/进化 forms, 99% non-self physical/magic in 完美 form)
        _mode_scale = self._enemy_mode_damage_scale(
            target, source, dmg_type)
        if _mode_scale != 1.0:
            amount = float(amount) * _mode_scale
        # element damage never triggers hit-recovery (????) - PRTS
        if dmg_type == DamageType.ELEMENT:
            no_hit_recovery = True
        dmg_ctx = {"amount": float(amount), "type": dmg_type,
                   "blocked": 0.0}
        # damage-modifier event chain (game DamageModifier pipeline):
        # BEFORE_APPLYING fires pre-calc, APPLYING pre-settle, APPLIED /
        # SKIPPED post-settle, OUTPUT on the source side.
        self._dispatch_buff_events(target, "ON_BEFORE_APPLYING_MODIFIER",
                                   source=source, damage=dmg_ctx)
        self._dispatch_buff_events(target, "ON_BEFORE_TARGET_APPLY_MODIFIER",
                                   source=source, damage=dmg_ctx)
        self._dispatch_buff_events(target, "ON_CALCULATE_DAMAGE",
                                   source=source, damage=dmg_ctx)
        # ON_TAKE_DAMAGE fires pre-settle: BlockDamage / DamageScale nodes
        # modify the damage amount here (game pipeline semantics).
        self._dispatch_buff_events(target, "ON_TAKE_DAMAGE",
                                   source=source, damage=dmg_ctx)
        self._dispatch_buff_events(target, "ON_APPLYING_MODIFIER",
                                   source=source, damage=dmg_ctx)
        amount = dmg_ctx["amount"]
        # fragility (\u8106\u5f31): target-side debuffs multiply the final
        # damage of the matching type (weak[magic]/weak[phy]/weak[ep], or
        # generic weak for every HP-damage type; e.g. PhonoR-0 talent
        # damage_scale 1.03~1.10). Element fragility scales the EP amount.
        _fragile = self._fragility_scale(target, dmg_type)
        barrier_abs = 0.0
        if dmg_type == DamageType.ELEMENT:
            if _fragile != 1.0:
                amount = amount * _fragile
            if element_as_hp and amount > 0 and not target.dead:
                # element HP damage bypasses the barrier pool (PRTS:
                # barrier absorbs physical/arts only); undeadable units
                # survive at 1 HP like every other damage type.
                _bar = float(target.barrier or 0.0)
                if _bar > 0:
                    target.barrier = 0.0
                try:
                    target.hp -= amount
                    if target.hp <= 0:
                        if target.undeadable():
                            target.hp = 1.0
                        else:
                            target.hp = 0.0
                            target.dead = True
                finally:
                    target.barrier = _bar
            else:
                self.add_ep(target, 0, amount)
            result = DamageResult(amount, dmg_type, source=source, target=target)
        else:
            # source penetration stats (percent + fixed) wired into formula
            pen_ratio, pen_fixed = 0.0, 0.0
            if source is not None:
                if dmg_type == DamageType.MAGICAL:
                    pen_ratio = source.attributes.get("magicResistPenetrate")
                    pen_fixed = source.attributes.get(
                        "magicResistPenetrateFixed")
                else:
                    pen_ratio = source.attributes.get("defPenetrate")
                    pen_fixed = source.attributes.get("defPenetrateFixed")
            dealt = calculate_damage(
                amount, target.attributes, dmg_type, atk_scale=atk_scale,
                penetrate_ratio=pen_ratio or 0.0,
                penetrate_fixed=pen_fixed or 0.0)
            self._dispatch_buff_events(target, "ON_AFTER_CALCULATE_DAMAGE",
                                       source=source, damage=dmg_ctx)
            # hit-rate roll (defensive): the TARGET damageHitrate decides
            # whether the hit lands (e.g. stalker \u4f0f\u51fb\u5ba2 50%
            # physical/magical dodge = hitrate 50); <100 means a miss chance
            acc = float(target.attributes.get(
                "damageHitrateMagical" if dmg_type == DamageType.MAGICAL
                else "damageHitratePhysical") or 100.0)
            if acc < 100.0 and self.rng.chance(1.0 - acc / 100.0):
                dealt = 0.0
                self._dispatch_buff_events(target, "ON_EVADE_DAMAGE",
                                           source=source, damage=dmg_ctx)
            # Ray \u5de1\u54e8\u4f19\u4f34: physical damage vs enemies inside her
            # sandbeast scouting area gets a final multiplier and counts a
            # bullet toward the S2 recovery pool on the sandbeast token.
            if dmg_type == DamageType.PHYSICAL and dealt > 0 and \
                    source is not None and getattr(source, "side", 0) == 1:
                try:
                    _ts2 = getattr(source, "talent_system", None)
                    _ds = _ts2.bb("damage_scale") if _ts2 is not None else None
                    if _ds:
                        _area = self.token_area_cells(source)
                        if _area and (target.row, target.col) in _area:
                            dealt *= (1.0 + float(_ds))
                            for _tok in self.tokens:
                                if _tok.owner is source and not _tok.dead:
                                    _tok._recover_bullets = getattr(
                                        _tok, "_recover_bullets", 0) + 1
                                    break
                except Exception:
                    pass
            # fragility final multiplier (after mitigation / hit-rate roll)
            if _fragile != 1.0:
                dealt = dealt * _fragile
            # doctor-overheal shield absorbs first (priority +1000 buff)
            rdoc_abs = target.absorb_rdoc_shield(dealt)
            dealt -= rdoc_abs
            # \u70db\u714c T2 \u7edd\u5904\u91cd\u71c3: a lethal hit (after
            # barrier absorption) flips her into the downed state instead of
            # killing her. Barrier is checked first, mirroring take_damage().
            effective = dealt
            if target.barrier and target.barrier > 0:
                effective = max(0.0, dealt - target.barrier)
            if effective > 0 and not target.dead and \
                    float(target.hp) - effective <= 0 and \
                    (self._try_blaze2_reborn(target)
                     or self._try_dollkeeper(target)):
                actual = 0.0
            else:
                # lethal-hit chain: ON_BEFORE_TRY_SET_HP_ZERO lets buffs
                # consume a TrySetHpZero modifier (Surtr T2 \u4f59\u70ec, Horn
                # T1, Bena) to survive; the POST event then drives the
                # follow-up (UNDEADABLE / stat buffs).
                _lethal = effective > 0 and not target.dead and \
                    float(target.hp) - effective <= 0
                if _lethal and not target.undeadable():
                    dmg_ctx.setdefault("_hp_zero_consumed", False)
                    dmg_ctx.setdefault("_hp_zero_blocked", False)
                    self._dispatch_buff_events(
                        target, "ON_BEFORE_TRY_SET_HP_ZERO",
                        source=source, damage=dmg_ctx)
                    if dmg_ctx.get("_hp_zero_blocked") or \
                            dmg_ctx.get("_hp_zero_consumed"):
                        dealt = max(0.0, float(target.hp) - 1.0)
                        effective = max(0.0, dealt - float(
                            target.barrier or 0.0))
                        self._dispatch_buff_events(
                            target, "ON_POST_TRY_SET_HP_ZERO",
                            source=source, damage=dmg_ctx)
                actual = target.take_damage(dealt)
            barrier_abs = rdoc_abs + float(
                getattr(target, "_barrier_absorbed", 0.0) or 0.0)
            if barrier_abs > 0:
                self.emit(self.tick, "barrier_hit", {
                    "unit": target.inst_id,
                    "amount": round(barrier_abs, 3)})
            result = DamageResult(actual, dmg_type, source=source, target=target)
        if source is not None and source.side == 1:
            self.stats["playerDamageDealt"] += result.amount
        if target.side == 1:
            self.stats["playerDamageTaken"] += result.amount
        # damage wakes sleeping (DOZE) targets
        if target.flag(43) and result.amount > 0:
            target.clear_flag(43)
            self.emit(self.tick, "sleep_woke",
                      {"unit": target.inst_id})
        dmg_ctx["amount"] = float(result.amount)
        if not target.dead:
            self._dispatch_buff_events(target, "ON_APPLIED_MODIFIER",
                                       source=source, damage=dmg_ctx)
        if result.amount <= 0.0:
            self._dispatch_buff_events(target, "ON_APPLYING_SKIPPED_MODIFIER",
                                       source=source, damage=dmg_ctx)
        # per-operator talent output hooks (e.g. Thumpy talent 1 attaches
        # erosion on physical damage output)
        if source is not None and result.amount > 0:
            _ts = getattr(source, "talent_system", None)
            if _ts is not None:
                try:
                    _ts.on_damage_output(target, dmg_type, result.amount, self)
                except Exception:
                    pass
        if source is not None and not getattr(source, "dead", False):
            self._dispatch_buff_events(source, "ON_OUTPUT_MODIFIER",
                                       target=target, damage=dmg_ctx)
            self._dispatch_buff_events(source, "ON_OUTPUT_DAMAGE",
                                       target=target, damage=dmg_ctx)
            self._dispatch_buff_events(source, "ON_AFTER_OUTPUT_DAMAGE",
                                       target=target, damage=dmg_ctx)
        self.emit(self.tick, EventType.DAMAGE, {
            "source": source.inst_id if source else None,
            "target": target.inst_id, "amount": round(result.amount, 3),
            "type": dmg_type,
            "barrierAbsorbed": round(barrier_abs, 3)})
        if target.side == 1 and source is not None and source.side == 0 \
                and not target.dead and not no_hit_recovery:
            sc = getattr(target, "skill_controller", None)
            if sc is not None:
                sc.recover_sp(4)          # hit-recover skills
        if target.side == 0 and not target.dead:
            sc = getattr(target, "skill_controller", None)
            if sc is not None:
                sc.on_enemy_take_damage()
        if target.dead:
            if getattr(target, "_death_reason", None) is None:
                target._death_reason = "KILLED"
            if getattr(target, "side", 0) == 1:
                # retreat/death returns stolen attributes
                self._clear_steal_buffs(target)
            try:
                self.buffs.on_owner_before_dead(target)
                self.buffs.on_owner_killed(target)
            except Exception:
                pass
            if source is not None and not getattr(source, "dead", False):
                self._dispatch_buff_events(source, "ON_TARGET_KILLED",
                                           source=source, target=target)
            if target.side == 0:
                self.stats["kills"] += 1
            else:
                self.stats["operatorDeaths"] += 1
            self.emit(self.tick, EventType.ENEMY_DEAD,
                      {"unit": target.inst_id})
            if source is not None and getattr(source, "side", 0) == 1:
                sc = getattr(source, "skill_controller", None)
                ts = getattr(source, "talent_system", None)
                if ts is not None and ts.kill_sp_bonus() and sc is not None:
                    sc.recover_sp(4, ts.kill_sp_bonus())
                # Ray S3: track kills for the end-of-skill SP refund
                _act = getattr(sc, "active", None) if sc is not None else None
                if _act is not None and getattr(getattr(_act, "skill", None),
                                                "skill_id", "") == \
                        "skchr_ray_3":
                    try:
                        _act._ray_s3_kills = getattr(
                            _act, "_ray_s3_kills", 0) + 1
                    except Exception:
                        pass
                # 诗怀雅 S3"千金一掷"：击倒敌人获得一枚金币
                if getattr(source, "_coin_max", 0) > 0:
                    _act2 = getattr(sc, "active", None) if sc is not None \
                        else None
                    if _act2 is not None and getattr(
                            getattr(_act2, "skill", None), "skill_id",
                            "") == "skchr_swire2_3":
                        source._coins = min(
                            source._coin_max,
                            getattr(source, "_coins", 0) + 1)
                # class trait: charger refunds deployment cost per kill
                trait = getattr(source, "trait_system", None)
                if trait is not None:
                    bonus = trait.kill_cost_bonus()
                    if bonus:
                        self.battle_cost_add(bonus)
                        self.emit(self.tick, "trait_cost_refund",
                                  {"unit": source.inst_id,
                                   "amount": round(bonus, 3)})
        return result

    def _weaken_scale(self, source):
        """Outgoing-damage multiplier from an active weaken buff
        (``ep_dark_weaken``, 50% decaying to 0 over the 15s decay burst).
        The buff's ``mul`` is refreshed every tick by BuffSystem.update."""
        if source is None:
            return 1.0
        wk = self.buffs.get(source, "ep_dark_weaken")
        if wk is None:
            return 1.0
        return max(0.0, 1.0 + wk.get("mul", 0.0))

    def _enemy_mode_damage_scale(self, target, source, dmg_type):
        """Form-based damage reduction for mode-machine bosses (进化的
       本质 enemy_1519_bgball).  talentBlackboard ``mode_{n}``:
         - ``damage_resistance`` with ``direction`` (0 up / 1 right /
           2 down / 3 left) reduces PHYSICAL/MAGICAL damage from sources
           on that side (初生: 0.8 left, 进化: 0.8 right);
         - without ``direction`` the resistance applies to every non-self
           physical/magic source (完美: 0.99).
        Element (EP) and true damage pass through."""
        if dmg_type not in (DamageType.PHYSICAL, DamageType.MAGICAL):
            return 1.0
        if target is None or getattr(target, "side", 0) != 0:
            return 1.0
        if source is target:
            return 1.0
        sc = getattr(target, "skill_controller", None)
        if sc is None:
            return 1.0
        mp = getattr(sc, "mode_params", None) or {}
        cur = mp.get(getattr(sc, "mode_index", 0) or 0) or {}
        try:
            res = float(cur.get("damage_resistance") or 0.0)
        except (TypeError, ValueError):
            return 1.0
        if res <= 0:
            return 1.0
        scale = max(0.0, 1.0 - res)
        try:
            direction = int(cur.get("direction") or -1)
        except (TypeError, ValueError):
            direction = -1
        if direction < 0:
            return scale                      # global resistance
        if source is None:
            return 1.0                        # positional: unknown side
        dc = int(getattr(source, "col", 0) or 0) - \
            int(getattr(target, "col", 0) or 0)
        dr = int(getattr(source, "row", 0) or 0) - \
            int(getattr(target, "row", 0) or 0)
        if direction == 0 and dr < 0:         # up
            return scale
        if direction == 1 and dc > 0:         # right
            return scale
        if direction == 2 and dr > 0:         # down
            return scale
        if direction == 3 and dc < 0:         # left
            return scale
        return 1.0

    def try_enemy_branch_summon(self, branch_id, source):
        """Summon cadence hook for branch-based enemy spawns
        (talentBlackboard ``mode_{n}_summon.branch_id``, e.g. 进化的本质's
        畸变赘生物 / 畸变恶性瘤 every 5s / 3s / 2s).  Always emits an
        ``enemy_summon`` event; when the level data carries an enemy-branch
        mapping (``enemyBranches``/``enemyBranch``) the referenced enemies
        are spawned near the summoner, otherwise the event still exposes
        the cadence for UI / AI."""
        if branch_id is None:
            return False
        spawned = []
        raw = getattr(self, "raw", None) or {}
        branches = raw.get("enemyBranches") or raw.get("enemyBranch") or {}
        keys = branches.get(str(branch_id))
        if isinstance(keys, str):
            keys = [keys]
        keys = keys or []
        if keys and source is not None and not getattr(source, "dead", False):
            for _k in keys:
                try:
                    e = self.spawn_enemy(_k, 0, overrides={
                        "row": int(getattr(source, "row", 0) or 0),
                        "col": int(getattr(source, "col", 0) or 0)})
                except Exception:
                    e = None
                if e is not None:
                    spawned.append(e.inst_id)
        self.emit(self.tick, "enemy_summon",
                  {"unit": getattr(source, "inst_id", None),
                   "branch": str(branch_id),
                   "spawned": spawned,
                   "source": "mode_passive"})
        return bool(spawned)

    def _dispatch_buff_events(self, unit, event, source=None, target=None,
                              damage=None):
        """Run every buff's template actions for ``event`` on ``unit``."""
        for b in list(getattr(unit, "buffs", []) or []):
            tpl_key = b.get("template_key") or b.get("templateKey")
            if not tpl_key:
                continue
            try:
                self.buffs._fire(unit, b, event, source=source, target=target,
                                 damage=damage)
            except Exception as e:
                self.emit(self.tick, "buff_event_error",
                          {"unit": unit.inst_id, "buff": tpl_key,
                           "event": event, "error": str(e)})

    def battle_cost_add(self, amount):
        """Add deployment cost (skills like vanguard charge), capped."""
        self.cost = min(self.max_cost, self.cost + float(amount))

    # ---- cost timer precision (MECHANICS §10) ----
    def cost_period(self):
        """Effective cost-recovery period in seconds.

        Sentinels: <=0 or >=1e6 mean no natural recovery. Negative cost
        recovers at half speed (GlobalConsts.NEGATIVE_COST_RECOVERY_MULTIPLIER
        = 0.5), i.e. the period doubles."""
        cit = float(self.cost_increase_time)
        if cit <= 0 or cit >= 1e6:
            return cit
        mul = 1.0
        for m in self._cost_timer_modifiers:
            mul *= float(m.get("mul", 1.0))
        if self.cost < 0:
            neg = max(0.01, float(self._negative_recovery_multiplier or 0.5))
            mul *= 1.0 / neg
        return cit * mul

    def modify_cost_increase_time(self, mul_value):
        """Multiply the base cost-recovery period (game ModifyCostIncreaseTime)."""
        self.cost_increase_time = float(self._cost_base_increase_time) * \
            float(mul_value)
        return True

    def set_cost_increase_time(self, value):
        """Set the base cost-recovery period absolutely."""
        self.cost_increase_time = float(value)
        self._cost_base_increase_time = self.cost_increase_time
        return True

    def add_cost_timer_modifier(self, mul_value, source=None, priority=0,
                                cost_add_locked=False):
        """Register a cost-timer modifier (buff/rune): period *= mul_value.

        Mirrors BattleController.CostTimerModifier (dump.cs:375904):
        {source, value, priority, costAddLocked}; AddCostTimerModifier's
        4th parameter is costAddLocked, which freezes natural recovery
        while the modifier is active. Multiple multipliers multiply.
        """
        self._cost_timer_modifiers.append({
            "mul": float(mul_value), "priority": int(priority),
            "source": source, "cost_add_locked": bool(cost_add_locked)})
        return len(self._cost_timer_modifiers) - 1

    def _cost_locked_by_modifier(self):
        """True when any active cost-timer modifier locks cost addition
        (game CostTimerModifier.costAddLocked)."""
        return any(bool(m.get("cost_add_locked"))
                   for m in self._cost_timer_modifiers)

    def remove_cost_timer_modifier(self, source):
        """Remove all modifiers registered by ``source`` (identity compare)."""
        before = len(self._cost_timer_modifiers)
        self._cost_timer_modifiers = [
            m for m in self._cost_timer_modifiers
            if m.get("source") is not source]
        return len(self._cost_timer_modifiers) < before

    def lock_cost_increasement(self, is_lock, reason=1):
        """Lock/unlock natural cost recovery (CostLockReason:
        1=DIALOG_SHOW 2=AUTOCHESS_REST 3=SANDBOX_V3_WAIT_BASE)."""
        self._cost_locked = bool(is_lock)
        self._cost_lock_reason = int(reason)

    def cost_timer_state(self):
        """Read-only cost timer info for UI/AI: period, progress,
        seconds until next +1, locked."""
        cit = self.cost_period()
        locked = self._cost_locked or self._cost_locked_by_modifier()
        if not (cit > 0 and cit < 1e6):
            return {"period": float(cit), "progress": 0.0,
                    "nextCostIn": None, "locked": locked}
        prog = min(1.0, max(0.0, self._cost_acc / cit))
        return {"period": round(cit, 4), "progress": round(prog, 4),
                "nextCostIn": round(max(0.0, cit - self._cost_acc), 4),
                "locked": locked}

    # ---- fragility (\u8106\u5f31) ----
    def _fragility_scale(self, target, dmg_type):
        """Total fragility multiplier of a target for one damage type.
        Generic 'weak' scales every HP-damage type; 'weak[magic]',
        'weak[phy]' and 'weak[ep]' scale their own type (EP)."""
        scale = 1.0
        for b in getattr(target, "buffs", None) or []:
            key = b.get("key") or ""
            v = self._fragility_buff_value(b)
            if v is None or v <= 0.0:
                continue
            if key == "weak":
                if dmg_type != DamageType.ELEMENT:
                    scale *= v
            elif key == "weak[magic]" and dmg_type == DamageType.MAGICAL:
                scale *= v
            elif key == "weak[phy]" and dmg_type == DamageType.PHYSICAL:
                scale *= v
            elif key == "weak[ep]" and dmg_type == DamageType.ELEMENT:
                scale *= v
        return scale

    def _fragility_buff_value(self, b):
        """Scale value carried by a fragility buff entry (blackboard
        damage_scale[..] keys, then plain damage_scale, then value)."""
        bb = b.get("blackboard") or {}
        for k in ("damage_scale[mag]", "damage_scale[element]",
                  "damage_scale[phy]", "damage_scale[input]",
                  "damage_scale"):
            v = bb.get(k)
            if v is not None:
                return float(v)
        v = b.get("value")
        if v is not None:
            f = float(v)
            if f > 0:
                return f
        return None

    def apply_heal(self, target, amount, source=None, trait_immune=False,
                   ignore_heal_free=False, ep_scale=1.0, trait_ep=True):
        """Apply a heal. Therapist-subclass output heals to targets outside the
        2-3 inner zone are scaled by trait heal_scale (0.8, final multiply);
        pass trait_immune=True for trait-immune (exempt) heals.
        ``ep_scale`` scales the wandermedic element recovery with the heal
        amount (e.g. \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S3 0.25 per shot)."""
        if not trait_immune and source is not None:
            trait = getattr(source, "trait_system", None)
            if trait is not None:
                try:
                    amount = amount * trait.heal_falloff_scale(target, self)
                except Exception:
                    pass
        healed = target.heal(amount, ignore_heal_free=ignore_heal_free)
        if healed > 0 and not getattr(target, "dead", False) and \
                float(target.hp) >= float(target.max_hp) - 1e-9:
            self._dispatch_buff_events(target, "ON_OWNER_HP_FULL",
                                       source=source, target=target)
        # wandermedic (\u884c\u533b) trait: every heal action also recovers
        # ALL element bars of the target by source ATK x ep_heal_ratio
        # (0.5). Full-HP targets are valid heal targets, but heal-free
        # blocks the whole heal action including the EP recovery.
        if trait_ep and not trait_immune and source is not None \
                and not getattr(target, "dead", False):
            _wm = getattr(source, "trait_system", None)
            if _wm is not None and _wm.is_wandermedic():
                try:
                    if ignore_heal_free or not target.heal_free():
                        _ep_amt = _wm.ep_heal_amount() * float(ep_scale)
                        # \u54c8\u6d1b\u5fb7 S2 \u91cd\u75c7\u4f18\u5148:
                        # while active, EP recovery vs an over-half target is
                        # multiplied by the skill's trait_scale (1.2~2.5).
                        _sc = getattr(source, "skill_controller", None)
                        _act = getattr(_sc, "active", None) \
                            if _sc is not None else None
                        if _act is not None:
                            try:
                                _ep_amt = _ep_amt * \
                                    _act.wandermedic_ep_scale(target)
                            except Exception:
                                pass
                        if _ep_amt > 0:
                            self.buffs.recover_ep(
                                target, _ep_amt, source=source)
                except Exception:
                    pass
        # Doctor (char_4125_rdoc) talent 2 \u4ea4\u611f\u795e\u7ecf\u6fc0\u6d3b:
        # heal overflowing the target's max HP converts into a decaying shield
        # (no conversion when the heal itself is fully rejected: dead/heal-free).
        if healed < amount and source is not None \
                and not getattr(target, "dead", False) \
                and not getattr(target, "heal_free", lambda: False)():
            _ts = getattr(source, "talent_system", None)
            if _ts is not None:
                try:
                    if _ts.rdoc_overheal_params() is not None:
                        self.add_rdoc_shield(target, amount - healed, source)
                except Exception:
                    pass
        self.emit(self.tick, EventType.HEAL,
                  {"source": source.inst_id if source else None,
                   "target": target.inst_id, "amount": round(healed, 3)})
        return healed

    def add_barrier(self, unit, amount, max_value=None, source=None):
        """Add to a unit's barrier (\u5c4f\u969c absorption pool), capped at
        max_value when given (e.g. Thumpy talent: 300% of max HP)."""
        if unit is None or getattr(unit, "dead", False):
            return 0.0
        amount = float(amount)
        if amount <= 0:
            return 0.0
        before = float(getattr(unit, "barrier", 0.0) or 0.0)
        newv = before + amount
        if max_value is not None:
            newv = min(float(max_value), newv)
        unit.barrier = newv
        added = newv - before
        if added > 0:
            self.emit(self.tick, "barrier_added", {
                "unit": unit.inst_id, "amount": round(added, 3),
                "total": round(newv, 3),
                "source": source.inst_id if source else None})
        return added

    def add_rdoc_shield(self, target, amount, source=None):
        """Doctor talent 2 \u4ea4\u611f\u795e\u7ecf\u6fc0\u6d3b: overheal
        converts into a decaying shield. Game rdoc_t2[shield]: priority +1000
        single buff that accumulates; cap = source ATK * scale (scale=50 ->
        5000%) evaluated at each trigger; when the current shield is already
        >= that cap no addition happens; first decay 1s after creation then
        every 0.1s by ceil(current * |dec_rate| * 0.1)."""
        if target is None or getattr(target, "dead", False) or amount <= 0:
            return 0.0
        _ts = getattr(source, "talent_system", None)
        if _ts is None:
            return 0.0
        try:
            params = _ts.rdoc_overheal_params()
        except Exception:
            return 0.0
        if params is None:
            return 0.0
        rate, scale = params
        cap = float(source.attributes.get("atk") or 0) * scale
        if cap <= 0:
            return 0.0
        cur = float(getattr(target, "_rdoc_shield", 0.0) or 0.0)
        if cur >= cap:
            return 0.0
        added = min(cap, cur + amount) - cur
        if added <= 0:
            return 0.0
        target._rdoc_shield = cur + added
        target._rdoc_shield_cap = cap
        target._rdoc_decay_rate = rate
        if target._rdoc_next_decay_tick is None:
            target._rdoc_next_decay_tick = self.tick + 30   # 1s grace
        self._rdoc_shield_units[target.inst_id] = target
        self.emit(self.tick, "rdoc_shield_added", {
            "unit": target.inst_id, "amount": round(added, 3),
            "total": round(target._rdoc_shield, 3),
            "cap": round(target._rdoc_shield_cap, 3),
            "source": source.inst_id if source else None})
        return added

    def _update_rdoc_shields(self):
        """Tick decay of doctor-overheal shields (1s grace, then 0.1s
        cadence; per-tick decay = ceil(current * rate) so the game's
        floor-of-negative rounding gives magnitude ceil)."""
        if not self._rdoc_shield_units:
            return
        for uid, u in list(self._rdoc_shield_units.items()):
            if getattr(u, "dead", False) or u._rdoc_shield <= 0:
                u._rdoc_shield = 0.0
                u._rdoc_next_decay_tick = None
                self._rdoc_shield_units.pop(uid, None)
                continue
            nd = u._rdoc_next_decay_tick
            if nd is None or self.tick < nd:
                continue
            import math as _math
            dec = _math.ceil(u._rdoc_shield * u._rdoc_decay_rate - 1e-9)
            if dec <= 0 and u._rdoc_shield > 0:
                dec = 1
            u._rdoc_shield = max(0.0, u._rdoc_shield - dec)
            self.emit(self.tick, "rdoc_shield_decay", {
                "unit": u.inst_id, "decay": round(float(dec), 3),
                "total": round(u._rdoc_shield, 3)})
            if u._rdoc_shield <= 0:
                u._rdoc_shield = 0.0
                u._rdoc_next_decay_tick = None
                self._rdoc_shield_units.pop(uid, None)
            else:
                u._rdoc_next_decay_tick = self.tick + 3   # 0.1s

    def add_buff(self, unit, buff):
        return self.buffs.apply(unit, buff)

    def _register_rally_point(self, unit):
        """Register a player token / trap as a TRAP_OR_ITEM rally point
        (RallyPointReborn reborns operators at these)."""
        if unit is None or getattr(unit, "dead", False):
            return
        cat = "TRAP_OR_ITEM"
        pts = self._rally_points.setdefault(cat, [])
        if unit.inst_id not in pts:
            pts.append(unit.inst_id)

    def _unregister_rally_point(self, unit):
        """Remove a token / trap from every rally-point category when it
        dies or is withdrawn."""
        if unit is None:
            return
        for cat, pts in list(self._rally_points.items()):
            if unit.inst_id in pts:
                pts.remove(unit.inst_id)

    def is_fogged(self, unit):
        """A unit standing on a tile marked out-of-view by MarkFogView is
        hidden by the fog (cannot be selected as a normal attack target).
        Tiles with no fog entry are always visible."""
        if unit is None:
            return False
        return self._fog_view.get(
            (int(getattr(unit, "row", -1) or -1),
             int(getattr(unit, "col", -1) or -1))) is False

    def add_abnormal(self, unit, flag, seconds, source=None):
        return self.buffs.set_abnormal(unit, flag, seconds, source=source)

    def add_ep(self, unit, ep_type, amount, source=None):
        return self.buffs.update_ep(unit, ep_type, amount, source=source)

    # ---- attribute steal (StealAttributeAbility, dump.cs:543106) ----
    def steal_attribute(self, source, target, attr, amount, max_total=None,
                        floor=1.0, key="attr"):
        """Steal ``amount`` of ``attr`` from ``target`` to ``source``.
        Per-cast value is capped by the target's remaining value (kept
        >= ``floor``) and by the source's total budget (``max_total``).
        Both sides receive cumulative additive buffs
        (``steal[{key}][target]`` / ``steal[{key}][source]``) that are
        cleaned when the source retreats/dies or its skill ends
        (StealAttributeAbility.OnDetached semantics).  The source's
        accumulated total is exposed in ``_steal_values`` and snapshots."""
        if source is None or target is None or target is source:
            return 0.0
        if getattr(target, "dead", False) or getattr(source, "dead", False):
            return 0.0
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return 0.0
        if amount <= 0:
            return 0.0
        key = str(key or "attr")
        sid = getattr(source, "inst_id", id(source))
        acc = self._steal_values.get((sid, key), 0.0)
        budget = float("inf")
        if max_total is not None:
            try:
                mt = float(max_total)
            except (TypeError, ValueError):
                mt = 0.0
            if mt > 0:
                budget = max(0.0, mt - acc)
                self._steal_max[(sid, key)] = mt
        try:
            cur_t = float(target.attributes.get(attr) or 0.0)
        except (TypeError, ValueError):
            cur_t = 0.0
        avail = max(0.0, cur_t - float(floor))
        steal = min(amount, avail, budget)
        if steal <= 0:
            return 0.0
        total = acc + steal
        tkey = f"steal[{key}][target]"
        skey = f"steal[{key}][source]"
        self.buffs.remove(target, tkey)
        self.buffs.remove(source, skey)
        self.add_buff(target, {"key": tkey, "stat": attr, "add": -total,
                               "remaining_ticks": 1 << 30, "layers": 1,
                               "source": source})
        self.add_buff(source, {"key": skey, "stat": attr, "add": total,
                               "remaining_ticks": 1 << 30, "layers": 1,
                               "source": source})
        self._steal_values[(sid, key)] = total
        self.emit(self.tick, "steal", {
            "source": getattr(source, "inst_id", None),
            "target": getattr(target, "inst_id", None),
            "attr": attr, "amount": round(steal, 3),
            "total": round(total, 3), "key": key})
        return steal

    def _clear_steal_buffs(self, unit):
        """Remove every steal buff this unit caused (its own gain plus the
        targets' losses) and reset its steal accumulator - the game's
        StealAttributeAbility.OnDetached behaviour on retreat / death /
        skill end."""
        if unit is None:
            return
        for u in ([unit] + list(self.operators) + list(self.tokens) +
                  list(self.enemies)):
            before = len(getattr(u, "buffs", None) or [])
            u.buffs = [b for b in (getattr(u, "buffs", None) or [])
                       if not (str(b.get("key", "")).startswith("steal[")
                               and b.get("source") is unit)]
            if len(u.buffs) != before:
                try:
                    self.buffs._rebuild_modifiers(u)
                except Exception:
                    pass
        sid = getattr(unit, "inst_id", id(unit))
        for k in [k for (s, k) in list(self._steal_values) if s == sid]:
            self._steal_values.pop((sid, k), None)
            self._steal_max.pop((sid, k), None)

    def _apply_attack_steal(self, op, target, act):
        """Per-hit attribute steal from an active skill's blackboard
        (``attack@steal_atk_speed`` / ``def_steal``; e.g. 伊内丝 S2,
        薇薇安娜 S2, 寻澜 S2 洞悉) or a token's steal talent blackboard
        (e.g. 缪尔赛思流形: ``steal_atk``/``steal_def``)."""
        ae = (getattr(act, "attack_effects", {}) or {}
              if act is not None else {})
        bb = (getattr(getattr(act, "skill", None), "blackboard", {}) or {}
              if act is not None else {})
        tsb = getattr(op, "token_steal_bb", None) or {}
        specs = []
        sa = ae.get("steal_atk_speed")
        if sa:
            specs.append(("attackSpeed", float(sa),
                          float(ae.get("steal_atk_speed_max") or 0.0)
                          or None, "atk_speed"))
        ds = bb.get("def_steal")
        if ds:
            specs.append(("def", float(ds),
                          float(bb.get("def_steal_max") or 0.0)
                          or None, "def"))
        ta = tsb.get("steal_atk")
        if ta:
            specs.append(("atk", float(ta),
                          float(tsb.get("steal_atk_max") or 0.0)
                          or None, "atk"))
        td = tsb.get("steal_def")
        if td:
            specs.append(("def", float(td),
                          float(tsb.get("steal_def_max") or 0.0)
                          or None, "def"))
        for attr, amount, cap, key in specs:
            if amount <= 0:
                continue
            try:
                self.steal_attribute(op, target, attr, amount, cap,
                                     key=key)
            except Exception:
                pass

    def enemy_normal_attack(self, enemy, target):
        """Basic attack from enemy to operator (physical default)."""
        atk = enemy.attributes.get("atk")
        self.apply_damage(target, atk, DamageType.PHYSICAL, source=enemy)
        sc = getattr(enemy, "skill_controller", None)
        if sc is not None:
            sc.on_enemy_attack()
        self._dispatch_buff_events(enemy, "ON_AFTER_ATTACK",
                                   source=enemy, target=target)
        self.emit(self.tick, EventType.ATTACK,
                  {"unit": enemy.inst_id, "target": target.inst_id})

    def on_enemy_ability_spell_on(self, enemy):
        """Enemy normal attack starts (spell-on): fire ON_BEFORE_ABILITY_SPELL_ON
        on the enemy's buffs so range-bound listeners react (e.g. \u9152\u795e
        T2 \u5760\u68a6: enemies in her attack range take 70 sanity EP on
        each normal attack). The per-buff source is preserved so element
        damage is attributed to the operator."""
        for b in list(getattr(enemy, "buffs", []) or []):
            tpl_key = b.get("template_key") or b.get("templateKey")
            if not tpl_key:
                continue
            try:
                self.buffs._fire(enemy, b, "ON_BEFORE_ABILITY_SPELL_ON",
                                 source=b.get("source"), target=enemy)
            except Exception as e:
                self.emit(self.tick, "buff_event_error",
                          {"unit": enemy.inst_id, "buff": tpl_key,
                           "event": "ON_BEFORE_ABILITY_SPELL_ON",
                           "error": str(e)})

    # ---- \u70db\u714c T2 \u7edd\u5904\u91cd\u71c3 (rebirth talent) ----
    def _blaze2_reborn_params(self, op):
        entry = self.buffs.get(op, "blaze2_t_2")
        if entry is None:
            return None
        bb = entry.get("blackboard") or {}
        return (float(bb.get("hp_recovery_per_sec_by_max_hp_ratio") or 0.0),
                float(bb.get("stun") or 5.0),
                float(bb.get("dynamic") or 6000.0))

    def _try_blaze2_reborn(self, op):
        """Enter the downed (\u91cd\u71c3) state: interrupt the skill, clear
        own buffs, hp -> 1, gain the 6000 barrier, 0.3s undead+invincible,
        block/attack/heal disabled, %maxHp regen per second. Can trigger
        again after each revival (PRTS: \u6b21\u6570\u4e0d\u9650)."""
        if getattr(op, "_reborn_state", False):
            return False
        params = self._blaze2_reborn_params(op)
        if params is None or params[0] <= 0:
            return False
        op._reborn_state = True
        sc = getattr(op, "skill_controller", None)
        if sc is not None:
            try:
                sc.interrupt_active()
            except Exception:
                pass
            op.sp = 0.0
        # \u6e05\u7a7a\u81ea\u8eabbuff: keep only the talent listeners and
        # the state markers (game retained-buff list).
        keep = {"blaze2_t_1", "blaze2_t_2",
                "blaze2_t_2[reborn_state]",
                "blaze2_t_2[reborn_state][trigger]"}
        op.buffs = [b for b in op.buffs if b.get("key") in keep]
        self.buffs._rebuild_modifiers(op)
        op._pending_attack = None
        op.hp = 1.0
        op.dead = False
        op.barrier = float(params[2])
        # marker buffs WITHOUT template keys: the game's reborn_state
        # template carries ON_TAKE_DAMAGE BlockDamage (the barrier), which
        # would double-settle with the unit.barrier pool, so the Python
        # driver owns the barrier/regen/revive entirely.
        self.add_buff(op, {"key": "blaze2_t_2[reborn_state]",
                           "remaining_ticks": 30 * 3600, "layers": 1,
                           "source": op,
                           "blackboard": {"dynamic": float(params[2])}})
        self.add_buff(op, {"key": "blaze2_t_2[reborn_state][trigger]",
                           "remaining_ticks": 30 * 3600, "layers": 1,
                           "source": op, "blackboard": {}})
        self.add_abnormal(op, AbnormalFlag.INVINCIBLE, 0.3, source=op)
        self.add_abnormal(op, AbnormalFlag.UNDEADABLE, 0.3, source=op)
        self.add_abnormal(op, AbnormalFlag.HEAL_FREE, 1 << 20, source=op)
        self.add_abnormal(op, AbnormalFlag.DISARMED, 1 << 20, source=op)
        self.add_abnormal(op, AbnormalFlag.SILENCED, 1 << 20, source=op)
        for f in list(op.abnormal):
            if f in (AbnormalFlag.STUNNED, AbnormalFlag.FROZEN,
                     AbnormalFlag.DOZE, AbnormalFlag.UNMOVABLE,
                     AbnormalFlag.LEVITATE, AbnormalFlag.PALSY):
                op.clear_flag(f)
        self.emit(self.tick, "blaze2_reborn", {
            "unit": op.inst_id, "barrier": round(op.barrier, 3),
            "regenPerSec": round(float(op.max_hp) * params[0], 3)})
        return True

    def _tick_blaze2_reborn(self, op, dt):
        """While downed: recover %maxHp per second; at full HP revive and
        stun enemies within radius 1.7 (PRTS) for stun seconds."""
        params = self._blaze2_reborn_params(op)
        if params is None or params[0] <= 0:
            return
        ratio = params[0]
        op.hp = min(float(op.max_hp), op.hp + float(op.max_hp) * ratio * dt)
        if op.hp >= float(op.max_hp) - 1e-9:
            self._blaze2_revive(op, params)

    def _blaze2_revive(self, op, params):
        ratio, stun, dynamic = params
        op._reborn_state = False
        for k in ("blaze2_t_2[reborn_state]",
                  "blaze2_t_2[reborn_state][trigger]",
                  "blaze2_t_2[reborn_state][vfx1]",
                  "blaze2_t_2[reborn_state][vfx2]"):
            self.buffs.remove(op, k)
        for f in (AbnormalFlag.HEAL_FREE, AbnormalFlag.DISARMED,
                  AbnormalFlag.SILENCED):
            op.clear_flag(f)
        op.barrier = 0.0
        op.hp = float(op.max_hp)
        radius = 1.7
        opx = float(op.pos_x if op.pos_x is not None else op.col)
        opy = float(op.pos_y if op.pos_y is not None else op.row)
        stunned = []
        for e in list(self.enemies):
            if e.dead:
                continue
            ex = float(e.pos_x if e.pos_x is not None else e.col)
            ey = float(e.pos_y if e.pos_y is not None else e.row)
            if (ex - opx) ** 2 + (ey - opy) ** 2 <= radius * radius + 1e-6:
                self.add_abnormal(e, AbnormalFlag.STUNNED, float(stun),
                                  source=op)
                stunned.append(e.inst_id)
        # brief undead+invincible during the revive animation (PRTS)
        self.add_abnormal(op, AbnormalFlag.INVINCIBLE, 0.3, source=op)
        self.add_abnormal(op, AbnormalFlag.UNDEADABLE, 0.3, source=op)
        self.emit(self.tick, "blaze2_revive", {
            "unit": op.inst_id, "stunSeconds": round(float(stun), 3),
            "stunned": stunned})

    # ================= dollkeeper (\u5080\u5121\u5e08) substitute =================
    def _doll_token_stats(self, op):
        """Attributes of the operator's substitute token (e.g. \u98ce\u4e38
        \u7eb8\u5076) from the summon registry; None when none shipped."""
        try:
            for entry in (self._summons.get(op.char_id) or []):
                tk = entry.get("tokenKey")
                data = self._char_base(tk)
                if not data:
                    continue
                ph = (data.get("phases") or [{}])[0]
                a = ((ph.get("attributesKeyFrames") or [{}])[0].get("data")
                     or {})
                if a.get("maxHp"):
                    return {
                        "maxHp": float(a["maxHp"]),
                        "atk": float(a.get("atk") or 0.0),
                        "def": float(a.get("def") or 0.0),
                    }
        except Exception:
            pass
        return None

    def _try_dollkeeper(self, op):
        """Dollkeeper trait: a lethal hit swaps the operator into its
        <\u66ff\u8eab> form (blockCnt 0, no taunt, doll stats when shipped)
        instead of retreating. After `duration` seconds the operator body
        returns with full HP and 0 SP; a lethal hit while already a doll
        defeats it normally."""
        if getattr(op, "dead", False) or getattr(op, "_doll_state", False):
            return False
        trait = getattr(op, "trait_system", None)
        if trait is None or not trait.is_dollkeeper():
            return False
        duration = trait.doll_duration()
        if duration <= 0:
            return False
        base = op.attributes.base
        op._doll_original = {
            "maxHp": float(base.get("maxHp") or 0.0),
            "atk": float(base.get("atk") or 0.0),
            "def": float(base.get("def") or 0.0),
            "blockCnt": float(base.get("blockCnt") or 0.0),
            "tauntLevel": float(base.get("tauntLevel") or 0.0),
        }
        doll = self._doll_token_stats(op)
        if doll:
            base["maxHp"] = doll["maxHp"]
            base["atk"] = doll["atk"]
            base["def"] = doll["def"]
        base["blockCnt"] = 0.0
        base["tauntLevel"] = 0.0
        op._doll_state = True
        op._doll_remaining = int(round(duration * 30.0))
        op.max_hp = max(1.0, float(base.get("maxHp") or 1.0))
        op.hp = op.max_hp
        op.sp = 0.0
        # release enemies the body was blocking (the doll cannot block)
        for e in list(getattr(op, "blocked_enemies", []) or []):
            if getattr(e, "blocked_by", None) is op:
                e.blocked_by = None
                if e.state in (EnemyState.COMBAT, EnemyState.ATTACK):
                    try:
                        e.set_state(EnemyState.MOVE)
                    except Exception:
                        pass
            op.remove_blockee(e)
        self.emit(self.tick, "doll_state",
                  {"unit": op.inst_id, "type": "swap",
                   "duration": round(duration, 3)})
        return True

    def _doll_restore(self, op):
        """Doll timer expired: the operator body replaces the substitute
        with full HP and 0 SP (PRTS/fandom dollkeeper behaviour)."""
        orig = getattr(op, "_doll_original", None)
        if orig:
            base = op.attributes.base
            for k, v in orig.items():
                base[k] = v
            op.max_hp = max(1.0, float(base.get("maxHp") or 1.0))
            op.hp = op.max_hp
        op._doll_state = False
        op._doll_remaining = 0
        op.sp = 0.0
        # reset the SP recovery accumulator so the same tick's auto
        # recovery does not immediately add +1 right after the reset
        op._sp_cooldown_remaining = 1.0
        self.emit(self.tick, "doll_state",
                  {"unit": op.inst_id, "type": "restore"})

    # ================= wave / spawn =================
    def spawn_enemy(self, key, route_index, source_ev=None, overrides=None):
        """Create an enemy from enemyRoster/enemy_database at route start.
        Level resolution order: custom overrides > level enemyDbRefs > 0.
        ``overrides`` (custom enemies) may carry level / attributes / skills."""
        if not key:
            self.emit(self.tick, "spawn_skipped",
                      {"reason": "missing_enemy_key", "route": route_index})
            return None
        # level rune: enemy key replacement (level_enemy_replace)
        if getattr(self, "_rune_enemy_replace", None) and \
                key in self._rune_enemy_replace:
            self.emit(self.tick, "enemy_replaced",
                      {"key": key,
                       "value": self._rune_enemy_replace[key]})
            key = self._rune_enemy_replace[key]
        level = (overrides or {}).get("level")
        if level is None:
            level = self._enemy_db_level(key)
        merged = self.store.build_merged_enemy(key, level)
        if hasattr(self.store, "_resolved_variants") and \
                key in self.store._resolved_variants:
            self.emit(self.tick, "enemy_variant_resolved",
                      {"key": key, "base": self.store._resolved_variants[key]})
        if (overrides or {}).get("attributes"):
            merged["data"] = dict(merged["data"])
            merged["data"]["attributes"] = dict(
                merged["data"].get("attributes") or {})
            merged["data"]["attributes"].update(overrides["attributes"])
        if (overrides or {}).get("skills") is not None:
            merged["data"] = dict(merged["data"])
            merged["data"]["skills"] = overrides["skills"]
        data = merged["data"]
        attrs = dict(data.get("attributes") or {})
        attrs = {k: (v if v is not None else 0.0) for k, v in attrs.items()}
        # top-level enemy_database fields (not part of AttributesData)
        for _ek in ("rangeRadius", "viewRadius"):
            _v = data.get(_ek)
            if _v is not None:
                attrs.setdefault(_ek, _v)
        if route_index is None:
            route_index = 0
        if not (0 <= route_index < len(self.routes)):
            return None
        route = self.routes[route_index]
        if not isinstance(route, dict):
            # null route entries in official gamedata levels keep their
            # list position but cannot host spawns
            self.emit(self.tick, "spawn_skipped",
                      {"reason": "null_route", "route": route_index})
            return None
        start = route.get("startPosition") or {"row": 0, "col": 0}
        # custom levels / editors may spawn at an explicit tile instead of
        # the route start (overrides > wave-timeline event > route start)
        sp_row, sp_col = None, None
        for _src in (overrides, source_ev):
            if isinstance(_src, dict) and _src.get("row") is not None:
                sp_row = int(_src.get("row"))
                sp_col = int(_src.get("col"))
                break
        if sp_row is None:
            sp_row = start.get("row", 0)
        if sp_col is None:
            sp_col = start.get("col", 0)
        sp_row = max(0, min(self.map.rows - 1, sp_row))
        sp_col = max(0, min(self.map.cols - 1, sp_col))
        # level runes: enemy attribute multipliers / additives
        _em = getattr(self, "_rune_enemy_mul", None)
        _ea = getattr(self, "_rune_enemy_add", None)
        if _em or _ea:
            _EMAP = {"atk": "atk", "def": "def", "max_hp": "maxHp",
                     "magic_resistance": "magicResistance",
                     "attack_speed": "attackSpeed",
                     "move_speed": "moveSpeed",
                     "rangeRadius": "rangeRadius",
                     "massLevel": "massLevel"}
            for _k, _m in (_em or {}).items():
                _sk = _EMAP.get(_k, _k)
                if _sk == "rangeRadius":
                    # attack-range runes scale the EFFECTIVE range; a
                    # missing / melee (<=0) radius starts from 1.5
                    _cur = attrs.get("rangeRadius")
                    if _cur is None or float(_cur or 0) <= 0:
                        _cur = 1.5
                    attrs["rangeRadius"] = float(_cur) * _m
                elif _sk in attrs and attrs[_sk] is not None:
                    attrs[_sk] = float(attrs[_sk]) * _m
            for _k, _a in (_ea or {}).items():
                _sk = _EMAP.get(_k, _k)
                if _sk in attrs and attrs[_sk] is not None:
                    attrs[_sk] = float(attrs[_sk]) + _a
        enemy = Enemy(key, Attributes(attrs), route_index=route_index,
                      row=sp_row, col=sp_col,
                      level=level, route=route, game_map=self.map)
        enemy.battle = self
        enemy._spawn_event = dict(source_ev or {})
        enemy._wave_start_time = float(
            (source_ev or {}).get("waveStart", 0.0) or 0.0)
        enemy._fragment_start_time = float(
            (source_ev or {}).get("fragmentStart", 0.0) or 0.0)
        enemy._wave_index = (source_ev or {}).get("wave")
        enemy._fragment_index = (source_ev or {}).get("fragment")
        enemy._managed_by_scheduler = (source_ev or {}).get(
            "managedByScheduler") is not False
        enemy._dont_block_wave = bool((source_ev or {}).get(
            "dontBlockWave", False))
        enemy._block_fragment = bool((source_ev or {}).get(
            "blockFragment", False))
        enemy.init_route(self.map)
        enemy.is_flying = bool((overrides or {}).get("is_flying")) or \
            self.store.is_flying_enemy(key)
        if enemy.is_flying:
            enemy.set_flag(3, 10 ** 9)   # BLOCK_FREE: drones cannot block
        enemy.life_point_reduce = data.get("lifePointReduce") or 1
        enemy.level_type = int(data.get("levelType") or 0)
        enemy.move_speed = float(attrs.get("moveSpeed") or 1.0)
        enemy.block_volume = int(attrs.get("blockCnt") or 1)
        enemy.sp_max = float((data.get("spData") or {}).get("maxSp") or 0)
        enemy.sp = float((data.get("spData") or {}).get("initSp") or 0)
        enemy._sp_data = data.get("spData") or {}
        enemy.talent_blackboard = {
            b.get("key"): (b.get("value") if b.get("value") is not None
                           else b.get("valueStr"))
            for b in (data.get("talentBlackboard") or [])
            if b.get("key") is not None}
        enemy.is_unharmful = bool((source_ev or {}).get(
            "isUnharmfulAndAlwaysCountAsKilled"))
        # skills
        skills = data.get("skills") or []
        enemy.skills = skills
        if skills:
            from .skills import EnemySkillController
            entries = self.store.enemy_skills(key)
            enemy.skill_controller = EnemySkillController(enemy, self, entries,
                                                          store=self.store)
        self._apply_enemy_skill_runes(enemy)
        self._apply_enemy_talent_runes(enemy)
        enemy.on_spawn(self.tick)
        self._apply_global_buffs(enemy)
        self._apply_enemy_prts_prefab_buffs(enemy)
        self.enemies.append(enemy)
        self._dispatch_buff_events(enemy, "ON_OWNER_BORN",
                                   source=enemy, target=enemy)
        self._dispatch_buff_events(enemy, "ON_OWNER_LOCATE",
                                   source=enemy, target=enemy)
        self.emit(self.tick, EventType.ENEMY_SPAWN, {
            "key": key, "routeIndex": route_index,
            "row": enemy.row, "col": enemy.col})
        self.prts.bind_enemy(enemy)
        return enemy

    def spawn_enemy_directive(self, key, row, col, route_index=0):
        """Summon-type skill placeholder: spawn at explicit tile."""
        merged = self.store.build_merged_enemy(key, 0)
        data = merged["data"]
        attrs = {k: (v if v is not None else 0.0)
                 for k, v in (data.get("attributes") or {}).items()}
        for _ek in ("rangeRadius", "viewRadius"):
            _v = data.get(_ek)
            if _v is not None:
                attrs.setdefault(_ek, _v)
        enemy = Enemy(key, Attributes(attrs), route_index=route_index,
                      row=row, col=col, route=self.routes[route_index],
                      game_map=self.map)
        enemy.battle = self
        enemy.init_route(self.map)
        enemy.pos_x, enemy.pos_y = float(col), float(row)
        enemy.on_spawn(self.tick)
        enemy.state = EnemyState.MOVE
        self.enemies.append(enemy)
        self._dispatch_buff_events(enemy, "ON_OWNER_BORN",
                                   source=enemy, target=enemy)
        self._dispatch_buff_events(enemy, "ON_OWNER_LOCATE",
                                   source=enemy, target=enemy)
        self.prts.bind_enemy(enemy)
        return enemy

    def execute_branch(self, branch_id, is_loop=False):
        """Advance a level branch's cursor and schedule the next phase.

        Game model (Scheduler.BranchRuntime / Nodes.MoveNextLevelBranch):
        each branch keeps a phase cursor; every trigger moves it to the next
        phase and deals that phase like a fragment (phase.preDelay +
        action.preDelay / count / interval), with random spawn groups
        resolved via the battle RNG and hiddenGroup rune gating applied per
        action. Returns the number of scheduled events (0 if none).
        """
        branches = self.raw.get("branches") or {}
        branch = branches.get(branch_id)
        if not branch:
            return 0
        phases = branch.get("phases") or []
        if not phases:
            return 0
        idx = self._branch_cursors.get(branch_id, 0)
        if idx >= len(phases):
            if not is_loop:
                return 0
            idx = 0
        self._branch_cursors[branch_id] = idx + 1
        return self._schedule_branch_phase(branch_id, idx)

    def execute_branch_random(self, branch_id, not_repeat=False,
                              block_game_finish=False):
        """Pick a random phase of a branch and deal it (Nodes.
        PickRandomBranchPhase / Scheduler.TryPickRandomBranch*)."""
        branches = self.raw.get("branches") or {}
        branch = branches.get(branch_id)
        if not branch:
            return 0
        phases = branch.get("phases") or []
        if not phases:
            return 0
        if not_repeat:
            used = self._branch_random_used.setdefault(branch_id, set())
            cand = [i for i in range(len(phases)) if i not in used]
            if not cand:
                used.clear()
                cand = list(range(len(phases)))
            idx = cand[self.rng.next(len(cand))]
            used.add(idx)
        else:
            idx = self.rng.next(len(phases))
        return self._schedule_branch_phase(branch_id, idx)

    def _schedule_branch_phase(self, branch_id, phase_idx):
        """Schedule one branch phase's actions as a wave-like stream from
        the current battle time."""
        branches = self.raw.get("branches") or {}
        branch = branches.get(branch_id) or {}
        phases = branch.get("phases") or []
        if phase_idx >= len(phases):
            return 0
        phase = phases[phase_idx]
        from .waves import build_wave_timeline, WaveScheduler
        synthetic = [{
            "preDelay": None,
            "postDelay": None,
            "fragments": [{
                "preDelay": phase.get("preDelay"),
                "actions": phase.get("actions") or [],
            }],
        }]
        tl = build_wave_timeline(synthetic, rng=self.rng)
        now = self.tick / TIME_ROUGH_LOGIC_RATE
        for ev in tl:
            ev["t"] = round(now + ev.get("t", 0.0), 3)
        sched = WaveScheduler(tl, self)
        self._branch_phases.append({
            "branch": branch_id, "phase": phase_idx,
            "scheduler": sched,
        })
        self.emit(self.tick, "level_branch",
                  {"branch": branch_id, "phase": phase_idx,
                   "count": len(tl), "randomGroups": sched.random_groups})
        return len(tl)


    def activate_predefined(self, key):
        """Activate a predefined token/trap from the level's predefines."""
        spawned = self.activate_predefined_alias(key)
        self.emit(self.tick, "predefined_activated",
                  {"key": key, "spawned": len(spawned)})

    def displace(self, enemy, dr, dc, distance, source=None, duration=None,
                 kind="effect", force_level=None):
        """Push/pull an enemy along a grid direction by ``distance`` tiles.

        Game model (PRTS summon / deploy-weight):
          - push: instantaneous impulse -> constant-deceleration slide whose
            ideal distance comes from PUSH_FORCE_TABLE (projectile/effect);
          - pull: force acts for 0.5-1.0s (PULL_FORCE_TABLE), decelerating
            motion ending at the front of the puller (stop radius 0.6708).
        The enemy cannot attack/block while displaced. ``kind`` is
        'effect'/'projectile'/'pull' and is exposed in the snapshot.
        """
        if enemy is None or enemy.dead or distance <= 0:
            return False
        if enemy.displacement is not None:
            return False
        # displacement breaks the current block (the enemy slides away)
        if enemy.blocked_by is not None:
            blk = enemy.blocked_by
            if hasattr(blk, "remove_blockee"):
                blk.remove_blockee(enemy)
            enemy.blocked_by = None
            if enemy.state == EnemyState.COMBAT:
                enemy.state = EnemyState.MOVE
        if duration is None:
            duration = max(0.3, min(0.9, distance * 0.18 + 0.3))
        if duration <= 0:
            duration = 0.3
        # constant deceleration: v(t) = 2*remaining/t_remaining, stops exactly
        # at the destination when both reach 0.
        enemy.displacement = {
            "dr": dr, "dc": dc, "remaining": distance,
            "total": distance, "speed": distance / duration,
            "dest_x": float(enemy.col) + dc * distance,
            "dest_y": float(enemy.row) + dr * distance,
            "duration_remaining": duration, "duration_total": duration,
            "kind": kind, "force_level": force_level,
            "source": source,
        }
        self.emit(self.tick, "displace",
                  {"unit": enemy.inst_id, "dr": dr, "dc": dc,
                   "distance": round(distance, 3),
                   "kind": kind, "force_level": force_level,
                   "source": source.inst_id if source else None})
        return True

    def on_displacement_end(self, enemy):
        """After a slide ends. Falling into a hole is handled by the tile
        effects pass (tile_effects._apply_hole -> enemy_falldown)."""
        if enemy.dead:
            return
        self.emit(self.tick, "displacement_end",
                  {"unit": enemy.inst_id, "row": enemy.row,
                   "col": enemy.col})

    def on_enemy_reach_exit(self, enemy):
        enemy.reach_exit = True
        enemy.state = EnemyState.REACH_EXIT
        if not enemy.is_unharmful:
            self.life_point = max(0, self.life_point - enemy.life_point_reduce)
            self.stats["leaks"] += enemy.life_point_reduce
            self.stats["lifeLost"] += enemy.life_point_reduce
            self.emit(self.tick, EventType.LIFE_POINT_LOST,
                      {"amount": enemy.life_point_reduce,
                       "lifePoint": self.life_point})
        self.emit(self.tick, EventType.ENEMY_REACH_EXIT,
                  {"unit": enemy.inst_id, "key": enemy.enemy_key,
                   "row": enemy.row, "col": enemy.col,
                   "routeIndex": enemy.route_index})
        enemy.dead = True
        enemy._death_reason = "REACH_EXIT"
        self._dispatch_buff_events(enemy, "ON_OWNER_REACH_EXIT",
                                   source=enemy, target=enemy)
        self._dispatch_buff_events(enemy, "ON_OWNER_FINISH",
                                   source=enemy, target=enemy)

    # ================= operator actions =================
    def deploy(self, char_id, row, col, direction=1, auto_summon=False,
               skill_index=None):
        if len(self.operators) >= self.character_limit:
            return False, "character_limit"
        data = self._char_base(char_id)
        if data is None:
            return False, "no_character_data"
        sk_data = self._char_skills(char_id)
        if skill_index is not None:
            try:
                skill_index = int(skill_index)
            except (TypeError, ValueError):
                return False, "invalid_skill"
            if skill_index < 0 or skill_index >= len(sk_data):
                return False, "invalid_skill"
        # melee (position 1) needs ground (buildableType & 1); ranged
        # (position 2) needs highland (buildableType & 2).
        pos = int(data.get("position") or 1)
        mask = 2 if pos == 2 else 1
        if self.map.buildable(row, col, mask) is False:
            return False, "not_buildable"
        t = self.map.tile(row, col)
        if t is None or t.buildable_type is None:
            return False, "not_buildable"
        if any((o.row, o.col) == (row, col) for o in self.operators):
            return False, "occupied"
        if (row, col) in getattr(self, "_rune_forbidden", set()):
            return False, "forbidden_location"
        if char_id in getattr(self, "_rune_excluded", set()):
            return False, "excluded"
        # redeploy cooldown (respawnTime after retreat/death)
        until = self._redeploy_until.get(char_id, 0)
        if self.tick < until:
            return False, "on_cooldown"
        # A web deployment may choose a skill for this placement without
        # rewriting the persistent squad.  All other squad fields still come
        # from the configured entry.
        entry = dict(self._squad_entry(char_id))
        if skill_index is not None:
            entry["skillIndex"] = skill_index
        phase = int(entry.get("phase", 2) if entry.get("phase") is not None else 2)
        level = int(entry.get("level", 1) or 1)
        potential = int(entry.get("potential", 0) or 0)
        attrs = self._char_attrs(data, phase, level)
        for k, v in self._potential_bonus(data, potential).items():
            attrs[k] = (attrs.get(k) or 0) + v
        # module (\u6a21\u7ec4) attribute bonuses: squad entry may carry
        # moduleId + moduleLevel (or a nested module {id, level}); the
        # per-phase bb stats from module_stats.json are added on top.
        _mod_id = entry.get("moduleId") or (entry.get("module") or {}).get("id")
        _mod_lv = entry.get("moduleLevel") or (entry.get("module") or {}).get("level")
        _mod_lv = 3 if _mod_lv is None else int(_mod_lv or 1)
        _MOD_STAT = {"max_hp": "maxHp", "atk": "atk", "def": "def",
                     "attack_speed": "attackSpeed",
                     "magic_resistance": "magicResistance", "cost": "cost",
                     "respawn_time": "respawnTime", "block_cnt": "blockCnt"}
        _mod_bb = {}
        try:
            _mod_bb = self.store.module_stat_bonus(_mod_id, _mod_lv) or {}
        except Exception:
            _mod_bb = {}
        for _mk, _mv in _mod_bb.items():
            _sk = _MOD_STAT.get(str(_mk).lower())
            if _sk is not None:
                attrs[_sk] = (attrs.get(_sk) or 0) + float(_mv)
        # \u4fe1\u8d56\u52a0\u6210 (trust): squad entry may carry ``trust``
        # 0-200 (\u6ee1\u4fe1\u8d56 200\uff09; the 200%\u503c from
        # trust_prts.json scales linearly and floors per stat.
        _trust = 0
        try:
            _trust = int(entry.get("trust") or 0)
        except (TypeError, ValueError):
            _trust = 0
        _trust = max(0, min(200, _trust))
        if _trust > 0:
            try:
                _tb = self.store.trust_bonuses.get(char_id) or {}
            except Exception:
                _tb = {}
            for _tk, _tv in (("hp", "maxHp"), ("atk", "atk"),
                             ("def", "def")):
                _v = _tb.get(_tk)
                if _v:
                    attrs[_tv] = (attrs.get(_tv) or 0) + \
                        int(float(_v) * _trust / 200.0)
        # level runes: operator attribute multipliers / additives,
        # deploy cost and respawn time
        _rm = getattr(self, "_rune_char_mul", {})
        _ra = getattr(self, "_rune_char_add", {})
        _AMAP = {"atk": "atk", "def": "def", "max_hp": "maxHp"}
        for _k, _m in _rm.items():
            _sk = _AMAP.get(_k, _k)
            if _sk in attrs and attrs[_sk] is not None:
                attrs[_sk] = float(attrs[_sk]) * _m
        for _k, _a in _ra.items():
            _sk = _AMAP.get(_k, _k)
            if _sk in attrs and attrs[_sk] is not None:
                attrs[_sk] = float(attrs[_sk]) + _a
        if getattr(self, "_rune_char_cost_mul", 1.0) != 1.0:
            attrs["cost"] = float(attrs.get("cost") or 0) * \
                self._rune_char_cost_mul
        if getattr(self, "_rune_char_cost_add", 0.0):
            attrs["cost"] = float(attrs.get("cost") or 0) + \
                self._rune_char_cost_add
        if getattr(self, "_rune_respawn_mul", 1.0) != 1.0 or \
                getattr(self, "_rune_respawn_add", 0.0):
            attrs["respawnTime"] = \
                (float(attrs.get("respawnTime") or 70.0) *
                 self._rune_respawn_mul + self._rune_respawn_add)
        if self.cost < attrs.get("cost", 0):
            return False, "insufficient_cost"
        self.cost -= attrs.get("cost", 0)
        op = Operator(char_id, Attributes(attrs), row=row, col=col,
                      direction=direction, deploy_tick=self.tick,
                      skills=self._char_skills(char_id))
        op.range_shape = self._range_shape(data, direction)
        op.position = pos
        op.module = ({"id": _mod_id, "level": _mod_lv}
                     if _mod_id else None)
        op.trust = _trust
        op.sub_profession_id = data.get("subProfessionId") if isinstance(
            data, dict) else None
        op.profession = int(data.get("profession") or 0) if isinstance(
            data, dict) else 0
        try:
            from .traits import TraitSystem
            op.trait_system = TraitSystem(op, data)
            # unyield (\u4e0d\u5c48\u8005) trait: cannot be healed by
            # allied operators (self-heal from skills/talents bypasses).
            if op.trait_system is not None and op.trait_system.is_unyield():
                self.add_abnormal(op, AbnormalFlag.HEAL_FREE, 1 << 20,
                                  source=op)
        except Exception:
            op.trait_system = None
        # talents from squad phase/level/potential
        try:
            from .talents import TalentSystem
            op.talent_system = TalentSystem(op, data.get("talents"),
                                            phase=phase, level=level,
                                            potential_rank=potential)
            # module talent blackboard upgrades (e.g. \u9152\u795e Y\u6a21\u7ec4
            # \u5760\u68a6: attack_speed/value replaced by module values)
            try:
                _mod_up = self.store.module_talent_upgrades(_mod_id, _mod_lv)
                if _mod_up:
                    op.talent_system.apply_module_upgrades(_mod_up,
                                                           potential_rank=potential)
            except Exception:
                pass
            # module trait blackboard upgrades (e.g. \u54c8\u6d1b\u5fb7
            # WDM-X \u817f\u90e8\u62a4\u7406\u5957\u88c5: ep_heal_ratio
            # 0.5 -> 0.6 at module level 1+)
            try:
                _mod_tr = self.store.module_trait_upgrades(_mod_id, _mod_lv)
                if _mod_tr:
                    op.trait_system.apply_module_upgrades(
                        _mod_tr, potential_rank=potential)
            except Exception:
                pass
        except Exception:
            op.talent_system = None
        # permanent talent stats (atk/def/attack_speed/penetration ...)
        _LAYER_KW = {"add": "additive", "mul": "multiplicative",
                     "final_add": "final_add", "final_mul": "final_mul"}
        try:
            for _stat, _val, _layer in op.talent_system.stat_modifiers():
                op.attributes.add_modifier(
                    _stat, **{_LAYER_KW.get(_layer, "additive"): _val},
                    key="talent:" + _stat)
        except Exception:
            pass
        # deploy-time talent buffs (e.g. \u70db\u714c T1 fire-burst listener)
        try:
            for _tb in op.talent_system.deploy_buffs(self):
                self.add_buff(op, _tb)
        except Exception:
            pass
        # maxHp from permanent talent modifiers (e.g. \u533b\u751f \u519b\u533b
        # +12% maxHp) must be reflected in the unit's max_hp field.
        try:
            _eff_mhp = float(op.attributes.get("maxHp") or 0.0)
            if _eff_mhp > 0:
                op.max_hp = _eff_mhp
                op.hp = _eff_mhp
        except Exception:
            pass
        if sk_data:
            from .operator_skills import OperatorSkillController
            levels = entry.get("skillLevels") or []
            op.skill_controller = OperatorSkillController(
                op, self, sk_data, levels,
                equipped_index=entry.get("skillIndex"))
            # initial SP pre-charged on deploy (controller init); then
            # deploy-triggered skills (spType=8) fire immediately
            op.skill_controller.trigger_on_deploy()
        self._register_summons(op, data)
        if auto_summon:
            self._auto_deploy_summon(op)
        self._sync_funnel_drones(op)
        self._apply_global_buffs(op)
        self.operators.append(op)
        self._dispatch_buff_events(op, "ON_OWNER_LOCATE",
                                   source=op, target=op)
        self.stats["deployments"] += 1
        self.emit(self.tick, EventType.DEPLOY,
                  {"charId": char_id, "instId": op.inst_id,
                   "row": row, "col": col, "direction": direction,
                   "skillIndex": entry.get("skillIndex"),
                   "cost": attrs.get("cost", 0)})
        return True, op.inst_id

    def deploy_token(self, token_key, row, col, direction=1, owner=None):
        """Deploy a token (summon) from characters.json token entries."""
        data = self._char_base(token_key)
        if data is None:
            return False, "no_token_data"
        attrs = self._char_attrs(data, 0, 50)
        # non-attacking tokens (sandbeast etc.): the raw data has no ATK,
        # but the Attributes default would turn it into 100 -> force 0 so
        # they never attack.
        try:
            _ph0 = ((data.get("phases") or [{}])[0].get(
                "attributesKeyFrames") or [{}])[0]
            if not (_ph0.get("data") or {}).get("atk"):
                attrs["atk"] = 0.0
        except Exception:
            pass
        # redeploy cooldown (tokens like Mon3tr have respawnTime)
        until = self._redeploy_until.get(token_key, 0)
        if self.tick < until:
            return False, "on_cooldown"
        # max deploy count (e.g. Mon3tr maxDeployCount=1)
        max_cnt = int(attrs.get("maxDeployCount") or 0)
        if max_cnt > 0:
            alive = [t for t in self.tokens
                     if t.token_id == token_key and not t.dead]
            if len(alive) >= max_cnt:
                return False, "deploy_limit"
        t = self.map.tile(row, col)
        if t is None or t.buildable_type is None:
            return False, "not_buildable"
        if any(o.row == row and o.col == col for o in self.operators):
            return False, "occupied"
        if any(tk.row == row and tk.col == col for tk in self.tokens):
            return False, "occupied"
        # Ray sandbeast: only deployable inside the summoner's range
        if token_key == "token_10034_ray_sndbst" and owner is not None:
            if getattr(owner, "range_shape", None) and not any(
                    (owner.row + dr, owner.col + dc) == (row, col)
                    for dr, dc in owner.range_shape):
                return False, "outside_owner_range"
        token = Token(token_key, Attributes(attrs), row=row, col=col,
                      owner=owner, is_deployable=True)
        token.pos_x, token.pos_y = float(col), float(row)
        token.range_shape = self._range_shape(data, direction)
        token.position = int(data.get("position") or 1)
        token.respawn_time = float(attrs.get("respawnTime") or 35.0)
        token.token_skill_bb = self._token_skill_bb(token_key)
        token.token_steal_bb = self._token_steal_bb(token_key)
        # optional lifetime from the token's own talent blackboard (sandbeast);
        # pick the highest-phase candidate (E2 duration 25s beats E1 15s)
        try:
            _best = None
            for _tal in (data.get("talents") or []):
                for _cand in (_tal.get("candidates") or []):
                    _dur = None
                    for _b in (_cand.get("blackboard") or []):
                        if _b.get("key") == "duration":
                            _dur = _b.get("value")
                    if not _dur:
                        continue
                    _uc = _cand.get("unlockCondition") or {}
                    _key = (int(_uc.get("phase") or 0),
                            int(_uc.get("level") or 0))
                    if _best is None or _key > _best[0]:
                        _best = (_key, _dur)
            if _best is not None:
                token.expire_tick = self.tick + int(
                    round(float(_best[1]) * 30))
        except Exception:
            pass
        # Ray S2: sandbeast respawn time reduced while \u5e7f\u57df\u8b66\u89c9 is active
        if owner is not None and token.token_id == "token_10034_ray_sndbst":
            _sc = getattr(owner, "skill_controller", None)
            _act = getattr(_sc, "active", None) if _sc is not None else None
            if _act is not None and getattr(getattr(_act, "skill", None),
                                            "skill_id", "") == "skchr_ray_2":
                try:
                    _rp = (_act.skill.blackboard or {}).get("respawn_time")
                    if _rp:
                        token.respawn_time = max(
                            1.0, token.respawn_time * (1.0 + float(_rp)))
                except (TypeError, ValueError):
                    pass
        self.tokens.append(token)
        self._summon_insts.setdefault(token_key, []).append(token.inst_id)
        self._register_rally_point(token)
        self.emit(self.tick, "token_spawn",
                  {"tokenId": token_key, "instId": token.inst_id,
                   "row": row, "col": col,
                   "owner": owner.inst_id if owner else None})
        return True, token.inst_id

    def spawn_token_forced(self, token_key, row, col, owner=None):
        """Force-spawn a token ignoring buildable/occupancy checks (game
        forced spawns like the mad cage on the bursting enemy's tile).
        An existing live same-key token on the tile is REFRESHED (HP reset)
        instead of duplicated; character-class units (operators/tokens)
        still block the spawn."""
        data = self._char_base(token_key)
        if data is None:
            return False, "no_token_data"
        t = self.map.tile(row, col)
        if t is None:
            return False, "no_tile"
        # same-key token already on the tile -> refresh
        for tk in self.tokens:
            if not tk.dead and tk.token_id == token_key and \
                    tk.row == row and tk.col == col:
                tk.hp = tk.max_hp
                self.emit(self.tick, "token_refresh",
                          {"tokenId": token_key, "instId": tk.inst_id,
                           "row": row, "col": col,
                           "owner": owner.inst_id if owner else None})
                return True, tk.inst_id
        if any(o.row == row and o.col == col for o in self.operators):
            return False, "occupied"
        if any(tk.row == row and tk.col == col for tk in self.tokens):
            return False, "occupied"
        attrs = self._char_attrs(data, 0, 50)
        try:
            _ph0 = ((data.get("phases") or [{}])[0].get(
                "attributesKeyFrames") or [{}])[0]
            if not (_ph0.get("data") or {}).get("atk"):
                attrs["atk"] = 0.0
        except Exception:
            pass
        token = Token(token_key, Attributes(attrs), row=row, col=col,
                      owner=owner, is_deployable=False)
        token.pos_x, token.pos_y = float(col), float(row)
        token.range_shape = self._range_shape(data, 1)
        token.position = int(data.get("position") or 1)
        token.respawn_time = float(attrs.get("respawnTime") or 35.0)
        token.token_skill_bb = self._token_skill_bb(token_key)
        token.token_steal_bb = self._token_steal_bb(token_key)
        self.tokens.append(token)
        self._summon_insts.setdefault(token_key, []).append(token.inst_id)
        self._register_rally_point(token)
        self.emit(self.tick, "token_spawn",
                  {"tokenId": token_key, "instId": token.inst_id,
                   "row": row, "col": col,
                   "owner": owner.inst_id if owner else None})
        return True, token.inst_id

    def deploy_gained_token(self, token_key, row, col, direction=1,
                            owner=None):
        """Deploy a player-side token previously gained through a GainToken
        buff node (act36side / event modes).  Each gained count is one
        deployment; the inventory is exposed in snapshots as gainedTokens
        and consumed here on success."""
        count = int(self._gained_tokens.get(token_key, 0) or 0)
        if count <= 0:
            return False, "not_gained"
        ok, res = self.deploy_token(token_key, row, col, direction,
                                    owner=owner)
        if not ok:
            return ok, res
        self._gained_tokens[token_key] = count - 1
        self.emit(self.tick, "token_deployed",
                  {"tokenKey": token_key, "remaining": count - 1})
        return True, res

    def deploy_summon(self, char_id, row, col, direction=1, owner=None,
                      skill_index=None):
        """Deploy the token bound to a deployed summoner operator."""
        keys = self._summons.get(char_id) or []
        if not keys:
            return False, "no_summon"
        if skill_index is not None:
            k = next((x for x in keys if x["skillIndex"] == skill_index),
                     keys[0])
        else:
            k = keys[0]
        if owner is None:
            for op in self.operators:
                if op.char_id == char_id:
                    owner = op
                    break
        return self.deploy_token(k["tokenKey"], row, col, direction,
                                 owner=owner)

    def _register_summons(self, op, data):
        """Register summonable tokens for a deployed operator."""
        keys = []
        ts = getattr(op, "talent_system", None)
        if ts is not None and getattr(ts, "token_key", None):
            keys.append({"tokenKey": ts.token_key, "source": "talent",
                         "skillIndex": None})
        for i, sk in enumerate(data.get("skills") or []):
            tk = sk.get("overrideTokenKey") if isinstance(sk, dict) else None
            if tk and not any(x["tokenKey"] == tk for x in keys):
                keys.append({"tokenKey": tk, "source": "skill",
                             "skillIndex": i})
        if keys:
            self._summons[op.char_id] = keys
            self.emit(self.tick, "summon_available",
                      {"charId": op.char_id, "tokens": keys})

    def _auto_deploy_summon(self, op):
        """Optional convenience: auto-place a summon next to its operator."""
        keys = self._summons.get(op.char_id) or []
        if not keys:
            return
        for dr, dc in ((0, -1), (0, 1), (-1, 0), (1, 0),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            r, c = op.row + dr, op.col + dc
            t = self.map.tile(r, c)
            if t is None or t.buildable_type is None:
                continue
            if any(o.row == r and o.col == c for o in self.operators):
                continue
            if any(tk.row == r and tk.col == c for tk in self.tokens):
                continue
            self.deploy_summon(op.char_id, r, c, owner=op)
            return

    def _retire_token(self, tok, reason="withdraw"):
        """Remove a token: clear blockees, start redeploy cooldown and
        run the Ray S2 bullet refund (sandbeast retreat)."""
        for e in list(self.enemies):
            if e.blocked_by is tok:
                e.blocked_by = None
                e.state = EnemyState.MOVE
        tok.dead = True
        self.tokens.remove(tok)
        self._unregister_rally_point(tok)
        cd = float(getattr(tok, "respawn_time", 35.0) or 35.0)
        self._redeploy_until[tok.token_id] = self.tick + int(round(cd * 30))
        self._token_retreat_refund(tok)
        self.emit(self.tick, EventType.WITHDRAW if reason == "withdraw"
                  else "token_expire",
                  {"instId": tok.inst_id, "tokenId": tok.token_id,
                   "redeployIn": round(cd, 1), "refund": 0.0,
                   "reason": reason})
        return True

    def _token_retreat_refund(self, tok):
        """Ray S2 passive: sandbeast retreat refunds bullets that hit
        its scouted area (recorded on the token)."""
        op = tok.owner
        cnt = int(getattr(tok, "_recover_bullets", 0) or 0)
        if cnt <= 0 or op is None or getattr(op, "dead", False):
            return
        ts = getattr(op, "trait_system", None)
        if ts is None or not ts.is_hunter():
            return
        if not any((s.get("skillId") if isinstance(s, dict) else
                    getattr(s, "skill_id", "")) == "skchr_ray_2"
                   for s in (getattr(op, "skills", None) or [])):
            return
        try:
            max_ammo = int(ts.hunter_ammo_max())
        except Exception:
            max_ammo = 0
        ammo = int(getattr(op, "_hunter_ammo", 0) or 0)
        refund = min(max(0, max_ammo - ammo), cnt)
        if refund > 0:
            op._hunter_ammo = ammo + refund
            self.emit(self.tick, "ray_sandbeast_ammo_recover",
                      {"unit": op.inst_id, "amount": refund,
                       "tokenId": tok.token_id})

    def withdraw_token(self, inst_id):
        """Retreat a token; starts its redeploy cooldown."""
        for tok in self.tokens:
            if tok.inst_id == inst_id:
                self._retire_token(tok, reason="withdraw")
                return True, inst_id
        return False, "not_found"

    def withdraw(self, inst_id):
        for op in self.operators:
            if op.inst_id == inst_id:
                self._clear_steal_buffs(op)
                for e in list(op.blocked_enemies):
                    e.blocked_by = None
                    e.state = EnemyState.MOVE
                op.dead = True
                self.clear_operator_skill_tiles(op)
                _ts = getattr(op, "trait_system", None)
                if _ts is not None:
                    try:
                        _ts.bard_aura_clear()
                    except Exception:
                        pass
                # Thumpy: retreating clears all water-break marks she applied
                for e in list(self.enemies):
                    e.buffs = [x for x in e.buffs
                               if not (x.get("source") is op and
                                       x.get("key") in
                                       ("thumpy_water_mark",
                                        "thumpy_s3_mark"))]
                self._dispatch_buff_events(op, "ON_OWNER_FINISH",
                                           source=op, target=op)
                self.operators.remove(op)
                # retreating the summoner retreats its summons (game rule)
                for tok in [t for t in list(self.tokens) if t.owner is op]:
                    self.withdraw_token(tok.inst_id)
                # funnel drones follow the operator and leave with her
                _drones = getattr(op, "_funnel_drones", None)
                if _drones:
                    for _d in list(_drones):
                        self.emit(self.tick, "funnel_drone",
                                  {"unit": op.inst_id,
                                   "drone": _d.inst_id,
                                   "type": "retreat"})
                    op._funnel_drones = []
                # redeploy cooldown starts on retreat
                cd = float(getattr(op, "respawn_time", 70.0) or 70.0)
                self._redeploy_until[op.char_id] =                     self.tick + int(round(cd * 30))
                # retreat refunds 50% of deploy cost (game rule)
                refund = float(getattr(op, "cost", 0.0) or 0.0) * 0.5
                self.cost = min(self.max_cost, self.cost + refund)
                self.emit(self.tick, EventType.WITHDRAW,
                          {"instId": inst_id,
                           "redeployIn": round(cd, 1),
                           "refund": round(refund, 1)})
                return True, inst_id
        return False, "not_found"

    def activate_skill(self, inst_id, skill_index=0):
        """Operator skill activation (SP consumed, buffs applied)."""
        for op in self.operators:
            if op.inst_id == inst_id:
                if getattr(op, "_reborn_state", False):
                    return False, "downed"
                sc = getattr(op, "skill_controller", None)
                if sc is None:
                    self.emit(self.tick, EventType.SKILL_CAST,
                              {"instId": inst_id, "skillIndex": skill_index})
                    return True, skill_index
                return sc.activate(skill_index)
        return False, "not_found"

    def _enemy_db_level(self, key):
        """Enemy level for this level's enemyDbRefs (default 0)."""
        refs = self.sim.get("enemyDbRefs") or []
        for r in refs:
            if r.get("id") == key or r.get("key") == key:
                return int(r.get("level", 0) or 0)
        return 0

    def _predefine_enabled(self, alias):
        """level_predefines_enable rune: alias (or its base key) enabled?"""
        en = getattr(self, "_rune_predefine_enable", set()) or set()
        if not en:
            return False
        if alias in en:
            return True
        base = str(alias or "").split("#", 1)[0]
        return base in en

    def _spawn_predefines(self):
        """Place predefined tokens (traps/towers) and NPC allies."""
        for t in self.predefines.get("tokenInsts") or []:
            if t.get("hidden") and not self._predefine_enabled(
                    t.get("alias")):
                self._predefined_pending.append(("token", t))
                continue
            self._spawn_predefined_token(t)
        for c in self.predefines.get("characterInsts") or []:
            if c.get("hidden") and not self._predefine_enabled(
                    c.get("alias")):
                self._predefined_pending.append(("char", c))
                continue
            self._spawn_predefined_char(c)
        self._spawn_rune_random_predefines()

    def _spawn_rune_random_predefines(self):
        """level_predefine_tokens_random_spawn_on_tile: place the token on
        every map tile of the rune's tile type."""
        specs = getattr(self, "_rune_random_predefines", None)
        if not specs:
            return
        n = 0
        for tiles, tk in specs:
            for r in range(self.map.rows):
                for c in range(self.map.cols):
                    t = self.map.tile(r, c)
                    if t is None or t.tile_key not in tiles:
                        continue
                    if any(x.token_id == tk and (x.row, x.col) == (r, c)
                           for x in self.tokens):
                        continue
                    n += 1
                    self._spawn_predefined_token({
                        "row": r, "col": c, "characterKey": tk,
                        "phase": 0, "level": 1, "direction": 0,
                        "alias": "%s#%d" % (tk, n), "hidden": False})

    def _token_skill_bb(self, token_key):
        """Merge a token's first skill blackboard (sktok_*) into a dict."""
        data = self._char_base(token_key)
        if not data:
            return {}
        bb = {}
        sk_data = self._char_skills(token_key)
        if sk_data:
            lv = ((sk_data[0].get("levels") or [{}])[0]
                  if sk_data[0] else {})
            for b in (lv.get("blackboard") or []):
                k = b.get("key") or ""
                if k.startswith("talent@"):
                    k = k[len("talent@"):]
                bb[k] = b.get("value")
        return bb

    def _token_steal_bb(self, token_key):
        """Token steal-attribute talent blackboard (e.g. 缪尔赛思流形:
        ``steal_atk``/``steal_def`` 10 per attack, max 250 each).  Picks
        the highest-phase candidate carrying steal keys."""
        data = self._char_base(token_key)
        if not data:
            return {}
        best = None
        for _tal in (data.get("talents") or []):
            for _c in (_tal.get("candidates") or []):
                bb = {x.get("key"): x.get("value")
                      for x in (_c.get("blackboard") or [])}
                if not any("steal" in str(k).lower() for k in bb):
                    continue
                _uc = _c.get("unlockCondition") or {}
                _key = (int(_uc.get("phase") or 0),
                        int(_uc.get("level") or 0))
                if best is None or _key > best[0]:
                    best = (_key, bb)
        return (best[1] if best else None) or {}

    def _spawn_predefined_token(self, t):
        data = self._char_base(t.get("characterKey") or "")
        if data is None:
            return None
        attrs = self._char_attrs(data, int(t.get("phase") or 0),
                                int(t.get("level") or 1))
        row = int(t.get("row") or 0)
        col = int(t.get("col") or 0)
        token = Token(t.get("characterKey") or "token",
                      Attributes(attrs), row=row, col=col,
                      is_deployable=False)
        token.pos_x, token.pos_y = float(col), float(row)
        token.direction = int(t.get("direction") or 0)
        token.alias = t.get("alias")
        token.range_shape = self._range_shape(data, token.direction)
        token.position = int(data.get("position") or 1)
        token.token_skill_bb = self._token_skill_bb(token.token_id)
        token.token_steal_bb = self._token_steal_bb(token.token_id)
        self.tokens.append(token)
        self.emit(self.tick, "predefined_spawn",
                  {"tokenId": token.token_id, "instId": token.inst_id,
                   "row": row, "col": col, "alias": t.get("alias")})
        return token

    def _spawn_predefined_char(self, c):
        """Spawn an NPC ally (side 1) from a predefined character inst."""
        cid = c.get("characterKey") or ""
        data = self._char_base(cid)
        if data is None:
            return None
        attrs = self._char_attrs(data, int(c.get("phase") or 0),
                                 int(c.get("level") or 1))
        row = int(c.get("row") or 0)
        col = int(c.get("col") or 0)
        op = Operator(cid, Attributes(attrs), row=row, col=col,
                      direction=int(c.get("direction") or 0),
                      deploy_tick=self.tick, skills=self._char_skills(cid))
        op.alias = c.get("alias")
        op.range_shape = self._range_shape(data, op.direction)
        try:
            from .talents import TalentSystem
            op.talent_system = TalentSystem(
                op, data.get("talents"), phase=int(c.get("phase") or 0),
                level=int(c.get("level") or 1),
                potential_rank=int(c.get("potentialRank") or 0))
        except Exception:
            op.talent_system = None
        sk_data = self._char_skills(cid)
        if sk_data:
            from .operator_skills import OperatorSkillController
            op.skill_controller = OperatorSkillController(
                op, self, sk_data, [int(c.get("mainSkillLvl") or 1)])
        self.operators.append(op)
        self.emit(self.tick, "predefined_spawn",
                  {"charId": cid, "instId": op.inst_id, "row": row,
                   "col": col, "alias": c.get("alias")})
        return op

    def _predefined_matches(self, inst, key):
        """Match a predefined instance against a wave key (alias or charId)."""
        if not key:
            return False
        alias = inst.get("alias") or ""
        ck = inst.get("characterKey") or ""
        return alias == key or alias.startswith(key + "#") or \
            ck == key or key.startswith(alias + ":")

    def activate_predefined_alias(self, alias):
        """Spawn pending (hidden) predefined instances by alias/charId."""
        spawned = []
        remaining = []
        for kind, t in self._predefined_pending:
            if self._predefined_matches(t, alias):
                if kind == "token":
                    spawned.append(self._spawn_predefined_token(t))
                else:
                    spawned.append(self._spawn_predefined_char(t))
            else:
                remaining.append((kind, t))
        self._predefined_pending = remaining
        return [x for x in spawned if x is not None]

    def _predefined_unit(self, key):
        """Find a spawned predefined unit by alias/charId prefix."""
        for t in list(self.tokens):
            alias = getattr(t, "alias", "") or ""
            if alias == key or alias.startswith(key + "#") or \
                    (t.token_id or "") == key:
                return t
        for o in list(self.operators):
            alias = getattr(o, "alias", "") or ""
            if alias == key or alias.startswith(key + "#") or \
                    (o.char_id or "") == key:
                return o
        return None

    def trigger_predefined(self, key):
        """Trigger a predefined unit's skill/ability (TRIGGER_PREDEFINED)."""
        unit = self._predefined_unit(key)
        if unit is None:
            self.emit(self.tick, "predefined_trigger_miss", {"key": key})
            return None
        sc = getattr(unit, "skill_controller", None)
        if sc is not None:
            sc.activate(0)
        self.emit(self.tick, "predefined_triggered",
                  {"key": key, "instId": unit.inst_id,
                   "charId": getattr(unit, "char_id", getattr(
                       unit, "token_id", None))})
        return unit

    def withdraw_predefined(self, key):
        """Withdraw/remove a predefined unit (WITHDRAW_PREDEFINED)."""
        unit = self._predefined_unit(key)
        if unit is None:
            self.emit(self.tick, "predefined_withdraw_miss", {"key": key})
            return None
        unit.dead = True
        _ts = getattr(unit, "trait_system", None)
        if _ts is not None:
            try:
                _ts.bard_aura_clear()
            except Exception:
                pass
        for e in list(getattr(unit, "blocked_enemies", []) or []):
            e.blocked_by = None
            e.state = EnemyState.MOVE
        if unit in self.tokens:
            self.tokens.remove(unit)
            self._unregister_rally_point(unit)
        if unit in self.operators:
            self.operators.remove(unit)
        self.emit(self.tick, "predefined_withdrawn",
                  {"key": key, "instId": unit.inst_id})
        return unit

    # ---- level runes (stage tags / crisis contracts) ----
    def _rune_bb(self, rune):
        bb = {}
        for b in (rune.get("blackboard") or []):
            if not isinstance(b, dict) or b.get("key") is None:
                continue
            k = b["key"]
            v = b.get("value")
            if v is None and b.get("valueStr") is not None:
                v = b["valueStr"]
            bb[k] = v
        return bb

    def _runes_for(self, key=None):
        """Matching rune blackboards for the current difficulty mask."""
        out = []
        runes = self.sim.get("runes") or []
        if not runes:
            runes = self.raw.get("runes") or []
        diff = getattr(self, "_rune_difficulty", 2)
        _diff_name = {"NONE": 0, "NORMAL": 1, "FOUR_STAR": 2, "EASY": 4,
                      "SIX_STAR": 8, "ALL": 15}
        for r in runes:
            if not isinstance(r, dict) or not r.get("key"):
                continue
            if key is not None and r["key"] != key:
                continue
            dm = r.get("difficultyMask") or {}
            if isinstance(dm, dict):
                mask = dm.get("value")
            elif isinstance(dm, str):
                mask = _diff_name.get(dm)
            else:
                mask = dm
            if mask is not None and int(mask) != 15 \
                    and not (int(mask) & diff):
                continue
            out.append(self._rune_bb(r))
        return out

    def _apply_level_runes(self):
        """Apply level runes. Global (life point / initial & max cost /
        cost recovery) map onto battle state; per-unit ones are stored in
        _rune_* fields and applied at spawn / deploy."""
        self._rune_enemy_mul = {}
        self._rune_enemy_add = {}
        self._rune_char_mul = {}
        self._rune_char_add = {}
        self._rune_char_cost_mul = 1.0
        self._rune_char_cost_add = 0.0
        self._rune_respawn_mul = 1.0
        self._rune_respawn_add = 0.0
        self._rune_forbidden = set()
        self._rune_excluded = set()
        self._rune_enemy_replace = {}
        self._rune_squad_limit = None
        self._rune_cost_recovery_mul = 1.0
        # hidden-group wave actions (level_hidden_group_enable /
        # level_hidden_group_disable): actions carrying a hiddenGroup
        # stay hidden unless enabled for the current difficulty, and
        # a matching disable rune re-hides them
        self._rune_hidden_groups = {"enable": set(), "disable": set()}
        # life point (gbuff_lifepoint / global_lifepoint)
        for bb in self._runes_for("gbuff_lifepoint") + \
                self._runes_for("global_lifepoint"):
            v = float(bb.get("value") or 0)
            if v:
                self.max_life_point = max(1, self.max_life_point + int(v))
                self.life_point = max(0, self.life_point + int(v))
        # initial cost (global_initial_cost_add / cbuff_initial_cost)
        for bb in self._runes_for("global_initial_cost_add") + \
                self._runes_for("cbuff_initial_cost"):
            v = float(bb.get("cost") if "cost" in bb
                      else bb.get("value") or 0)
            self.initial_cost = max(0.0, self.initial_cost + v)
            self.cost = max(0.0, self.cost + v)
        # max cost (cbuff_max_cost)
        for bb in self._runes_for("cbuff_max_cost"):
            mc = bb.get("max_cost")
            if mc is not None:
                self.max_cost = float(mc)
        # cost recovery (global_cost_recovery_mul / cbuff_cost_recovery)
        for bb in self._runes_for("global_cost_recovery_mul") + \
                self._runes_for("cbuff_cost_recovery"):
            sc = float(bb.get("scale") or 1.0)
            if sc > 0:
                self._rune_cost_recovery_mul *= sc
        if self._rune_cost_recovery_mul != 1.0:
            self.cost_increase_time /= self._rune_cost_recovery_mul
            self._cost_base_increase_time = self.cost_increase_time
        # enemy attribute multipliers / additives
        _EMAP = {"atk": "atk", "def": "def", "max_hp": "maxHp",
                 "magic_resistance": "magicResistance",
                 "attack_speed": "attackSpeed", "move_speed": "moveSpeed"}
        for bb in self._runes_for("enemy_attribute_mul") + \
                self._runes_for("ebuff_attribute"):
            for k in _EMAP:
                if k in bb:
                    self._rune_enemy_mul[k] = \
                        self._rune_enemy_mul.get(k, 1.0) * float(bb[k])
        for bb in self._runes_for("enemy_attribute_add"):
            for k in ("atk", "def", "max_hp", "magic_resistance"):
                if k in bb:
                    self._rune_enemy_add[k] = \
                        self._rune_enemy_add.get(k, 0.0) + float(bb[k])
        # operator attribute multipliers / additives
        for bb in self._runes_for("char_attribute_mul") + \
                self._runes_for("cbuff_attribute"):
            for k in ("atk", "def", "max_hp"):
                if k in bb:
                    self._rune_char_mul[k] = \
                        self._rune_char_mul.get(k, 1.0) * float(bb[k])
        for bb in self._runes_for("char_attribute_add"):
            for k in ("atk", "def", "max_hp"):
                if k in bb:
                    self._rune_char_add[k] = \
                        self._rune_char_add.get(k, 0.0) + float(bb[k])
        # operator deploy cost / respawn
        for bb in self._runes_for("char_cost_mul") + \
                self._runes_for("cbuff_char_cost"):
            sc = float(bb.get("scale") or 1.0)
            if sc:
                self._rune_char_cost_mul *= sc
        for bb in self._runes_for("char_cost_add"):
            self._rune_char_cost_add += float(bb.get("value") or 0)
        for bb in self._runes_for("char_respawntime_mul") + \
                self._runes_for("cbuff_respawn_time"):
            sc = float(bb.get("scale") or 1.0)
            if sc:
                self._rune_respawn_mul *= sc
        for bb in self._runes_for("char_respawntime_add"):
            self._rune_respawn_add += float(bb.get("value") or 0)
        # forbidden deploy locations "(r,c)|(r,c)"
        for bb in self._runes_for("global_forbid_location"):
            loc = bb.get("location")
            if isinstance(loc, str):
                for part in loc.split("|"):
                    part = part.strip().strip("()")
                    if "," in part:
                        try:
                            _r, _c = part.split(",")
                            self._rune_forbidden.add((int(_r), int(_c)))
                        except ValueError:
                            pass
        # excluded characters (cbuff_excluded / char_exclude)
        for bb in self._runes_for("cbuff_excluded") + \
                self._runes_for("char_exclude"):
            ch = bb.get("char")
            if ch:
                self._rune_excluded.add(ch)
        # enemy key replacement (level_enemy_replace)
        for bb in self._runes_for("level_enemy_replace"):
            k = bb.get("key")
            v = bb.get("value")
            if k and v:
                self._rune_enemy_replace[k] = v
        # squad limit
        for bb in self._runes_for("global_squad_num_limit"):
            v = bb.get("value")
            if v is not None:
                self._rune_squad_limit = int(v)
        # hidden wave-action groups: blackboard "key" -> group name
        # (value stored as valueStr, e.g. "raid" / "hidden_fstar")
        for bb in self._runes_for("level_hidden_group_enable"):
            _g = bb.get("key")
            if _g:
                self._rune_hidden_groups["enable"].add(str(_g))
        for bb in self._runes_for("level_hidden_group_disable"):
            _g = bb.get("key")
            if _g:
                self._rune_hidden_groups["disable"].add(str(_g))
        # predefined enable set (level_predefines_enable: bb keys are
        # predefined aliases like trap_014_tower#1)
        self._rune_predefine_enable = set()
        for bb in self._runes_for("level_predefines_enable"):
            for k in bb:
                if k:
                    self._rune_predefine_enable.add(k)
        # random predefined tokens on tile types
        # (level_predefine_tokens_random_spawn_on_tile)
        self._rune_random_predefines = []
        for bb in self._runes_for(
                "level_predefine_tokens_random_spawn_on_tile"):
            tiles = [x.strip() for x in str(bb.get("tile") or "").split("|")
                     if x.strip()]
            tk = bb.get("token_key")
            if tiles and tk:
                self._rune_random_predefines.append((tiles, str(tk)))
        # environment systems (env_system_new / env_gbuff_new /
        # env_gbuff_new_with_verify): parsed references + attribute maps
        # for snapshot exposure and global buff application.
        self.env_systems = []
        for bb in self._runes_for("env_system_new"):
            key = bb.get("key")
            if key:
                self.env_systems.append({"key": str(key), "kind": "system"})
        for bb in (self._runes_for("env_gbuff_new") +
                   self._runes_for("env_gbuff_new_with_verify")):
            key = bb.get("key")
            if not key:
                continue
            attrs = {k: v for k, v in bb.items() if k != "key"}
            self.env_systems.append({"key": str(key), "kind": "gbuff",
                                     "attributes": attrs})
        # map tile blackboard overrides (assign / add / mul), keyed either
        # by tile type ('tile_reed|tile_reedf') or by location ('(r,c)')
        self._rune_tile_bb = {"assign": {}, "add": {}, "mul": {}}
        for _mode, _keys in (("assign", ("map_tile_blackb_assign",)),
                             ("add", ("map_tile_blackb_add",)),
                             ("mul", ("map_tile_blackb_mul",))):
            for bb in self._runes_for(_keys[0]):
                targets = []
                _tl = bb.get("tile")
                if _tl:
                    targets += [("tile", x.strip())
                                for x in str(_tl).split("|") if x.strip()]
                _loc = bb.get("location")
                if _loc:
                    for part in str(_loc).split("|"):
                        part = part.strip().strip("()")
                        if "," in part:
                            try:
                                _r, _c = part.split(",")
                                targets.append(("loc", (int(_r), int(_c))))
                            except ValueError:
                                pass
                for _tkind, _tval in targets:
                    for k, v in bb.items():
                        if k in ("tile", "location"):
                            continue
                        try:
                            v = float(v)
                        except (TypeError, ValueError):
                            continue
                        self._rune_tile_bb[_mode].setdefault(
                            (_tkind, _tval), {})[k] = v
        # deployable operator count (gbuff_placable_char_num /
        # global_placable_char_num_add)
        for bb in self._runes_for("gbuff_placable_char_num") + \
                self._runes_for("global_placable_char_num_add"):
            v = float(bb.get("value") or 0)
            if v:
                self.character_limit = max(
                    0, self.character_limit + int(v))
        # enemy attack range multiplier (enemy_attackradius_mul /
        # ebuff_attack_radius)
        for bb in self._runes_for("enemy_attackradius_mul") + \
                self._runes_for("ebuff_attack_radius"):
            sc = float(bb.get("scale") or bb.get("range_scale") or 1.0)
            if sc > 0:
                self._rune_enemy_mul["rangeRadius"] = \
                    self._rune_enemy_mul.get("rangeRadius", 1.0) * sc
        # enemy weight (ebuff_weight add / enemy_weight_add)
        for bb in self._runes_for("ebuff_weight") + \
                self._runes_for("enemy_weight_add"):
            v = float(bb.get("value") or 0)
            if v:
                self._rune_enemy_add["massLevel"] = \
                    self._rune_enemy_add.get("massLevel", 0.0) + v

    def _apply_enemy_skill_runes(self, enemy):
        """Apply enemy_skill_blackb_mul/add runes onto the matching enemy
        skill blackboards (rune blackboard: enemy = 'a|b|c', skill =
        prefabKey; remaining keys scale/add onto the skill blackboard)."""
        sc = getattr(enemy, "skill_controller", None)
        if sc is None:
            return
        for rune in (self._runes_for("enemy_skill_blackb_mul") +
                     self._runes_for("enemy_skill_blackb_add")):
            es = str(rune.get("enemy") or "")
            if es:
                ek_list = [x for x in es.split("|") if x]
                if ek_list and enemy.enemy_key not in ek_list:
                    continue
            is_mul = rune in self._runes_for("enemy_skill_blackb_mul")
            sk_f = str(rune.get("skill") or "")
            for s in sc.skills:
                if sk_f and s.prefab_key != sk_f:
                    continue
                for k, v in rune.items():
                    if k in ("enemy", "skill"):
                        continue
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        continue
                    cur = s.blackboard.get(k)
                    try:
                        cur = float(cur) if cur is not None else 0.0
                    except (TypeError, ValueError):
                        cur = 0.0
                    if is_mul:
                        s.blackboard[k] = cur * v if cur else v
                    else:
                        s.blackboard[k] = cur + v

    def _apply_enemy_talent_runes(self, enemy):
        """enemy_talent_blackb_mul/add / ebuff_talent_blackb_mul: keys are
        '<skillPrefabKey>.<blackboardKey>' (e.g. Boom.atk_scale) and scale
        or add onto the matching skill blackboard."""
        sc = getattr(enemy, "skill_controller", None)
        if sc is None:
            return
        mul = self._runes_for("enemy_talent_blackb_mul") + \
            self._runes_for("ebuff_talent_blackb_mul")
        add = self._runes_for("enemy_talent_blackb_add")
        for rune in mul + add:
            es = str(rune.get("enemy") or "")
            if es:
                ek_list = [x for x in es.split("|") if x]
                if ek_list and enemy.enemy_key not in ek_list:
                    continue
            is_mul = rune in mul
            for k, v in rune.items():
                if k == "enemy" or "." not in str(k):
                    continue
                sk_name, bb_key = str(k).split(".", 1)
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
                for s in sc.skills:
                    if s.prefab_key != sk_name:
                        continue
                    cur = s.blackboard.get(bb_key)
                    try:
                        cur = float(cur) if cur is not None else 0.0
                    except (TypeError, ValueError):
                        cur = 0.0
                    if is_mul:
                        s.blackboard[bb_key] = cur * v if cur else v
                    else:
                        s.blackboard[bb_key] = cur + v

    def _apply_global_buffs(self, unit):
        """Apply level global buffs (prefabKey-based, e.g. night maps)."""
        if not self.global_buffs:
            return
        key = "global_buff"
        if unit.inst_id in self._global_buff_applied:
            return
        self._global_buff_applied.add(unit.inst_id)
        for gb in self.global_buffs:
            pk = gb.get("prefabKey") if isinstance(gb, dict) else gb
            if not pk:
                continue
            # night_map_default etc: keep marker for AI/snapshot
            self.emit(self.tick, EventType.BUFF_APPLIED,
                      {"unit": unit.inst_id, "buff": key,
                       "prefabKey": pk})
        # env_system_new / env_gbuff_new references exposed on every
        # spawned unit (same marker channel; attributes carried in bb)
        for es in getattr(self, "env_systems", []):
            self.emit(self.tick, EventType.BUFF_APPLIED,
                      {"unit": unit.inst_id, "buff": key,
                       "prefabKey": es.get("key"),
                       "kind": es.get("kind"),
                       "attributes": es.get("attributes")})

    def _apply_enemy_prts_prefab_buffs(self, enemy):
        """Mount Mainline-15 PRTS driving buffs from the enemy's base
        prefab.

        The 15-18 boss / highland guards carry trigger buffs on their base
        prefab components (marked ``_attachPassiveBuffsOnDummy``) whose
        templates contain Main15* action nodes (Main15InsertPrtsAction /
        Main15TryNextPrtsAction / Main15SkipPrtsAction ...).  In the game
        these drive the PRTS script queue (priority actions inserted when
        the boss flies / guards act, then advanced by the PRTS enemy's
        Grab abilities).  Only templates that contain Main15 nodes are
        mounted, so regular enemies are untouched.
        """
        if enemy is None:
            return
        try:
            comps = self.store.prefab_components(enemy.enemy_key)
        except Exception:
            return
        if not comps:
            return
        try:
            from .buff_templates import materialise_buff
        except Exception:
            return
        try:
            prts_keys = _prts_template_keys()
        except Exception:
            prts_keys = frozenset()
        have = {b.get("key") for b in (enemy.buffs or [])}
        for c in comps:
            f = c.get("fields") or {}
            if f.get("_attachPassiveBuffsOnDummy") not in (1, True):
                continue
            for _k in ("_buffs", "_passiveBuffs", "_passiveBuffsToOwner"):
                for b in f.get(_k) or []:
                    if not (isinstance(b, dict) and b.get("buffKey")):
                        continue
                    bk = b["buffKey"]
                    if bk in have:
                        continue
                    if (b.get("templateKey") or bk) not in prts_keys:
                        continue
                    have.add(bk)
                    try:
                        entry = materialise_buff(self, enemy, b, {}, enemy)
                    except Exception:
                        entry = None
                    if entry and entry.get("key"):
                        self.add_buff(enemy, entry)

    def _char_damage_type(self, op):
        """Damage type from character description (fashu -> MAGICAL).
        Uses unicode escapes to avoid encoding issues; default PHYSICAL."""
        try:
            data = self._char_base(getattr(op, "char_id", ""))
            desc = (data or {}).get("description") or ""
            # "法术伤害" (fashu shanghai) = MAGICAL
            if "法术伤害" in desc:
                return DamageType.MAGICAL
        except Exception:
            pass
        try:
            trait = getattr(op, "trait_system", None)
            if trait is not None:
                dt = trait.damage_type()
                if dt is not None:
                    return dt
        except Exception:
            pass
        return DamageType.PHYSICAL

    def _char_base(self, char_id):
        if self.char_data is not None:
            return self.char_data.get(char_id)
        return None

    def _char_attrs(self, data, phase=0, level=1):
        """Attributes at a given elite phase + level (linear interp between
        the frame levels, matching the game's growth curve)."""
        phases = data.get("phases") or []
        if not phases:
            return {}
        if phase >= len(phases):
            phase = len(phases) - 1
        frames = phases[phase].get("attributesKeyFrames") or []
        if not frames:
            return {}
        frames = sorted(frames, key=lambda f: f.get("level") or 0)
        lo = frames[0]
        if len(frames) == 1 or level <= (lo.get("level") or 0):
            return dict(lo.get("data") or {})
        hi = frames[-1]
        l_lo = lo.get("level") or 0
        l_hi = hi.get("level") or l_lo + 1
        t = 0.0 if l_hi == l_lo else (level - l_lo) / (l_hi - l_lo)
        t = max(0.0, min(1.0, t))
        lo_d = lo.get("data") or {}
        hi_d = hi.get("data") or {}
        attrs = {}
        for k in set(list(lo_d.keys()) + list(hi_d.keys())):
            a = lo_d.get(k)
            b = hi_d.get(k)
            if a is None:
                attrs[k] = b
            elif b is None:
                attrs[k] = a
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                attrs[k] = a + (b - a) * t
            else:
                attrs[k] = b
        return attrs

    def _squad_entry(self, char_id):
        """Look up a squad config entry for char_id ({} if not found)."""
        for m in (self.squad or []):
            if isinstance(m, dict) and m.get("charId") == char_id:
                return m
        return {}

    def _squad_attrs(self, char_id, data):
        """Attributes from squad config (phase/level) with defaults."""
        entry = self._squad_entry(char_id)
        phase = int(entry.get("phase", 2) if entry.get("phase") is not None else 2)
        level = int(entry.get("level", 1) or 1)
        return self._char_attrs(data, phase, level)

    @staticmethod
    def _potential_bonus(data, potential):
        """Parse potentialRanks descriptions into stat bonuses."""
        import re
        out = {}
        ranks = data.get("potentialRanks") or []
        for i in range(min(potential, len(ranks))):
            desc = (ranks[i] or {}).get("description") or ""
            if "生命" in desc:
                m = re.search(r"[+\-](\d+)", desc)
                if m:
                    out["maxHp"] = out.get("maxHp", 0) + int(m.group(1))
            elif "攻击" in desc:
                m = re.search(r"[+\-](\d+)", desc)
                if m:
                    out["atk"] = out.get("atk", 0) + int(m.group(1))
            elif "防御" in desc:
                m = re.search(r"[+\-](\d+)", desc)
                if m:
                    out["def"] = out.get("def", 0) + int(m.group(1))
            elif "部署费用" in desc:
                m = re.search(r"-(\d+)", desc)
                if m:
                    out["cost"] = out.get("cost", 0) - int(m.group(1))
        return out

    def _char_skills(self, char_id):
        """Merge characters.json skill IDs with skills.json level data."""
        if self.char_data is None:
            return []
        data = self.char_data.get(char_id)
        if not data:
            return []
        skill_ids = data.get("skills") or []
        skill_table = getattr(self.store, "character_skills", None)
        out = []
        for sid in skill_ids:
            sid = sid.get("skillId") if isinstance(sid, dict) else sid
            if not sid:
                continue
            if skill_table is not None:
                entry = skill_table.get(sid)
                out.append(entry if entry else {"skillId": sid, "levels": []})
            else:
                out.append({"skillId": sid, "levels": []})
        return out

    def _range_shape(self, data, direction=1):
        """Map rangeId -> tile offsets, rotated by the unit's facing.

        Uses the exact range_table (73 shapes); unknown ids fall back to
        the approximate grid. Direction: 0=up 1=right 2=down 3=left.
        """
        phases = data.get("phases") or []
        range_id = None
        for ph in phases:
            range_id = ph.get("rangeId")
            if range_id:
                break
        return range_offsets_rotated(range_id, direction)

    # ================= main loop =================
    def tick_once(self):
        if self.finished or self.paused:
            return
        dt = 1.0 / TIME_ROUGH_LOGIC_RATE
        # 1. waves (+ custom enemies)
        self.waves.update()
        if self.custom_waves is not None:
            self.custom_waves.update()
        # 1.1 level branch phase schedulers (deal one phase per trigger,
        #     timed like a fragment from the trigger time)
        alive = []
        for bp in self._branch_phases:
            sched = bp["scheduler"]
            if sched.finished:
                continue
            sched.update()
            if not sched.finished:
                alive.append(bp)
        self._branch_phases = alive
        # 2. enemies
        from .ai import update_enemy_ai
        for e in list(self.enemies):
            if e.dead and e.state == EnemyState.DEAD:
                continue
            _old_rc = (e.row, e.col)
            update_enemy_ai(e, self, dt)
            if (e.row, e.col) != _old_rc:
                self._check_enemy_overlap(e)
        # 2.1 traps (\u9677\u9631\u5e08 mines) fire when an enemy steps on
        #     their tile
        self._trigger_traps()
        # 2.2 mainline-15 PRTS script manager (the PRTS enemy's movement
        #     runs inside the enemy AI above; this advances the sub-action
        #     pipeline and spawns / drags / applies buffs)
        self.prts.on_tick(dt)
        # 3. operators
        self._update_operators(dt)
        # 3.1 attribute-based HP recovery (hpRecoveryPerSec: bard
        #     aura, talent gain treatments, skill regen). Not a
        #     heal action, so it bypasses heal-free.
        self._tick_hp_regen(dt)
        # 4. blocking resolution
        self._update_blocking()
        # 4.5 talent auras (instructor family; conditions re-evaluated)
        self._update_talent_auras()
        self._update_enemy_talent_auras()
        # 5. buffs / abnormal
        self.buffs.update(dt)
        # 5.1 act35side gems: drop entries whose gem enemy was killed
        self.act35.on_tick()
        self._update_rdoc_shields()
        # 5.5 projectiles
        self._update_projectiles(dt)
        # 5.6 terrain effects
        self.tile_effects.tick()
        # 5.7 dynamic skill tiles (conveyor belts etc.)
        self._tick_skill_tiles(dt)
        # 6. cost recovery: precise periodic timer, +1 every effective
        # period; pauses while full or locked (keeps remainder)
        if not self._cost_locked and not self._cost_locked_by_modifier() \
                and self.cost < self.max_cost:
            cit = self.cost_period()
            if cit > 0 and cit < 1e6:      # large values = no natural recovery
                self._cost_acc += dt
                if self._cost_acc + 1e-9 >= cit:
                    self._cost_acc -= cit
                    self.cost = min(self.max_cost, self.cost + 1.0)
            elif cit >= 1e6:
                self._cost_acc = 0.0       # no natural recovery
        # cleanup dead
        self.enemies = [e for e in self.enemies if not e.dead]
        # 7. end conditions
        self._check_end()
        self._tick += 1

    @property
    def tick(self):
        """Current logic tick (0-based); increments after each tick_once()."""
        return self._tick

    def _update_projectiles(self, dt):
        """Advance in-flight projectiles; apply damage on hit."""
        for p in list(self.projectiles):
            if p.update(dt):
                p.on_hit(self)
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def spawn_projectile(self, source, target, projectile_key, damage_type,
                         atk_scale=1.0, hit_callback=None, delay_ticks=0,
                         hit_extra=None):
        """Create an in-flight projectile (returns Projectile or None).

        ``delay_ticks`` models the Ability ``_preDelay`` cast windup before
        the projectile starts moving (still counted in flight time).
        ``hit_extra`` runs after the default projectile damage/hit event
        (attack-attached effects that must land with the hit, e.g. the
        elemental damage of a ranged basic attack).
        """
        from .projectiles import Projectile, projectile_speed
        if target is None or getattr(target, "dead", False):
            return None

        def _wrap_hit(battle, proj):
            if hit_callback is not None:
                hit_callback(battle, proj)
            else:
                # default projectile damage: pass raw atk*scale so
                # battle.apply_damage applies penetration/mitigation once
                atk = source.attributes.get("atk")
                amt = float(atk or 0.0) * float(atk_scale or 1.0)
                battle.apply_damage(proj.target, amt, damage_type,
                                    source=source)
                battle.emit(battle.tick, "attack",
                            {"unit": source.inst_id,
                             "target": proj.target.inst_id,
                             "projectile": projectile_key,
                             "type": "projectile_hit"})
                # class trait on basic ranged attacks (slower sluggish,
                # musha/reaper self-heal, chain jump)
                if getattr(source, "side", 0) == 1 and \
                        str(projectile_key).startswith("op_") and \
                        getattr(source, "trait_system", None) is not None:
                    battle._trait_hit(source, proj.target)
                if hit_extra is not None:
                    try:
                        hit_extra(battle, proj)
                    except Exception:
                        pass
            # enemy attack-recover SP on projectile hit
            if getattr(source, "side", 0) == 0:
                sc = getattr(source, "skill_controller", None)
                if sc is not None:
                    sc.on_enemy_attack()

        _pen_r = 0.0
        _pen_f = 0.0
        if source is not None:
            if damage_type == DamageType.MAGICAL:
                _pen_r = float(source.attributes.get(
                    "magicResistPenetrate") or 0.0)
                _pen_f = float(source.attributes.get(
                    "magicResistPenetrateFixed") or 0.0)
            else:
                _pen_r = float(source.attributes.get("defPenetrate") or 0.0)
                _pen_f = float(source.attributes.get(
                    "defPenetrateFixed") or 0.0)
        p = Projectile(source, target, projectile_speed(projectile_key),
                       damage_type=damage_type, atk_scale=atk_scale,
                       key=projectile_key, hit_callback=_wrap_hit,
                       delay_ticks=delay_ticks,
                       penetrate_ratio=_pen_r, penetrate_fixed=_pen_f)
        self.projectiles.append(p)
        self.emit(self.tick, "attack",
                  {"unit": source.inst_id, "target": target.inst_id,
                   "projectile": projectile_key, "type": "projectile_launch"})
        return p

    @staticmethod
    def _bb_like(bb, suffix):
        """Blackboard value by key suffix (e.g. '...atk_scale')."""
        for k, v in (bb or {}).items():
            if k == suffix or k.endswith(suffix):
                return v
        return None

    def _token_attack(self, tok, target):
        """Token attack: normal atk, or maxHp*scale magical for skill
        towers (e.g. L-44 drone, maxHp * 5% magical per hit)."""
        bb = getattr(tok, "token_skill_bb", None) or {}
        atk = tok.attributes.get("atk")
        scale = self._bb_like(bb, ".atk_scale")
        if scale is None:
            scale = bb.get("atk_scale")
        if (atk <= 0 and not scale) or tok.token_id in _NON_ATTACK_TOKENS:
            tok.attack_timer = 0.5
            return
        if atk <= 0 and scale:
            amount = tok.max_hp * float(scale)
            self.apply_damage(target, amount, DamageType.MAGICAL,
                              source=tok)
        else:
            self._operator_attack(tok, target,
                                  tok.attributes.attack_interval())
            return
        self.emit(self.tick, EventType.ATTACK,
                  {"unit": tok.inst_id, "target": target.inst_id})
        tok.attack_timer = tok.attributes.attack_interval()

    def _token_periodic(self, tok, dt):
        """Periodic token skill effects (e.g. L-44 heal every 5s)."""
        bb = getattr(tok, "token_skill_bb", None) or {}
        interval = self._bb_like(bb, ".interval")
        if interval is None:
            interval = bb.get("interval")
        interval = float(interval or 0.0)
        if interval <= 0:
            return
        acc = getattr(tok, "_token_acc", 0.0) + dt
        tok._token_acc = acc
        if acc < interval:
            return
        tok._token_acc = 0.0
        heal_ratio = self._bb_like(bb, ".hp_ratio")
        if heal_ratio is None:
            heal_ratio = bb.get("hp_ratio")
        if not heal_ratio:
            return
        amount = tok.max_hp * float(heal_ratio)
        for ally in list(self.get_operators()) + list(self.get_tokens()):
            if ally.dead or ally is tok:
                continue
            if abs(ally.row - tok.row) <= 2 and \
                    abs(ally.col - tok.col) <= 2:
                self.apply_heal(ally, amount, source=tok)

    # ================= dynamic skill tiles =================
    def place_operator_skill_tiles(self, op, skill_id, positions,
                                   bb=None, duration=60.0):
        """Register dynamic field tiles created by an operator skill
        (e.g. Thumpy S3 portable conveyor belt). Positions outside the
        map / on forbidden or exit tiles are skipped."""
        now = self.tick
        expiry = now + max(1, int(round(float(duration) * 30.0)))
        placed = []
        for r, c in positions:
            if not (0 <= r < self.map.rows and 0 <= c < self.map.cols):
                continue
            t = self.map.tile(r, c)
            if t is None or t.tile_key in ("tile_forbidden", "tile_end"):
                continue
            self._skill_tile_seq += 1
            self._skill_tiles[(r, c)] = {
                "id": self._skill_tile_seq,
                "op": op, "skillId": skill_id,
                "expiry_tick": expiry,
                "bb": dict(bb or {}),
                "acc": 0.0,
            }
            placed.append({"row": r, "col": c})
        if placed:
            self.emit(self.tick, "skill_tile_placed",
                      {"instId": op.inst_id, "skillId": skill_id,
                       "tiles": placed, "untilTick": expiry})
        return placed

    def clear_operator_skill_tiles(self, op):
        """Remove every skill tile belonging to ``op``."""
        removed = [(r, c) for (r, c), v in self._skill_tiles.items()
                   if v.get("op") is op]
        for rc in removed:
            self._skill_tiles.pop(rc, None)
        if removed:
            self.emit(self.tick, "skill_tile_removed",
                      {"instId": op.inst_id,
                       "tiles": [{"row": r, "col": c} for r, c in removed]})
        return removed

    def skill_tile_at(self, row, col):
        v = self._skill_tiles.get((row, col))
        if v is None:
            return None
        if self.tick >= v["expiry_tick"]:
            self._skill_tiles.pop((row, col), None)
            return None
        return v

    def skill_tile_conveyor_at(self, row, col):
        v = self.skill_tile_at(row, col)
        if v is None:
            return None
        if (v.get("kind") or "conveyor_pull") != "conveyor_pull":
            return None
        return v

    def _tick_skill_tiles(self, dt):
        """Per-tick dynamic skill tile effects (pull + periodic damage)."""
        if not self._skill_tiles:
            return
        expired = [k for k, v in self._skill_tiles.items()
                   if self.tick >= v["expiry_tick"]]
        for k in expired:
            self._skill_tiles.pop(k, None)
        for (r, c), v in list(self._skill_tiles.items()):
            self._tick_conveyor_tile(r, c, v, dt)

    def _tick_conveyor_tile(self, r, c, v, dt):
        """Thumpy S3 belt: pull unblocked mass<=4 enemies toward the
        operator and deal periodic physical + erosion damage."""
        op = v.get("op")
        if op is None or getattr(op, "dead", False):
            return
        bb = v.get("bb") or {}
        speed = float(bb.get("conveyor_speed") or 0.0)
        mass_max = float(bb.get("mass_level") or 99.0)
        interval = float(bb.get("interval") or 1.0)
        atk_scale = float(bb.get("atk_scale") or 0.0)
        for e in list(self.enemies):
            if e.dead or (e.row, e.col) != (r, c):
                continue
            mass = float(e.attributes.get("massLevel") or 0.0)
            # pull only applies to unblocked enemies with mass <= mass_max;
            # the periodic damage hits every enemy standing on the belt
            if mass <= mass_max and e.blocked_by is None and speed > 0:
                dx = op.pos_x - e.pos_x
                dy = op.pos_y - e.pos_y
                dist = (dx * dx + dy * dy) ** 0.5
                if dist > 1e-6:
                    mv = min(speed * dt, dist)
                    e.pos_x += dx / dist * mv
                    e.pos_y += dy / dist * mv
                    nr = int(round(e.pos_y))
                    nc = int(round(e.pos_x))
                    if 0 <= nr < self.map.rows and 0 <= nc < self.map.cols:
                        e.row, e.col = nr, nc
                    self.emit(self.tick, "conveyor_pull",
                              {"unit": e.inst_id, "row": e.row,
                               "col": e.col, "source": op.inst_id})
            if interval > 0:
                v["acc"] = v.get("acc", 0.0) + dt
                if v["acc"] >= interval:
                    v["acc"] = 0.0
                    atk = float(op.attributes.get("atk") or 0)
                    # S3 belt mark first so the burst (triggered by the
                    # talent-attached erosion inside apply_damage) sees it
                    # and applies the extra -30 DEF stack.
                    def_delta = float(bb.get("ep_break_def") or -30.0)
                    self.add_buff(e, {
                        "key": "thumpy_s3_mark",
                        "remaining_ticks": 45,     # refreshed while on belt
                        "layers": 1,
                        "source": op,
                        "blackboard": {"def_delta": def_delta},
                    })
                    if atk_scale and atk > 0:
                        self.apply_damage(e, atk * atk_scale,
                                          DamageType.PHYSICAL, source=op)
                    # water erosion is attached by Thumpy talent 1 inside
                    # apply_damage (physical output), not by the tile itself

    def _trait_tick(self, op, dt):
        """Operator trait periodic effects (merchant cost drain, geek
        \u602a\u6770 HP drain)."""
        trait = getattr(op, "trait_system", None)
        if trait is None:
            return
        drain = trait.cost_drain()
        if drain is not None:
            interval, amount = drain
            if interval <= 0:
                return
            acc = getattr(op, "_trait_drain_acc", 0.0) + dt
            if acc < interval:
                op._trait_drain_acc = acc
                return
            op._trait_drain_acc = 0.0
            if self.cost < amount:
                self.withdraw(op.inst_id)
                return
            self.cost -= amount
            self.emit(self.tick, "trait_cost_drain",
                      {"unit": op.inst_id, "amount": round(amount, 3)})
            # 诗怀雅"大买家"：技能期间每次特性消耗费用 +1 金币（上限
            # 由装备技能 blackboard `sp` 键决定，用于技能消耗）
            if getattr(op, "_coin_max", 0) > 0:
                _sc = getattr(op, "skill_controller", None)
                if _sc is not None and _sc.active is not None:
                    op._coins = min(op._coin_max,
                                    getattr(op, "_coins", 0) + 1)
        if trait.is_geek() and not getattr(op, "dead", False):
            interval = 1.0
            acc = getattr(op, "_trait_geek_acc", 0.0) + dt
            if acc >= interval:
                op._trait_geek_acc = 0.0
                ratio = trait.geek_drain_ratio()
                if ratio > 0:
                    amt = float(op.max_hp) * ratio
                    op.hp = max(1.0, float(op.hp) - amt)
                    self.emit(self.tick, "trait_hp_drain",
                              {"unit": op.inst_id,
                               "amount": round(amt, 3),
                               "hp": round(op.hp, 3)})
            else:
                op._trait_geek_acc = acc

    # ================= funnel (\u9a6b\u68b0\u672f\u5e08) drones =================
    def _funnel_active_bb(self, op):
        sc = getattr(op, "skill_controller", None)
        act = getattr(sc, "active", None)
        if act is None:
            return None
        return getattr(getattr(act, "skill", None), "blackboard", None) or {}

    def _funnel_active_skill_id(self, op):
        sc = getattr(op, "skill_controller", None)
        act = getattr(sc, "active", None)
        if act is None:
            return None
        return getattr(getattr(act, "skill", None), "skill_id", "") or ""

    def _sync_funnel_drones(self, op):
        """Spawn/despawn floating drones to match the active skill count
        (base 1; S1/S2 +1; S3 +2)."""
        trait = getattr(op, "trait_system", None)
        if trait is None or not trait.is_funnel():
            return
        if getattr(op, "dead", False):
            return
        want = trait.funnel_drone_count(self._funnel_active_bb(op))
        drones = getattr(op, "_funnel_drones", None)
        if drones is None:
            drones = []
            op._funnel_drones = drones
        from .entities import FunnelDrone
        while len(drones) < want:
            d = FunnelDrone(op)
            drones.append(d)
            self.emit(self.tick, "funnel_drone",
                      {"unit": op.inst_id, "drone": d.inst_id,
                       "type": "spawn"})
        while len(drones) > want:
            d = drones.pop()
            self.emit(self.tick, "funnel_drone",
                      {"unit": op.inst_id, "drone": d.inst_id,
                       "type": "despawn"})

    def _funnel_targets(self, op):
        """Drone candidates: whole battlefield for S3 (\u6f84\u95ea\u7684\u7f24\u7401
        / skchr_gdglow_3), otherwise enemies in the operator's current range."""
        if self._funnel_active_skill_id(op) == "skchr_gdglow_3":
            return [e for e in self.get_enemies() if not e.dead]
        shape = getattr(op, "range_shape", None) or []
        cells = {(op.row + dr, op.col + dc) for dr, dc in shape}
        return [e for e in self.get_enemies()
                if not e.dead and (e.row, e.col) in cells]

    def _update_funnel_drones(self, dt):
        """Advance each funnel operator's floating drones: re-acquire a
        target when the old one dies, keep attacking the same enemy to build
        the damage ramp, apply S3 sluggish, and settle magical damage."""
        from .targeting import HateSystem
        for op in self.operators:
            trait = getattr(op, "trait_system", None)
            if trait is None or not trait.is_funnel() or op.dead:
                continue
            if op.in_deploy_anim(self.tick):
                continue
            drones = getattr(op, "_funnel_drones", None) or []
            if not drones:
                continue
            params = dict(trait.funnel_params())
            if self._funnel_active_skill_id(op) == "skchr_rockr_2":
                _s = (self._funnel_active_bb(op) or {}).get("scale")
                if _s:
                    params["max"] = params["max"] * float(_s)
                    params["max_stack"] = max(
                        params["max_stack"],
                        int(round((params["max"] - params["init"])
                                  / params["delta"])))
            interval = op.attributes.attack_interval()
            for d in drones:
                d.attack_timer -= dt
                if d.attack_timer > 0:
                    continue
                d.attack_timer = interval
                tgt = d.target
                if tgt is None or getattr(tgt, "dead", False):
                    d.target = None
                    d.stacks = 0
                    cands = self._funnel_targets(op)
                    if cands:
                        d.target = HateSystem(self).operator_target(
                            op, candidates=cands)
                if d.target is None:
                    continue
                scale = min(params["max"],
                            params["init"] + params["delta"] * d.stacks)
                d.stacks = min(d.stacks + 1, params["max_stack"])
                atk = float(op.attributes.get("atk") or 0)
                amt = atk * scale
                self.apply_damage(d.target, amt, DamageType.MAGICAL,
                                  source=op)
                if self._funnel_active_skill_id(op) == "skchr_gdglow_3":
                    try:
                        from .traits import _sluggish_buff
                        self.add_buff(d.target, _sluggish_buff(op, 0.5))
                    except Exception:
                        pass
                # Goldenglow talent 1 \u4fe1\u6807\u7684\u6012\u706b: while a
                # skill is active each drone may self-destruct.
                _ts = getattr(op, "talent_system", None)
                _prob = _ts.bb("attack@prob") if _ts else None
                if _prob is not None and self._funnel_active_bb(op) is not None:
                    self._funnel_try_destruct(op, d, float(_prob), _ts)
                self.emit(self.tick, "funnel_attack",
                          {"unit": op.inst_id, "drone": d.inst_id,
                           "target": d.target.inst_id,
                           "atkScale": round(scale, 4),
                           "stacks": d.stacks,
                           "amount": round(amt, 3),
                           "type": "MAGICAL"})

    def _funnel_try_destruct(self, op, drone, prob, ts):
        """Goldenglow talent 1 \u4fe1\u6807\u7684\u6012\u706b: per-drone
        self-destruct layer (1.5% per layer, +1 on failed attacks, 40 layers
        -> guaranteed). On success deal ATK * attack@atk_scale_2 magical
        damage to enemies within radius 1.1 (3x3) of the target, reset the
        drone's layers and trait ramp, and apply S3 sluggish."""
        layers = int(getattr(drone, "destruct_layers", 1) or 1)
        max_layers = int(float(ts.bb("attack@max_stack_cnt") or 40.0))
        chance = min(1.0, layers * prob)
        if not self.rng.chance(chance) and layers < max_layers:
            drone.destruct_layers = layers + 1
            return
        scale = float(ts.bb("attack@atk_scale_2") or 2.0)
        atk = float(op.attributes.get("atk") or 0)
        tgt = drone.target
        victims = [e for e in self.get_enemies()
                   if not e.dead and abs(e.row - tgt.row) <= 1
                   and abs(e.col - tgt.col) <= 1]
        ids = []
        total = 0.0
        for e in victims:
            ids.append(e.inst_id)
            amt = atk * scale
            total += amt
            self.apply_damage(e, amt, DamageType.MAGICAL, source=op)
            if self._funnel_active_skill_id(op) == "skchr_gdglow_3":
                try:
                    from .traits import _sluggish_buff
                    self.add_buff(e, _sluggish_buff(op, 0.5))
                except Exception:
                    pass
        drone.destruct_layers = 1
        drone.stacks = 0
        self.emit(self.tick, "funnel_destruct",
                  {"unit": op.inst_id, "drone": drone.inst_id,
                   "target": tgt.inst_id, "atkScale": round(scale, 4),
                   "targets": ids, "amount": round(total, 3)})

    # ================= talent auras (instructor family) =================
    def _update_talent_auras(self):
        """Re-evaluate ally talent auras each tick (3-star / melee / block
        capacity / self-blocking conditions) and keep buffs in sync."""
        new_applied = set()
        named = {}   # (tgt_inst_id, name) -> (spec, source_op), max value
        for op in list(self.operators):
            if op.dead:
                continue
            ts = getattr(op, "talent_system", None)
            specs = []
            if ts is not None:
                try:
                    specs = list(ts.aura_specs() or [])
                except Exception:
                    specs = []
            # active-skill auras (e.g. \u6851\u8393 S2 \u5b89\u5168\u533a\u57df:
            # allies in range take less element damage while the skill runs)
            try:
                _sas = getattr(op, "_skill_aura_specs", None) or []
                specs += [s for s in _sas if s.get("enabled", True)]
            except Exception:
                pass
            if not specs:
                continue
            for spec, tgt in self._aura_targets(op, specs):
                nm = spec.get("named")
                if nm:
                    key0 = (tgt.inst_id, nm)
                    cur = named.get(key0)
                    if cur is None or float(spec.get("value") or 0.0) > \
                            float(cur[0].get("value") or 0.0):
                        named[key0] = (spec, op)
                    # named conditional auras include the owner when the
                    # owner itself qualifies (Pallas is a [\u7c73\u8bfa\u65af]
                    # operator, PRTS confirms she receives her own buff)
                    if self._aura_target_ok(op, op, spec):
                        key1 = (op.inst_id, nm)
                        cur1 = named.get(key1)
                        if cur1 is None or \
                                float(spec.get("value") or 0.0) > \
                                float(cur1[0].get("value") or 0.0):
                            named[key1] = (spec, op)
                    continue
                # value in the key: when the aura magnitude changes (e.g.
                # \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 T2 doubled by S3), a new
                # key is created and the stale one is dropped by the sync.
                if spec.get("skill_id"):
                    key = "skill_aura:%d:%s:%.6g" % (
                        op.inst_id, spec["stat"],
                        float(spec.get("value") or 0.0))
                else:
                    key = "talent_aura:%d:%s:%.6g" % (
                        op.inst_id, spec["stat"],
                        float(spec.get("value") or 0.0))
                b = {"key": key, "stat": spec["stat"],
                     spec["layer"]: spec["value"],
                     "remaining_ticks": 30 * 3600,
                     "source": op}
                self.add_buff(tgt, b)
                new_applied.add((tgt.inst_id, key))
        # same-name conditional buffs (e.g. peak_performance) take the max
        # across all aura owners, applied as a single per-target buff
        for (tid, nm), (spec, src_op) in named.items():
            unit = self._unit_by_inst(tid)
            if unit is None or unit.dead:
                continue
            key = "talent_aura:%s:%d" % (nm, tid)
            b = {"key": key, "stat": spec["stat"],
                 spec["layer"]: spec["value"],
                 "remaining_ticks": 30 * 3600,
                 "source": src_op}
            self.add_buff(unit, b)
            new_applied.add((tid, key))
        old = getattr(self, "_aura_applied", set())
        for tid, key in old - new_applied:
            unit = self._unit_by_inst(tid)
            if unit is not None:
                self.buffs.remove(unit, key)
        self._aura_applied = new_applied

    def _update_enemy_talent_auras(self):
        """Evaluate enemy-side talent auras per tick (e.g. \u9152\u795e T2
        \u5760\u68a6). Two sync groups, one buff key per enemy each:
          - phatm2_t_2[attack_speed]: every enemy in SANITY burst recovery
            gets attack_speed -12/-16 while \u9152\u795e is on field;
          - phatm2_t_2: enemies inside her attack range get the 70-sanity-
            per-normal-attack listener buff.
        Stale buffs are removed when she retreats / conditions change."""
        new_applied = set()
        for op in list(self.operators):
            if op.dead:
                continue
            ts = getattr(op, "talent_system", None)
            if ts is None:
                continue
            try:
                specs = ts.enemy_aura_specs()
            except Exception:
                specs = []
            for spec in specs:
                kind = spec.get("kind")
                if kind == "phatm2_t2_speed":
                    for e in list(self.enemies):
                        if e.dead:
                            continue
                        if self.buffs.get(e, "ep_burst_cd_0"):
                            if not self.buffs.get(e, "phatm2_t_2[attack_speed]"):
                                self.add_buff(e, {
                                    "key": "phatm2_t_2[attack_speed]",
                                    "stat": "attackSpeed",
                                    "add": float(spec["attack_speed"]),
                                    "remaining_ticks": 30 * 3600,
                                    "layers": 1, "source": op})
                            new_applied.add(
                                (e.inst_id, "phatm2_t_2[attack_speed]"))
                elif kind == "phatm2_t2_attack":
                    try:
                        cells = {(op.row + dr, op.col + dc)
                                 for dr, dc in op.range_shape}
                    except Exception:
                        cells = set()
                    for e in list(self.enemies):
                        if e.dead or (e.row, e.col) not in cells:
                            continue
                        if not self.buffs.get(e, "phatm2_t_2"):
                            self.add_buff(e, {
                                "key": "phatm2_t_2",
                                "template_key": "phatm2_t_2",
                                "remaining_ticks": 30 * 3600,
                                "layers": 1, "source": op,
                                "blackboard": {"value": float(
                                    spec["value"])}})
                        new_applied.add((e.inst_id, "phatm2_t_2"))
        old = getattr(self, "_enemy_aura_applied", set())
        stale = old - new_applied
        if stale:
            by_inst = {}
            for e in self.enemies:
                by_inst.setdefault(e.inst_id, e)
            for eid, key in stale:
                u = by_inst.get(eid)
                if u is not None:
                    self.buffs.remove(u, key)
        self._enemy_aura_applied = new_applied

    def _aura_targets(self, op, specs):
        out = []
        for spec in specs:
            if spec["scope"] == "self":
                out.append((spec, op))
                continue
            if spec["scope"] == "field":
                cands = [u for u in self.get_operators() if not u.dead]
            elif spec["scope"] == "range":
                # allies standing on the owner's range tiles (the owner's
                # own tile counts when the range shape includes (0,0))
                try:
                    cells = {(op.row + dr, op.col + dc)
                             for dr, dc in op.range_shape}
                except Exception:
                    cells = set()
                cands = [u for u in self.get_operators()
                         if not u.dead and (u.row, u.col) in cells]
            else:  # cell8: the 8 surrounding tiles
                cands = [u for u in self.get_operators()
                         if not u.dead and u is not op
                         and abs(u.row - op.row) <= 1
                         and abs(u.col - op.col) <= 1]
            for u in cands:
                if u.dead:
                    continue
                if u is op and spec["scope"] not in ("range",):
                    continue
                if not self._aura_target_ok(op, u, spec):
                    continue
                out.append((spec, u))
        return out

    def _aura_target_ok(self, op, u, spec):
        target = spec.get("target")
        if target == "melee":
            if int(getattr(u, "position", 1) or 1) != 1:
                return False
        elif target == "rarity3":
            data = self._char_base(getattr(u, "char_id", "")) or {}
            if int(data.get("rarity") or 0) != 3:
                return False
        elif target == "minos":
            data = self._char_base(getattr(u, "char_id", "")) or {}
            if data.get("nationId") != "minos":
                return False
        cond = spec.get("cond")
        if cond == "hp_gt":
            ratio = float(spec.get("hp_ratio") or 0.8)
            if float(u.hp) / max(1e-6, float(u.max_hp)) <= ratio:
                return False
        elif cond == "block_ge3":
            if int(u.attributes.get("blockCnt") or 0) < 3:
                return False
        elif cond == "block_lt3":
            if int(u.attributes.get("blockCnt") or 0) >= 3:
                return False
        elif cond == "ep_over_half":
            try:
                from .targeting import _unit_ep_over_half
                if not _unit_ep_over_half(u, self):
                    return False
            except Exception:
                return False
        return True

    def _unit_by_inst(self, inst_id):
        for u in (list(self.get_operators()) + list(self.get_tokens())
                  + list(self.get_enemies())):
            if getattr(u, "inst_id", None) == inst_id:
                return u
        return None

    def _trait_hit(self, op, target):
        """Apply the operator's class trait on a basic-attack hit."""
        trait = getattr(op, "trait_system", None)
        if trait is None or target is None or getattr(target, "dead", False):
            return
        try:
            trait.on_hit(target, self)
        except Exception:
            pass

    def _apply_agoat2_t1(self, op, target):
        """\u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 T1 \u6c29\u6c33: a normal heal
        gives the target a HoT (real template agoat2_t_1): every second an
        extra ATK x heal_scale HP heal + element recovery, stacking up to 3;
        re-application resets the duration and updates the cached ATK
        (PRTS).  Uses the wandermedic trait ep_heal_ratio for the element
        recovery."""
        if getattr(op, "char_id", "") != "char_1016_agoat2":
            return
        ts = getattr(op, "talent_system", None)
        if ts is None or getattr(target, "dead", False):
            return
        ratio = float(ts.bb_exact("heal_scale") or 0.0)
        duration = float(ts.bb_exact("duration") or 0.0)
        max_stack = int(float(ts.bb_exact("max_stack_cnt") or 3.0))
        if ratio <= 0 or duration <= 0:
            return
        cached = float(op.attributes.get("atk") or 0.0)
        ep_ratio = 0.5
        try:
            tr = getattr(op, "trait_system", None)
            if tr is not None:
                ep_ratio = float(tr.ep_heal_ratio())
        except Exception:
            pass
        existing = self.buffs.get(target, "agoat2_t_1")
        if existing is not None:
            bb = existing.setdefault("blackboard", {})
            bb["dynamic"] = cached
            bb["heal_scale"] = ratio
            bb["ep_heal_ratio"] = ep_ratio
            cur = float(bb.get("stack_cnt", 1.0) or 1.0)
            bb["stack_cnt"] = min(float(max_stack), cur + 1.0)
            existing["remaining_ticks"] = int(duration * 30)
            existing["layers"] = int(bb["stack_cnt"])
            return
        self.add_buff(target, {
            "key": "agoat2_t_1", "template_key": "agoat2_t_1",
            "remaining_ticks": int(duration * 30),
            "_trigger_interval": 30, "layers": 1,
            "source": op,
            "blackboard": {
                "dynamic": cached, "heal_scale": ratio,
                "ep_heal_ratio": ep_ratio, "stack_cnt": 1.0,
                "max_stack_cnt": float(max_stack),
            },
        })

    def _operator_attack(self, op, target, interval, atk_scale=1.0,
                         targets=None, hits=1, hit_scales=None,
                         fortress_splash=False):
        """Start an operator/token attack windup: damage (melee) or the
        projectile launch (ranged) lands at the spine OnAttack hit frame,
        i.e. ``interval * hit_frame_ratio`` after the attack starts.
        ``atk_scale`` scales the hit damage (hunter trait 120%).
        ``targets`` (multi-target trait: centurion/pusher attack all
        blocked enemies) is snapshotted at windup; when None the pending
        attack keeps the single ``target``.  ``fortress_splash`` marks a
        fortress (\u8981\u585e) ranged splash attack: at the hit frame the
        whole 3x3 block around the target takes physical ATK damage."""
        dmg_type = self._char_damage_type(op)
        _sc = getattr(op, "skill_controller", None)
        _act = getattr(_sc, "active", None) if _sc is not None else None
        if _act is not None:
            try:
                _ov = _act.damage_type_switch()
                if _ov is not None:
                    dmg_type = _ov
            except Exception:
                pass
        _pos = int(getattr(op, "position", 1) or 1)
        _sub = getattr(op, "sub_profession_id", None)
        if _pos == 2:
            # ranged operators (snipers/casters/supporters/...): projectile
            ranged = True
        elif _sub == "instructor":
            # instructor (\u6559\u5b98) attacks are melee swings even at the
            # 2-tile front range (no projectile)
            ranged = False
        elif (getattr(op, "trait_system", None) is not None
              and getattr(op, "trait_system", None).is_fortress()):
            # fortress (\u8981\u585e): blocking -> melee swing at the
            # blocked target; not blocking -> fortress_splash branch
            # (ranged 3x3 AOE) resolves directly at the hit frame
            ranged = False
        elif any((dr, dc) == (0, 0) for dr, dc in op.range_shape):
            # melee-shaped unit (guard/vanguard/defender/specialist): melee
            # when the target is adjacent; hybrid units (lord \u9886\u4e3b)
            # launch a projectile when attacking at range
            ranged = bool(op.range_shape) and not (
                abs(op.row - target.row) <= 1 and
                abs(op.col - target.col) <= 1)
        else:
            ranged = bool(op.range_shape)
        _trait = getattr(op, "trait_system", None)
        if _trait is not None:
            try:
                atk_scale *= _trait.atk_scale(ranged=ranged)
            except Exception:
                pass
        try:
            from .attack_timing import hit_frame_ratio
            ratio = hit_frame_ratio(
                getattr(op, "char_id", "") or getattr(op, "token_id", ""),
                "Attack")
        except Exception:
            ratio = 0.5
        if not (0 < float(ratio) < 1):
            ratio = float(getattr(op, "hit_frame_ratio", 0.5) or 0.5)
        op.hit_frame_ratio = float(ratio)
        frames = max(1, int(round(interval * float(ratio) * 30.0)))
        _heal_shots = 1
        _heal_scale = 1.0
        if targets is None:
            _ts = getattr(op, "trait_system", None)
            # multi-target heal skills (e.g. \u871c\u8393 S1/S2): the heal
            # action snapshots the top-N in-range allies in game priority
            # order (wandermedic ep/hp ordering from targeting).
            _sc2 = getattr(op, "skill_controller", None)
            _act2 = getattr(_sc2, "active", None) if _sc2 else None
            _heal_n = 1
            _shots = 1
            _hscale = 1.0
            if _ts is not None and _act2 is not None:
                if _ts.is_healer() or _ts.heal_while_skill():
                    try:
                        _heal_n = int(_act2.heal_max_target())
                        _shots = int(_act2.heal_shot_count())
                        _hscale = float(_act2.heal_attack_scale())
                    except Exception:
                        _heal_n, _shots, _hscale = 1, 1, 1.0
            if _heal_n > 1 or _shots > 1:
                from .targeting import HateSystem
                # snapshot enough candidates for the distinct multi-target
                # heal (top-N) and/or the sequential shots (cycle through
                # the ordered candidates when fewer than shots).
                targets = HateSystem(self).operator_targets(
                    op, max(_heal_n, _shots))
            _heal_shots = _shots
            _heal_scale = _hscale
            # active skill attack@max_target: basic attacks hit up to N
            # in-range enemies (e.g. silverash S3 zhen-yin-zhan, guards
            # with multi-target switch attacks)
            if targets is None:
                _amt = None
                if _act2 is not None:
                    try:
                        _amt = (getattr(_act2, "attack_effects", {}) or {}
                                ).get("max_target")
                    except Exception:
                        _amt = None
                if _amt is not None and int(_amt) > 1:
                    cand = [e for e in self.get_enemies()
                            if not getattr(e, "dead", False)
                            and op.range_shape and any(
                                (op.row + dr, op.col + dc) == (e.row, e.col)
                                for dr, dc in op.range_shape)]
                    cand.sort(key=lambda e: (e is not target, e.hp))
                    targets = cand[:int(_amt)]
                elif _ts is not None:
                    try:
                        if _ts.attack_all_blocked():
                            targets = [e for e in list(
                                getattr(op, "blocked_enemies", []) or [])
                                if not getattr(e, "dead", False)
                                and getattr(e, "blocked_by", None) is op]
                        elif _ts.attack_all_in_range():
                            targets = [e for e in self.get_enemies()
                                       if not getattr(e, "dead", False)
                                       and op.range_shape and any(
                                           (op.row + dr, op.col + dc) ==
                                           (e.row, e.col)
                                           for dr, dc in op.range_shape)]
                    except Exception:
                        targets = None
        if targets:
            target = targets[0]
        target_scales = None
        _tr = getattr(op, "trait_system", None)
        if _tr is not None and _tr.is_reaperrange() and targets:
            # reaperrange (\u6536\u5272\u8005\uff08\u8fdc\uff09): enemies on
            # the front row take 150% ATK, the rest take full ATK
            target_scales = [
                (_tr.reaperrange_atk_scale()
                 if _tr.reaperrange_front_row(t) else 1.0)
                for t in targets]
        op._pending_attack = {
            "target": target,
            "targets": list(targets) if targets else None,
            "heal_shots": _heal_shots,
            "heal_scale": _heal_scale,
            "remaining": frames,
            "ranged": ranged,
            "dmg_type": dmg_type,
            "atk_scale": float(atk_scale),
            "hits": max(1, int(hits)),
            "hit_scales": (list(hit_scales) if hit_scales
                           else [float(atk_scale)] * max(1, int(hits))),
            "fortress_splash": bool(fortress_splash),
            "target_scales": target_scales,
        }
        op.attack_timer = interval

    def _pending_attack_live(self, pa):
        """Prune dead targets out of a pending operator attack; returns the
        pruned dict (primary target refreshed) or None when nothing to hit."""
        targets = pa.get("targets")
        if targets:
            live = [t for t in targets
                    if t is not None and not getattr(t, "dead", False)]
            if not live:
                return None
            pa["targets"] = live
            pa["target"] = live[0]
        else:
            t = pa.get("target")
            if t is None or getattr(t, "dead", False):
                return None
        return pa

    def _resolve_operator_attack(self, op, pa):
        """Hit frame reached: melee deals damage, ranged launches the
        projectile; on-attack skill effects and SP recovery fire here."""
        targets = pa.get("targets")
        if targets:
            targets = [t for t in targets
                       if t is not None and not getattr(t, "dead", False)]
        else:
            t = pa.get("target")
            targets = ([t] if t is not None
                       and not getattr(t, "dead", False) else [])
        if not targets:
            return False
        target = targets[0]
        # medic / healer basic attack heals the wounded ally instead
        if getattr(target, "side", 0) == 1:
            amount = float(op.attributes.get("atk") or 0)
            _bts = getattr(op, "trait_system", None)
            if _bts is not None and _bts.is_blessing():
                amount *= _bts.blessing_heal_scale()
            _shots = int(pa.get("heal_shots", 1) or 1)
            _hscale = float(pa.get("heal_scale", 1.0) or 1.0)
            amount *= _hscale
            healed_ids = []
            if _shots > 1:
                # sequential shots (e.g. \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S3
                # \u706b\u5c71\u56de\u97ff 5 \u8fde\u53d1): each shot re-picks the
                # top not-yet-selected ally; cycle through the ordered
                # snapshot when there are fewer candidates than shots.
                ordered = [t for t in targets
                           if getattr(t, "side", 0) == 1]
                for i in range(_shots):
                    if not ordered:
                        break
                    t = ordered[i % len(ordered)]
                    self.apply_heal(t, amount, source=op, ep_scale=_hscale)
                    self._trait_hit(op, t)
                    self._apply_agoat2_t1(op, t)
                    healed_ids.append(t.inst_id)
            else:
                for t in targets:
                    if getattr(t, "side", 0) != 1:
                        continue
                    self.apply_heal(t, amount, source=op, ep_scale=_hscale)
                    # chainhealer trait: heal jumps to further wounded allies
                    self._trait_hit(op, t)
                    self._apply_agoat2_t1(op, t)
                    healed_ids.append(t.inst_id)
            self.emit(self.tick, EventType.ATTACK,
                      {"unit": op.inst_id, "target": target.inst_id,
                       "targets": healed_ids,
                       "heal": True})
            return True
        dmg_type = pa.get("dmg_type", DamageType.PHYSICAL)
        atk_scale = float(pa.get("atk_scale", 1.0) or 1.0)
        scales = pa.get("hit_scales") or [atk_scale]
        if pa.get("fortress_splash"):
            # fortress (\u8981\u585e) not blocking: ranged splash on the
            # target tile (radius 1.0 = 3x3 block), full physical ATK each.
            atk = float(op.attributes.get("atk") or 0.0)
            radius = 1.0
            _fs = getattr(op, "trait_system", None)
            if _fs is not None:
                try:
                    radius = _fs.fortress_splash_radius()
                except Exception:
                    pass
            victims = [e for e in self.get_enemies()
                       if not getattr(e, "dead", False)
                       and abs(e.row - target.row) <= radius
                       and abs(e.col - target.col) <= radius]
            ids = []
            total = 0.0
            for e in victims:
                amt = atk * atk_scale
                ids.append(e.inst_id)
                total += amt
                self.apply_damage(e, amt, dmg_type, source=op)
                self._trait_hit(op, e)
                self._on_operator_hit_heal(op, e)
            sc = getattr(op, "skill_controller", None)
            if sc is not None and sc.active is not None:
                for e in victims:
                    try:
                        sc.active.apply_on_attack(e)
                    except Exception:
                        pass
            self.emit(self.tick, EventType.ATTACK,
                      {"unit": op.inst_id, "target": target.inst_id,
                       "targets": ids, "type": "fortress_splash",
                       "amount": round(total, 3)})
            return True
        tscales = pa.get("target_scales")
        # multi-hit switch attacks (attack@times with an atk_scale, e.g.
        # Chen S3 zhen-ying 10-hit slash / Exusiai S3 overload): the basic
        # attack IS the combo - skip the plain hit and let apply_on_attack
        # land the `times` hits below (otherwise 1+n hits).
        _sc4 = getattr(op, "skill_controller", None)
        _act4 = getattr(_sc4, "active", None) if _sc4 else None
        _replace = False
        if _act4 is not None:
            try:
                _ae4 = getattr(_act4, "attack_effects", {}) or {}
                if int(_ae4.get("times") or 1) > 1 and \
                        float(_ae4.get("atk_scale") or 0.0) > 0:
                    _replace = True
            except Exception:
                _replace = False
        if _replace:
            pass
        elif pa.get("ranged"):
            _pkey = "op_%s" % (getattr(op, "char_id", None)
                               or getattr(op, "token_id", "tok"))
            _sc_r = getattr(op, "skill_controller", None)
            _has_active_r = _sc_r is not None and _sc_r.active is not None
            _tsb_r = getattr(op, "token_steal_bb", None)
            for ti, t in enumerate(targets):
                _tsc = tscales[ti] if tscales else 1.0
                for s in scales:
                    _scale = s * _tsc
                    if _has_active_r or _tsb_r:
                        def _hit_extra(battle, proj, oo=op, ss=_scale,
                                       dd=dmg_type, act=_sc_r.active,
                                       aa=_has_active_r, tb=_tsb_r):
                            tg = proj.target
                            if getattr(tg, "side", 0) != 0:
                                return
                            if aa and act is not None:
                                act.apply_on_attack(tg)
                                battle._apply_attack_steal(oo, tg, act)
                            elif tb:
                                battle._apply_attack_steal(oo, tg, None)
                        self.spawn_projectile(op, t, _pkey, dmg_type,
                                              atk_scale=_scale,
                                              hit_extra=_hit_extra)
                    else:
                        self.spawn_projectile(op, t, _pkey, dmg_type,
                                              atk_scale=_scale)
        else:
            atk = float(op.attributes.get("atk") or 0.0)
            for ti, t in enumerate(targets):
                _tsc = tscales[ti] if tscales else 1.0
                for s in scales:
                    self.apply_damage(t, atk * s * _tsc, dmg_type,
                                      source=op)
                self._trait_hit(op, t)
                self._on_operator_hit_heal(op, t)
        # active-skill on-attack effects (attack@* blackboard)
        sc = getattr(op, "skill_controller", None)
        has_active = sc is not None and sc.active is not None
        for t in targets:
            if getattr(t, "side", 0) != 0:
                continue
            if pa.get("ranged") and not _replace:
                # ranged attack-attached effects (EP / extra hits / steal)
                # land with the projectile (PRTS: 攻击附带的元素损伤紧接在
                # 当次攻击的伤害后处理).  Switch-attack combos (_replace,
                # e.g. Exusiai S3 / Chen S3) fire their hits at resolve.
                continue
            if has_active:
                sc.active.apply_on_attack(t)
                self._apply_attack_steal(op, t, sc.active)
            elif getattr(op, "token_steal_bb", None):
                self._apply_attack_steal(op, t, None)
        self.emit(self.tick, EventType.ATTACK,
                  {"unit": op.inst_id, "target": target.inst_id,
                   "targets": [t.inst_id for t in targets]})
        return True

    def _on_operator_hit_heal(self, op, target):
        """Pallas talent 2 \u5973\u795e\u7684\u632f\u594b: each attack on an
        enemy heals herself and the friendly operator in the tile directly in
        front (facing direction) for a flat amount (40/45)."""
        if target is None or getattr(target, "side", 0) == 1:
            return
        ts = getattr(op, "talent_system", None)
        if ts is None or getattr(op, "dead", False):
            return
        try:
            v = ts.attack_heal_flat()
        except Exception:
            return
        if not v or v <= 0:
            return
        _dirs = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        dr, dc = _dirs.get(int(getattr(op, "direction", 1) or 1), (0, 1))
        self.apply_heal(op, v, source=op)
        fr, fc = op.row + dr, op.col + dc
        for ally in list(self.operators):
            if ally is op or ally.dead:
                continue
            if (ally.row, ally.col) == (fr, fc):
                self.apply_heal(ally, v, source=op)
                break

    def _tick_hp_regen(self, dt):
        """Attribute-based HP recovery (hpRecoveryPerSec):
        operators and tokens regenerate continuously; bypasses
        heal-free (attribute regen is not a heal action)."""
        for u in list(self.operators) + list(self.tokens):
            if u.dead or u.hp >= u.max_hp:
                continue
            rate = float(u.attributes.get("hpRecoveryPerSec") or 0.0)
            if rate > 0:
                u.hp = min(float(u.max_hp), u.hp + rate * dt)

    def _check_enemy_overlap(self, e):
        """Fire ON_ENTITY_WILL_OVERLAP / ON_OWNER_OVERLAPPED when an enemy
        enters a tile shared with another unit (the tile has overlap
        enabled - trap_ftshad \u7a7a\u58f3 / mylyss - or the occupant
        explicitly allows this enemy source - trap_trpot / ubodst)."""
        t = self.map.tile(getattr(e, "row", 0), getattr(e, "col", 0))
        if t is None:
            return
        e_key = getattr(e, "enemy_key", "") or ""
        for u in list(self.tokens) + list(self.operators):
            if getattr(u, "dead", False):
                continue
            if (getattr(u, "row", 0), getattr(u, "col", 0)) != \
                    (getattr(e, "row", 0), getattr(e, "col", 0)):
                continue
            allowed = bool(getattr(t, "_overlap_enabled", False))
            u_ids = getattr(u, "_overlap_source_ids", None) or set()
            e_ids = getattr(e, "_overlap_source_ids", None) or set()
            if not allowed and e_key not in u_ids and \
                    not (u_ids & e_ids):
                continue
            self._dispatch_buff_events(u, "ON_ENTITY_WILL_OVERLAP",
                                       source=e, target=e)
            self._dispatch_buff_events(u, "ON_OWNER_OVERLAPPED",
                                       source=e, target=e)

    def _trigger_traps(self):
        """Traper (\u9677\u9631\u5e08) mines: an enemy stepping onto a trap
        token's tile fires it - physical ATK x atk_scale damage, constraint
        bind (UNMOVABLE), optional push - then the trap is consumed."""
        from .consts import AbnormalFlag as _AF
        fired = []
        for tok in list(self.tokens):
            tid = getattr(tok, "token_id", "") or ""
            if tid == "token_10031_swire2_gdtrap" \
                    and not getattr(tok, "dead", False):
                self._trigger_champagne(tok)
                continue
            if "_mine" not in tid or getattr(tok, "dead", False):
                continue
            bb = getattr(tok, "token_skill_bb", None) or {}
            trig = [e for e in self.enemies
                    if not getattr(e, "dead", False)
                    and e.row == tok.row and e.col == tok.col]
            if not trig:
                continue
            for e in trig:
                atk = float(tok.attributes.get("atk") or 0.0)
                scale = float(bb.get("atk_scale") or 1.0)
                if atk > 0:
                    self.apply_damage(e, atk * scale, DamageType.PHYSICAL,
                                      source=tok)
                constraint = bb.get("constraint")
                if constraint:
                    self.add_abnormal(e, _AF.UNMOVABLE, float(constraint),
                                      source=tok)
                force = bb.get("force")
                if force and float(force) > 0:
                    dr = dc = 0
                    try:
                        idx = e.game_map.idx(e.row, e.col) if e.game_map \
                            else -1
                        nxt = (e._next_map[idx] if idx >= 0 and e._next_map
                               else -1)
                        if nxt >= 0 and e.game_map:
                            nr, nc = e.game_map.rc(nxt)
                            dr, dc = nr - e.row, nc - e.col
                    except Exception:
                        pass
                    if dr or dc:
                        self.displace(e, dr, dc, 1.0, source=tok,
                                      kind="effect")
                fired.append((tok.inst_id, e.inst_id))
        for tok_id, e_id in fired:
            self.emit(self.tick, "trap_fired",
                      {"token": tok_id, "target": e_id})
            for tok in list(self.tokens):
                if tok.inst_id == tok_id and not tok.dead:
                    self._retire_token(tok, reason="trap_fired")
                    break
        return fired

    def _trigger_champagne(self, tok):
        """诗怀雅 S2"见面礼"香槟炸弹：触碰首个敌人造成 owner 攻击力 ×
        attack@atk_scale 物理伤害并停顿 attack@sluggish 秒；在场满
        duration_switch（3s）后可额外触发一次（共 2 次），用完消失。"""
        from .consts import AbnormalFlag as _AF
        bb = getattr(tok, "token_skill_bb", None) or {}
        owner = tok.owner
        if owner is None or getattr(owner, "dead", False):
            return
        trig = [e for e in self.enemies
                if not getattr(e, "dead", False)
                and e.row == tok.row and e.col == tok.col]
        if not trig:
            return
        hits = getattr(tok, "_bomb_hits", 0)
        spawn_tick = getattr(tok, "_bomb_spawn_tick", self.tick)
        switch = float(bb.get("duration_switch") or 0.0)
        max_hits = 2 if self.tick - spawn_tick >= int(switch * 30) else 1
        if hits >= max_hits:
            return
        atk = float(owner.attributes.get("atk") or 0.0)
        scale = float(bb.get("attack@atk_scale") or 0.0)
        slg = float(bb.get("attack@sluggish") or 0.0)
        e = trig[0]
        if atk > 0 and scale > 0:
            self.apply_damage(e, atk * scale, DamageType.PHYSICAL,
                              source=owner)
        if slg > 0:
            self.add_buff(e, {"key": "op_sluggish_atk",
                              "remaining_ticks": int(slg * 30),
                              "layers": 1, "mul": -0.5,
                              "stat": "moveSpeed", "source": owner})
        hits += 1
        tok._bomb_hits = hits
        if hits >= 2:
            self._retire_token(tok, reason="trigger")

    def _update_operators(self, dt):
        from .targeting import HateSystem
        hate = HateSystem(self)
        # tokens attack like operators (skill-driven towers use maxHp ratio)
        for tok in list(self.tokens):
            if tok.dead:
                continue
            if getattr(tok, "expire_tick", None) is not None \
                    and self.tick >= tok.expire_tick:
                self._retire_token(tok, reason="expire")
                continue
            self._token_periodic(tok, dt)
            # trap_237_hlnpcb (圣堂保育员扮演者): full-map aura - every
            # second friendly units recover attack@sp SP; sleeping (DOZE)
            # allies get attack@sleeper_sp extra.
            if tok.token_id == "trap_237_hlnpcb":
                _hb = tok.token_skill_bb or {}
                _acc = getattr(tok, "_hlnpcb_acc", 0.0) + dt
                tok._hlnpcb_acc = _acc
                if _acc >= 1.0:
                    tok._hlnpcb_acc = 0.0
                    _sp = float(_hb.get("attack@sp") or 0.0)
                    _ssp = float(_hb.get("attack@sleeper_sp") or 0.0)
                    for _u in list(self.get_operators()) + \
                            list(self.get_tokens()):
                        if _u.dead or getattr(_u, "sp_max", 0) <= 0:
                            continue
                        _add = _sp
                        if _ssp and _u.flag(43):    # DOZE 睡眠
                            _add += _ssp
                        if _add > 0:
                            _u.sp = min(float(_u.sp_max),
                                        float(_u.sp or 0.0) + _add)
            if tok._pending_attack is not None:
                pa = self._pending_attack_live(tok._pending_attack)
                if pa is None:
                    tok._pending_attack = None
                else:
                    pa["remaining"] -= 1
                    if pa["remaining"] <= 0:
                        self._resolve_operator_attack(tok, pa)
                        tok._pending_attack = None
            tok.attack_timer -= dt
            if tok.attack_timer <= 0:
                # trap_200_muulcl (喷射汽水机): sprays a random friendly
                # operator every 0.2s, granting attack@sp SP on hit.
                if tok.token_id == "trap_200_muulcl":
                    _mb = tok.token_skill_bb or {}
                    _sp = float(_mb.get("attack@sp") or 0.0)
                    if _sp > 0:
                        _allies = [u for u in list(self.get_operators()) +
                                   list(self.get_tokens())
                                   if not u.dead and u is not tok
                                   and getattr(u, "sp_max", 0) > 0]
                        if _allies:
                            try:
                                _u = self.rng.choice(_allies)
                            except Exception:
                                _u = _allies[0]
                            _u.sp = min(float(_u.sp_max),
                                        float(_u.sp or 0.0) + _sp)
                    tok.attack_timer = tok.attributes.attack_interval()
                    continue
                _tok_atk = tok.attributes.get("atk")
                try:
                    _tok_scale = self._bb_like(
                        tok.token_skill_bb or {}, ".atk_scale")
                    if _tok_scale is None:
                        _tok_scale = (tok.token_skill_bb or {}).get(
                            "atk_scale")
                except Exception:
                    _tok_scale = None
                if (not _tok_atk and not _tok_scale) or \
                        tok.token_id in _NON_ATTACK_TOKENS:
                    tok.attack_timer = 0.5
                    continue
                target = hate.operator_attack_target(tok)
                if target is not None:
                    self._token_attack(tok, target)
                else:
                    tok.attack_timer = 0.1
        for op in self.operators:
            if op.dead:
                continue
            if op.in_deploy_anim(self.tick):
                # deploy animation: no attacks/talents, but active-skill
                # timers must keep running (duration starts at cast)
                _sca = getattr(op, "skill_controller", None)
                if _sca is not None:
                    _sca.tick(dt)
                continue
            if getattr(op, "_reborn_state", False):
                # \u70db\u714c downed: no attack, regen %maxHp per second
                # (skills stay interrupted; SP may recover for after revive)
                sc = getattr(op, "skill_controller", None)
                if sc is not None:
                    sc.tick(dt)
                self._tick_blaze2_reborn(op, dt)
                continue
            if getattr(op, "_doll_state", False):
                # dollkeeper substitute timer: when it expires the body
                # replaces the doll (full HP, 0 SP)
                op._doll_remaining -= 1
                if op._doll_remaining <= 0:
                    self._doll_restore(op)
            self._trait_tick(op, dt)
            _ts = getattr(op, "talent_system", None)
            if _ts is not None:
                try:
                    _ts.tick(dt, self)
                except Exception:
                    pass
            # skill controller (auto SP recovery + active effect timing)
            sc = getattr(op, "skill_controller", None)
            if sc is not None:
                sc.tick(dt)
            # per-tick subclass traits: phalanx idle defense / liberator
            # idle ramp + blockCnt gate (skill-state transitions reset here)
            _trait = getattr(op, "trait_system", None)
            if _trait is not None:
                try:
                    _trait.phalanx_sync()
                    _trait.librator_sync(
                        sc.active is not None if sc is not None else False,
                        dt)
                    _trait.bard_aura_sync(self)
                except Exception:
                    pass
            # controlled states (stun/freeze/levitate/palsy): the operator
            # cannot attack; both the windup and the attack timer pause
            # (they resume once the control ends)
            _op_ctrl = any(op.flag(f) for f in (0, 16, 25, 39))
            interval = op.attributes.attack_interval()
            if _op_ctrl:
                if op._pending_attack is not None:
                    pa = self._pending_attack_live(op._pending_attack)
                    if pa is None:
                        op._pending_attack = None
            else:
                op.attack_timer -= dt
                if op._pending_attack is not None:
                    pa = self._pending_attack_live(op._pending_attack)
                    if pa is None:
                        op._pending_attack = None
                    else:
                        pa["remaining"] -= 1
                        if pa["remaining"] <= 0:
                            self._resolve_operator_attack(op, pa)
                            op._pending_attack = None
                            if sc is not None:
                                act = getattr(sc, "active", None)
                                ae = getattr(act, "attack_effects", {}) or {}
                                hits = max(1, int(ae.get("times")
                                                  or ae.get("cnt") or 1))
                                sc.on_attack_landed(hits)
                                sc.on_ammo_attack()     # ammo skills
                                ts = getattr(op, "talent_system", None)
                                if ts is not None and \
                                        ts.attack_sp_bonus():
                                    sc.recover_sp(2, ts.attack_sp_bonus())
            if not _op_ctrl and op.attack_timer <= 0:
                target = hate.operator_attack_target(op)
                trait = getattr(op, "trait_system", None)
                if trait is not None and (trait.is_funnel()
                                          or trait.is_bard()):
                    # funnel operators never basic-attack (drones do);
                    # bards (吟游者) never attack at all
                    op.attack_timer = 0.1
                elif trait is not None and trait.is_hunter():
                    trait.hunter_tick(target, interval, self)
                elif trait is not None and trait.is_librator() and (
                        sc is None or sc.active is None):
                    # liberator: idle (blockCnt 0), no basic attack while
                    # no skill is active (PRTS trait)
                    op.attack_timer = 0.1
                elif trait is not None and trait.is_mystic():
                    # mystic (秘术师): store attacks while no
                    # target is in range; release the current attack plus
                    # all stored charges when a target appears
                    trait.mystic_attack_tick(target, interval, self)
                elif trait is not None and trait.attack_all_blocked():
                    # centurion / pusher: swing at every blocked enemy; idle
                    # when nothing is blocked (PRTS trait)
                    blk = [e for e in list(
                        getattr(op, "blocked_enemies", []) or [])
                        if not getattr(e, "dead", False)
                        and getattr(e, "blocked_by", None) is op]
                    if blk:
                        self._operator_attack(op, blk[0], interval,
                                              targets=blk)
                    else:
                        op.attack_timer = 0.1
                elif trait is not None and trait.is_fortress():
                    # fortress (\u8981\u585e): blocking -> melee swing at
                    # the blocked target; not blocking -> ranged splash on
                    # the target tile (PRTS trait).
                    blk = [e for e in list(
                        getattr(op, "blocked_enemies", []) or [])
                        if not getattr(e, "dead", False)
                        and getattr(e, "blocked_by", None) is op]
                    if blk:
                        self._operator_attack(op, blk[0], interval)
                    elif target is not None:
                        self._operator_attack(op, target, interval,
                                              fortress_splash=True)
                    else:
                        op.attack_timer = 0.1
                elif target is not None:
                    self._operator_attack(op, target, interval)
                else:
                    op.attack_timer = 0.1
        self._update_funnel_drones(dt)

    def _op_liftoff(self, op):
        """Skywalker (\u4fa6\u5bdf\u8005) liftoff state: the operator is
        airborne while one of its skills is active and the active skill
        carries the attack@height_offset blackboard (\u4e91\u8ff9/\u8482\u6bd4
        S1/S2, \u4e88\u613f\u5b89\u6770\u8389\u5a1c skills). While airborne it
        can block flying enemies (trait: \u8d77\u98de\u540e\u80fd\u591f\u963b\u6321
        2 \u4e2a\u98de\u884c\u654c\u4eba).  Operators whose block mode was
        switched to FLY by the taraxa_fly_mode buff template (Taraxa S1/S2,
        Orchid2 S2 liftoff) count as lifted off too."""
        if str(getattr(op, "_block_mode", "") or "").upper() == "FLY":
            return True
        trait = getattr(op, "trait_system", None)
        if trait is None or not trait._flags.get("liftoff"):
            return False
        sc = getattr(op, "skill_controller", None)
        act = getattr(sc, "active", None) if sc is not None else None
        if act is None:
            return False
        bb = getattr(getattr(act, "skill", None), "blackboard", None) or {}
        return bb.get("attack@height_offset") is not None

    def _update_blocking(self):
        """Scan operators + tokens -> block enemies within 1 tile."""
        blockers = [u for u in list(self.operators) + list(self.tokens)
                    if not u.dead]
        for op in blockers:
            if getattr(op, "_reborn_state", False):
                continue
            block_cnt = int(op.attributes.get("blockCnt") or 0)
            for e in self.enemies:
                if e.dead or e.blocked_by is not None or e.state not in (
                        EnemyState.MOVE, EnemyState.ATTACK, EnemyState.COMBAT):
                    continue
                if e.displacement is not None:   # sliding: not blockable
                    continue
                if e.flag(3):  # BLOCK_FREE (flying enemies)
                    # only a liftoff skywalker may block flying enemies
                    if not self._op_liftoff(op):
                        continue
                if e._next_map is not None and e.game_map is not None:
                    idx = e.game_map.idx(e.row, e.col)
                    nxt = e._next_map[idx] if idx >= 0 else -1
                    nrow, ncol = e.game_map.rc(nxt) if nxt >= 0 else                         (-1, -1)
                    # blocked only when the blocker's tile is the enemy's
                    # next movement step (same tile or next flow-field cell)
                    on_path = (e.row == op.row and e.col == op.col) or                         (nrow == op.row and ncol == op.col)
                    if not on_path:
                        continue
                elif not (e.row == op.row and e.col == op.col):
                    continue
                if abs(e.row - op.row) <= 1 and abs(e.col - op.col) <= 1:
                    volume = e.block_volume
                    used = sum(x.block_volume for x in op.blocked_enemies)
                    cap = block_cnt
                    if e.flag(3) and self._op_liftoff(op):
                        # liftoff skywalker: holds up to 2 flying enemies
                        cap = max(cap, 2)
                    if used + volume <= cap:
                        e.blocked_by = op
                        e.state = EnemyState.COMBAT
                        op.add_blockee(e)
                        self._dispatch_buff_events(
                            e, "ON_OWNER_BLOCKEE_CHANGED",
                            source=e, target=e)
        # queue overflow: enemies whose next step is held by a blocker at
        # full capacity wait in place (game behaviour - no passing through)
        for e in self.enemies:
            e.blocked_wait = False
            if e.dead or e.blocked_by is not None or e.state not in (
                    EnemyState.MOVE, EnemyState.ATTACK, EnemyState.COMBAT):
                continue
            if e.displacement is not None or e.flag(3):
                continue
            if e._next_map is None or e.game_map is None:
                continue
            idx = e.game_map.idx(e.row, e.col)
            nxt = e._next_map[idx] if idx >= 0 else -1
            if nxt < 0:
                continue
            nrow, ncol = e.game_map.rc(nxt)
            for op in blockers:
                if op.row != nrow or op.col != ncol:
                    continue
                if getattr(op, "_reborn_state", False):
                    continue
                block_cnt = int(op.attributes.get("blockCnt") or 0)
                used = sum(x.block_volume for x in op.blocked_enemies)
                if used + e.block_volume > block_cnt:
                    e.blocked_wait = True
                    break
        # clear released blockers: dead/retreated blockers, and flying
        # enemies whose skywalker blocker left liftoff (no longer holds them)
        alive = set(self.operators) | set(self.tokens)
        for e in self.enemies:
            b = e.blocked_by
            if b is not None and (b.dead or b not in alive):
                e.blocked_by = None
                if e.state == EnemyState.COMBAT:
                    e.state = EnemyState.MOVE
                self._dispatch_buff_events(
                    e, "ON_OWNER_BLOCKEE_CHANGED", source=e, target=e)
            elif b is not None and e.flag(3) and not self._op_liftoff(b):
                e.blocked_by = None
                if e.state == EnemyState.COMBAT:
                    e.state = EnemyState.MOVE
                b.remove_blockee(e)
                self._dispatch_buff_events(
                    e, "ON_OWNER_BLOCKEE_CHANGED", source=e, target=e)

    def _check_end(self):
        if self.life_point <= 0:
            self.finished = True
            self.result = "defeat"
        elif (self.waves.finished and not self.enemies
              and not getattr(self, "_branch_phases", [])):
            # victory = all scheduled waves/branches dealt and all enemies
            # cleared (operators may stay deployed); pending level-branch
            # phase actions keep the battle running
            self.finished = True
            self.result = "victory"
        elif self.max_play_time > 0 and self.tick / TIME_ROUGH_LOGIC_RATE >= \
                self.max_play_time:
            self.finished = True
            self.result = "timeout"

    def summon_snapshot(self):
        """Deployable summon tokens for each deployed summoner."""
        out = []
        for char_id, keys in self._summons.items():
            for k in keys:
                insts = [i for i in self._summon_insts.get(k["tokenKey"], [])
                         if any(t.inst_id == i and not t.dead
                                for t in self.tokens)]
                until = self._redeploy_until.get(k["tokenKey"], 0)
                out.append({
                    "charId": char_id,
                    "tokenKey": k["tokenKey"],
                    "source": k["source"],
                    "skillIndex": k["skillIndex"],
                    "deployed": insts,
                    "deployable": not insts and self.tick >= until,
                    "redeployIn": round(max(0, until - self.tick) / 30.0, 2),
                })
        return out

    # ================= snapshot =================
    def snapshot(self, since_seq=0):
        return {
            "tick": self.tick,
            "t": round(self.tick / TIME_ROUGH_LOGIC_RATE, 4),
            "lifePoint": self.life_point,
            "cost": round(self.cost, 3),
            "maxCost": self.max_cost,
            "costTimer": self.cost_timer_state(),
            "paused": self.paused,
            "finished": self.finished,
            "result": self.result,
            "deployed": [o.to_dict() for o in self.operators],
            "summons": self.summon_snapshot(),
            "enemies": [e.to_dict() for e in self.enemies],
            "tokens": [t.to_dict() for t in self.tokens],
            "projectiles": [p.to_dict() for p in self.projectiles],
            "waves": {
                "remaining": self.waves.remaining(),
                "spawned": self.waves.spawned,
                "finished": self.waves.finished,
                "nextSpawnAt": self.waves.next_spawn_at(),
                "randomGroups": getattr(self.waves, "random_groups", []),
                **self.waves.status(),
            },
            "hiddenGroups": {
                k: sorted(v) for k, v in (
                    getattr(self, "_rune_hidden_groups", None) or
                    {"enable": set(), "disable": set()}).items()
            },
            "branches": {
                "cursors": dict(getattr(self, "_branch_cursors", {})),
                "activePhases": len(getattr(self, "_branch_phases", [])),
            },
            "stats": {k: round(v, 3) if isinstance(v, float) else v
                      for k, v in self.stats.items()},
            "redeploys": [
                {"charId": cid, "redeployIn": round(
                    max(0, until - self.tick) / 30.0, 2)}
                for cid, until in self._redeploy_until.items()
            ],
            "gainedTokens": {
                k: {"count": v,
                    "timing": self._gained_token_timings.get(k)}
                for k, v in self._gained_tokens.items()},
            "stealValues": {
                f"{u},{a}": {"value": round(v, 3),
                             "max": round(self._steal_max.get((u, a), 0.0), 3)}
                for (u, a), v in self._steal_values.items()},
            "rallyCategory": self._rally_category,
            "rallyPoints": {k: list(v) for k, v in self._rally_points.items()},
            "fogView": {f"{r},{c}": in_view
                        for (r, c), in_view in self._fog_view.items()},
            "excludedDeckCards": sorted(self._excluded_deck_cards),
            "scores": {k: v for k, v in self._scores.items()},
            "droppedLoot": {k: v for k, v in self._dropped_loot.items()},
            "tileSideCache": {f"{r},{c}": side
                              for (r, c), side in self._tile_side_cache.items()},
            "extraLog": dict(self._extra_log),
            "fever": dict(self._fever),
            "feverActive": self._fever_active,
            "football": {"pos": self._football_pos,
                         "stopped": self._football_stopped},
            "legion": {"gold": self._legion_gold,
                       "hand": list(self._legion_hand),
                       "pending": list(self._legion_pending),
                       "traps": sorted(self._legion_traps),
                       "professionLevels": dict(
                           self._legion_profession_levels),
                       "dangerLevel": self._legion_danger_level},
            "wdslmStands": {
                k: [getattr(e, "inst_id", None) for e in v]
                for k, v in self._wdslm_stands.items()},
            "durbusPassengers": {
                k: len(v) for k, v in self._durbus_passengers.items()},
            "sandbox": {
                "weather": self._sandbox_weather,
                "nodeType": self._sandbox_node_type,
                "season": self._sandbox_season,
                "buildMode": self._sandbox_build_mode,
                "stats": dict(self._sandbox_stats),
                "res": self._sandbox_res,
                "items": dict(self._sandbox_items),
            },
            "act49TileTypes": {
                f"{r},{c}": t for (r, c), t in
                sorted(self._act49_tile_types.items())},
            "act49PrintProgress": round(self._act49_print_progress, 3),
            "ro4dlc2SealTiles": sorted(self._ro4dlc2_seal_tiles),
            "progressBuffs": list(self._progress_buffs),
            "electricWork": dict(self._electric_work),
            "coopScores": dict(self._coop_scores),
            "gatherListeners": [
                {"unit": getattr(u, "inst_id", None), "type": t}
                for u, t in self._gather_listeners],
            "roguelike": {
                "zoneType": self._rogue_zone_type,
                "duelStage": self._rogue_duel_stage,
                "deifyStage": self._rogue_deify_stage,
                "shield": self._rogue_shield,
                "diceLog": list(self._rogue_dice_log),
                "expUse": dict(self._rogue_exp_use),
            },
            "rogueExp": self._rogue_exp,
            "dynamicTileExcludes": sorted(self._dynamic_tile_excludes),
            "predefines": {
                "tokens": len(self.predefines.get("tokenInsts") or []),
                "characters": len(self.predefines.get("characterInsts") or []),
                "pending": len(self._predefined_pending),
            },
            "map": self.map.to_dict(),
            "tileModes": {f"{r},{c}": m
                          for (r, c), m in self._tile_modes.items()},
            "skillTiles": [{
                "row": r, "col": c, "kind": v.get("kind") or "conveyor_pull",
                "skillId": v.get("skillId"),
                "instId": (v.get("op").inst_id
                           if v.get("op") is not None else None),
                "remaining": round(
                    max(0, v["expiry_tick"] - self.tick) / 30.0, 3),
                "blackboard": v.get("bb"),
            } for (r, c), v in self._skill_tiles.items()],
            "routes": self.routes,
            "globalBuffs": self.global_buffs,
            "globalBlackboard": dict(self._global_bb),
            "sharedBlackboard": dict(self._char_shared_bb),
            "tileBlackboard": {
                f"{r},{c}": dict(bb)
                for (r, c), bb in self._tile_bb.items()},
            "envSystems": getattr(self, "env_systems", []),
            "prts": self.prts.to_dict(),
            "act35": self.act35.to_dict(),
            "act31": self.act31.to_dict(),
            "events": self.events.snapshot_events(since_seq=since_seq),
        }


_RANGE_TABLE = None

# Scout / utility tokens that never attack despite a placeholder ATK
# (Ray sandbeast has raw atk=100 in the table but is a scouting unit).
_NON_ATTACK_TOKENS = frozenset({"token_10034_ray_sndbst"})


def _load_range_table():
    global _RANGE_TABLE
    if _RANGE_TABLE is None:
        import json as _json
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data_range_table.json")
        with io.open(_p, encoding="utf-8") as f:
            _RANGE_TABLE = _json.load(f)
    return _RANGE_TABLE


def range_offsets_rotated(range_id, direction=1):
    """Exact range grid from range_table, rotated to the unit's facing.
    ``x-N`` ids (bards, phalanx casters, tokens, towers) are real
    entries in the range table; the Chebyshev-radius square is only
    a fallback for ids absent from the table."""
    if not range_id:
        return [(0, 0)]
    try:
        entry = _load_range_table().get(range_id)
        grids = entry.get("grids") or [] if entry else []
    except Exception:
        grids = []
    if not grids:
        try:
            r, c = range_id.split("-")
            if r.lower() == "x":
                n = int(c)
                return [(dr, dc) for dr in range(-n, n + 1)
                        for dc in range(-n, n + 1)
                        if abs(dr) <= n and abs(dc) <= n]
        except (ValueError, AttributeError):
            pass
        return _range_offsets(range_id)
    dirn = int(direction) % 4
    out = []
    for g in grids:
        gr = g.get("row", 0)
        gc = g.get("col", 0)
        if dirn == 0:          # up
            dr, dc = -gc, gr
        elif dirn == 2:        # down
            dr, dc = gc, -gr
        elif dirn == 3:        # left
            dr, dc = -gr, -gc
        else:                  # right
            dr, dc = gr, gc
        out.append((dr, dc))
    return out


def _range_offsets(range_id):
    """Approximate range shapes by rangeId (fallback for unknown ids)."""
    if not range_id:
        return [(0, 0)]
    try:
        r, c = range_id.split("-")
        r, c = int(r), int(c)
    except (ValueError, AttributeError):
        return [(0, 0)]
    offs = []
    for dr in range(-r + 1, r):
        for dc in range(-c + 1, c):
            if abs(dr) + abs(dc) <= max(r, c):
                offs.append((dr, dc))
    return offs
