"""Operator skill system (my-side SP + activation + effects).

Game mechanics (MECHANICS §4.1), aligned with PRTS + local skills.json:
  spType is a bitmask (dump.cs Torappu.SpType):
    NONE=0 / INCREASE_WITH_TIME=1 / INCREASE_WHEN_ATTACK=2 /
    INCREASE_WHEN_TAKEN_DAMAGE=4 / ATTACK_OR_DAMAGE=6 / ALL=7.
    spType=8 marks deploy-triggered "no SP" skills (old
    SpTypeIndex.NEVER_USE): they fire once on deploy and have no SP bar
    (e.g. Skadi S2 / Gravel S1 / Red S1).
  - auto recovery runs on a hidden cooldown slot of 1/increment seconds;
    +1 SP when the slot completes; the slot pauses while blocked
    (SP_RECOVER_STOPPED / a SP skill is active / SP is full) and keeps
    its remaining time.
  - attack/hit recovery is a flat +1 per event (bitmask test), so
    spType 6/7 match both attack and damage.
  - while a SP skill is active the operator is SP-blocked (zuhui).
  - charging: maxSp = spCost * maxChargeTime (per charge).
  - ammo skills (durationType=AMMO): normal attacks consume 1 ammo,
    the skill ends when ammo is exhausted.
  - swordmaster (subProfessionId == "sword") innate double attacks
    only grant +1 SP total (PRTS exception).
"""

import math

from .consts import (
    AbnormalFlag,
    DamageType,
    PULL_FRONT_OFFSET,
    PULL_STOP_RADIUS,
    PUSH_ANGLE_CORRECTION,
    PUSH_CORRECTED_LEVEL_DELTA,
    PUSH_DIST_CORRECTION,
    force_level_from,
    pull_displacement,
    pull_duration,
    pull_pulled_home,
    push_displacement,
    push_duration,
    translate_game_element_type,
)
from .damage import calculate_damage

# operator facing: 0=up 1=right 2=down 3=left (row increases downward)
_DIR_VECTORS = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}

# Swordmaster (jianhao) branch innate attacks hit twice but only grant +1 SP
# per attack action (PRTS exception to "combo hits each give SP").
SWORDMASTER_SUB_PROFESSION = "sword"


def _unit_is_swordmaster(op):
    spid = getattr(op, "sub_profession_id", None)
    if spid is None:
        try:
            spid = op.attributes.get("subProfessionId")
        except Exception:
            spid = None
    return spid == SWORDMASTER_SUB_PROFESSION

import io as _io
import json as _json
import os as _os

_OP_BUFFS = None
_PREFAB_STORE = None


def _operator_prefab_buffs(skill_id):
    """Buff entries bound to a skill via its prefab GameObject.

    Returns [(component_class, field, buff_dict, component), ...].
    Semantics by component class / field (extracted from [uc]skills CAB):
      - Ability/AbilityStandard._buffs ......... owner self-buffs
      - any._passiveBuffs ...................... owner passive buffs
      - BuffAbility._buffs / any._activeBuffs .. target buffs
    The component dict carries `_runActionOnEvent` so cast-end buffs
    (ON_CAST_END / ON_SPELL_END) can be deferred to skill finish.
    Falls back to the small curated data_operator_skill_buffs.json.
    """
    global _OP_BUFFS, _PREFAB_STORE
    out = []
    comps = _operator_prefab_components(skill_id)
    for c in comps:
        ccls = c.get("class", "")
        for fk in ("_buffs", "_activeBuffs", "_passiveBuffs"):
            for b in (c.get(fk) or []):
                if isinstance(b, dict) and b.get("buffKey"):
                    out.append((ccls, fk, b, c))
    if out:
        return out
    if _OP_BUFFS is None:
        _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "data_operator_skill_buffs.json")
        try:
            with _io.open(_p, encoding="utf-8") as f:
                _OP_BUFFS = _json.load(f)
        except Exception:
            _OP_BUFFS = {}
    return [("legacy", "_buffs", bd, {}) for bd in
            (_OP_BUFFS.get(skill_id) or [])]


def _buff_has_cost_action(bd):
    """True when a buff's template contains a ModifyCost action."""
    for ev in _buff_template_actions(bd).values():
        for a in (ev or []):
            if "ModifyCost" in (a.get("$type") or ""):
                return True
    return False


def _buff_has_heal_action(bd):
    """True when a buff's template contains heal-type action nodes."""
    for ev in _buff_template_actions(bd).values():
        for a in (ev or []):
            cls = a.get("$type") or ""
            if "Heal" in cls or "ElementHeal" in cls or "RestoreHp" in cls:
                return True
    return False


import re as _re


def _projectile_belongs(skill_id, key):
    """A projectile key names its owner in `chr_<code>` form (e.g.
    projectile_chr_texas2_s3_sword_rain). Reject keys that carry a foreign
    character code (shared sub-ability from another operator), but accept
    generic keys (projectile_sword_rain / projectile_crossbow ...)."""
    if not key:
        return False
    m = _re.search(r"chr_([a-z0-9]+)_", key)
    if not m:
        return True
    parts = (skill_id or "").split("_")
    code = parts[1] if len(parts) > 1 else ""
    return bool(code) and m.group(1) == code


# CompositeAbility sub-ability PPtrs are NOT followed by the extractor
# summary, so skills whose projectile Ability lives on a referenced
# sub-ability GameObject are injected here with data resolved directly
# from the [uc]skills CAB (e.g. tinman S2: _abilityConfigs ->
# projectile_chr_tinman_s2 carrying tinman_s_2[buff]).
_COMPOSITE_PROJECTILE_OVERRIDES = {
    "skchr_tinman_2": {
        "_projectileKey": "projectile_chr_tinman_s2",
        "_activeBuffs": [{
            "buffKey": "tinman_s_2[buff]",
            "templateKey": "tinman_s_2[buff]",
            "loadFromDB": 0,
            "isDurableBuff": 0,
            "isDamageMissable": 0,
            "isSilenceable": 0,
            "isStunnable": 0,
            "isFreezable": 0,
            "isLevitatable": 0,
            "isGroundBoundable": 0,
            "statusResistable": 2,
            "disableOverride": 1,
            "maxStackCnt": 1,
            "lifeTimeType": 2,
            "durationKey": "duration",
            "attributes": {
                "abnormalFlags": [], "abnormalImmunes": [],
                "abnormalAntis": [], "abnormalCombos": [],
                "abnormalComboImmunes": [], "attributeModifiers": [],
            },
        }],
    },
}


# Multi-target heal skills whose target count only lives in the skill
# description / prefab config (no attack@max_target blackboard key).
# \u871c\u8393 S1 \u7cbe\u795e\u62a4\u7406: "\u4e0b\u6b21\u6cbb\u7597\u4ee5\u5143\u7d20
# \u635f\u4f24\u6700\u4e25\u91cd\u76842\u540d\u5e72\u5458\u4e3a\u76ee\u6807";
# \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S1 \u65e0\u58f0\u6da6\u7269: "\u6bcf\u6b21\u53ef\u989d
# \u5916\u6cbb\u7597\u4e00\u540d\u5355\u4f4d" (+1 target).
_HEAL_MULTI_TARGET = {
    "skchr_glider_1": 2,
    "skchr_agoat2_1": 2,
}


# Multi-shot heal skills: each heal action fires N sequential shots, each
# shot re-picking the top not-yet-selected ally (cycling back through the
# priority order when there are fewer candidates than shots).
# \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S3 \u706b\u5c71\u56de\u97ff:
# "\u6cbb\u7597\u53d8\u4e3a{attack@heal_scale}\u6cbb\u7597\u91cf...\u7684 5 \u8fde\u53d1"
# (attack@heal_scale = 0.25 at rank 1).
_HEAL_SHOT_COUNT = {
    "skchr_agoat2_3": 5,
}


# Element types named by the skill description's 元素损伤 tag
# (神经/侵蚀/灼燃/凋亡 -> 0/1/2/3).  The description is authoritative for
# operator skills: prefab `_elementDamageType` is often absent (kaitou /
# warmy / nymph prefabs carry only the FSM buff), while the game text
# always names the element, e.g. <$ba.dt.apoptosis2>凋亡损伤</>.
_EP_DESC_TYPES = (
    ("神经损伤", 0),
    ("侵蚀损伤", 1),
    ("灼燃损伤", 2),
    ("凋亡损伤", 3),
)


def _ep_type_from_desc(desc):
    """Element type (0=neural 1=water 2=fire 3=dark) named by a skill
    description, or None when it names no 元素损伤."""
    d = desc or ""
    for name, t in _EP_DESC_TYPES:
        if name in d:
            return t
    return None


def _operator_prefab_components(skill_id):
    """Runtime prefab components for a skill, resolving MainSkill
    overridePrefabKey (token skills like sktok_phatm2_mndclv_3 use
    sktok_empty)."""
    try:
        if _PREFAB_STORE is None:
            from .loader import DataStore
            globals()['_PREFAB_STORE'] = DataStore()
        return _PREFAB_STORE.operator_prefab_for_skill(skill_id or "")
    except Exception:
        return []


def _operator_prefab_params(skill_id):
    """Merge damage/projectile params from the skill's prefab components.

    The first Ability/AbilityStandard/AttackAbility component carrying
    `_damageType` wins (game enum: 1=PHYSICAL 2=MAGICAL 3=PURE 5=ELEMENT).
    """
    out = {}
    comps = _operator_prefab_components(skill_id)
    for c in comps:
        ccls = c.get("class", "")
        if ccls not in ("Ability", "AbilityStandard", "AttackAbility",
                        "BuffAbility"):
            continue
        if c.get("_damageType") is not None and "_damageType" not in out:
            out["_damageType"] = c.get("_damageType")
        for k in ("_elementDamageType", "_epDamageRatio", "_projectileKey",
                  "_atkScale", "_additionalTimes", "_preDelay"):
            if c.get(k) is not None and k not in out:
                # only accept a projectile whose key belongs to this skill
                if k == "_projectileKey" and not _projectile_belongs(
                        skill_id, c[k]):
                    continue
                out[k] = c.get(k)
        if c.get("_projectileKey") and _projectile_belongs(
                skill_id, c.get("_projectileKey")):
            # target buffs carried by the projectile itself (applied on hit)
            if c.get("_activeBuffs"):
                out.setdefault("_projectileBuffs", []).extend(
                    b for b in c["_activeBuffs"]
                    if isinstance(b, dict) and b.get("buffKey"))
    # NB: no early break - with CompositeAbility resolution the projectile
    # key can sit on a sub-ability processed after the first _damageType.
    ov = _COMPOSITE_PROJECTILE_OVERRIDES.get(skill_id or "")
    if ov:
        for k, v in ov.items():
            if k == "_activeBuffs":
                out.setdefault("_projectileBuffs", []).extend(
                    b for b in v if isinstance(b, dict) and b.get("buffKey"))
            else:
                out.setdefault(k, v)
    return out


def _buff_template_actions(bd, event=None):
    """Template action lists for a buff (all events or one event)."""
    try:
        from .buff_templates import template
        t = template(bd.get("templateKey") or bd.get("buffKey"))
        evs = (t or {}).get("eventToActions") or {}
    except Exception:
        evs = {}
    if event is not None:
        return evs.get(event) or []
    return evs


