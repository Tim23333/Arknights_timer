"""Enemy skill controller (docs 03_skill_system / 07_ai_decision).

Model:
  - Each enemy has skills: [{prefabKey, priority, cooldown, initCooldown,
    spCost, blackboard}] (from enemy_database merged with roster).
  - EnemySkill wraps an Ability: familyMask (1=ATTACK 2=COMBAT 4=SKILL
    8=TALENT 16=GENERAL), cooldown timer, max trigger count, SP cost.
  - Every tick: decrement cooldowns; when castable pick the highest-priority
    available skill (CD ready, not used up, SP enough, trigger has a target
    unless allowNoTarget), else normal attack.
  - Ability timeline: preDelay -> spell_on (execute effects) -> postDelay ->
    cast_end (reset CD, spend SP, triggerCnt++).
"""

from .consts import (AbnormalFlag, DamageType, EnemyState, FinishReason,
                     resolve_attack_range, translate_game_damage_type,
                     translate_game_element_type)
from .damage import calculate_damage
import json
import re


class EnemySkillController:
    """Attached to Enemy.skill_controller. Drives skills + normal attack."""

    def __init__(self, enemy, battle, catalog_entries=None, store=None):
        self.enemy = enemy
        self.battle = battle
        self.store = store
        self.skills = []          # list of EnemySkillRun
        self.casting = None       # active ability run
        self.normal_attack_cd = 0.0
        # enemy mode state machine (e.g. 进化的本质 初生/进化/完美):
        # 0-based current form; switch skills and per-mode attack chains
        # are gated on it (see EnemySkillRun mode parsing).
        self.mode_index = 0
        # form-machine parameters from the enemy talentBlackboard
        # (mode_{n}.hp_ratio / evolve_time / damage_resistance / direction /
        # interval / damage / mode_{n}_summon.interval / branch_id), e.g.
        # 进化的本质 enemy_1519_bgball: 60% -> 进化, 20% -> 完美, 100s
        # timeout, side resist 0.8 / 0.99, perfect self-DoT 300 true dmg/s,
        # summons every 5s / 3s / 2s.
        self.mode_params = self._parse_mode_params(
            getattr(enemy, "talent_blackboard", None) or {})
        self.mode_enter_tick = 0
        self._mode_dot_acc = 0.0
        self._mode_summon_acc = 0.0
        self._init_skills(enemy, catalog_entries)
        # aggregate aura definitions from all skills onto the enemy
        enemy.auras = [a for sk in self.skills
                       for a in getattr(sk, "auras", [])]
        self._aura_acc = 0
        if getattr(enemy, "auras", None):
            self._update_auras(force=True)

    # ---- init ----
    def _init_skills(self, enemy, catalog_entries):
        raw_skills = getattr(enemy, "skills", None) or []
        for sk in raw_skills:
            entry = self._catalog_entry(catalog_entries, sk, enemy)
            self.skills.append(EnemySkillRun(enemy, sk, entry, self.battle,
                                             self.store))
        self.skills.sort(key=lambda s: (s.priority if s.priority is not None else 0),
                         reverse=True)
        self.normal_attack_cd = enemy.attributes.attack_interval()

    def _catalog_entry(self, catalog_entries, skill, enemy):
        if catalog_entries:
            prefab = skill.get("prefabKey")
            for e in catalog_entries:
                if (e.get("prefabKey") == prefab and
                        e.get("enemyId") == enemy.enemy_key):
                    return e
        return None

    # ---- per-tick ----
    def update(self, dt=1.0 / 30.0):
        enemy = self.enemy
        for s in self.skills:
            s.cooldown_remaining = max(0.0, s.cooldown_remaining - dt)
        # enemy SP recovery (spData)
        self._update_sp(dt)
        # form machine: HP / duration switch + per-form passives run even
        # while a cast is in flight (self-DoT / summons / HP threshold)
        self._mode_condition_check()
        self._mode_passive_tick(dt)
        if self.casting is not None:
            self.casting.tick(dt)
            if self.casting.finished:
                _fin_skill = self.casting.skill
                _fin_target = self.casting.target
                try:
                    self.battle._dispatch_buff_events(
                        self.enemy, "ON_SKILL_FINISH",
                        source=self.enemy, target=self.enemy)
                    self.battle._dispatch_buff_events(
                        self.enemy, "ON_ABILITY_FINISH",
                        source=self.enemy, target=self.enemy)
                except Exception:
                    pass
                self.casting = None
                self.enemy._immune_stun_affecting = False
                # mode-form attack chain: Warning -> Effect -> RealAttack
                # fire back-to-back (CompositeAbility always-next), so the
                # next stage casts immediately after the previous finishes.
                _nxt = self._chain_next(_fin_skill)
                if _nxt is not None:
                    t = _fin_target
                    if t is None or getattr(t, "dead", False):
                        t = self._find_target(_nxt)
                    if t is not None or _nxt.allow_no_target:
                        self._start_cast((_nxt, t))
                        return
            return
        # aura buffs refresh every second
        if getattr(enemy, "auras", None):
            self._aura_acc += dt
            if self._aura_acc >= 1.0:
                self._aura_acc = 0.0
                self._update_auras()
        if self._can_act():
            self.normal_attack_cd = max(0.0, self.normal_attack_cd - dt)

    def _update_sp(self, dt):
        """Enemy SP per spType: 1=auto(time), 2=attack, 4=taken damage."""
        e = self.enemy
        if e.sp_max <= 0:
            return
        spd = getattr(e, "_sp_data", None) or {}
        st = int(spd.get("spType") or 0)
        if st == 1:   # INCREASE_WITH_TIME
            inc = float(spd.get("increment") or 1.0)
            if e.flag(1):      # SP_RECOVER_STOPPED
                return
            e.sp = min(e.sp_max, e.sp + inc * dt)
        # spType 2/4 handled by hooks: on_attack() / on_take_damage()

    # ---- mode state machine (form switch + per-form passives) ----
    def _parse_mode_params(self, tb):
        """talentBlackboard ``mode_{n}.*`` / ``mode_{n}_summon.*`` keys ->
        per-mode dict (0-based index)."""
        out = {}
        for k, v in (tb or {}).items():
            # the shipped data spells mode_1 summon interval
            # "mode_1_summoni.interval" (missing 'n') - accept both
            m = re.match(r"^mode_(\d+)(_summoni?)?\.([a-z_]+)$", str(k))
            if not m:
                continue
            idx = int(m.group(1)) - 1
            key = ("summon_" + m.group(3)) if m.group(2) else m.group(3)
            try:
                val = float(v)
            except (TypeError, ValueError):
                val = v
            out.setdefault(idx, {})[key] = val
        return out

    def _mode_condition_check(self):
        """HP / duration driven form switch (PRTS 进化的本质: mode_1
        hp_ratio 60% / mode_2 hp_ratio 20%, evolve_time 100s per form).
        When the leaving form's condition is met, force-cast its
        SwitchToMode skill - independent of the form's periodic charge
        attack (the old real-attack-fired gate stays for manual/level-
        triggered switches, PRTS marks HP/time as the actual trigger)."""
        mp = self.mode_params.get(self.mode_index)
        if not mp:
            return
        battle = self.battle
        if battle is None:
            return
        e = self.enemy
        if getattr(e, "dead", False):
            return
        hp_ratio = float(mp.get("hp_ratio") or 0.0)
        evolve_time = float(mp.get("evolve_time") or 0.0)
        triggered = False
        if hp_ratio > 0:
            max_hp = float(getattr(e, "max_hp", 0.0) or 0.0)
            if max_hp > 0 and \
                    float(getattr(e, "hp", 0.0) or 0.0) / max_hp < hp_ratio:
                triggered = True
        if not triggered and evolve_time > 0 and \
                battle.tick - self.mode_enter_tick >= evolve_time * 30:
            triggered = True
        if not triggered:
            return
        switch = None
        for s in self.skills:
            if s.mode_from == self.mode_index and s.mode_to is not None:
                switch = s
                break
        if switch is None or self.casting is not None:
            return
        if switch.cooldown_remaining > 0:
            return
        if e.flag(12) and not switch.ignore_silence:
            return
        self._start_cast((switch, None))

    def _mode_passive_tick(self, dt):
        """Per-form passive effects (进化的本质): perfect-form self true
        damage (mode_3.damage 300 every mode_3.interval 1s) and periodic
        summon cadence (mode_{n}_summon.interval -> branch_id)."""
        mp = self.mode_params.get(self.mode_index)
        if not mp:
            return
        e = self.enemy
        battle = self.battle
        if getattr(e, "dead", False):
            return
        interval = float(mp.get("interval") or 0.0)
        damage = float(mp.get("damage") or 0.0)
        if interval > 0 and damage > 0:
            self._mode_dot_acc = float(
                getattr(self, "_mode_dot_acc", 0.0)) + dt
            if self._mode_dot_acc >= interval - 1e-9:
                self._mode_dot_acc = 0.0
                if battle is not None:
                    battle.apply_damage(e, damage, DamageType.TRUE,
                                        source=None)
        s_int = float(mp.get("summon_interval") or 0.0)
        branch = mp.get("summon_branch_id")
        if s_int > 0 and branch and battle is not None:
            self._mode_summon_acc = float(
                getattr(self, "_mode_summon_acc", 0.0)) + dt
            if self._mode_summon_acc >= s_int - 1e-9:
                self._mode_summon_acc = 0.0
                battle.try_enemy_branch_summon(str(branch), e)

    def skill_states(self):
        """Per-skill runtime state for snapshots / AI."""
        out = []
        for sk in self.skills:
            out.append({
                "prefabKey": sk.prefab_key,
                "priority": sk.priority,
                "cooldown": sk.cooldown,
                "cooldownRemaining": round(sk.cooldown_remaining, 3),
                "spCost": sk.sp_cost,
                "triggerCount": sk.trigger_count,
                "maxTriggerTime": sk.max_trigger_time,
                "usedUp": sk.is_used_up,
                "waitForAttackEvent": sk.wait_for_attack_event,
                "selfBuffs": [sb["data"].get("buffKey")
                              for sb in sk.self_buffs],
                "targetBuffs": [b.get("buffKey") for b in sk.prefab_buffs],
            })
        return out

    def casting_state(self):
        if self.casting is None:
            return None
        return {
            "skill": self.casting.skill.prefab_key,
            "phase": self.casting.phase,
            "preRemaining": round(self.casting.pre_remaining, 3),
            "postRemaining": round(self.casting.post_remaining, 3),
            "target": self.casting.target.inst_id if self.casting.target
            else None,
        }

    # ---- aura system ----
    def _aura_bb(self):
        """Merged blackboard of all skills (aura durations come from here)."""
        bb = {}
        for sk in self.skills:
            bb.update(sk.blackboard)
        return bb

    def _update_auras(self, force=False):
        e = self.enemy
        battle = self.battle
        if battle is None:
            return
        bb = self._aura_bb()
        radius = resolve_attack_range(e.attributes.get("rangeRadius"))
        r, c = e.row, e.col
        for aura in e.auras:
            aradius = aura.get("radius") or radius
            targets = []
            for other in battle.get_enemies():
                if other is e or other.dead:
                    continue
                if abs(other.row - r) <= aradius and \
                        abs(other.col - c) <= aradius:
                    targets.append(other)
            if aura["self_option"] == 1 and not e.dead:
                targets.append(e)
            applied = aura.setdefault("_applied", {})
            in_range = set()
            for t in targets:
                in_range.add(t.inst_id)
                if aura["only_once"] and t.inst_id in applied:
                    continue
                for bd in aura["buffs"]:
                    self._apply_aura_buff(t, bd, bb)
                applied[t.inst_id] = True
            if aura["remove_when_leave"]:
                keys = [bd.get("buffKey") for bd in aura["buffs"]]
                for other in battle.get_enemies():
                    if other.inst_id in applied and \
                            other.inst_id not in in_range:
                        for k in keys:
                            battle.buffs.remove(other, k)
                        applied.pop(other.inst_id, None)

    def _apply_aura_buff(self, target, buff_data, bb):
        """Resolve (DB merge + blackboard) and apply an aura buff."""
        try:
            from .buff_templates import (buff_definition, materialise_buff,
                                         named_buff)
            data = buff_data
            if data.get("loadFromDB"):
                db = buff_definition(data.get("buffKey") or "")
                if db:
                    merged = named_buff(db)
                    for k, v in data.items():
                        if v not in (None, "", 0, [], {}):
                            if k == "templateKey" and str(v).lower() in (
                                    "empty", "none"):
                                continue
                            merged[k] = v
                    data = merged
            entry = materialise_buff(self.battle, target, data, dict(bb),
                                     self.enemy)
            if entry and entry.get("key"):
                self.battle.add_buff(target, entry)
        except Exception:
            pass

    def on_enemy_attack(self):
        """Called after an enemy attack; +SP for spType 2 (attack)."""
        e = self.enemy
        spd = getattr(e, "_sp_data", None) or {}
        if int(spd.get("spType") or 0) == 2:
            e.sp = min(e.sp_max, e.sp + float(spd.get("increment") or 1.0))

    def on_enemy_take_damage(self):
        """Called when enemy takes damage; +SP for spType 4."""
        e = self.enemy
        spd = getattr(e, "_sp_data", None) or {}
        if int(spd.get("spType") or 0) & 4:
            e.sp = min(e.sp_max, e.sp + float(spd.get("increment") or 1.0))

    def _can_act(self):
        e = self.enemy
        return e.state in (EnemyState.MOVE, EnemyState.ATTACK,
                           EnemyState.COMBAT) and not any(
            e.flag(f) for f in (0, 16, 25, 39))

    def should_cast_normal_attack(self):
        """Battle calls when attack timer expires. True = skill took over."""
        if self.casting is not None:
            return True
        chosen = self._pick_skill()
        if chosen is not None:
            self._start_cast(chosen)
            return True
        return False

    def _pick_skill(self):
        for s in self.skills:
            if not self._skill_available(s):
                continue
            target = self._find_target(s)
            if target is None and not s.allow_no_target:
                continue
            return (s, target)
        return None

    def _skill_available(self, s):
        e = self.enemy
        if s.is_used_up:
            return False
        if s.cooldown_remaining > 0:
            return False
        # mode-gated skills: per-form attack chains only run in their own
        # form; switch skills only in the form they leave.
        if s.mode_skill is not None and s.mode_skill != self.mode_index:
            return False
        if s.mode_from is not None:
            if s.mode_from != self.mode_index:
                return False
            # HP / duration driven mode machine (mode_params present, e.g.
            # 进化的本质): the switch skill is cast ONLY by
            # _mode_condition_check (PRTS: HP < 60% / 20% or 100s per
            # form), never by the generic skill picker - the old
            # "real-attack fired" gate would switch the boss too early.
            if self.mode_params:
                return False
            # PRTS: every form periodically releases its charged attack
            # (初生 900 / 进化 1000 / 完美 1200 true to all operators)
            # before evolving; a switch only opens after the leaving
            # form's real attack has fired at least once.
            if not self._mode_real_attack_fired(s.mode_from):
                return False
        # Effect/RealAttack chain stages are cast only as continuations of
        # the mode attack chain, never picked independently
        if getattr(s, "mode_chain_only", False):
            return False
        if s.sp_cost and e.sp < s.sp_cost:
            return False
        if e.flag(12) and not s.ignore_silence:      # SILENCED
            return False
        if s.check_parent_active and not getattr(e, "parent_active", True):
            return False
        return True

    def _mode_real_attack_fired(self, mode):
        """True when the given form's M{n}RealAttack has landed at least
        once (gate for SwitchToMode skills)."""
        for s in self.skills:
            if s.mode_skill == mode and s.mode_real_attack \
                    and s.trigger_count > 0:
                return True
        return False

    def _chain_next(self, skill):
        """Next stage of a mode-form attack chain (M{n}AttackWarning ->
        M{n}Effect -> M{n}RealAttack), or None."""
        stage = getattr(skill, "mode_chain_stage", None)
        if stage is None or skill.mode_skill is None:
            return None
        nxt = {"warning": "effect", "effect": "real"}.get(stage)
        if not nxt:
            return None
        for s in self.skills:
            if s.mode_skill == skill.mode_skill and \
                    getattr(s, "mode_chain_stage", None) == nxt:
                return s
        return None

    def _find_target(self, s):
        enemy = self.enemy
        # a blocked enemy's abilities target its blocker first
        # (MECHANICS 5.1: ?? -> ????? -> ??? -> ????)
        blk = enemy.blocked_by
        if blk is not None and getattr(blk, "side", 0) == 1 \
                and not blk.dead:
            return blk
        radius = s.range_radius
        base = resolve_attack_range(enemy.attributes.get("rangeRadius"))
        # bb range_radius is the EFFECT radius (splash / aoe), while target
        # selection follows the enemy's attack range; a melee skill with
        # range_radius 0.8 must still reach an adjacent tile (1.5 default).
        radius = max(radius or 0.0, base)
        ops = [o for o in self.battle.get_operators()
               if not o.dead and not o.in_deploy_anim(self.battle.tick)]
        if not ops:
            return None
        # Skill target selectors obey the same 3-logic-tick search gate as
        # normal attacks (SelectorTrigger.SEARCH_TARGET_TICK=3, dump.cs:
        # 437169): repeated searches inside the window keep the cached
        # target while it is still alive; when the cached target is no
        # longer a valid in-range candidate the search re-runs immediately
        # (Search(force)).  The blocked fast-path above stays ungated.
        from .targeting import search_gate

        def _scan():
            best = None
            best_d = float("inf")
            for o in ops:
                d = ((enemy.pos_x - o.pos_x) ** 2 +
                     (enemy.pos_y - o.pos_y) ** 2) ** 0.5
                if d <= radius and d < best_d:
                    best, best_d = o, d
            return best

        target = search_gate(enemy, self.battle, _scan)
        if target is not None:
            d = ((enemy.pos_x - target.pos_x) ** 2 +
                 (enemy.pos_y - target.pos_y) ** 2) ** 0.5
            if target not in ops or d > radius:
                target = search_gate(enemy, self.battle, _scan, force=True)
        return target

    def force_trigger(self, prefab_key):
        """Trigger a skill by prefabKey (buff TriggerEnemySkill node):
        casts it immediately when available and not already casting."""
        if self.casting is not None:
            return False
        for s in self.skills:
            if s.prefab_key != prefab_key or not self._skill_available(s):
                continue
            target = self._find_target(s)
            if target is None and not s.allow_no_target:
                continue
            self._start_cast((s, target))
            return True
        return False

    def _start_cast(self, chosen):
        s, target = chosen
        self.casting = AbilityRun(self, s, target, self.battle)
        # EnemySkill._immuneStunWhenAffecting: stun-immune while casting
        self.enemy._immune_stun_affecting = bool(
            getattr(s, "immune_stun_when_affecting", False))
        if self.battle:
            try:
                self.battle._dispatch_buff_events(self.enemy,
                                                  "ON_SKILL_START",
                                                  source=self.enemy,
                                                  target=target or
                                                  self.enemy)
                self.battle._dispatch_buff_events(
                    self.enemy, "ON_ABILITY_START",
                    source=self.enemy, target=target or self.enemy)
                if target is not None:
                    self.battle._dispatch_buff_events(
                        self.enemy, "ON_ABILITY_CAST_ON_TARGET",
                        source=self.enemy, target=target)
                self.battle._dispatch_buff_events(
                    self.enemy, "ON_ABILITY_SPELL_ON",
                    source=self.enemy, target=target or self.enemy)
            except Exception:
                pass
            self.battle.emit(self.battle.tick, "skill_cast",
                             {"unit": self.enemy.inst_id,
                              "skill": s.prefab_key,
                              "target": target.inst_id if target else None})

    def on_attack_timer_zero(self):
        if self.casting is None:
            return self.should_cast_normal_attack()
        return True


