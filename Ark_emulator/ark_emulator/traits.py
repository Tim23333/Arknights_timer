"""Operator trait (特性) system.

Two data sources:
1. ``characters.json`` TraitData.candidates[].blackboard holds per-character
   trait parameters (charger cost refund, merchant cost drain, slower
   sluggish, chain-caster jump, musha/reaper self-heal ...).
2. ``data_class_traits.json`` holds shared profession / subProfession
   mechanics that the client hard-codes (sniper prefers air, caster /
   supporter deal magical damage, medic heals, charger refunds cost on
   kill, merchant drains cost ...).

Emulator hooks:
- kill refund:  battle.apply_damage -> TraitSystem.kill_cost_bonus()
- cost drain:   battle._trait_tick -> TraitSystem.cost_drain()
- on-hit:       battle._trait_hit -> TraitSystem.on_hit()
- damage type:  battle._char_damage_type -> TraitSystem.damage_type()
- targeting:    targeting.HateSystem.operator_target -> prefer_air / is_healer
"""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data_class_traits.json")

# Chain casters: each jump deals 15% less than the previous hit.
_CHAIN_DECAY = 0.85

# Therapist (疗养师) inner full-heal zone: targets outside this shape are
# healed at trait heal_scale (final multiply). PRTS "无特性影响的范围"
# = range 2-3 (the standard medic E0 7-tile shape).
_HEALER_INNER_RANGE_ID = "2-3"


def _load_table():
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"profession": {}, "subprofession": {}}


def _sluggish_buff(source, seconds):
    """Buff payload matching operator_skills' sluggish application."""
    return {
        "key": "op_sluggish",
        "remaining_ticks": int(float(seconds) * 30),
        "layers": 1,
        "mul": -0.5,
        "stat": "moveSpeed",
        "source": source,
    }