class OperatorSkillController:
    """Per-operator skill state machine (precise SP model, MECHANICS §4.1)."""

    def __init__(self, op, battle, skill_data, skill_levels=None,
                 equipped_index=None):
        self.op = op
        self.battle = battle
        self.skills = []
        self.active = None      # running skill effect (or None)
        levels = list(skill_levels or [])
        for i, sk in enumerate(skill_data or []):
            lv = levels[i] if i < len(levels) else 1
            run = OperatorSkillRun(op, sk, lv)
            run.controller_index = i
            run.use_count = 0      # \u6bcf\u6b21\u90e8\u7f72\u89e6\u53d1\u6b21\u6570\u9650\u5236
            self.skills.append(run)
        # spType=0/8 skills never use SP.
        self.deploy_skills = [s for s in self.skills if s.sp_type == 8]
        self.equipped_index = None
        if equipped_index is not None:
            try:
                ei = int(equipped_index)
                if 0 <= ei < len(self.skills):
                    self.equipped_index = ei
            except (TypeError, ValueError):
                pass
        # hidden auto-recovery cooldown slot: 1/increment seconds per point
        op._sp_cooldown_remaining = 1.0
        if self.equipped_index is not None:
            # in-game: the equipped skill defines the SP bar (maxSp/initSp)
            eq = self.skills[self.equipped_index]
            if eq.sp_type in (0, 8):
                self.sp_skills = []
                op.sp_max = 0.0
                op.sp = 0.0
            else:
                self.sp_skills = [eq]
                op.sp_max = eq.max_sp
                op.sp = min(op.sp_max, float(eq.init_sp))
        else:
            # fallback (no equipped info): shared bar over selectable skills
            self.sp_skills = [s for s in self.skills
                              if s.sp_type not in (0, 8)]
            if self.sp_skills:
                op.sp_max = max(s.max_sp for s in self.sp_skills)
                init = min((s.init_sp for s in self.sp_skills), default=0.0)
                op.sp = min(op.sp_max, float(init))
            else:
                op.sp_max = 0.0
                op.sp = 0.0
        # 琳琅诗怀雅 merchant 金币：装备技能 blackboard `sp` 键 = 金币上限
        # （S1=1 / S2=3 / S3=10）；金币独立于 SP 槽。
        op._coin_max = 0
        op._coins = 0
        _eqi = self.equipped_index
        if _eqi is not None and 0 <= _eqi < len(self.skills):
            _eqk = self.skills[_eqi]
            if str(_eqk.skill_id or "").startswith("skchr_swire2"):
                try:
                    op._coin_max = max(0, int(float(
                        (_eqk.blackboard or {}).get("sp") or 0)))
                except (TypeError, ValueError):
                    op._coin_max = 0

    # ---- SP model ----
    @property
    def equipped(self):
        """The SP skill that defines the shared SP bar (game: equipped)."""
        if not self.sp_skills:
            return None
        return max(self.sp_skills, key=lambda s: s.max_sp)

    def _auto_increment(self):
        """SP per second = equipped skill increment x spRecoveryPerSec mod."""
        sk = self.equipped
        inc = float(getattr(sk, "increment", None) or 1.0) if sk else 1.0
        try:
            mod = float(self.op.attributes.get("spRecoveryPerSec") or 1.0)
        except (TypeError, ValueError):
            mod = 1.0
        return inc * mod

    def _sp_blocked(self):
        """True while SP recovery must pause: SP_RECOVER_STOPPED (flag 1)
        or a SP skill is active (zuhui)."""
        op = self.op
        if op.sp_max <= 0:
            return True
        if op.flag(1):
            return True
        if self.active is not None and self.sp_skills:
            return True
        return False

    def recover_sp(self, mode, amount=1.0):
        """mode bitmask: 1=auto(slot) 2=per attack 4=per hit.
        spType values 6/7 (attack-or-hit / all) match via bit test."""
        op = self.op
        if op.sp_max <= 0 or op.sp >= op.sp_max:
            return 0.0
        if self._sp_blocked():
            return 0.0
        if mode == 2 and _unit_is_swordmaster(op):
            amount = 1.0          # swordmaster double attack: +1 total
        granted = 0.0
        cap = op.sp_max - op.sp
        for s in self.sp_skills:
            if s.on_cooldown:
                continue
            if mode and (s.sp_type & mode):
                add = min(float(amount), cap)
                op.sp += add
                granted += add
                break
        return granted

    def on_attack_landed(self, hits=1):
        """Attack-recovery SP: one event per attack action. ``hits`` = number
        of damage hits in the action (combo hits each +1; swordmaster innate
        double attack only +1)."""
        if hits < 1:
            hits = 1
        return self.recover_sp(2, float(hits))

    def on_ammo_attack(self):
        """A normal attack consumes 1 ammo; the ammo skill ends at 0."""
        if self.active is not None and self.active.is_ammo:
            sid = getattr(getattr(self.active, "skill", None),
                          "skill_id", "") or ""
            # Angelina2 S3 每次攻击消耗 5 发（attack@trigger_time=50 总弹）
            cost = 5 if sid == "skchr_angel2_3" else 1
            self.active.ammo -= cost
            if self.active.ammo <= 0:
                self.active.on_expire()
                self.active = None

    def trigger_on_deploy(self):
        """Deploy-triggered skills (spType=8, e.g. Gravel S1 / Skadi S2)
        fire immediately on deploy with no SP involvement. The equipped
        skill (squad skillIndex) decides which one fires; without equip
        info the first deploy skill is used."""
        for i, s in enumerate(self.skills):
            if s.sp_type != 8:
                continue
            if self.equipped_index is not None and i != self.equipped_index:
                continue
            # 诗怀雅 S1/S2：部署消耗一枚金币（金币不足则技能不触发）
            _sid8 = getattr(s, "skill_id", "") or ""
            if _sid8 in ("skchr_swire2_1", "skchr_swire2_2"):
                if getattr(self.op, "_coins", 0) < 1:
                    return 0
                self.op._coins -= 1
                if _sid8 == "skchr_swire2_2":
                    # 在范围内第一个可放置且可通行的地面放香槟炸弹
                    _bp = None
                    for _dr, _dc in (getattr(self.op, "range_shape", None)
                                     or [(0, 1)]):
                        _r, _c = self.op.row + _dr, self.op.col + _dc
                        if (_r, _c) == (self.op.row, self.op.col):
                            continue
                        if self.battle.map.tile(_r, _c) is None:
                            continue
                        if self.battle.map.buildable(_r, _c, 1) is not False:
                            _bp = (_r, _c)
                            break
                    if _bp is not None:
                        _ok = self.battle.spawn_token_forced(
                            "token_10031_swire2_gdtrap",
                            _bp[0], _bp[1], owner=self.op)
                        if _ok[0]:
                            _tk = [t for t in self.battle.tokens
                                   if not t.dead and
                                   t.token_id == "token_10031_swire2_gdtrap"][-1]
                            _tk._bomb_spawn_tick = self.battle.tick
            self.active = ActiveSkillEffect(self, s)
            self.active.on_start()
            return 1
        return 0

    def tick(self, dt):
        op = self.op
        # attack@interval passives that run while the skill is NOT active
        # (e.g. Magellan S1: every 3s sluggish inside own + drone ranges).
        self._passive_attack_interval_tick()
        # active skill effect timing (ammo skills have no duration)
        if self.active is not None:
            if not self.active.is_ammo:
                self.active.remaining -= dt
            self.active.tick(dt)
            if not self.active.is_ammo and self.active.remaining <= 1e-9:
                self.active.on_expire()
                self.active = None
        # auto recovery on the hidden cooldown slot; the slot pauses while
        # SP full / SP_RECOVER_STOPPED / a SP skill is active (zuhui), and
        # keeps its remaining time.
        rem = getattr(op, "_sp_cooldown_remaining", 1.0)
        if op.sp_max > 0 and op.sp < op.sp_max and not self._sp_blocked():
            inc = self._auto_increment()
            slot = (1.0 / inc) if inc > 0 else 1.0
            rem -= dt
            # 1e-9 tolerance absorbs float drift in repeated 1/30 subtractions
            while rem <= 1e-9 and op.sp < op.sp_max:
                op.sp = min(op.sp_max, op.sp + 1.0)
                rem += slot
        op._sp_cooldown_remaining = rem
        # AUTO skills fire themselves when SP reaches the (first) charge
        # (never while downed - \u70db\u714c T2 \u7edd\u5904\u91cd\u71c3)
        if self.active is None and not getattr(op, "_reborn_state", False):
            for i, sk in enumerate(self.skills):
                if self.equipped_index is not None \
                        and i != self.equipped_index:
                    continue
                if sk.skill_type == 2 and sk.sp_type not in (0, 8) \
                        and not sk.on_cooldown and op.sp >= sk.sp_cost:
                    self.activate(i)
                    break

    def _passive_attack_interval_tick(self):
        """Periodic ``attack@interval`` effects that keep running while the
        skill is inactive.  Magellan S1 is the shipped example: its passive
        applies ``attack@sluggish`` (0.7s) every ``attack@interval`` (3s)
        to enemies inside her own attack range AND every deployed drone's
        range; while the skill is active the ActiveSkillEffect interval
        path replaces the sluggish with a bind (attack@frozen_duration)."""
        battle = self.battle
        op = self.op
        for s in self.skills:
            if self.equipped_index is not None \
                    and s.controller_index != self.equipped_index:
                continue
            ae = getattr(s, "attack_effects", {}) or {}
            iv = float(ae.get("interval") or 0.0)
            slg = ae.get("sluggish")
            if iv <= 0 or not slg:
                continue
            if self.active is not None and self.active.skill is s:
                continue
            frames = max(1, int(round(iv * 30)))
            anchor = getattr(s, "_interval_anchor", None)
            if anchor is None:
                s._interval_anchor = battle.tick
                continue
            if battle.tick - anchor < frames:
                continue
            s._interval_anchor = battle.tick
            for e in self._passive_range_enemies(op):
                if e.dead:
                    continue
                battle.add_buff(e, {
                    "key": "op_sluggish_atk",
                    "remaining_ticks": int(float(slg) * 30),
                    "layers": 1, "mul": -0.5,
                    "stat": "moveSpeed", "source": op})

    def _passive_range_enemies(self, op):
        """Enemies inside the operator's own attack range plus every
        friendly token's (drone) range - Magellan S1 covers both."""
        battle = self.battle
        enemies = [e for e in battle.get_enemies() if not e.dead]
        cells = set()
        units = [op]
        units += [t for t in battle.get_tokens() if not t.dead]
        for u in units:
            shape = getattr(u, "range_shape", None) or []
            if not shape:
                continue
            cells |= {(u.row + dr, u.col + dc) for dr, dc in shape}
        if not cells:
            shape = getattr(op, "range_shape", None) or []
            cells = {(op.row + dr, op.col + dc) for dr, dc in shape}
        return [e for e in enemies if (e.row, e.col) in cells]

    def activate(self, index=0):
        op = self.op
        if getattr(op, "_reborn_state", False):
            return False, "downed"
        if self.active is not None:
            return False, "already_active"
        if index >= len(self.skills):
            return False, "bad_index"
        s = self.skills[index]
        if s.sp_type in (0, 8):
            return False, "deploy_skill"
        if self.equipped_index is not None and index != self.equipped_index:
            return False, "not_equipped"
        if s.on_cooldown or op.sp < s.sp_cost:
            return False, "not_ready"
        # per-deployment activation limit (e.g. \u533b\u751f S1/S2: 3 times)
        max_use = getattr(s, "max_use_time", 0) or 0
        if max_use > 0 and getattr(s, "use_count", 0) >= max_use:
            return False, "use_limit"
        op.sp -= s.sp_cost
        s.cooldown_remaining = 0.0
        s.use_count = getattr(s, "use_count", 0) + 1
        self.active = ActiveSkillEffect(self, s)
        self.active.on_start()
        self.battle.stats["skillCasts"] += 1
        self.battle.emit(self.battle.tick, "skill_cast",
                         {"instId": op.inst_id, "skillIndex": index,
                          "skillId": s.skill_id})
        return True, index

    def interrupt_active(self):
        """Force-stop the running skill and clean up its effects (used by
        \u70db\u714c T2 downed transition: the game interrupts the skill
        and clears its buffs)."""
        if self.active is not None:
            try:
                self.battle._dispatch_buff_events(
                    self.op, "ON_ABILITY_INTERRUPTED",
                    source=self.op, target=self.op)
            except Exception:
                pass
            self.active.on_expire()
            self.active = None
        return True

    def skill_states(self):
        return [s.to_dict() for s in self.skills]


class OperatorSkillRun:
    """One operator skill level (first level used; calibrate later)."""

    def __init__(self, op, skill, skill_level=1):
        self.op = op
        self.skill_id = skill.get("skillId")
        levels = skill.get("levels") or []
        # skill_level is 1-based rank (1..10); clamp to data range
        idx = min(max(skill_level, 1), len(levels)) - 1
        lv = levels[idx] if levels else {}
        self.rank = idx + 1
        self.name = lv.get("name", "")
        self.description = lv.get("description", "") or ""
        # SkillType: 0=PASSIVE 1=MANUAL 2=AUTO (dump.cs)
        self.skill_type = int(lv.get("skillType") if lv.get(
            "skillType") is not None else 1)
        self.sp_data = lv.get("spData") or {}
        self.sp_type = int(self.sp_data.get("spType", 1))
        self.sp_cost = float(self.sp_data.get("spCost", 0))
        self.init_sp = float(self.sp_data.get("initSp", 0))
        self.increment = float(self.sp_data.get("increment", 1.0) or 1.0)
        self.max_charge_time = int(self.sp_data.get("maxChargeTime", 1) or 1)
        self.max_sp = float(self.sp_cost * max(1, self.max_charge_time))
        self.duration_type = int(lv.get("durationType") or 0)
        self.is_ammo = self.duration_type == 1
        self.duration = float(lv.get("duration") or 0)
        self.range_id = lv.get("rangeId") or ""
        self.blackboard = {b["key"]: b.get("value")
                           for b in (lv.get("blackboard") or [])}
        # phased periodic effects: "<prefix>.interval" keys (e.g.
        # texas2_s_3[sword].interval / appear.atk_scale / mylss_s_1[cost])
        self.phases = {}
        for _k, _v in self.blackboard.items():
            _m = _re.match(
                r"^([a-z0-9_]+(?:_s_\d+)?(?:\[[^\]]+\])?)\."
                r"([a-z0-9_]+)$", _k)
            if _m:
                self.phases.setdefault(_m.group(1), {})[_m.group(2)] = _v
        # attack@-prefixed keys = effects applied on each attack while active
        self.attack_effects = {
            k[len("attack@"):]: v for k, v in self.blackboard.items()
            if k.startswith("attack@")}
        # talent@-prefixed keys = talent-scaled values merged into effects
        self.talent_params = {
            k[len("talent@"):]: v for k, v in self.blackboard.items()
            if k.startswith("talent@")}
        # merge talent params into blackboard/attack effects (talent overrides)
        for k, v in self.talent_params.items():
            if k not in self.blackboard or self.blackboard[k] is None:
                self.blackboard[k] = v
            if k in self.attack_effects and (self.attack_effects[k] is None):
                self.attack_effects[k] = v
        self.cooldown_remaining = 0.0
        try:
            self.max_use_time = int(float(
                self.blackboard.get("skill_max_trigger_time") or 0.0))
        except (TypeError, ValueError):
            self.max_use_time = 0

    @property
    def on_cooldown(self):
        return self.cooldown_remaining > 0

    def to_dict(self):
        return {"skillId": self.skill_id, "name": self.name,
                "equippedIndex": getattr(self, "controller_index", None),
                "spType": self.sp_type, "spCost": self.sp_cost,
                "maxSp": round(self.max_sp, 3),
                "maxChargeTime": self.max_charge_time,
                "increment": self.increment,
                "initSp": self.init_sp, "duration": self.duration,
                "isAmmo": self.is_ammo,
                "cooldownRemaining": round(self.cooldown_remaining, 3),
                "blackboard": self.blackboard}


def _range_offsets(range_id):
    """Approximate skill range shapes by rangeId (calibrate later)."""
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