class EnemySkillRun:
    """One skill instance with runtime CD/trigger counters."""

    def __init__(self, enemy, skill, catalog_entry, battle, store=None):
        self.enemy = enemy
        self.battle = battle
        self.store = store
        self.prefab_key = skill.get("prefabKey")
        # ?? prefab ??????????damageType/??/??/???
        self.prefab = store.enemy_prefab_ability_fields(
            enemy.enemy_key, self.prefab_key) \
            if store is not None else {}
        # defensive numeric coercion: a few parsed skill entries carry a
        # blackboard key string where the numeric field should be (e.g.
        # DeepBreathS4.spCost == "startCol"); never crash on them
        def _num(v, default=None):
            if v is None:
                return default
            try:
                return float(v)
            except (TypeError, ValueError):
                return default
        self.priority = _num(skill.get("priority"))
        self.cooldown = _num(skill.get("cooldown"))
        self.init_cooldown = _num(skill.get("initCooldown"))
        try:
            self.sp_cost = int(_num(skill.get("spCost"), 0))
        except (TypeError, ValueError):
            self.sp_cost = 0
        self.blackboard = {
            b["key"]: (b.get("value")
                       if b.get("value") is not None
                       else b.get("valueStr"))
            for b in (skill.get("blackboard") or [])
            if b.get("key") is not None}
        catalog_entry = catalog_entry or {}
        es = catalog_entry.get("enemySkill") or {}
        for b in (catalog_entry.get("blackboard") or []):
            if b.get("key") is None:
                continue
            self.blackboard[b["key"]] = (
                b.get("value") if b.get("value") is not None
                else b.get("valueStr"))
        self.family_mask = int(es.get("_familyMask", 3))
        self.max_trigger_time = int(es.get("_maxTriggerTime", -1))
        self.overwrite_init_cd = es.get("_overwriteInitCooldown", -1)
        self.ignore_silence = bool(es.get("_ignoreSilence", 0))
        self.cast_like_attack = bool(es.get("_castLikeAttack", 0))
        self.reset_main_ability_cd = bool(es.get("_resetMainAbilityCdWhenCastEnd", 0))
        self.reset_cd_wait_first = bool(es.get("_resetCdWaitFirstPeriod", 1))
        self.check_parent_active = bool(es.get("_checkParentActive", 0))
        # EnemySkill._immuneStunWhenAffecting: while this skill is being
        # cast the enemy ignores incoming stuns (dump.cs EnemySkill 0x39).
        self.immune_stun_when_affecting = bool(
            es.get("_immuneStunWhenAffecting", 0))
        self.add_enemy_id_to_signal_id = bool(
            es.get("_addEnemyIdToSignalId", 0))
        self.trigger_count = 0
        # variable cooldown sequence: cooldown_0, cooldown_1, ... (docs 03)
        self.cooldown_sequence = []
        for i in range(32):
            v = self.blackboard.get(f"cooldown_{i}")
            if v is None:
                break
            self.cooldown_sequence.append(float(v))
        if self.overwrite_init_cd is not None and self.overwrite_init_cd >= 0:
            first_cd = float(self.overwrite_init_cd)
        elif self.init_cooldown is not None:
            first_cd = float(self.init_cooldown)
        elif self.cooldown_sequence:
            first_cd = self.cooldown_sequence[0]
        else:
            first_cd = float(self.cooldown or 0.0)
        self.cooldown_remaining = max(0.0, first_cd)
        self.abilities = catalog_entry.get("abilities") or []
        self.allow_no_target = False
        self.range_radius = None
        self.pre_delay = 0.0
        # enemy mode state machine fields: switch skills carry
        # C{n}_Die -> C{m}_Idle anim keys (form n dies, form m appears);
        # per-form attack chains use the M{n}* prefab-key prefix.
        self.mode_from = None
        self.mode_to = None
        self.mode_skill = None
        self.mode_real_attack = False
        self.mode_chain_stage = None
        self.mode_chain_only = False
        for ab in self.abilities:
            if "_allowNoTarget" in ab:
                self.allow_no_target = bool(ab.get("_allowNoTarget", 0))
            if "_preDelay" in ab and ab.get("_preDelay"):
                self.pre_delay = float(ab.get("_preDelay"))
        pf = self.prefab
        # enemy mode state machine fields: switch skills carry
        # C{n}_Die -> C{m}_Idle anim keys (form n dies, form m appears);
        # per-form attack chains use the M{n}* prefab-key prefix.
        try:
            import re as _re
            _ak = str(pf.get("_animKey") or "")
            _ek = str(pf.get("_endAnimKey") or "")
            _mf = _re.match(r"^C(\d+)_Die$", _ak)
            _mt = _re.match(r"^C(\d+)_Idle$", _ek)
            if _mf and _mt:
                self.mode_from = int(_mf.group(1)) - 1
                self.mode_to = int(_mt.group(1)) - 1
            _mk = _re.match(r"^M(\d+)", str(self.prefab_key or ""))
            if _mk:
                self.mode_skill = int(_mk.group(1)) - 1
            self.mode_real_attack = bool(_re.match(
                r"^M(\d+)RealAttack$", str(self.prefab_key or "")))
            _mcs = _re.match(
                r"^M(\d+)(AttackWarning|Effect|RealAttack)$",
                str(self.prefab_key or ""))
            if _mcs:
                self.mode_chain_stage = {
                    "AttackWarning": "warning",
                    "Effect": "effect",
                    "RealAttack": "real"}.get(_mcs.group(2))
                # Effect/RealAttack only fire as chain continuations
                self.mode_chain_only = self.mode_chain_stage in (
                    "effect", "real")
        except Exception:
            pass
        if pf.get("_preDelay") is not None:
            self.pre_delay = float(pf.get("_preDelay"))
        # EasyToStartAbility._waitForAttackEvent: when true the ability
        # waits for the spine OnAttack event before executing effects;
        # when false effects fire at spell start (after preDelay).
        # Absent in the extract -> keep the OnAttack-driven behaviour.
        _waits = [ab.get("_waitForAttackEvent") for ab in self.abilities
                  if "_waitForAttackEvent" in ab]
        if _waits:
            self.wait_for_attack_event = any(_waits)
        else:
            _wfe = pf.get("_waitForAttackEvent")
            self.wait_for_attack_event = (
                bool(_wfe) if _wfe is not None else True)
        r = self.blackboard.get("range_radius") or \
            self.blackboard.get("rangeRadius")
        self.range_radius = float(r) if r is not None else None
        # ?????????? prefab ????
        self.anim_key = pf.get("_animKey")
        self.atk_scale = float(pf.get("_atkScale") or 1.0)
        # prefab damage types use the GAME enums (PHYSICAL=1 MAGICAL=2
        # PURE=3 ELEMENT=5; ElementType SANITY=1..DARK=4) -> translate
        self.prefab_damage_type = translate_game_damage_type(
            pf.get("_damageType")) if pf.get("_damageType") is not None \
            else None
        self.element_damage_type = translate_game_element_type(
            pf.get("_elementDamageType")) if pf.get("_elementDamageType") \
            is not None else 0
        self.ep_damage_ratio = float(pf.get("_epDamageRatio") or 0.0)
        self.projectile_key = pf.get("_projectileKey")
        self.face_to_target = bool(pf.get("_faceToTarget", 0))
        self.max_anim_scale = float(pf.get("_maxAnimScale") or 1.0)
        self.affected_by_slow_down = bool(pf.get("_affectedBySlowDown", 1))
        self.cooldown_key = pf.get("_cooldownKey")
        # ?????xLua Nodes????????
        self.action_nodes = (pf.get("_actions") or {}).get(
            "SerializedState") if pf.get("_actions") else None
        self.action_nodes_trigger = (pf.get("_actionsOnTrigger") or {}).get(
            "SerializedState") if pf.get("_actionsOnTrigger") else None
        # prefab-attached BuffData lists, classified by target:
        #   prefab_buffs -> applied to the cast target (debuffs on hit)
        #   self_buffs   -> applied to the casting enemy itself
        #     ({data, remove_on_end}: BuffToOwnerDuringAbility entries are
        #      removed at cast end; _passiveBuffs are kept)
        # AuraAbility components (selfOption present) carry passive aura
        # buffs instead -- they are handled by the aura system separately.
        self.prefab_buffs = []
        self.self_buffs = []
        self.auras = []
        # behavior buffKeys are aggregated per prefab (shared prefab =
        # union of every enemy that uses it), so only keys naming this
        # enemy's own code with a self-oriented template count as the
        # caster's own buffs; they are applied here and skipped from
        # the target-buff list below.
        self._behavior_self_keys = set()
        _key = getattr(enemy, "enemy_key", None) or ""
        _code = _key.split("_", 2)[-1] if _key else ""
        _codes = {_code} if _code else set()
        _tail = _code
        while "_" in _tail:
            _suf = _tail.rsplit("_", 1)[1]
            if _suf.isdigit() or (len(_suf) == 1 and _suf.isalpha()):
                _tail = _tail.rsplit("_", 1)[0]
                _codes.add(_tail)
            else:
                break
        try:
            from .buff_templates import template as _tpl
        except Exception:
            _tpl = None
        if _tpl is not None:
            for _bk in (catalog_entry.get("buffKeys") or []):
                if not _bk or str(_bk).lower() in ("empty", "none"):
                    continue
                try:
                    _tplv = _tpl(_bk)
                except Exception:
                    _tplv = None
                if not _tplv:
                    continue
                _s = json.dumps(_tplv, ensure_ascii=False)
                _own = (not _codes or
                        any(_cd in _bk for _cd in _codes))
                _heal_shared = (
                    "HealViaMaxHpRatio" in _s or "FixedValueHeal" in _s)
                # shared templates whose actions target an explicit victim
                # (kill / damage / element) are mounted on the TARGET, even
                # when they also reference BUFF_SOURCE for the caster
                # (e.g. bldkgt_t_devour: heal caster + kill victim).
                # only ON_BUFF_START victim actions decide target mounting;
                # ON_BUFF_FINISH InstantKill is a self-suicide (e.g.
                # enemy_trtrsl_s run_suc) and must not exclude the buff.
                _start_s = json.dumps(
                    (_tplv.get("eventToActions") or {}).get(
                        "ON_BUFF_START", []), ensure_ascii=False)
                _target_action = any(
                    _k in _start_s for _k in ("InstantKill",
                                              "AdvancedApplyDamage",
                                              "NoSourceDamage", "AOEDamage",
                                              "DamageVia",
                                              "ApplyElementDamage"))
                if _target_action:
                    continue
                if not _own and not _heal_shared:
                    # shared pure-self templates (mode switches, run
                    # buffs) reference BUFF_OWNER/BUFF_SOURCE without
                    # any victim action -> treat as the caster's own
                    if "BUFF_OWNER" in _s or "BUFF_SOURCE" in _s:
                        _own = True
                    if not _own:
                        continue
                if "BUFF_OWNER" not in _s and "BUFF_SOURCE" not in _s:
                    continue
                self._behavior_self_keys.add(_bk)
        try:
            for c in (store.enemy_prefab_components(
                          enemy.enemy_key, self.prefab_key)
                      if store is not None else []):
                f = c.get("fields") or {}
                if "_selfOption" in f:
                    buffs = []
                    for key in ("_buffs", "_passiveBuffs"):
                        for b in f.get(key) or []:
                            if isinstance(b, dict) and b.get("buffKey"):
                                buffs.append(b)
                    if buffs:
                        self.auras.append({
                            "buffs": buffs,
                            "self_option": int(f.get("_selfOption") or 0),
                            "remove_when_leave": bool(
                                f.get("_removeBuffWhenTargetLeave", 0)),
                            "only_once": bool(
                                f.get("_onlyAddBuffOnceForEachTarget", 0)),
                            "radius": None,
                            "_applied": {},
                        })
                    continue
                # BuffToOwnerDuringAbility: buffs the owner (self) during
                # the skill window and removes them at cast end.
                is_owner_buff = ("_forceFinishBuffOnCastEnd" in f or
                                 ("_startEvent" in f and "_endEvent" in f)) \
                    and "_buffs" in f
                if is_owner_buff:
                    for b in f.get("_buffs") or []:
                        if isinstance(b, dict) and b.get("buffKey"):
                            self.self_buffs.append(
                                {"data": b, "remove_on_end": True})
                # FilterBuffTarget selectors use _buffs as filter keys,
                # not buffs to apply.
                if "_filterBuffSource" in f:
                    continue
                for key in ("_passiveBuffs", "_passiveBuffsToOwner"):
                    for b in f.get(key) or []:
                        if isinstance(b, dict) and b.get("buffKey"):
                            self.self_buffs.append(
                                {"data": b, "remove_on_end": False})
                for key in ("_activeBuffs", "_additiveActiveBuffs"):
                    for b in f.get(key) or []:
                        if isinstance(b, dict) and b.get("buffKey"):
                            if b["buffKey"] in self._behavior_self_keys:
                                continue
                            self.prefab_buffs.append(b)
                if not is_owner_buff:
                    for b in f.get("_buffs") or []:
                        if isinstance(b, dict) and b.get("buffKey"):
                            if b["buffKey"] in self._behavior_self_keys:
                                continue
                            self.prefab_buffs.append(b)
        except Exception:
            pass
        # dedupe self buffs by key (the same BuffData repeats per component)
        _seen = set()
        _dedup = []
        for sb in self.self_buffs:
            k = sb["data"].get("buffKey")
            if k in _seen:
                continue
            _seen.add(k)
            _dedup.append(sb)
        self.self_buffs = _dedup
        # apply the caster's own behavior buffs at spell_on (the
        # per-enemy buffKeys were resolved and filtered above)
        for _bk in sorted(self._behavior_self_keys):
            if any(sb["data"].get("buffKey") == _bk
                   for sb in self.self_buffs):
                continue
            self.self_buffs.append({
                "data": {"buffKey": _bk, "templateKey": _bk,
                         "attributes": {}, "maxStackCnt": 1},
                "remove_on_end": False, "behavior": True,
            })
        # OnAttack hit frames: prefer the calibrated per-skill entry
        # (data_enemy_attack_timing.json, keyed by prefabKey); fall back to
        # the animation-based lookup on _animKey.
        self.hit_times = []
        try:
            from .attack_timing import (animation_duration, on_attack_times,
                                        skill_hit_times)
            self.hit_times = skill_hit_times(enemy.enemy_key,
                                             self.prefab_key)
            if not self.hit_times:
                self.hit_times = on_attack_times(enemy.enemy_key,
                                                 self.anim_key)
            self.anim_duration = animation_duration(enemy.enemy_key,
                                                    self.anim_key) or 0.0
        except Exception:
            self.anim_duration = 0.0

    @property
    def is_used_up(self):
        return 0 <= self.max_trigger_time <= self.trigger_count

    def _apply_cooldown(self):
        """Set the cooldown after a cast (normal or interrupted)."""
        if self.cooldown_sequence:
            idx = min(self.trigger_count, len(self.cooldown_sequence)) - 1
            cd = self.cooldown_sequence[idx]
        else:
            cd = float(self.cooldown or 0.0)
        self.cooldown_remaining = max(0.0, cd)

    def on_cast_finish(self):
        self.trigger_count += 1
        if self.sp_cost:
            self.enemy.sp = max(0.0, self.enemy.sp - self.sp_cost)
        self._apply_cooldown()
        # mode switch skill finished -> the enemy enters the new form
        if self.mode_to is not None:
            sc = getattr(self.enemy, "skill_controller", None)
            if sc is not None:
                sc.mode_index = self.mode_to
                sc.mode_enter_tick = sc.battle.tick if sc.battle else 0
                sc._mode_dot_acc = 0.0
                sc._mode_summon_acc = 0.0
                # form-entry invincibility (SwitchToMode blackboard
                # invincible_after_skill_duration, e.g. 进化的本质 10s)
                try:
                    _inv = float((self.blackboard or {}).get(
                        "invincible_after_skill_duration") or 0.0)
                except (TypeError, ValueError):
                    _inv = 0.0
                if _inv > 0 and sc.battle:
                    sc.battle.add_abnormal(self.enemy,
                                           AbnormalFlag.INVINCIBLE, _inv)
                if sc.battle:
                    sc.battle.emit(sc.battle.tick, "enemy_mode_switch",
                                   {"unit": self.enemy.inst_id,
                                    "mode": self.mode_to,
                                    "skill": self.prefab_key,
                                    "invincible": _inv})