class TraitSystem:
    """Runtime trait execution for one deployed operator."""

    def __init__(self, op, char_data, table=None):
        self.op = op
        self.profession = 0
        self.sub_profession = ""
        self.bb = {}
        self.description = None
        if isinstance(char_data, dict):
            self.profession = int(char_data.get("profession") or 0)
            self.sub_profession = char_data.get("subProfessionId") or ""
            cands = ((char_data.get("trait") or {}).get("candidates") or [])
            for cand in cands:
                for b in (cand.get("blackboard") or []):
                    key = b.get("key")
                    if key:
                        self.bb[key] = b.get("value")
                if cand.get("overrideDescripton"):
                    self.description = cand["overrideDescripton"]
        table = table if table is not None else _load_table()
        prof = table.get("profession", {}).get(str(self.profession)) or {}
        sub = table.get("subprofession", {}).get(self.sub_profession) or {}
        self._flags = dict(prof)
        self._flags.update(sub)
        if self.is_hunter():
            self.op._hunter_ammo = self.hunter_ammo_max()
            self.op._hunter_reloading = False
            self.op._hunter_focus = None            # Ray talent focus stacks
            self.op._hunter_next_reload_bonus = 0  # Ray S1 kill bonus
        if self.is_mystic():
            self.op._mystic_stored = 0
        if self.is_stalker():
            # 50% physical & magical dodge (bb prob): implemented as
            # defensive damage-hitrate modifiers (percent units; the
            # battle apply_damage rolls against the TARGET hitrate)
            hit = (1.0 - self.stalker_dodge_prob()) * 100.0
            if hit < 100.0:
                self.op.attributes.add_modifier(
                    "damageHitratePhysical", additive=hit,
                    key="trait_stalker_dodge")
                self.op.attributes.add_modifier(
                    "damageHitrateMagical", additive=hit,
                    key="trait_stalker_dodge")

    def apply_module_upgrades(self, upgrades, potential_rank=0):
        """Override trait blackboard values from an equipped module
        (battle_equip overrideTraitDataBundle).  The module value list
        follows the base trait candidate's blackboard key order; when the
        module lists several candidates the last one wins at potential
        rank >= 4 (mirrors apply_module_upgrades in talents.py).  Example:
        \u54c8\u6d1b\u5fb7 WDM-X \u817f\u90e8\u62a4\u7406\u5957\u88c5:
        ep_heal_ratio 0.5 -> 0.6 at module level 1+."""
        if not upgrades:
            return
        pick = upgrades[-1] if (potential_rank >= 4 and len(upgrades) > 1) \
            else upgrades[0]
        base_keys = list(self.bb.keys())
        vals = (pick or {}).get("values") or []
        for i, k in enumerate(base_keys):
            if i < len(vals) and vals[i] is not None:
                self.bb[k] = vals[i]

    # ---- shared profession / subclass mechanics ----
    def prefer_air(self):
        # bombarder (\u6295\u63b7\u624b) is ground-only despite the sniper
        # profession flag: it cannot select flying targets at all.
        if self.ground_only():
            return False
        return bool(self._flags.get("preferAir"))

    def is_healer(self):
        return bool(self._flags.get("healer"))

    def damage_type(self):
        dt = self._flags.get("damageType")
        if dt == "MAGICAL":
            from .consts import DamageType
            return DamageType.MAGICAL
        return None

    def attack_all_blocked(self):
        """Centurion / pusher trait: a basic attack hits EVERY enemy this
        operator currently blocks (PRTS: "simultaneously attack all blocked
        enemies"). The target set is snapshotted at windup and re-pruned at
        the hit frame."""
        return bool(self._flags.get("attackAllBlocked"))

    # ---- stalker (\u4f0f\u51fb\u5ba2) ----
    def is_stalker(self):
        return self.sub_profession == "stalker"

    def stalker_dodge_prob(self):
        """Physical & magical dodge chance (bb prob, default 0.5)."""
        v = self.bb.get("prob")
        return float(v) if v is not None else 0.5

    def attack_all_in_range(self):
        """Stalker trait: a basic attack hits EVERY enemy inside the
        operator attack range (PRTS: \u5bf9\u653b\u51fb\u8303\u56f4\u5185\u6240\u6709\u654c\u4eba\u9020\u6210\u4f24\u5bb3)."""
        return bool(self._flags.get("attackAllInRange"))

    # ---- hammer (\u64bc\u5730\u8005) splash ----
    def is_hammer(self):
        return self.sub_profession == "hammer"

    def hammer_splash_params(self):
        """Splash on basic attack: enemies around the target (radius in
        tiles) take atk * atk_scale_2 physical damage; main target takes
        the full hit normally."""
        return {
            "radius": float(self.bb.get("attack@ability_range_radius")
                            or 1.0),
            "scale": float(self.bb.get("attack@atk_scale_2") or 0.5),
        }

    def is_splashcaster(self):
        return self.sub_profession == "splashcaster"

    def _splash_hit(self, target, battle):
        """Basic-attack splash on the hit target tile:
        hammer (\u64bc\u5730\u8005): neighbours take atk*0.5 PHYSICAL;
        splashcaster (\u6269\u6563\u672f\u5e08): neighbours take
        atk*1.0 MAGICAL. The main target itself is resolved by the
        normal attack pipeline."""
        if target is None:
            return
        from .consts import DamageType
        if self.is_hammer():
            p = self.hammer_splash_params()
            radius, scale, dmg_type, evt = (
                p["radius"], p["scale"], DamageType.PHYSICAL,
                "hammer_splash")
        elif self.is_splashcaster():
            radius, scale, dmg_type, evt = (
                1.0, 1.0, DamageType.MAGICAL, "splashcaster_splash")
        else:
            return
        op = self.op
        atk = float(op.attributes.get("atk") or 0)
        if atk <= 0 or scale <= 0:
            return
        tr, tc = target.row, target.col
        victims = [e for e in battle.get_enemies()
                   if not e.dead and e is not target
                   and abs(e.row - tr) <= radius
                   and abs(e.col - tc) <= radius]
        if not victims:
            return
        ids = []
        total = 0.0
        for e in victims:
            amt = atk * scale
            ids.append(e.inst_id)
            total += amt
            battle.apply_damage(e, amt, dmg_type, source=op)
        battle.emit(battle.tick, "attack",
                    {"unit": op.inst_id, "target": target.inst_id,
                     "type": evt, "targets": ids,
                     "amount": round(total, 3)})

    # ---- phalanx (\u9635\u6cd5\u672f\u5e08) idle defense ----
    def is_phalanx(self):
        return self.sub_profession == "phalanx"

    def phalanx_sync(self):
        """Not attacking (no pending attack windup): DEF x2 and
        magic resistance +20 (PRTS / character blackboard)."""
        if not self.is_phalanx():
            return
        op = self.op
        attacking = getattr(op, "_pending_attack", None) is not None
        op.attributes.remove_modifier("trait_phalanx_idle")
        if not attacking:
            op.attributes.add_modifier(
                "def", multiplicative=1.0, key="trait_phalanx_idle")
            op.attributes.add_modifier(
                "magicResistance", additive=20.0, key="trait_phalanx_idle")

    # ---- liberator (\u89e3\u653e\u8005) idle ramp ----
    def is_librator(self):
        return self.sub_profession == "librator"

    def librator_sync(self, skill_active, dt):
        """Idle (no active skill): blockCnt=0 and no basic attack; ATK ramps
        linearly to +atk% over max_stack_cnt seconds. While a skill is
        active the ramped ATK freezes and blocking/attacking resume; when
        the skill ends the ramp resets to 0 (PRTS / character blackboard)."""
        if not self.is_librator():
            return
        op = self.op
        max_ramp = float(self.bb.get("max_stack_cnt") or 40.0)
        atk_bonus = float(self.bb.get("atk") or 0.0)
        base_atk = float(op.attributes.base.get("atk") or 0.0)
        base_block = float(op.attributes.base.get("blockCnt") or 0.0)
        was = bool(getattr(self, "_librator_skill_active", False))
        if skill_active:
            if not was:
                op.attributes.remove_modifier("trait_librator_idle")
            ramp = float(getattr(self, "_librator_ramp", 0.0))
        else:
            if was:
                self._librator_ramp = 0.0
            ramp = min(max_ramp, float(getattr(self, "_librator_ramp", 0.0))
                       + dt)
            self._librator_ramp = ramp
            op.attributes.remove_modifier("trait_librator_ramp")
            # Attributes.add_modifier skips zero values, so zero out
            # blockCnt with an additive -base instead of final_mul 0.
            op.attributes.add_modifier(
                "blockCnt", additive=-base_block,
                key="trait_librator_idle")
        self._librator_skill_active = bool(skill_active)
        frac = min(1.0, ramp / max_ramp) if max_ramp > 0 else 0.0
        op.attributes.remove_modifier("trait_librator_ramp")
        if frac > 0 and base_atk > 0:
            op.attributes.add_modifier(
                "atk", additive=base_atk * atk_bonus * frac,
                key="trait_librator_ramp")

    # ---- bard (吟游者) heal aura ----
    def is_bard(self):
        return self.sub_profession == "bard"

    def bard_aura_ratio(self):
        """HP per second per ATK (bb atk_to_hp_recovery_ratio,
        default 10%)."""
        v = self.bb.get("atk_to_hp_recovery_ratio")
        return float(v) if v else 0.1

    def bard_aura_sync(self, battle):
        """Bard trait: never attacks; every friendly unit inside this
        operator range gains hpRecoveryPerSec = atk * ratio. PRTS:
        the trait raises the beneficiary HP-recovery-speed attribute,
        so it is not a heal action and bypasses heal-free. Modifiers
        are added/removed as units enter/leave range and refreshed
        when the bard ATK changes."""
        if not self.is_bard():
            return
        op = self.op
        ratio = self.bard_aura_ratio()
        amt = float(op.attributes.get("atk") or 0.0) * ratio
        if ratio <= 0 or not op.range_shape:
            targets = []
        else:
            targets = [u for u in (list(battle.get_operators()) +
                                   list(battle.get_tokens()))
                       if not u.dead and any(
                           (op.row + dr, op.col + dc) == (u.row, u.col)
                           for dr, dc in op.range_shape)]
        key = "trait_bard_aura:%d" % op.inst_id
        applied = getattr(self, "_bard_aura_applied", {})
        new_applied = {}
        for u in targets:
            prev = applied.get(u.inst_id)
            if prev is None:
                u.attributes.add_modifier(
                    "hpRecoveryPerSec", additive=amt, key=key)
                new_applied[u.inst_id] = (u, amt)
            elif abs(prev[1] - amt) > 1e-9:
                u.attributes.remove_modifier(key)
                u.attributes.add_modifier(
                    "hpRecoveryPerSec", additive=amt, key=key)
                new_applied[u.inst_id] = (u, amt)
            else:
                new_applied[u.inst_id] = prev
        for tid, (u, _amt) in applied.items():
            if tid not in new_applied:
                u.attributes.remove_modifier(key)
        self._bard_aura_applied = new_applied

    # ---- mystic (秘术师) stored attacks ----
    def is_mystic(self):
        return self.sub_profession == "mystic"

    def mystic_max_times(self):
        """Max stored attack charges (bb `times`, default 3)."""
        v = self.bb.get("times")
        return max(1, int(float(v))) if v else 3

    def mystic_merge_cnt(self):
        """Charges merged into one stronger hit (bb `merge_cnt`,
        default 1 = each charge hits separately; ?? uses 3)."""
        v = self.bb.get("merge_cnt")
        return max(1, int(float(v))) if v else 1

    def mystic_attack_tick(self, target, interval, battle):
        """Mystic stored-attack trait: with no target in range the
        operator stores one charge per normal attack interval (up to
        `times`; PRTS: storage occupies the normal interval, at full
        capacity it idles). When a target appears, the current attack
        plus every stored charge are released together at full ATK;
        merge_cnt charges merge into a single stronger hit."""
        if not self.is_mystic():
            return
        op = self.op
        max_times = self.mystic_max_times()
        merge = self.mystic_merge_cnt()
        stored = int(getattr(op, "_mystic_stored", 0) or 0)
        # the shared target selector may fall back to an
        # out-of-range enemy; storage must only release for a
        # target that is actually inside the operator range
        if target is not None and not any(
                (op.row + dr, op.col + dc) == (target.row, target.col)
                for dr, dc in (op.range_shape or [])):
            target = None
        if target is None:
            if stored < max_times:
                op._mystic_stored = stored + 1
                op.attack_timer = interval
            else:
                op.attack_timer = 0.1
            return
        scales = [1.0]
        rem = stored
        if merge > 1:
            while rem > 0:
                g = min(merge, rem)
                scales.append(float(g))
                rem -= g
        else:
            scales.extend([1.0] * stored)
        op._mystic_stored = 0
        battle._operator_attack(op, target, interval,
                                hits=len(scales),
                                hit_scales=scales)

    # ---- blessing (\u62a4\u4f51\u8005) attack -> heal mode ----
    def is_blessing(self):
        return self.sub_profession == "blessing"

    def heal_while_skill(self):
        """While a skill is active the basic attack turns into a
        heal on the most wounded friendly in range (PRTS trait)."""
        return bool(self._flags.get("healWhileSkill"))

    def blessing_heal_scale(self):
        """Heal amount per ATK (bb heal_scale, default 0.75)."""
        v = self.bb.get("heal_scale")
        return float(v) if v is not None else 0.75

    def bard_aura_clear(self):
        """Remove every hpRecoveryPerSec modifier this bard
        applied. Called on retreat/removal: the per-tick sync
        can no longer run once the operator leaves the field."""
        applied = getattr(self, "_bard_aura_applied", {})
        if not applied:
            return
        key = "trait_bard_aura:%d" % self.op.inst_id
        for _tid, (u, _amt) in applied.items():
            u.attributes.remove_modifier(key)
        self._bard_aura_applied = {}

    # ---- per-character trait parameters ----
    def kill_cost_bonus(self):
        """Charger: 击杀敌人后额外回复部署费用 (bb key 'cost')."""
        v = self.bb.get("cost")
        return float(v) if v and float(v) > 0 else 0.0

    def cost_drain(self):
        """Merchant: 每 interval 秒消耗 |cost| 点部署费用（不足自动撤退）。"""
        interval = self.bb.get("interval")
        cost = self.bb.get("cost")
        if interval is None or cost is None or float(cost) >= 0:
            return None
        return (float(interval), -float(cost))

    def hit_sluggish(self):
        """Slower / chain: attack applies 停顿 for this many seconds."""
        for key in ("sluggish", "attack@sluggish"):
            v = self.bb.get(key)
            if v:
                return float(v)
        return 0.0

    def hit_self_heal(self):
        """Musha / reaper: 每次攻击到敌人后回复自身生命 (bb key 'value')."""
        if not self._flags.get("hitSelfHeal"):
            return 0.0
        v = self.bb.get("value")
        return float(v) if v else 0.0

    def chain_max_target(self):
        """Chain-attack jump count: trait bb attack@chain.max_target, with
        the active skill's attack@chain.max_target taking precedence."""
        for key in ("attack@max_target", "attack@chain.max_target"):
            v = self.bb.get(key)
            if v and float(v) > 1:
                return int(float(v))
        act = getattr(getattr(self.op, "skill_controller", None),
                      "active", None)
        ae = (getattr(act, "attack_effects", None) or {}) if act else {}
        v = ae.get("chain.max_target")
        if v and float(v) > 1:
            return int(float(v))
        return 1

    # ---- hunter (hunter subclass) ammo / reload ----
    def is_hunter(self):
        return self.sub_profession == "hunter"

    def hunter_ammo_max(self):
        """Max bullets: trait blackboard 'value' (4/6/8 by elite phase)."""
        v = self.bb.get("value")
        return int(float(v)) if v else 0

    def hunter_atk_scale(self):
        """Hunter trait: attacks deal 120% ATK while a bullet is loaded.
        An active skill's attack@atk_scale overrides it (Ray S3)."""
        op = self.op
        sc = getattr(op, "skill_controller", None)
        if sc is not None and getattr(sc, "active", None) is not None:
            bb = getattr(getattr(sc.active, "skill", None),
                         "blackboard", None) or {}
            try:
                v = bb.get("attack@atk_scale")
                if v:
                    return float(v)
            except (TypeError, ValueError):
                pass
        v = self.bb.get("atk_scale")
        return float(v) if v else 1.0

    def hunter_focus_multiplier(self, target):
        """Ray talent 2 \u5165\u795e: attacking the same target stacks
        +atk% per hit (max max_stack_cnt); switching target resets to 1."""
        if target is None:
            return 1.0
        op = self.op
        ts = getattr(op, "talent_system", None)
        if ts is None or ts.bb("max_stack_cnt") is None:
            return 1.0
        atk_pct = float(ts.bb("atk") or 0.0)
        max_stack = max(1, int(float(ts.bb("max_stack_cnt") or 1.0)))
        focus = getattr(op, "_hunter_focus", None)
        if focus is None or focus.get("target") != target.inst_id:
            stacks = 1
        else:
            stacks = min(max_stack, int(focus.get("stacks", 1)) + 1)
        op._hunter_focus = {"target": target.inst_id, "stacks": stacks}
        return 1.0 + atk_pct * stacks

    def hunter_reload_interval(self):
        """Reload interval = base attack interval + active skill modifier
        (PRTS: reload interval defaults to the base attack interval and is
        not affected by attack speed)."""
        op = self.op
        base = float(op.attributes.get("baseAttackTime") or 1.6)
        mod = 0.0
        sc = getattr(op, "skill_controller", None)
        if sc is not None and getattr(sc, "active", None) is not None:
            bb = getattr(getattr(sc.active, "skill", None),
                         "blackboard", None) or {}
            try:
                mod = float(bb.get("reload_interval") or 0.0)
            except (TypeError, ValueError):
                mod = 0.0
        return max(0.05, base + mod)

    def hunter_tick(self, target, interval, battle):
        """One attack-timer expiry for a hunter operator: fire (consume a
        bullet) or perform/complete a reload action."""
        op = self.op
        ammo = getattr(op, "_hunter_ammo", 0)
        max_ammo = self.hunter_ammo_max()
        atk_scale = self.hunter_atk_scale()
        if getattr(op, "_hunter_reloading", False):
            # reload action finished -> gain one bullet (+ Ray S1 bonus)
            op._hunter_reloading = False
            bonus = int(getattr(op, "_hunter_next_reload_bonus", 0) or 0)
            ammo = min(max_ammo, ammo + 1 + bonus)
            op._hunter_next_reload_bonus = 0
            op._hunter_ammo = ammo
            battle.emit(battle.tick, "hunter_reload",
                        {"unit": op.inst_id, "ammo": ammo})
            if target is not None and ammo > 0:
                op._hunter_ammo = ammo - 1
                battle.emit(battle.tick, "hunter_attack",
                            {"unit": op.inst_id, "ammo": ammo - 1})
                battle._operator_attack(
                    op, target, interval,
                    atk_scale=atk_scale *
                    self.hunter_focus_multiplier(target))
                return
            if ammo < max_ammo:
                op._hunter_reloading = True
                op.attack_timer = self.hunter_reload_interval()
                battle.emit(battle.tick, "hunter_reload_start",
                            {"unit": op.inst_id})
                return
            op.attack_timer = 0.1
            return
        if ammo <= 0:
            # out of bullets: reload even while a target exists
            op._hunter_reloading = True
            op.attack_timer = self.hunter_reload_interval()
            battle.emit(battle.tick, "hunter_reload_start",
                        {"unit": op.inst_id})
            return
        if target is None:
            if ammo < max_ammo:
                op._hunter_reloading = True
                op.attack_timer = self.hunter_reload_interval()
                battle.emit(battle.tick, "hunter_reload_start",
                            {"unit": op.inst_id})
                return
            op.attack_timer = 0.1
            return
        # fire: consume one bullet, deal atk * atk_scale * focus stacks
        op._hunter_ammo = ammo - 1
        battle.emit(battle.tick, "hunter_attack",
                    {"unit": op.inst_id, "ammo": ammo - 1})
        battle._operator_attack(
            op, target, interval,
            atk_scale=atk_scale * self.hunter_focus_multiplier(target))

    # ---- medic subclasses: incantationmedic / chainhealer ----
    def incant_heal_scale(self):
        """???: ??????????????????? atk*scale."""
        if self.sub_profession != "incantationmedic":
            return 0.0
        v = self.bb.get("scale")
        return float(v) if v else 0.0

    def chain_heal_params(self):
        """Chain-healer jump params: (max_target, scale).  Base values
        come from the trait blackboard (attack@chain.max_target 3 /
        attack@chain.atk_scale 0.75); an active skill can replace the jump
        count (attack@chain.max_target) or add extra jumps
        (attack@chain.extra_value, e.g. 莎草 S2 / 明椒 S2 / 乌啾 S1 /
        Mon3tr S1 "每次治疗的跳跃次数+X")."""
        if not self._flags.get("chainHeal"):
            return None
        max_target = 3
        scale = 0.75
        for key in ("attack@chain.max_target", "chain.max_target"):
            v = self.bb.get(key)
            if v:
                max_target = int(float(v))
        for key in ("attack@chain.atk_scale", "chain.atk_scale"):
            v = self.bb.get(key)
            if v:
                scale = float(v)
        act = getattr(getattr(self.op, "skill_controller", None),
                      "active", None)
        ae = (getattr(act, "attack_effects", None) or {}) if act else {}
        for key in ("chain.max_target", "attack@chain.max_target"):
            v = ae.get(key)
            if v:
                max_target = int(float(v))
        ev = ae.get("chain.extra_value")
        if ev:
            max_target += int(float(ev))
        return (max_target, scale)

    # ---- wandermedic (\u884c\u533b) ----
    def is_wandermedic(self):
        return bool(self._flags.get("elementHeal")) or \
            self.sub_profession == "wandermedic"

    def ep_heal_ratio(self):
        """Trait bb ep_heal_ratio (0.5 base; module upgrades to 0.6)."""
        if not self.is_wandermedic():
            return 0.0
        v = self.bb.get("ep_heal_ratio")
        return float(v) if v else 0.0

    def ep_heal_amount(self):
        """Element damage recovered per heal action = ATK x trait ratio."""
        return float(self.op.attributes.get("atk") or 0.0) * \
            self.ep_heal_ratio()

    def heal_falloff_scale(self, target, battle):
        """疗养师: 治疗同部署方向 2-3 内圈之外的目标时, 治疗量最终乘
        heal_scale (0.8); 内圈（PRTS 无特性影响范围 2-3）全额."""
        if self.sub_profession != "healer" or target is None:
            return 1.0
        scale = self.bb.get("heal_scale")
        if scale is None or float(scale) >= 1.0:
            return 1.0
        op = self.op
        try:
            from .battle import range_offsets_rotated
            inner = range_offsets_rotated(
                _HEALER_INNER_RANGE_ID, getattr(op, "direction", 1))
        except Exception:
            return 1.0
        if not inner:
            return 1.0
        if any((op.row + dr, op.col + dc) == (target.row, target.col)
               for dr, dc in inner):
            return 1.0
        return float(scale)

    def _wounded_ally(self, battle):
        """Lowest hp-ratio ally in this operator's range (wounded)."""
        op = self.op
        allies = [u for u in (list(battle.get_operators()) +
                              list(battle.get_tokens()))
                  if not u.dead and u.hp < u.max_hp - 0.01
                  and op.range_shape and any(
                      (op.row + dr, op.col + dc) == (u.row, u.col)
                      for dr, dc in op.range_shape)]
        if not allies:
            return None
        allies.sort(key=lambda u: u.hp / max(u.max_hp, 1e-9))
        return allies[0]

    def _chain_heal_jump(self, battle, primary):
        """???: after the primary heal, jump to further wounded allies
        in range; each jump heals atk * scale^n."""
        params = self.chain_heal_params()
        if params is None or primary is None:
            return
        max_target, scale = params
        if max_target <= 1:
            return
        op = self.op
        base = float(op.attributes.get("atk") or 0)
        hit = {primary.inst_id}
        prev = primary
        for jump in range(1, max_target):
            cands = [u for u in (list(battle.get_operators()) +
                                 list(battle.get_tokens()))
                     if not u.dead and u.inst_id not in hit
                     and u.hp < u.max_hp - 0.01
                     and op.range_shape and any(
                         (op.row + dr, op.col + dc) == (u.row, u.col)
                         for dr, dc in op.range_shape)]
            if not cands:
                break
            cands.sort(key=lambda u: (abs(u.row - prev.row) +
                                      abs(u.col - prev.col)))
            nxt = cands[0]
            hit.add(nxt.inst_id)
            battle.apply_heal(nxt, base * (scale ** jump), source=op)
            prev = nxt

    # ---- instructor / lord attack multiplier ----
    def atk_scale(self, ranged=False):
        """Trait-level basic-attack multiplier.

        instructor (\u6559\u5b98): attacks deal x1.2 (bb `atk_scale`, PRTS).
        lord (\u9886\u4e3b): ranged basic attacks deal x0.8 (melee stays x1.0).
        """
        if self.sub_profession in ("instructor", "lord"):
            if self.sub_profession == "lord" and not ranged:
                return 1.0
            v = self.bb.get("atk_scale")
            return float(v) if v else 1.0
        return 1.0

    # ---- bombarder (\u6295\u63b7\u624b) aftershock ----
    def is_bombarder(self):
        return self.sub_profession == "bombarder"

    def ground_only(self):
        """Bombarders can only select ground enemies as attack targets."""
        return bool(self._flags.get("groundOnly"))

    def bombarder_append_atk_scale(self):
        """Aftershock damage = ATK * append_atk_scale (0.5 by default)."""
        v = self.bb.get("attack@append_atk_scale")
        return float(v) if v else 0.5

    def bombarder_aftershock_count(self):
        """Number of aftershock waves per basic attack.

        Base: 1 (main + 1 aftershock = 2 damage rounds, PRTS).
        `attack@times` stores the TOTAL rounds for an operator (Rosmontis
        times=2 -> 1 aftershock); `attack@enable_third_attack` (Wis'adel)
        -> 2 aftershocks (3 rounds).
        """
        if not self.is_bombarder():
            return 0
        if self.bb.get("attack@times") is not None:
            return max(1, int(float(self.bb["attack@times"])) - 1)
        if "attack@enable_third_attack" in self.bb:
            return 2
        return 1

    def _bombarder_aftershock(self, target, battle):
        """After a basic attack lands, deal append_atk_scale x ATK physical
        damage to every GROUND enemy in the 3x3 splash area around the
        target (splash radius 0.9), repeating for each aftershock wave.
        The primary target is inside the splash area (PRTS: \u653b\u51fb\u548c\u4f59\u9707
        are separate damage rounds)."""
        if not self.is_bombarder() or target is None:
            return
        from .consts import DamageType
        op = self.op
        atk = float(op.attributes.get("atk") or 0)
        scale = self.bombarder_append_atk_scale()
        waves = self.bombarder_aftershock_count()
        if atk <= 0 or waves <= 0 or scale <= 0:
            return
        tr, tc = target.row, target.col
        ids = []
        total = 0.0
        for _ in range(waves):
            victims = [e for e in battle.get_enemies()
                       if not e.dead
                       and not getattr(e, "is_flying", False)
                       and abs(e.row - tr) <= 1 and abs(e.col - tc) <= 1]
            for e in victims:
                amt = atk * scale
                ids.append(e.inst_id)
                total += amt
                battle.apply_damage(e, amt, DamageType.PHYSICAL, source=op)
        battle.emit(battle.tick, "attack",
                    {"unit": op.inst_id, "target": target.inst_id,
                     "type": "aftershock", "waves": waves,
                     "atkScale": round(scale, 4),
                     "targets": ids, "amount": round(total, 3)})

    # ---- funnel (\u9a6b\u68b0\u672f\u5e08) floating drones ----
    def is_funnel(self):
        return self.sub_profession == "funnel"

    def funnel_params(self):
        """Drone damage ramp: first hit init x ATK, +delta per consecutive
        hit on the same target, capped at max (max_stack_cnt increments)."""
        bb = self.bb
        return {
            "init": float(bb.get("init_atk_scale") or 0.2),
            "delta": float(bb.get("delta_atk_scale") or 0.15),
            "max": float(bb.get("max_atk_scale") or 1.1),
            "max_stack": max(1, int(float(bb.get("max_stack_cnt") or 6))),
        }

    def funnel_drone_count(self, skill_bb=None):
        """Number of floating drones: base 1 + active skill attack@cnt
        (Goldenglow S1/S2 +1, S3 +2)."""
        base = 1
        extra = 0
        if skill_bb:
            v = skill_bb.get("attack@cnt")
            if v:
                try:
                    extra += int(float(v))
                except (TypeError, ValueError):
                    pass
        return max(1, base + extra)

    # ---- runtime hooks ----
    def on_hit(self, target, battle):
        """Apply trait effects when a basic attack lands on ``target``."""
        if target is None or getattr(target, "dead", False):
            return
        sluggish = self.hit_sluggish()
        if sluggish:
            battle.add_buff(target, _sluggish_buff(self.op, sluggish))
        heal = self.hit_self_heal()
        if heal and not self.op.dead and self.op.hp < self.op.max_hp:
            battle.apply_heal(self.op, float(heal), source=self.op)
        # incantationmedic (???): heal one ally in range on every hit
        incant = self.incant_heal_scale()
        if incant and not self.op.dead:
            ally = self._wounded_ally(battle)
            if ally is not None:
                atk = float(self.op.attributes.get("atk") or 0)
                battle.apply_heal(ally, atk * incant, source=self.op)
        if self._flags.get("chainHit"):
            self._chain_jump(target, battle)
        if self._flags.get("chainHeal"):
            self._chain_heal_jump(battle, target)
        if self.is_bombarder():
            self._bombarder_aftershock(target, battle)
        if self.is_hammer() or self.is_splashcaster():
            self._splash_hit(target, battle)

    def _chain_jump(self, target, battle):
        """Chain caster trait: attack jumps to up to max_target-1 additional
        enemies in range; each jump deals 85% of the previous hit."""
        max_target = self.chain_max_target()
        if max_target <= 1:
            return
        from .consts import DamageType
        op = self.op
        base = float(op.attributes.get("atk") or 0)
        sluggish = self.hit_sluggish()
        hit_ids = {target.inst_id}
        prev = target
        for jump in range(1, max_target):
            cands = [e for e in battle.get_enemies()
                     if not e.dead and e.inst_id not in hit_ids
                     and any((op.row + dr, op.col + dc) == (e.row, e.col)
                             for dr, dc in op.range_shape)]
            if not cands:
                break
            cands.sort(key=lambda e: (abs(e.row - prev.row) +
                                      abs(e.col - prev.col)))
            nxt = cands[0]
            hit_ids.add(nxt.inst_id)
            battle.apply_damage(nxt, base * (_CHAIN_DECAY ** jump),
                                DamageType.MAGICAL, source=op)
            if sluggish:
                battle.add_buff(nxt, _sluggish_buff(op, sluggish))
            prev = nxt

    # ---- dollkeeper (\u5080\u5121\u5e08) substitute form ----
    def is_dollkeeper(self):
        return self.sub_profession == "dollkeeper"

    def doll_duration(self):
        """Substitute duration in seconds (bb duration, default 20)."""
        v = self.bb.get("duration")
        return float(v) if v is not None else 20.0

    # ---- reaperrange (\u6536\u5272\u8005\uff08\u8fdc\uff09) all-range + front row ----
    def is_reaperrange(self):
        return self.sub_profession == "reaperrange"

    def reaperrange_atk_scale(self):
        """Front-row damage multiplier (bb atk_scale, default 1.5 = 150%)."""
        v = self.bb.get("atk_scale")
        return float(v) if v is not None else 1.5

    def reaperrange_front_row(self, target):
        """PRTS: \u5bf9\u81ea\u5df1\u524d\u65b9\u4e00\u6a2a\u6392\u7684\u654c\u4eba\u653b\u51fb\u529b\u63d0\u5347\u81f3150%.
        The strip directly ahead of the operator in its facing direction."""
        if target is None:
            return False
        op = self.op
        dr, dc = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}.get(
            int(getattr(op, "direction", 1) or 1), (0, 1))
        if dc:
            return target.row == op.row and (target.col - op.col) * dc > 0
        return target.col == op.col and (target.row - op.row) * dr > 0

    # ---- geek (\u602a\u6770) HP drain ----
    def is_geek(self):
        return self.sub_profession == "geek"

    def geek_drain_ratio(self):
        """HP drained per second as a maxHp ratio (bb hp_ratio, default 1%)."""
        v = self.bb.get("hp_ratio")
        return float(v) if v is not None else 0.01

    # ---- unyield (\u4e0d\u5c48\u8005) cannot be healed by allies ----
    def is_unyield(self):
        return self.sub_profession == "unyield"

    # ---- fortress (\u8981\u585e) ranged splash / melee ----
    def is_fortress(self):
        return self.sub_profession == "fortress"

    def fortress_splash_radius(self):
        """Ranged splash radius in tiles (PRTS: 1.0 = the 3x3 block around
        the target tile)."""
        v = self.bb.get("attack@ability_range_radius")
        return float(v) if v is not None else 1.0

    def to_dict(self):
        d = {
            "profession": self.profession,
            "subProfession": self.sub_profession,
            "description": self.description,
            "blackboard": dict(self.bb),
            "flags": dict(self._flags),
        }
        if self.is_hunter():
            d["hunter"] = {
                "ammo": getattr(self.op, "_hunter_ammo", 0),
                "maxAmmo": self.hunter_ammo_max(),
                "atkScale": self.hunter_atk_scale(),
                "reloading": bool(getattr(self.op, "_hunter_reloading",
                                          False)),
                "reloadInterval": round(self.hunter_reload_interval(), 3),
            }
        if self.sub_profession == "healer":
            scale = self.bb.get("heal_scale")
            d["healFalloff"] = {
                "innerRange": _HEALER_INNER_RANGE_ID,
                "scale": float(scale) if scale else 1.0,
            }
        if self.sub_profession == "instructor":
            d["atkScale"] = self.atk_scale()
        if self.is_bombarder():
            d["aftershock"] = {
                "count": self.bombarder_aftershock_count(),
                "appendAtkScale": self.bombarder_append_atk_scale(),
                "splashRadius": 0.9,
                "groundOnly": True,
            }
        if self.is_funnel():
            d["funnel"] = self.funnel_params()
        if self.is_hammer():
            d["hammerSplash"] = self.hammer_splash_params()
        if self.is_phalanx():
            d["phalanxIdleDef"] = {"defMul": 2.0, "magicResistanceAdd": 20.0}
        if self.is_librator():
            d["liberator"] = {
                "rampSeconds": round(
                    float(getattr(self, "_librator_ramp", 0.0)), 3),
                "maxRampSeconds": float(self.bb.get("max_stack_cnt") or 40.0),
                "atkBonus": float(self.bb.get("atk") or 0.0),
                "skillActive": bool(
                    getattr(self, "_librator_skill_active", False)),
            }
        return d