class ActiveSkillEffect:
    """A running skill's effect (buff window + instant effects).

    Supported blackboard keys (from skills.json):
      atk/def/attack_speed/base_attack_time/max_hp ...  stat buffs
      atk_scale + damage/cnt/interval ................  skill damage
      heal_scale .....................................  healing
      stun/sluggish ..................................  abnormal on enemies
      max_target .....................................  hit count limit
    """

    def __init__(self, controller, skill_run):
        self.controller = controller
        self.op = controller.op
        self.skill = skill_run
        self.is_ammo = bool(getattr(skill_run, "is_ammo", False))
        if not self.is_ammo:
            try:
                pref = _operator_prefab_params(
                    getattr(skill_run, "skill_id", "") or "")
                if int(pref.get("_showSpAsBulletMode") or 0) == 1:
                    self.is_ammo = True
            except Exception:
                pass
        if getattr(self, "is_ammo", False):
            self.remaining = 1e9     # ammo skills have no duration
            self.ammo = self._ammo_count()
        else:
            # LevelData duration == -1: deploy skills / infinite skills.
            # Non-deploy skills with no blackboard duration are infinite
            # (e.g. Ray S2 / Whisperain S2 "\u6301\u7eed\u65f6\u95f4\u65e0\u9650").
            dur = skill_run.duration
            if dur <= 0:
                try:
                    dur = float((getattr(skill_run, "blackboard", {}) or
                                 {}).get("duration") or 0.0)
                except (TypeError, ValueError):
                    dur = 0.0
                if skill_run.duration < 0 and dur <= 0 \
                        and int(getattr(skill_run, "sp_type", 1) or 1) != 8:
                    # duration<0 with no blackboard duration is either an
                    # infinite sustained window (sustained stat keys present,
                    # e.g. Ray S2 / Whisperain S2) or an instant cast with no
                    # sustained keys (e.g. Doctor S2 hormone shot).
                    _sbb = (getattr(skill_run, "blackboard", {}) or {})
                    _sustained = any(k in _sbb for k in (
                        "atk", "def", "attack_speed", "base_attack_time",
                        "max_hp", "hp_recovery_per_sec",
                        "sp_recovery_per_sec", "taunt_level", "block_cnt",
                        "magic_resistance", "interval", "respawn_time")) or \
                        any(str(k).startswith("attack@") for k in _sbb)
                    # 诗怀雅 S3"千金一掷"：持续时间无限（可随时主动关闭）
                    if str(getattr(skill_run, "skill_id", "") or "") == \
                            "skchr_swire2_3":
                        _sustained = True
                    if _sustained:
                        dur = 1e9
            self.remaining = max(dur, 0.1)
            self.ammo = 0
        self.buffs = []
        self._phase_fired = set()   # phased stat buffs applied once per run
        self.attack_effects = dict(getattr(skill_run, "attack_effects", {}))
        self._ray_s3_kills = 0      # Ray S3: kills refund SP at skill end
        battle = controller.battle
        # prefab `_damageType` (game enum) takes priority over the character
        # description heuristic (e.g. Texas S2 sword rain is MAGICAL)
        pref = _operator_prefab_params(
            getattr(skill_run, "skill_id", "") or "")
        pd = pref.get("_damageType")
        if pd == 2:
            self.dmg_type = DamageType.MAGICAL
        elif pd == 3:
            self.dmg_type = DamageType.TRUE
        elif pd == 1:
            self.dmg_type = DamageType.PHYSICAL
        elif pd == 5:
            self.dmg_type = DamageType.ELEMENT
        elif hasattr(battle, "_char_damage_type"):
            self.dmg_type = battle._char_damage_type(self.op)
        else:
            self.dmg_type = DamageType.MAGICAL

    def _ammo_count(self):
        """Ammo capacity from blackboard (cnt/ammo/max_ammo); default 1."""
        bb = getattr(self.skill, "blackboard", {}) or {}
        for k in ("cnt", "ammo", "max_ammo", "maxAmmo", "trigger_time",
                  "attack@trigger_time"):
            v = bb.get(k)
            if v is not None:
                try:
                    return max(1, int(float(v)))
                except (TypeError, ValueError):
                    continue
        return 1

    def heal_max_target(self):
        """Multi-target heal count while this skill is active.  The
        blackboard `attack@max_target` (>1) wins (e.g. \u871c\u8393 S2
        \u632f\u5948); otherwise curated skills whose count only lives in
        the description/prefab (\u871c\u8393 S1 \u7cbe\u795e\u62a4\u7406:
        2).  Returns 1 when the skill heals a single target."""
        ae = getattr(self, "attack_effects", {}) or {}
        v = ae.get("max_target")
        if v is not None:
            try:
                n = int(v)
            except (TypeError, ValueError):
                n = 1
            if n > 1:
                return n
        sid = getattr(getattr(self, "skill", None), "skill_id", "") or ""
        return int(_HEAL_MULTI_TARGET.get(sid, 1))

    def heal_shot_count(self):
        """Sequential heal shots per attack while active.  \u7eaf\u70c1
        \u827e\u96c5\u6cd5\u62c9 S3 \u706b\u5c71\u56de\u97ff fires 5 shots;
        each shot re-picks the top not-yet-selected ally (cycles when fewer
        candidates than shots)."""
        sid = getattr(getattr(self, "skill", None), "skill_id", "") or ""
        return int(_HEAL_SHOT_COUNT.get(sid, 1))

    def heal_attack_scale(self):
        """Heal amount multiplier applied by the active skill
        (attack@heal_scale, e.g. \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S3
        0.25 per shot); 1.0 when the skill does not scale healing."""
        ae = getattr(self, "attack_effects", {}) or {}
        try:
            return float(ae.get("heal_scale") or 1.0)
        except (TypeError, ValueError):
            return 1.0

    def wandermedic_ep_scale(self, target):
        """\u54c8\u6d1b\u5fb7 S2 \u91cd\u75c7\u4f18\u5148: while active, the
        wandermedic element-damage recovery is multiplied by the skill's
        trait_scale (1.2~2.5 by rank) when healing a target whose accumulated
        element damage exceeds half its burst threshold ("\u6cbb\u7597\u5143
        \u7d20\u635f\u4f24\u7d2f\u8ba1\u8d85\u8fc7\u4e00\u534a\u7684\u76ee\u6807
        \u65f6\uff0c\u5143\u7d20\u635f\u4f24\u56de\u590d\u91cf\u63d0\u5347\u81f3
        X%"); other targets stay at 1.0."""
        sid = getattr(getattr(self, "skill", None), "skill_id", "") or ""
        if sid != "skchr_harold_2":
            return 1.0
        bb = getattr(getattr(self, "skill", None), "blackboard", {}) or {}
        try:
            ts = float(bb.get("trait_scale") or 1.0)
        except (TypeError, ValueError):
            return 1.0
        try:
            from .targeting import _unit_ep_over_half
            if _unit_ep_over_half(target, self.controller.battle):
                return ts
        except Exception:
            pass
        return 1.0

    def _resolve_dmg_type(self):
        """Robust damage type: prefab `_damageType` first (game enum
        PHYSICAL=1 MAGICAL=2 PURE=3 ELEMENT=5), else character heuristic."""
        dt = getattr(self, "dmg_type", None)
        if dt is not None:
            return dt
        pref = _operator_prefab_params(
            getattr(getattr(self, "skill", None), "skill_id", "") or "")
        pd = pref.get("_damageType")
        if pd is not None:
            if pd == 2:
                return DamageType.MAGICAL
            if pd == 3:
                return DamageType.TRUE
            if pd == 1:
                return DamageType.PHYSICAL
            if pd == 5:
                return DamageType.ELEMENT
        battle = self.controller.battle if getattr(
            self, "controller", None) else None
        op = getattr(self, "op", None)
        if battle is not None and op is not None and hasattr(
                battle, "_char_damage_type"):
            return battle._char_damage_type(op)
        return DamageType.MAGICAL

    def _resolve_ep_type(self):
        """Element type of the element damage this skill attaches (plain
        ``ep_damage_ratio`` bursts and ``attack@ep_damage_ratio``).

        Resolution order: the skill description's 元素损伤 name first
        (operator skill text always names it, e.g. 折光 S1
        ``凋亡损伤`` -> DARK/3), then the prefab ``_elementDamageType``
        (game enum SANITY=1 WATER=2 FIRE=3 DARK=4) when present, else 0
        (neural).  Hardcoding 0 was wrong for 灼燃/侵蚀/凋亡 skills
        (温米 S1 / 波卜 S2 / 凛视 S2 / 折光 S1+S2 / 妮芙 S1 / 伯塔尼 S2),
        while 神经 skills (Miss.Christine S1 / 塑心 S2 / 酒神 S3) keep 0.
        """
        et = getattr(self, "_resolved_ep_type", None)
        if et is not None:
            return et
        et = 0
        sid = getattr(getattr(self, "skill", None), "skill_id", "") or ""
        desc = getattr(getattr(self, "skill", None), "description", "") or ""
        _d = _ep_type_from_desc(desc)
        if _d is not None:
            et = _d
        else:
            pref = _operator_prefab_params(sid)
            edt = pref.get("_elementDamageType")
            if edt is not None:
                try:
                    et = translate_game_element_type(int(edt))
                except (TypeError, ValueError):
                    et = 0
        self._resolved_ep_type = et
        return et

    def damage_type_switch(self):
        """Damage-type override while this skill is active (e.g. Amiya S3
        \u5947\u7f8e\u62c9: damage type becomes TRUE). Returns None when the
        skill does not override the basic-attack damage type."""
        sid = getattr(getattr(self, "skill", None), "skill_id", "") or ""
        if sid == "skchr_amiya_3":
            return DamageType.TRUE
        # prefab-level explicit damage type also overrides basic attacks
        pd = getattr(self, "dmg_type", None)
        return pd if pd is not None else None

    def _fire_burst(self, targets, dmg_type, scale, dmg, stun, sluggish,
                    ep, hits, proj_key, pref_params, bb,
                    delay_for_cast=True, apply_abnormal=True):
        """Apply a damage burst to ``targets``.

        Projectile skills fire projectiles (damage + target effects land on
        hit, carrying the prefab's projectile buffs); instant skills apply
        damage immediately. ``apply_abnormal`` gates stun/sluggish/ep on
        the instant path (on_start applies abnormal to ALL enemies after
        the burst for non-projectile skills).
        """
        battle = self.controller.battle
        op = self.op
        atk = op.attributes.get("atk")
        if not targets:
            return
        _ep_type = self._resolve_ep_type()
        if proj_key:
            # Blackboard `atk_scale` is the player-facing multiplier;
            # prefab `_atkScale` only fills in when the blackboard has none.
            pref_scale = pref_params.get("_atkScale")
            eff_scale = float(pref_scale) \
                if (pref_scale is not None and not bb.get("atk_scale")) \
                else float(scale or 0.0)
            proj_buffs = pref_params.get("_projectileBuffs") or []
            add_times = int(pref_params.get("_additionalTimes") or 0)
            proj_count = max(1, int(hits or 1)) * (1 + add_times)
            # alchemist (\u70bc\u91d1\u5e08) alchemy units: the projectile
            # lands as a persistent zone; the projectile buffs apply to every
            # unit (ally/enemy) within `projectile_range` of the landing tile
            try:
                proj_range = float(bb.get("projectile_range") or 0.0)
            except (TypeError, ValueError):
                proj_range = 0.0
            delay_ticks = int(round(
                float(pref_params.get("_preDelay") or 0.0) * 30)) \
                if delay_for_cast else 0
            for e in targets:
                if e.dead:
                    continue
                for _ in range(proj_count):
                    if e.dead:
                        break
                    _tgt = e
                    _dmg = dmg
                    _scale = eff_scale
                    _stun = stun
                    _sluggish = sluggish
                    _ep = ep
                    _buffs = proj_buffs
                    _op = op
                    _dt = dmg_type
                    _atk = atk
                    _bb = bb
                    _run = self
                    _prange = proj_range
                    _ept = _ep_type

                    def _cb(battle, proj, _tgt=_tgt, _dmg=_dmg,
                            _scale=_scale, _stun=_stun, _sluggish=_sluggish,
                            _ep=_ep, _buffs=_buffs, _op=_op, _dt=_dt,
                            _atk=_atk, _bb=_bb, _run=_run, _prange=_prange,
                            _ept=_ept):
                        if _dmg:
                            battle.apply_damage(_tgt, float(_dmg), _dt,
                                                source=_op)
                        elif _scale and not _prange:
                            battle.apply_damage(_tgt, _atk * _scale, _dt,
                                                source=_op)
                        if _stun:
                            battle.add_abnormal(_tgt, 0, float(_stun))
                        if _sluggish:
                            battle.add_buff(_tgt, {
                                "key": "op_sluggish",
                                "remaining_ticks":
                                int(float(_sluggish) * 30),
                                "layers": 1, "mul": -0.5,
                                "stat": "moveSpeed", "source": _op})
                        if _ep:
                            battle.add_ep(_tgt, _ept, _atk * float(_ep))
                        if _prange:
                            # alchemy zone: apply the projectile buffs to
                            # every unit around the landing tile
                            zone = [_tgt]
                            for _u in (list(battle.get_operators())
                                       + list(battle.get_tokens())
                                       + list(battle.get_enemies())):
                                if _u is _tgt or getattr(_u, "dead", False):
                                    continue
                                if abs(_u.row - _tgt.row) <= _prange and \
                                        abs(_u.col - _tgt.col) <= _prange:
                                    zone.append(_u)
                        else:
                            zone = [_tgt]
                        for bd in _buffs:
                            try:
                                from .buff_templates import materialise_buff
                                mbb = dict(_bb)
                                mbb.setdefault(
                                    "duration",
                                    max(1.0, float(getattr(
                                        _run, "remaining", 1.0) or 1.0)))
                                if _prange:
                                    # alchemy unit caches the throw-time
                                    # attack power: cached_atk = atk x
                                    # atk_scale (used by NoSourceDamage);
                                    # zone lifetime = projectile_delay_time
                                    mbb["cached_atk"] = float(_atk) * \
                                        float(mbb.get("atk_scale") or 1.0)
                                    mbb["duration"] = float(
                                        mbb.get("projectile_delay_time")
                                        or mbb.get("duration") or 10.0)
                                for _u in zone:
                                    entry = materialise_buff(
                                        battle, _u, dict(bd), mbb, _op)
                                    if entry and entry.get("key"):
                                        battle.add_buff(_u, entry)
                            except Exception:
                                pass
                    battle.spawn_projectile(op, e, proj_key, _dt,
                                            atk_scale=eff_scale,
                                            hit_callback=_cb,
                                            delay_ticks=delay_ticks)
            return
        for e in targets:
            if e.dead:
                continue
            for _ in range(max(1, int(hits or 1))):
                if e.dead:
                    break
                if dmg:
                    battle.apply_damage(e, float(dmg), dmg_type,
                                        source=op)
                elif scale:
                    battle.apply_damage(e, atk * float(scale),
                                        dmg_type, source=op)
                if apply_abnormal:
                    if stun:
                        battle.add_abnormal(e, 0, float(stun))
                    if sluggish:
                        battle.add_buff(e, {
                            "key": "op_sluggish",
                            "remaining_ticks": int(float(sluggish) * 30),
                            "layers": 1, "mul": -0.5,
                            "stat": "moveSpeed", "source": op})
                    if ep:
                        battle.add_ep(e, _ep_type, atk * float(ep))

    def apply_on_attack(self, target):
        """Effects applied on each attack while the skill is active."""
        if target is None or target.dead:
            return
        battle = self.controller.battle
        op = self.op
        _sid = getattr(self.skill, "skill_id", "") or ""
        ae = self.attack_effects
        # Sharp S3 uses unprefixed keys (atk_each_stack) with no attack@
        # effects; everything else needs attack@ entries to do anything.
        if not ae and _sid != "skchr_acguad_3":
            return
        # probability gate
        prob = float(ae.get("prob") or 1.0)
        if prob < 1.0 and not battle.rng.chance(prob):
            return
        atk = op.attributes.get("atk")
        dmg_type = self._resolve_dmg_type()
        # multi-hit: attack@times / attack@cnt (e.g. Ch'en S3 6 hits)
        hits = max(1, int(ae.get("times") or ae.get("cnt") or 1))
        if _sid == "skchr_angel2_3":
            hits = 5        # 新约能天使 S3: 每次攻击为 5 连击
        # extra damage hit (attack@atk_scale).  Hunters already apply the
        # skill's attack@atk_scale to their base attack (trait override,
        # e.g. Ray S3), so the extra hit must be skipped there.  NOTE:
        # attack@atk is a positive activation stat buff (atk +% on self /
        # summons / allies, e.g. catap2 S2 / kalts S2 / necras S3), NEVER
        # extra flat damage - wired in on_start instead.
        scale = float(ae.get("atk_scale") or 0.0)
        _hunter = False
        try:
            _ts = getattr(op, "trait_system", None)
            _hunter = bool(_ts is not None and _ts.is_hunter())
        except Exception:
            _hunter = False
        if scale and not (_hunter and scale > 0):
            per_hit = atk * scale
            for _ in range(hits):
                if target.dead:
                    break
                battle.apply_damage(target, per_hit, dmg_type, source=op)
        # attack@hp_ratio: damage scaled by target hp ratio
        hp_ratio = ae.get("hp_ratio")
        if hp_ratio:
            ratio = target.hp / target.max_hp if target.max_hp else 1.0
            battle.apply_damage(target, atk * float(hp_ratio) * (1 - ratio),
                                dmg_type, source=op)
        # abnormal on hit
        stun = ae.get("stun")
        if stun:
            # attack@buff_prob gates the attached abnormal (e.g. 雷蛇 S2
            # 10% / 帕拉斯 S2 50% / 推王 S3 40% / 赫德雷 S3 25% stun);
            # skills without it apply the abnormal on every hit.
            _bprob = float(ae.get("buff_prob") or 1.0)
            if _bprob >= 1.0 or battle.rng.chance(_bprob):
                battle.add_abnormal(target, 0, float(stun))
        sluggish = ae.get("sluggish")
        # Periodic bind skills (attack@interval + attack@frozen_duration,
        # e.g. Magellan S1) apply their sluggish/bind through the interval
        # path, not on every attack hit (Magellan's sluggish is the passive
        # value; while active the interval tick applies the bind instead).
        if sluggish and not (ae.get("interval") and ae.get("frozen_duration")):
            battle.add_buff(target, {"key": "op_sluggish_atk",
                                     "remaining_ticks":
                                     int(float(sluggish) * 30),
                                     "layers": 1, "mul": -0.5,
                                     "stat": "moveSpeed", "source": op})
        silence = ae.get("silence")
        if silence:
            battle.add_abnormal(target, 12, float(silence))
        unmove = ae.get("unmove_duration")
        if unmove:
            battle.add_abnormal(target, 13, float(unmove))  # \u675f\u7f1a
        # abnormal on hit: 寒冷 / 沉睡 / 浮空 / 恐惧 / 束缚
        # (attack@ keys carry the duration in seconds, e.g. 极光 S2
        # attack@cold 2.5, 缇缇 S1 attack@sleep 1.5, 霍尔海雅 S2
        # attack@levitate 1.0, 荒芜拉普兰德 S2 attack@fear 1.0).
        cold = ae.get("cold")
        if cold:
            battle.add_abnormal(target, AbnormalFlag.COLD, float(cold))
        sleep_dur = ae.get("sleep")
        if sleep_dur:
            battle.add_abnormal(target, AbnormalFlag.DOZE, float(sleep_dur))
        levitate = ae.get("levitate")
        if levitate:
            battle.add_abnormal(target, AbnormalFlag.LEVITATE,
                                float(levitate))
        fear = ae.get("fear")
        if fear:
            battle.add_abnormal(target, AbnormalFlag.FEARED, float(fear))
        # attack@frozen_duration carries a bind/root duration in the
        # shipped data (奥斯塔 S2 / 麦哲伦 S1 descriptions say 束缚);
        # periodic skills (attack@interval present) apply it through the
        # interval path instead of every hit.
        root = ae.get("frozen_duration")
        if root and not ae.get("interval"):
            battle.add_abnormal(target, AbnormalFlag.UNMOVABLE,
                                float(root))
        # attribute debuffs on hit (attack@move_speed / attack@attack_speed
        # WITH attack@duration, e.g. 安哲拉 S2 -20% 移速 3s / 白雪 S2 -22%
        # 1s / 慑砂 S2 目标攻速 -3 3s).  Aura-style keys without a duration
        # (海霓 S2 / 荒芜拉普兰德 S3 / 万顷 S2 self+ally buffs) stay in
        # their own paths.  moveSpeed is a 1.0-base ratio (mul layer);
        # attackSpeed is a 100-base percentage (add layer).
        _hit_dur = float(ae.get("duration") or 0.0)
        ms = ae.get("move_speed")
        if ms and _hit_dur > 0:
            battle.add_buff(target, {
                "key": "op_skill_atk_move_speed",
                "remaining_ticks": int(_hit_dur * 30),
                "layers": 1, "mul": float(ms),
                "stat": "moveSpeed", "source": op})
        aspd = ae.get("attack_speed")
        if aspd and _hit_dur > 0:
            battle.add_buff(target, {
                "key": "op_skill_atk_attack_speed",
                "remaining_ticks": int(_hit_dur * 30),
                "layers": 1, "add": float(aspd),
                "stat": "attackSpeed", "source": op})
        # Ch'en S2/S3 slime field: every attack drops slime inside the
        # range for attack@projectile_life_time (5s); grounded enemies in
        # it get attack@move_speed (mul) + attack@def (add) debuffs.
        # chen2_2: -10% move / -50 def; chen2_3: -20% move / -100 def.
        if ae.get("projectile_life_time") is not None:
            _life = float(ae.get("projectile_life_time") or 0.0)
            _ms = ae.get("move_speed")
            _df = ae.get("def")
            if _life > 0 and _ms is not None and float(_ms) < 0 \
                    and _df is not None and float(_df) < 0:
                _ticks = max(1, int(_life * 30))
                for e in self._in_range_enemies():
                    if e.dead or getattr(e, "is_flying", False):
                        continue
                    battle.add_buff(e, {
                        "key": "op_slime_field",
                        "remaining_ticks": _ticks,
                        "layers": 1, "mul": float(_ms),
                        "stat": "moveSpeed", "source": op})
                    battle.add_buff(e, {
                        "key": "op_slime_field_def",
                        "remaining_ticks": _ticks,
                        "layers": 1, "add": float(_df),
                        "stat": "def", "source": op})
        # attack@sp: hit-attached SP recovery.  Windflit S1 "此身为筑":
        # the hit gives attack@sp (1) SP to every reliable-battery wearer
        # (caster profession 32 / supporter 16, incl. himself).  Other
        # attack@sp skills have their own semantics (Angelina S3 = SP for
        # the delivered operator, champagne-bottle tokens, negative coin
        # keys) and are wired separately, not here.
        sp_gain = ae.get("sp")
        if sp_gain is not None and _sid == "skchr_windft_1":
            try:
                v = float(sp_gain)
            except (TypeError, ValueError):
                v = 0.0
            if v > 0:
                for u in list(battle.get_operators()) + \
                        list(battle.get_tokens()):
                    if u.dead or getattr(u, "sp_max", 0) <= 0:
                        continue
                    _p = int(getattr(u, "profession", -1) or -1)
                    if _p not in (16, 32):   # supporter / caster
                        continue
                    # 直接回复技力（不受目标 spType 门控，区别于攻击回复）
                    u.sp = min(float(u.sp_max), float(u.sp or 0.0) + v)
        # ---- stack-on-hit buffs (attack@max_stack_cnt family) ----
        # Closur S3 "Q.E.D.": each hit stacks a 3% slow on the target
        # (attack@slow_down), 3s, up to attack@max_stack_cnt (10), total
        # slow capped at attack@slow_down_max (30%).
        if _sid == "skchr_closur_3":
            _sd = ae.get("slow_down")
            _sdt = ae.get("slow_down_time")
            _mx = int(ae.get("max_stack_cnt") or 1)
            if _sd is not None and _sdt is not None:
                self._stack_buff(target, "op_closur_slow", "moveSpeed",
                                 float(_sd), _mx, int(float(_sdt) * 30))
        # Pepe S3 "时光震荡": each attack stacks self atk +10%
        # (attack@atk) up to attack@max_stack_cnt (4) for the skill
        # window.
        elif _sid == "skchr_pepe_3":
            _av = ae.get("atk")
            _mx = int(ae.get("max_stack_cnt") or 1)
            if _av is not None:
                self._stack_buff(op, "op_pepe_atk_stack", "atk",
                                 float(_av), _mx,
                                 max(1, int(getattr(self, "remaining",
                                                    1.0) * 30)))
        # Veen S2 "以鲜血洗去": each attack stacks self atk +6% and
        # attack speed +5 (attack@veen_s_2_buff[stack].*) up to
        # max_stack_cnt (7).
        elif _sid == "skchr_veen_2":
            _va = ae.get("veen_s_2_buff[stack].atk")
            _vs = ae.get("veen_s_2_buff[stack].attack_speed")
            _vm = int(ae.get("veen_s_2_buff[stack].max_stack_cnt") or 1)
            if _va is not None or _vs is not None:
                _ticks = max(1, int(getattr(self, "remaining", 1.0) * 30))
                if _va is not None:
                    self._stack_buff(op, "op_veen_atk_stack", "atk",
                                     float(_va), _vm, _ticks)
                if _vs is not None:
                    self._stack_buff(op, "op_veen_aspd_stack",
                                     "attackSpeed", float(_vs), _vm,
                                     _ticks, formula=0)
        # Sharp S3 "力战不竭": each attack stacks self atk +15%
        # (atk_each_stack, max_atk_stack_cnt 8); switching targets resets
        # the stacks.
        elif _sid == "skchr_acguad_3":
            _bb = getattr(self.skill, "blackboard", {}) or {}
            _ea = _bb.get("atk_each_stack")
            _em = int(_bb.get("max_atk_stack_cnt") or 1)
            if _ea is not None:
                _last = getattr(op, "_acguad_last_target", None)
                if _last is not None and _last is not target:
                    battle.buffs.remove(op, "op_acguad_atk_stack")
                op._acguad_last_target = target
                self._stack_buff(op, "op_acguad_atk_stack", "atk",
                                 float(_ea), _em,
                                 max(1, int(getattr(self, "remaining",
                                                    1.0) * 30)))
        # Angelina2 S3 "使命必达！": the delivery coordinate
        # (token_10056_angel2_target).  Every attack cannon-bombs the
        # coordinate (atk * attack@cannon_atk_scale splash) and deploys
        # the ground operator with the longest redeploy timer there,
        # granting attack@sp (6) SP.
        if _sid == "skchr_angel2_3":
            _dlv = [t for t in battle.get_tokens()
                    if not t.dead
                    and t.token_id == "token_10056_angel2_target"
                    and t.owner is op]
            if _dlv:
                _dest = _dlv[0]
                _cannon = float(ae.get("cannon_atk_scale") or 0.0)
                if _cannon > 0:
                    for e in list(battle.get_enemies()):
                        if e.dead:
                            continue
                        if abs(e.row - _dest.row) <= 1 \
                                and abs(e.col - _dest.col) <= 1:
                            battle.apply_damage(e, atk * _cannon,
                                                DamageType.PHYSICAL,
                                                source=op)
                _cand = None
                for _cid, _until in list(battle._redeploy_until.items()):
                    if any(_o.char_id == _cid
                           for _o in battle.get_operators()):
                        continue
                    if _cand is None or _until > _cand[1]:
                        _cand = (_cid, _until)
                if _cand is not None:
                    _cid = _cand[0]
                    _old = battle._redeploy_until.get(_cid)
                    battle._redeploy_until[_cid] = 0    # 投递无视冷却
                    try:
                        # 投递坐标是一次性的：部署前回收，腾出目标格
                        try:
                            battle.withdraw_token(_dest.inst_id)
                        except Exception:
                            pass
                        _ok = battle.deploy(_cid, _dest.row, _dest.col)
                    finally:
                        if _old is not None:
                            battle._redeploy_until[_cid] = _old
                        else:
                            battle._redeploy_until.pop(_cid, None)
                    if _ok[0]:
                        _sp = float(ae.get("sp") or 0.0)
                        if _sp > 0:
                            _dep = battle.operators[-1]
                            _dep.sp = min(
                                float(_dep.sp_max or 0.0),
                                float(_dep.sp or 0.0) + _sp)
        # 诗怀雅 S1"仗义疏财"：消耗 1 金币的"下一次攻击"为周围 8 格内
        # 血量不足 70% 的一名友方恢复 attack@heal_scale 生命，触发后技能结束
        if _sid == "skchr_swire2_1":
            _hs = ae.get("heal_scale")
            if _hs:
                _cands = [u for u in list(battle.get_operators()) +
                          list(battle.get_tokens())
                          if not u.dead and u is not op
                          and abs(u.row - op.row) <= 1
                          and abs(u.col - op.col) <= 1
                          and u.hp < u.max_hp * 0.7]
                if _cands:
                    try:
                        _t = battle.rng.choice(_cands)
                    except Exception:
                        _t = _cands[0]
                    battle.apply_heal(_t, atk * float(_hs), source=op)
                sc0 = self.controller
                if sc0.active is self:
                    sc0.active.on_expire()
                    sc0.active = None
        # heal on hit (attack@heal_scale / attack@atk_to_hp_recovery_ratio)
        heal_scale = ae.get("heal_scale")
        if heal_scale:
            _heal_target = op
            if _sid == "skchr_taraxa_1":
                # 风絮 S1: 随机回复攻击范围内已受伤的一名单位（含自身）
                _cells = {(op.row + _dr, op.col + _dc)
                          for _dr, _dc in (op.range_shape or [])}
                _cands = [op]
                for u in list(battle.get_operators()) + \
                        list(battle.get_tokens()):
                    if u.dead or u is op or u.hp >= u.max_hp:
                        continue
                    if (u.row, u.col) in _cells:
                        _cands.append(u)
                if len(_cands) > 1:
                    try:
                        _heal_target = battle.rng.choice(_cands)
                    except Exception:
                        _heal_target = _cands[0]
            battle.apply_heal(_heal_target, atk * float(heal_scale),
                              source=op)
        # element damage on hit (attack@ep_damage_ratio)
        ep = ae.get("ep_damage_ratio")
        if ep:
            _et = self._resolve_ep_type()
            battle.add_ep(target, _et, atk * float(ep))
        # burst-window bonus (attack@extra_ep_damage_scale): while the
        # target is in the SAME element's burst, deal extra ELEMENT
        # damage = atk x scale (game templates kaitou_s_1[ep_damage] /
        # kaitou_s_2[ep_damage] / nymph_s_1[ep_damage]:
        # FilterEPBreakRecoveryType DARK -> AdvancedApplyDamage ELEMENT).
        # During a burst all EP bars are locked, so this is HP damage,
        # not an EP accumulation (the ep_damage_ratio part no-ops).
        extra_ep = ae.get("extra_ep_damage_scale")
        if extra_ep:
            _et2 = self._resolve_ep_type()
            if battle.buffs.get(target, "ep_burst_cd_%d" % _et2):
                battle.apply_damage(target, atk * float(extra_ep),
                                    DamageType.ELEMENT, source=op,
                                    element_as_hp=True)
        # displacement on hit (attack@force)
        force = ae.get("force")
        if force is not None:
            self._displace(target, force, force_source="attack")

    # ---- displacement (push / pull) ----
    # Projectile-vs-effect displacement: PRTS separates "bullet" (dan-dao)
    # forces from "effect" (te-xiao) forces; a force applied through a ranged
    # attack or a listed projectile skill travels as a projectile.
    PROJECTILE_FORCE_SKILLS = frozenset({
        "skchr_shaw_1", "skchr_shaw_2",       # Shaw S1/S2
        "skchr_weedy_2", "skchr_weedy_3",     # Weedy S2/S3
    })

    def _op_attack_ranged(self):
        op = self.op
        shape = getattr(op, "range_shape", None) or []
        return bool(shape) and not any(
            (dr, dc) == (0, 0) for dr, dc in shape)

    def _force_kind(self, force_source="bb"):
        """'projectile' (bullet) or 'effect' (immediate).

        attack@force on a ranged attack -> projectile displacement;
        other force applications use the effect table.
        """
        sid = getattr(getattr(self, "skill", None), "skill_id", "") or ""
        if force_source == "attack" and self._op_attack_ranged():
            return "projectile"
        if sid in self.PROJECTILE_FORCE_SKILLS:
            return "projectile"
        return "effect"

    def _displace(self, target, force, kind=None, force_source="bb"):
        """Push/pull an enemy by a force level (blackboard ``force``).

        PRTS push/pull rules:
          - effective level = force level - enemy massLevel (min 0)
          - push: direction-corrected when the hit angle is oblique
            (>45 deg) or the enemy is closer than 0.25 tiles -> radial
            force and effective level -2; otherwise the axis force table
            applies (bullet vs effect rows).
          - pull: effective level >= 0 pulls to 0.5 tiles in front of the
            caster (stop radius 0.6708); negative levels use the d=2/d=3
            interpolation tables and drag for 1s (0.5s when < -1).
        """
        if target is None or getattr(target, "dead", False):
            return False
        battle = self.controller.battle
        op = self.op
        f = float(force)
        mass = 0
        try:
            mass = int(target.attributes.get("massLevel") or 0)
        except (TypeError, ValueError):
            mass = 0
        if kind is None:
            kind = self._force_kind(force_source)
        ox, oy = float(op.pos_x), float(op.pos_y)
        tx, ty = float(target.pos_x), float(target.pos_y)
        if f >= 0:
            fl = int(round(f))
            dr, dc = _DIR_VECTORS.get(getattr(op, "direction", 1), (0, 1))
            fx, fy = dc, dr
            dxu, dyu = tx - ox, ty - oy
            dist = (dxu * dxu + dyu * dyu) ** 0.5
            eff = force_level_from(fl, mass)
            # oblique / too close -> radial force, effective level -2
            angle = 0.0
            if dist > 1e-6:
                cosang = (dxu * fx + dyu * fy) / dist
                cosang = max(-1.0, min(1.0, cosang))
                angle = math.degrees(math.acos(cosang))
            if dist < PUSH_DIST_CORRECTION or angle > PUSH_ANGLE_CORRECTION:
                eff += PUSH_CORRECTED_LEVEL_DELTA
                if dist > 1e-6:
                    dr, dc = dyu / dist, dxu / dist
            if eff < -3:
                return False
            if eff != force_level_from(fl, mass):
                # corrected level: rebuild from (fl + delta) so the table row
                # matches the corrected effective level
                fl_eff = fl + PUSH_CORRECTED_LEVEL_DELTA
            else:
                fl_eff = fl
            distance = push_displacement(fl_eff, mass, kind)
            if distance <= 0:
                return False
            duration = push_duration(fl_eff, mass, kind)
            return battle.displace(target, dr, dc, distance, source=op,
                                   duration=duration,
                                   kind=kind, force_level=eff)
        # ---- pull ----
        fl = int(round(-f))
        dr0, dc0 = _DIR_VECTORS.get(getattr(op, "direction", 1), (0, 1))
        sx = ox + dc0 * PULL_FRONT_OFFSET     # pull home: 0.5 in front
        sy = oy + dr0 * PULL_FRONT_OFFSET
        dxu, dyu = sx - tx, sy - ty
        dist = (dxu * dxu + dyu * dyu) ** 0.5
        if dist <= 1e-6:
            return False
        dr, dc = dyu / dist, dxu / dist
        eff = force_level_from(fl, mass)
        if eff < -3:
            return False
        if pull_pulled_home(fl, mass):
            # effective level >= 0: pull to 0.5 in front, stop 0.6708
            distance = dist
        else:
            d_front = dist + PULL_FRONT_OFFSET  # distance to the stop point
            distance = pull_displacement(fl, mass, d_front)
            if distance <= 0:
                return False
        return battle.displace(target, dr, dc, distance, source=op,
                               duration=pull_duration(fl, mass),
                               kind="pull", force_level=eff)

    # ---- helpers ----
    def _in_range_enemies(self):
        battle = self.controller.battle
        op = self.op
        enemies = [e for e in battle.get_enemies() if not e.dead]
        rid = getattr(self.skill, "range_id", "") or ""
        if rid.startswith("x-"):            # whole-map skill (e.g. Fiammetta)
            return enemies
        if rid:
            rng = _range_offsets(rid)
            cells = {(op.row + dr, op.col + dc) for dr, dc in rng}
            return [e for e in enemies if (e.row, e.col) in cells]
        if getattr(op, "range_shape", None):
            cells = {(op.row + dr, op.col + dc) for dr, dc in op.range_shape}
            return [e for e in enemies if (e.row, e.col) in cells]
        return [e for e in enemies
                if abs(e.row - op.row) <= 2 and abs(e.col - op.col) <= 2]

    def _add_stat_buff(self, key, stat, value, formula=0, unit=None):
        """formula 0 = additive, 3 = multiplicative (game formulaItem)."""
        if value is None:
            return
        unit = unit or self.op
        battle = self.controller.battle
        b = {"key": key, "remaining_ticks": int(self.remaining * 30),
             "layers": 1, "stat": stat, "source": self.op}
        if formula == 3:
            b["mul"] = float(value)
        else:
            b["add"] = float(value)
        battle.add_buff(unit, b)
        self.buffs.append(b)

    def _stack_buff(self, unit, key, stat, per, max_cnt, ticks, formula=3):
        """Stack-on-hit buff: target layer count = min(current+1, max_cnt).
        The buff system keeps max(existing, new) on same-key refresh, so
        we pass the explicit target layer count each hit.  formula 3 = mul
        (percentage ratio), 0 = additive."""
        battle = self.controller.battle
        cur = battle.buffs.get(unit, key)
        lv = min((cur.get("layers", 0) if cur else 0) + 1,
                 max(1, int(max_cnt)))
        b = {"key": key, "remaining_ticks": int(ticks), "layers": lv,
             "source": self.op, "stat": stat}
        if formula == 3:
            b["mul"] = float(per)
        else:
            b["add"] = float(per)
        battle.add_buff(unit, b)
        return lv

    # percentage stats use the multiplicative layer (game skill semantics)
    _PCT_STATS = {"def", "atk", "maxHp", "moveSpeed", "magicResistance"}

    def _apply_prefixed_stat_buffs(self):
        """Skill blackboard keys like ``sk_1[self].def`` / ``sk_1[ally].def``
        apply stat buffs to self and/or allied units in range."""
        bb = self.skill.blackboard
        battle = self.controller.battle
        op = self.op
        for key, val in bb.items():
            tag = None
            for t in ("[self]", "[ally]", "[team]", "[friend]"):
                if t in key:
                    tag = t
                    break
            stat = key.rsplit(".", 1)[-1].strip("]") if "." in key else                 (key.replace(tag, "") if tag else key)
            if tag is None:
                # phase-prefixed self stats: '<skill>[a|b].attack_speed'
                # (e.g. amgoat S1 double-chant +30 attack speed / +30%
                # ATK during the skill window)
                _st_map = {"atk": "atk", "def": "def",
                           "attack_speed": "attackSpeed",
                           "base_attack_time": "baseAttackTime",
                           "max_hp": "maxHp", "move_speed": "moveSpeed",
                           "magic_resistance": "magicResistance"}
                if "." in key and stat in _st_map and val:
                    formula = 3 if stat in self._PCT_STATS else 0
                    self._add_stat_buff("op_skill_" + stat,
                                        _st_map[stat], val,
                                        formula=formula, unit=op)
                continue
            if not val:
                continue
            formula = 3 if stat in self._PCT_STATS else 0
            if tag == "[self]":
                self._add_stat_buff(f"op_skill_{stat}", stat, val,
                                    formula=formula, unit=op)
            else:
                allies = [u for u in list(battle.get_operators()) +
                          list(battle.get_tokens())
                          if not u.dead and u is not op and
                          abs(u.row - op.row) <= 4 and
                          abs(u.col - op.col) <= 4]
                for ally in allies:
                    self._add_stat_buff(f"op_skill_ally_{stat}", stat, val,
                                        formula=formula, unit=ally)

    def tick(self, dt):
        """Per-tick periodic effects: DoT / cost recovery / phased
        intervals (e.g. texas2_s_3[sword].interval sword rain)."""
        bb = self.skill.blackboard
        battle = self.controller.battle
        op = self.op
        # \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S1 \u65e0\u58f0\u6da6\u7269:
        # every 1s (30 ticks, activation-aligned) all friendly units inside
        # the attack range recover element damage = ATK x
        # agoat2_s_1[aura].ep_heal_ratio (2%~8% by rank; infinite window).
        if getattr(self.skill, "skill_id", "") == "skchr_agoat2_1":
            try:
                _ratio = float(
                    bb.get("agoat2_s_1[aura].ep_heal_ratio") or 0.0)
                if _ratio > 0:
                    _last = getattr(self, "_aura_last_tick", None)
                    if _last is None:
                        _last = battle.tick
                        self._aura_last_tick = _last
                    if battle.tick - _last >= 30:
                        _amt = float(op.attributes.get("atk") or 0.0) \
                            * _ratio
                        _cells = {(op.row + dr, op.col + dc)
                                  for dr, dc in (op.range_shape or [])}
                        for u in (list(battle.get_operators()) +
                                  list(battle.get_tokens())):
                            if u.dead or (u.row, u.col) not in _cells:
                                continue
                            battle.buffs.recover_ep(u, _amt, source=op)
                        self._aura_last_tick = battle.tick
            except Exception:
                pass
        interval = float(bb.get("interval") or 0.0)
        frames = max(1, int(round(interval * 30))) if interval > 0 else 0
        if interval > 0 and battle.tick % frames == 0:
            cost = bb.get("cost")
            if cost:
                battle.battle_cost_add(float(cost))
            atk = op.attributes.get("atk")
            scale = float(bb.get("atk_scale") or 0.0)
            ep_ratio = bb.get("ep_damage_ratio")
            for e in self._in_range_enemies():
                if e.dead:
                    continue
                if scale:
                    battle.apply_damage(e, atk * scale,
                                        self._resolve_dmg_type(),
                                        source=op)
                if ep_ratio:
                    battle.add_ep(e, self._resolve_ep_type(),
                                  atk * float(ep_ratio))
        # attack@interval: periodic ability ticks driven by the blackboard
        # (Magellan S1 active bind / Brigid S2 cutting / Tmoris S2
        # per-second damage / MCNist S1 ...).  While the skill is active a
        # bind (frozen_duration) replaces the passive sluggish (Magellan).
        ae = getattr(self, "attack_effects", {}) or {}
        ae_iv = float(ae.get("interval") or 0.0)
        if ae_iv > 0:
            frames = max(1, int(round(ae_iv * 30)))
            anchor = getattr(self, "_iv_anchor", None)
            if anchor is None:
                # continue the passive cycle from deployment (Magellan S1:
                # activating only swaps the effect, the periodic ticker
                # keeps running on the same phase).
                anchor = getattr(self.skill, "_interval_anchor", None)
                if anchor is None:
                    anchor = battle.tick
                    self.skill._interval_anchor = anchor
                self._iv_anchor = anchor
            if battle.tick - anchor >= frames:
                self._iv_anchor = battle.tick
                self.skill._interval_anchor = battle.tick
                root = ae.get("frozen_duration")
                slg = ae.get("sluggish")
                scale = float(ae.get("atk_scale") or 0.0)
                ep_ratio = ae.get("ep_damage_ratio")
                atk = op.attributes.get("atk")
                for e in self._in_range_enemies():
                    if e.dead:
                        continue
                    if scale:
                        battle.apply_damage(e, atk * scale,
                                            self._resolve_dmg_type(),
                                            source=op)
                    if ep_ratio:
                        battle.add_ep(e, self._resolve_ep_type(),
                                      atk * float(ep_ratio))
                    if root:
                        battle.add_abnormal(e, AbnormalFlag.UNMOVABLE,
                                            float(root), source=op)
                    elif slg:
                        battle.add_buff(e, {
                            "key": "op_sluggish_atk",
                            "remaining_ticks": int(float(slg) * 30),
                            "layers": 1, "mul": -0.5,
                            "stat": "moveSpeed", "source": op})
        # ?? S3: keep the mad-cage detect buff (and EP cooldown speed)
        # on every enemy in the expanded range
        if getattr(self.skill, "skill_id", "") == "skchr_phatm2_3":
            self._phatm2_s3_tick()
        # phased intervals ("<prefix>.interval", e.g. mylss_s_1[cost] /
        # texas2_s_3[sword])
        for prefix, pbb in (getattr(self.skill, "phases", {}) or {}).items():
            iv = float(pbb.get("interval") or 0.0)
            if iv <= 0:
                continue
            if battle.tick % max(1, int(round(iv * 30))) != 0:
                continue
            self._run_phase(prefix, pbb)
        # Orchid2 S2 "飞翔瞪射": 3 arrow waves (3/4/5 shots) after liftoff.
        if getattr(self.skill, "skill_id", "") == "skchr_orchd2_2":
            self._orchd2_s2_tick()

    def _is_front_target(self, op, unit):
        """Unit is strictly in front of the operator (facing direction)."""
        dr, dc = {0: (-1, 0), 1: (0, 1), 2: (1, 0),
                  3: (0, -1)}.get(int(getattr(op, "direction", 1) or 1),
                                  (0, 1))
        if dc:
            return (unit.col - op.col) * dc > 0
        return (unit.row - op.row) * dr > 0

    def _orchd2_s2_tick(self):
        """Fire the 3 arrow waves (3/4/5 shots each, atk_scale_loop)
        during the 4.2s liftoff window; the landing burst
        (atk_scale_end) is applied by on_expire."""
        battle = self.controller.battle
        op = self.op
        bb = self.skill.blackboard
        scale_loop = float(bb.get("attack@atk_scale_loop") or 0.0)
        if scale_loop <= 0:
            return
        start = getattr(self, "_orchd2_start_tick", battle.tick)
        elapsed = battle.tick - start
        counts = (3, 4, 5)
        gap = int(1.3 * 30)          # 近似：4.2s 内 3 波均匀 + 降落
        first_at = max(1, int(0.2 * 30))   # 起飞动画 fly_duration
        fired = getattr(self, "_orchd2_waves_fired", 0)
        enemies = [e for e in self._in_range_enemies()
                   if not e.dead and self._is_front_target(op, e)]
        if not enemies:
            return
        atk = op.attributes.get("atk")
        for wi in range(fired, 3):
            if elapsed < first_at + wi * gap:
                break
            count = counts[wi]
            for i in range(count):
                t = enemies[i % len(enemies)]
                battle.apply_damage(t, atk * scale_loop,
                                    DamageType.PHYSICAL, source=op)
            self._orchd2_waves_fired = wi + 1

    def _run_phase(self, prefix, pbb):
        """One periodic phase tick: cost gain, one-time stat buffs, and a
        damage burst (projectile if the skill has one)."""
        battle = self.controller.battle
        op = self.op
        bb = self.skill.blackboard
        cost = pbb.get("cost")
        if cost:
            battle.battle_cost_add(float(cost))
        if prefix not in self._phase_fired:
            self._phase_fired.add(prefix)
            st_map = {"atk": "atk", "def": "def",
                      "attack_speed": "attackSpeed",
                      "base_attack_time": "baseAttackTime",
                      "max_hp": "maxHp"}
            for st_key, st_val in pbb.items():
                if st_key in st_map and st_val is not None:
                    formula = 3 if st_key in ("atk", "def", "max_hp") else 0
                    self._add_stat_buff(
                        "op_skill_phase_" + prefix + "_" + st_key,
                        st_map[st_key], st_val, formula=formula)
        scale = float(pbb.get("atk_scale") or
                      bb.get("atk_scale") or 0.0)
        dmg = pbb.get("damage") or bb.get("damage")
        stun = pbb.get("stun", bb.get("stun"))
        sluggish = pbb.get("sluggish", bb.get("sluggish"))
        ep = pbb.get("ep_damage_ratio", bb.get("ep_damage_ratio"))
        max_target = int(pbb.get("max_target") or bb.get("max_target") or
                         bb.get("attack@max_target") or 1)
        if not (scale or dmg):
            return
        enemies = self._in_range_enemies()
        enemies.sort(key=lambda e: e.hp)
        tgt = enemies if max_target <= 0 else enemies[:max_target]
        pref_params = _operator_prefab_params(
            getattr(self.skill, "skill_id", "") or "")
        proj_key = pref_params.get("_projectileKey") or None
        self._fire_burst(tgt, self._resolve_dmg_type(), scale, dmg,
                         stun, sluggish, ep, 1, proj_key, pref_params, bb,
                         delay_for_cast=False, apply_abnormal=True)

    def on_start(self):
        bb = self.skill.blackboard
        op = self.op
        battle = self.controller.battle
        _sid = getattr(self.skill, "skill_id", "")
        try:
            battle._dispatch_buff_events(op, "ON_SKILL_START",
                                         source=op, target=op)
        except Exception:
            pass
        # stats already provided by the prefab's OWNER buffs (attribute
        # modifiers) must not be applied again from the blackboard, or the
        # effect would be double-counted (e.g. scave S2 atk +20%).
        prefab_stats = set()
        for ccls, bfield, bd, _c in _operator_prefab_buffs(
                getattr(self.skill, "skill_id", "")):
            if ccls == "BuffAbility" or bfield == "_activeBuffs":
                continue
            try:
                from .buff_templates import _ATTR_TYPE_NAMES, _attr_type_int
                for m in ((bd.get("attributes") or {}).get(
                        "attributeModifiers") or []):
                    st = _ATTR_TYPE_NAMES.get(
                        _attr_type_int(m.get("attributeType", 0)))
                    if st:
                        prefab_stats.add(st)
                # template-driven stat modifiers (e.g. def_atten decay)
                for ev in _buff_template_actions(bd).values():
                    for a in (ev or []):
                        if "RemainingRatioToAttributeModifier" in (
                                a.get("$type") or ""):
                            st = _ATTR_TYPE_NAMES.get(_attr_type_int(
                                a.get("_attributeType")))
                            if st:
                                prefab_stats.add(st)
            except Exception:
                pass
        # stat buffs (duration window). Percentage stats (atk/def/max_hp)
        # use the multiplicative layer; flat stats use additive.
        if bb.get("atk") is not None and "atk" not in prefab_stats:
            self._add_stat_buff("op_skill_atk", "atk", bb.get("atk"),
                                formula=3)
        if bb.get("def") is not None and "def" not in prefab_stats:
            self._add_stat_buff("op_skill_def", "def", bb.get("def"),
                                formula=3)
        if bb.get("attack_speed") is not None \
                and "attackSpeed" not in prefab_stats:
            self._add_stat_buff("op_skill_as", "attackSpeed",
                                bb.get("attack_speed"))
        if bb.get("base_attack_time") is not None \
                and "baseAttackTime" not in prefab_stats:
            self._add_stat_buff("op_skill_bat", "baseAttackTime",
                                bb.get("base_attack_time"))
        if bb.get("max_hp") is not None and "maxHp" not in prefab_stats:
            self._add_stat_buff("op_skill_mhp", "maxHp", bb.get("max_hp"),
                                formula=3)
        if bb.get("block_cnt") is not None and "blockCnt" not in prefab_stats:
            self._add_stat_buff("op_skill_block", "blockCnt",
                                bb.get("block_cnt"))
        if bb.get("magic_resistance") is not None \
                and "magicResistance" not in prefab_stats:
            self._add_stat_buff("op_skill_mres", "magicResistance",
                                bb.get("magic_resistance"))
        if bb.get("taunt_level") is not None \
                and "tauntLevel" not in prefab_stats:
            self._add_stat_buff("op_skill_taunt", "tauntLevel",
                                bb.get("taunt_level"))
        if bb.get("hp_recovery_per_sec") is not None \
                and "hpRecoveryPerSec" not in prefab_stats:
            self._add_stat_buff("op_skill_hpr", "hpRecoveryPerSec",
                                bb.get("hp_recovery_per_sec"))
        if bb.get("sp_recovery_per_sec") is not None \
                and "spRecoveryPerSec" not in prefab_stats:
            self._add_stat_buff("op_skill_spr", "spRecoveryPerSec",
                                bb.get("sp_recovery_per_sec"))

        # [self]/[ally] prefixed stat buffs (e.g. bison_s_2 / nian_s_3)
        self._apply_prefixed_stat_buffs()

        # funnel (\u9a6b\u68b0\u672f\u5e08): drones follow the active skill
        # count; a skill with a rangeId (Goldenglow S2 3-18) overrides the
        # attack range while active.
        _ftr = getattr(op, "trait_system", None)
        if _ftr is not None and _ftr.is_funnel():
            try:
                battle._sync_funnel_drones(op)
            except Exception:
                pass
            if getattr(self.skill, "range_id", ""):
                try:
                    from .battle import range_offsets_rotated
                    if getattr(op, "_base_range_shape", None) is None:
                        op._base_range_shape = list(op.range_shape)
                    op.range_shape = range_offsets_rotated(
                        self.skill.range_id, getattr(op, "direction", 1))
                except Exception:
                    pass
        # \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S3 \u706b\u5c71\u56de\u97ff:
        # "\u653b\u51fb\u8303\u56f4\u6269\u5927\u81f3\u6574\u4e2a\u6218\u573a" - the
        # whole map becomes heal range while the skill is active (restored
        # in on_expire via _base_range_shape).
        if _sid == "skchr_agoat2_3":
            try:
                rows = int(getattr(battle.map, "rows", 0) or 0)
                cols = int(getattr(battle.map, "cols", 0) or 0)
                if rows > 0 and cols > 0:
                    if getattr(op, "_base_range_shape", None) is None:
                        op._base_range_shape = list(op.range_shape)
                    op.range_shape = [
                        (r - op.row, c - op.col)
                        for r in range(rows) for c in range(cols)]
                # S3 "\u4e22\u5931\u5168\u90e8\u89c6\u91ce": observable flag;
                # a healer's heal targeting needs no enemy vision, so the
                # gameplay effect is only informational in the sim.
                op._vision_lost = True
            except Exception:
                pass
        # \u6851\u8393 S2 \u5b89\u5168\u533a\u57df: allies inside the attack
        # range take less element damage while the skill is active
        # (blackboard ep_damage_resistance -> percent).  Registered as a
        # skill aura so the per-tick aura sync adds/removes it for allies
        # entering/leaving range and drops it when the skill ends.
        if _sid == "skchr_mberry_2":
            try:
                _res = float(bb.get("ep_damage_resistance") or 0.0)
                op._skill_aura_specs = [{
                    "scope": "range", "stat": "epDamageResistance",
                    "value": _res * 100.0, "layer": "add",
                    "skill_id": _sid, "enabled": True}]
            except Exception:
                pass
        # \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S1 \u65e0\u58f0\u6da6\u7269:
        # activation-aligned 1s cadence for the per-second EP regen aura.
        if _sid == "skchr_agoat2_1":
            self._aura_last_tick = battle.tick

        # \u65b0\u7ea6\u80fd\u5929\u4f7f S2 \u5f00\u706b\u6210\u763e\u75c7:
        # "\u7acb\u5373\u5077\u53d6\u653b\u51fb\u8303\u56f4\u5185 1 \u540d\u53cb\u65b9
        # \u5e72\u5458 {steal} \u70b9\u653b\u51fb\u901f\u5ea6\uff08\u6301\u7eed\u81f3\u6280
        # \u80fd\u7ed3\u675f\u6216\u65b0\u7ea6\u80fd\u5929\u4f7f\u79bb\u573a\uff09"
        # - the stolen ASPD buffs are reclaimed by on_expire /
        # _clear_steal_buffs when the skill ends or she retreats.
        if _sid == "skchr_angel2_2":
            try:
                _st = float(bb.get("steal") or 0.0)
                if _st > 0:
                    _cap = float(bb.get("steal_max") or 0.0) or None
                    allies = [u for u in list(battle.operators) +
                              list(battle.tokens)
                              if u is not op and not getattr(u, "dead", False)
                              and op.range_shape and any(
                                  (op.row + dr, op.col + dc) == (u.row, u.col)
                                  for dr, dc in op.range_shape)]
                    if allies:
                        allies.sort(key=lambda u: getattr(
                            u, "deploy_tick", 0))
                        battle.steal_attribute(
                            op, allies[0], "attackSpeed", _st, _cap,
                            key="angel2_s2")
            except Exception:
                pass

        # ---- instant effects ----
        atk = op.attributes.get("atk")

        # instant deployment cost gain (vanguard charge skills); skipped when
        # the prefab's OWNER buff already carries a ModifyCost action (e.g.
        # scave S2 charge_cost) or the cost is periodic (interval)
        cost = bb.get("cost")
        _prefab_cost = any(
            "ModifyCost" in (a.get("$type") or "")
            for ccls2, bfield2, bd2, _c2 in _operator_prefab_buffs(
                getattr(self.skill, "skill_id", ""))
            if not (ccls2 == "BuffAbility" or bfield2 == "_activeBuffs")
            for ev2 in _buff_template_actions(bd2).values()
            for a in (ev2 or []))
        if cost is not None and not float(bb.get("interval") or 0.0) \
                and not _prefab_cost:
            battle.battle_cost_add(float(cost))

        # healing (heal_scale * atk to self / lowest ally in range)
        heal_scale = bb.get("heal_scale")
        if heal_scale:
            amount = atk * float(heal_scale)
            if _sid == "skchr_rdoc_1":
                # \u533b\u751f S1 \u4ee5\u66b4\u5236\u66b4: heals only the caster
                # immediately at cast (no nearby-ally splash)
                battle.apply_heal(op, amount, source=op)
            elif _sid == "skchr_rdoc_2":
                # \u533b\u751f S2 \u6fc0\u7d20\u624b\u67aa: heal lands with the
                # hormone bullet's first friendly hit, not at cast
                pass
            else:
                battle.apply_heal(op, amount, source=op)
                for ally in list(battle.get_operators()) + list(battle.get_tokens()):
                    if ally is op or ally.dead:
                        continue
                    if abs(ally.row - op.row) <= 2 and abs(ally.col - op.col) <= 2:
                        battle.apply_heal(ally, amount, source=op)

        pref_params = _operator_prefab_params(
            getattr(self.skill, "skill_id", "") or "")
        proj_key = pref_params.get("_projectileKey") or None

        # element damage (ep_damage_ratio * atk) on enemies in range; for
        # projectile skills this lands with the projectile instead.
        ep_ratio = bb.get("ep_damage_ratio")
        if ep_ratio and not proj_key:
            _ep_type = self._resolve_ep_type()
            for e in self._in_range_enemies():
                if e.dead:
                    continue
                battle.add_ep(e, _ep_type, atk * float(ep_ratio))

                # skill damage: atk_scale * atk, optional cnt hits / interval.
        # Target limit: blackboard max_target wins; otherwise descriptions
        # that hit "all enemies" are AOE (0 = unlimited), others single.
        atk_scale = float(bb.get("atk_scale") or 0.0)
        dmg = bb.get("damage")
        _desc = getattr(getattr(self, "skill", None),
                        "description", "") or ""
        _aoe = ("\u6240\u6709\u654c\u4eba" in _desc) or (
            "\u5168\u90e8\u654c\u4eba" in _desc)
        max_target = int(bb.get("max_target") or
                         bb.get("attack@max_target") or (0 if _aoe else 1))
        # ammo skills: cnt/ammo is the ammo count, not burst hits on cast
        if getattr(self, "is_ammo", False):
            hits = 0
        else:
            hits = max(1, int(bb.get("times") or bb.get("cnt") or 1))
        # deploy-phase override: "<skill>.<appear>" blackboard values define
        # the on-cast burst (e.g. alter Texas S3 appear.atk_scale=1.0,
        # appear.stun=1.0, all enemies, two sword-rain hits)
        _phases = getattr(self.skill, "phases", {}) or {}
        _appear = _phases.get("appear")
        _burst_stun = bb.get("stun")
        _burst_sluggish = bb.get("sluggish")
        _burst_ep = bb.get("ep_damage_ratio")
        if _appear is not None:
            atk_scale = float(_appear.get("atk_scale") or atk_scale)
            dmg = _appear.get("damage", dmg)
            _burst_stun = _appear.get("stun", bb.get("stun"))
            _burst_sluggish = _appear.get("sluggish",
                                          bb.get("sluggish"))
            _burst_ep = _appear.get("ep_damage_ratio",
                                    bb.get("ep_damage_ratio"))
            max_target = 0          # appear burst hits all enemies in range
        if (atk_scale or dmg) and not getattr(self, "is_ammo", False):
            enemies = self._in_range_enemies()
            # prioritize lowest hp for skill targets (game default often)
            enemies.sort(key=lambda e: e.hp)
            dmg_type = self._resolve_dmg_type()
            tgt_enemies = enemies if max_target <= 0 \
                else enemies[:max_target]
            # projectile damage lands on hit; instant damage applies now.
            self._fire_burst(tgt_enemies, dmg_type, atk_scale, dmg,
                             _burst_stun, _burst_sluggish, _burst_ep,
                             hits, proj_key, pref_params, bb,
                             delay_for_cast=True, apply_abnormal=False)