class AbilityRun:
    """Active ability cast timeline: preDelay -> spell -> postDelay -> end."""

    def __init__(self, controller, skill, target, battle):
        self.controller = controller
        self.enemy = controller.enemy
        self.skill = skill
        self.target = target
        # the ability's target context: buff-template TARGET nodes
        # (e.g. devour InstantKill) resolve to this unit, not the
        # buff owner, when the buff fires during the cast
        self.enemy._skill_target = target
        self.battle = battle
        self.phase = "pre_delay"
        self.pre_remaining = float(skill.pre_delay or 0.0)
        self.post_remaining = 0.2          # simplified ?? (0.2s)
        self.finished = False
        self.finish_reason = FinishReason.NORMAL_EXIT
        self.hit_times = sorted(
            float(t) for t in (getattr(skill, "hit_times", []) or [])
            if t is not None)
        # effects wait for each spine OnAttack hit frame within the skill
        # animation (relative to the spell start); no events -> immediate.
        # Multi-hit skills execute effects once per hit frame.
        self._hit_deltas = []
        prev = 0.0
        for t in self.hit_times:
            d = max(1, int(round((t - prev) * 30.0)))
            self._hit_deltas.append(d)
            prev = t
        self.hit_wait = self._hit_deltas[0] if self._hit_deltas else 0
        self.wait_for_attack_event = bool(
            getattr(skill, "wait_for_attack_event", True))
        self._spell_on_done = False
        # wait=1: effective spell_on = max(preDelay, first OnAttack)
        # measured from cast start; the remaining wait after preDelay
        # is max(0, hit_times[0] - preDelay) (both fire at 0 for the
        # common preDelay=0 case, keeping the old sum behaviour)
        _pd = float(getattr(skill, "pre_delay", 0.0) or 0.0)
        self._first_hit_after_pre_ticks = 0
        if self._hit_deltas:
            _rem = self.hit_times[0] - _pd
            self._first_hit_after_pre_ticks = max(
                0, int(round(_rem * 30.0)))

    def tick(self, dt):
        if self.finished:
            return
        if self.phase == "pre_delay":
            if self._check_interrupt():
                self._finish(FinishReason.INTERRUPTED)
                return
            self.pre_remaining -= dt
            if self.pre_remaining <= 0:
                self.phase = "spell"
                if self.wait_for_attack_event and self._hit_deltas:
                    # spell_on = first OnAttack frame; action nodes and
                    # self buffs fire together with the effects there
                    self.hit_wait = self._first_hit_after_pre_ticks
                else:
                    self._spell_on()
        elif self.phase == "spell":
            if self.wait_for_attack_event and self.hit_wait > 0:
                self.hit_wait -= 1
                if self.hit_wait == 0:
                    # fire on the tick the frame counter reaches zero, so the
                    # effective hit time equals the calibrated OnAttack frame
                    # exactly (previously one tick late)
                    if not self._spell_on_done:
                        self._spell_on()
                    self._execute_effects()
                    if self._hit_deltas:
                        self._hit_deltas.pop(0)
                    self.hit_wait = self._hit_deltas[0] \
                        if self._hit_deltas else 0
                    if not self._hit_deltas:
                        self.phase = "post_delay"
                return
            # waitForAttackEvent=false, no calibrated hit frames, or
            # the OnAttack frame already passed inside preDelay:
            # spell_on + effects fire right after preDelay
            if not self._spell_on_done:
                self._spell_on()
            self._execute_effects()
            self.phase = "post_delay"
        elif self.phase == "post_delay":
            if self._check_target_dead():
                self._finish(FinishReason.TARGET_DEAD)
                return
            self.post_remaining -= dt
            if self.post_remaining <= 0:
                self._finish(FinishReason.NORMAL_EXIT)

    def _check_interrupt(self):
        e = self.enemy
        return e.state in (EnemyState.STUN, EnemyState.FROZEN,
                           EnemyState.LEVITATE, EnemyState.PALSY) or \
            any(e.flag(f) for f in (0, 16, 25, 39))

    def _check_target_dead(self):
        t = self.target
        return t is not None and t.dead

    def _finish(self, reason):
        self.finished = True
        if getattr(self.enemy, "_skill_target", None) is self.target:
            self.enemy._skill_target = None
        self.finish_reason = reason
        if reason == FinishReason.INTERRUPTED:
            # an interrupted cast still enters cooldown (no trigger count,
            # no SP cost) so the enemy cannot instantly recast after the
            # stun/freeze wears off
            try:
                self.skill._apply_cooldown()
            except Exception:
                pass
        if reason == FinishReason.NORMAL_EXIT:
            self.skill.on_cast_finish()
            if self.skill.reset_main_ability_cd:
                self.enemy.attack_timer = 0.0
            # BuffToOwnerDuringAbility buffs end with the cast
            if self.battle is not None:
                for sb in self.skill.self_buffs:
                    if sb.get("remove_on_end"):
                        try:
                            self.battle.buffs.remove(
                                self.enemy, sb["data"].get("buffKey"))
                        except Exception:
                            pass
        if self.battle:
            self.battle.emit(self.battle.tick, "skill_finish",
                             {"unit": self.enemy.inst_id,
                              "skill": self.skill.prefab_key,
                              "reason": reason})

    def _spell_on(self):
        """Ability spell_on: action nodes + caster self buffs.

        For waitForAttackEvent=true abilities this runs at the first
        calibrated OnAttack frame; otherwise right after preDelay.
        """
        self._spell_on_done = True
        self._execute()
        self._apply_self_buffs()

    def _execute(self):
        """Execute skill effects: damage / buff / abnormal from blackboard."""
        # run prefab action nodes (summon / branch / instant kill / blink)
        try:
            from .action_nodes import ActionNodeExecutor
            ex = ActionNodeExecutor(self.battle)
            ex.execute(ex.parse(self.skill.action_nodes),
                       source=self.enemy, target=self.target,
                       owner=self)
        except Exception:
            pass

    def _apply_self_buffs(self):
        """Apply the caster's own prefab buffs (passive / BuffToOwner)."""
        e = self.enemy
        for sb in self.skill.self_buffs:
            self._apply_buff_data(e, sb["data"])

    def _execute_effects(self):
        """Damage / buff / abnormal from blackboard + prefab fields.

        Damage type/scale/ep come from the full prefab serialisation when
        available (skill.prefab_*), falling back to blackboard values.
        """
        e = self.enemy
        bb = self.skill.blackboard
        atk = e.attributes.get("atk")
        s = self.skill
        # enemy healer: bb heal_scale -> heal up to max_target allied
        # enemies within range_radius of the caster by atk * heal_scale
        _heal_scale = bb.get("heal_scale")
        if _heal_scale is not None and float(_heal_scale) > 0:
            _rr = float(bb.get("range_radius") or 1.5)
            _mt = max(1, int(bb.get("max_target") or 1))
            _al = [u for u in self.battle.get_enemies()
                   if u is not e and not u.dead and
                   ((u.pos_x - e.pos_x) ** 2 +
                    (u.pos_y - e.pos_y) ** 2) ** 0.5 <= _rr]
            _al.sort(key=lambda u: u.hp / max(1.0, u.max_hp))
            _amt = atk * float(_heal_scale)
            for u in _al[:_mt]:
                self.battle.apply_heal(u, _amt, source=e)
            if self.battle:
                self.battle.emit(
                    self.battle.tick, "attack",
                    {"unit": e.inst_id, "skill": s.prefab_key,
                     "target": None, "heal": True})
            return
        if bb.get("atk_scale") is not None:
            scale = float(bb["atk_scale"])
        elif bb.get("atk") is not None and float(bb["atk"]) > 0 and (
                s.prefab_damage_type is not None or
                bool(getattr(s, "projectile_key", None))):
            # attack-typed skills carry the multiplier in bb "atk"
            # (Electrify 0.5 / Roar2 0.2); negative values are atk
            # debuffs, not scales
            scale = float(bb["atk"])
        else:
            # atk_scale variant keys (magic_atk_scale 3.0,
            # combat_atk_scale 2.0, atk_scale_boom 2.0 ...) are the
            # attack multiplier for skills without a plain scale key;
            # dot / namespaced debuff params are excluded
            _vscale = None
            for _k, _v in bb.items():
                if "atk_scale" not in _k or "dot" in _k or "." in _k:
                    continue
                try:
                    _f = float(_v)
                except (TypeError, ValueError):
                    continue
                if _f > 0:
                    _vscale = _f
                    break
            if _vscale is not None:
                scale = _vscale
            else:
                # prefab _atkScale fallback for real non-default values
                # (0.0 is shared-prefab merge noise; 1.0 is the default)
                scale = s.atk_scale if getattr(
                    s, "atk_scale", 1.0) != 1.0 else 1.0
        stun = bb.get("stun")
        # negative bb 'atk' is a target atk debuff (e.g.
        # AtkDesWeaken -0.5 / SandStorm -0.7 -> atk x (1+value))
        atk_debuff = 0.0
        atk_debuff_key = f"{s.prefab_key}[atk_down]"
        if bb.get("atk") is not None and float(bb["atk"]) < 0:
            atk_debuff = float(bb["atk"])
        atk_debuff_dur = float(bb.get("duration") or 1.0)
        # Only abilities carrying an attack component deal damage:
        # prefab _damageType, or blackboard atk_scale[/*]/atk/damage*
        # keys. Pure summon/branch/self-buff skills (e.g. SummonBallis,
        # Shine, StartRun) deal no damage at all.
        def _has_attack_component(bb, has_dt=False, has_proj=False):
            if bb.get("atk_scale") is not None:
                return True
            for k in bb:
                if k == "atk":
                    # bare atk is a multiplier only on attack-typed
                    # skills; on buff skills it is an atk BUFF value
                    if has_dt or has_proj:
                        return True
                    continue
                if k.startswith("atk_scale"):
                    return True
                if ("damage" in k and "resistance" not in k and
                        not k.startswith("ep_")):
                    return True
            return False
        has_damage = (s.prefab_damage_type is not None or
                      _has_attack_component(
                          bb, s.prefab_damage_type is not None,
                          bool(getattr(s, "projectile_key", None))))
        targets = [self.target] if self.target is not None else []
        # 进化的本质 蓄力击: the per-form RealAttack chain hits EVERY
        # operator (PRTS: 900/1000/1200 true damage to all), so expand the
        # effect target list beyond the single cast target.
        if getattr(self.skill, "mode_real_attack", False):
            _all_ops = [o for o in self.battle.get_operators()
                        if not o.dead and
                        not o.in_deploy_anim(self.battle.tick)]
            if _all_ops:
                targets = _all_ops
        # map-wide direct hits: range_radius >= 10 (e.g. Talulah
        # DragonFire 100 / pyczog Roar 15) hit every operator; small
        # radii need selector work (self-centred bursts, line types)
        _aoe = float(bb.get("range_radius") or 0.0)
        if self.target is not None:
            _ops = [o for o in self.battle.get_operators()
                    if not o.dead and
                    not o.in_deploy_anim(self.battle.tick)]
            if _aoe >= 10.0:
                targets = _ops
            elif _aoe > 0 and s.prefab_damage_type is not None:
                # attack-typed radial splash (Roar1 5 / CombatAoe 1.6 /
                # BigBomb 2.0 / fishing 4.0): hit all operators within
                # the effect radius of the impact point
                _tx = float(self.target.pos_x)
                _ty = float(self.target.pos_y)
                targets = [o for o in _ops
                           if ((o.pos_x - _tx) ** 2 +
                               (o.pos_y - _ty) ** 2) ** 0.5 <= _aoe]
        for t in targets:
            if t.dead:
                continue
            dt = s.prefab_damage_type if s.prefab_damage_type is not None \
                else DamageType.PHYSICAL
            if dt not in (DamageType.PHYSICAL, DamageType.MAGICAL,
                          DamageType.TRUE):
                dt = DamageType.PHYSICAL
            ep = s.ep_damage_ratio if s.ep_damage_ratio else \
                bb.get("ep_damage_ratio")
            _bb_trig = bb.get("ep_damage_ratio[trigger]")
            ep_type = translate_game_element_type(_bb_trig) \
                if _bb_trig is not None else s.element_damage_type
            # ???????????????????
            aoe = float(bb.get("range_radius") or 0.0)
            if has_damage and getattr(s, "projectile_key", None):
                battle = self.battle
                hit_cb = None
                if stun or ep or self.skill.prefab_buffs or aoe > 0:
                    sk = self.skill
                    run = self
                    def _cb(battle, proj, stun_=stun, ep_=ep,
                            ep_type_=ep_type, s=sk, r=run,
                            aoe_=aoe):
                        # projectile impact: land the base skill damage
                        # (radial splash when range_radius > 0, e.g.
                        # frost star ArcticBlast 2.5 / W C4 2.5)
                        if aoe_ > 0:
                            tx = getattr(proj.target, "pos_x", 0.0)
                            ty = getattr(proj.target, "pos_y", 0.0)
                            ts = [o for o in battle.get_operators()
                                  if not getattr(o, "dead", False) and
                                  ((getattr(o, "pos_x", 0.0) - tx) ** 2 +
                                   (getattr(o, "pos_y", 0.0) - ty) ** 2)
                                  ** 0.5 <= aoe_]
                        else:
                            ts = [proj.target]
                        for tg in ts:
                            amt = calculate_damage(
                                e.attributes.get("atk"),
                                tg.attributes, dt, atk_scale=scale)
                            battle.apply_damage(tg, amt, dt, source=e)
                            if stun_:
                                battle.add_abnormal(tg, 0, float(stun_))
                            if ep_:
                                battle.add_ep(tg, int(ep_type_),
                                              float(ep_))
                            for bd in s.prefab_buffs:
                                r._apply_buff_data(tg, bd)
                            if atk_debuff < 0 and not \
                                    battle.buffs.get(tg, atk_debuff_key):
                                _ph = any(
                                    battle.buffs.get(tg, bd.get("buffKey"))
                                    is not None
                                    for bd in s.prefab_buffs
                                    if bd.get("buffKey"))
                                if not _ph:
                                    battle.add_buff(tg, {
                                        "key": atk_debuff_key,
                                        "stat": "atk",
                                        "mul": atk_debuff,
                                        "remaining_ticks": max(
                                            1, int(atk_debuff_dur * 30)),
                                        "layers": 1, "source": e})
                    hit_cb = _cb
                battle.spawn_projectile(e, t, s.projectile_key, dt,
                                        atk_scale=scale, hit_callback=hit_cb)
                continue
            if has_damage:
                amount = calculate_damage(
                    atk, t.attributes, dt, atk_scale=scale)
                self.battle.apply_damage(t, amount, dt, source=e)
            if stun:
                self.battle.add_abnormal(t, 0, float(stun))
            if ep:
                self.battle.add_ep(t, int(ep_type), float(ep))
            for bd in self.skill.prefab_buffs:
                self._apply_buff_data(t, bd)
            if atk_debuff < 0 and not \
                    self.battle.buffs.get(t, atk_debuff_key):
                # only fall back when no prefab atk-debuff buff landed
                _prefab_hit = any(
                    self.battle.buffs.get(t, bd.get("buffKey")) is not None
                    for bd in self.skill.prefab_buffs
                    if bd.get("buffKey"))
                if _prefab_hit:
                    pass
                else:
                    self.battle.add_buff(t, {
                        "key": atk_debuff_key, "stat": "atk",
                        "mul": atk_debuff,
                        "remaining_ticks": max(
                            1, int(atk_debuff_dur * 30)),
                        "layers": 1, "source": e})
        move_speed = bb.get("move_speed")
        if move_speed:
            e.move_speed = float(move_speed)
        if self.battle:
            self.battle.emit(self.battle.tick, "attack",
                             {"unit": e.inst_id, "skill": self.skill.prefab_key,
                              "target": self.target.inst_id
                              if self.target else None})

    def _apply_buff_data(self, target, buff_data):
        """Resolve a prefab BuffData (DB merge + blackboard) and apply it."""
        battle = self.battle
        try:
            from .buff_templates import buff_definition, materialise_buff, \
                named_buff
            data = buff_data
            if data.get("loadFromDB"):
                db = buff_definition(data.get("buffKey") or "")
                if db:
                    merged = named_buff(db)
                    for k, v in data.items():
                        if v not in (None, "", 0, [], {}):
                            if k == "templateKey" and str(v).lower() in (
                                    "empty", "none"):
                                continue
                            merged[k] = v
                    data = merged
            entry = materialise_buff(battle, target, data,
                                     dict(self.skill.blackboard), self.enemy)
            if entry and entry.get("key"):
                battle.add_buff(target, entry)
        except Exception:
            pass
