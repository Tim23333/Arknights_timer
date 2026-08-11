"""Buff and abnormal-state system.

Attribute modifiers follow the game's four-layer model (MECHANICS §2.2):
    add       -> direct additive      (直接加算)
    mul       -> direct multiplicative (直接乘算, percentages sum)
    final_add -> final additive        (最终加算)
    final_mul -> final multiplicative  (最终乘算, multiply)

The Attributes class stores a single (additive, multiplicative) pair per
modifier; we map the four layers onto two slots by folding final layers
into the multiplicative pair via dedicated keys (see Attributes.get()).
"""

from .attributes import Attributes
from .consts import AbnormalFlag, DamageType, EnemyState


# CC statuses the \u70db\u714c downed form is immune to (and counters):
# stun / stun-no-amplify / frozen / immobile / sleep (PRTS \u7edd\u5904\u91cd\u71c3).
_REBORN_CC_FLAGS = frozenset({
    AbnormalFlag.STUNNED, AbnormalFlag.STUNNED_NO_AMPLIFY_DAMAGE,
    AbnormalFlag.FROZEN, AbnormalFlag.UNMOVABLE, AbnormalFlag.DOZE,
})


class BuffSystem:
    """Applies/ticks buffs and abnormal flags on Units."""

    def __init__(self, battle=None):
        self.battle = battle
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from .buff_templates import BuffTemplateEngine
            self._engine = BuffTemplateEngine(self.battle)
        return self._engine

    # ---- template events ----
    def _fire(self, unit, buff_entry, event, source=None, target=None,
              damage=None, extra_bb=None):
        """Run a buff's template actions for an event (depth guarded)."""
        tpl_key = buff_entry.get("template_key") or buff_entry.get(
            "templateKey")
        if not tpl_key or not self.battle:
            return
        battle = self.battle
        depth = getattr(battle, "_buff_dispatch_depth", 0)
        if depth > 12:
            return
        battle._buff_dispatch_depth = depth + 1
        try:
            bb = dict(buff_entry.get("blackboard") or {})
            if extra_bb:
                bb.update(extra_bb)
            bb.setdefault("buff_key", buff_entry.get("key"))
            bb.setdefault("template_key", tpl_key)
            bb.setdefault("_buff_entry", buff_entry)
            bb.setdefault("_remaining_ticks",
                          buff_entry.get("remaining_ticks", 1))
            bb.setdefault("_total_ticks", buff_entry.get("_total_ticks")
                          or buff_entry.get("remaining_ticks", 1))
            self.engine.dispatch(unit, event, tpl_key, source=source,
                                 target=target, damage=damage, bb=bb)
            # persist chain-blackboard writes back onto the buff entry
            # (AssignValueToBB / BlackboardAdd / counters etc.), matching
            # the game's mutable BuffData blackboard. Runtime-injected
            # underscore keys (_buff_entry, _remaining_ticks, trigger
            # cursors) and the recursive self-reference are excluded so
            # decay calculations keep reading fresh values and snapshots
            # stay acyclic.
            _persist = {k: v for k, v in bb.items()
                        if not str(k).startswith("_")}
            buff_entry["blackboard"] = _persist
        finally:
            battle._buff_dispatch_depth = depth

    def on_owner_before_dead(self, unit):
        """Fire ON_OWNER_BEFORE_DEAD buff templates just before a unit
        dies (enemy_mjcdog kill hooks etc.)."""
        if unit is None:
            return
        for b in list(getattr(unit, "buffs", None) or []):
            if b.get("template_key"):
                try:
                    self._fire(unit, b, "ON_OWNER_BEFORE_DEAD",
                               source=b.get("source"))
                except Exception:
                    pass

    def on_owner_finish(self, unit):
        """Fire ON_OWNER_FINISH buff templates when a unit finishes
        (dies / reaches the exit / retreats / is removed)."""
        if unit is None:
            return
        for b in list(getattr(unit, "buffs", None) or []):
            if b.get("template_key"):
                try:
                    self._fire(unit, b, "ON_OWNER_FINISH",
                               source=b.get("source"))
                except Exception:
                    pass

    def on_owner_killed(self, unit):
        """Fire ON_OWNER_KILLED buff templates when a unit dies
        (death-triggered effects: Mephisto drone heal, death spawns,
        die-to-add-cost ...). ON_OWNER_FINISH also fires on death."""
        if unit is None:
            return
        for b in list(getattr(unit, "buffs", None) or []):
            if b.get("template_key"):
                try:
                    self._fire(unit, b, "ON_OWNER_KILLED",
                               source=b.get("source"))
                    self._fire(unit, b, "ON_OWNER_FINISH",
                               source=b.get("source"))
                except Exception:
                    pass

    def _trigger_spec(self, buff_entry):
        """triggerInterval/triggerCnt from the template (seconds)."""
        tpl_key = buff_entry.get("template_key") or buff_entry.get(
            "templateKey")
        if not tpl_key:
            return None, 0
        try:
            from .buff_templates import template
            t = template(tpl_key)
            ev = (t or {}).get("eventToActions") or {}
            if not ev.get("ON_BUFF_TRIGGER"):
                return None, 0
            # template root has no trigger fields; buff data drives it.
            # fall back to 1s interval so ON_BUFF_TRIGGER still runs.
            return 1.0, 0
        except Exception:
            return None, 0

    # ---- buffs ----
    def apply(self, unit, buff):
        """buff: dict {key, remaining_ticks, layers, add, mul, final_add,
        final_mul, source}. Same key refreshes (default strategy: refresh
        duration, keep max layers)."""
        if unit is None or getattr(unit, "dead", False):
            return None
        key = buff.get("key")
        if not key:
            return None
        existing = self.get(unit, key)
        # merge only entries with the same stat: one buffKey can carry
        # several attributeModifiers (e.g. Goldenglow S1 atk + attackSpeed)
        # and they must remain separate BuffSystem entries to both apply.
        if existing is not None and (
                existing.get("stat") == buff.get("stat")):
            # refresh strategy: renew duration, stack layers up to given
            existing["remaining_ticks"] = max(existing.get("remaining_ticks", 0),
                                              buff.get("remaining_ticks", 0))
            existing["layers"] = max(existing.get("layers", 1),
                                     buff.get("layers", 1))
            self._rebuild_modifiers(unit)
            return existing
        entry = {
            "key": key,
            "remaining_ticks": int(buff.get("remaining_ticks", 1)),
            "_total_ticks": int(buff.get("remaining_ticks", 1)),
            "layers": max(1, buff.get("layers", 1)),
            "add": float(buff.get("add", 0.0)),
            "mul": float(buff.get("mul", 0.0)),
            "final_add": float(buff.get("final_add", 0.0)),
            "final_mul": float(buff.get("final_mul", 0.0)),
            "source": buff.get("source"),
            "derived_from": buff.get("derived_from"),
            "tick_applied": self.battle.tick if self.battle else 0,
            "stat": buff.get("stat"),
            "template_key": buff.get("template_key") or
                            buff.get("templateKey"),
            "blackboard": buff.get("blackboard") or {},
            "abnormalImmunes": buff.get("abnormalImmunes"),
        }
        if entry.get("template_key"):
            # buffs materialised from real BuffData carry their own
            # triggerInterval (e.g. DoT ticks every 0.1~5s); never
            # overwrite it with the 1s template fallback.
            if buff.get("_trigger_interval") is not None:
                entry["_trigger_interval"] = int(buff.get(
                    "_trigger_interval"))
                entry["_trigger_acc"] = 0
            else:
                ival, _ = self._trigger_spec(entry)
                if ival:
                    entry["_trigger_interval"] = int(ival * 30)
                    entry["_trigger_acc"] = 0
            if buff.get("_first_trigger_interval") is not None and \
                    int(buff.get("wait_first_trigger",
                                 buff.get("waitFirstTriggerInterval", 1))
                        or 0) != 0:
                entry["_first_trigger_remaining"] = int(
                    buff.get("_first_trigger_interval"))
            if buff.get("_trigger_max") is not None:
                entry["_trigger_max"] = int(buff.get("_trigger_max"))
                entry["_trigger_count"] = 0
        unit.buffs.append(entry)
        self._rebuild_modifiers(unit)
        if self.battle:
            self.battle.emit(self.battle.tick, "buff_applied",
                             {"unit": unit.inst_id, "buff": key})
            if entry.get("template_key"):
                self._fire(unit, entry, "ON_BUFF_START", source=entry.get(
                    "source"))
                # ON_OTHER_BUFF_START: every other buff on the unit is
                # notified of the newly started buff (CheckMainBuffId
                # filters by _other_buff_key; recat/necras upgrade chains)
                for _ob in list(unit.buffs):
                    if _ob is entry or not _ob.get("template_key"):
                        continue
                    self._fire(unit, _ob, "ON_OTHER_BUFF_START",
                               source=entry.get("source"),
                               extra_bb={"_other_buff_key": key})
                # immediate first trigger for waitFirstTriggerInterval=0
                # (e.g. Gravel S1 def_atten starts at full +200% at cast)
                if int(buff.get("wait_first_trigger",
                               buff.get("waitFirstTriggerInterval", 1))
                       or 0) == 0:
                    ival, _ = self._trigger_spec(entry)
                    if ival:
                        self._fire(unit, entry, "ON_BUFF_TRIGGER",
                                   source=entry.get("source"))
        return entry

    def get(self, unit, key):
        for b in unit.buffs:
            if b["key"] == key:
                return b
        return None

    def remove(self, unit, key):
        """Remove a buff and any derived buffs (AttachAsDerivedBuff
        children whose ``derived_from`` points at the removed key).
        Removal is one-way parent -> children: removing a derived buff
        never touches its parent."""
        before = len(unit.buffs)
        drop = {key}
        changed = True
        while changed:
            changed = False
            for b in list(unit.buffs):
                if b["key"] in drop:
                    unit.buffs.remove(b)
                    changed = True
                elif b.get("derived_from") in drop:
                    drop.add(b["key"])
                    unit.buffs.remove(b)
                    changed = True
        if len(unit.buffs) != before:
            self._rebuild_modifiers(unit)
        return before != len(unit.buffs)

    def update(self, dt, tick=None):
        """Decrement all buffs on all units; fire trigger/finish events."""
        for unit in self._all_units():
            expired = []
            _ep_speed = self.ep_cooldown_speed(unit)
            for b in unit.buffs:
                if _ep_speed != 1.0 and str(b.get("key", "")).startswith(
                        "ep_burst_cd_"):
                    b["remaining_ticks"] -= _ep_speed
                else:
                    b["remaining_ticks"] -= 1
                ival = b.get("_trigger_interval")
                if ival:
                    if b.get("_first_trigger_remaining", 0) > 0:
                        b["_first_trigger_remaining"] -= 1
                        if b["_first_trigger_remaining"] > 0:
                            continue
                    tmax = b.get("_trigger_max")
                    if tmax is not None and \
                            b.get("_trigger_count", 0) >= tmax:
                        continue
                    b["_trigger_acc"] = b.get("_trigger_acc", 0) + 1
                    if b["_trigger_acc"] >= ival:
                        b["_trigger_acc"] = 0
                        self._fire(unit, b, "ON_BUFF_TRIGGER", source=b.get(
                            "source"))
                        if tmax is not None:
                            b["_trigger_count"] = b.get(
                                "_trigger_count", 0) + 1
                if b["remaining_ticks"] <= 0:
                    expired.append(b)
            for b in expired:
                if b.get("template_key"):
                    self._fire(unit, b, "ON_BUFF_FINISH", source=b.get(
                        "source"))
                self.remove(unit, b["key"])
                if self.battle:
                    self.battle.emit(tick if tick is not None else 0,
                                     "buff_expired",
                                     {"unit": unit.inst_id,
                                      "buff": b["key"]})
                if str(b.get("key", "")).startswith("ep_burst_cd_"):
                    # burst cooldown ended: all element bars restore to
                    # maximum (PRTS element page: 元素爆发结束时，爆发冷却
                    # 一并结束，随后单位所有种类的元素值恢复至最大值).
                    self._ep_burst_end(unit)
            # element-burst periodic effects (PRTS):
            #  - DARK on enemies: 50% weaken decays linearly to 0 over the
            #    15s burst (虚弱 = 50% x 剩余时间/总持续时间);
            #  - DARK on operators: 1 SP/s drain + 100 magic damage per
            #    second for 15s (阻回/静默 applied at burst time).
            if self.battle is not None:
                for b in unit.buffs:
                    if b.get("key") == "ep_dark_weaken":
                        _total = b.get("_total_ticks") or 1
                        _rem = max(0.0, float(b.get("remaining_ticks", 0)))
                        b["mul"] = -0.5 * _rem / _total
                    elif b.get("key") == "ep_dark_dot":
                        _elapsed = (int(self.battle.tick or 0) -
                                    int(b.get("tick_applied", 0)))
                        if _elapsed > 0 and _elapsed % 30 == 0:
                            try:
                                self.battle.apply_damage(
                                    unit, 100.0, DamageType.MAGICAL,
                                    source=None)
                            except Exception:
                                pass
                            _sp = getattr(unit, "sp", None)
                            if _sp is not None:
                                unit.sp = max(0.0, float(_sp) - 1.0)
            self._tick_abnormal(unit, dt)

    def _all_units(self):
        if not self.battle:
            return []
        return (list(self.battle.get_enemies()) +
                list(self.battle.get_operators()) +
                list(self.battle.get_tokens()))

    def _rebuild_modifiers(self, unit):
        """Fold buff list into Attributes modifiers.

        Attributes only stores one (add, mul) pair per key; we translate the
        four-layer model by issuing two internal modifier keys per buff:
          layer A: additive  -> key:(key)#a
          layer B: percent   -> key:(key)#p
        final layers are folded into the same pair with distinct keys.
        """
        attrs = unit.attributes
        for stat in list(Attributes.FIELDS):
            attrs.remove_modifier(f"buff:{stat}:a")
            attrs.remove_modifier(f"buff:{stat}:p")
            attrs.remove_modifier(f"buff:{stat}:fa")
            attrs.remove_modifier(f"buff:{stat}:fm")
        self._apply_buff_entries(unit, attrs)
        # maxHp sync: buff/talent maxHp changes also scale current HP by the
        # same ratio (game maxHp modifier rule), keeping max_hp/hp in sync.
        try:
            eff = float(attrs.get("maxHp") or 0.0)
            if eff > 0 and abs(eff - float(unit.max_hp)) > 1e-6:
                ratio = (float(unit.hp) / float(unit.max_hp)
                         if float(unit.max_hp) > 0 else 1.0)
                unit.max_hp = eff
                unit.hp = 0.0 if unit.dead else min(eff, eff * ratio)
        except Exception:
            pass

    def _apply_buff_entries(self, unit, attrs):
        from collections import defaultdict
        agg = defaultdict(lambda: {"add": 0.0, "mul": 0.0,
                                   "final_add": 0.0, "final_mul": 1.0,
                                   "cnt": 0})
        for b in unit.buffs:
            stat = b.get("stat")
            if not stat or stat not in Attributes.FIELDS:
                continue
            layers = b.get("layers", 1)
            g = agg[stat]
            g["cnt"] += 1
            g["add"] += b.get("add", 0.0) * layers
            g["mul"] += b.get("mul", 0.0) * layers
            g["final_add"] += b.get("final_add", 0.0) * layers
            fm = b.get("final_mul", 1.0)
            g["final_mul"] *= (fm ** layers) if fm else 1.0
        for stat, g in agg.items():
            if g["add"]:
                attrs.add_modifier(stat, additive=g["add"], key=f"buff:{stat}:a")
            if g["mul"]:
                attrs.add_modifier(stat, multiplicative=g["mul"],
                                   key=f"buff:{stat}:p")
            if g["final_add"]:
                attrs.add_modifier(stat, final_add=g["final_add"],
                                   key=f"buff:{stat}:fa")
            if g["final_mul"] != 1.0:
                attrs.add_modifier(stat, final_mul=g["final_mul"],
                                   key=f"buff:{stat}:fm")

    # ---- abnormal ----
    def _buff_abnormal_immune(self, unit, flag):
        """True when a buff on the unit carries abnormalImmunes naming the
        flag (game buffs e.g. invincible/status-resist entries)."""
        _NAME_MAP = {
            "STUNNED": 0, "SILENCED": 12, "FROZEN": 16, "LEVITATE": 25,
            "PALSY": 39, "FEARED": 33, "ATTRACTED": 41, "TELEPORTED": 44,
            "GROUND_BOUND": 45, "COLD": 23, "INVINCIBLE": 5,
            "UNDEADABLE": 6, "HEAL_FREE": 7,
        }
        for b in list(getattr(unit, "buffs", None) or []):
            ims = b.get("abnormalImmunes")
            if not ims:
                continue
            for im in ims:
                if im is None:
                    continue
                try:
                    if isinstance(im, bool):
                        continue
                    if isinstance(im, int) and im == flag:
                        return True
                    if str(im).isdigit() and int(im) == flag:
                        return True
                    if _NAME_MAP.get(str(im)) == flag:
                        return True
                except Exception:
                    continue
        return False

    def set_abnormal(self, unit, flag, seconds, layers=1, source=None):
        """Apply abnormal flag with immunity check (attributes base +
        buff-provided abnormalImmunes)."""
        if self._buff_abnormal_immune(unit, flag):
            return False
        # EnemySkill._immuneStunWhenAffecting: while a stun-immune enemy
        # skill is being cast, incoming stuns are ignored
        if flag == AbnormalFlag.STUNNED and getattr(
                unit, "_immune_stun_affecting", False):
            return False
        immune_map = {
            AbnormalFlag.STUNNED: "stunImmune",
            AbnormalFlag.SILENCED: "silenceImmune",
            AbnormalFlag.FROZEN: "frozenImmune",
            AbnormalFlag.LEVITATE: "levitateImmune",
            AbnormalFlag.PALSY: "palsyImmune",
            AbnormalFlag.FEARED: "fearedImmune",
            AbnormalFlag.ATTRACTED: "attractImmune",
            AbnormalFlag.TELEPORTED: "teleportImmune",
            AbnormalFlag.GROUND_BOUND: "groundBoundImmune",
        }
        field = immune_map.get(flag)
        if field and unit.attributes.get_bool(field):
            return False
        # \u70db\u714c T2 \u7edd\u5904\u91cd\u71c3: while downed she is
        # immune to stun/freeze/immobile/sleep and reflects the status back
        # to the enemy source (PRTS: \u6655\u7729\u53cd\u5236 etc).
        if getattr(unit, "_reborn_state", False) and \
                flag in _REBORN_CC_FLAGS:
            src = source
            if src is not None and getattr(src, "side", 0) == 0 \
                    and not getattr(src, "dead", False) \
                    and not getattr(src, "_reborn_state", False):
                try:
                    self.set_abnormal(src, flag, seconds, layers=layers,
                                      source=unit)
                except Exception:
                    pass
            return False
        ticks = max(1, int(round(seconds * 30)))
        unit.set_flag(flag, ticks, layers, source=source)
        if self.battle:
            self.battle.emit(self.battle.tick, "abnormal_applied",
                             {"unit": unit.inst_id, "flag": flag,
                              "ticks": ticks})
        self._flag_dirty(unit)
        return True

    def _flag_dirty(self, unit):
        if self.battle is not None:
            try:
                self.battle._dispatch_buff_events(
                    unit, "ON_ABNORMAL_FLAG_DIRTY", source=unit, target=unit)
            except Exception:
                pass

    def clear_abnormal(self, unit, flag):
        unit.clear_flag(flag)
        if self.battle:
            self.battle.emit(self.battle.tick, "abnormal_ended",
                             {"unit": unit.inst_id, "flag": flag})
        self._flag_dirty(unit)

    def _tick_abnormal(self, unit, dt):
        expired = []
        for flag, rec in unit.abnormal.items():
            rec["ticks"] -= 1
            if rec["ticks"] <= 0:
                expired.append(flag)
        for flag in expired:
            unit.clear_flag(flag)
            if self.battle:
                self.battle.emit(self.battle.tick, "abnormal_ended",
                                 {"unit": unit.inst_id, "flag": flag})
        # map abnormal -> enemy state override; remember the pre-abnormal
        # state and restore it when all such flags expire (a COMBAT enemy
        # must return to COMBAT, not fall back to MOVE and stop attacking)
        from .consts import ABNORMAL_STATE
        if getattr(unit, "set_state", None):
            override = None
            for flag, state in ABNORMAL_STATE.items():
                if unit.flag(flag):
                    override = state
                    break
            if override is not None:
                if unit._pre_abnormal_state is None:
                    unit._pre_abnormal_state = unit.state
                if unit.state != override:
                    unit.set_state(override)
            else:
                prev = getattr(unit, "_pre_abnormal_state", None)
                if prev is not None:
                    unit.set_state(prev)
                    unit._pre_abnormal_state = None

    # ---- element damage (EP) ----
    EP_KEYS = {0: "ep_neural", 1: "ep_water", 2: "ep_fire", 3: "ep_dark"}
    # PRTS element page 元素损伤爆发 column: burst/cooldown duration by
    # element type (seconds). Erosion drops to 8s on enemy-class units.
    _BURST_DURATION_SECS = {0: 10.0, 1: 10.0, 2: 10.0, 3: 15.0}

    def _ep_lock_active(self, unit):
        """PRTS: during a burst cooldown ALL element values are locked
        (cannot be lost nor recovered by any means)."""
        return any(str(b.get("key", "")).startswith("ep_burst_cd_")
                   for b in getattr(unit, "buffs", None) or [])

    def _burst_cooldown_ticks(self, unit, ep_type):
        secs = self._BURST_DURATION_SECS.get(ep_type, 10.0)
        if ep_type == 1 and getattr(unit, "side", 0) == 0:
            secs = 8.0    # enemy erosion burst duration reduced to 8s
        return int(round(secs * 30))

    def ep_max(self, unit):
        """Element-burst threshold: the unit's ``maxEp`` attribute when set
        (dump.cs AttributesData.maxEp / UnitData.get_maxEp), else the game
        default 1000.  PRTS element page (prts.wiki/w/元素) / CH-7:
        ordinary and elite enemies burst at 1000, while LEADER-class
        (BOSS) enemies get +1000 -> 2000; operators stay at 1000.  A
        unit-level maxEp attribute overrides both defaults."""
        try:
            v = unit.attributes.get("maxEp")
            if v and float(v) > 0:
                return float(v)
        except Exception:
            pass
        if getattr(unit, "side", 0) == 0 and int(
                getattr(unit, "level_type", 0) or 0) == 2:
            return 2000.0
        return 1000.0

    def update_ep(self, unit, ep_type, amount, source=None):
        """Add element damage; returns True when burst triggers.
        ``source`` enables ON_AFTER_OUTPUT_ELEMENT_DAMAGE template dispatch
        (e.g. ?? S3 sanity marks on enemies he deals element damage to)."""
        if unit.dead:
            return False
        # during burst cooldown ALL element values are locked (PRTS)
        if self._ep_lock_active(unit):
            return False
        # damage = amount * (1 - epDamageResistance * 0.01)
        res = unit.attributes.get("epDamageResistance")
        amount = amount * max(0.0, 1.0 - (res or 0.0) * 0.01)
        # per-operator element damage taken talent (e.g. Thumpy talent 1)
        _ts = getattr(unit, "talent_system", None)
        if _ts is not None:
            try:
                amount = amount * _ts.ep_damage_scale()
            except Exception:
                pass
        # source-side module traits (e.g. \u9152\u795e Y\u6a21\u7ec4:
        # element damage vs elite/leader enemies +18%)
        if source is not None:
            _ts_src = getattr(source, "talent_system", None)
            if _ts_src is not None:
                try:
                    _mscale = _ts_src.module_elite_ep_scale()
                    if _mscale != 1.0 and int(getattr(
                            unit, "level_type", 0) or 0) in (1, 2):
                        amount = amount * _mscale
                except Exception:
                    pass
        max_ep = self.ep_max(unit)
        if amount < 0:
            # recovery path: the full bar (value = remaining, maxEp full)
            # rises back toward maxEp; never fire damage observers
            key = self.EP_KEYS.get(ep_type, f"ep_{ep_type}")
            rec = unit.buffs and self.get(unit, key)
            cur = rec["value"] if rec else max_ep
            new = min(max_ep, cur - amount)
            if rec:
                rec["value"] = new
            else:
                unit.buffs.append({"key": key, "remaining_ticks": 1 << 30,
                                   "layers": 1, "value": new,
                                   "source": None, "tick_applied": 0})
            return False
        unit._last_ep_type = ep_type
        key = self.EP_KEYS.get(ep_type, f"ep_{ep_type}")
        rec = unit.buffs and self.get(unit, key)
        # full-bar model: value = remaining element bar (maxEp full);
        # element damage DEDUCTS it, burst when it reaches 0
        cur = rec["value"] if rec else max_ep
        new = cur - amount
        # template observers on the source (ON_AFTER_OUTPUT_ELEMENT_DAMAGE)
        # run before the EP is stored so gates like FilterModifierByRealDelta
        # can inspect the actual delta
        if self.battle:
            self._dispatch_after_output_element(unit, ep_type, amount, source)
        if new > 0:
            if rec:
                rec["value"] = new
            else:
                unit.buffs.append({"key": key, "remaining_ticks": 1 << 30,
                                   "layers": 1, "value": new,
                                   "source": None, "tick_applied": 0})
            return False
        # burst: bar resets to full (no accumulated damage - mirrors the
        # old accumulate model's clear-to-0), enter cooldown (locked)
        if rec:
            rec["value"] = max_ep
        else:
            unit.buffs.append({"key": key, "remaining_ticks": 1 << 30,
                               "layers": 1, "value": max_ep,
                               "source": None, "tick_applied": 0})
        burst_key = f"ep_burst_cd_{ep_type}"
        self.apply(unit, {"key": burst_key,
                          "remaining_ticks":
                              self._burst_cooldown_ticks(unit, ep_type),
                          "layers": 1, "source": None})
        if self.battle:
            self._fire_ep_break_templates(unit, ep_type)
            self._burst_effect(unit, ep_type)
            self._dispatch_ep_break_event(unit, ep_type, "ON_EP_BREAK_START")
            self.battle.emit(self.battle.tick, "ep_burst",
                             {"unit": unit.inst_id, "type": ep_type})
        return True

    def recover_ep(self, unit, amount, source=None):
        """Element heal: every EP bar (full-bar model) rises by ``amount``
        toward maxEp. During a burst cooldown all bars are locked (PRTS).
        Returns the total recovered."""
        if unit is None or getattr(unit, "dead", False) or amount <= 0:
            return 0.0
        if self._ep_lock_active(unit):
            return 0.0
        total = 0.0
        for ep_type in sorted(self.EP_KEYS):
            key = self.EP_KEYS[ep_type]
            rec = self.get(unit, key)
            max_ep = self.ep_max(unit)
            cur = rec["value"] if rec else max_ep
            if cur >= max_ep:
                continue
            healed = min(max_ep - cur, float(amount))
            rec["value"] = cur + healed
            total += healed
        if total > 0 and self.battle is not None:
            self.battle.emit(self.battle.tick, "ep_recovered", {
                "unit": unit.inst_id,
                "amount": round(total, 3),
                "source": source.inst_id if source is not None else None})
        return total

    def _ep_burst_end(self, unit):
        """Burst cooldown ended: every element bar restores to maximum
        (full-bar model: remaining value = maxEp)."""
        for key in self.EP_KEYS.values():
            rec = self.get(unit, key)
            if rec is not None:
                rec["value"] = self.ep_max(unit)
        if self.battle:
            self.battle.emit(self.battle.tick, "ep_burst_end",
                             {"unit": unit.inst_id})

    def _fire_ep_break_templates(self, unit, ep_type):
        """Generic ON_BEFORE_EP_BREAK_START dispatch before the built-in
        burst effect (see _dispatch_ep_break_event)."""
        self._dispatch_ep_break_event(unit, ep_type, "ON_BEFORE_EP_BREAK_START")

    def _dispatch_ep_break_event(self, unit, ep_type, event):
        """Generic element-burst template dispatch for event
        (ON_BEFORE_EP_BREAK_START / ON_EP_BREAK_START). The event runs for:
          - every buff ON the bursting unit (owner = the bursting unit,
            e.g. phatm2_s_3[token] cage detection / thumpy water detect);
          - every buff on OPERATORS (global field listeners, e.g.
            blaze2_t_1 melts-and-ignites: any enemy fire burst heals the
            source and deals element damage to the bursting enemy).
        The action context: owner = the buff holder, target = the bursting
        unit, bb._ep_break_type = the bursting element type."""
        if not self.battle or not unit:
            return
        try:
            from .buff_templates import template as _tpl
        except Exception:
            return

        def _has_event(buff_entry):
            tpl_key = buff_entry.get("template_key") or \
                buff_entry.get("templateKey")
            if not tpl_key:
                return False
            try:
                t = _tpl(tpl_key)
            except Exception:
                return False
            return bool(t) and event in ((t.get("eventToActions") or {}))

        holders = [unit]
        try:
            holders += [o for o in list(self.battle.operators)
                        if o is not unit and not getattr(o, "dead", False)]
        except Exception:
            pass
        seen = set()
        for holder in holders:
            for entry in list(getattr(holder, "buffs", None) or []):
                if id(entry) in seen:
                    continue
                seen.add(id(entry))
                if not _has_event(entry):
                    continue
                extra = {"_ep_break_type": ep_type}
                if event == "ON_EP_BREAK_START":
                    extra["_ep_break_phase"] = True
                self._fire(holder, entry, event,
                           source=entry.get("source"), target=unit,
                           extra_bb=extra)

    def add_ep_force(self, unit, ep_type, amount):
        """Accumulate element EP ignoring the burst cooldown lock and
        without triggering a new burst. Used by ON_EP_BREAK_START burst-
        damage templates (e.g. ?? ???? deals atk*scale element damage
        to the bursting enemy, accumulating toward the NEXT burst).
        Full-bar model: the remaining bar is DEDUCTED toward the next
        burst; values may go negative (over-accumulated damage beyond the
        bar, e.g. Blaze2 T1 2150 EP while the bar is 1000 - mirrors the
        old accumulate model's >max accumulation)."""
        key = self.EP_KEYS.get(ep_type, f"ep_{ep_type}")
        rec = self.get(unit, key)
        max_ep = self.ep_max(unit)
        cur = rec["value"] if rec else max_ep
        new = cur - amount
        if rec:
            rec["value"] = new
        else:
            unit.buffs.append({"key": key, "remaining_ticks": 1 << 30,
                               "layers": 1, "value": new,
                               "source": None, "tick_applied": 0})
        return new

    def _dispatch_after_output_element(self, unit, ep_type, amount, source):
        """Run ON_AFTER_OUTPUT_ELEMENT_DAMAGE on the source's buffs when a
        source deals element damage (bb: _ep_type / _ep_delta)."""
        if source is None:
            return
        try:
            from .buff_templates import template as _tpl
        except Exception:
            return
        for entry in list(getattr(source, "buffs", None) or []):
            tpl_key = entry.get("template_key") or entry.get("templateKey")
            if not tpl_key:
                continue
            try:
                t = _tpl(tpl_key)
            except Exception:
                continue
            if not t or "ON_AFTER_OUTPUT_ELEMENT_DAMAGE" not in (
                    (t.get("eventToActions") or {})):
                continue
            self._fire(source, entry, "ON_AFTER_OUTPUT_ELEMENT_DAMAGE",
                       source=entry.get("source"), target=unit,
                       extra_bb={"_ep_type": ep_type,
                                 "_ep_delta": float(amount)})

    def ep_cooldown_speed(self, unit):
        """EP burst cooldown speed multiplier for a unit (?? S3:
        +50% recovery while in range -> cooldown ticks at 1.5/tick)."""
        if self.get(unit, "phatm2_s_3[token]"):
            return 1.5
        return 1.0

    def _burst_effect(self, unit, ep_type):
        """Element burst effects, side-split per the PRTS element page
        (https://prts.wiki/w/元素):
          0=neural 1=erosion 2=burning 3=decay.
        Player-class units use the 我方 effect; enemy-class units use the
        其他单位 effect (since 2026-04-07 enemy-class units use the enemy
        effect regardless of faction).  The element-damage components of
        the enemy effects hit the bursting unit itself, whose EP is locked
        by the just-started burst cooldown, so they are no-ops here."""
        b = self.battle
        enemy_side = getattr(unit, "side", 0) == 0
        if ep_type == 0:      # SANITY 神经损伤
            if enemy_side:
                # 若单位不具有麻痹免疫，获得3层麻痹（每层5s -> 15s 总时长；
                # PRTS: 麻痹等效果每5秒流失1层）；随后6000元素普通伤害在
                # 爆发冷却中被锁定，无实际效果。
                self.set_abnormal(unit, AbnormalFlag.PALSY, 15.0, layers=3)
            else:
                self.set_abnormal(unit, AbnormalFlag.STUNNED, 10.0)
                b.apply_damage(unit, 1000.0, DamageType.TRUE, source=None)
        elif ep_type == 1:    # WATER 侵蚀损伤
            if enemy_side:
                # 爆发期降至8s；-120防御永久可叠加（直接加算，不被重生清除）
                self._stack_ep_def(unit, -120.0)
                # 随后5000元素普通伤害：爆发冷却锁定，无实际效果。
            else:
                # -100防御永久可叠加 + 800物理普通伤害
                self._stack_ep_def(unit, -100.0)
                b.apply_damage(unit, 800.0, DamageType.PHYSICAL,
                               source=None)
            # Thumpy S3 belt marks: each water burst adds a permanent
            # -DEF stack (skill bb thumpy[ep_break_water].def = -30).
            for mark in [x for x in (unit.buffs or [])
                         if x.get("key") == "thumpy_s3_mark"]:
                try:
                    delta = float((mark.get("blackboard") or {}).get(
                        "def_delta", -30.0))
                except (TypeError, ValueError):
                    delta = -30.0
                existing = self.get(unit, "thumpy_ep_break_def")
                layers = (existing.get("layers", 1) if existing else 0) + 1
                b.add_buff(unit, {"key": "thumpy_ep_break_def",
                                  "stat": "def", "add": delta,
                                  "layers": layers,
                                  "remaining_ticks": 1 << 30,
                                  "source": mark.get("source")})
                b.emit(b.tick, "thumpy_ep_break",
                       {"unit": unit.inst_id, "defDelta": delta,
                        "source": getattr(mark.get("source"), "inst_id",
                                          None)})
            # Thumpy talent 2: marked-enemy bursts grant DEF + barrier
            # to the marking operator (????).
            for mark in [x for x in (unit.buffs or [])
                         if x.get("key") == "thumpy_water_mark"]:
                _src = mark.get("source")
                _ts = getattr(_src, "talent_system", None)
                if _ts is not None:
                    try:
                        _ts.thumpy_burst_reward(b, unit)
                    except Exception:
                        pass
        elif ep_type == 2:    # FIRE 灼燃损伤
            # 双方：爆发期间法术抗性-20（直接加算，持续10s）
            b.add_buff(unit, {"key": "ep_fire_mres", "remaining_ticks":
                              10 * 30, "layers": 1, "add": -20.0,
                              "stat": "magicResistance", "source": None})
            if enemy_side:
                # 7000元素普通伤害：爆发冷却锁定，无实际效果。
                pass
            else:
                # 1200法术普通伤害（可享受上面的法抗-20）
                b.apply_damage(unit, 1200.0, DamageType.MAGICAL,
                               source=None)
        elif ep_type == 3:    # DARK 凋亡损伤
            if enemy_side:
                # 15s 50%虚弱（随剩余时间线性衰减，见 update() 周期刷新）；
                # 每秒800元素持续伤害被爆发冷却锁定，无实际效果。
                b.add_buff(unit, {"key": "ep_dark_weaken",
                                  "remaining_ticks": 15 * 30, "layers": 1,
                                  "mul": -0.5, "source": None})
            else:
                # 15s 阻回+静默；期间每秒-1 SP 并受到100法术持续伤害
                self.set_abnormal(unit, AbnormalFlag.SP_RECOVER_STOPPED,
                                  15.0)
                self.set_abnormal(unit, AbnormalFlag.SILENCED, 15.0)
                b.add_buff(unit, {"key": "ep_dark_dot",
                                  "remaining_ticks": 15 * 30, "layers": 1,
                                  "source": None})

    def _stack_ep_def(self, unit, delta):
        """Permanent stackable DEF reduction from an erosion burst
        (each burst adds one layer; same-key buffs refresh layers)."""
        existing = self.get(unit, "ep_erosion_def")
        layers = (existing.get("layers", 1) if existing else 0) + 1
        self.battle.add_buff(unit, {"key": "ep_erosion_def",
                                    "remaining_ticks": 1 << 30,
                                    "layers": layers, "add": float(delta),
                                    "stat": "def", "source": None})