# abnormal: stun / sluggish on ALL enemies in range (not
        # target-limited); projectile skills apply these on hit instead.
        stun = _burst_stun
        sluggish = _burst_sluggish
        if (stun or sluggish) and not proj_key:
            for e in self._in_range_enemies():
                if e.dead:
                    continue
                if stun:
                    battle.add_abnormal(e, 0, float(stun))
                if sluggish:
                    # slow: reduce move speed (game sluggish ~ 50-80% slow)
                    battle.add_buff(e, {
                        "key": "op_sluggish", "remaining_ticks":
                        int(float(sluggish) * 30), "layers": 1,
                        "mul": -0.5, "stat": "moveSpeed", "source": op})

        # displacement (push/pull) on all enemies in range
        force = bb.get("force")
        if force is not None:
            for e in self._in_range_enemies():
                if e.dead:
                    continue
                self._displace(e, force, force_source="bb")

        # prefab-bound buffs (operator skill prefab -> buff template).
        # Owner self-buffs go on the caster; target buffs (abnormal flags /
        # attribute modifiers) go to enemies in range.
        from .buff_templates import materialise_buff
        # buff duration fallback: the active skill window (>=1s for
        # degenerate/mode skills with no LevelData duration)
        _skill_dur = max(1.0, float(getattr(self, "remaining", 1.0) or 1.0))
        # BuffAbility buffs whose runActionOnEvent is cast-end / spell-end
        # (AbilityStandard.Event: 1=ON_DETACHED 3=ON_CAST_END 5=ON_SPELL_END)
        # apply when the skill finishes, not at cast.
        _END_EVENTS = {1, 3, 5}
        self.deferred_buffs = []
        for ccls, bfield, bd, _comp in _operator_prefab_buffs(
                getattr(self.skill, "skill_id", "")):
            mbb = dict(bb)
            mbb.setdefault("duration", _skill_dur)
            try:
                if ccls == "BuffAbility":
                    evt = int(_comp.get("_runActionOnEvent", 2) or 2)
                    if evt in _END_EVENTS:
                        self.deferred_buffs.append((bd, mbb))
                        continue
                is_target = (ccls == "BuffAbility" and bfield == "_buffs") \
                    or bfield == "_activeBuffs"
                if proj_key and bfield == "_activeBuffs" and \
                        _comp.get("_projectileKey") and \
                        _projectile_belongs(_sid, _comp.get(
                            "_projectileKey")) and \
                        _comp.get("_damageType") is not None:
                    # Projectile-riding buffs on attack components (abnormal
                    # flags e.g. Texas S2 stun, heal e.g. rdoc S2 hormone
                    # bullet, damage/slow e.g. sleach S2/S3) are applied on
                    # hit by the projectile callback, never materialised at
                    # cast. Non-attack components that happen to carry a
                    # projectile key (e.g. mberry S1 -> projectile_chr_mberry_2)
                    # keep their immediate ally application.
                    continue
                if is_target:
                    # debuffs (abnormal flags) -> enemies in range;
                    # heal-type templates -> allies in range; other target
                    # buffs (charge/switch etc.) need selector parsing -> skip
                    flags = ((bd.get("attributes") or {}).get(
                        "abnormalFlags") or [])
                    if flags:
                        targets = self._in_range_enemies()
                    elif _buff_has_heal_action(bd):
                        targets = [u for u in
                                   list(battle.get_operators()) +
                                   list(battle.get_tokens())
                                   if not u.dead]
                    else:
                        targets = []
                    for t in targets:
                        entry = materialise_buff(battle, t, dict(bd),
                                                 mbb, op)
                        if entry and entry.get("key"):
                            battle.add_buff(t, entry)
                else:
                    # end-of-skill withdrawal buffs (e.g. Amiya suicide) are
                    # applied when the ability finishes, not at cast
                    if getattr(self.skill, "skill_id", "") == \
                            "skchr_agoat2_1" and \
                            bd.get("buffKey") == "agoat2_s_1[aura]":
                        # 纯艾 S1 无声润物: the game's ep_heal_when_trigger
                        # buff is owner-scoped in this emulator and heals by
                        # maxEp x ratio (20/s), but the real aura is ATK x
                        # ep_heal_ratio to every ally in range - implemented
                        # range-wide in tick() below, so skip this wrong
                        # owner-only buff (double-regen / wrong amount).
                        continue
                    starts = _buff_template_actions(bd, "ON_BUFF_START")
                    if any("Withdraw" in (a.get("$type") or "")
                           for a in starts):
                        self.deferred_buffs.append((bd, mbb))
                        continue
                    entry = materialise_buff(battle, op, dict(bd),
                                             mbb, op)
                    if entry and entry.get("key"):
                        battle.add_buff(op, entry)
            except Exception:
                pass

        # skill-placed field tiles (e.g. Thumpy S3 conveyor belt)
        self._place_skill_tiles()

        # Ray (hunter) skill-specific wiring
        _sid = getattr(self.skill, "skill_id", "")
        if _sid == "skchr_rdoc_1":
            self._rdoc_s1_cast()
        elif _sid == "skchr_rdoc_2":
            self._rdoc_s2_fire()
        elif _sid == "skchr_ray_1":
            self._ray_s1_special_bullet()
        elif _sid == "skchr_ray_3":
            # S3: stop attacking until the magazine is full -> empty it and
            # let the shortened reload refill it (reload_interval -1.2).
            op._hunter_ammo = 0
            op._hunter_reloading = False
        # skill attack-range override while active (Ray S2/S3 / ?? S3)
        if _sid in ("skchr_ray_2", "skchr_ray_3", "skchr_phatm2_3") and \
                getattr(self.skill, "range_id", ""):
            try:
                from .battle import range_offsets_rotated
                if getattr(op, "_base_range_shape", None) is None:
                    op._base_range_shape = list(op.range_shape)
                op.range_shape = range_offsets_rotated(
                    self.skill.range_id, getattr(op, "direction", 1))
            except Exception:
                pass
        # ?? S3: prefers enemies that are NOT in element burst recovery
        if _sid == "skchr_phatm2_3":
            op.prefer_unburst = True
        # attack@atk / attack@def / attack@max_hp / attack@block_cnt
        # (positive) activation stat buffs on summon/allied targets.
        self._apply_attack_effect_stat_buffs()
        # Taraxa / Orchid2: liftoff state + attack@base_attack_time.
        self._apply_taraxa_liftoff()
        if _sid == "skchr_orchd2_2":
            self._orchd2_start_tick = battle.tick
            self._orchd2_waves_fired = 0

    def _apply_attack_effect_stat_buffs(self):
        """attack@atk / attack@def / attack@max_hp / attack@block_cnt
        (positive) = activation stat buffs on the skill's targets (summon
        tokens / allies), NOT extra damage.  Self-only activation buffs are
        already provided by the prefab's OWNER buffs (catap2 S2 / kalts
        S1 self part verified), so only summon/allied targets are wired
        here.  Target rules per skill:
          - kalts_1/2/3 Mon3tr, bstalk_2 crabs, necras_3 servant: summons
          - acmedc_2: all medics
          - pallas_3: the ally on the tile directly in front
          - cetsyr_2 / dolris_1: allies inside the attack range (bard
            inspiration values)
        """
        ae = getattr(self, "attack_effects", {}) or {}
        if not ae:
            return
        _sid = getattr(self.skill, "skill_id", "") or ""
        _st_map = {"atk": "atk", "def": "def", "max_hp": "maxHp",
                   "block_cnt": "blockCnt"}
        _vals = {}
        for _k, _v in ae.items():
            if _k not in _st_map or _v is None:
                continue
            try:
                _f = float(_v)
            except (TypeError, ValueError):
                continue
            if _f > 0:
                _vals[_k] = _f
        if not _vals:
            return
        battle = self.controller.battle
        op = self.op
        units = []
        if _sid in ("skchr_kalts_1", "skchr_kalts_2", "skchr_kalts_3",
                    "skchr_bstalk_2", "skchr_necras_3"):
            # summons: Kaltsit Mon3tr / Beanstalk crabs / Necras servant
            units = [t for t in battle.get_tokens()
                     if not t.dead and t.owner is op]
        elif _sid == "skchr_acmedc_2":
            units = [u for u in battle.get_operators()
                     if not u.dead
                     and int(getattr(u, "profession", -1) or -1) == 8]
        elif _sid == "skchr_pallas_3":
            _dr, _dc = {0: (-1, 0), 1: (0, 1), 2: (1, 0),
                        3: (0, -1)}.get(
                int(getattr(op, "direction", 1) or 1), (0, 1))
            _cell = (op.row + _dr, op.col + _dc)
            units = [u for u in list(battle.get_operators()) +
                     list(battle.get_tokens())
                     if not u.dead and (u.row, u.col) == _cell]
        elif _sid in ("skchr_cetsyr_2", "skchr_dolris_1"):
            _cells = {(op.row + _dr, op.col + _dc)
                      for _dr, _dc in (op.range_shape or [])}
            units = [u for u in list(battle.get_operators()) +
                     list(battle.get_tokens())
                     if not u.dead and (u.row, u.col) in _cells]
        elif _sid in ("skchr_taraxa_2", "skchr_oblvns_2"):
            units = [op]       # self activation atk buff (attack@atk)
        for u in units:
            for _k, _v in _vals.items():
                # atk/def/maxHp are percentage ratios (mul layer);
                # blockCnt is a flat +N (add layer).
                _formula = 3 if _k in ("atk", "def", "max_hp") else 0
                self._add_stat_buff("op_skill_ae_" + _k, _st_map[_k],
                                    _v, formula=_formula, unit=u)

    def _apply_taraxa_liftoff(self):
        """Taraxa (风絮) S1/S2 + Orchid2 (兰) S2: liftoff state.  The game
        implements it with the ``taraxa_fly_mode`` buff template whose
        ON_BUFF_START runs ChangeCharBlockMode(_blockMode=FLY) - the
        operator becomes airborne and can block flying enemies; the buff
        template restores the mode on finish.  attack@base_attack_time
        (Taraxa S1 fast 0.2s attack) lives in attack_effects and is
        applied here as a baseAttackTime buff."""
        _sid = getattr(self.skill, "skill_id", "") or ""
        if _sid not in ("skchr_taraxa_1", "skchr_taraxa_2",
                        "skchr_orchd2_2"):
            return
        battle = self.controller.battle
        op = self.op
        ticks = max(1, int(getattr(self, "remaining", 1.0) * 30))
        battle.add_buff(op, {"key": "taraxa_fly_mode",
                             "template_key": "taraxa_fly_mode",
                             "remaining_ticks": ticks,
                             "layers": 1, "source": op,
                             "blackboard": {}})
        ae = getattr(self, "attack_effects", {}) or {}
        bat = ae.get("base_attack_time")
        if bat is not None:
            # attack@base_attack_time is a MULTIPLIER on the attack
            # interval (PRTS: Taraxa S1 攻击间隔大幅度缩短 *0.2), unlike
            # the unprefixed base_attack_time which is a seconds delta.
            # The attribute mul layer is base*(1+mul), so ×0.2 -> -0.8.
            self._add_stat_buff("op_skill_ae_base_attack_time",
                                "baseAttackTime", float(bat) - 1.0,
                                formula=3)

    def _rdoc_s1_cast(self):
        """Doctor S1 \u4ee5\u66b4\u5236\u66b4: instant self-heal (handled in
        the generic heal_scale path), attack interval buff from
        base_attack_time, ammo 31 via attack@trigger_time (consumed by
        on_ammo_attack); nothing further at cast."""
        return

    def _rdoc_s2_fire(self):
        """Doctor S2 \u6fc0\u7d20\u624b\u67aa: fires a straight-line hormone
        bullet (projectile_chr_rdoc_s2, speed 5.0) up to 4 tiles ahead. The
        first unit hit (friendly operator / token or GROUND enemy) stops it:
        allies are healed for atk * heal_scale, ground enemies take no
        damage or effect."""
        battle = self.controller.battle
        op = self.op
        bb = getattr(self.skill, "blackboard", {}) or {}
        scale = float(bb.get("heal_scale") or 3.0)
        _dirs = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        dr, dc = _dirs.get(int(getattr(op, "direction", 1) or 1), (0, 1))
        first = None
        for d in range(1, 5):      # rangeId 4-1: 4 tiles in a straight line
            rr, cc = op.row + dr * d, op.col + dc * d
            if battle.map.tile(rr, cc) is None:
                break
            for u in list(battle.get_operators()) + list(battle.get_tokens()):
                if u is op or u.dead:
                    continue
                if (u.row, u.col) == (rr, cc):
                    first = (u, "ally")
                    break
            if first:
                break
            for e in list(battle.enemies):
                if e.dead or getattr(e, "_motion_mode", 0) != 0:
                    continue     # ground enemies only
                if (e.row, e.col) == (rr, cc):
                    first = (e, "enemy")
                    break
            if first:
                break
        if first is None:
            return
        target, kind = first
        from .projectiles import projectile_speed

        def _hit(battle_, proj):
            tgt = proj.target
            if kind == "ally" and tgt is not None and not tgt.dead:
                battle_.apply_heal(tgt, op.attributes.get("atk") * scale,
                                   source=op)
            battle_.emit(battle_.tick, "rdoc_s2_hit", {
                "unit": op.inst_id,
                "target": tgt.inst_id if tgt is not None else None,
                "kind": kind, "healScale": round(scale, 3)})

        battle.spawn_projectile(op, target, "projectile_chr_rdoc_s2",
                                DamageType.PHYSICAL, atk_scale=0.0,
                                hit_callback=_hit, delay_ticks=0)

    def _ray_s1_special_bullet(self):
        """Ray S1 \u8131\u8eab\u77e2: instant special bullet (no ammo
        consumed), atk*atk_scale physical + push; killing the target makes
        the next reload gain cnt extra bullets."""
        battle = self.controller.battle
        op = self.op
        bb = self.skill.blackboard
        scale = float(bb.get("atk_scale") or 0.0)
        force = bb.get("force")
        cnt = int(float(bb.get("cnt") or 0.0))
        if scale <= 0:
            return
        try:
            from .targeting import HateSystem
            target = HateSystem(battle).operator_target(op)
        except Exception:
            target = None
        if target is None:
            return
        atk = float(op.attributes.get("atk") or 0)
        res = battle.apply_damage(target, atk * scale,
                                  DamageType.PHYSICAL, source=op)
        if force is not None:
            try:
                self._displace(target, force, force_source="bb")
            except Exception:
                pass
        if res.amount > 0 and getattr(target, "dead", False) and cnt > 0:
            op._hunter_next_reload_bonus = int(getattr(
                op, "_hunter_next_reload_bonus", 0) or 0) + cnt
            battle.emit(battle.tick, "hunter_reload_bonus",
                        {"unit": op.inst_id, "bonus": cnt})

    def _place_skill_tiles(self):
        """Skill-placed field tiles, driven by prefab data: Thumpy S3
        ('thumpy[switch_mode_2]' active buff on the OffsetTile ability)
        places a 4-tile portable conveyor belt in front of the operator."""
        sid = getattr(self.skill, "skill_id", "")
        prefab_keys = [bd.get("buffKey")
                       for _ccls, _bf, bd, _c in _operator_prefab_buffs(sid)]
        if "thumpy[switch_mode_2]" not in prefab_keys:
            return
        op = self.op
        bb = self.skill.blackboard
        length = 4     # description: ???? 4 ???????
        dirs = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        dr, dc = dirs.get(int(getattr(op, "direction", 1) or 1), (0, 1))
        positions = [(op.row + dr * i, op.col + dc * i)
                     for i in range(1, length + 1)]
        belt_bb = {
            "conveyor_speed": float(bb.get("conveyor_speed") or 0.8),
            "atk_scale": float(bb.get("atk_scale") or 0.0),
            "interval": float(bb.get("interval") or 1.0),
            "mass_level": float(bb.get("mass_level") or 4.0),
            # erosion on belt damage is attached by Thumpy talent 1 inside
            # the damage output hook, not by the tile itself
            "ep_break_def": bb.get("thumpy[ep_break_water].def"),
        }
        battle = self.controller.battle
        battle.place_operator_skill_tiles(
            op, sid, positions, bb=belt_bb,
            duration=getattr(self, "remaining", 60.0))

    def _phatm2_s3_tick(self):
        """?? S3 \u7a7a\u5267\u573a: refresh the cage-detect buff on enemies
        inside the expanded range every 5 ticks (also drives the +50% EP
        burst-cooldown recovery speed)."""
        battle = self.controller.battle
        op = self.op
        if battle.tick % 5 != 0:
            return
        try:
            cells = {(op.row + dr, op.col + dc)
                     for dr, dc in op.range_shape}
        except Exception:
            return
        for e in list(battle.get_enemies()):
            if e.dead or (e.row, e.col) not in cells:
                continue
            if battle.buffs.get(e, "phatm2_s_3[token]"):
                continue
            battle.add_buff(e, {
                "key": "phatm2_s_3[token]",
                "template_key": "phatm2_s_3[token]",
                "remaining_ticks": 30 * 3600,
                "layers": 1, "source": op,
                "blackboard": {}})

    def on_expire(self):
        battle = self.controller.battle
        try:
            battle._dispatch_buff_events(self.op, "ON_SKILL_FINISH",
                                         source=self.op, target=self.op)
        except Exception:
            pass
        # \u5077\u53d6\u5c5e\u6027\u5f52\u8fd8\uff1askill-end returns every
        # attribute this operator stole (StealAttributeAbility detach).
        try:
            battle._clear_steal_buffs(self.op)
        except Exception:
            pass
        battle.clear_operator_skill_tiles(self.op)
        _sid = getattr(getattr(self, "skill", None), "skill_id", "")
        if _sid == "skchr_phatm2_3":
            self.op.prefer_unburst = False
            for _e in list(battle.get_enemies()):
                for _k in ("phatm2_s_3[token]", "phatm2_s_3[trigger]"):
                    if any(b.get("key") == _k and b.get("source") is self.op
                           for b in _e.buffs):
                        battle.buffs.remove(_e, _k)
        if _sid == "skchr_mberry_2":
            # \u6851\u8393 S2 \u5b89\u5168\u533a\u57df: drop the skill aura
            # registration; the next per-tick aura sync removes the stale
            # epDamageResistance buffs from every ally.
            try:
                self.op._skill_aura_specs = []
            except Exception:
                pass
        if _sid in ("skchr_taraxa_1", "skchr_taraxa_2",
                    "skchr_orchd2_2"):
            # liftoff buff cleanup (template restores block mode on finish)
            battle.buffs.remove(self.op, "taraxa_fly_mode")
            # manual remove does not fire ON_BUFF_FINISH - restore here
            self.op._block_mode = None
        if _sid == "skchr_orchd2_2":
            # 降落：对前方小范围所有敌人造成攻击力 attack@atk_scale_end
            # 的物理伤害（"之后降落并对前方小范围内的所有敌人..."）
            _bb = getattr(self.skill, "blackboard", {}) or {}
            _scale_end = float(_bb.get("attack@atk_scale_end") or 0.0)
            if _scale_end > 0:
                op = self.op
                _atk = op.attributes.get("atk")
                _dr, _dc = {0: (-1, 0), 1: (0, 1), 2: (1, 0),
                            3: (0, -1)}.get(
                    int(getattr(op, "direction", 1) or 1), (0, 1))
                for e in battle.get_enemies():
                    if e.dead:
                        continue
                    _fr = (e.col - op.col) * _dc if _dc \
                        else (e.row - op.row) * _dr
                    _side = abs(e.row - op.row) if _dc else abs(e.col - op.col)
                    # 前方 2 格内（小范围）
                    if _fr > 0 and _side <= 1 and abs(_fr) <= 2:
                        battle.apply_damage(e, _atk * _scale_end,
                                            DamageType.PHYSICAL,
                                            source=op)
        if _sid == "skchr_swire2_3":
            # 主动关闭"千金一掷"：消耗所有金币，每枚金币对前方范围随机
            # 敌人造成 atk×atk_scale 物理伤害并小力向前推开
            _bb = getattr(self.skill, "blackboard", {}) or {}
            _scale = float(_bb.get("atk_scale") or 0.0)
            _coins = getattr(self.op, "_coins", 0)
            if _scale > 0 and _coins > 0:
                op = self.op
                _atk = op.attributes.get("atk")
                _front = [e for e in battle.get_enemies()
                          if not e.dead and self._is_front_target(op, e)]
                for _ in range(_coins):
                    if not _front:
                        break
                    try:
                        _e = battle.rng.choice(_front)
                    except Exception:
                        _e = _front[0]
                    battle.apply_damage(_e, _atk * _scale,
                                        DamageType.PHYSICAL, source=op)
                    try:
                        self._displace(_e, 0, force_source="effect")
                    except Exception:
                        pass
                self.op._coins = 0
        for b in list(self.buffs):
            if b.get("template_key"):
                try:
                    battle.buffs._fire(self.op, b, "ON_BUFF_FINISH",
                                       source=b.get("source"))
                except Exception:
                    pass
            battle.buffs.remove(self.op, b["key"])
        # restore the base attack range overridden by the skill
        _base = getattr(self.op, "_base_range_shape", None)
        if _base is not None:
            self.op.range_shape = _base
            self.op._base_range_shape = None
        self.op._vision_lost = False
        # funnel drones: skill bonus count expires
        _ftr = getattr(self.op, "trait_system", None)
        if _ftr is not None and _ftr.is_funnel():
            try:
                battle._sync_funnel_drones(self.op)
            except Exception:
                pass
        # Ray S3 kill-refund now flows through the ray_s_3[sp] buff
        # template (ON_TARGET_KILLED marks, ON_BUFF_FINISH ModifySp); the
        # earlier manual refund was removed to avoid double payouts.
        # cast-end / spell-end BuffAbility buffs (runActionOnEvent 1/3/5)
        # apply now that the skill has finished
        for bd, mbb in getattr(self, "deferred_buffs", []):
            try:
                from .buff_templates import materialise_buff
                flags = ((bd.get("attributes") or {}).get(
                    "abnormalFlags") or [])
                _starts = _buff_template_actions(bd, "ON_BUFF_START")
                if any("Withdraw" in (a.get("$type") or "")
                       for a in _starts):
                    # end-of-skill withdrawal (e.g. Amiya S3 suicide)
                    targets = [self.op]
                elif flags:
                    targets = self._in_range_enemies()
                elif _buff_has_heal_action(bd):
                    targets = [u for u in list(battle.get_operators()) +
                               list(battle.get_tokens()) if not u.dead]
                else:
                    targets = []
                for t in targets:
                    entry = materialise_buff(battle, t, dict(bd),
                                             dict(mbb), self.op)
                    if entry and entry.get("key"):
                        battle.add_buff(t, entry)
            except Exception:
                pass
