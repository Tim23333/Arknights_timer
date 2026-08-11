"""Buff template engine - interprets buff_template_data event-to-action trees.

The game's buffs are pure data: a buffKey references a template whose
``eventToActions`` maps battle events (ON_BUFF_START / ON_BUFF_FINISH /
ON_BUFF_TRIGGER / ON_TAKE_DAMAGE / ON_CALCULATE_DAMAGE / ON_OUTPUT_DAMAGE
...) to ordered lists of ActionNodes. This module loads
data_buff_templates.json (parsed from the game's buff_template_data.bytes;
see unpack_work/buff_table_scan/parse_buff_templates.py) and executes the
action trees against BattleController helpers.

Node types implemented (suffix after "Nodes+" in $type):
  BlockDamage, AdvancedApplyDamage, NoSourceDamage, ApplyDamageByFixedValue,
  HealViaMaxHpRatio, HealByFixedValue, DamageScale, CreateBuff,
  CreateBuffById, CreateBuffInRange, RemoveBuff,
  RemoveAllStatusResistableBuffs, TriggerAbility, IfElse, IfNot, AlwaysNext,
  CheckContainsBuff, CheckBlackboardContainsKey, EnsureBlackboardDefaultValue,
  AssignBlackboardValue, CreateEffect, PlayAudio (visual -> recorded only).
Unknown node types are recorded and skipped (never fatal).
"""

import io
import itertools
import json
import os

from .consts import AbnormalFlag, DamageType


_CARD_UID_COUNTER = itertools.count(1)

_ABNORMAL_FLAG_ID = {name: getattr(AbnormalFlag, name)
                     for name in dir(AbnormalFlag) if name.isupper()}


def _flag_id(value):
    """Abnormal flag value from int, digit string, or enum name string
    (buff templates store flags as names like 'INVISIBLE')."""
    if isinstance(value, int):
        return value
    s = str(value)
    if s.isdigit():
        return int(s)
    return _ABNORMAL_FLAG_ID.get(s, 0)

_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data_buff_templates.json")
_DATA_TABLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data_buff_table.json")

# ---------------------------------------------------------------------------
# data access
# ---------------------------------------------------------------------------

_templates = None


def load_templates(path=_DATA_FILE):
    global _templates
    if _templates is None:
        with io.open(path, "r", encoding="utf-8") as f:
            _templates = json.load(f)
    return _templates


def template(template_key, path=_DATA_FILE):
    return load_templates(path).get(template_key)


_buff_table = None


def load_buff_table(path=_DATA_TABLE_FILE):
    """buffKey -> BuffData definition (parsed from buff_table352282.bytes)."""
    global _buff_table
    if _buff_table is None:
        with io.open(path, "r", encoding="utf-8") as f:
            _buff_table = json.load(f)
    return _buff_table


def buff_definition(buff_key, path=_DATA_TABLE_FILE):
    return load_buff_table(path).get(buff_key)


# BuffData int-indexed fields (FlatBuffers schema == C# declaration order,
# see dump.cs BuffData / AttributeModifierData). Keys are ints in the JSON.
_BUFF_FIELDS = [
    "attributes", "buffKey", "loadFromDB", "isDurableBuff",
    "isDamageMissable", "isSilenceable", "isStunnable", "isFreezable",
    "isLevitatable", "isGroundBoundable", "statusResistable", "templateKey",
    "disableOverride", "overrideKey", "overrideType", "maxStackCnt",
    "refreshRemainingTimeWhenStackMax", "clearAllStackCntWhenTimeUp",
    "maxValidStackCnt", "independentCharacterSource", "overrideEffectKey",
    "overrideOnEventPriority", "onEventPriority", "audioSignal",
    "lifeTimeType", "takeSnapshotWhenExtend", "durationKey", "lifeTime",
    "triggerLifeType", "triggerCnt", "triggerInterval",
    "waitFirstTriggerInterval", "firstTriggerInterval", "priority",
    "priorityBBKeys", "stripBlackboardParamsWithBuffKey", "blackboard",
    "enableInitDirectionFromSource",
]
_ATTR_FIELDS = ["abnormalFlags", "abnormalImmunes", "abnormalAntis",
                "abnormalCombos", "abnormalComboImmunes",
                "attributeModifiers"]
_MOD_FIELDS = ["attributeType", "formulaItem", "value",
               "loadFromBlackboard", "fetchBaseValueFromSourceEntity"]

_ATTR_TYPE_MAP = {
    "MAX_HP": 0, "ATK": 1, "DEF": 2, "MAGIC_RESISTANCE": 3, "COST": 4,
    "BLOCK_CNT": 5, "MOVE_SPEED": 6, "ATTACK_SPEED": 7, "BASE_ATTACK_TIME": 8,
    "HP_RECOVERY_PER_SEC": 13, "SP_RECOVERY_PER_SEC": 14,
    "MAX_DEPLOY_COUNT": 16, "DEF_PENETRATE": 17,
    "MAGIC_RESIST_PENETRATE": 18, "TAUNT_LEVEL": 20, "RESPAWN_TIME": 21,
    "MASS_LEVEL": 23, "EP_DAMAGE_RESISTANCE": 31, "EP_RESISTANCE": 32,
    "SLOW_DOWN": 36,
}


_FORMULA_MAP = {"ADDITION": 0, "MULTIPLIER": 1, "FINAL_ADDITION": 2,
                "FINAL_SCALER": 3, "FINAL_MULTIPLIER": 3}


def _formula_int(v):
    if isinstance(v, str):
        return _FORMULA_MAP.get(v.strip().upper(), 0)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _attr_type_int(v):
    """Normalise attributeType (int or enum-name string like 'ATK')."""
    if isinstance(v, str):
        return _ATTR_TYPE_MAP.get(v.strip().upper(), 0)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


_ATTR_TYPE_NAMES = {
    0: "maxHp", 1: "atk", 2: "def", 3: "magicResistance", 4: "cost",
    5: "blockCnt", 6: "moveSpeed", 7: "attackSpeed",
    8: "baseAttackTime", 13: "hpRecoveryPerSec", 14: "spRecoveryPerSec",
    16: "maxDeployCount", 17: "defPenetrate",
    18: "magicResistPenetrate", 20: "tauntLevel", 21: "respawnTime",
    23: "massLevel", 31: "epDamageResistance", 32: "epResistance",
    36: "slowDown",
}

_BB_KEY_BY_STAT = {
    "maxhp": "max_hp", "atk": "atk", "def": "def",
    "magicresistance": "magic_resistance", "cost": "cost",
    "blockcnt": "block_cnt", "movespeed": "move_speed",
    "attackspeed": "attack_speed", "baseattacktime": "base_attack_time",
    "hprecoverypersec": "hp_recovery_per_sec",
    "sprecoverypersec": "sp_recovery_per_sec",
    "maxdeploycount": "max_deploy_count",
    "defpenetrate": "def_penetrate",
    "magicresistpenetrate": "magic_resist_penetrate",
    "tauntlevel": "taunt_level", "respawn_time": "respawn_time",
    "masslevel": "mass_level",
}
_ABNORMAL_NAMES = {
    0: "STUNNED", 12: "SILENCED", 16: "FROZEN", 25: "LEVITATE",
    33: "FEARED", 39: "PALSY", 45: "GROUND_BOUND",
}


def named_buff(data):
    """Convert int-indexed BuffData dict (keys may be ints or digit strs)
    to named fields."""
    out = {}
    for i, name in enumerate(_BUFF_FIELDS):
        v = data.get(i, data.get(str(i)))
        if v is not None:
            out[name] = v
    attrs = out.get("attributes")
    if isinstance(attrs, dict):
        na = {}
        for i, name in enumerate(_ATTR_FIELDS):
            v = attrs.get(i, attrs.get(str(i)))
            if v is not None:
                na[name] = v
        if isinstance(na.get("attributeModifiers"), list):
            mods = []
            for m in na["attributeModifiers"]:
                if isinstance(m, dict):
                    nm = {}
                    for i, name in enumerate(_MOD_FIELDS):
                        v = m.get(i, m.get(str(i)))
                        if v is not None:
                            nm[name] = v
                    mods.append(nm)
            na["attributeModifiers"] = mods
        out["attributes"] = na
    bb = out.get("blackboard")
    if isinstance(bb, list):
        out["blackboard"] = {k: v for k, v in bb if k is not None}
    return out


def buff_duration_seconds(buff_data, bb):
    """Resolve a buff's duration: lifeTime > 0 wins, else durationKey in bb,
    else durationKey suffix, else 1s default."""
    life = _num(buff_data.get("lifeTime"), 0.0)
    if life > 0:
        return life
    dkey = buff_data.get("durationKey")
    if dkey:
        v = bb.get(dkey)
        if v is None:
            v = bb.get(str(dkey).replace("[", ".").replace("]", ""))
        if v is not None:
            return _num(v, 1.0)
    # many prefab buffs omit durationKey; the skill blackboard/LevelData
    # carries the duration (e.g. Gravel S1 6s, Amiya S3 30s)
    if bb.get("duration") is not None:
        return _num(bb.get("duration"), 1.0)
    return 1.0


# ---------------------------------------------------------------------------
# node helpers
# ---------------------------------------------------------------------------

def node_class(node):
    t = node.get("$type") or ""
    if "+" in t:
        t = t.split("+", 1)[1]
    if "," in t:
        t = t.split(",", 1)[0]
    return t.strip()


def _num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _targets(battle, spec, owner, source=None, target=None, self_unit=None):
    """Resolve _targetType / _ownerType / _sourceType enums to units."""
    s = (spec or "").upper()
    if s in ("BUFF_OWNER", "OWNER", "SELF"):
        return [self_unit or owner]
    if s in ("SOURCE", "BUFF_SOURCE"):
        return [source] if source is not None else [owner]
    if s in ("TARGET", "MODIFIER_TARGET"):
        return [target] if target is not None else [owner]
    return [owner]


def _source_unit(battle, spec, owner, source=None, target=None):
    s = (spec or "").upper()
    if s in ("BUFF_OWNER", "OWNER", "SELF"):
        return owner
    if s in ("SOURCE", "BUFF_SOURCE", "MODIFIER_SOURCE"):
        return source if source is not None else owner
    if s in ("TARGET", "MODIFIER_TARGET"):
        return target if target is not None else owner
    return owner


_ABNORMAL_FILTER = {"STUNNED": 0, "SILENCED": 12, "UNMOVABLE": 13,
                   "FROZEN": 16, "LEVITATE": 25, "DOZE": 43}
_PROF_NAMES = {"WARRIOR": 1, "SNIPER": 2, "TANK": 4, "MEDIC": 8,
               "SUPPORT": 16, "CASTER": 32, "SPECIAL": 64, "TOKEN": 128,
               "PIONEER": 512}


def _passes_target_options(u, opts):
    """Apply a selector's _targetOptions filters (targetSide / motion /
    category / profession / abnormal) to a unit."""
    if u is None or getattr(u, "dead", False):
        return False
    opts = opts or {}
    side = str(opts.get("targetSide") or "ALL").upper()
    got_side = int(getattr(u, "side", 0) or 0)
    if side == "ALLY" and got_side != 1:
        return False
    if side == "ENEMY" and got_side != 0:
        return False
    motion = str(opts.get("targetMotion") or "ALL").upper()
    mm = int(getattr(u, "_motion_mode", 0) or 0)
    if motion == "WALK" and mm != 0:
        return False
    if motion == "FLY" and mm != 1:
        return False
    cat = str(opts.get("targetCategory") or "").upper()
    if cat:
        cats = [c.strip() for c in cat.split(",") if c.strip()]
        is_token = bool(getattr(u, "token_id", None))
        if cats:
            if is_token:
                if not any(c in ("TRAP_OR_ITEM", "OBSTACLE", "DEFAULT")
                           for c in cats):
                    return False
            elif "DEFAULT" not in cats:
                return False
    prof_mask = str(opts.get("professionMask") or "").upper()
    if prof_mask and prof_mask != "NONE":
        profs = [v for k, v in _PROF_NAMES.items()
                 if k in [x.strip() for x in prof_mask.split(",")]]
        if profs:
            p = int(getattr(u, "profession", 0) or 0)
            if p not in profs:
                return False
    if opts.get("excludeSomeAbnormalFlags"):
        flag = _ABNORMAL_FILTER.get(
            str(opts.get("excludeAbnormalFlag") or "").upper())
        if flag is not None and u.flag(flag):
            return False
    if opts.get("containSomeAbnormalFlags"):
        flag = _ABNORMAL_FILTER.get(
            str(opts.get("containAbnormalFlag") or "").upper())
        if flag is not None and not u.flag(flag):
            return False
    return True


# ---------------------------------------------------------------------------
# damage / attribute helpers (shared with buffs.py semantics)
# ---------------------------------------------------------------------------

def _apply_attribute_modifiers(battle, unit, buff_data, bb, source):
    """Apply a CreateBuff._buff.attributes block onto a unit as modifiers."""
    from .consts import AbnormalFlag
    attrs = buff_data.get("attributes") or {}
    for m in attrs.get("attributeModifiers") or []:
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(m.get("attributeType", 0)))
        if stat:
            stat = stat.lower()
        formula = str(m.get("formulaItem") or "")
        val = m.get("value")
        if m.get("loadFromBlackboard"):
            bkey = str(m.get("blackboardKey") or "")
            if not bkey:
                bkey = _BB_KEY_BY_STAT.get((stat or "").lower(), "")
            val = pbb.get(bkey, val)
        if not stat or val is None:
            continue
        val = _num(val)
        stat_map = {"atk": "atk", "def": "def", "maxhp": "maxHp",
                    "max_hp": "maxHp", "attack_speed": "attackSpeed",
                    "attackinterval": "baseAttackTime",
                    "movespeed": "moveSpeed", "magicresistance":
                    "magicResistance", "blockcnt": "blockCnt",
                    "cost": "cost", "respawn_time": "respawnTime",
                    "tauntlevel": "tauntLevel", "masslevel": "massLevel",
                    "max_deploy_count": "maxDeployCount"}
        stat = stat_map.get(stat, stat)
        layer = "final_mul" if formula.upper() == "FINAL_MULTIPLIER" else \
            ("mul" if formula.upper() in ("MULTIPLIER", "PERCENT") else "add")
        if str(formula).upper() in ("FINAL_SCALER", "FINAL_MULTIPLIER"):
            val = 1.0 + val
        battle.add_buff(unit, {
            "key": buff_data.get("buffKey") or "buff_mod",
            "remaining_ticks": 30 * 3600 if _num(
                buff_data.get("lifeTimeType")) in (0,) or str(
                    buff_data.get("lifeTimeType")).upper() in ("INFINITY",) else
                max(1, int(_num(buff_data.get("lifeTime"), 1.0) * 30)),
            "layers": max(1, int(_num(buff_data.get("maxStackCnt"), 1))),
            layer: val,
            "stat": stat,
            "source": source,
            "template_key": buff_data.get("templateKey") or
            buff_data.get("buffKey"),
            "blackboard": bb,
        })
    for flag in attrs.get("abnormalFlags") or []:
        fid = flag.get("flag") if isinstance(flag, dict) else flag
        t = _num(flag.get("duration") if isinstance(flag, dict) else 0, 1.0)
        battle.add_abnormal(unit, _flag_id(fid), t)
    for combo in attrs.get("abnormalCombos") or []:
        for fid in combo:
            battle.add_abnormal(unit, _flag_id(fid), 1.0)


def materialise_buff(battle, unit, buff_data, bb, source):
    """Apply a BuffData (prefab component or DB entry) to a unit.

    Returns the BuffSystem entry dict. Abnormal flags and attribute
    modifiers are applied directly; template events fire via BuffSystem.
    """
    def _intkey(d):
        return any(isinstance(k, int) or (isinstance(k, str) and k.isdigit())
                   for k in (d or {}))
    if _intkey(buff_data):
        named = named_buff(buff_data)
    else:
        named = buff_data
    if _intkey(named):
        named = named_buff(named)
    attrs = named.get("attributes") or {}
    # stripBlackboardParamsWithBuffKey: buff params arrive namespaced
    # on the skill blackboard as '<buffKey>.<key>' (e.g.
    # dragon_fire.duration / dragon_fire.baseDamage); the buff reads
    # them unprefixed
    pbb = dict(bb)
    _pfx = str(named.get("buffKey") or "") + "."
    if named.get("stripBlackboardParamsWithBuffKey"):
        pbb = {k[len(_pfx):] if k.startswith(_pfx) else k: v
               for k, v in bb.items()}
    duration = buff_duration_seconds(named, pbb)
    for flag in attrs.get("abnormalFlags") or []:
        battle.add_abnormal(unit, _flag_id(flag), duration)
    for m in attrs.get("attributeModifiers") or []:
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(m.get("attributeType", 0)))
        if not stat:
            continue
        val = m.get("value")
        if m.get("loadFromBlackboard"):
            bkey = str(m.get("blackboardKey") or "")
            if not bkey:
                bkey = _BB_KEY_BY_STAT.get((stat or "").lower(), "")
            val = bb.get(bkey, val)
        if val is None:
            continue
        val = _num(val, 0.0)
        formula = _formula_int(m.get("formulaItem", 0))
        layer = "final_mul" if formula == 3 else \
            ("mul" if formula == 1 else
             ("final_add" if formula == 2 else "add"))
        if formula == 3:
            # FINAL_SCALER applies as (1 + value) multiplier
            val = 1.0 + val
        # stat-only entry: deliberately no template_key so template
        # ON_BUFF_START actions (ModifyCost / switch_mode ...) fire exactly
        # once from the main buff entry returned below.
        battle.add_buff(unit, {
            "key": named.get("buffKey") or "buff_mod",
            "remaining_ticks": max(1, int(duration * 30)),
            "layers": max(1, int(_num(named.get("maxStackCnt"), 1))),
            layer: val,
            "stat": stat,
            "source": source,
            "blackboard": pbb,
        })
    tpl_key = named.get("templateKey")
    if not tpl_key or str(tpl_key).lower() in ("empty", "none", ""):
        tpl_key = named.get("buffKey")
    entry = {
        "key": named.get("buffKey") or "buff",
        "remaining_ticks": max(1, int(duration * 30)),
        "layers": max(1, int(_num(named.get("maxStackCnt"), 1))),
        "source": source,
        "template_key": tpl_key,
        "blackboard": pbb,
        "wait_first_trigger": int(named.get("waitFirstTriggerInterval", 1)
                                  or 0),
        "abnormalImmunes": named.get("abnormalImmunes"),
    }
    trig = _num(named.get("triggerInterval"), -1.0)
    if trig > 0:
        entry["_trigger_interval"] = int(trig * 30)
        entry["_trigger_acc"] = 0
    first = _num(named.get("firstTriggerInterval"), -1.0)
    if first > 0:
        entry["_first_trigger_interval"] = int(first * 30)
    tcnt = _num(named.get("triggerCnt"), 0)
    if tcnt > 0:
        entry["_trigger_max"] = int(tcnt)
    return entry


def _embedded_buff(battle, unit, buff_node, bb, source):
    """Materialise the _buff embedded in CreateBuff nodes.

    When the embedded buff has loadFromDB=true (208 template nodes), the
    real definition (abnormal flags / attribute modifiers / durations)
    comes from the global buff_table; embedded fields override the DB.
    """
    b = dict(buff_node.get("_buff") or {})
    key = b.get("buffKey") or "buff"
    if b.get("loadFromDB"):
        db = buff_definition(key)
        if db:
            merged = named_buff(db)
            if b.get("disableOverride"):
                # embedded fields override the DB definition
                for k, v in b.items():
                    if v not in (None, "", 0, [], {}):
                        merged[k] = v
            elif b.get("templateKey") not in (None, "", "empty"):
                merged["templateKey"] = b["templateKey"]
            b = merged
    # abnormal flags + attribute modifiers from the resolved definition
    materialise_buff(battle, unit, b, bb, source)
    dur = buff_duration_seconds(b, bb)
    life = b.get("lifeTimeType")
    if str(life).upper() in ("INFINITY",) or _num(life) == 0 and dur <= 0:
        ticks = 30 * 3600
    else:
        ticks = max(1, int(dur * 30))
    entry = {
        "key": key,
        "remaining_ticks": ticks,
        "layers": max(1, int(_num(b.get("maxStackCnt"), 1))),
        "source": source,
        "template_key": b.get("templateKey") or key,
        "blackboard": bb,
    }
    return entry


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------

class BuffTemplateEngine:
    """Executes buff template action trees."""

    def __init__(self, battle=None):
        self.battle = battle
        # node types already reported as unhandled (dedupe the
        # buff_node_unhandled notifications so the event stream does not
        # flood with identical unknowns)
        self._reported_unhandled = set()

    # ---- public API ------------------------------------------------------
    def dispatch(self, unit, event, template_key, source=None, target=None,
                 damage=None, bb=None):
        """Run a buff template's actions for ``event`` on ``unit``."""
        tpl = template(template_key)
        if not tpl:
            return []
        actions = (tpl.get("eventToActions") or {}).get(event)
        if not actions:
            return []
        ctx = {
            "owner": unit, "source": source, "target": target,
            "damage": damage, "bb": bb or {},
        }
        return self.run_actions(unit, actions, ctx, 0)

    def run_actions(self, unit, actions, ctx, index=0, max_depth=40):
        """Execute a list of action nodes in order (game linear-chain
        gate model: each node passes its boolean result as the gate for the
        next node; IfNot flips the gate; a false gate skips the rest)."""
        out = []
        battle = self.battle
        owner = ctx.get("owner") or unit
        i = index
        guard = 0
        gate = True
        while i < len(actions) and guard < max_depth:
            guard += 1
            node = actions[i]
            cls = node_class(node)
            if cls == "IfNot":
                # IfNot flips the gate even when the previous node failed
                gate = not gate
                out.append({"node": "IfNot", "action": gate})
                i += 1
                continue
            if cls == "AlwaysNext":
                # pass-through: does NOT reset a failed gate (game chain
                # semantics - a false condition still aborts the rest)
                out.append({"node": "AlwaysNext", "action": True})
                i += 1
                continue
            if not gate:
                out.append({"node": cls, "action": "skipped"})
                i += 1
                continue
            handler = getattr(self, "_n_" + cls, None)
            if handler is None:
                if battle is not None and cls not in self._reported_unhandled:
                    self._reported_unhandled.add(cls)
                    try:
                        battle.emit(battle.tick, "buff_node_unhandled",
                                    {"node": cls, "unit": getattr(
                                        owner, "inst_id", None)})
                    except Exception:
                        pass
                out.append({"node": cls, "action": "skipped"})
                i += 1
                continue
            res = handler(owner, node, ctx)
            out.append({"node": cls, "action": res})
            if isinstance(res, bool):
                gate = res
            i += 1
        return out

    # ---- control flow -----------------------------------------------------
    def _n_IfElse(self, owner, node, ctx):
        cond = node.get("_conditionNode")
        ok = False
        if cond:
            ok = bool(self.run_actions(owner, [cond], ctx, 0)[0]["action"])
        branch = node.get("_succeedNodes") if ok else node.get("_failNodes")
        if branch:
            self.run_actions(owner, branch, ctx, 0)
        return ok

    def _n_IfConditions(self, owner, node, ctx):
        conds = node.get("_conditionsNode") or []
        is_and = bool(node.get("_isAnd", True))
        ok = True
        for cond in conds:
            r = bool(self.run_actions(owner, [cond], ctx, 0)[0]["action"])
            if is_and and not r:
                ok = False
                break
            if not is_and and r:
                ok = True
                break
        if not is_and and conds:
            ok = any(bool(self.run_actions(owner, [c], ctx, 0)[0]["action"])
                     for c in conds)
        branch = node.get("_succeedNodes") if ok else node.get("_failNodes")
        if branch:
            self.run_actions(owner, branch, ctx, 0)
        return ok

    def _n_Loop(self, owner, node, ctx):
        """Repeat _loopBody. With _keyMappingList, walk each mapping entry
        (copy source bb -> target bb) and run the body, stopping on success
        when _stopWhenPreviousSucceed (trap_trbox_s / enemy_cnvlap
        try-until-succeed lists). Otherwise loop _loopCnt times or by the
        blackboard count key; degenerate zero-count loops run once."""
        body = node.get("_loopBody") or []
        if not body:
            return True
        bb = ctx.setdefault("bb", {})
        mappings = node.get("_keyMappingList") or []
        stop_on_success = bool(node.get("_stopWhenPreviousSucceed"))
        if mappings:
            for item in mappings:
                for kv in (item.get("mapping") or []):
                    src = kv.get("source")
                    tgt = kv.get("target")
                    if src and tgt:
                        bb[tgt] = bb.get(src)
                res = self.run_actions(owner, body, ctx, 0)
                if stop_on_success and res and \
                        isinstance(res[-1]["action"], bool) and \
                        res[-1]["action"]:
                    break
            return True
        key = node.get("_loopCntKey")
        if key:
            try:
                cnt = int(float(bb.get(key, 0) or 0))
            except (TypeError, ValueError):
                cnt = 0
        else:
            try:
                cnt = int(float(node.get("_loopCnt") or 0))
            except (TypeError, ValueError):
                cnt = 0
        if cnt <= 0:
            cnt = 1
        for _ in range(min(cnt, 100)):
            res = self.run_actions(owner, body, ctx, 0)
            if stop_on_success and res and \
                    isinstance(res[-1]["action"], bool) and \
                    res[-1]["action"]:
                break
        return True

    def _n_IfNot(self, owner, node, ctx):
        return True  # handled by run_actions as an inversion marker

    def _n_IfTargetSide(self, owner, node, ctx):
        """Gate: the resolved unit belongs to _sideMask (ALLY/ENEMY).

        Game semantics: a side mismatch fails the gate, aborting the rest
        of the chain (e.g. tinman S2 area buff heals allies on
        ON_BUFF_START and damages enemies on ON_BUFF_TRIGGER).
        """
        t = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if t is None or getattr(t, "dead", False):
            return False
        mask = str(node.get("_sideMask") or "ENEMY").upper()
        if mask == "ALLY":
            return t.side == 1
        if mask == "ENEMY":
            return t.side == 0
        # NEUTRAL / unknown masks: any alive unit passes
        return True

    def _n_CheckAbnormalFlags(self, owner, node, ctx):
        """Gate: the resolved unit has ANY of the abnormal flags."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        flags = node.get("_abnormalFlags") or []
        return any(bool(getattr(u, "flag", lambda f: False)(
            _flag_id(f))) for f in flags)

    def _n_CheckCanUseAtkOrCbt(self, owner, node, ctx):
        """Gate: the resolved unit can attack / use combat (not stunned,
        frozen, levitated or palsied - the same control flags the battle
        controller uses to pause attack timers)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or getattr(u, "dead", False):
            return False
        if any(u.flag(f) for f in (0, 16, 25, 39)):
            return False
        try:
            from .consts import EnemyState
            st = getattr(u, "state", None)
            if st in (EnemyState.STUN, EnemyState.FROZEN,
                      EnemyState.LEVITATE, EnemyState.PALSY):
                return False
        except Exception:
            pass
        return True

    def _n_CheckBuildCnt(self, owner, node, ctx):
        """Gate: the current deployed operator count compares to
        _checkBuildCnt via _condType (LE/GE/LT/GT/EQ/NE). Used by
        first/second-deploy talents (attr_up_after_first_deploy counts
        <= 1, add_sp_since_secondary_deployed counts > 1)."""
        battle = self.battle
        if not battle:
            return False
        n = len([o for o in battle.operators
                 if not getattr(o, "dead", False)])
        target = int(_num(node.get("_checkBuildCnt"), 1.0))
        cond = str(node.get("_condType") or "EQ").upper()
        if cond in ("LE", "<="):
            return n <= target
        if cond in ("GE", ">="):
            return n >= target
        if cond in ("LT", "<"):
            return n < target
        if cond in ("GT", ">"):
            return n > target
        if cond in ("NE", "!=", "NOT_EQ"):
            return n != target
        return n == target

    def _n_CheckRootTileAdvBuildableMask(self, owner, node, ctx):
        """Gate: the owner's root tile advancedBuildableMask contains the
        requested mask (night-map deploy rules). The internal night
        override stores 1 for NIGHT / None for DEFAULT; base level masks
        pass through unchanged."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        t = battle.map.tile(int(getattr(u, "row", 0) or 0),
                            int(getattr(u, "col", 0) or 0))
        if t is None:
            return False
        eff = t._advanced_buildable_override
        if eff is None:
            eff = t.advanced_buildable_mask
        try:
            eff_i = int(eff or 0)
        except (TypeError, ValueError):
            eff_i = 0
        mask_name = str(node.get("_buildableMask") or "DEFAULT").upper()
        if mask_name == "NIGHT":
            return bool(eff_i & 1)
        return eff_i & 1 == 0

    def _n_CreateBuffUseAbilitySelector(self, owner, node, ctx):
        """Create the embedded buff on the resolved ability target
        (selector approximation: target, else owner)."""
        battle = self.battle
        if not battle:
            return False
        bd = dict(node.get("_buff") or {})
        if not bd.get("buffKey"):
            return False
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = dict(ctx.get("bb") or {})
        entry = materialise_buff(battle, u, bd, bb, owner)
        if entry and entry.get("key"):
            battle.add_buff(u, entry)
            return True
        return False

    def _n_CreateBuffToCertainSideUnits(self, owner, node, ctx):
        """Create the embedded buff on all units of the given side."""
        battle = self.battle
        if not battle:
            return False
        bd = dict(node.get("_buff") or {})
        if not bd.get("buffKey"):
            return False
        side = str(node.get("_sideMask") or "ALL").upper()
        bb = dict(ctx.get("bb") or {})
        hit = 0
        for u in (list(battle.get_enemies()) +
                  list(battle.get_operators()) +
                  list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if side == "ENEMY" and u.side != 0:
                continue
            if side == "ALLY" and u.side != 1:
                continue
            entry = materialise_buff(battle, u, bd, bb, owner)
            if entry and entry.get("key"):
                battle.add_buff(u, entry)
                hit += 1
        return hit > 0

    def _n_CreateNoSourceBuff(self, owner, node, ctx):
        """Create the embedded buff on _buffOwner with no source (game
        CreateNoSourceBuff: stage-mechanic buffs like env_act46side[no_skill]
        are not attributed to any unit)."""
        battle = self.battle
        if not battle:
            return False
        bd = dict(node.get("_buff") or {})
        if not bd.get("buffKey"):
            return False
        tgt = _source_unit(battle, node.get("_buffOwner") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            tgt = owner
        entry = _embedded_buff(battle, tgt, node, dict(ctx.get("bb") or {}),
                               None)
        if entry and entry.get("key"):
            battle.add_buff(tgt, entry)
            return True
        return False

    def _n_CreateBuffUseHostAsSource(self, owner, node, ctx):
        """Create _buffData on the resolved target with the buff template's
        host (owner) as its source. loadFromDB definitions are merged like
        CreateBuff (embedded fields override the DB when disableOverride).
        _isDerivedBuff marks the new buff as a child of the current buff."""
        battle = self.battle
        if not battle:
            return False
        bd = dict(node.get("_buffData") or {})
        if not bd.get("buffKey"):
            return False
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            tgt = owner
        entry = _embedded_buff(battle, tgt, {"_buff": bd},
                               dict(ctx.get("bb") or {}), owner)
        if node.get("_isDerivedBuff"):
            parent = (ctx.get("bb") or {}).get("_buff_entry") or {}
            pkey = parent.get("key")
            if pkey:
                entry["derived_from"] = pkey
        if entry and entry.get("key"):
            battle.add_buff(tgt, entry)
            return True
        return False

    def _n_AttachAsDerivedBuff(self, owner, node, ctx):
        """Attach the embedded _buff to the resolved unit as a derived buff
        of _buffKey (or the current buff when the key is absent). With
        _finishDerivedBuffIfParentFinish the derived buff is removed
        whenever its parent is removed/expires (enemy_trcerb eat mark,
        enemy_xdmon shield fx)."""
        battle = self.battle
        if not battle:
            return False
        bd = dict(node.get("_buff") or {})
        if not bd.get("buffKey"):
            return False
        tgt = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            tgt = owner
        parent = (ctx.get("bb") or {}).get("_buff_entry") or {}
        pkey = node.get("_buffKey") or parent.get("key")
        entry = _embedded_buff(battle, tgt, node, dict(ctx.get("bb") or {}),
                               owner)
        if pkey and node.get("_finishDerivedBuffIfParentFinish", True):
            entry["derived_from"] = pkey
        if entry and entry.get("key"):
            battle.add_buff(tgt, entry)
            return True
        return False

    def _n_FilterDamageModifer(self, owner, node, ctx):
        """Gate: the damage event's type matches _damageMask (and
        _attackTypeFilter when _filterAttackType)."""
        dmg = ctx.get("damage")
        if dmg is None:
            return True
        if node.get("_filterDamageType"):
            mask = str(node.get("_damageMask") or "").upper()
            dtype = str(dmg.get("type") or "").upper()
            if mask and mask not in ("NONE",) and mask != dtype:
                return False
        return True

    def _n_CheckAbnormalFlag(self, owner, node, ctx):
        """Gate: the resolved unit has (or lacks when _isUnset)
        the abnormal flag."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        fid = _flag_id(node.get("_abnormalFlag") or 0)
        has = bool(getattr(u, "flag", lambda f: False)(fid))
        return (not has) if bool(node.get("_isUnset")) else has

    def _n_IsBlackboardZero(self, owner, node, ctx):
        """Gate: the blackboard variable is zero / falsy."""
        bb = ctx.get("bb") or {}
        key = node.get("_var") or node.get("_blackboardKey") or ""
        try:
            return _num(bb.get(key), 0.0) == 0.0
        except (TypeError, ValueError):
            return not bb.get(key)

    def _n_IfTarget(self, owner, node, ctx):
        """Gate: the resolved target exists (and is alive when
        _checkTargetAlive). Other target filters approximated as pass."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        if node.get("_checkTargetAlive") and getattr(u, "dead", False):
            return False
        return True

    def _n_FilterByBuffStackCount(self, owner, node, ctx):
        """Gate: the stack count of a buff on the resolved unit matches
        _stackCount (or bb _stackCountKey) by _condType."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_buffKey") or ""
        want = node.get("_stackCount")
        if want is None and node.get("_stackCountKey"):
            want = bb.get(node.get("_stackCountKey"))
        try:
            want = int(float(want))
        except (TypeError, ValueError):
            want = 0
        entry = battle.buffs.get(u, key) if key else None
        got = int((entry or {}).get("layers", 0) or 0)
        cond = str(node.get("_condType") or "EQUALS").upper()
        if cond in ("EQUALS", "EQ"):
            return got == want
        if cond == "NE":
            return got != want
        if cond == "GT":
            return got > want
        if cond == "LT":
            return got < want
        if cond == "GE":
            return got >= want
        if cond == "LE":
            return got <= want
        return True

    def _n_FilterByTargetHpRatio(self, owner, node, ctx):
        """Gate: the resolved unit's hp/maxHp compares against _value."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        mx = float(getattr(u, "max_hp", 0.0) or 0.0)
        if mx <= 0:
            return False
        ratio = float(getattr(u, "hp", 0.0) or 0.0) / mx
        want = _num(node.get("_value"), 0.0)
        cond = str(node.get("_condType") or "LT").upper()
        if cond == "LT":
            return ratio < want
        if cond == "GT":
            return ratio > want
        if cond == "LE":
            return ratio <= want
        if cond == "GE":
            return ratio >= want
        if cond in ("EQUALS", "EQ"):
            return ratio == want
        return True

    def _n_FilterByTargetAttribute(self, owner, node, ctx):
        """Gate: the resolved unit's attribute compares against _value
        (condType LE/GE/LT/GT/EQ, e.g. ensure_block BLOCK_CNT<=0)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return True
        attrs = getattr(u, "attributes", None)
        got = None
        if attrs is not None and hasattr(attrs, "get"):
            got = attrs.get(stat)
        if got is None:
            got = getattr(u, stat, None)
        if got is None:
            got = getattr(u, _BB_KEY_BY_STAT.get(stat.lower(), stat), None)
        if got is None:
            return True
        got = _num(got)
        use_f = bool(node.get("_useFloat"))
        want = _num(node.get("_valueFP") if use_f else node.get("_value"), 0.0)
        cond = str(node.get("_condType") or "EQ").upper()
        if cond == "LT":
            return got < want
        if cond == "GT":
            return got > want
        if cond == "LE":
            return got <= want
        if cond == "GE":
            return got >= want
        if cond in ("EQUALS", "EQ", "=="):
            return got == want
        return True

    def _n_Dice(self, owner, node, ctx):
        """Gate: random chance against bb _probKey (battle RNG)."""
        battle = self.battle
        if not battle or not hasattr(battle, "rng"):
            return True
        bb = ctx.get("bb") or {}
        prob = _num(bb.get(node.get("_probKey") or "prob"), 1.0)
        return battle.rng.chance(max(0.0, min(1.0, prob)))

    def _n_CheckContainsDerviedBuff(self, owner, node, ctx):
        """Gate: the resolved unit carries the (derived) buff key."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        key = node.get("_derviedBuffKey") or node.get("_buffKey") or ""
        if u is None or not battle or not key:
            return False
        return battle.buffs.get(u, key) is not None

    def _n_CheckUnitCurrentMode(self, owner, node, ctx):
        """Gate: the resolved unit's mode index equals _checkCurModeIndex."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        want = node.get("_checkCurModeIndex")
        try:
            want = int(float(want))
        except (TypeError, ValueError):
            want = 0
        return int(getattr(u, "mode_index", 0) or 0) == want

    def _n_CheckUnitEnemyId(self, owner, node, ctx):
        """Gate: the resolved unit's enemy_key matches (delegates to
        CheckEnemyId)."""
        return self._n_CheckEnemyId(owner, node, ctx)

    def _n_CheckEnemyId(self, owner, node, ctx):
        """Gate: the resolved unit's enemy_key is (or is not when
        _isUnset) in _filterIds."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        ids = node.get("_filterIds") or []
        has = bool(u is not None and
                   getattr(u, "enemy_key", "") in ids)
        return (not has) if bool(node.get("_isUnset")) else has

    def _n_CheckFilterTag(self, owner, node, ctx):
        """Gate: the resolved unit carries the tag name (approximated by
        scanning the unit's tags / enemy data description)."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        tag = str(node.get("_tag") or node.get("_filterTag") or "").upper()
        if not tag:
            return True
        tags = [str(t).upper() for t in
                (getattr(u, "tags", None) or getattr(u, "_tags", None) or [])]
        return tag in tags

    def _n_CheckUnitAlive(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_ownerType") or
                         node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        return bool(u is not None and not getattr(u, "dead", False))

    def _n_CheckBlocked(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        return bool(u is not None and getattr(u, "blocked_by", None)
                    is not None)

    def _n_FilterByBlackboardValue(self, owner, node, ctx):
        """Gate: compare a blackboard value against _valueToCompare
        with _condType (EQUALS/NE/GT/LT/GE/LE)."""
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey") or ""
        val = bb.get(key)
        cmpv = _num(node.get("_valueToCompare"), 0.0)
        try:
            fv = float(val)
        except (TypeError, ValueError):
            fv = 0.0
        cond = str(node.get("_condType") or "EQUALS").upper()
        if cond in ("EQUALS", "EQ"):
            return fv == cmpv
        if cond == "NE":
            return fv != cmpv
        if cond == "GT":
            return fv > cmpv
        if cond == "LT":
            return fv < cmpv
        if cond == "GE":
            return fv >= cmpv
        if cond == "LE":
            return fv <= cmpv
        return True

    def _n_AtkScaleUp(self, owner, node, ctx):
        """Set the attack-scale blackboard key (default 1.0) for the
        ongoing ability; overwrites only when _overwriteAtkScale."""
        bb = ctx.get("bb")
        if bb is None:
            return True
        key = node.get("_atkScaleKey") or "atk_scale"
        if key in bb and not node.get("_overwriteAtkScale"):
            return True
        val = node.get("_value")
        if val is None:
            val = node.get("_defaultValue", 1.0)
        try:
            bb[key] = float(val)
        except (TypeError, ValueError):
            bb[key] = 1.0
        return True

    def _n_FixedValueHeal(self, owner, node, ctx):
        """Heal the resolved target by a fixed blackboard value."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None or getattr(u, "dead", False):
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_healValueKey") or "value"
        amount = _num(bb.get(key), 0.0)
        if amount > 0:
            battle.apply_heal(u, amount, source=owner,
                              ignore_heal_free=bool(node.get(
                                  "_ignoreHealFree")))
        return True

    def _n_CheckAbnormalImmune(self, owner, node, ctx):
        """Gate: the resolved unit is immune (or not, _isUnset) to the
        abnormal flag."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        flag = str(node.get("_abnormalFlag") or "").upper()
        field = {"STUNNED": "stunImmune", "FROZEN": "frozenImmune",
                 "SILENCED": "silenceImmune", "LEVITATE": "levitateImmune",
                 "FEARED": "fearedImmune", "PALSY": "palsyImmune"}.get(flag)
        immune = False
        if field and hasattr(u, "attributes"):
            immune = bool(u.attributes.immune(field))
        return (not immune) if bool(node.get("_isUnset")) else immune

    def _n_ReleaseFromBlocker(self, owner, node, ctx):
        """Release the resolved unit from its blocker."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_target"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        blk = getattr(u, "blocked_by", None)
        if blk is not None:
            if hasattr(blk, "remove_blockee"):
                blk.remove_blockee(u)
            u.blocked_by = None
            from .consts import EnemyState
            if getattr(u, "state", None) == EnemyState.COMBAT:
                u.state = EnemyState.MOVE
            return True
        return False

    def _n_IfEnemyIsMovingBySelf(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        from .consts import EnemyState
        return getattr(u, "state", None) == EnemyState.MOVE and \
            getattr(u, "blocked_by", None) is None and \
            getattr(u, "displacement", None) is None

    def _n_CreateBuffInCircleRange(self, owner, node, ctx):
        """Create the embedded buffs on all units of the target side
        within the circle range of the source."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        radius = _num(node.get("_rangeRadius"), None)
        if radius is None:
            radius = _num(bb.get("range_radius"), 1.5)
        opts = node.get("_targetOptions") or {}
        buffs = node.get("_buffs") or []
        if not buffs:
            return False
        hit = 0
        for u in (list(battle.get_enemies()) +
                  list(battle.get_operators()) +
                  list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if not _passes_target_options(u, opts):
                continue
            if abs(u.row - src.row) > radius or \
                    abs(u.col - src.col) > radius:
                continue
            for bd in buffs:
                if not isinstance(bd, dict) or not bd.get("buffKey"):
                    continue
                try:
                    entry = materialise_buff(battle, u, dict(bd), bb, owner)
                    if entry and entry.get("key"):
                        battle.add_buff(u, entry)
                        hit += 1
                except Exception:
                    pass
        return hit > 0

    def _n_CreateBuffUseTargetAsSource(self, owner, node, ctx):
        """Create the embedded buff using the target as the source (apply
        on the target)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        bd = dict(node.get("_buff") or {})
        if u is None or not bd.get("buffKey"):
            return False
        bb = dict(ctx.get("bb") or {})
        entry = materialise_buff(battle, u, bd, bb, u)
        if entry and entry.get("key"):
            battle.add_buff(u, entry)
            return True
        return False

    def _n_AddAbilityBlackboard(self, owner, node, ctx):
        """Add a chain-blackboard value into an ability's blackboard key."""
        sc = getattr(owner, "skill_controller", None)
        if sc is None:
            return False
        bb = ctx.get("bb") or {}
        keys = [k.strip() for k in str(
            node.get("_blackboardKeys") or "").split(",") if k.strip()]
        add_key = node.get("_addBlackboardKey") or ""
        add_val = _num(bb.get(add_key), 0.0) if add_key else 0.0
        found = False
        for s in getattr(sc, "skills", None) or []:
            for k in keys:
                cur = _num(s.blackboard.get(k), 0.0)
                s.blackboard[k] = cur - add_val if node.get("_isMinus") \
                    else cur + add_val
                found = True
        return found

    def _n_AttachAsDerivedBuffById(self, owner, node, ctx):
        """Attach a DB buff by key onto the source as a derived buff."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        key = node.get("_buffKey") or ""
        if src is None or not key:
            return False
        db = buff_definition(key)
        bb = dict(ctx.get("bb") or {})
        if db:
            entry = materialise_buff(battle, src, named_buff(db), bb, owner)
        else:
            entry = materialise_buff(battle, src,
                                     {"buffKey": key, "templateKey": key,
                                      "attributes": {}, "maxStackCnt": 1},
                                     bb, owner)
        if entry and entry.get("key"):
            battle.add_buff(src, entry)
            return True
        return False

    def _n_CreateBuffToBlockee(self, owner, node, ctx):
        """Create the embedded buff on the resolved unit's blockees."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        bd = dict(node.get("_buff") or {})
        if u is None or not bd.get("buffKey"):
            return False
        bb = dict(ctx.get("bb") or {})
        hit = 0
        for blk in list(getattr(u, "blocked_enemies", None) or []):
            if getattr(blk, "dead", False):
                continue
            entry = materialise_buff(battle, blk, bd, bb, owner)
            if entry and entry.get("key"):
                battle.add_buff(blk, entry)
                hit += 1
        return hit > 0

    def _n_InterruptCharacterSkill(self, owner, node, ctx):
        """Interrupt the resolved unit's active skill."""
        u = _source_unit(self.battle, node.get("_charFrom"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is not None and hasattr(sc, "interrupt_active"):
            try:
                sc.interrupt_active()
                return True
            except Exception:
                pass
        return False

    def _n_IsElementDamage(self, owner, node, ctx):
        """Gate: the damage event is element damage."""
        dmg = ctx.get("damage")
        return bool(dmg is not None and
                    str(dmg.get("type", "")).upper() in ("ELEMENT", "EP"))

    def _n_SetBodyDirection(self, owner, node, ctx):
        """Set the resolved unit's facing direction."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        want = str(node.get("_direction") or "").upper()
        mapping = {"UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3}
        if want in mapping:
            u.direction = mapping[want]
        return True

    def _n_IsBlackboardEqualWithString(self, owner, node, ctx):
        bb = ctx.get("bb") or {}
        var = node.get("_var") or ""
        val = bb.get(var)
        want = node.get("_compareValue")
        if node.get("_compareBBKey"):
            want = bb.get(node.get("_compareBBKey"))
        return str(val) == str(want)

    def _n_CheckCurrentTileKey(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        t = battle.get_tile(getattr(u, "row", 0), getattr(u, "col", 0))
        key = t.tile_key if t is not None else ""
        hit = key in (node.get("_tileKey") or [])
        return (not hit) if bool(node.get("_isExclude")) else hit

    def _n_CheckMotionMode(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        mode = str(node.get("_mode") or "WALK").upper()
        return int(getattr(u, "_motion_mode", 0) or 0) == \
            (1 if mode == "FLY" else 0)

    def _n_FilterByGlobalBlackboard(self, owner, node, ctx):
        """Gate: chain-blackboard value compares against _valueToCompare
        (global approximation)."""
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey") or ""
        try:
            val = float(bb.get(key))
        except (TypeError, ValueError):
            return False
        want = _num(node.get("_valueToCompare"), 0.0)
        cond = str(node.get("_condType") or "GE").upper()
        if cond in ("GE",):
            return val >= want
        if cond == "LE":
            return val <= want
        if cond == "GT":
            return val > want
        if cond == "LT":
            return val < want
        if cond in ("EQUALS", "EQ"):
            return val == want
        return True

    def _n_IfTargetEqual(self, owner, node, ctx):
        """Gate: the two resolved targets are the same unit."""
        t1 = _source_unit(self.battle, node.get("_target1"), owner,
                          ctx.get("source"), ctx.get("target"))
        t2 = _source_unit(self.battle, node.get("_target2"), owner,
                          ctx.get("source"), ctx.get("target"))
        if t1 is None and t2 is None:
            return bool(node.get("_equalIfBothNull"))
        return t1 is not None and t1 is t2

    def _n_Evade(self, owner, node, ctx):
        """Gate: the damage event type falls in _damageMask (evade)."""
        dmg = ctx.get("damage")
        if dmg is None:
            return False
        dt = str(dmg.get("type", "")).upper()
        mask = str(node.get("_damageMask") or "ALL").upper()
        if mask in ("ALL", "NONE"):
            return mask == "ALL"
        if mask in ("PHYSICAL_AND_MAGICAL", "PHYSICAL_OR_MAGICAL"):
            return dt in ("PHYSICAL", "MAGICAL")
        return dt == mask

    def _n_CreateBuffToHost(self, owner, node, ctx):
        """Create the embedded buff on the host (source)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        bd = dict(node.get("_buffData") or {})
        if src is None or not bd.get("buffKey"):
            return False
        bb = dict(ctx.get("bb") or {})
        entry = materialise_buff(battle, src, bd, bb, owner)
        if entry and entry.get("key"):
            battle.add_buff(src, entry)
            return True
        return False

    def _n_CompareCharSkillAvailableCnt(self, owner, node, ctx):
        """Gate: the unit has at least _count available skills."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is None:
            return False
        avail = 0
        for s in getattr(sc, "skills", None) or []:
            if getattr(s, "cooldown_remaining", 0.0) <= 0 and \
                    not getattr(s, "is_used_up", False):
                avail += 1
        want = int(node.get("_count") or 1)
        cond = str(node.get("_condType") or "GE").upper()
        if cond == "GE":
            return avail >= want
        if cond == "LE":
            return avail <= want
        if cond == "GT":
            return avail > want
        return avail == want

    def _n_VertifyTarget(self, owner, node, ctx):
        """Gate: the resolved target matches the targetOptions side."""
        u = _source_unit(self.battle, node.get("_target"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        opts = node.get("_targetOptions") or {}
        side = str(opts.get("targetSide") or "ALL").upper()
        if side == "ENEMY" and u.side != 0:
            return False
        if side == "ALLY" and u.side != 1:
            return False
        return True

    def _n_FilterAbilityName(self, owner, node, ctx):
        """Gate: the ability name matches (approx: owner's current skill)."""
        want = node.get("_abilityName") or ""
        if not want:
            return True
        sc = getattr(owner, "skill_controller", None)
        if sc is None or sc.casting is None:
            return True
        return getattr(getattr(sc.casting, "skill", None),
                       "prefab_key", "") == want

    def _n_UpdateAbilityCoolDown(self, owner, node, ctx):
        """Set a skill's cooldown remaining from the chain blackboard."""
        u = _source_unit(self.battle, node.get("_ownerType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is None:
            return False
        name = node.get("_abilityName") or ""
        bb = ctx.get("bb") or {}
        ck = node.get("_coolDownKey") or ""
        val = _num(bb.get(ck), None) if ck else None
        for s in getattr(sc, "skills", None) or []:
            if name and s.prefab_key != name:
                continue
            if val is not None:
                s.cooldown_remaining = val
            return True
        return False

    def _n_TriggerSkill(self, owner, node, ctx):
        """Trigger a skill by name (delegates to TriggerEnemySkill)."""
        return self._n_TriggerEnemySkill(owner, node, ctx)

    def _n_TriggerAbilityUseSelector(self, owner, node, ctx):
        """Trigger an ability by name on the resolved unit."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        name = node.get("_abilityName") or ""
        if u is None or not name:
            return False
        if battle:
            battle.emit(battle.tick, "skill_trigger",
                        {"unit": getattr(u, "inst_id", None),
                         "skill": name})
        sc = getattr(u, "skill_controller", None)
        if sc is not None and hasattr(sc, "force_trigger"):
            try:
                sc.force_trigger(name)
            except Exception:
                pass
        return True

    def _n_AdvancedApplyHeal(self, owner, node, ctx):
        """Heal the resolved target by source atk x heal_scale."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        if tgt is None or getattr(tgt, "dead", False):
            return False
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        key = node.get("_healScaleKey") or "heal_scale"
        scale = _num(bb.get(key), 1.0)
        atk = _num(getattr(src, "attributes", None) and
                   src.attributes.get("atk"), 0.0)
        amount = atk * scale
        if node.get("_useDynamicVar"):
            # dynamic var = the source's attribute cached at buff application
            # (AssignAttributeAsDynamicVarToBB writes bb["dynamic"]); heal
            # amount = dynamic x heal_scale (e.g. \u7eaf\u70c1 T1 \u6c29\u6c33)
            amount = _num(bb.get("dynamic"), 0.0) * scale
        suk = node.get("_scaleUpByBlackboardKey")
        if suk:
            amount *= _num(bb.get(suk), 1.0)
        if amount > 0:
            # template-driven heals carry their own element recovery
            # (FixedValueElementHeal / ApplyElementHeal); the wandermedic
            # trait's atk x 50% EP hook belongs to normal-attack heals only,
            # otherwise HoTs (e.g. \u7eaf\u70c1 T1 \u6c29\u6c33) double-count.
            battle.apply_heal(tgt, amount, source=src, trait_ep=False)
        return True

    def _n_FinishCurrentWave(self, owner, node, ctx):
        """Finish (skip) the current wave."""
        battle = self.battle
        if not battle:
            return False
        try:
            battle.waves.finish_current_wave()
            return True
        except Exception:
            return False

    def _n_ClearAllBuffs(self, owner, node, ctx):
        """Clear all buffs on the resolved unit except retained keys."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        keep = set(node.get("_retainedBuffsWhenClear") or [])
        removed = 0
        for bf in list(getattr(u, "buffs", None) or []):
            if bf.get("key") in keep:
                continue
            try:
                battle.buffs.remove(u, bf.get("key"))
                removed += 1
            except Exception:
                pass
        return removed > 0

    def _n_AssignHpRatioToBB(self, owner, node, ctx):
        """Write the resolved unit's hp/maxHp into the chain blackboard."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        bb = ctx.get("bb")
        key = node.get("_blackboardKey")
        if u is None or bb is None or not key:
            return False
        mx = float(getattr(u, "max_hp", 0.0) or 0.0)
        bb[key] = float(getattr(u, "hp", 0.0) or 0.0) / mx if mx > 0 else 0.0
        return True

    def _n_InterruptEnemyAbility(self, owner, node, ctx):
        """Interrupt the resolved enemy's current ability cast."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is None or sc.casting is None:
            return False
        try:
            from .consts import FinishReason
            sc.casting._finish(FinishReason.INTERRUPTED)
            return True
        except Exception:
            return False

    def _n_TriggerEnvSystem(self, owner, node, ctx):
        """Trigger an environment system (observer event)."""
        battle = self.battle
        if battle:
            battle.emit(battle.tick, "env_trigger",
                        {"unit": getattr(owner, "inst_id", None),
                         "env": node.get("_envKey") or ""})
        return True

    def _n_FilterByExecuteBlackboardValue(self, owner, node, ctx):
        """Gate: chain-blackboard value compares against _valueToCompare."""
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey") or ""
        try:
            val = float(bb.get(key))
        except (TypeError, ValueError):
            return False
        want = _num(node.get("_valueToCompare"), 0.0)
        cond = str(node.get("_condType") or "EQUALS").upper()
        if cond in ("EQUALS", "EQ"):
            return val == want
        if cond == "GT":
            return val > want
        if cond == "LT":
            return val < want
        if cond == "GE":
            return val >= want
        if cond == "LE":
            return val <= want
        return True

    def _n_FilterByCharacterSharedBlackboard(self, owner, node, ctx):
        """Gate: chain-blackboard value compares (shared approximation)."""
        return self._n_FilterByExecuteBlackboardValue(owner, node, ctx)

    def _n_AssignAttributeAsDynamicVarToBB(self, owner, node, ctx):
        """Copy a resolved unit's attribute into the chain blackboard."""
        return self._n_AssignAttributeToBB(owner, node, ctx)

    def _n_CheckHasAllyInRange(self, owner, node, ctx):
        """Gate: the resolved unit has an ally (operator/token) in its
        attack range."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_soureceType") or
                           node.get("_sourceType"), owner,
                           ctx.get("source"))
        if src is None or not hasattr(src, "attributes"):
            return False
        try:
            from .consts import resolve_attack_range
            radius = resolve_attack_range(
                src.attributes.get("rangeRadius"))
        except Exception:
            radius = 1.5
        for u in (list(battle.get_operators()) +
                  list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if abs(u.row - src.row) > radius or \
                    abs(u.col - src.col) > radius:
                continue
            return True
        return False

    def _n_InsertCheckPointInRuntimeRoute(self, owner, node, ctx):
        """Insert a WAIT_FOR_SECONDS checkpoint into the target enemy's
        route (pauses it for _time seconds)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_target"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        if str(node.get("_type") or "").upper() == "WAIT_FOR_SECONDS":
            t = _num(node.get("_time"), 0.0)
            if t > 0:
                u._wait_remaining = max(float(getattr(
                    u, "_wait_remaining", 0.0) or 0.0), t)
        return True

    def _n_CheckHasEnemyInRange(self, owner, node, ctx):
        """Gate: the resolved unit has an enemy in its attack range."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_soureceType") or
                           node.get("_sourceType"), owner,
                           ctx.get("source"))
        if src is None or not hasattr(src, "attributes"):
            return False
        try:
            from .consts import resolve_attack_range
            radius = resolve_attack_range(
                src.attributes.get("rangeRadius"))
        except Exception:
            radius = 1.5
        for en in battle.get_enemies():
            if getattr(en, "dead", False):
                continue
            if abs(en.row - src.row) > radius or \
                    abs(en.col - src.col) > radius:
                continue
            if en is src:
                continue
            return True
        return False

    def _n_ModifierScaleUp(self, owner, node, ctx):
        """Scale up modifiers (scale key resolution pending; no-op)."""
        return True

    def _n_SpShowBuff(self, owner, node, ctx):
        """SP-show buff: surface an observer event."""
        battle = self.battle
        if battle:
            battle.emit(battle.tick, "sp_show_buff",
                        {"unit": getattr(owner, "inst_id", None),
                         "key": node.get("_spShowBuffKey") or ""})
        return True

    def _n_CreateCardBuff(self, owner, node, ctx):
        """Roguelike card buff: surface an observer event (card system
        not modelled)."""
        battle = self.battle
        if battle:
            battle.emit(battle.tick, "card_buff",
                        {"unit": getattr(owner, "inst_id", None),
                         "target": node.get("_target"),
                         "lifeType": node.get("_lifeType")})
        return True

    def _n_CheckEntityDisappeared(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        from .consts import EnemyState
        return bool(getattr(u, "dead", False) or
                    getattr(u, "state", None) == EnemyState.DISAPPEAR)

    def _n_DamageViaAttr(self, owner, node, ctx):
        """Deal damage equal to an attribute value (e.g. DEF) of the
        source/target."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None or getattr(tgt, "dead", False):
            return False
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        attr_u = tgt if node.get("_getAttrFromTarget") else src
        if attr_u is None or not hasattr(attr_u, "attributes"):
            return False
        atype = str(node.get("_attributeType") or "DEF").upper()
        stat = {"DEF": "def", "ATK": "atk", "MAX_HP": "maxHp",
                "MAGIC_RESISTANCE": "magicResistance"}.get(atype)
        amount = float(attr_u.attributes.get(stat)) if stat else 0.0
        dmg_type = self._dmg_type(node.get("_damageType"))
        if amount > 0:
            battle.apply_damage(tgt, amount, dmg_type, source=src or owner,
                                no_hit_recovery=True)
        return True

    def _n_CreateBuffToToken(self, owner, node, ctx):
        """Create the embedded buff on the source's token(s)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        bd = dict(node.get("_buffData") or {})
        if src is None or not bd.get("buffKey"):
            return False
        bb = dict(ctx.get("bb") or {})
        hit = 0
        for tok in list(battle.get_tokens()):
            if getattr(tok, "owner", None) is src and not tok.dead:
                entry = materialise_buff(battle, tok, bd, bb, src)
                if entry and entry.get("key"):
                    battle.add_buff(tok, entry)
                    hit += 1
        return hit > 0

    def _n_CheckSkillIndex(self, owner, node, ctx):
        """Gate: the source's equipped skill index matches _skillIndex."""
        u = _source_unit(self.battle, node.get("_ownerType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is None:
            return False
        idx = int(getattr(sc, "equipped_index",
                          getattr(sc, "active_index", -1)) or -1)
        return idx == int(node.get("_skillIndex") or 0)

    def _n_AddGlobalBlackboard(self, owner, node, ctx):
        """Write a value into the chain blackboard and the battle-level
        global blackboard (shared across buffs / enemy teleports)."""
        bb = ctx.get("bb")
        if bb is None:
            return True
        key = node.get("_blackboardKey")
        if not key:
            return True
        val = node.get("_value")
        if node.get("_valueBlackboardKey"):
            val = bb.get(node.get("_valueBlackboardKey"), val)
        if node.get("_addString"):
            val = node.get("_valueStr") or ""
        if node.get("_overwrite") or key not in bb:
            bb[key] = val
        battle = self.battle
        if battle is not None:
            battle._global_bb[key] = val
        return True

    def _n_AtkToHpRecovery(self, owner, node, ctx):
        """Heal the owner by its ATK x blackboard ratio (wanqin S2 / atk
        to hp recovery; ratio keys value / ratio / heal_ratio)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        ratio = None
        for k in ("value", "ratio", "heal_ratio", "hp_recovery_ratio"):
            if bb.get(k) is not None:
                ratio = _num(bb.get(k), None)
                break
        if ratio is None:
            return True
        src = _source_unit(battle, node.get("_getAtkTargetType") or
                           "BUFF_SOURCE", owner, ctx.get("source"))
        if src is None:
            src = owner
        atk = _num(getattr(src, "attributes", None) and
                   src.attributes.get("atk"), 0.0)
        battle.apply_heal(owner, atk * ratio, source=src)
        return True

    def _n_ModifyCostIncreaseTime(self, owner, node, ctx):
        """Multiply (or divide) the battle cost-recovery period by the
        blackboard delta (bhrjst T1 cost inc/restore)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey") or "delta_cost_increase_time"
        val = _num(bb.get(key), _num(node.get("_deltaCostIncreaseTime"), 1.0))
        if val <= 0:
            return True
        if node.get("_isMulOtherwiseDiv"):
            battle.cost_increase_time = float(battle._cost_base_increase_time) * val
        else:
            battle.cost_increase_time = float(battle._cost_base_increase_time) / val
        return True

    def _n_ModifyMaxCost(self, owner, node, ctx):
        """Adjust the battle max cost by the blackboard value
        (bthtms T1 max_cost; _isMinus subtracts)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        val = _num(bb.get("value"), 0.0)
        if not val:
            return True
        delta = -val if node.get("_isMinus") else val
        battle.max_cost = max(1.0, float(battle.max_cost) + delta)
        if node.get("_ensureCurCostNotExceedMax"):
            battle.cost = min(float(battle.cost), float(battle.max_cost))
        return True

    def _n_CheckManhattanDistance(self, owner, node, ctx):
        """Gate: the Manhattan distance between the owner and its target
        is within [min, max] (enemy_duruin spawned)."""
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            tgt = ctx.get("target")
        if tgt is None:
            return False
        d = abs(getattr(owner, "row", 0) - getattr(tgt, "row", 0)) + \
            abs(getattr(owner, "col", 0) - getattr(tgt, "col", 0))
        lo = int(_num(node.get("_minDist"), 0))
        hi = int(_num(node.get("_maxDist"), 999))
        return lo <= d <= hi

    def _n_IsElementHeal(self, owner, node, ctx):
        """Gate: the modifier is an element heal (chnut output-modifier
        chains)."""
        dmg = ctx.get("damage") or {}
        return bool(dmg.get("_element_heal", False)) or \
            dmg.get("type") == DamageType.ELEMENT

    def _n_IsUnharmfulEnemy(self, owner, node, ctx):
        """Gate: the resolved unit is an unharmful (non-damaging) enemy."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        return u is not None and bool(getattr(u, "is_unharmful", False))

    def _n_CheckHasUnitInRange(self, owner, node, ctx):
        """Gate: any unit of the target side is within the radius (or
        range shape) around the resolved unit (uasnip power listener)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        bb = ctx.get("bb") or {}
        radius = _num(bb.get(node.get("_radiusKey") or "radius"), 1.0)
        side = str((node.get("_targetSide") or "ALL")).upper()
        for cand in (list(battle.get_enemies()) +
                     list(battle.get_operators()) +
                     list(battle.get_tokens())):
            if cand is u or getattr(cand, "dead", False):
                continue
            if side == "ALLY" and int(getattr(cand, "side", 0) or 0) != 1:
                continue
            if side == "ENEMY" and int(getattr(cand, "side", 0) or 0) != 0:
                continue
            d = abs(getattr(cand, "row", 0) - getattr(u, "row", 0)) + \
                abs(getattr(cand, "col", 0) - getattr(u, "col", 0))
            if d <= radius:
                return True
        return False

    def _n_SetEnemyCanNotExit(self, owner, node, ctx):
        """Set the resolved enemy's can-not-exit flag (pyczog riding)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        u.can_not_exit = bool(node.get("_canNotExit"))
        return True

    def _n_AssignIDToBlackboard(self, owner, node, ctx):
        """Write the resolved unit's id (char/enemy/token key) into the
        blackboard (act45side mujica / sandbox same-ranch check)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        bb[node.get("_bbKey") or "id"] = (getattr(u, "char_id", None) or
                                          getattr(u, "enemy_key", None) or
                                          getattr(u, "token_id", None) or
                                          str(getattr(u, "inst_id", 0)))
        return True

    def _n_CheckEnemyAbilityName(self, owner, node, ctx):
        """Gate: the resolved enemy's active ability name matches
        (enemy_blord2 BloodFountain2 / BloodFog2)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        want = str(node.get("_abilityName") or "")
        sc = getattr(u, "skill_controller", None)
        act = getattr(sc, "active", None)
        sk = getattr(act, "skill", None) if act is not None else None
        if sk is None:
            return False
        got = str(getattr(sk, "name", "") or "") + \
            str(getattr(sk, "prefab_key", "") or "") + \
            str(getattr(sk, "skill_id", "") or "")
        return bool(want) and want in got

    def _n_RecordAbilityRemainingTime(self, owner, node, ctx):
        """Record the named ability's remaining time into the blackboard
        (enemy_mandra PetrifiedRay / SummonDupilr CDs)."""
        bb = ctx.setdefault("bb", {})
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        want = str(node.get("_abilityName") or "")
        sc = getattr(u, "skill_controller", None)
        best = None
        for sk in (getattr(sc, "skills", None) or []):
            got = str(getattr(sk, "name", "") or "") + \
                str(getattr(sk, "prefab_key", "") or "")
            if want and want not in got:
                continue
            rem = getattr(sk, "cooldown_remaining", None)
            if rem is None:
                continue
            if best is None or rem > best:
                best = rem
        if best is None:
            return False
        bb[node.get("_recordKey") or "cd"] = best
        return True

    def _n_SpawnTokenOnRangeTile(self, owner, node, ctx):
        """Force-spawn the embedded token on the resolved target's tile
        (enemy_stmkgt / mpgrou tileblock seal)."""
        battle = self.battle
        if not battle:
            return True
        tgt = _source_unit(battle, node.get("_targetType") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            return True
        inst = ((node.get("_tokenToSpawn") or {}).get("inst")) or {}
        key = inst.get("characterKey") or ""
        if not key:
            return True
        ok, _ = battle.spawn_token_forced(key, tgt.row, tgt.col, owner=owner)
        return bool(ok)

    def _n_ModifyCharacterAttackTriggerRangeId(self, owner, node, ctx):
        """Override the resolved unit's attack-trigger range id (trap_ftshad
        overlapped / target)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        u._attack_trigger_range_id = node.get("_rangeId") or \
            node.get("_useSpecifiedModeRangeId") and str(
                node.get("_sourceMode") or "")
        return True

    def _n_CheckEnemySkillSelectorHasTargets(self, owner, node, ctx):
        """Gate: the enemy's named skill has targets available (xbfiry
        counter attack)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        act = getattr(sc, "active", None)
        if act is None:
            return False
        sk = getattr(act, "skill", None)
        name = str(node.get("_skillName") or "")
        if name and sk is not None:
            got = str(getattr(sk, "name", "") or "") + \
                str(getattr(sk, "skill_id", "") or "")
            if name not in got:
                return False
        tgt = getattr(act, "target", None) or getattr(act, "_target", None)
        return tgt is not None

    def _n_AssignEnemySkillCoolDownToBB(self, owner, node, ctx):
        """Write the enemy's named skill cooldown into the blackboard
        (enemy_ubbplwq Destroy)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        cd = getattr(sc, "cooldown_remaining", None)
        if cd is None:
            act = getattr(sc, "active", None)
            cd = getattr(act, "cooldown", None)
        if cd is None:
            return False
        bb = ctx.setdefault("bb", {})
        bb[node.get("_outputKey") or "cd"] = cd
        return True

    def _n_SetBossCountDown(self, owner, node, ctx):
        """Set the boss countdown from the blackboard (ubbplwq destroy)."""
        u = owner
        bb = ctx.get("bb") or {}
        key = node.get("_cdBBKey") or "cd"
        val = _num(bb.get(key), _num(node.get("_cdValue"), -1.0))
        u._boss_countdown = val
        return True

    def _n_CheckCharacterInIdleState(self, owner, node, ctx):
        """Gate: the resolved character is idle (no pending attack and not
        attacking)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        if getattr(u, "_pending_attack", None) is not None:
            return False
        return not bool(getattr(u, "attack_timer", 0.0) > 0.0)

    def _n_ForceEnterSkillOverloadProgress(self, owner, node, ctx):
        """Force the resolved unit into skill overload (tmslot S2)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_SOURCE",
                         owner, ctx.get("source"))
        if u is None:
            return False
        u._skill_overload = True
        return True

    def _n_InterruptEnemyAbility(self, owner, node, ctx):
        """Interrupt the resolved enemy's active ability (xi S2 shield /
        ltsmer), optionally resetting the cooldown."""
        u = _source_unit(self.battle, node.get("_enemyFrom") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is not None:
            try:
                sc.interrupt_active()
                if node.get("_resetCooldown"):
                    sc.cooldown_remaining = 0.0
                return True
            except Exception:
                pass
        return False

    def _n_CheckCharacterInMagicCircuit(self, owner, node, ctx):
        """Gate: the resolved character is inside a magic circuit (Sammy
        mechanics not modelled) - returns False."""
        return False

    def _n_ModifyRuntimeRouteUseBranchRoute(self, owner, node, ctx):
        """Point the resolved enemy's runtime route at its branch route
        (cjstel absorb / rabbithole assign)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None or not battle:
            return False
        try:
            end = u._target_idx()
            diag = bool((u.route or {}).get("allowDiagonalMove", True))
            u._next_map, u._dist_map = battle.map.build_flow_field(
                end, u._motion_mode, diag)
        except Exception:
            return False
        return True

    def _n_CreateBuffToBlockee(self, owner, node, ctx):
        """Apply the embedded buff to a unit blocked BY the owner
        (enemy_bomscr boom / dhnzzh mark / dhshld passive; the blocker
        applies the effect to its blockees)."""
        battle = self.battle
        if not battle:
            return True
        bd = node.get("_buff") or {}
        if not bd.get("buffKey"):
            return False
        blockees = [x for x in (getattr(owner, "blocked_enemies", None) or [])
                    if not getattr(x, "dead", False)]
        if not blockees:
            return False
        entry = materialise_buff(battle, blockees[0], dict(bd),
                                 ctx.get("bb") or {}, owner)
        if entry and entry.get("key"):
            battle.add_buff(blockees[0], entry)
            return True
        return False

    def _n_EnemyKillToken(self, owner, node, ctx):
        """Kill the resolved token (redace tal trigger / wdsmgc)."""
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None or not battle:
            return False
        tgt.hp = 0.0
        tgt.dead = True
        return True

    def _n_SetCharacterMaxEs(self, owner, node, ctx):
        """Set the resolved unit's max-ES ratio (rogue / humus ES
        modifier; recorded for snapshot)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey")
        ratio = _num(bb.get(key), _num(node.get("_maxEsRatio"), 1.0)) \
            if key else _num(node.get("_maxEsRatio"), 1.0)
        u._max_es_ratio = ratio
        return True

    def _n_AssignMapPositionToBlackboard(self, owner, node, ctx):
        """Write the resolved unit's grid position into the blackboard
        (ymgpck dont-move kill tracking)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        bb[node.get("_XKey") or "x"] = getattr(u, "col", 0)
        bb[node.get("_YKey") or "y"] = getattr(u, "row", 0)
        return True

    def _n_CheckEnemyIsTracingTarget(self, owner, node, ctx):
        """Gate: the enemy is tracing a target (pycrol riding / mnctur)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        return getattr(u, "_trace_target", None) is not None

    def _n_EnemyChangeRouteToEndTile(self, owner, node, ctx):
        """Point the enemy's route straight at its end tile (aglina M2 /
        vtarsn work)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None or not battle:
            return False
        try:
            end = u._target_idx()
            diag = bool((u.route or {}).get("allowDiagonalMove", True))
            u._next_map, u._dist_map = battle.map.build_flow_field(
                end, u._motion_mode, diag)
        except Exception:
            return False
        return True

    def _n_CheckCharacterInBornState(self, owner, node, ctx):
        """Gate: the resolved unit is in BORN state."""
        from .consts import EnemyState
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        return u is not None and getattr(u, "state", None) == EnemyState.BORN

    def _n_CheckDynamicBuffTileModeInEnum(self, owner, node, ctx):
        """Gate: the owner's tile dynamic-buff mode is in _modes
        (ltrock hit); _exclude negates."""
        battle = self.battle
        if not battle:
            return True
        modes = node.get("_modes") or []
        cur = battle.tile_mode(getattr(owner, "row", 0),
                               getattr(owner, "col", 0))
        has = cur in modes
        return (not has) if node.get("_exclude") else has

    def _n_CheckFaceLOrR(self, owner, node, ctx):
        """Gate: the resolved unit faces LEFT/RIGHT (aglna2 S3 / siege2
        token direction)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        d = int(getattr(u, "direction", 1) or 1)
        want = str(node.get("_direction") or "").upper()
        if want == "RIGHT":
            return d == 1
        if want == "LEFT":
            return d == 3
        return False

    def _n_FixedValueElementHeal(self, owner, node, ctx):
        """Recover element bars by the blackboard value (agoat2 /
        highmo T2 ep heal; scale-ups multiplied)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_valueKey") or "value"
        amount = _num(bb.get(key), 0.0)
        for k in (node.get("_scaleUpKeys") or []):
            amount *= _num(bb.get(k), 1.0)
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None or amount <= 0:
            return True
        battle.buffs.recover_ep(tgt, amount, source=owner)
        return True

    def _n_AssignHostBlackboardToBuffBlackboard(self, owner, node, ctx):
        """Copy a value from the host buff's blackboard into this buff's
        (prosts Mon3tr atk / mcgraf hp_ratio)."""
        battle = self.battle
        if not battle:
            return True
        u = _source_unit(battle, node.get("_hostTargetType") or "BUFF_SOURCE",
                         owner, ctx.get("source"))
        if u is None:
            return True
        hb = battle.buffs.get(u, node.get("_hostBuffKey") or "")
        fk = node.get("_fromBlackboardKey") or ""
        val = None
        if hb is not None:
            val = (hb.get("blackboard") or {}).get(fk)
        if val is None:
            val = node.get("_defaultValue")
        bb = ctx.setdefault("bb", {})
        bb[node.get("_toBlackboardKey") or fk] = val
        return True

    def _n_IfTargetFromDirection(self, owner, node, ctx):
        """Gate: the damage source lies in the named direction relative to
        the target (bgball directional damage reduction)."""
        battle = self.battle
        src = _source_unit(battle, node.get("_sourceType") or "MODIFIER_SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_targetType") or "MODIFIER_TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None:
            return False
        dr = getattr(tgt, "row", 0) - getattr(src, "row", 0)
        dc = getattr(tgt, "col", 0) - getattr(src, "col", 0)
        want = str(node.get("_direction") or "").upper()
        if want == "LEFT":
            return dc > 0
        if want == "RIGHT":
            return dc < 0
        if want == "UP":
            return dr > 0
        if want == "DOWN":
            return dr < 0
        return False

    def _n_CheckGamePlayedTime(self, owner, node, ctx):
        """Gate: the battle play time compares against the blackboard
        value (enemy_sfsui / racing mode)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        got = battle.tick / 30.0
        want = _num(bb.get("time"), 0.0)
        cond = str(node.get("_condType") or "GE").upper()
        if cond == "GT":
            return got > want
        if cond == "GE":
            return got >= want
        if cond == "LT":
            return got < want
        if cond == "LE":
            return got <= want
        return True

    def _n_VerifyTargetWithCertainSource(self, owner, node, ctx):
        """Gate: the resolved unit is on the expected side (night map
        default buff applies to ALLY)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        st = str(node.get("_sourceType") or "").upper()
        got = int(getattr(u, "side", 0) or 0)
        if st == "ALLY":
            return got == 1
        if st == "ENEMY":
            return got == 0
        return True

    def _n_IsIgnoreForSp(self, owner, node, ctx):
        """Gate: the damage context ignores SP recovery (csdcr / csdoll)."""
        dmg = ctx.get("damage") or {}
        return bool(dmg.get("_ignore_for_sp", False))

    def _n_EnemyDurcarChangeDirection(self, owner, node, ctx):
        """Turn the enemy toward the character (durcar direction marks)."""
        ch = _source_unit(self.battle, node.get("_character") or "BUFF_OWNER",
                          owner, ctx.get("source"))
        en = _source_unit(self.battle, node.get("_enemy") or "BUFF_SOURCE",
                          owner, ctx.get("source"))
        if ch is None or en is None:
            return False
        dr = getattr(ch, "row", 0) - getattr(en, "row", 0)
        dc = getattr(ch, "col", 0) - getattr(en, "col", 0)
        if abs(dr) > abs(dc):
            en.direction = 0 if dr < 0 else 2
        elif dc:
            en.direction = 1 if dc > 0 else 3
        return True

    def _n_CheckSpecificEnemyCount(self, owner, node, ctx):
        """Gate: the number of live enemies of the id compares against the
        limit (wdslm summon gates)."""
        battle = self.battle
        if not battle:
            return False
        eid = node.get("_enemyId") or ""
        n = sum(1 for e in battle.get_enemies()
                if getattr(e, "enemy_key", "") == eid and
                not getattr(e, "dead", False))
        bb = ctx.get("bb") or {}
        key = node.get("_limitAmountKey")
        want = _num(bb.get(key), _num(node.get("_limitAmount"), 0.0)) \
            if key else _num(node.get("_limitAmount"), 0.0)
        cond = str(node.get("_condType") or "GT").upper()
        if cond == "GT":
            return n > want
        if cond == "GE":
            return n >= want
        if cond == "LT":
            return n < want
        if cond == "LE":
            return n <= want
        if cond in ("EQUALS", "EQ", "=="):
            return n == want
        return True

    def _n_FilterIsDummy(self, owner, node, ctx):
        """Gate: the resolved unit is a dummy/preview (svash2 token cost
        reduce)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        return bool(getattr(u, "_is_dummy", False))

    def _n_CheckUnitSideOfMap(self, owner, node, ctx):
        """Gate: the resolved unit stands on the left (or right) half of
        the map (dyshhj side checks)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_source") or "BUFF_SOURCE",
                         owner, ctx.get("source"))
        if u is None or not battle:
            return False
        mid = battle.map.cols / 2.0
        left = getattr(u, "col", 0) < mid
        return left if node.get("_checkLeft") else (not left)

    def _n_NoSourceDamageNew(self, owner, node, ctx):
        """Deal fixed damage from the blackboard without a source
        (enemy_sgass / trap_crfilm boom)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_damageKey") or "damage"
        amount = _num(bb.get(key), 0.0)
        tgt = _source_unit(battle, node.get("_targetType") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None or amount <= 0:
            return True
        battle.apply_damage(tgt, amount,
                            self._dmg_type(node.get("_damageType")),
                            source=owner, no_hit_recovery=True)
        return True

    def _n_AmmoSkillCountModifier(self, owner, node, ctx):
        """Modify the resolved unit's ammo count (hlegle steal / hlnpcb
        add bullet / trap recover)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return True
        bb = ctx.get("bb") or {}
        cur = int(getattr(u, "_hunter_ammo", 0) or 0)
        add = 0
        if node.get("_addCountBBKey"):
            add = int(_num(bb.get(node.get("_addCountBBKey")), 0.0))
        else:
            add = int(_num(node.get("_addCount"), 0.0))
        if node.get("_recoverEventCount"):
            rk = node.get("_recoverCountBBKey") or "recover_count"
            add = int(_num(bb.get(rk), 0.0))
        u._hunter_ammo = max(0, cur + add)
        return True

    def _n_FinishTokenBuffsById(self, owner, node, ctx):
        """Remove the buff key from every token owned by the resolved
        unit (mylyss S3 token buffs)."""
        battle = self.battle
        if not battle:
            return False
        key = node.get("_buffKey") or ""
        if not key:
            return False
        hit = 0
        for t in list(battle.tokens):
            if getattr(t, "owner", None) is not owner:
                continue
            if battle.buffs.get(t, key) is not None:
                battle.buffs.remove(t, key)
                hit += 1
        return hit > 0

    def _n_CheckEnemyLevelMask(self, owner, node, ctx):
        """Gate: the resolved unit's level type matches the mask
        (NORMAL / ELITE / BOSS / ELITE_AND_BOSS)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        lv = int(getattr(u, "level_type", 0) or 0)
        mask = str(node.get("_targetLevelMask") or "").upper()
        if mask == "NORMAL":
            return lv == 0
        if mask == "ELITE":
            return lv == 1
        if mask == "BOSS":
            return lv == 2
        if mask in ("ELITE_AND_BOSS", "ELITE_AND_BOSS"):
            return lv >= 1
        return True

    def _n_ModifySpData(self, owner, node, ctx):
        """Update the resolved unit's skill SP cost from the blackboard
        (enemy_trcerb clear / marcil mana_max)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_spCostString") or "sp_cost"
        if key not in bb:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is not None:
            act = getattr(sc, "active", None)
            sk = getattr(act, "skill", None)
            if sk is not None:
                sk.blackboard[key] = bb[key]
                return True
        u._sp_cost_override = bb[key]
        return True

    def _n_FinishOneBuffById(self, owner, node, ctx):
        """Remove a single buff key from the resolved unit."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        key = node.get("_buffKey") or ""
        if battle.buffs.get(u, key) is None:
            return False
        battle.buffs.remove(u, key)
        return True

    def _n_AssignCharacterSkillBlackboardToBB(self, owner, node, ctx):
        """Copy a value from the resolved unit's skill blackboard into the
        chain blackboard (thorn2 T1 projectile delay / haruka levitate)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        sk = None
        if sc is not None:
            sk = getattr(getattr(sc, "active", None), "skill", None)
        skey = node.get("_sourceBlackboardKey") or ""
        val = None
        if sk is not None and getattr(sk, "blackboard", None):
            val = sk.blackboard.get(skey)
        if val is None:
            return False
        bb = ctx.setdefault("bb", {})
        bb[node.get("_targetBlackboardKey") or skey] = val
        return True

    def _n_ApplyElementDamageBasedOnDamageValue(self, owner, node, ctx):
        """Apply element damage proportional to the damage value (aegiret
        S1 fire / act38side light; ratio from bb)."""
        battle = self.battle
        if not battle:
            return True
        dmg = ctx.get("damage") or {}
        amount = _num(dmg.get("amount"), 0.0)
        if amount <= 0:
            return True
        bb = ctx.get("bb") or {}
        ratio = _num(bb.get("ep_damage_scale"), _num(bb.get("ratio"), 1.0))
        etype = {"FIRE": 2, "WATER": 1, "DARK": 3, "SANITY": 0}.get(
            str(node.get("_elementType") or "").upper(), 0)
        tgt = _source_unit(battle, node.get("_targetType") or "MODIFIER_TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            return True
        battle.add_ep(tgt, etype, amount * ratio)
        return True

    def _n_AssignAmmoSkillRemainingCountToBB(self, owner, node, ctx):
        """Write the resolved unit's remaining ammo into the blackboard
        (hlegle steal / angel2 S1)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        bb[node.get("_blackboardKey") or "rest_bullet"] = int(
            getattr(u, "_hunter_ammo", 0) or 0)
        return True

    def _n_AssignTokenCntToBB(self, owner, node, ctx):
        """Write the number of live tokens owned by the unit (necras)."""
        battle = self.battle
        if not battle:
            return True
        u = _source_unit(battle, node.get("_actionTargetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return True
        n = sum(1 for t in battle.tokens
                if getattr(t, "owner", None) is u and not getattr(t, "dead",
                                                                  False))
        bb = ctx.setdefault("bb", {})
        bb[node.get("_blackboardKey") or "current_token_cnt"] = n
        return True

    def _n_FinishBuffsOfEveryEnemyById(self, owner, node, ctx):
        """Remove the buff key from every enemy (blaze2 S2 on_tile)."""
        battle = self.battle
        if not battle:
            return False
        key = node.get("_buffKey") or ""
        if not key:
            return False
        hit = 0
        for e in list(battle.get_enemies()):
            if battle.buffs.get(e, key) is not None:
                battle.buffs.remove(e, key)
                hit += 1
        return hit > 0

    def _n_CheckHostContainsBuff(self, owner, node, ctx):
        """Gate: the resolved unit carries all (isAND) of the buff keys
        (mylyss waterman switch)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None or not self.battle:
            return False
        keys = node.get("_buffKeys") or []
        have = [k for k in keys if self.battle.buffs.get(u, k) is not None]
        if not have:
            return False
        return all(k in have for k in keys) if node.get("isAND") else True

    def _n_InterruptEnemyCombat(self, owner, node, ctx):
        """Interrupt the resolved enemy's combat (vtmstr equip B disarm):
        drop the pending attack."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        u._pending_attack = None
        return True

    def _n_Knockback(self, owner, node, ctx):
        """Push the target away from the source (knockback[dir] /
        knockback[relative])."""
        battle = self.battle
        src = _source_unit(battle, node.get("_source") or "SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_target") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None or not battle:
            return True
        if src is None:
            src = owner
        dr = getattr(tgt, "row", 0) - getattr(src, "row", 0)
        dc = getattr(tgt, "col", 0) - getattr(src, "col", 0)
        if dr == 0 and dc == 0:
            dr, dc = (1, 0)
        norm = (dr * dr + dc * dc) ** 0.5
        dr, dc = dr / norm, dc / norm
        bb = ctx.get("bb") or {}
        dist = _num(bb.get("distance"), 1.0)
        battle.displace(tgt, dr, dc, dist, source=owner)
        return True

    def _n_CheckTargetSkillDurationType(self, owner, node, ctx):
        """Gate: the resolved unit's active skill duration type matches
        (AMMO etc.)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        act = getattr(sc, "active", None)
        sk = getattr(act, "skill", None)
        types = node.get("_checkTypes") or []
        if not types:
            return True
        is_ammo = bool(getattr(sk, "is_ammo", False) or
                       getattr(u, "is_ammo", False))
        if "AMMO" in types:
            return is_ammo
        return False

    def _n_CheckRouteMotionMode(self, owner, node, ctx):
        """Gate: the resolved enemy's route motion mode matches (ymdgct
        highland)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        want = str(node.get("_mode") or "").upper()
        got = int(getattr(u, "_motion_mode", 0) or 0)
        return (got == 0) if want == "WALK" else (got == 1)

    def _n_AssignHostAttributeToBB(self, owner, node, ctx):
        """Write an attribute of the resolved unit (x scale) into the
        blackboard (token_phatm2 cached_atk / entlec def)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return False
        val = _num(getattr(getattr(u, "attributes", None), "get",
                           lambda k: 0.0)(stat), 0.0)
        bb = ctx.setdefault("bb", {})
        sv = node.get("_scaleVar") or ""
        if sv and sv != "scale_invalid":
            val = val * _num(bb.get(sv), 1.0)
        bb[node.get("_blackboardKey") or "value"] = val
        if node.get("_setCurrentHp"):
            bb["hp"] = _num(getattr(u, "hp", 0.0) or 0.0)
        return True

    def _n_CheckDirectionWithBB(self, owner, node, ctx):
        """Gate: the resolved unit's facing vs the blackboard direction
        (sandbox weather storm)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        bb = ctx.get("bb") or {}
        want = bb.get(node.get("_blackboardKey") or "direction")
        if want is None:
            return True
        got = int(getattr(u, "direction", 1) or 1)
        judge = str(node.get("_judgeType") or "EQUAL").upper()
        if judge == "OPPOSITE":
            return abs(got - int(want)) == 2
        return got == int(want)

    def _n_CheckEnemyWhetherReachedSomeCheckPoint(self, owner, node, ctx):
        """Gate: the enemy has reached the checkpoint index (mhrors
        sleep listener / gractrl)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        idx = node.get("_checkPointIndex")
        if node.get("_indexBbKey"):
            idx = (ctx.get("bb") or {}).get(node.get("_indexBbKey"), idx)
        try:
            want = int(idx)
        except (TypeError, ValueError):
            return False
        return int(getattr(u, "_checkpoint_idx", 0) or 0) >= want

    def _n_CheckCharacterOnTile(self, owner, node, ctx):
        """Gate: another character stands on the resolved unit's tile
        (yrjump achievement)."""
        battle = self.battle
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None or not battle:
            return False
        for o in list(battle.get_operators()) + list(battle.get_tokens()):
            if o is u or getattr(o, "dead", False):
                continue
            if (getattr(o, "row", 0), getattr(o, "col", 0)) == \
                    (getattr(u, "row", 0), getattr(u, "col", 0)):
                return True
        return False

    def _n_UpdateAttributeRawData(self, owner, node, ctx):
        """Update a raw attribute from the blackboard value (duskld
        revive max_hp)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_valueKey") or "value"
        if key not in bb:
            return False
        u.attributes.base[stat] = _num(bb[key], 0.0)
        if stat == "maxHp":
            u.max_hp = max(1.0, u.attributes.get("maxHp"))
            u.hp = min(u.hp, u.max_hp)
        return True

    def _n_FilterCharacterKey(self, owner, node, ctx):
        """Gate: the resolved unit's key matches (trap_148_amblls /
        token_10027_ironmn_pile3)."""
        u = _source_unit(self.battle, node.get("_sourceType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        key = node.get("_key") or ""
        uid = (getattr(u, "token_id", None) or getattr(u, "enemy_key", None)
               or getattr(u, "char_id", ""))
        return bool(key) and uid == key

    def _n_ReplaceAbilityDamageType(self, owner, node, ctx):
        """Override the resolved unit's ability damage type (trap_ftshad
        target modes)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        dmap = {"PHYSICAL": 0, "MAGICAL": 1, "TRUE": 2, "ELEMENT": 3}
        dt = dmap.get(str(node.get("_damageType") or "").upper())
        if dt is None:
            return True
        u._ability_damage_type_override = dt
        return True

    def _n_ModifyAttributeRawDataByEntity(self, owner, node, ctx):
        """Copy raw attributes from the source to the target (trap_ftshad
        absorbs the overlapping unit's stats; _useRatio multiplies)."""
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        if tgt is None or src is None or not battle:
            return False
        use_ratio = bool(node.get("_useRatio"))
        types = node.get("_typesNeedtoModify") or []
        for name in types:
            stat = _ATTR_TYPE_NAMES.get(_attr_type_int(name))
            if not stat:
                continue
            sv = _num(getattr(src, "attributes", None) and
                      src.attributes.get(stat), 0.0)
            tv = _num(getattr(tgt, "attributes", None) and
                      tgt.attributes.get(stat), 0.0)
            if use_ratio:
                sv = tv * sv
            tgt.attributes.base[stat] = sv
        return True

    def _n_HpRatioToAttributeMul(self, owner, node, ctx):
        """Multiplicative attribute buff scaled by the source's HP ratio
        (noirc2 T1 / limit_bonus def)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        src = _source_unit(battle, node.get("_hpRatioSource") or "SOURCE",
                           owner, ctx.get("source"))
        if src is None:
            return True
        mx = _num(getattr(src, "max_hp", 0.0) or 0.0)
        ratio = (_num(getattr(src, "hp", 0.0) or 0.0) / mx) if mx > 0 else 0.0
        lo = _num(node.get("_minHpRatio"), 0.0)
        hi = _num(node.get("_maxHpRatio"), 1.0)
        if ratio < lo or ratio > hi:
            return True
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return True
        value = _num(bb.get("value"), 0.0)
        if not value:
            return True
        battle.add_buff(owner, {
            "key": "op_hp_ratio_mul", "remaining_ticks": 30,
            "layers": 1, "stat": stat, "mul": value * ratio,
            "source": src})
        return True

    def _n_CheckCharSkillAvailable(self, owner, node, ctx):
        """Gate: the resolved unit has an available skill (trap_rift)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        return sc is not None and getattr(sc, "active", None) is not None

    def _n_AssignAbilityBlackboardFromOthers(self, owner, node, ctx):
        """Copy source-ability blackboard keys into the target ability
        (enemy_xdagt summon counters)."""
        battle = self.battle
        if not battle:
            return True
        src_u = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                             owner, ctx.get("source"))
        tgt_u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                             owner, ctx.get("source"))
        if src_u is None or tgt_u is None:
            return False
        sname = node.get("_sourceAbilityName") or ""
        tname = node.get("_targetAbilityName") or ""
        sbb = getattr(getattr(getattr(src_u, "skill_controller", None),
                              "active", None), "blackboard", None)
        tbb = getattr(getattr(getattr(tgt_u, "skill_controller", None),
                              "active", None), "blackboard", None)
        if tbb is None:
            return True
        keys = node.get("_sourceBBKeys") or []
        for k in keys:
            if sbb is not None and k in sbb:
                tbb[k] = sbb[k]
        return True

    def _n_CheckCharacterData(self, owner, node, ctx):
        """Gate: the resolved unit has character data (approximate pass)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        return u is not None

    def _n_CheckEntitySuicide(self, owner, node, ctx):
        """Gate: the death event is a suicide (approximate: no external
        source)."""
        src = ctx.get("source")
        return src is None or src is owner

    def _n_InterruptCharacterAbility(self, owner, node, ctx):
        """Interrupt the resolved unit's active ability (ash S2 / bena
        switch)."""
        u = _source_unit(self.battle, node.get("_charFrom") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        if sc is not None:
            try:
                sc.interrupt_active()
                return True
            except Exception:
                pass
        return False

    def _n_EnsureDmgOrHeal(self, owner, node, ctx):
        """Ensure the blackboard has the value key (default 1.0 when
        missing; acdrop trait atk_scale guards)."""
        bb = ctx.get("bb")
        if bb is None:
            return True
        key = node.get("_key") or ""
        if key and key not in bb:
            bb[key] = 1.0
        return True

    def _n_SetIgnoreMissFlag(self, owner, node, ctx):
        """Mark the damage context to ignore miss/evade for the flag
        (ignore_evade[physical] / fartth T2)."""
        dmg = ctx.get("damage")
        if dmg is None:
            return True
        flag = str(node.get("_ignoreMissFlag") or "").upper()
        dmg["_ignore_miss"] = flag
        return True

    def _n_RecordDamageModifier(self, owner, node, ctx):
        """Record the damage modifier value into bb['value'] (empgrd
        buffer / mirbst counter)."""
        bb = ctx.setdefault("bb", {})
        dmg = ctx.get("damage") or {}
        bb["value"] = _num(dmg.get("amount"), 0.0)
        return True

    def _n_CharacterHasValidToken(self, owner, node, ctx):
        """Gate: the resolved host has a live token (kalts Mon3tr /
        phatm2 cage)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_hostType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        return any(getattr(t, "owner", None) is u and not getattr(t, "dead",
                                                                  False)
                   for t in battle.tokens)

    def _n_FinishBuffsByIdByBuffSource(self, owner, node, ctx):
        """Remove the buff key from the resolved target whose source matches
        (bbrain mark cleanup / ristar boss buff)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        key = node.get("_buffKey") or ""
        entry = battle.buffs.get(u, key)
        if entry is None:
            return False
        battle.buffs.remove(u, key)
        return True

    def _n_FinishAllStatusResistableBuffs(self, owner, node, ctx):
        """Remove buffs that are status-resistable from the resolved unit
        (purify / mcnist invincible); keeps stat modifiers."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        removed = 0
        for b in list(getattr(u, "buffs", []) or []):
            if b.get("status_resistable") or b.get("abnormalImmunes") is not None:
                battle.buffs.remove(u, b["key"])
                removed += 1
        return removed > 0

    def _n_HasTileAlongDirection(self, owner, node, ctx):
        """Gate: a tile of the listed keys lies along the owner's facing
        (ristar orbital road)."""
        battle = self.battle
        if not battle:
            return True
        keys = node.get("_tileKeyList") or []
        if not keys:
            return True
        d = int(getattr(owner, "direction", 1) or 1)
        dr, dc = ((-1, 0), (0, 1), (1, 0), (0, -1))[d]
        r, c = getattr(owner, "row", 0), getattr(owner, "col", 0)
        for _ in range(max(battle.map.rows, battle.map.cols)):
            r += dr
            c += dc
            t = battle.map.tile(r, c)
            if t is None:
                return False
            if (t.tile_key or "") in keys:
                return True
        return False

    def _n_RechargeTokenByKey(self, owner, node, ctx):
        """Recharge a token's redeploy cooldown by key (enemy_pycblk
        riding / pyczog hitwall)."""
        battle = self.battle
        if not battle:
            return True
        tk = node.get("_tokenKey") or ""
        cnt = int(_num((ctx.get("bb") or {}).get(node.get("_cntKey") or "cnt"),
                       1.0))
        if not tk:
            return True
        battle._redeploy_until.pop(tk, None)
        if not node.get("_refreshRemainingCnt"):
            battle._redeploy_until[tk] = 0
        return True

    def _n_AssignProfessionCntToBlackboard(self, owner, node, ctx):
        """Count deployed operators of the profession and write it to the
        blackboard (cdcaster caster count / rogue relic medic count)."""
        battle = self.battle
        if not battle:
            return True
        cat = str(node.get("_professionCategory") or "").upper()
        names = {"WARRIOR": 1, "SNIPER": 2, "TANK": 4, "MEDIC": 8,
                 "SUPPORT": 16, "CASTER": 32, "SPECIAL": 64, "PIONEER": 512}
        prof = names.get(cat)
        if prof is None:
            return True
        n = sum(1 for o in battle.get_operators()
                if not getattr(o, "dead", False) and
                int(getattr(o, "profession", 0) or 0) == prof)
        bb = ctx.setdefault("bb", {})
        bb[node.get("_blackboardKey") or "cnt"] = n
        return True

    def _n_CheckConatinsMapTags(self, owner, node, ctx):
        """Gate: the level carries one of the map tags (act25side_extra /
        main_12)."""
        battle = self.battle
        if not battle:
            return True
        tags = set(node.get("_mapTags") or [])
        got = set(battle.raw.get("mapTags") or [])
        return bool(tags & got)

    def _n_CheckEnemyTalentContainsKey(self, owner, node, ctx):
        """Gate: the resolved enemy's talent blackboard carries the key
        (rogue_4 parasitic buff)."""
        u = _source_unit(self.battle, node.get("_source") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        key = node.get("_key") or ""
        bb = getattr(u, "talent_bb", None) or {}
        if key in bb:
            return True
        return any(str(b.get("key", "")).find(key) >= 0
                   for b in getattr(u, "buffs", []) or [])

    def _n_CheckHeightTypeOfCharacterRootTile(self, owner, node, ctx):
        """Gate: the resolved unit's tile height type matches (LOWLAND /
        HIGHLAND; chnut / aegiret traits)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        t = battle.map.tile(getattr(u, "row", 0), getattr(u, "col", 0))
        if t is None:
            return False
        want = str(node.get("_heightType") or "").upper()
        got = str(getattr(t, "height_type", "") or "").upper() or "LOWLAND"
        has = bool(want and got == want)
        return (not has) if node.get("_isUnset") else has

    def _n_CompareModifierValueWithTargetType(self, owner, node, ctx):
        """Gate: the modifier value compares against the target HP (or max
        HP x ratio when _useMaxRatio; blkngt sleep / ristar star mode)."""
        u = _source_unit(self.battle, node.get("_modifierTarget") or
                         "BUFF_OWNER", owner, ctx.get("source"),
                         ctx.get("target"))
        if u is None:
            return False
        dmg = ctx.get("damage") or {}
        got = _num(dmg.get("amount"), 0.0)
        if node.get("_useMaxRatio"):
            want = _num(getattr(u, "max_hp", 0.0) or 0.0) * _num(
                node.get("_ratio"), 1.0)
        else:
            want = _num(getattr(u, "hp", 0.0) or 0.0)
        cond = str(node.get("_condType") or "LE").upper()
        if cond == "LT":
            return got < want
        if cond == "GT":
            return got > want
        if cond == "GE":
            return got >= want
        if cond == "LE":
            return got <= want
        return True

    def _n_ChangeCharBlockMode(self, owner, node, ctx):
        """Switch the resolved unit's block mode (WALK/FLY; aglna2
        levitate). _resetToDefault clears the override."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        if node.get("_resetToDefault"):
            u._block_mode = None
        else:
            u._block_mode = str(node.get("_blockMode") or "WALK").upper()
        return True

    def _n_CheckBlockMode(self, owner, node, ctx):
        """Gate: the resolved unit's block mode matches (murad pollutant)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        want = str(node.get("_blockMode") or "").upper()
        got = str(getattr(u, "_block_mode", "") or "WALK").upper()
        return bool(want) and got == want

    def _n_FilterId(self, owner, node, ctx):
        """Gate: the resolved unit's id (token/enemy/char key) matches
        _filterId or _filterIds (aegiret shell / dsblock destroy)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        fid = node.get("_filterId") or ""
        if node.get("_filterIdKey"):
            fid = (ctx.get("bb") or {}).get(node.get("_filterIdKey"), fid)
        ids = node.get("_filterIds") or []
        uid = (getattr(u, "token_id", None) or getattr(u, "enemy_key", None)
               or getattr(u, "char_id", ""))
        has = bool(uid == fid or (ids and uid in ids))
        return (not has) if node.get("_isUnset") else has

    def _n_ChangeEnemyRouteMotionMode(self, owner, node, ctx):
        """Switch the enemy's route motion mode (WALK/FLY) and rebuild its
        flow field (dugago / cjstel fly)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None or not battle:
            return False
        want = str(node.get("_motionMode") or "").upper()
        u._motion_mode = 0 if want == "WALK" else 1
        try:
            end = u._target_idx()
            diag = bool((u.route or {}).get("allowDiagonalMove", True))
            u._next_map, u._dist_map = battle.map.build_flow_field(
                end, u._motion_mode, diag)
        except Exception:
            pass
        return True

    def _n_FilterCharacterLastDeathReason(self, owner, node, ctx):
        """Gate: the character's last death reason matches
        (MOVE_LIKE_RESPAWN_SELF etc.)."""
        u = _source_unit(self.battle, node.get("_characterType") or
                         "BUFF_OWNER", owner, ctx.get("source"))
        if u is None:
            return False
        reason = str(getattr(u, "_death_reason", "") or "").upper()
        want = str(node.get("_finishReason") or "").upper()
        return bool(want) and reason == want

    def _n_AlwaysExecuteNodeList(self, owner, node, ctx):
        """Run every nested node list unconditionally (aglna2 S2 branches)."""
        groups = node.get("_nodes") or []
        ran = 0
        for g in groups:
            if isinstance(g, list) and g:
                self.run_actions(owner, g, ctx, 0)
                ran += 1
            elif isinstance(g, dict):
                self.run_actions(owner, [g], ctx, 0)
                ran += 1
        return ran > 0

    def _n_CreateBuffs(self, owner, node, ctx):
        """Create the buff pair (mudrok T1 shield init); applies the
        embedded buff(s)."""
        battle = self.battle
        if not battle:
            return True
        pair = node.get("_buffPair") or {}
        bd = pair.get("buff") or {}
        if not bd.get("buffKey"):
            return False
        entry = materialise_buff(battle, owner, dict(bd), ctx.get("bb") or {},
                                 owner)
        if entry and entry.get("key"):
            battle.add_buff(owner, entry)
        extra = pair.get("buff2") or pair.get("_buff2") or {}
        if extra.get("buffKey"):
            e2 = materialise_buff(battle, owner, dict(extra),
                                  ctx.get("bb") or {}, owner)
            if e2 and e2.get("key"):
                battle.add_buff(owner, e2)
        return True

    def _n_AssignPlayTimeToBB(self, owner, node, ctx):
        """Write the battle play time (seconds) into the blackboard."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.setdefault("bb", {})
        bb[node.get("_blackboardKey") or "play_time"] = battle.tick / 30.0
        return True

    def _n_WithdrawTokens(self, owner, node, ctx):
        """Withdraw (remove) the tokens owned by the resolved unit
        (kalts_t withdraw token / necras)."""
        battle = self.battle
        if not battle:
            return False
        hit = 0
        for t in list(battle.tokens):
            if getattr(t, "owner", None) is not owner:
                continue
            if getattr(t, "dead", False):
                continue
            t.dead = True
            hit += 1
        if hit:
            battle.tokens = [t for t in battle.tokens if not t.dead]
        return hit > 0

    def _n_FetchHpToBlackboard(self, owner, node, ctx):
        """Write the resolved unit's HP (or hp ratio) into the blackboard
        (dhdcr show pv / dhtl)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackboardStr") or "dynamic"
        if node.get("_isHpRatio"):
            mx = _num(getattr(u, "max_hp", 0.0) or 0.0)
            bb[key] = (_num(getattr(u, "hp", 0.0) or 0.0) / mx) if mx > 0 \
                else 0.0
        else:
            bb[key] = _num(getattr(u, "hp", 0.0) or 0.0)
        return True

    def _n_RecordCurrentHpRatio(self, owner, node, ctx):
        """Record the resolved unit's current HP ratio (mandra stone skin /
        wlfmster damage record)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        mx = _num(getattr(u, "max_hp", 0.0) or 0.0)
        ratio = (_num(getattr(u, "hp", 0.0) or 0.0) / mx) if mx > 0 else 0.0
        bb = ctx.setdefault("bb", {})
        bb[node.get("_recordKey") or "hp_ratio"] = ratio
        return True

    def _n_CheckDistance(self, owner, node, ctx):
        """Gate: the source-target distance is within the radius (bb
        range_radius; damage_scale[type] / skzdd shield)."""
        battle = self.battle
        src = _source_unit(battle, node.get("_source") or "MODIFIER_SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_target") or "MODIFIER_TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None:
            return False
        radius = _num((ctx.get("bb") or {}).get(node.get("_radiusBbKey")
                                                or "range_radius"),
                      _num(node.get("_radius"), 0.0))
        dist = ((getattr(tgt, "row", 0) - getattr(src, "row", 0)) ** 2 +
                (getattr(tgt, "col", 0) - getattr(src, "col", 0)) ** 2) ** 0.5
        return dist <= radius

    def _n_FilterByTargetMassLevel(self, owner, node, ctx):
        """Gate: the resolved target's mass level compares against the bb
        value (glady T2 / poca T1)."""
        u = _source_unit(self.battle, node.get("_target") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        got = _num(getattr(u, "attributes", None) and
                   u.attributes.get("massLevel"), 0.0)
        want = _num((ctx.get("bb") or {}).get("mass_level"), 0.0)
        cond = str(node.get("_condType") or "LE").upper()
        if cond == "LT":
            return got < want
        if cond == "GT":
            return got > want
        if cond == "GE":
            return got >= want
        if cond == "LE":
            return got <= want
        return True

    def _n_KnockBackWithDirection(self, owner, node, ctx):
        """Push the owner in the given direction (blizzard knockback)."""
        battle = self.battle
        if not battle:
            return True
        d = str(node.get("_direction") or "RIGHT").upper()
        vec = {"UP": (-1, 0), "RIGHT": (0, 1), "DOWN": (1, 0),
               "LEFT": (0, -1)}.get(d, (0, 1))
        bb = ctx.get("bb") or {}
        dist = _num(bb.get("distance"), 1.0)
        force = _num(bb.get("force"), _num(node.get("_defaultForceLevel"), 0))
        if force:
            dist = max(dist, float(force) * 0.5)
        battle.displace(owner, vec[0], vec[1], dist, source=owner)
        return True

    def _n_SwitchDynamicBuffTileMode(self, owner, node, ctx):
        """Switch dynamic-buff tile modes (reed -> flaming etc.); with
        _useOwnerRootTile only the owner's tile is switched."""
        battle = self.battle
        if not battle:
            return True
        op = str(node.get("_operation") or "INDEX").upper()
        mi = node.get("_modeIndex")
        tt = node.get("_tileType") or ""
        spec = bool(node.get("_specifyTileType"))
        if node.get("_useOwnerRootTile"):
            r, c = getattr(owner, "row", 0), getattr(owner, "col", 0)
            t = battle.map.tile(r, c)
            if t is None:
                return True
            tk = t.tile_key or ""
            if spec and tt:
                if tt == "REED_TILE" and not tk.startswith("tile_reed"):
                    return True
                if tt != "REED_TILE" and tt.lower() not in tk:
                    return True
            cur = battle.tile_mode(r, c)
            battle._tile_modes[(r, c)] = 1 - cur if op == "FLIP_BOOL" \
                else int(mi if mi is not None else 1)
            return True
        return battle.switch_tiles_mode(operation=op, mode_index=mi,
                                        tile_type=tt, specify=spec,
                                        source=owner) > 0

    def _n_SwitchDynamicBuffTileModeOneLine(self, owner, node, ctx):
        """One-line variant: delegates to the same tile-mode switch."""
        return self._n_SwitchDynamicBuffTileMode(owner, node, ctx)

    def _n_ModifyAbilityAttackTime(self, owner, node, ctx):
        """Write a value into the named ability's attack-time blackboard
        (pope S1 M1/M2 sync parameters)."""
        bb = ctx.get("bb") or {}
        key = node.get("_bbKey") or ""
        val = _num(bb.get(key), _num(node.get("_value"), 0.0))
        sc = getattr(owner, "skill_controller", None)
        if sc is None:
            return True
        act = getattr(sc, "active", None)
        sk = getattr(act, "skill", None)
        name = str(node.get("_abilityName") or "")
        if name and sk is not None:
            got = str(getattr(sk, "name", "") or "") + \
                str(getattr(sk, "skill_id", "") or "")
            if name not in got:
                return True
        if key:
            if sk is not None:
                sk.blackboard[key] = val
            elif act is not None:
                act.blackboard[key] = val
        return True

    def _n_CalculateTraitAbilityBlackboard(self, owner, node, ctx):
        """Compute a trait/skill blackboard value: targetKey =
        fromKey (+/- addKey) (coldst reload interval)."""
        bb = ctx.get("bb") or {}
        fk = node.get("_fromBlackboardKey") or ""
        tk = node.get("_targetBlackboardKey") or fk
        if not fk and not tk:
            return True
        base = _num(bb.get(fk), 0.0)
        add = _num(bb.get(node.get("_addBlackboardKey") or ""), 0.0)
        if node.get("_useTraitBBToAdd"):
            ts = getattr(owner, "trait_system", None)
            if ts is not None:
                add = _num(ts.bb.get(node.get("_addBlackboardKey") or ""), add)
        val = base - add if node.get("_isSub") else base + add
        bb[tk] = val
        return True

    def _n_FilterByTargetDataLevel(self, owner, node, ctx):
        """Gate: the resolved unit's data level compares (trap mesh
        visibility by level)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        got = _num(getattr(u, "level", 0) or 0)
        want = _num(node.get("_level"), 0.0)
        cond = str(node.get("_condType") or "LE").upper()
        if cond == "LT":
            return got < want
        if cond == "GT":
            return got > want
        if cond == "GE":
            return got >= want
        if cond == "LE":
            return got <= want
        if cond in ("EQUALS", "EQ", "=="):
            return got == want
        return True

    def _n_AssignValueToTraitBB(self, owner, node, ctx):
        """Write a value into the owner's trait blackboard (coldst
        RELOAD_FLAG)."""
        key = node.get("_blackboardKey")
        if not key:
            return True
        val = node.get("_value")
        ts = getattr(owner, "trait_system", None)
        if ts is not None:
            ts.bb[key] = val
        else:
            owner._trait_bb_extra = getattr(owner, "_trait_bb_extra", {})
            owner._trait_bb_extra[key] = val
        return True

    def _n_CheckEnemyCurrentCheckpoint(self, owner, node, ctx):
        """Gate: the enemy currently waits at a checkpoint of one of the
        listed types (enemy_xdmush wait)."""
        types = node.get("_checkpointTypes") or []
        cp_idx = getattr(owner, "_checkpoint_idx", 0) or 0
        cps = getattr(owner, "route", {}).get("checkpoints") or []
        if cp_idx >= len(cps):
            return False
        cp = cps[cp_idx] or {}
        ctype = cp.get("type") or {}
        if isinstance(ctype, dict):
            ctype = ctype.get("value", 0)
        names = {1: "WAIT_FOR_SECONDS", 3: "WAIT_CURRENT_FRAGMENT_TIME",
                 4: "WAIT_CURRENT_WAVE_TIME", 8: "PATROL_MOVE"}
        got = names.get(int(ctype), "")
        return got in types

    def _n_CheckEnemyFaceAndMoveDir(self, owner, node, ctx):
        """Gate: the enemy's facing and movement direction match
        (mhkryk back-listener SAME / face-listener OPPOSITE)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        d = int(getattr(u, "direction", 1) or 1)
        mv = getattr(u, "_move_dir", None)
        if mv is None:
            return True
        same = d == int(mv)
        want = str(node.get("_checkType") or "SAME").upper()
        return same if want == "SAME" else (not same)

    def _n_ModifyBlackboardFromTrait(self, owner, node, ctx):
        """Copy (or add) trait blackboard values into the chain blackboard
        (leizi2 max_stack_cnt / atk sync)."""
        bb = ctx.get("bb") or {}
        ts = getattr(owner, "trait_system", None)
        keys = str(node.get("_blackboardKeys") or "").split(",")
        from_keys = str(node.get("_fromBlackboardKeys") or "").split(",")
        for i, k in enumerate([k.strip() for k in keys if k.strip()]):
            fk = from_keys[i].strip() if i < len(from_keys) else k
            src_val = None
            if ts is not None:
                src_val = ts.bb.get(fk)
            if src_val is None:
                src_val = bb.get(fk)
            if src_val is None:
                continue
            val = _num(src_val, 0.0)
            if node.get("_addBasedOriginValue"):
                val += _num(bb.get(k), 0.0)
            bb[k] = val
        return True

    def _n_ModifyBoomberangMaxCnt(self, owner, node, ctx):
        """Set/reset the owner's boomerang max count (caper S2)."""
        if node.get("_reset"):
            owner._boomberang_max_cnt = None
        else:
            bb = ctx.get("bb") or {}
            owner._boomberang_max_cnt = int(_num(bb.get("max_cnt"), 1.0))
        return True

    def _n_AddEnemyBlockVolume(self, owner, node, ctx):
        """Adjust the resolved unit's block volume (enemy_dssalr)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        vol = int(_num(node.get("_additionVolume"), 0.0))
        if node.get("_isMinus"):
            vol = -vol
        u.block_volume = max(1, int(getattr(u, "block_volume", 1) or 1) + vol)
        return True

    def _n_AddTileBlackboard(self, owner, node, ctx):
        """Add to a per-tile blackboard value (enemy_xdmush mushroom
        counter on its root tile)."""
        battle = self.battle
        if not battle:
            return True
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        r = getattr(u, "row", 0)
        c = getattr(u, "col", 0)
        if node.get("_useTargetOldTile"):
            r, c = getattr(u, "_old_row", r), getattr(u, "_old_col", c)
        key = node.get("_blackboardKey")
        if not key:
            return True
        addition = _num(node.get("_addition"), 0.0)
        if node.get("_additionKey"):
            addition = _num(ctx.get("bb", {}).get(node.get("_additionKey")),
                            addition)
        bb = battle._tile_bb.setdefault((r, c), {})
        bb[key] = _num(bb.get(key), 0.0) + addition
        return True

    def _n_ModifyTileBlackboard(self, owner, node, ctx):
        """Set a per-tile blackboard value (enemy_lrtsia core flag)."""
        battle = self.battle
        if not battle:
            return True
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        r = getattr(u, "row", 0)
        c = getattr(u, "col", 0)
        key = node.get("_blackboardKey")
        if not key:
            return True
        if node.get("_assignStrValue"):
            val = node.get("_valueStr") or ""
        elif node.get("_valueKey"):
            val = ctx.get("bb", {}).get(node.get("_valueKey"))
        else:
            val = node.get("_value")
        battle._tile_bb.setdefault((r, c), {})[key] = val
        return True

    def _n_FilterTileBlackboard(self, owner, node, ctx):
        """Gate: the target tile's blackboard value compares (enemy_fthlgj
        burn reduction check)."""
        battle = self.battle
        if not battle:
            return True
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        r = getattr(u, "row", 0)
        c = getattr(u, "col", 0)
        key = node.get("_blackboardKey")
        if not key:
            return True
        tbb = battle._tile_bb.get((r, c), {})
        got = _num(tbb.get(key), 0.0)
        rk = node.get("_anotherKeyToCompare")
        want = _num(tbb.get(rk), _num(node.get("_valueToCompare"), 0.0)) \
            if rk else _num(node.get("_valueToCompare"), 0.0)
        cond = str(node.get("_condType") or "GT").upper()
        if cond == "GT":
            return got > want
        if cond == "GE":
            return got >= want
        if cond == "LT":
            return got < want
        if cond == "LE":
            return got <= want
        if cond in ("EQUALS", "EQ", "=="):
            return got == want
        return True

    def _n_CreateBuffToUnitInCurrentMapLayer(self, owner, node, ctx):
        """Apply the embedded buff to units of the target side on the map
        (pbank death buffs; layer approximation = side filter)."""
        battle = self.battle
        if not battle:
            return True
        bd = node.get("_buff") or {}
        if not bd.get("buffKey"):
            return False
        opts = node.get("_targetOptions") or {}
        side = str(opts.get("targetSide") or "ENEMY").upper()
        want = 0 if side == "ENEMY" else 1
        hit = 0
        for u in (list(battle.get_enemies()) + list(battle.get_operators())
                  + list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if int(getattr(u, "side", 0) or 0) != want:
                continue
            entry = materialise_buff(battle, u, dict(bd), ctx.get("bb") or {},
                                     owner)
            if entry and entry.get("key"):
                battle.add_buff(u, entry)
                hit += 1
        return hit > 0

    def _n_CheckUnitInMoveState(self, owner, node, ctx):
        """Gate: the resolved unit is in MOVE state."""
        from .consts import EnemyState
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        return u is not None and getattr(u, "state", None) == EnemyState.MOVE

    def _n_CheckUnitInAttackState(self, owner, node, ctx):
        """Gate: the resolved unit is attacking (ATTACK/COMBAT); _isUnset
        negates (enemy spmode check)."""
        from .consts import EnemyState
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        in_atk = getattr(u, "state", None) in (EnemyState.ATTACK,
                                               EnemyState.COMBAT)
        return (not in_atk) if node.get("_isUnset") else in_atk

    def _n_ModifyAttackMaxTarget(self, owner, node, ctx):
        """Set the resolved unit's normal-attack max target count
        (enemy_dsdevr split arrows / hsgma2 S3)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        try:
            u._attack_max_target = int(node.get("_maxTarget") or 1)
        except (TypeError, ValueError):
            u._attack_max_target = 1
        return True

    def _n_ModifyEnemySkillMaxTarget(self, owner, node, ctx):
        """Set the max target of the named enemy skill (smdeer Lasso)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        skey = node.get("_skillKey") or ""
        sc = getattr(u, "skill_controller", None)
        val = int(node.get("_maxTarget") or 1)
        if sc is not None:
            act = getattr(sc, "active", None)
            sk = getattr(act, "skill", None)
            if sk is not None and (not skey or skey in
                                   (getattr(sk, "name", "") or "") or
                                   skey in (getattr(sk, "skill_id", "") or "")):
                sk.blackboard["max_target"] = val
                return True
        u._skill_max_target_override = {skey: val}
        return True

    def _n_FinishBuffsOfEveryCharacterById(self, owner, node, ctx):
        """Remove the buff key from every operator/token (murad passive
        cleanup / acelem parasite clear)."""
        battle = self.battle
        if not battle:
            return False
        key = node.get("_buffKey") or ""
        if not key:
            return False
        hit = 0
        for u in list(battle.get_operators()) + list(battle.get_tokens()):
            if battle.buffs.get(u, key) is not None:
                battle.buffs.remove(u, key)
                hit += 1
        return hit > 0

    def _n_CheckEnemySkillAffecting(self, owner, node, ctx):
        """Gate: the resolved enemy has an active skill (enemy_sgcat gems
        trigger only while a skill is affecting)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        sc = getattr(u, "skill_controller", None)
        return sc is not None and getattr(sc, "active", None) is not None

    def _n_FinishSeveralBuffsById(self, owner, node, ctx):
        """Remove several buff keys from the resolved unit (enemy_minima
        shield refresh / durcar direction marks)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        keys = node.get("_buffKeys") or []
        hit = 0
        for k in keys:
            if battle.buffs.get(u, k) is not None:
                battle.buffs.remove(u, k)
                hit += 1
        return hit > 0

    def _n_CreateBuffToHostAsSource(self, owner, node, ctx):
        """Create the embedded buff on the host with itself as source
        (delegates to CreateBuff semantics on the owner)."""
        battle = self.battle
        if not battle:
            return True
        bd = node.get("_buff") or {}
        if not bd.get("buffKey"):
            return False
        entry = materialise_buff(battle, owner, dict(bd), ctx.get("bb") or {},
                                 owner)
        if entry and entry.get("key"):
            battle.add_buff(owner, entry)
        return True

    def _n_AssignGlobalBlackboardToBlackboard(self, owner, node, ctx):
        """Copy a value from the battle-level global blackboard into the
        chain blackboard (enemy_cjdoor teleport row/col)."""
        battle = self.battle
        if battle is None:
            return True
        gk = node.get("_globalblackboardKey") or ""
        if gk not in battle._global_bb:
            return True
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackboardKey") or gk
        val = battle._global_bb[gk]
        if node.get("_assignString"):
            val = str(val)
        bb[key] = val
        return True

    def _n_AssignCharacterSharedBBToBlackboard(self, owner, node, ctx):
        """Copy a value from the battle-level character-shared blackboard
        (aglna2 located row/col)."""
        battle = self.battle
        if battle is None:
            return True
        sk = node.get("_sourceBBKey") or ""
        if sk not in battle._char_shared_bb:
            return True
        bb = ctx.setdefault("bb", {})
        bb[node.get("_targetBBKey") or sk] = battle._char_shared_bb[sk]
        return True

    def _n_AddCharacterSharedBlackboard(self, owner, node, ctx):
        """Write into the chain blackboard and the battle-level
        character-shared blackboard."""
        bb = ctx.get("bb")
        if bb is None:
            return True
        key = node.get("_blackboardKey")
        if not key:
            return True
        if node.get("_isStringBB"):
            val = node.get("_valueStr") or ""
        elif node.get("_useValueKey") and node.get("_valueKey"):
            val = bb.get(node.get("_valueKey"))
        else:
            val = node.get("_value")
        if node.get("_isOverwrite") or key not in bb:
            bb[key] = val
        battle = self.battle
        if battle is not None and val is not None:
            battle._char_shared_bb[key] = val
        return True

    def _n_ModifyLifePoint(self, owner, node, ctx):
        """Modify the battle life point by a blackboard value."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey") or "value"
        amount = _num(bb.get(key), 0.0)
        battle.life_point = max(0, battle.life_point + int(amount))
        return True

    def _n_HpRatioTrigger(self, owner, node, ctx):
        """Gate: the resolved unit's hp ratio compares against
        _hpRatioEachTime."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        mx = float(getattr(u, "max_hp", 0.0) or 0.0)
        if mx <= 0:
            return False
        ratio = float(getattr(u, "hp", 0.0) or 0.0) / mx
        want = _num(node.get("_hpRatioEachTime"), 0.0)
        cond = str(node.get("_condType") or "GT").upper()
        if cond == "GT":
            return ratio > want
        if cond == "LT":
            return ratio < want
        if cond == "GE":
            return ratio >= want
        if cond == "LE":
            return ratio <= want
        return True

    def _n_MoveNextLevelBranch(self, owner, node, ctx):
        """Advance a level branch (branch id from node or blackboard)."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        branch = node.get("_branchId") or bb.get("branch_id") or ""
        if not branch:
            return False
        try:
            battle.execute_branch(branch, is_loop=bool(node.get("_isLoop")))
            return True
        except Exception:
            return False

    def _n_CheckEnemyUnbalanced(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        return bool(u is not None and getattr(u, "displacement", None)
                    is not None)

    def _n_IsCharacter(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        return bool(u is not None and getattr(u, "char_id", None))

    def _n_IsCharacterOrTokenOrTrap(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        return bool(getattr(u, "char_id", None) or
                    getattr(u, "token_id", None))

    def _n_ClearCharacterSp(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_charFrom"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is not None:
            u.sp = 0.0
        return True

    def _n_CheckCharacterDefaultDirection(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_target"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        want = str(node.get("_direction") or "").upper()
        mapping = {"UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3}
        return int(getattr(u, "direction", 0) or 0) == mapping.get(want, -1)

    def _n_CheckTargetProfession(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        profs = node.get("_profession") or []
        if not profs:
            return True
        p = str(getattr(u, "profession", "") or "").upper()
        return any(str(x).upper() == p or
                   (str(x).upper() == "TOKEN" and
                    getattr(u, "token_id", None)) for x in profs)

    def _n_CheckModifierContainsKey(self, owner, node, ctx):
        """Gate: a buff with the custom key exists on the resolved unit."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        key = node.get("_customKey") or ""
        if u is None or not battle or not key:
            return False
        return any(str(x.get("key", "")).find(key) >= 0
                   for x in (getattr(u, "buffs", None) or []))

    def _n_ModifyAbilityBlackboard(self, owner, node, ctx):
        """Write chain-blackboard values into an ability's blackboard
        (no cast)."""
        sc = getattr(owner, "skill_controller", None)
        if sc is None:
            return False
        keys = [k.strip() for k in str(
            node.get("_blackboardKeys") or "").split(",") if k.strip()]
        bb = ctx.get("bb") or {}
        found = False
        for s in getattr(sc, "skills", None) or []:
            for k in keys:
                if k in bb:
                    s.blackboard[k] = bb[k]
                    found = True
        return found

    def _n_CancelModifier(self, owner, node, ctx):
        """Remove attribute-modifier buffs from the resolved unit."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        removed = 0
        for bf in list(getattr(u, "buffs", None) or []):
            if bf.get("stat") and (bf.get("add") or bf.get("mul") or
                                   bf.get("final_add") or bf.get("final_mul")):
                try:
                    battle.buffs.remove(u, bf.get("key"))
                    removed += 1
                except Exception:
                    pass
        return removed > 0

    def _n_AttributeModifierWithBB(self, owner, node, ctx):
        """Apply an attribute modifier (value from bb _valueKey) to the
        resolved unit."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None or not hasattr(u, "attributes"):
            return False
        bb = ctx.get("bb") or {}
        vkey = node.get("_valueKey") or ""
        val = _num(bb.get(vkey), 0.0)
        atype = str(node.get("_attributeType") or "").upper()
        stat = {"MAX_HP": "maxHp", "ATK": "atk", "DEF": "def",
                "MAGIC_RESISTANCE": "magicResistance",
                "MOVE_SPEED": "moveSpeed", "ATTACK_SPEED": "attackSpeed",
                "BLOCK_CNT": "blockCnt", "HP_RECOVERY_PER_SEC":
                "hpRecoveryPerSec", "SP_RECOVERY_PER_SEC":
                "spRecoveryPerSec"}.get(atype)
        if not stat:
            return False
        formula = str(node.get("_formulaType") or "ADDITION").upper()
        entry = {
            "key": "buff_attr_bb", "stat": stat,
            "remaining_ticks": 1 << 30, "layers": 1,
            "source": owner,
        }
        if formula in ("MULTIPLIER", "FINAL_SCALER"):
            entry["mul"] = val
        else:
            entry["add"] = val
        battle.add_buff(u, entry)
        return True

    def _n_SummonEnemyWithRuntimeRoute(self, owner, node, ctx):
        """Summon an enemy at the source (with runtime route / flight /
        unharmful flags)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source"), owner,
                           ctx.get("source"))
        if src is None:
            src = owner
        key = node.get("_enemyKey") or ""
        if not key:
            return False
        try:
            spawned = battle.spawn_enemy_directive(
                key, getattr(src, "row", 0), getattr(src, "col", 0))
            if spawned is not None and                     str(node.get("_motionMode") or "").upper() == "FLY":
                spawned._motion_mode = 1
            if node.get("_unharmful"):
                spawned.is_unharmful = True
            return True
        except Exception:
            return False

    def _summon_enemy_key(self, node, bb):
        """Enemy key for summon nodes: explicit node field first, then the
        standard blackboard keys (enemy_key / enemyKey / enemy_id /
        enemyId)."""
        key = node.get("_enemyKey") or node.get("_enemyId") or ""
        if not key:
            for k in ("enemy_key", "enemyKey", "enemy_id", "enemyId"):
                v = (bb or {}).get(k)
                if v:
                    key = str(v)
                    break
        return key

    def _apply_summon_buffs(self, battle, spawned, buffs, bb, owner):
        """Apply buff definitions to a freshly summoned enemy."""
        for bd in buffs or []:
            if not isinstance(bd, dict) or not bd.get("buffKey"):
                continue
            try:
                entry = materialise_buff(battle, spawned, dict(bd),
                                         dict(bb or {}), owner)
                if entry and entry.get("key"):
                    battle.add_buff(spawned, entry)
            except Exception:
                pass

    def _n_SummonEnemiesWithRuntimeNearestEndPointRoute(self, owner, node, ctx):
        """Summon _summonCount copies of the enemy at the source's tile
        with the runtime nearest-end route (SummonEnemiesWithRuntime-
        NearestEndPointRoute: dhnzzh reborn, trap_trbox_s, legion traps,
        dysbox ...). The enemy key comes from the node or the buff
        blackboard."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        key = self._summon_enemy_key(node, ctx.get("bb") or {})
        if not key:
            return False
        count = max(1, int(_num(node.get("_summonCount"), 1.0)))
        row = int(getattr(src, "row", 0) or 0)
        col = int(getattr(src, "col", 0) or 0)
        motion = str(node.get("_motionMode") or "WALK").upper()
        spawned = []
        for _ in range(count):
            e = battle.spawn_enemy_directive(key, row, col)
            if e is None:
                continue
            if motion == "FLY":
                e._motion_mode = 1
            if node.get("_unharmful"):
                e.is_unharmful = True
            self._apply_summon_buffs(battle, e, node.get("_buffs"),
                                     ctx.get("bb") or {}, owner)
            spawned.append(e.inst_id)
        battle.emit(battle.tick, "enemy_summoned",
                    {"unit": getattr(src, "inst_id", None),
                     "enemyKey": key, "count": len(spawned),
                     "instances": spawned,
                     "node": "SummonEnemiesWithRuntimeNearestEndPointRoute"})
        return bool(spawned)

    def _n_HalfIdleSummonEnemyAtTargetMapPos(self, owner, node, ctx):
        """Summon the enemy at the resolved target unit's map position
        (HalfIdleSummonEnemyAtTargetMapPos, half-idle event traps). The
        enemy key comes from _enemyId or the blackboard; the spawned
        enemy gets the _buffToEnemy buff when _hasBuffToEnemySource."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            tgt = owner
        key = self._summon_enemy_key(node, ctx.get("bb") or {})
        if not key:
            return False
        count = max(1, int(_num(node.get("_count"), 1.0)))
        row = int(getattr(tgt, "row", 0) or 0)
        col = int(getattr(tgt, "col", 0) or 0)
        motion = str(node.get("_motionMode") or "WALK").upper()
        spawned = []
        for _ in range(count):
            e = battle.spawn_enemy_directive(key, row, col)
            if e is None:
                continue
            if motion == "FLY":
                e._motion_mode = 1
            if node.get("_unharmful"):
                e.is_unharmful = True
            if node.get("_hasBuffToEnemySource"):
                self._apply_summon_buffs(battle, e,
                                         [node.get("_buffToEnemy")],
                                         ctx.get("bb") or {}, owner)
            spawned.append(e.inst_id)
        battle.emit(battle.tick, "enemy_summoned",
                    {"unit": getattr(tgt, "inst_id", None),
                     "enemyKey": key, "count": len(spawned),
                     "instances": spawned,
                     "node": "HalfIdleSummonEnemyAtTargetMapPos"})
        return bool(spawned)

    def _n_SummonEnemiesOnTargetTile(self, owner, node, ctx):
        """Summon _summonCount enemies on the resolved target's tile
        (SummonEnemiesOnTargetTile; enemy_ltniak deathmark, xbthdr, ...
        The key comes from the node or the blackboard; _excludeRootTile
        skips when the tile is the owner's own tile."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None:
            src = owner
        key = self._summon_enemy_key(node, ctx.get("bb") or {})
        if not key:
            return False
        row = int(getattr(src, "row", 0) or 0)
        col = int(getattr(src, "col", 0) or 0)
        if node.get("_excludeRootTile") and owner is not None and \
                (row, col) == (int(getattr(owner, "row", -1) or -1),
                               int(getattr(owner, "col", -1) or -1)):
            return True
        count = max(1, int(_num(node.get("_summonCount"), 1.0)))
        off = float((node.get("_randomOffsetBound") or {}).get(
            "_serializedValue", 0.0) or 0.0)
        spawned = []
        for _ in range(count):
            rr, cc = row, col
            if off > 0 and battle.rng is not None:
                try:
                    rr = max(0, min(battle.map.rows - 1,
                                    row + battle.rng.Next(-1, 2)))
                    cc = max(0, min(battle.map.cols - 1,
                                    col + battle.rng.Next(-1, 2)))
                except Exception:
                    pass
            e = battle.spawn_enemy_directive(key, rr, cc)
            if e is None:
                continue
            if node.get("_unharmful"):
                e.is_unharmful = True
            if node.get("_addBuffToEnemy") and node.get("_buffToEnemy"):
                self._apply_summon_buffs(battle, e,
                                         [node.get("_buffToEnemy")],
                                         ctx.get("bb") or {}, owner)
            spawned.append(e.inst_id)
        battle.emit(battle.tick, "enemy_summoned",
                    {"unit": getattr(src, "inst_id", None),
                     "enemyKey": key, "count": len(spawned),
                     "instances": spawned,
                     "node": "SummonEnemiesOnTargetTile"})
        return bool(spawned)

    def _n_AOEDamage(self, owner, node, ctx):
        """Deal damage to all units of the target side within range_radius
        of the source unit."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        radius = _num(bb.get("range_radius"), 1.5)
        amount = _num(bb.get("damage"), None)
        if amount is None:
            scale = _num(bb.get("atk_scale"), 1.0)
            atk = _num(getattr(getattr(src, "attributes", None), "get",
                               lambda k: 0.0)("atk"), 0.0)
            amount = atk * scale
        dmg_type = self._dmg_type(node.get("_damageType"))
        opts = node.get("_targetOptions") or {}
        hit = 0
        for u in (list(battle.get_enemies()) +
                  list(battle.get_operators()) +
                  list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if not _passes_target_options(u, opts):
                continue
            if abs(u.row - src.row) > radius or \
                    abs(u.col - src.col) > radius:
                continue
            battle.apply_damage(u, amount, dmg_type, source=src,
                                no_hit_recovery=True)
            hit += 1
        return hit > 0

    def _n_FinishDerivedBuff(self, owner, node, ctx):
        """Finish (remove) the buff that owns this node."""
        battle = self.battle
        if not battle:
            return False
        entry = (ctx.get("bb") or {}).get("_buff_entry")
        if entry is None or not entry.get("key"):
            return False
        try:
            battle.buffs.remove(owner, entry["key"])
        except Exception:
            pass
        return True

    def _n_CreateBuffStacked(self, owner, node, ctx):
        """Materialise an embedded buff with stack layers."""
        battle = self.battle
        if not battle:
            return False
        bd = dict(node.get("_buff") or {})
        if not bd.get("buffKey"):
            return False
        bb = dict(ctx.get("bb") or {})
        entry = materialise_buff(battle, owner, bd, bb, owner)
        if entry and entry.get("key"):
            battle.add_buff(owner, entry)
        return True

    def _n_ModifyBlackboard(self, owner, node, ctx):
        """Set chain blackboard key(s) to _value (or add to origin)."""
        bb = ctx.get("bb")
        if bb is None:
            return True
        keys = [k.strip() for k in str(node.get("_blackboardKeys") or "").split(
            ",") if k.strip()]
        if not keys:
            return True
        val = node.get("_value")
        try:
            val = float(val)
        except (TypeError, ValueError):
            pass
        for k in keys:
            if node.get("_addBasedOriginValue") and isinstance(val, float):
                bb[k] = _num(bb.get(k), 0.0) + val
            else:
                bb[k] = val
        return True

    def _n_InterruptAbility(self, owner, node, ctx):
        """Interrupt the owner's current ability cast."""
        battle = self.battle
        sc = getattr(owner, "skill_controller", None)
        if sc is None or sc.casting is None:
            return False
        try:
            from .consts import FinishReason
            sc.casting._finish(FinishReason.INTERRUPTED)
        except Exception:
            pass
        return True

    def _n_IsDamage(self, owner, node, ctx):
        """Gate: this is a damage event."""
        return ctx.get("damage") is not None

    def _n_IsHeal(self, owner, node, ctx):
        """Gate: this is a heal event (heal dispatches are not wired to
        the engine yet, so this conservatively gates False)."""
        return bool(ctx.get("_is_heal"))

    def _n_DamageViaMaxHpRatio(self, owner, node, ctx):
        """Deal maxHp x ratio PURE damage to the resolved target."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or getattr(u, "dead", False):
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_ratioKey") or (
            "hp_ratio" if bb.get("hp_ratio") is not None else "ratio")
        ratio = _num(bb.get(key), 0.0)
        base = getattr(owner, "max_hp", 0.0)
        if node.get("_getMaxHpFromTarget"):
            base = getattr(u, "max_hp", base)
        amount = float(base or 0.0) * ratio
        dmg_type = self._dmg_type(node.get("_damageType"))
        if amount > 0:
            battle.apply_damage(u, amount, dmg_type, source=owner,
                                no_hit_recovery=True)
        return True

    def _n_FilterByTargetSpRatio(self, owner, node, ctx):
        """Gate: the resolved unit's sp/spMax compares against _spRatio."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        mx = float(getattr(u, "sp_max", 0.0) or 0.0)
        if mx <= 0:
            return False
        ratio = float(getattr(u, "sp", 0.0) or 0.0) / mx
        want = _num(node.get("_spRatio"), 0.0)
        cond = str(node.get("_condType") or "GE").upper()
        if cond in ("GE",):
            return ratio >= want
        if cond == "LE":
            return ratio <= want
        if cond == "GT":
            return ratio > want
        if cond == "LT":
            return ratio < want
        if cond in ("EQUALS", "EQ"):
            return ratio == want
        return True

    def _n_AssignBuffCountIntoBlackboard(self, owner, node, ctx):
        """Copy a buff's stack count into the chain blackboard."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        key = node.get("_buffKey") or ""
        bkey = node.get("_stackCountKey")
        bb = ctx.get("bb")
        if u is None or not key or not bkey or bb is None:
            return False
        entry = battle.buffs.get(u, key)
        cnt = int((entry or {}).get("layers", 0) or 0)
        if node.get("_stackCountPeeling") and entry:
            cnt = max(0, cnt + int(node.get("_stackCountPeeling") or 0))
        bb[bkey] = cnt
        return True

    def _n_AssignAttributeToBB(self, owner, node, ctx):
        """Copy a resolved unit's attribute into the chain blackboard."""
        u = _source_unit(self.battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        bkey = node.get("_blackboardKey")
        bb = ctx.get("bb")
        if u is None or not bkey or bb is None:
            return False
        atype = str(node.get("_attributeType") or "").upper()
        stat = {"MOVE_SPEED": "moveSpeed", "ATK": "atk", "DEF": "def",
                "MAX_HP": "maxHp", "MAGIC_RESISTANCE": "magicResistance",
                "ATTACK_SPEED": "attackSpeed", "BLOCK_CNT": "blockCnt",
                "COST": "cost"}.get(atype)
        if stat and hasattr(u, "attributes"):
            bb[bkey] = u.attributes.get(stat)
        return True

    def _n_ChangeMotionMode(self, owner, node, ctx):
        """Switch the resolved unit's motion mode (WALK=0 / FLY=1)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or node.get(
            "_targetType"), owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        mode = str(node.get("_motionMode") or "WALK").upper()
        u._motion_mode = 1 if mode == "FLY" else 0
        if battle:
            battle.emit(battle.tick, "enemy_motion_mode",
                        {"unit": getattr(u, "inst_id", None),
                         "motion": mode})
        return True

    def _n_TriggerBuff(self, owner, node, ctx):
        """Force-fire ON_BUFF_TRIGGER on the current buff entry."""
        battle = self.battle
        if not battle:
            return False
        entry = (ctx.get("bb") or {}).get("_buff_entry")
        if entry is None:
            return False
        try:
            battle.buffs._fire(owner, entry, "ON_BUFF_TRIGGER",
                               source=entry.get("source"))
        except Exception:
            pass
        return True

    def _n_LogExtraBattleInfo(self, owner, node, ctx):
        """Surface an extra-battle-info log as an observer event."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_key") or ""
        if node.get("_loadKeyFromBlackBoard"):
            key = bb.get("_log_key") or key
        battle.emit(battle.tick, "battle_log",
                    {"unit": getattr(owner, "inst_id", None),
                     "key": key,
                     "value": node.get("_additionValue") or 1})
        return True

    def _n_FixedValueDamage(self, owner, node, ctx):
        """Deal fixed damage (bb _damageKey, or atk x _atkScaleKey) to the
        resolved target."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or getattr(u, "dead", False):
            return False
        bb = ctx.get("bb") or {}
        dkey = node.get("_damageKey") or "damage"
        amount = _num(bb.get(dkey), None)
        if amount is None and node.get("_atkScaleKey"):
            scale = _num(bb.get(node.get("_atkScaleKey")), 1.0)
            amount = _num(getattr(owner, "attributes", None)
                          and owner.attributes.get("atk"), 0.0) * scale
        if amount is None:
            amount = 0.0
        dmg_type = self._dmg_type(node.get("_damageType"))
        if amount > 0:
            battle.apply_damage(u, amount, dmg_type, source=owner,
                                no_hit_recovery=True)
        return True

    def _n_AssignBuffBlackboardFromOthers(self, owner, node, ctx):
        """Copy a value from another buff's blackboard into a buff on the
        resolved unit."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        bkey = node.get("_buffKey")
        bbkey = node.get("_blackboardKey")
        vkey = node.get("_valueKey")
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if u is None or not bkey or not bbkey:
            return False
        entry = battle.buffs.get(u, bkey)
        if entry is None:
            return False
        val = None
        if src is not None:
            val = (battle.buffs.get(src, bkey) or {}).get(
                "blackboard", {}).get(vkey)
        if val is None:
            val = (ctx.get("bb") or {}).get(vkey)
        entry.setdefault("blackboard", {})
        entry["blackboard"][bbkey] = val
        return True

    def _n_ModifyAbilityBlackboardAndCast(self, owner, node, ctx):
        """Write chain-blackboard values into an ability's blackboard and
        cast it (e.g. buff-scaled Poison)."""
        battle = self.battle
        if not battle:
            return False
        sc = getattr(owner, "skill_controller", None)
        if sc is None:
            return False
        ability = node.get("_ability") or ""
        keys = [k.strip() for k in str(
            node.get("_blackboardKeys") or "").split(",") if k.strip()]
        bb = ctx.get("bb") or {}
        found = False
        for s in getattr(sc, "skills", None) or []:
            if s.prefab_key == ability:
                for k in keys:
                    if k in bb:
                        s.blackboard[k] = bb[k]
                found = True
                break
        if not found:
            return False
        try:
            sc.force_trigger(ability)
        except Exception:
            pass
        return True

    def _n_CheckCharSkillAffecting(self, owner, node, ctx):
        """Gate: a character skill is currently affecting the unit
        (approximated by buffs sourced from an operator with an active
        skill)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        for bf in (getattr(u, "buffs", None) or []):
            src = bf.get("source")
            if src is not None and getattr(src, "side", 0) == 1:
                sc = getattr(src, "skill_controller", None)
                if sc is not None and getattr(sc, "active", None) is not None:
                    return True
        return False

    def _n_TriggerEnemySkill(self, owner, node, ctx):
        """Trigger a skill by prefabKey on the resolved unit (emits an
        event; casts it when the unit's controller exposes a trigger)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        name = node.get("_skillName") or ""
        if u is None or not name:
            return False
        battle.emit(battle.tick, "skill_trigger",
                    {"unit": getattr(u, "inst_id", None), "skill": name})
        sc = getattr(u, "skill_controller", None)
        if sc is not None and hasattr(sc, "force_trigger"):
            try:
                sc.force_trigger(name)
            except Exception:
                pass
        return True

    def _n_BlackboardAdd(self, owner, node, ctx):
        """Add a value to a chain blackboard key (from _addition or bb
        _additionKey), optionally clamped by _maxKey."""
        bb = ctx.get("bb")
        if bb is None:
            return True
        key = node.get("_blackboardKey")
        if not key:
            return True
        add = node.get("_addition")
        if add is None and node.get("_additionKey"):
            add = bb.get(node.get("_additionKey"))
        try:
            add = float(add or 0.0)
        except (TypeError, ValueError):
            return True
        cur = _num(bb.get(key), 0.0)
        bb[key] = cur + add
        if node.get("_maxKey"):
            try:
                mx = float(bb.get(node.get("_maxKey")) or 0.0)
                if mx > 0:
                    bb[key] = min(mx, bb[key])
            except (TypeError, ValueError):
                pass
        return True

    def _n_FinishDerivedBuffById(self, owner, node, ctx):
        """Remove a buff by key from the resolved target (same as
        FinishBuffsById)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        key = node.get("_buffKey")
        if u is None or not key:
            return False
        try:
            battle.buffs.remove(u, key)
        except Exception:
            pass
        return True

    def _n_AddBuffBlackboard(self, owner, node, ctx):
        """Add a value into the blackboard of a buff on the resolved unit."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        key = node.get("_buffKey")
        bkey = node.get("_blackboardKey")
        if u is None or not key or not bkey:
            return False
        entry = battle.buffs.get(u, key)
        if entry is None:
            return False
        add = node.get("_addition")
        if add is None and node.get("_additionKey"):
            add = (ctx.get("bb") or {}).get(node.get("_additionKey"))
        try:
            add = float(add or 0.0)
        except (TypeError, ValueError):
            return True
        entry.setdefault("blackboard", {})
        entry["blackboard"][bkey] = _num(entry["blackboard"].get(bkey), 0.0) \
            + add
        return True

    def _n_AssignBuffBlackboard(self, owner, node, ctx):
        """Assign a blackboard value into a buff's blackboard key."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        key = node.get("_buffKey")
        bkey = node.get("_blackboardKey")
        vkey = node.get("_valueKey")
        if u is None or not key or not bkey:
            return False
        entry = battle.buffs.get(u, key)
        if entry is None:
            return False
        val = (ctx.get("bb") or {}).get(vkey) if vkey else None
        if val is None and node.get("_assignString"):
            val = node.get("_value") or ""
        entry.setdefault("blackboard", {})
        entry["blackboard"][bkey] = val
        return True

    def _n_AssignValueToBB(self, owner, node, ctx):
        """Write a value into the chain blackboard for later nodes."""
        bb = ctx.get("bb")
        if bb is None:
            return True
        key = node.get("_blackboardKey")
        if not key:
            return True
        src = node.get("_copyFromKey")
        bb[key] = bb.get(src) if src else node.get("_value")
        return True

    def _n_InstantKill(self, owner, node, ctx):
        """Kill the resolved target outright (death effects fire)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if (u is None or u is owner) and \
                str(node.get("_targetType") or "").upper() == "TARGET":
            # TARGET in a buff firing during a cast resolves to the
            # ability's target (e.g. devour kills the victim); suicide
            # buffs without a cast fall back to the owner
            u = getattr(owner, "_skill_target", None) or u
        if u is None or getattr(u, "dead", False):
            return False
        if getattr(u, "_death_reason", None) is None:
            u._death_reason = "KILLED"
        u.take_damage(u.hp + 1.0)
        try:
            battle.buffs.on_owner_killed(u)
        except Exception:
            pass
        battle.emit(battle.tick, "instant_kill",
                    {"unit": u.inst_id, "source":
                     getattr(owner, "inst_id", None)})
        return True

    def _n_FinishBuffsById(self, owner, node, ctx):
        """Remove a buff by key from the resolved target."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        key = node.get("_buffKey")
        if u is None or not key:
            return False
        try:
            battle.buffs.remove(u, key)
        except Exception:
            pass
        return True

    def _n_ModifySp(self, owner, node, ctx):
        """Add a fixed SP amount (node _value or blackboard) to the
        resolved unit (clamped to sp_max)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType"), owner,
                         ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.get("bb") or {}
        amount = node.get("_value")
        if amount is None:
            amount = bb.get(node.get("_valueKey") or "sp")
        try:
            amount = float(amount or 0.0)
        except (TypeError, ValueError):
            return False
        if node.get("_modifyByRatio"):
            amount = float(getattr(u, "sp", 0.0) or 0.0) * float(
                node.get("_modifyRatio") or 0.0)
        sp_max = float(getattr(u, "sp_max", 0.0) or 0.0)
        u.sp = max(0.0, min(sp_max, float(getattr(u, "sp", 0.0) or 0.0)
                            + amount))
        return True

    def _n_FilterDeathReason(self, owner, node, ctx):
        """Gate: the owner died with the given finish reason
        (FALLDOWN / REACH_EXIT / KILLED / OTHER ...)."""
        reason = str(node.get("_finishReason") or "").upper()
        u = _source_unit(self.battle, node.get("_source"), owner,
                         ctx.get("source"))
        return str(getattr(u, "_death_reason", "") or "").upper() \
            == reason

    def _n_SummonEnemiesFollowMyRouteWithBuff(self, owner, node, ctx):
        """Death split summon + immediately attach the embedded buff to
        each summoned enemy."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        key = (node.get("_enemyKey") or bb.get("enemy_key") or
               bb.get("summon_enemy_key") or "")
        try:
            cnt = int(float(node.get("_summonCount") or
                            bb.get("summon_count") or
                            bb.get("count") or 1))
        except (TypeError, ValueError):
            cnt = 1
        src = _source_unit(battle, node.get("_source"), owner,
                           ctx.get("source"))
        if src is None:
            src = owner
        spawned = 0
        for _ in range(max(1, cnt)):
            if not key:
                continue
            try:
                u = battle.spawn_enemy_directive(
                    key, getattr(src, "row", 0), getattr(src, "col", 0))
            except Exception:
                u = None
            if u is None:
                continue
            if node.get("_unharmful") or node.get("_useLocalUnharmfulFlag"):
                u.is_unharmful = True
            nsb = node.get("_noSourceBuff") or {}
            if nsb.get("buffKey") and node.get("_addNoSourceBuffImmediately"):
                try:
                    entry = materialise_buff(battle, u, dict(nsb), bb, owner)
                    if entry and entry.get("key"):
                        battle.add_buff(u, entry)
                except Exception:
                    pass
            spawned += 1
        return spawned > 0

    def _n_SummonEnemiesFollowMyRoute(self, owner, node, ctx):
        """Death split: summon enemies at the owner's tile following
        its route (enemyKey/count from node or blackboard)."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        key = (node.get("_enemyKey") or bb.get("enemy_key") or
               bb.get("summon_enemy_key") or "")
        try:
            cnt = int(float(node.get("_summonCount") or
                            bb.get("summon_count") or
                            bb.get("count") or 1))
        except (TypeError, ValueError):
            cnt = 1
        src = _source_unit(battle, node.get("_source"), owner,
                           ctx.get("source"))
        if src is None:
            src = owner
        spawned = 0
        for _ in range(max(1, cnt)):
            if key:
                try:
                    battle.spawn_enemy_directive(
                        key, getattr(src, "row", 0),
                        getattr(src, "col", 0))
                    spawned += 1
                except Exception:
                    pass
        return spawned > 0

    def _n_SummonEnemiesFollowBranchRoute(self, owner, node, ctx):
        """Summon enemies on the owner's tile following its branch route
        (enemyKey from _overrideEnemyKey or blackboard, count from bb),
        attaching the embedded _buffToEnemy when present (e.g.
        trap_bgarmn[sync_hp_from_trap])."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        key = (node.get("_overrideEnemyKey") or bb.get("enemy_key") or
               bb.get("summon_enemy_key") or node.get("_enemyKey") or "")
        try:
            cnt = int(float(bb.get("summon_count") or
                            bb.get("count") or 1))
        except (TypeError, ValueError):
            cnt = 1
        src = _source_unit(battle, node.get("_source"), owner,
                           ctx.get("source"))
        if src is None:
            src = owner
        spawned = 0
        for _ in range(max(1, cnt)):
            if not key:
                continue
            try:
                u = battle.spawn_enemy_directive(
                    key, getattr(src, "row", 0), getattr(src, "col", 0))
            except Exception:
                u = None
            if u is None:
                continue
            if node.get("_unharmful"):
                u.is_unharmful = True
            nb = node.get("_buffToEnemy") or {}
            if nb.get("buffKey"):
                try:
                    entry = materialise_buff(battle, u, dict(nb), bb, owner)
                    if entry and entry.get("key"):
                        battle.add_buff(u, entry)
                except Exception:
                    pass
            spawned += 1
        return spawned > 0


    def _n_AlwaysNext(self, owner, node, ctx):
        return True

    def _n_End(self, owner, node, ctx):
        return False

    # ---- conditions --------------------------------------------------------
    def _n_CheckContainsBuff(self, owner, node, ctx):
        target = _source_unit(self.battle, node.get("_targetType"), owner,
                              ctx.get("source"))
        if target is None:
            return False
        keys = node.get("_buffKeys") or []
        is_and = bool(node.get("isAND"))
        have = [k for k in keys if self.battle.buffs.get(target, k)]
        if not have:
            return False
        return all(have) if is_and else True

    def _n_FilterEPBreakRecoveryType(self, owner, node, ctx):
        """Gate: the bursting element type matches _recoveryType
        (SANITY=0 WATER=1 FIRE=2 DARK=3) or the blackboard key value when
        _readTypeFromBb is set."""
        bb = ctx.get("bb") or {}
        ep = bb.get("_ep_break_type")
        if ep is None:
            return False
        want = None
        if node.get("_readTypeFromBb"):
            bk = node.get("_bbKey")
            if bk:
                try:
                    want = int(float(bb.get(bk)))
                except (TypeError, ValueError):
                    want = None
        else:
            rec = {"SANITY": 0, "WATER": 1, "FIRE": 2, "DARK": 3}
            want = rec.get(str(node.get("_recoveryType") or "").upper())
        return want is not None and int(ep) == int(want)

    def _n_FilterModifierByRealDelta(self, owner, node, ctx):
        """Gate: the modifier delta actually applied was real. For the
        element-damage dispatch (bb._ep_delta present) any nonzero applied
        delta passes; HP/SP-style events use LT=loss / GT=gain."""
        bb = ctx.get("bb") or {}
        if "_ep_delta" in bb:
            try:
                return float(bb.get("_ep_delta", 0.0)) != 0.0
            except (TypeError, ValueError):
                return False
        delta = bb.get("_delta", 0.0)
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            delta = 0.0
        cond = str(node.get("_condType") or "").upper()
        if cond == "LT":
            return delta < 0
        if cond == "GT":
            return delta > 0
        return delta != 0

    def _n_FilterElementDamageModifer(self, owner, node, ctx):
        """Gate: the applied element damage type matches _epType
        (SANITY/WATER/FIRE/DARK) when _filterEPType is set."""
        if not node.get("_filterEPType"):
            return True
        bb = ctx.get("bb") or {}
        ep = bb.get("_ep_type")
        if ep is None:
            return False
        rec = {"SANITY": 0, "WATER": 1, "FIRE": 2, "DARK": 3}
        want = rec.get(str(node.get("_epType") or "").upper())
        return want is not None and int(ep) == int(want)

    def _n_IsTargetInEPBreakRecovery(self, owner, node, ctx):
        """True when the owner is in any (or matching) EP burst recovery."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or \
            ctx.get("target") or owner
        rec = {"SANITY": 0, "WATER": 1, "FIRE": 2, "DARK": 3}
        elem = str(node.get("_elementType") or "NONE").upper()
        types = [rec[elem]] if elem in rec else range(4)
        return any(battle.buffs.get(tgt, f"ep_burst_cd_{t}")
                   for t in types)

    def _n_ApplyElementDamage(self, owner, node, ctx):
        """Apply element EP damage from the source's ATK scaled by
        bb[_epDamageScale] (game ApplyElementDamage)."""
        battle = self.battle
        if not battle:
            return True
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source")) or ctx.get("source")
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or \
            ctx.get("target") or owner
        rec = {"SANITY": 0, "WATER": 1, "FIRE": 2, "DARK": 3}
        ep_type = rec.get(str(node.get("_elementDamageType") or "").upper(),
                          0)
        bb = ctx.get("bb") or {}
        if node.get("_isFixedEpDamage"):
            # fixed EP damage (e.g. ?? T2: 70 sanity per enemy normal attack)
            key = node.get("_fixedEpDamageKey") or "value"
            amount = _num(bb.get(key), _num(node.get("_fixedEpDamage"), 0.0))
            if amount > 0 and tgt is not None and not getattr(
                    tgt, "dead", False):
                battle.add_ep(tgt, ep_type, amount, source=src)
            return True
        key = node.get("_epDamageScale") or "ep_damage_ratio"
        scale = _num(bb.get(key), 0.0)
        if scale <= 0 or tgt is None or getattr(tgt, "dead", False):
            return True
        base = _num(getattr(src, "attributes", None) and
                    src.attributes.get("atk"), 0.0)
        battle.add_ep(tgt, ep_type, base * scale, source=src)
        return True

    def _n_CalculateBlackboardValueViaParams(self, owner, node, ctx):
        """Compute output = (input x multiply) +/- add/minus from the buff
        blackboard and store it back (e.g. alchemist heal zone:
        cached_atk x hp_recovery_per_sec_ratio -> hp_recovery_per_sec)."""
        bb = ctx.get("bb") or {}
        i_key = node.get("_inputKey") or ""
        o_key = node.get("_outputKey") or ""
        if not i_key or not o_key:
            return True
        try:
            v = float(bb.get(i_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return True
        m = node.get("_multiplyParamKey")
        if m:
            v *= float(bb.get(m, 1.0) or 1.0)
        a = node.get("_addParamKey")
        if a:
            v += float(bb.get(a, 0.0) or 0.0)
        s = node.get("_minusParamKey")
        if s:
            v -= float(bb.get(s, 0.0) or 0.0)
        if node.get("_finalAbs"):
            v = abs(v)
        bb[o_key] = v
        return True

    def _n_FinishBuff(self, owner, node, ctx):
        """Finish (remove) the buff that owns this action tree."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        entry = bb.get("_buff_entry")
        if entry is None:
            return True
        key = entry.get("key")
        if key:
            battle.buffs.remove(owner, key)
        return True

    def _n_TriggerBuffsByKeys(self, owner, node, ctx):
        """Trigger ON_BUFF_TRIGGER on the target's buffs matching keys
        (or all buffs when _triggerAllBuffs)."""
        battle = self.battle
        if not battle:
            return False
        target = _source_unit(battle, node.get("_targetType"), owner,
                              ctx.get("source"), ctx.get("target"))
        if target is None:
            return False
        keys = node.get("_buffKeys") or []
        entries = list(getattr(target, "buffs", None) or [])
        if not node.get("_triggerAllBuffs"):
            entries = [e for e in entries if e.get("key") in keys]
        for e in entries:
            battle.buffs._fire(target, e, "ON_BUFF_TRIGGER",
                               source=ctx.get("source"), target=owner)
        return True

    def _n_CheckBlackboardContainsKey(self, owner, node, ctx):
        key = node.get("_blackboardKey")
        bb = ctx.get("bb") or {}
        return key in bb

    def _n_CheckTargetRootTile(self, owner, node, ctx):
        """Check the owner's tile for character-class units (operators /
        tokens) and/or certain enemies (game CheckTargetRootTile). Empty
        character key list means 'any character'."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None:
            return False
        r, c = tgt.row, tgt.col
        if node.get("_hasCharacter"):
            keys = node.get("_characterKeys") or []
            chars = [u for u in list(battle.get_operators()) +
                     list(battle.get_tokens())
                     if not u.dead and u.row == r and u.col == c]
            if keys:
                cids = {getattr(u, "char_id", "") or getattr(u, "token_id", "")
                        for u in chars}
                if not (cids & set(keys)):
                    return False
            elif not chars:
                return False
        if node.get("_hasCertainEnemy"):
            keys = node.get("_enemyKeys") or []
            foes = [e for e in battle.get_enemies()
                    if not e.dead and e.row == r and e.col == c]
            if keys:
                eids = {getattr(e, "enemy_key", "") for e in foes}
                if not (eids & set(keys)):
                    return False
            elif not foes:
                return False
        return True

    def _n_CheckHeightTypeOfRootTile(self, owner, node, ctx):
        """Tile height gate: LOWLAND (buildable bit 1) / HIGHLAND (bit 2)."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None:
            return False
        tile = battle.map.tile(tgt.row, tgt.col)
        if tile is None:
            return False
        bt = tile.buildable_type
        h = str(node.get("_heightType") or "").upper()
        if h == "LOWLAND":
            return bool(bt is not None and (int(bt) & 1))
        if h == "HIGHLAND":
            return bool(bt is not None and (int(bt) & 2))
        return True

    def _n_CheckCharacterGroupTag(self, owner, node, ctx):
        target = _source_unit(self.battle, node.get("_targetType"), owner,
                              ctx.get("source"))
        tag = node.get("_groupTag")
        if target is None or not tag:
            return False
        data = getattr(getattr(self.battle, "char_data", None) or {}, "get",
                       lambda k: None)(getattr(target, "char_id", "")) or {}
        return tag in (data.get("tagList") or []) or tag in (
            data.get("groupId") or "") or tag in (data.get("teamId") or "")

    def _n_CheckEnemySkillSelector(self, owner, node, ctx):
        return True  # structural node; treat as pass

    def _n_FilterAbilityFamily(self, owner, node, ctx):
        """Gate: the fired ability family matches _familyGroupMask
        (ATTACK / COMBAT / ATTACK_OR_COMBAT ...). We dispatch this event
        only from normal attacks, so any attack/combat mask passes."""
        mask = str(node.get("_familyGroupMask") or "").upper()
        if not mask or mask == "ALL":
            return True
        if mask in ("ATTACK", "COMBAT", "ATTACK_OR_COMBAT"):
            return True
        return False

    def _n_FilterByAbilityIgnorePalsyInterrupt(self, owner, node, ctx):
        """Gate: only abilities that can be interrupted by palsy pass when
        ``_unset`` is true. Normal attacks qualify (skill-cast abilities
        that ignore palsy interruption fail)."""
        if node.get("_unset"):
            return True
        return False

    # ---- damage -----------------------------------------------------------
    def _n_BlockDamage(self, owner, node, ctx):
        battle = self.battle
        dmg = ctx.get("damage") or {}
        target = ctx.get("target") or owner
        if not dmg:
            return True
        amount = float(dmg.get("amount") or 0.0)
        if amount <= 0:
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_damageValueKey") or "damage_block"
        block = _num(bb.get(key), 0.0)
        if block <= 0:
            block = _num(bb.get("damage_block"), 0.0)
        if block <= 0:
            # block value usually keyed by the template key (damage_block[all])
            for bkey in (bb.get("template_key"), bb.get("buff_key")):
                if bkey:
                    block = _num(bb.get(bkey), 0.0)
                    if block > 0:
                        break
        if node.get("_useDynamicVar"):
            block = _num(bb.get(node.get("_dynamicVarKey") or key), 0.0)
        if node.get("_useFixedValue"):
            block = _num(node.get("_fixedValue"), 0.0)
        if block <= 0:
            return True
        blocked = min(amount, block)
        # damage reduction: store on the damage event so the damage pipeline
        # can subtract it (v1: apply directly as shield-like absorption)
        dmg["blocked"] = dmg.get("blocked", 0.0) + blocked
        dmg["amount"] = max(0.0, amount - blocked)
        if battle:
            battle.emit(battle.tick, "buff_block_damage",
                        {"unit": target.inst_id, "blocked": round(blocked, 3),
                         "buff": owner.buffs[-1]["key"] if owner.buffs else ""})
        return True

    def _n_DamageScale(self, owner, node, ctx):
        dmg = ctx.get("damage") or {}
        if not dmg:
            return True
        bb = ctx.get("bb") or {}
        # game DamageScale node (dump.cs:567695) has no _scaleKey field:
        # it reads the buff blackboard's "damage_scale" (or _customKey
        # when set, e.g. damage_share).  The old "scale" default made the
        # 295 stock templates multiply damage by 0 (missing key) instead
        # of leaving it unchanged.
        key = node.get("_customKey") or node.get("_scaleKey") or \
            "damage_scale"
        scale = bb.get(key)
        if scale is None and key != "damage_scale":
            scale = bb.get("damage_scale")
        if scale is None and key != "scale":
            scale = bb.get("scale")
        if scale is None:
            return True        # no value -> leave damage unchanged
        scale = float(scale)
        if node.get("_isOneMinus"):
            scale = 1.0 - scale
        dmg["amount"] = max(0.0, float(dmg.get("amount") or 0.0) * scale)
        return True

    def _n_ConsumeTrySetHpZeroModifier(self, owner, node, ctx):
        """Spend one TrySetHpZero (lethal-hit immunity) modifier when a
        lethal hit tries to zero the owner's HP (Surtr T2, Horn T1,
        Bena). _blockThisHpSet fully cancels the HP-zero; the consumed
        marker is carried on the damage ctx so the caller can keep the
        unit at 1 HP and fire ON_POST_TRY_SET_HP_ZERO."""
        dmg = ctx.get("damage")
        if dmg is None:
            return False
        if node.get("_dontConsumeWhenUndeadable") and owner.undeadable():
            return True      # already immortal; nothing to spend
        dmg["_hp_zero_consumed"] = True
        if node.get("_blockThisHpSet"):
            dmg["_hp_zero_blocked"] = True
        return True

    def _n_IsConsumerOfTrySetHpZeroModifier(self, owner, node, ctx):
        """Gate: the TrySetHpZero modifier was actually consumed on this
        lethal-hit event (drives the ON_POST chain: Surtr gains UNDEADABLE,
        Horn gains the stat buffs)."""
        dmg = ctx.get("damage") or {}
        return bool(dmg.get("_hp_zero_consumed"))

    def _n_AssignRootTileToBB(self, owner, node, ctx):
        """Write the resolved unit's row/col (or root tile key) into the
        blackboard (enemy_cjdoor_direction drives door-facing)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        rk = node.get("_rowKey") or "row"
        ck = node.get("_colKey") or "col"
        if node.get("_bbKey"):
            bb[node.get("_bbKey")] = getattr(
                getattr(self.battle, "map", None) and
                self.battle.map.tile(getattr(u, "row", 0),
                                     getattr(u, "col", 0)),
                "tile_key", None)
            return True
        if node.get("_assignAsString"):
            bb[rk] = str(getattr(u, "row", 0))
            bb[ck] = str(getattr(u, "col", 0))
        else:
            bb[rk] = getattr(u, "row", 0)
            bb[ck] = getattr(u, "col", 0)
        return True

    def _n_AssignGridPositionToBlackboard(self, owner, node, ctx):
        """Write the resolved unit's grid row/col into the blackboard
        (aglina_m23[record_position]; default keys row/col)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        rk = node.get("_gridRowKey") or "row"
        ck = node.get("_gridColKey") or "col"
        bb[rk] = getattr(u, "row", 0)
        bb[ck] = getattr(u, "col", 0)
        return True

    def _n_IsBlackboardEqualWithFloat(self, owner, node, ctx):
        """Gate: bb[_var] equals _compareValue."""
        bb = ctx.get("bb") or {}
        key = node.get("_var")
        if not key:
            return False
        try:
            return abs(_num(bb.get(key), 0.0) - _num(node.get("_compareValue"),
                                                     0.0)) < 1e-9
        except (TypeError, ValueError):
            return False

    def _n_FilterByTargetHp(self, owner, node, ctx):
        """Gate: the resolved unit's HP compares against _hpValue."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        hv = node.get("_hpValue") or {}
        want = _num(hv.get("_serializedValue", hv.get("value")), 0.0)
        got = _num(getattr(u, "hp", 0.0) or 0.0)
        cond = str(node.get("_condType") or "LE").upper()
        if cond == "LT":
            return got < want
        if cond == "GT":
            return got > want
        if cond == "GE":
            return got >= want
        if cond == "LE":
            return got <= want
        if cond in ("EQUALS", "EQ", "=="):
            return got == want
        return True

    def _n_AssignDirectionToBB(self, owner, node, ctx):
        """Write the resolved unit's facing direction into the blackboard
        (_isReverse flips it; trap_ftshad_overlapped_target)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackboardKey") or "direction"
        d = int(getattr(u, "direction", 1) or 1)
        if node.get("_isReverse"):
            d = (d + 2) % 4
        bb[key] = d
        return True

    def _n_CheckDirection(self, owner, node, ctx):
        """Gate: the source's facing equals / opposes the target's facing
        (blower_s_character EQUAL / OPPOSITE)."""
        battle = self.battle
        src = _source_unit(battle, node.get("_source") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None:
            return False
        sd = int(getattr(src, "direction", 1) or 1)
        td = int(getattr(tgt, "direction", 1) or 1)
        judge = str(node.get("_judgeType") or "EQUAL").upper()
        if judge == "OPPOSITE":
            return abs(sd - td) == 2
        return sd == td

    def _n_CheckFaceDirection(self, owner, node, ctx):
        """Gate: the resolved unit faces the named direction (UP/RIGHT/
        DOWN/LEFT; simulator direction 0=up 1=right 2=down 3=left)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        want = {"UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3}.get(
            str(node.get("_direction") or "").upper(), None)
        if want is None:
            return True
        return int(getattr(u, "direction", 1) or 1) == want

    def _n_UpdateEnemyCurrentTile(self, owner, node, ctx):
        """Sync the enemy's row/col with its interpolated position (flying
        enemies landing: enemy_durokt[fly] / enemy_mheagl_fly)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        px = getattr(u, "pos_x", None)
        py = getattr(u, "pos_y", None)
        if px is None or py is None:
            return True
        u.col = int(round(float(px)))
        u.row = int(round(float(py)))
        return True

    def _n_AssignDamageValueToBlackboard(self, owner, node, ctx):
        """Write the current damage/heal value (optionally x scale) into
        bb['value'] (hbisc2_tr trait heal / enemy_mhrors damage counter)."""
        bb = ctx.setdefault("bb", {})
        dmg = ctx.get("damage") or {}
        amount = _num(dmg.get("amount"), 0.0)
        sk = node.get("_scaleKey")
        if sk and not node.get("_assignValueWithoutCalculate"):
            amount = amount * _num(bb.get(sk), 1.0)
        bb["value"] = amount
        return True

    def _n_AssignCurSpToBB(self, owner, node, ctx):
        """Write the resolved unit's current SP (or SP ratio) into the
        blackboard (enemy_trcerb_strong_check / trap_trpot_mark)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackboardKey") or "sp"
        sp = _num(getattr(u, "sp", 0.0) or 0.0)
        if node.get("_isRatio"):
            mx = _num(getattr(u, "sp_max", 0.0) or 0.0)
            bb[key] = (sp / mx) if mx > 0 else 0.0
        else:
            bb[key] = sp
        return True

    def _n_AssignModifierValueIntoBlackboard(self, owner, node, ctx):
        """Write the current damage-modifier value into the blackboard
        (enemy_muwiz_t[shield] absorbs the incoming hit; enemy_lrtsia
        counts hp steps)."""
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackboardKey") or "value"
        dmg = ctx.get("damage") or {}
        bb[key] = _num(dmg.get("amount"), _num(dmg.get("_delta"), 0.0))
        return True

    def _n_CheckTargetInRange(self, owner, node, ctx):
        """Gate: the resolved target lies inside the source's range shape
        (acdrop_t_1 / ceylon_trait heal-range gating)."""
        battle = self.battle
        if not battle:
            return True
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        src = _source_unit(battle, node.get("_soureceType") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        if tgt is None or src is None:
            return False
        rid = node.get("_rangeId")
        if not rid:
            return True
        try:
            from .battle import range_offsets_rotated
            cells = range_offsets_rotated(rid, getattr(src, "direction", 1))
        except Exception:
            return True
        tpos = (getattr(tgt, "row", 0), getattr(tgt, "col", 0))
        spos = (getattr(src, "row", 0), getattr(src, "col", 0))
        return tpos in [(spos[0] + dr, spos[1] + dc) for dr, dc in cells]

    def _n_SetSharedFlag(self, owner, node, ctx):
        """Tag the current damage context with a shared flag (e.g. Platinium
        T2 damage may hurt sleeping entities)."""
        dmg = ctx.get("damage")
        if dmg is None:
            return True
        flags = dmg.setdefault("_shared_flags", set())
        flags.add(str(node.get("_sharedFlagIndex") or ""))
        return True

    def _n_CheckIfDamageHasSharedFlags(self, owner, node, ctx):
        """Gate: the damage context carries the shared flag(s); _isUnset
        negates (INSTANT_KILL_LIKE_DAMAGE split checks)."""
        dmg = ctx.get("damage") or {}
        flags = dmg.get("_shared_flags") or set()
        want = str(node.get("_sharedFlags") or "")
        has = bool(want and want in flags)
        return (not has) if node.get("_isUnset") else has

    def _n_AttributeModifierWithCertainBuffCount(self, owner, node, ctx):
        """Attribute modifier scaled by the stack count of a referenced
        buff (takila TR atk per stack / enemy_cbshld def stacking)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        bk = node.get("_buffKey") or ""
        entry = battle.buffs.get(u, bk) if bk else None
        cnt = int((entry or {}).get("layers", 0) or 0)
        if node.get("_useOneAsMinCnt"):
            cnt = max(1, cnt)
        mx = int(node.get("_maxCnt") or 0)
        if mx > 0:
            cnt = min(cnt, mx)
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return True
        value = _num(bb.get("value"), 0.0)
        formula = str(node.get("_formulaType") or "ADDITION").upper()
        layer = "mul" if formula in ("MULTIPLIER", "PERCENT") else "add"
        battle.add_buff(u, {
            "key": "op_buffcnt_attr", "remaining_ticks": 30,
            "layers": 1, "stat": stat, layer: value * cnt, "source": owner})
        if node.get("_writeModifyValueToBB") and node.get("_writeToBBKey"):
            bb[node.get("_writeToBBKey")] = value * cnt
        return True

    def _n_CheckAbnormalFlags(self, owner, node, ctx):
        """Gate: the resolved unit carries any of the listed abnormal flags
        (dsurch damaged-check / enemy_mmstck source check)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        want = {"STUNNED": 0, "SILENCED": 12, "UNMOVABLE": 13, "FROZEN": 16,
                "LEVITATE": 25, "DOZE": 43}.get
        for f in (node.get("_abnormalFlags") or []):
            fid = want(str(f).upper())
            if fid is not None and u.flag(fid):
                return True
        return False

    def _n_CreateBuffToCertainProfession(self, owner, node, ctx):
        """Apply the embedded buff to every operator (or token) whose
        profession matches _professionMask (enemy_murad check / smephi
        poison before death)."""
        battle = self.battle
        if not battle:
            return True
        mask = str(node.get("_professionMask") or "").upper()
        names = {"WARRIOR": 1, "SNIPER": 2, "TANK": 4, "MEDIC": 8,
                 "SUPPORT": 16, "CASTER": 32, "SPECIAL": 64, "TOKEN": 128,
                 "PIONEER": 512}
        profs = [names[p.strip()] for p in mask.split(",")
                 if p.strip() in names]
        bd = node.get("_buffData") or {}
        if not bd.get("buffKey"):
            return False
        hit = 0
        for u in list(battle.get_operators()) + list(battle.get_tokens()):
            if getattr(u, "dead", False):
                continue
            prof = int(getattr(u, "profession", 0) or 0)
            is_token = bool(getattr(u, "token_id", None))
            if 512 in profs and is_token:
                pass
            elif profs and prof not in profs:
                continue
            entry = materialise_buff(battle, u, dict(bd), ctx.get("bb") or {},
                                     owner)
            if entry and entry.get("key"):
                battle.add_buff(u, entry)
                hit += 1
        return hit > 0

    def _n_AssignAttributeAsDynamicVarToBB(self, owner, node, ctx):
        """Write an attribute (x blackboard scale) into bb['value']
        (enemy_ncrmcr sacrifice hit / sgactr count)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return False
        val = _num(getattr(getattr(u, "attributes", None), "get",
                           lambda k: 0.0)(stat), 0.0)
        bb = ctx.setdefault("bb", {})
        sv = node.get("_scaleVar") or ""
        if sv:
            val = val * _num(bb.get(sv), 1.0)
        # the game's "dynamic var": consumers read bb["dynamic"]
        # (_useDynamicVar / _valueKey "dynamic", e.g. \u7eaf\u70c1 T1
        # \u6c29\u6c33, many shield/BlockDamage templates).  "value" is kept
        # for legacy consumers that were tuned to it.
        bb["dynamic"] = val
        bb["value"] = val
        return True

    def _n_AssignAttributeRawDataIntoBlackboard(self, owner, node, ctx):
        """Write the raw attribute value into the blackboard key
        (duskld/duskls default max_hp for revive scaling)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return False
        bb = ctx.setdefault("bb", {})
        bb[node.get("_blackBoardKey") or "value"] = _num(
            getattr(getattr(u, "attributes", None), "get",
                    lambda k: 0.0)(stat), 0.0)
        return True

    def _n_SetWithdrawCostRecoverRatio(self, owner, node, ctx):
        """Set the resolved unit's withdraw cost recovery ratio
        (bpipe_e_trait / wildmn_e_trait gaincost)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        if node.get("_isReset"):
            u._withdraw_cost_recover_ratio = None
        else:
            u._withdraw_cost_recover_ratio = _num(node.get("_ratio"), 0.0)
        return True

    def _n_ResetAbilityAtkScale(self, owner, node, ctx):
        """Overwrite the named ability's atk scale from the blackboard
        (enemy_tinker Missile / acdums AOE)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        sc = getattr(owner, "skill_controller", None)
        if sc is None:
            return True
        act = getattr(sc, "active", None)
        sk = getattr(act, "skill", None)
        name = str(node.get("_abilityName") or "")
        if name and sk is not None:
            got = str(getattr(sk, "name", "") or "") or \
                str(getattr(sk, "skill_id", "") or "")
            if name not in got:
                return True
        key = node.get("_atkScale") or "atk_scale"
        if node.get("_overwriteAtkScale") and key in bb:
            if sk is not None:
                sk.blackboard[key] = bb[key]
            elif act is not None:
                act.blackboard[key] = bb[key]
            return True
        return False

    def _n_CheckTraitAbilityBlackboard(self, owner, node, ctx):
        """Gate: compare two values on the owner's trait/skill blackboard
        (coldst attack counter vs max)."""
        bb = ctx.get("bb") or {}
        lk = node.get("_leftBlackboardKey")
        if not lk:
            return False
        got = _num(bb.get(lk), 0.0)
        rk = node.get("_rightBlackboardKey")
        want = _num(bb.get(rk), _num(node.get("_rightValue"), 0.0)) \
            if rk else _num(node.get("_rightValue"), 0.0)
        cmp = str(node.get("_compareType") or "GE").upper()
        if cmp == "GT":
            return got > want
        if cmp == "GE":
            return got >= want
        if cmp == "LT":
            return got < want
        if cmp == "LE":
            return got <= want
        if cmp in ("EQUALS", "EQ", "=="):
            return got == want
        return True

    def _n_FilterByAbilityFinishReason(self, owner, node, ctx):
        """Gate: the finished ability's reason matches (NORMAL_EXIT /
        INTERRUPTED; hlsnip S1 SP refund / spbell CD reset)."""
        bb = ctx.get("bb") or {}
        reason = bb.get("_ability_finish_reason") or \
            getattr(owner, "_ability_finish_reason", "")
        want = str(node.get("_finishReason") or "").upper()
        return str(reason or "").upper() == want

    def _n_DamageScaleBaseOnDistance(self, owner, node, ctx):
        """Scale the damage by the source-target distance (glaze_e_trait /
        cuttle_e_trait; scale from bb max_scale, distance threshold)."""
        battle = self.battle
        dmg = ctx.get("damage") or {}
        if not dmg:
            return True
        bb = ctx.get("bb") or {}
        src = _source_unit(battle, node.get("_sourceType") or "MODIFIER_SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_targetType") or "MODIFIER_TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None:
            return True
        dist = ((getattr(tgt, "row", 0) - getattr(src, "row", 0)) ** 2 +
                (getattr(tgt, "col", 0) - getattr(src, "col", 0)) ** 2) ** 0.5
        min_d = _num(node.get("_minTriggerDistance"), 0.0)
        if dist < min_d:
            return True
        max_scale = _num(bb.get("max_scale"), _num(node.get("_maxScale"), 0.0))
        if max_scale <= 0:
            return True
        ratio = min(max_scale, dist / max(dist, 1.0))
        if node.get("_reverseDistance"):
            ratio = max_scale - ratio
        dmg["amount"] = max(0.0, float(dmg.get("amount") or 0.0) * ratio)
        return True

    def _n_CheckAbnormalCombo(self, owner, node, ctx):
        """Gate: the resolved unit carries the abnormal combo (SLEEPING ->
        DOZE flag 43; STUNNED -> flag 0); _isUnset negates."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        combo = str(node.get("_abnormalCombo") or "").upper()
        flag = {"SLEEPING": 43, "STUNNED": 0, "FROZEN": 16,
                "LEVITATE": 25, "SILENCED": 12, "UNMOVABLE": 13}.get(combo)
        has = bool(flag is not None and u.flag(flag))
        return (not has) if node.get("_isUnset") else has

    def _n_CheckIfSourceGridPosFaceTargetGridPos(self, owner, node, ctx):
        """Gate: the target lies in FRONT of (or BACK of) the source's
        facing (enemy_mhkryk weakness: back-attack bonus)."""
        battle = self.battle
        src = _source_unit(battle, node.get("_source") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        tgt = _source_unit(battle, node.get("_target") or "MODIFIER_SOURCE",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None:
            return False
        dr = getattr(tgt, "row", 0) - getattr(src, "row", 0)
        dc = getattr(tgt, "col", 0) - getattr(src, "col", 0)
        d = int(getattr(src, "direction", 1) or 1)
        if dr == 0 and dc == 0:
            same = str(node.get("_faceIfSameCol") or "NONE").upper()
            return same in ("FRONT", "BACK") and \
                same == str(node.get("_faceType") or "").upper()
        if d == 0:
            front = dr < 0
        elif d == 1:
            front = dc > 0
        elif d == 2:
            front = dr > 0
        else:
            front = dc < 0
        want = str(node.get("_faceType") or "FRONT").upper()
        return front if want == "FRONT" else (not front)

    def _n_UpdateBuffAttributeModifier(self, owner, node, ctx):
        """Update an attribute modifier on the owner (enemy_blkswb DEF
        penetration ramp): value from blackboard when _useBlackboard."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return True
        if node.get("_useBlackboard"):
            value = _num(bb.get("value"), 0.0)
        else:
            value = _num(node.get("_value"), 0.0)
        if not value:
            return True
        entry = battle.buffs.get(owner, "op_attr_update")
        if entry is not None:
            entry["add"] = value
            battle.buffs._rebuild_modifiers(owner)
            return True
        battle.add_buff(owner, {
            "key": "op_attr_update", "remaining_ticks": 30 * 30,
            "layers": 1, "stat": stat, "add": value})
        return True

    def _n_AssignBuffBlackboardFromAbility(self, owner, node, ctx):
        """Copy a value from the resolved unit's active ability blackboard
        into the current buff blackboard (enemy_mjcdog GetChar)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_SOURCE",
                         owner, ctx.get("source"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        key = node.get("_assignedBlackboardKey") or \
            node.get("_blackboardKeyInAbility")
        src_key = node.get("_blackboardKeyInAbility") or key
        if not key:
            return False
        sc = getattr(u, "skill_controller", None)
        val = None
        if sc is not None:
            act = getattr(sc, "active", None)
            sk = getattr(act, "skill", None)
            if sk is not None and getattr(sk, "blackboard", None):
                val = sk.blackboard.get(src_key)
            if val is None and getattr(act, "blackboard", None):
                val = act.blackboard.get(src_key)
        if val is None:
            return False
        bb[key] = val
        return True

    def _n_CheckHasCharacterInRange(self, owner, node, ctx):
        """Gate: a character (operator/token) is inside the range around
        the resolved unit (enemy_hlslp wake, aglina speed-up)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        rid = node.get("_rangeId")
        if node.get("_globalRange") or not rid:
            return True
        try:
            from .battle import range_offsets_rotated
            cells = range_offsets_rotated(rid, getattr(u, "direction", 1))
        except Exception:
            cells = []
        pos = [(getattr(u, "row", 0) + dr, getattr(u, "col", 0) + dc)
               for dr, dc in cells]
        exclude_trap = bool(node.get("_excludeTrapAndToken"))
        exclude = ctx.get("target") if node.get("_excludeTarget") else None
        for o in list(battle.get_operators()) + list(battle.get_tokens()):
            if getattr(o, "dead", False) or o is exclude:
                continue
            if exclude_trap and o is not None and \
                    getattr(o, "token_id", None):
                continue
            if (getattr(o, "row", 0), getattr(o, "col", 0)) in pos:
                return True
        return False

    def _n_ForceSetToTilePosition(self, owner, node, ctx):
        """Teleport the resolved unit to the tile from the blackboard
        (enemy_cjdoor teleport / cjtaot core infection)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        bb = ctx.get("bb") or {}
        rk = node.get("_rowKey") or "row"
        ck = node.get("_colKey") or "col"
        if rk not in bb or ck not in bb:
            return False
        try:
            rr, cc = int(bb[rk]), int(bb[ck])
        except (TypeError, ValueError):
            return False
        if battle.map.tile(rr, cc) is None:
            return False
        u.row, u.col = rr, cc
        u.pos_x, u.pos_y = float(cc), float(rr)
        if node.get("_releaseFromBlocker"):
            u.blocked_by = None
        return True

    def _n_CheckEnemyDirection(self, owner, node, ctx):
        """Gate: the resolved enemy faces the named direction (or the bb
        value when _useBB)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        if node.get("_useBB"):
            bb = ctx.get("bb") or {}
            want = bb.get(node.get("_bbKey") or "direction")
        else:
            want = {"UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3}.get(
                str(node.get("_direction") or "").upper())
        if want is None:
            return True
        try:
            return int(getattr(u, "direction", 1) or 1) == int(want)
        except (TypeError, ValueError):
            return False

    def _n_RandomCreateBuff(self, owner, node, ctx):
        """Randomly pick one embedded buff and create it (haak T1 / tomimi
        S2 random pools)."""
        battle = self.battle
        datas = node.get("_datas") or []
        if not datas or not battle:
            return True
        item = datas[battle.rng.next(len(datas))]
        bd = (item or {}).get("buff") or {}
        if not bd.get("buffKey"):
            return False
        entry = materialise_buff(battle, owner, dict(bd), ctx.get("bb") or {},
                                 owner)
        if entry and entry.get("key"):
            battle.add_buff(owner, entry)
        return True

    def _n_SwitchDirection(self, owner, node, ctx):
        """Set the source's facing and run the direction-specific branch
        (sand_storm ally/trap direction switches)."""
        battle = self.battle
        src = _source_unit(battle, node.get("_source") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        if src is None:
            return False
        if node.get("_useCustomDirection"):
            d = node.get("_direction")
        else:
            d = {"UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3}.get(
                str(node.get("_direction") or "").upper())
        if d is not None:
            try:
                src.direction = int(d)
                if battle is not None:
                    battle._dispatch_buff_events(
                        src, "ON_DIRECTION_CHANGED", source=src, target=src)
            except (TypeError, ValueError):
                pass
        branch = node.get("_rightNodes") or node.get("_leftNodes") or []
        if branch:
            self.run_actions(owner, branch, ctx, 0)
        return True

    def _n_SaveHpToDynamicVar(self, owner, node, ctx):
        """Save the resolved unit's HP to a dynamic variable (enemy_lrtsia
        captureSoul reborn restores it)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        u._saved_hp = _num(getattr(u, "hp", 0.0) or 0.0)
        return True

    def _n_CheckTriggerable(self, owner, node, ctx):
        """Gate: the current battle state allows the trigger (brownb S2 /
        c2e_cold tile mode chains). Approximated as pass."""
        return True

    def _n_ModifyCharacterLimit(self, owner, node, ctx):
        """Adjust a character-limit counter (farm S1 / hlnpcm recover);
        recorded on the battle for snapshot visibility."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        val = _num(bb.get(node.get("_blackboardKey") or "value"), 0.0)
        if not hasattr(battle, "_character_limit_mod"):
            battle._character_limit_mod = 0.0
        battle._character_limit_mod += val if not node.get("_isMins") else -val
        return True

    def _n_EpDamageScale(self, owner, node, ctx):
        """Scale the element-damage amount in flight (mberry S2 / element
        resistance: _isOneMinus flips to 1 - value)."""
        dmg = ctx.get("damage") or {}
        if not dmg:
            return True
        bb = ctx.get("bb") or {}
        scale = _num(bb.get("ep_damage_scale"), _num(bb.get("scale"), 0.0))
        if node.get("_isOneMinus"):
            scale = 1.0 - scale
        dmg["amount"] = max(0.0, float(dmg.get("amount") or 0.0) * scale)
        return True

    def _n_DamageViaCurHpRatio(self, owner, node, ctx):
        """Deal PURE damage equal to the target's CURRENT HP x bb hp_ratio
        (Utage S2 loses 50% current HP on deploy)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        u = _source_unit(battle, node.get("_targetType") or "SOURCE",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        ratio = _num(bb.get("hp_ratio"), 0.0)
        if ratio <= 0:
            return True
        amount = _num(getattr(u, "hp", 0.0) or 0.0) * ratio
        battle.apply_damage(u, amount,
                            self._dmg_type(node.get("_damageType")),
                            source=owner, no_hit_recovery=True)
        return True

    def _n_CheckUnitInRebornState(self, owner, node, ctx):
        """Gate: the resolved unit is in the reborn/downed state."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        return bool(getattr(u, "_reborn_state", False) or
                    getattr(u, "_doll_state", False))

    def _n_CheckUnitInDisappearState(self, owner, node, ctx):
        """Gate: the resolved unit is in DISAPPEAR state."""
        from .consts import EnemyState
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        return getattr(u, "state", None) == EnemyState.DISAPPEAR

    def _n_CheckBuildableType(self, owner, node, ctx):
        """Gate: the resolved unit's tile allows the buildable type
        (MELEE=1 / RANGED=2; zebra aura only on highland)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or not battle:
            return False
        t = battle.map.tile(getattr(u, "row", 0), getattr(u, "col", 0))
        if t is None or t.buildable_type is None:
            return False
        want = {"MELEE": 1, "RANGED": 2}.get(
            str(node.get("_buildableType") or "").upper(), 0)
        return bool(want and (t.buildable_type & want))

    def _n_CheckEntityEquals(self, owner, node, ctx):
        """Gate: the two resolved units are the same entity (dusk token
        kill self-check / bgball exclude-self)."""
        battle = self.battle
        lhs = _source_unit(battle, node.get("_lhsType"), owner,
                           ctx.get("source"), ctx.get("target"))
        rhs = _source_unit(battle, node.get("_rhsType"), owner,
                           ctx.get("source"), ctx.get("target"))
        return lhs is not None and lhs is rhs

    def _n_FilterModifierTargetType(self, owner, node, ctx):
        """Gate: the modifier applies to the expected target type (HP/SP).
        Falls through when the context carries no modifier target."""
        bb = ctx.get("bb") or {}
        got = str(bb.get("_modifier_target_type", "")).upper()
        want = str(node.get("_modifierTargetType") or "").upper()
        if not got:
            return True
        return got == want

    def _n_CheckEnemyLevelType(self, owner, node, ctx):
        """Gate: the resolved unit's level type matches (BOSS=2)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        want = {"NORMAL": 0, "ELITE": 1, "BOSS": 2}.get(
            str(node.get("_targetLevelType") or "").upper(), None)
        if want is None:
            return True
        return int(getattr(u, "level_type", 0) or 0) == want

    def _n_FilterByShieldValue(self, owner, node, ctx):
        """Gate: the resolved unit's shield (barrier) compares against
        _shieldValue (mcnist shield breaks when barrier <= 0)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        got = _num(getattr(u, "barrier", 0.0) or 0.0)
        want = _num(node.get("_shieldValue"), 0.0)
        cond = str(node.get("_condType") or "LE").upper()
        if cond == "LT":
            return got < want
        if cond == "GT":
            return got > want
        if cond == "GE":
            return got >= want
        if cond == "LE":
            return got <= want
        if cond in ("EQUALS", "EQ", "=="):
            return got == want
        return True

    def _n_CreateBuffToUid(self, owner, node, ctx):
        """Apply the embedded buff to the unit whose inst id comes from
        the blackboard (_uidKey; enemy lookup via _getFromEnemy)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        uid = bb.get(node.get("_uidKey") or "uid")
        if uid is None:
            return False
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            pass
        pool = list(battle.get_enemies()) if node.get("_getFromEnemy") else \
            (list(battle.get_enemies()) + list(battle.get_operators())
             + list(battle.get_tokens()))
        for u in pool:
            if getattr(u, "inst_id", None) != uid:
                continue
            bd = node.get("_buff") or {}
            if not bd.get("buffKey"):
                return False
            entry = materialise_buff(battle, u, dict(bd), bb, owner)
            if entry and entry.get("key"):
                battle.add_buff(u, entry)
            return True
        return False

    def _n_EqualizeTargetHpRatio(self, owner, node, ctx):
        """Set the target's HP to the source's HP ratio (or _hpRatio) of
        its max HP (trap_bgarmn sync_hp / fttreant)."""
        battle = self.battle
        src = _source_unit(battle, node.get("_source") or "SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_target") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None:
            return False
        mx = _num(getattr(tgt, "max_hp", 0.0) or 0.0)
        if mx <= 0:
            return True
        if node.get("_useSourceHpRatio") and src is not None:
            smx = _num(getattr(src, "max_hp", 0.0) or 0.0)
            ratio = (_num(getattr(src, "hp", 0.0) or 0.0) / smx) \
                if smx > 0 else 0.0
        else:
            ratio = _num(node.get("_hpRatio"), 0.5)
        tgt.hp = min(mx, max(0.0, mx * ratio))
        return True

    def _n_MarkCurrentHpRatio(self, owner, node, ctx):
        """Record the resolved unit's current HP ratio in the blackboard
        (smephi poison tracks the marked ratio)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        mx = _num(getattr(u, "max_hp", 0.0) or 0.0)
        ratio = (_num(getattr(u, "hp", 0.0) or 0.0) / mx) if mx > 0 else 0.0
        if node.get("_markInBlackboard"):
            bb = ctx.setdefault("bb", {})
            bb["marked_hp_ratio"] = ratio
        else:
            u._marked_hp_ratio = ratio
        return True

    def _n_CheckCost(self, owner, node, ctx):
        """Gate: battle cost compares against the blackboard value
        (strong_tr / nothin_tr cost thresholds)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey") or "cost"
        want = _num(bb.get(key), 0.0)
        got = _num(getattr(battle, "cost", 0.0) or 0.0)
        cmp = str(node.get("_compareType") or "GE").upper()
        if cmp == "GT":
            return got > want
        if cmp == "GE":
            return got >= want
        if cmp == "LT":
            return got < want
        if cmp == "LE":
            return got <= want
        if cmp in ("EQUALS", "EQ", "=="):
            return got == want
        return True

    def _n_HpRatioToAttributeAdd(self, owner, node, ctx):
        """Add an attribute buff scaled by the source's HP ratio (Helaeg
        T1 / Utage T1 attack-speed scaling)."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        src = _source_unit(battle, node.get("_hpRatioSource") or "SOURCE",
                           owner, ctx.get("source"))
        if src is None:
            return True
        mx = _num(getattr(src, "max_hp", 0.0) or 0.0)
        ratio = (_num(getattr(src, "hp", 0.0) or 0.0) / mx) if mx > 0 else 0.0
        lo = _num(node.get("_minHpRatio"), 0.0)
        hi = _num(node.get("_maxHpRatio"), 1.0)
        if ratio < lo or ratio > hi:
            return True
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat:
            return True
        value = _num(bb.get("value"), _num(bb.get("attack_speed"), 0.0))
        if not value:
            return True
        battle.add_buff(owner, {
            "key": "op_hp_ratio_attr", "remaining_ticks": 30,
            "layers": 1, "stat": stat, "add": value * ratio,
            "source": src})
        return True

    def _n_CheckMainBuffId(self, owner, node, ctx):
        """Gate: the buff that just started (ON_OTHER_BUFF_START) matches
        _idToFilter (recat polluted / necras upgrade chains)."""
        bb = ctx.get("bb") or {}
        return bb.get("_other_buff_key") == node.get("_idToFilter")

    def _n_SetDisappear(self, owner, node, ctx):
        """Set the resolved unit's disappear state (enemy_mpplai passive
        P0 shows/hides on buff finish)."""
        from .consts import EnemyState
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        if node.get("_isDisappear"):
            u.state = EnemyState.DISAPPEAR
            u._pending_attack = None
        else:
            if getattr(u, "state", None) == EnemyState.DISAPPEAR:
                u.state = EnemyState.MOVE
        return True

    def _n_ClearEnemySp(self, owner, node, ctx):
        """Zero the resolved enemy's current SP (enemy_dhnzzh P2 /
        agpack record counters)."""
        u = _source_unit(self.battle, node.get("_enemy") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            return False
        u.sp = 0.0
        return True

    def _n_PickRandomBranchPhase(self, owner, node, ctx):
        """Deal a random phase of the branch referenced by the blackboard
        (csdoll shield modes / summons), honouring not-repeat."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        branch = bb.get("branch_id") or bb.get("branch") or \
            getattr(owner, "branch_id", None)
        if not branch:
            return True
        try:
            n = battle.execute_branch_random(
                str(branch),
                not_repeat=bool(node.get("_notRepeatInOneLoop")),
                block_game_finish=bool(node.get("_blockGameFinish")))
        except Exception:
            return False
        return n > 0

    def _n_AssignUidToBlackBoard(self, owner, node, ctx):
        """Write the resolved unit's uid (inst id or key) into the
        blackboard (agbmal/agbomb record modifier source)."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackBoardKey") or node.get("_blackboardKey") or "uid"
        if node.get("_assignAsInt"):
            bb[key] = getattr(u, "inst_id", 0)
        else:
            bb[key] = (getattr(u, "enemy_key", None) or
                       getattr(u, "token_id", None) or
                       getattr(u, "char_id", None) or
                       str(getattr(u, "inst_id", 0)))
        return True

    def _n_CreateBuffWithOverrideEffect(self, owner, node, ctx):
        """Same as CreateBuff but with an override effect key (visual);
        delegates to the regular CreateBuff pipeline."""
        return self._n_CreateBuff(owner, node, ctx)

    def _n_FilterByTargetSPType(self, owner, node, ctx):
        """Gate: the resolved unit's skill SP type matches _spType
        (INCREASE_WHEN_ATTACK=2). Falls through when the unit exposes no
        SP type."""
        u = _source_unit(self.battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sp_type = None
        sc = getattr(u, "skill_controller", None)
        if sc is not None:
            act = getattr(sc, "active", None)
            sk = getattr(act, "skill", None)
            if sk is not None:
                sp_type = getattr(getattr(sk, "sp_data", None), "spType", None)
                if sp_type is None:
                    sp_type = (getattr(sk, "sp_data", None) or {}).get(
                        "spType") if isinstance(getattr(sk, "sp_data", None),
                                                dict) else None
        if sp_type is None:
            return True
        want = {"INCREASE_WHEN_ATTACK": 2, "INCREASE_WHEN_DAMAGED": 4,
                "INCREASE_WHEN_TIME": 1}.get(
                    str(node.get("_spType") or "").upper())
        if want is None:
            return True
        return int(sp_type) == want

    def _n_IfDamageTargetSide(self, owner, node, ctx):
        """Gate: the damage source (or target) belongs to _sideMask
        (bubble S2 / folnic S2 enemy-damage gates)."""
        dmg = ctx.get("damage") or {}
        if not dmg:
            return False
        u = _source_unit(self.battle, node.get("_sourceType") or
                         "MODIFIER_SOURCE", owner, ctx.get("source"))
        if u is None:
            u = ctx.get("source")
        side = str(node.get("_sideMask") or "ENEMY").upper()
        got = int(getattr(u, "side", 0) or 0)
        if side == "ENEMY":
            return got == 0
        if side == "ALLY":
            return got == 1
        if side in ("BOTH_ALLY_AND_ENEMY", "BOTH", "ALL"):
            return True
        return False

    def _n_RandomSetter(self, owner, node, ctx):
        """Write a battle-RNG random value into the blackboard (amgoat T2
        random SP gain / enemy_xdbird random landing delay)."""
        battle = self.battle
        if not battle or not hasattr(battle, "rng"):
            return True
        bb = ctx.setdefault("bb", {})
        key = node.get("_targetKey")
        if not key:
            return False
        if hasattr(battle.rng, "next_float"):
            val = battle.rng.next_float()
        else:
            val = battle.rng.chance(1.0) and 1.0 or 0.0
        if node.get("_convertToInt"):
            val = int(val)
        bb[key] = val
        return True

    def _n_AssignModifierRealDeltaToBB(self, owner, node, ctx):
        """Write the real modifier delta (actual damage applied) into the
        blackboard (trap_ftshad[ep_damage] last_damage / pyczog loss_hp)."""
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackboardKey") or "value"
        dmg = ctx.get("damage") or {}
        bb[key] = _num(dmg.get("amount"), _num(dmg.get("_delta"), 0.0))
        return True

    def _n_CheckTargetGridPositionRowOrColWithBB(self, owner, node, ctx):
        """Gate: the resolved unit's row (or col) equals the blackboard
        value (agbmes_t12_s1[follow_me] row/col sync)."""
        u = _source_unit(self.battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey")
        if not key:
            return False
        want = bb.get(key)
        got = getattr(u, "row", 0) if node.get("_checkRow") else             getattr(u, "col", 0)
        cmp = str(node.get("_compareType") or "EQUALS").upper()
        try:
            if cmp in ("EQUALS", "EQ", "=="):
                return float(got) == float(want)
            if cmp == "GT":
                return float(got) > float(want)
            if cmp == "GE":
                return float(got) >= float(want)
            if cmp == "LT":
                return float(got) < float(want)
            if cmp == "LE":
                return float(got) <= float(want)
        except (TypeError, ValueError):
            return False
        return True

    def _n_DamageByDistance(self, owner, node, ctx):
        """Damage proportional to distance moved since the last trigger
        (Weedy S3 rupture: moving enemies take value x distance TRUE
        damage every interval). _isInit records the reference position."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        if node.get("_isInit"):
            bb["_dpx"] = getattr(u, "pos_x", None)
            bb["_dpy"] = getattr(u, "pos_y", None)
            bb["_drow"] = getattr(u, "row", 0)
            bb["_dcol"] = getattr(u, "col", 0)
            return True
        px = getattr(u, "pos_x", None)
        py = getattr(u, "pos_y", None)
        if bb.get("_dpx") is not None and px is not None:
            moved = ((px - bb["_dpx"]) ** 2 + (py - bb["_dpy"]) ** 2) ** 0.5
            bb["_dpx"], bb["_dpy"] = px, py
        else:
            dr = getattr(u, "row", 0) - bb.get("_drow", getattr(u, "row", 0))
            dc = getattr(u, "col", 0) - bb.get("_dcol", getattr(u, "col", 0))
            moved = (dr * dr + dc * dc) ** 0.5
            bb["_drow"], bb["_dcol"] = getattr(u, "row", 0), \
                getattr(u, "col", 0)
        if moved <= 1e-6:
            return True
        value = _num(bb.get("value"), 0.0)
        if value <= 0:
            return True
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        battle.apply_damage(u, moved * value,
                            self._dmg_type(node.get("_damageType")),
                            source=src or owner, no_hit_recovery=True)
        return True

    def _n_CreateBuffToUnitId(self, owner, node, ctx):
        """Apply the embedded buff to the unit whose key matches _unitId
        (enemy_ubbplwq kills its linked heavy / bomb notice)."""
        battle = self.battle
        if not battle:
            return True
        uid = node.get("_unitId") or ""
        if not uid:
            return False
        for u in (list(battle.get_enemies()) + list(battle.get_operators())
                  + list(battle.get_tokens())):
            key = getattr(u, "enemy_key", None) or getattr(
                u, "token_id", None) or getattr(u, "char_id", "")
            if key != uid:
                continue
            bd = node.get("_buff") or {}
            if not bd.get("buffKey"):
                return False
            entry = materialise_buff(battle, u, dict(bd), ctx.get("bb") or {},
                                     owner)
            if entry and entry.get("key"):
                battle.add_buff(u, entry)
            return True
        return False

    def _n_SwitchSide(self, owner, node, ctx):
        """Flip the resolved unit's side (0=enemy 1=ally): enemy defectors
        (enemy_trspsb_eating, trap_mptxs_mark) and burning heaters
        (trap_winfire[burn] -> ALLY, [extinguish] -> ENEMY). A switched
        enemy stops acting; _markEnemyKilled records the defection so a
        later death can still count as an enemy kill."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        side_type = str(node.get("_sideType") or "ALLY").upper()
        u.side = 1 if side_type == "ALLY" else 0
        if node.get("_markEnemyKilled"):
            u._mark_switched_side_killed = True
        return True

    def _n_SetTilesEnableOverlap(self, owner, node, ctx):
        """Enable/disable tile overlap on the owner's root tile (or the
        configured offsets): while enabled other units may share the tile
        (trap_ftshad "\u7a7a\u58f3" / mlyss_wtrman_s_begin)."""
        battle = self.battle
        if not battle:
            return True
        is_enable = bool(node.get("_isEnable"))
        r0 = getattr(owner, "row", 0)
        c0 = getattr(owner, "col", 0)
        cells = [(r0, c0)]
        if node.get("_onlyRootTile"):
            cells = [(r0, c0)]
        elif node.get("_useOffset") and node.get("_offsets"):
            cells = [(r0 + int(o.get("row") or 0), c0 + int(o.get("col") or 0))
                     for o in (node.get("_offsets") or [])]
        elif node.get("_allTilesExceptRootTile"):
            cells = []
        changed = 0
        for rr, cc in cells:
            t = battle.map.tile(rr, cc)
            if t is None:
                continue
            t._overlap_enabled = is_enable
            changed += 1
        return changed > 0

    def _n_ModifyOverlapSourceId(self, owner, node, ctx):
        """Register / remove an overlap source id on the resolved target
        (trap_102_mhwrbg shares its tile; trap_trpot mark/finish)."""
        battle = self.battle
        if not battle:
            return True
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        src = node.get("_sourceId") or ""
        if node.get("_useBlackboardId"):
            bb = ctx.get("bb") or {}
            src = bb.get("source_id") or bb.get("sourceId") or src
        if not src:
            return False
        ids = getattr(u, "_overlap_source_ids", None)
        if ids is None:
            u._overlap_source_ids = set()
            ids = u._overlap_source_ids
        if node.get("_isRemove"):
            ids.discard(src)
        else:
            ids.add(src)
        return True

    def _n_RewriteTileOptions(self, owner, node, ctx):
        """Rewrite the passable options of the owner's tile (planet debris
        blocks its cell while stationary, restores when it moves / is hit;
        _restoreTileOptions=true clears the override, otherwise
        _isObstacleLike makes the tile impassable)."""
        battle = self.battle
        if not battle:
            return True
        row = getattr(owner, "row", 0)
        col = getattr(owner, "col", 0)
        if node.get("_restoreTileOptions"):
            return bool(battle.map.restore_tile_passable(row, col))
        if node.get("_isObstacleLike"):
            return bool(battle.map.rewrite_tile_passable(row, col, 0))
        return True

    def _n_RewriteTileOptionsInRange(self, owner, node, ctx):
        """Rewrite buildable options over a range around the source unit
        (game RewriteTileOptionsInRange). Two use families:
          - night-map lantern tokens: _advancedBuildableMask NIGHT/DEFAULT
            flips the tiles' advanced buildable mask (state + observer,
            night deploy gating is not modelled);
          - enemy_dysuib_withdraw_ally: _buildableChange + _buildableType
            NONE makes every tile in the range undeployable, restored on
            ON_BUFF_FINISH via _restoreTileOptions.
        The range follows the source unit's facing (range_offsets_rotated)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        try:
            from .battle import range_offsets_rotated
            offs = range_offsets_rotated(
                node.get("_rangeId") or "",
                int(getattr(src, "direction", 1) or 1))
        except Exception:
            offs = [(0, 0)]
        r0 = int(getattr(src, "row", 0) or 0)
        c0 = int(getattr(src, "col", 0) or 0)
        cells = [(r0 + dr, c0 + dc) for dr, dc in offs]
        changed = 0
        if node.get("_restoreTileOptions"):
            for r, c in cells:
                if battle.map.restore_tile_buildable(r, c):
                    changed += 1
        else:
            if node.get("_buildableChange"):
                bt = str(node.get("_buildableType") or "NONE").upper()
                mask = 0 if bt == "NONE" else None
                if mask is None:
                    try:
                        mask = int(bt)
                    except (TypeError, ValueError):
                        mask = None
                if mask is not None:
                    for r, c in cells:
                        if battle.map.rewrite_tile_buildable(r, c, mask):
                            changed += 1
            adv = str(node.get("_advancedBuildableMask") or "").upper()
            if adv in ("NIGHT", "DEFAULT"):
                for r, c in cells:
                    t = battle.map.tile(r, c)
                    if t is None:
                        continue
                    t.set_advanced_buildable_override(
                        1 if adv == "NIGHT" else None)
                    changed += 1
        battle.emit(battle.tick, "tile_options_rewritten",
                    {"unit": getattr(src, "inst_id", None),
                     "range": node.get("_rangeId") or "",
                     "tiles": len(cells), "changed": changed,
                     "restore": bool(node.get("_restoreTileOptions")),
                     "nightMode": bool(node.get("_nightMode")),
                     "buildableType": node.get("_buildableType"),
                     "advancedBuildableMask": node.get(
                         "_advancedBuildableMask")})
        return True

    def _n_DisableEnemySwitchFaceByMove(self, owner, node, ctx):
        """Toggle the enemy's switch-face-on-move flag
        (DisableEnemySwitchFaceByMove). Stored on the unit and exposed
        as an observable event."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._disable_face_switch = bool(node.get("_disabled"))
        if battle:
            battle.emit(battle.tick, "enemy_face_switch_flag",
                        {"unit": getattr(u, "inst_id", None),
                         "disabled": bool(node.get("_disabled"))})
        return True

    def _n_ReleaseEnemyFromCurrentWave(self, owner, node, ctx):
        """Mark the enemy as released from the current wave tracking
        (ReleaseEnemyFromCurrentWave; wave-track integration is a flag +
        observable event in the timeline model)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        u._released_from_wave = True
        u._track_next_wave = bool(node.get("_trackEnemyAtNextWave"))
        battle.emit(battle.tick, "enemy_released_from_wave",
                    {"unit": getattr(u, "inst_id", None),
                     "trackNextWave": bool(node.get("_trackEnemyAtNextWave")),
                     "removeWaveCache": bool(node.get("_removeWaveCache"))})
        return True

    def _n_EnemyForceTracePosition(self, owner, node, ctx):
        """Force the enemy to trace a target unit / position instead of
        its route (EnemyForceTracePosition). While tracing, the enemy
        moves straight toward the target (+_reachOffset); the trace ends
        on arrival, or when the target dies and _stopTraceWhenNoTarget.
        _createBuffToTraceTarget applies the embedded buff to the traced
        unit."""
        battle = self.battle
        if not battle:
            return False
        e = _source_unit(battle, node.get("_source") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if e is None:
            e = owner
        tgt = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        bb = dict(ctx.get("bb") or {})
        off = node.get("_reachOffset") or {}
        e._trace_reach = float(off.get("x") or 0.0)
        e._trace_ox = float(off.get("x") or 0.0)
        e._trace_oy = float(off.get("y") or 0.0)
        e._stop_trace_on_no_target = bool(
            node.get("_stopTraceWhenNoTarget", True))
        e._trace_target = None
        e._trace_pos = None
        if node.get("_loadPosFromBlackboard"):
            rk = node.get("_loadPosRowKey") or "row"
            ck = node.get("_loadPosColKey") or "col"
            try:
                r = int(_num(bb.get(rk), 0.0))
                c = int(_num(bb.get(ck), 0.0))
                e._trace_pos = (float(c), float(r))
            except (TypeError, ValueError):
                pass
        elif node.get("_loadMapPosFromBlackboard"):
            xk = node.get("_loadMapPosXKey") or "pos_x"
            yk = node.get("_loadMapPosYKey") or "pos_y"
            e._trace_pos = (float(_num(bb.get(xk), 0.0)),
                            float(_num(bb.get(yk), 0.0)))
        elif tgt is not None:
            e._trace_target = tgt
            if node.get("_createBuffToTraceTarget"):
                bd = dict(node.get("_buffToTraceTarget") or {})
                if bd.get("buffKey"):
                    entry = materialise_buff(battle, tgt, bd, bb, owner)
                    if entry and entry.get("key"):
                        battle.add_buff(tgt, entry)
        battle.emit(battle.tick, "enemy_force_trace",
                    {"unit": e.inst_id,
                     "target": getattr(tgt, "inst_id", None)
                     if tgt is not None else None,
                     "pos": e._trace_pos,
                     "reach": round(e._trace_reach, 4)})
        return True

    def _n_BlinkNode(self, owner, node, ctx):
        """Teleport the enemy along its route (BlinkNode): to the next
        checkpoint with a position, to a map position from the blackboard
        / node fields, or to the row/col keys on the blackboard. Emits an
        enemy_blink event with the resulting tile."""
        battle = self.battle
        if not battle:
            return False
        e = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if e is None:
            e = owner
        bb = dict(ctx.get("bb") or {})
        if node.get("_useRowAndColOnBlackboard"):
            rk = node.get("_rowKey") or "row"
            ck = node.get("_colKey") or "col"
            r = bb.get(rk)
            c = bb.get(ck)
            if r is not None and c is not None:
                e.pos_x = float(c)
                e.pos_y = float(r)
                e._sync_tile()
        elif node.get("_toMapPosition") or node.get("_forceToMapPosition"):
            x = node.get("_mapPosX")
            y = node.get("_mapPosY")
            if x is None:
                x = bb.get("pos_x")
            if y is None:
                y = bb.get("pos_y")
            if x is not None and y is not None:
                e.pos_x = float(x)
                e.pos_y = float(y)
                e._sync_tile()
        elif node.get("_toNextCheckpoint"):
            cps = (getattr(e, "route", None) or {}).get("checkpoints") or []
            target = None
            idx = int(getattr(e, "_checkpoint_idx", 0) or 0)
            for i in range(idx, len(cps)):
                pos = (cps[i].get("position") or {})
                if pos:
                    target = (float(pos.get("col", 0.0)),
                              float(pos.get("row", 0.0)))
                    e._checkpoint_idx = i + 1
                    break
            if target is None and node.get("_toEndIfNoCheckpoint"):
                end = (getattr(e, "route", None) or {}).get("endPosition")
                if end:
                    target = (float(end.get("col", 0.0)),
                              float(end.get("row", 0.0)))
            if target is not None:
                e.pos_x, e.pos_y = target
                e._sync_tile()
        battle.emit(battle.tick, "enemy_blink",
                    {"unit": e.inst_id, "row": e.row, "col": e.col})
        return True

    def _n_GainToken(self, owner, node, ctx):
        """Gain a player-side deployable token (GainToken, act36side /
        multi-fortress event tokens). The token key comes from the
        blackboard 'token_key' (split on ',' when _spiltTokenKey); the
        gained key is added to the battle's gained-token inventory and
        exposed in the snapshot as gainedTokens."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        bb = ctx.get("bb") or {}
        raw = bb.get("token_key")
        if raw is None:
            raw = bb.get("tokenKey")
        if not raw:
            return True
        if node.get("_spiltTokenKey"):
            keys = [str(k).strip() for k in str(raw).split(",")
                    if str(k).strip()]
        else:
            keys = [str(raw)]
        timing = node.get("_rechargeTiming") or "NORMAL"
        for k in keys:
            battle._gained_tokens[k] = battle._gained_tokens.get(k, 0) + 1
            battle._gained_token_timings[k] = timing
            battle.emit(battle.tick, "token_gained",
                        {"unit": getattr(u, "inst_id", None),
                         "tokenKey": k, "timing": timing,
                         "count": battle._gained_tokens[k],
                        "extraLog": node.get("_extraLogKey")})
        return bool(keys)

    # ---- card / deck system ----------------------------------------------
    def _card_key(self, node, ctx):
        """Card key for card nodes: explicit _cardBuffKey when used,
        otherwise the current buff's own key (CreateCardBuff turns the
        finishing buff into a card, e.g. nearl2_s_2[withdraw])."""
        if node.get("_useCardBuffKey") and node.get("_cardBuffKey"):
            return str(node.get("_cardBuffKey"))
        bb = ctx.get("bb") or {}
        entry = bb.get("_buff_entry") or {}
        return entry.get("key") or bb.get("buff_key") or ""

    def _add_card(self, unit, key, life_type, ctx):
        """Add a card entry to a unit (same key + lifeType stacks layers);
        returns the card uid. Cards are observer-visible state."""
        cards = getattr(unit, "cards", None)
        if cards is None:
            unit.cards = []
            cards = unit.cards
        for c in cards:
            if c.get("key") == key and \
                    c.get("lifeType") == (life_type or "ALL_THE_TIME"):
                c["layers"] = int(c.get("layers", 1) or 1) + 1
                return c.get("uid")
        uid = next(_CARD_UID_COUNTER)
        cards.append({"uid": uid, "key": key,
                      "lifeType": life_type or "ALL_THE_TIME",
                      "hidden": None, "inHand": False, "layers": 1})
        if self.battle:
            self.battle.emit(self.battle.tick, "card_added",
                             {"unit": getattr(unit, "inst_id", None),
                              "cardKey": key, "uid": uid,
                              "lifeType": life_type})
        return uid

    def _n_CreateCardBuff(self, owner, node, ctx):
        """Create a card from the current buff on the resolved target
        (CreateCardBuff; e.g. nearl2 S2/S3, enemy_flwitch respawn). The
        card uid is written to bb 'card_uid' for later Finish/Assign
        nodes."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        key = self._card_key(node, ctx)
        if not key:
            # no derivable key: keep the legacy observable event so
            # key-less calls remain externally visible
            battle.emit(battle.tick, "card_buff",
                        {"unit": getattr(u, "inst_id", None),
                         "lifeType": node.get("_lifeType")})
            return False
        uid = self._add_card(u, key, node.get("_lifeType"), ctx)
        ctx.setdefault("bb", {})["card_uid"] = uid
        return True

    def _n_CheckContainsCardBuff(self, owner, node, ctx):
        """Gate: the resolved unit has a card with _key (or the blackboard
        key when _readBuffKeyFromBlackboard)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        key = node.get("_key") or ""
        if node.get("_readBuffKeyFromBlackboard"):
            key = (ctx.get("bb") or {}).get("card_buff_key") or key
        cards = getattr(u, "cards", []) or []
        return any(c.get("key") == key for c in cards)

    def _n_FinishCardBuff(self, owner, node, ctx):
        """Finish the card tied to this buff (bb card_uid)."""
        bb = ctx.get("bb") or {}
        uid = bb.get("card_uid")
        if uid is None:
            return False
        cards = getattr(owner, "cards", None)
        if not cards:
            return False
        before = len(cards)
        owner.cards = [c for c in cards if c.get("uid") != uid]
        return len(owner.cards) != before

    def _n_FinishCardBuffsByKey(self, owner, node, ctx):
        """Remove all cards with _cardBuffKey (from every unit when
        _findAllCard, else the resolved target)."""
        battle = self.battle
        key = node.get("_cardBuffKey") or ""
        if not key:
            return False
        if node.get("_findAllCard"):
            units = (list(battle.get_enemies()) +
                     list(battle.get_operators()) +
                     list(battle.get_tokens()))
        else:
            u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                             owner, ctx.get("source"), ctx.get("target"))
            units = [u] if u is not None else []
        removed = 0
        for u in units:
            cards = getattr(u, "cards", None)
            if not cards:
                continue
            before = len(cards)
            u.cards = [c for c in cards if c.get("key") != key]
            removed += before - len(u.cards)
        return removed > 0

    def _n_CreateDeckBuff(self, owner, node, ctx):
        """Create a deck buff (collection of cards) on the resolved
        target from _deckBuff (key = embedded buffKey). Modeled as a card
        entry with isDeck=True."""
        battle = self.battle
        if not battle:
            return False
        deck = node.get("_deckBuff") or {}
        buf = deck.get("buff") or {}
        key = buf.get("buffKey") or deck.get("deckBuffKey") or ""
        if not key:
            key = self._card_key(node, ctx)
        if not key:
            return False
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        uid = self._add_card(u, key, deck.get("lifeType"), ctx)
        for c in u.cards:
            if c.get("uid") == uid:
                c["isDeck"] = True
                c["cardEffectType"] = deck.get("cardEffectType")
        ctx.setdefault("bb", {})["card_uid"] = uid
        return True

    def _n_CheckContainsDeckBuff(self, owner, node, ctx):
        """Gate: the resolved unit holds a deck with _key."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        key = node.get("_key") or ""
        cards = getattr(u, "cards", []) or []
        return any(c.get("isDeck") and c.get("key") == key for c in cards)

    def _n_FinishDeckBuffByKey(self, owner, node, ctx):
        """Remove the deck with _deckBuffKey from the resolved target."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        key = node.get("_deckBuffKey") or ""
        cards = getattr(u, "cards", None)
        if not cards or not key:
            return False
        before = len(cards)
        u.cards = [c for c in cards
                   if not (c.get("isDeck") and c.get("key") == key)]
        return len(u.cards) != before

    def _n_FinishDeckBuffByCardUIDAndKey(self, owner, node, ctx):
        """Remove the deck matched by the blackboard card uid and key
        (FinishDeckBuffByCardUIDAndKey)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        bb = ctx.get("bb") or {}
        uid = bb.get(node.get("_blackBoardKey") or "card_uid")
        key = node.get("_deckBuffKey") or ""
        cards = getattr(u, "cards", None)
        if not cards or not key:
            return False
        before = len(cards)
        u.cards = [c for c in cards
                   if not (c.get("isDeck") and c.get("key") == key and
                           (uid is None or c.get("uid") == uid))]
        return len(u.cards) != before

    def _n_AssignCardUIDToBlackBoard(self, owner, node, ctx):
        """Write the resolved unit's card uid (current bb card_uid, else
        the first card) to the blackboard key (AssignCardUIDToBlackBoard)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        bb = ctx.setdefault("bb", {})
        key = node.get("_blackBoardKey") or "card_uid"
        uid = bb.get("card_uid")
        if uid is None:
            cards = getattr(u, "cards", []) or []
            if cards:
                uid = cards[0].get("uid")
        if node.get("_assignAsString"):
            bb[key] = str(uid) if uid is not None else None
        else:
            bb[key] = uid
        return True

    def _n_CreateCardBuffToMyToken(self, owner, node, ctx):
        """Create the card on every live token owned by the owner
        (CreateCardBuffToMyToken, e.g. svash2 S3 token cost reduction)."""
        battle = self.battle
        if not battle:
            return False
        key = self._card_key(node, ctx)
        if not key:
            return False
        hit = 0
        for tk in battle.get_tokens():
            if getattr(tk, "dead", False):
                continue
            if getattr(tk, "owner", None) is not owner:
                continue
            self._add_card(tk, key, node.get("_lifeType"), ctx)
            hit += 1
        return hit > 0

    def _n_HideCardByTokenOrHostUid(self, owner, node, ctx):
        """Show / hide the resolved unit's cards with a hidden reason
        (HideCardByTokenOrHostUid; deck UI state, observer-visible)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "SOURCE",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        shown = bool(node.get("_isShow"))
        reason = node.get("_hiddenReason") or "deck_default_hidden"
        for c in getattr(u, "cards", []) or []:
            c["hidden"] = None if shown else reason
        if battle:
            battle.emit(battle.tick, "card_hidden_state",
                        {"unit": getattr(u, "inst_id", None),
                         "shown": shown, "reason": reason})
        return True

    def _n_CreateCardBuffFilterByDeckBuff(self, owner, node, ctx):
        """Create a card only when the resolved target holds the deck buff
        with _buffKey (CreateCardBuffFilterByDeckBuff)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        deck_key = node.get("_buffKey") or ""
        cards = getattr(u, "cards", []) or []
        if deck_key and not any(c.get("isDeck") and c.get("key") == deck_key
                                for c in cards):
            return False
        key = self._card_key(node, ctx)
        if not key:
            return False
        uid = self._add_card(u, key, node.get("_lifeType"), ctx)
        ctx.setdefault("bb", {})["card_uid"] = uid
        return True

    def _n_CreateCardBuffFilterByTag(self, owner, node, ctx):
        """Create the card only when the resolved target carries _tag
        (CreateCardBuffFilterByTag; tags are not stored on units yet, so
        units without a tag attribute pass through unverified)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        tag = node.get("_tag") or ""
        tags = getattr(u, "tags", None)
        if tags is not None and tag and tag not in tags:
            return False
        key = self._card_key(node, ctx)
        if not key:
            return False
        uid = self._add_card(u, key, node.get("_lifeType"), ctx)
        ctx.setdefault("bb", {})["card_uid"] = uid
        return True

    def _n_CreateCardFilterByProfession(self, owner, node, ctx):
        """Create the card only when the target's profession bitmask
        matches the _profession list (WARRIOR/SNIPER/... names). Enemies
        without a profession fail the filter."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        prof = getattr(u, "profession", None)
        if prof is None:
            return False
        try:
            prof_i = int(prof or 0)
        except (TypeError, ValueError):
            return False
        mask = 0
        for name in str(node.get("_profession") or "").upper().split(","):
            name = name.strip()
            if name in _PROF_NAMES:
                mask |= _PROF_NAMES[name]
        if mask and not (prof_i & mask):
            return False
        key = self._card_key(node, ctx)
        if not key:
            return False
        uid = self._add_card(u, key, node.get("_lifeType"), ctx)
        ctx.setdefault("bb", {})["card_uid"] = uid
        return True

    def _n_ExcludeDeckCardFromBattle(self, owner, node, ctx):
        """Toggle a deck card's battle exclusion (ExcludeDeckCardFrom-
        Battle: deck UI / battle-pool state, snapshot excludedDeckCards)."""
        battle = self.battle
        if not battle:
            return False
        card_id = node.get("_cardId") or ""
        if not card_id:
            return True
        if node.get("_excludeFromBattle"):
            battle._excluded_deck_cards.add(card_id)
        else:
            battle._excluded_deck_cards.discard(card_id)
        battle.emit(battle.tick, "deck_card_excluded",
                    {"cardId": card_id,
                     "excluded": bool(node.get("_excludeFromBattle")),
                     "playerSide": node.get("_playerSide")})
        return True

    def _n_AssignCardRemainingCntToBlackboard(self, owner, node, ctx):
        """Write the remaining count (stack layers) of the card _cardKey
        on the resolved unit to the blackboard key."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        card_key = node.get("_cardKey") or ""
        cnt = 0
        for c in getattr(u, "cards", []) or []:
            if c.get("key") == card_key:
                cnt += int(c.get("layers", 1) or 1)
        ctx.setdefault("bb", {})[node.get("_blackboardKey") or "times"] = cnt
        return True

    def _n_FinishTokenCardBuffByKey(self, owner, node, ctx):
        """Remove cards with _cardBuffKey from every live token owned by
        the resolved source (FinishTokenCardBuffByKey)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        key = node.get("_cardBuffKey") or ""
        if not key:
            return False
        removed = 0
        for tk in battle.get_tokens():
            if getattr(tk, "dead", False):
                continue
            if getattr(tk, "owner", None) is not src:
                continue
            cards = getattr(tk, "cards", None)
            if not cards:
                continue
            before = len(cards)
            tk.cards = [c for c in cards if c.get("key") != key]
            removed += before - len(tk.cards)
        return removed > 0

    def _n_CheckCharacterIsFreelySpawnedFromDeck(self, owner, node, ctx):
        """Gate: the resolved owner was freely spawned from a deck (the
        free-summon path sets _freely_spawned_from_deck)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        return bool(getattr(u, "_freely_spawned_from_deck", False))

    # ---- visual / cosmetic state -----------------------------------------
    def _n_CreateLineEffect(self, owner, node, ctx):
        battle = self.battle
        if battle:
            src = _source_unit(battle, node.get("_sourceType") or
                               "BUFF_SOURCE", owner, ctx.get("source"))
            tgt = _source_unit(battle, node.get("_targetType") or
                               "BUFF_OWNER", owner, ctx.get("source"),
                               ctx.get("target"))
            battle.emit(battle.tick, "line_effect",
                        {"unit": getattr(src, "inst_id", None),
                         "target": getattr(tgt, "inst_id", None),
                         "effect": node.get("_effectKey")})
        return True

    def _n_SetSpineSkin(self, owner, node, ctx):
        """Set the unit's spine skin key (SetSpineSkin, cosmetic state
        exposed in the snapshot)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._spine_skin = node.get("_skinKey")
        if battle:
            battle.emit(battle.tick, "spine_skin",
                        {"unit": getattr(u, "inst_id", None),
                         "skin": node.get("_skinKey")})
        return True

    def _n_PlayUnitAnimation(self, owner, node, ctx):
        battle = self.battle
        if battle:
            u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                             owner, ctx.get("source"), ctx.get("target"))
            battle.emit(battle.tick, "unit_animation",
                        {"unit": getattr(u, "inst_id", None),
                         "animation": node.get("_animation")})
        return True

    # ---- fog of war -------------------------------------------------------
    def _n_MarkFogView(self, owner, node, ctx):
        """Mark the tiles in the unit's range as in/out of the fog view
        (MarkFogView, env_004_fog). State is exposed per-tile in the
        snapshot fogView; targeting does not consume it yet."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        in_view = bool(node.get("_markInView"))
        if node.get("_globalRange"):
            cells = [(r, c) for r in range(battle.map.rows)
                     for c in range(battle.map.cols)]
        else:
            try:
                from .battle import range_offsets_rotated
                offs = range_offsets_rotated(
                    node.get("_rangeId") or "",
                    int(getattr(u, "direction", 1) or 1))
            except Exception:
                offs = [(0, 0)]
            r0 = int(getattr(u, "row", 0) or 0)
            c0 = int(getattr(u, "col", 0) or 0)
            cells = [(r0 + dr, c0 + dc) for dr, dc in offs]
        changed = 0
        for r, c in cells:
            if battle.map.tile(r, c) is None:
                continue
            if in_view:
                if battle._fog_view.pop((r, c), None) is not None:
                    changed += 1
            elif battle._fog_view.get((r, c)) is not True:
                battle._fog_view[(r, c)] = False
                changed += 1
        battle.emit(battle.tick, "fog_view_marked",
                    {"unit": getattr(u, "inst_id", None),
                     "envSystemKey": node.get("_envSystemKey"),
                     "inView": in_view, "cells": len(cells),
                     "changed": changed})
        return True

    # ---- rally-point rebirth ----------------------------------------------
    def _n_SwitchRallyPointCategory(self, owner, node, ctx):
        """Switch the battle's active rally-point category
        (SwitchRallyPointCategory)."""
        battle = self.battle
        if not battle:
            return False
        cat = str(node.get("_category") or "CHARACTER").upper()
        battle._rally_category = cat
        battle._rally_switch_count = int(
            getattr(battle, "_rally_switch_count", 0) or 0) + 1
        battle.emit(battle.tick, "rally_category_switched",
                    {"category": cat,
                     "unit": getattr(owner, "inst_id", None)})
        return True

    def _n_RallyPointReborn(self, owner, node, ctx):
        """Reborn the resolved unit at the nearest rally point of the
        active category (RallyPointReborn). Rally points are registered in
        battle._rally_points per category; without any the node records an
        observable event only."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        cat = battle._rally_category
        pts = battle._rally_points.get(cat) or []
        allu = (list(battle.get_tokens()) + list(battle.get_operators()) +
                list(battle.get_enemies()))
        alive = [x for x in pts
                 if any(t.inst_id == x and not getattr(t, "dead", False)
                        for t in allu)]
        if alive:
            rp = next((t for t in allu
                       if t.inst_id == alive[0] and not t.dead), None)
            if rp is not None:
                u.row, u.col = rp.row, rp.col
                u.pos_x, u.pos_y = rp.pos_x, rp.pos_y
                if hasattr(u, "_sync_tile"):
                    u._sync_tile()
                u.hp = float(u.max_hp)
        battle.emit(battle.tick, "rally_point_reborn",
                    {"unit": getattr(u, "inst_id", None),
                     "category": cat, "rallyPoints": alive})
        return True

    def _n_OnRallyPointLikeReborn(self, owner, node, ctx):
        """Hook fired when a rally-point-like unit is reborn
        (OnRallyPointLikeReborn): observable event; the rebirth state is
        driven by the rally-point system."""
        battle = self.battle
        if battle:
            u = _source_unit(battle, node.get("_targetType") or "TARGET",
                             owner, ctx.get("source"), ctx.get("target"))
            battle.emit(battle.tick, "rally_point_like_reborn",
                        {"unit": getattr(u, "inst_id", None)})
        return True

    def _n_TriggerHostsBuffsByKeys(self, owner, node, ctx):
        """Fire ON_BUFF_TRIGGER on every buff with one of _buffKeys on the
        resolved host unit (TriggerHostsBuffsByKeys; e.g. vigil reborn
        triggers vigil_s_3[buff_token] on its host)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        keys = node.get("_buffKeys") or []
        fired = 0
        for entry in list(getattr(u, "buffs", []) or []):
            if entry.get("key") not in keys and \
                    (entry.get("template_key") or "") not in keys:
                continue
            try:
                battle.buffs._fire(u, entry, "ON_BUFF_TRIGGER",
                                   source=entry.get("source"), target=u)
                fired += 1
            except Exception:
                pass
        return fired > 0

    def _n_RespawnCharacter(self, owner, node, ctx):
        """Respawn the resolved character at the blackboard row/col (or
        in place when _forceRespawnInPlace / _respawnInSameTile): full HP,
        alive, repositioned (RespawnCharacter)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "SOURCE",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        bb = ctx.get("bb") or {}
        if node.get("_forceRespawnInPlace") or node.get("_respawnInSameTile"):
            pass
        else:
            rk = node.get("_rowKey") or "row"
            ck = node.get("_colKey") or "col"
            r = bb.get(rk)
            c = bb.get(ck)
            if r is not None and c is not None:
                u.row = int(r)
                u.col = int(c)
                u.pos_x = float(u.col)
                u.pos_y = float(u.row)
                if hasattr(u, "_sync_tile"):
                    u._sync_tile()
        u.dead = False
        u.hp = float(u.max_hp)
        u._respawn_cnt = int(getattr(u, "_respawn_cnt", 0) or 0) + 1
        battle.emit(battle.tick, "character_respawned",
                    {"unit": getattr(u, "inst_id", None),
                     "row": u.row, "col": u.col,
                     "respawnCnt": u._respawn_cnt})
        return True

    def _n_IsRallyPoint(self, owner, node, ctx):
        """Gate: the resolved unit is a registered rally point
        (IsRallyPoint)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        uid = getattr(u, "inst_id", None)
        return any(uid in pts for pts in battle._rally_points.values())

    def _n_AssignRespawnCntToBlackboard(self, owner, node, ctx):
        """Write the unit's respawn count to the blackboard key
        (AssignRespawnCntToBlackboard, e.g. curRespawnCnt)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        ctx.setdefault("bb", {})[node.get("_blackboardKey") or
                                 "curRespawnCnt"] = int(
            getattr(u, "_respawn_cnt", 0) or 0)
        return True

    def _n_FilterByBlackboardStrIsValue(self, owner, node, ctx):
        """Gate: bb[_valueKey] equals bb[_valueKeyToCompare]
        (FilterByBlackboardStrIsValue)."""
        bb = ctx.get("bb") or {}
        a = bb.get(node.get("_valueKey"))
        b = bb.get(node.get("_valueKeyToCompare"))
        if a is None or b is None:
            return False
        if node.get("_useOrdinalIgnoreCase"):
            return str(a).lower() == str(b).lower()
        return a == b

    def _n_FilterModifierCancelReason(self, owner, node, ctx):
        """Gate: the damage modifier's cancel reason matches _reason."""
        dmg = ctx.get("damage") or {}
        reason = dmg.get("cancelReason") or dmg.get("_cancel_reason") or \
            "NONE"
        want = str(node.get("_reason") or "NONE").upper()
        return str(reason).upper() == want

    def _n_CheckBuildableTypeOfCharacterRootTile(self, owner, node, ctx):
        """Gate: the resolved unit's root tile buildable type contains
        _buildableType (MELEE=1 / RANGED=2)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        t = battle.map.tile(int(getattr(u, "row", 0) or 0),
                            int(getattr(u, "col", 0) or 0))
        if t is None or t.buildable_type is None:
            return False
        want = str(node.get("_buildableType") or "").upper()
        mask = {"MELEE": 1, "RANGED": 2, "HIGH_GROUND": 2}.get(want, 0)
        if not mask:
            return False
        return bool(t.buildable_type & mask)

    def _n_CheckContainsEnvSystem(self, owner, node, ctx):
        """Gate: the battle has the environment system _envSysKey."""
        battle = self.battle
        if not battle:
            return False
        key = node.get("_envSysKey") or ""
        if not key:
            return False
        for env in getattr(battle, "env_systems", []) or []:
            if isinstance(env, dict):
                if env.get("key") == key or env.get("envSystemKey") == key:
                    return True
            elif str(env) == key:
                return True
        return False

    def _n_UpdateScoreManually(self, owner, node, ctx):
        """Add 1 to the battle score counter for _score (bossrush score
        categories), exposed in the snapshot."""
        battle = self.battle
        if not battle:
            return False
        cat = str(node.get("_score") or "BASIC")
        battle._scores[cat] = battle._scores.get(cat, 0) + 1
        battle.emit(battle.tick, "score_updated",
                    {"category": cat, "value": battle._scores[cat]})
        return True

    def _n_GameCityUpdateScore(self, owner, node, ctx):
        """GameCity score update (GameCityUpdateScore): increment the
        game_city counter and emit an observable event."""
        battle = self.battle
        if not battle:
            return False
        battle._scores["game_city"] = battle._scores.get("game_city", 0) + 1
        battle.emit(battle.tick, "score_updated",
                    {"category": "game_city",
                     "value": battle._scores["game_city"]})
        return True

    def _n_FinishGame(self, owner, node, ctx):
        """End the battle with the given result (FinishGame: WIN/LOSE)."""
        battle = self.battle
        if not battle:
            return False
        res = str(node.get("_gameResult") or "WIN").upper()
        battle.finished = True
        battle.result = "defeat" if res == "LOSE" else "victory"
        battle.emit(battle.tick, "battle_end",
                    {"result": battle.result, "node": "FinishGame"})
        return True

    def _n_KillCharacterOnTileIfExists(self, owner, node, ctx):
        """Kill the character on the resolved target's tile
        (KillCharacterOnTileIfExists; _skipReborn leaves the unit dead)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or getattr(u, "dead", False):
            return False
        try:
            battle.apply_damage(u, float(u.hp) + 1.0, DamageType.PURE,
                                source=None, no_hit_recovery=True)
        except Exception:
            u.dead = True
            u.hp = 0.0
        battle.emit(battle.tick, "character_killed",
                    {"unit": getattr(u, "inst_id", None),
                     "skipReborn": bool(node.get("_skipReborn"))})
        return True

    def _n_InterruptCharacterAttack(self, owner, node, ctx):
        """Cancel the resolved character's pending attack; _resetCD also
        zeroes the attack timer."""
        u = _source_unit(self.battle, node.get("_charFrom") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        if getattr(u, "_pending_attack", None) is not None:
            u._pending_attack = None
        if node.get("_resetCD"):
            u.attack_timer = 0.0
        if self.battle:
            self.battle.emit(self.battle.tick, "attack_interrupted",
                             {"unit": getattr(u, "inst_id", None),
                              "resetCd": bool(node.get("_resetCD"))})
        return True

    def _n_HalfIdleDropResource(self, owner, node, ctx):
        """Half-idle resource drop (HalfIdleDropResource): read the pool
        key + count from the blackboard and record the drop (observer
        state, no loot table resolution)."""
        return self._record_loot_drop(owner, node, ctx, kind="resource")

    def _n_HalfIdleDropBattleItem(self, owner, node, ctx):
        """Half-idle battle-item drop (HalfIdleDropBattleItem): same as
        resource drops but from the equip pool."""
        return self._record_loot_drop(owner, node, ctx, kind="battle_item")

    def _record_loot_drop(self, owner, node, ctx, kind):
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        pool_key = bb.get(node.get("_poolKeyBB") or "resource_pool") or \
            "unknown"
        count = max(0, int(_num(bb.get(node.get("_countBB") or "cnt"), 1.0)))
        key = f"{kind}:{pool_key}"
        battle._dropped_loot[key] = battle._dropped_loot.get(key, 0) + count
        battle.emit(battle.tick, "loot_drop",
                    {"kind": kind, "pool": str(pool_key),
                     "count": count,
                     "unit": getattr(owner, "inst_id", None)})
        return count > 0

    def _n_SetCharacterDontOccupyDeployCntFlag(self, owner, node, ctx):
        """Set / unset the character's don't-occupy-deploy-count flag."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._dont_occupy_deploy_cnt = not bool(node.get("_isUnset"))
        if battle:
            battle.emit(battle.tick, "deploy_cnt_flag",
                        {"unit": getattr(u, "inst_id", None),
                         "dontOccupy": u._dont_occupy_deploy_cnt})
        return True

    def _n_ForceCharacterFaceDefaultDirection(self, owner, node, ctx):
        """Force / release the character's default facing."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._force_face_default = bool(node.get("_force"))
        if battle:
            battle.emit(battle.tick, "face_default_flag",
                        {"unit": getattr(u, "inst_id", None),
                         "force": u._force_face_default})
        return True

    def _n_HideEntityGraphicOrNot(self, owner, node, ctx):
        """Hide / show the resolved unit's graphic (HideEntityGraphicOrNot,
        cosmetic state exposed in the snapshot)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._graphic_hidden = bool(node.get("_hide"))
        if battle:
            battle.emit(battle.tick, "graphic_hidden",
                        {"unit": getattr(u, "inst_id", None),
                         "hidden": u._graphic_hidden})
        return True

    def _n_ShakeCamera(self, owner, node, ctx):
        """Camera shake (visual only): observable event with the shake
        params."""
        if self.battle:
            self.battle.emit(self.battle.tick, "camera_shake",
                             {"duration": node.get("_duration"),
                              "strength": node.get("_strength"),
                              "vibrato": node.get("_vibrato"),
                              "randomness": node.get("_randomness")})
        return True

    def _n_EnableShadowController(self, owner, node, ctx):
        """Enable / disable the unit's shadow controller (cosmetic)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._shadow_enabled = bool(node.get("_enabled"))
        if battle:
            battle.emit(battle.tick, "shadow_controller",
                        {"unit": getattr(u, "inst_id", None),
                         "enabled": u._shadow_enabled})
        return True

    def _n_ModifyCharacterSpineColor(self, owner, node, ctx):
        """Modify the character's spine color (cosmetic state, exposed in
        the snapshot as spineColor)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._spine_color = node.get("_color") or \
            (node.get("_newColor") or {}).get("a")
        if battle:
            battle.emit(battle.tick, "spine_color",
                        {"unit": getattr(u, "inst_id", None),
                         "color": u._spine_color,
                         "lockColor": bool(node.get("_lockColor"))})
        return True

    # ---- batch61: visual / animator / log record-only + small real --------
    def _emit_visual(self, node, type_, data=None):
        if self.battle:
            self.battle.emit(self.battle.tick, type_,
                             dict(data or {}))
        return True

    def _n_ChangeAnimatorMeshRenderer(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        return self._emit_visual(
            node, "animator_mesh",
            {"unit": getattr(u, "inst_id", None),
             "rendererIndex": node.get("_rendererIndex"),
             "enable": bool(node.get("_enable")),
             "exclusive": bool(node.get("_exclusive"))})

    def _n_ChangeAnimatorMeshRendererViaIndexList(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        return self._emit_visual(
            node, "animator_mesh",
            {"unit": getattr(u, "inst_id", None),
             "rendererIndexList": node.get("_rendererIndexList"),
             "enable": bool(node.get("_enable"))})

    def _n_ModifyAnimatorHookerReplacePair(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        return self._emit_visual(
            node, "animator_hooker",
            {"unit": getattr(u, "inst_id", None),
             "replaceAnimPairs": node.get("_replaceAnimPairs"),
             "isOverwrite": bool(node.get("_isOverwrite"))})

    def _n_AddHeightOffsetToSpine(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        bb = ctx.get("bb") or {}
        val = _num(bb.get(node.get("_blackboardKey") or "value"),
                   node.get("_offset"))
        if node.get("isSet"):
            u._spine_height_offset = float(val)
        else:
            u._spine_height_offset = float(
                getattr(u, "_spine_height_offset", 0.0) or 0.0) + float(val)
        return self._emit_visual(
            node, "spine_height_offset",
            {"unit": getattr(u, "inst_id", None),
             "offset": round(float(u._spine_height_offset), 4)})

    def _n_Act29SideCheckCurrentAudioType(self, owner, node, ctx):
        """Gate on the act29 audio-type env system (audio state not
        modelled: record the check and pass)."""
        return self._emit_visual(
            node, "act29_audio_check",
            {"envSysKey": node.get("_evnSysKey"),
             "audioType": node.get("_audioType")})

    def _n_Act49sideBossUpdateWarningEffect(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        return self._emit_visual(
            node, "boss_warning_effect",
            {"unit": getattr(u, "inst_id", None),
             "partName": node.get("_partName"),
             "force": bool(node.get("_force"))})

    def _n_ForceCharacterAnimatorFaceFront(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._animator_face_front = bool(node.get("_FroceFaceFront"))
        return self._emit_visual(
            node, "animator_face_front",
            {"unit": getattr(u, "inst_id", None),
             "force": u._animator_face_front})

    def _n_DisableEnemyHud(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._hud_disabled = True
        return self._emit_visual(
            node, "enemy_hud_disabled",
            {"unit": getattr(u, "inst_id", None)})

    def _n_ActiveCameraEffect(self, owner, node, ctx):
        return self._emit_visual(
            node, "camera_effect",
            {"effectKey": node.get("_effectKey"),
             "active": bool(node.get("_active"))})

    def _n_PlayBGM(self, owner, node, ctx):
        return self._emit_visual(node, "bgm_play",
                                 {"needSourceStateRunning": bool(
                                     node.get("_needSourceStateRunning"))})

    def _n_ShowGameCityUiPluginText(self, owner, node, ctx):
        bb = ctx.get("bb") or {}
        return self._emit_visual(
            node, "game_city_ui_text",
            {"unit": getattr(owner, "inst_id", None),
             "index": bb.get(node.get("_indexKey") or "value")})

    def _n_SandboxShowToast(self, owner, node, ctx):
        return self._emit_visual(
            node, "sandbox_toast",
            {"unit": getattr(owner, "inst_id", None),
             "toastKey": node.get("_toastKey"),
             "lastTime": node.get("_lastTime")})

    def _n_CollectTargetInfoFunLiveModeOnly(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        return self._emit_visual(
            node, "funlive_target_info",
            {"unit": getattr(u, "inst_id", None),
             "collectRare": bool(node.get("_collectRareTargetInfo"))})

    def _n_LogExtraBattleInfoForBossRush(self, owner, node, ctx):
        return self._emit_visual(
            node, "extra_battle_info",
            {"unit": getattr(owner, "inst_id", None),
             "infoType": node.get("_infoType"), "key": node.get("_key")})

    def _n_LogExtraBattleInfoWithNoTarget(self, owner, node, ctx):
        battle = self.battle
        bb = ctx.get("bb") or {}
        key = node.get("_key") or ""
        if node.get("_loadKeyFromBlackBoard"):
            key = bb.get(key, key)
        if key and battle is not None:
            battle._extra_log[key] = battle._extra_log.get(key, 0) + int(
                _num(node.get("_additionValue"), 1.0))
        return self._emit_visual(
            node, "extra_battle_info",
            {"key": key, "logType": node.get("_logType"),
             "additionValue": node.get("_additionValue")})

    def _n_LogExtraBattleInfoForModifierRealDelta(self, owner, node, ctx):
        dmg = ctx.get("damage") or {}
        key = node.get("_key") or "modifier_delta"
        if node.get("_cacheLogKey"):
            ctx.setdefault("bb", {})["log_key"] = key
        delta = _num(dmg.get("_real_delta",
                             dmg.get("amount", 0.0)), 0.0)
        return self._emit_visual(
            node, "extra_battle_info",
            {"unit": getattr(owner, "inst_id", None),
             "key": key, "delta": round(delta, 3)})

    def _n_IsTargetInDialog(self, owner, node, ctx):
        """Gate: the resolved target is in a dialog (dialog state not
        modelled: record and fail)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "TARGET",
                         owner, ctx.get("source"), ctx.get("target"))
        if battle:
            battle.emit(battle.tick, "dialog_check",
                        {"unit": getattr(u, "inst_id", None)})
        return False

    def _n_CheckFirstRallyPointMode(self, owner, node, ctx):
        """Gate: the battle has switched the rally category exactly once
        (CheckFirstRallyPointMode approximation)."""
        battle = self.battle
        if not battle:
            return False
        return int(getattr(battle, "_rally_switch_count", 0) or 0) == 1

    def _n_AssignResCountToBB(self, owner, node, ctx):
        """Write the survival-gather resource count of
        bb[_resourceTypeKey] to the blackboard key."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.setdefault("bb", {})
        rtype = bb.get(node.get("_resourceTypeKey") or
                       "survival_gather_type") or "unknown"
        bb[node.get("_blackboardKey") or "remain"] = \
            battle._dropped_loot.get(f"resource:{rtype}", 0)
        return True

    def _n_CharSearchBlockeeImmediate(self, owner, node, ctx):
        """Find the enemy immediately blocking the resolved character and
        write its inst_id to bb 'blockee_inst_id' (CharSearchBlockeeImmediate)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        blockee = None
        for e in getattr(u, "blocked_enemies", []) or []:
            if not getattr(e, "dead", False):
                blockee = e
                break
        bb = ctx.setdefault("bb", {})
        bb["blockee_inst_id"] = getattr(blockee, "inst_id", None)
        return blockee is not None

    def _n_SwitchDynamicBuffTileModeInRange(self, owner, node, ctx):
        """Switch the dynamic buff tile mode over the unit's range
        (SwitchDynamicBuffTileModeInRange); _decBbKey decrements the
        blackboard counter."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        try:
            from .battle import range_offsets_rotated
            offs = range_offsets_rotated(
                node.get("_rangeId") or "",
                int(getattr(src, "direction", 1) or 1))
        except Exception:
            offs = [(0, 0)]
        r0 = int(getattr(src, "row", 0) or 0)
        c0 = int(getattr(src, "col", 0) or 0)
        mode = node.get("_modeIndex")
        op = node.get("_operation") or "SET_INDEX"
        changed = 0
        for dr, dc in offs:
            r, c = r0 + dr, c0 + dc
            if battle.map.tile(r, c) is None:
                continue
            if node.get("_requireCharacterNotOn") and any(
                    getattr(u, "row", -1) == r and getattr(u, "col", -1) == c
                    for u in list(battle.get_enemies()) +
                    list(battle.get_operators()) + list(battle.get_tokens())):
                continue
            battle._tile_modes[(r, c)] = mode
            changed += 1
        dk = node.get("_decBbKey")
        if dk:
            bb = ctx.setdefault("bb", {})
            bb[dk] = max(0, int(_num(bb.get(dk), 0.0)) - 1)
        battle.emit(battle.tick, "tile_mode_switch",
                    {"unit": getattr(src, "inst_id", None),
                     "operation": op, "modeIndex": mode,
                     "cells": changed})
        return True

    def _n_RewriteDynamicBuffTileOptionsOneLine(self, owner, node, ctx):
        """Write the dynamic buff tile option (_buffKey) into a line of
        cells from the source (RewriteDynamicBuffTileOptionsOneLine;
        minimal tile-blackboard state)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        row = int(getattr(src, "row", 0) or 0)
        col = int(getattr(src, "col", 0) or 0)
        direction = str(node.get("_direction") or "RIGHT").upper()
        dmap = {"LEFT": (0, -1), "RIGHT": (0, 1),
                "UP": (-1, 0), "DOWN": (1, 0)}
        dr, dc = dmap.get(direction, (0, 1))
        buff_key = node.get("_buffKey") or "tile_buff"
        changed = 0
        for step in range(1, 4):
            r, c = row + dr * step, col + dc * step
            if battle.map.tile(r, c) is None:
                break
            battle._tile_bb.setdefault((r, c), {})[buff_key] = 1
            changed += 1
        battle.emit(battle.tick, "tile_options_line",
                    {"unit": getattr(src, "inst_id", None),
                     "buffKey": buff_key, "direction": direction,
                     "cells": changed})
        return True

    def _n_HalfIdleTriggerTrapUpgradeCheck(self, owner, node, ctx):
        """Trigger the half-idle trap upgrade check for the trap at the
        source tile (observable; the actual upgrade is performed by
        HalfIdleUpgradeTrap when the conditions pass)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourcePosType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        row = int(getattr(src, "row", 0) or 0)
        col = int(getattr(src, "col", 0) or 0)
        trap = next((t for t in battle.get_tokens()
                     if not t.dead and t.row == row and t.col == col), None)
        battle.emit(battle.tick, "trap_upgrade_check",
                    {"unit": getattr(src, "inst_id", None),
                     "row": row, "col": col,
                     "trap": getattr(trap, "token_id", None)})
        return trap is not None

    # ---- batch60: card-all / deck-by-cnt / drag / skill-cd / tile side ----
    def _n_CreateCardBuffToAllCard(self, owner, node, ctx):
        """Create the card on every unit holding at least one card
        (CreateCardBuffToAllCard; excludes the owner / tokens and traps
        per the flags)."""
        battle = self.battle
        if not battle:
            return False
        key = self._card_key(node, ctx)
        if not key:
            return False
        hit = 0
        for u in (list(battle.get_enemies()) +
                  list(battle.get_operators()) +
                  list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if node.get("_exceptOwner") and u is owner:
                continue
            if node.get("_exceptTokenAndTrap") and \
                    getattr(u, "token_id", None) is not None:
                continue
            if not getattr(u, "cards", None):
                continue
            self._add_card(u, key, node.get("_lifeType"), ctx)
            hit += 1
        return hit > 0

    def _n_CreateDeckBuffByCnt(self, owner, node, ctx):
        """Create _deckBuff repeatedly on the resolved target
        (CreateDeckBuffByCnt; each add stacks layers)."""
        battle = self.battle
        if not battle:
            return False
        deck = node.get("_deckBuff") or {}
        buf = deck.get("buff") or {}
        key = buf.get("buffKey") or deck.get("deckBuffKey") or ""
        if not key:
            return False
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        cnt = max(1, int(_num(node.get("_cnt"), 1.0)))
        uid = None
        for _ in range(cnt):
            uid = self._add_card(u, key, deck.get("lifeType"), ctx)
        for c in u.cards:
            if c.get("uid") == uid:
                c["isDeck"] = True
                c["cardEffectType"] = deck.get("cardEffectType")
        ctx.setdefault("bb", {})["card_uid"] = uid
        return True

    def _n_DragTowardSource(self, owner, node, ctx):
        """Drag the target toward the source by up to 1 tile
        (DragTowardSource, simplified pull)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source") or "SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_target") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None or src is tgt or \
                getattr(tgt, "dead", False):
            return False
        dx = float(src.pos_x) - float(tgt.pos_x)
        dy = float(src.pos_y) - float(tgt.pos_y)
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 1e-6:
            return False
        pull = min(1.0, dist)
        dr = int(round(dy / dist)) if dist > 0 else 0
        dc = int(round(dx / dist)) if dist > 0 else 0
        if dr == 0 and dc == 0:
            dr, dc = (1, 0) if abs(dy) >= abs(dx) else (0, 1)
        try:
            battle.displace(tgt, dr, dc, pull, source=src)
        except Exception:
            return False
        battle.emit(battle.tick, "drag_toward_source",
                    {"unit": getattr(tgt, "inst_id", None),
                     "source": getattr(src, "inst_id", None),
                     "distance": round(pull, 4)})
        return True

    def _n_SetStackCountViaBlockNum(self, owner, node, ctx):
        """Set the current buff's stack count (layers) to the owner's
        blocked-enemy count (SetStackCountViaBlockNum)."""
        bb = ctx.setdefault("bb", {})
        entry = bb.get("_buff_entry")
        if not isinstance(entry, dict):
            return False
        n = len(getattr(owner, "blocked_enemies", []) or [])
        entry["layers"] = max(1, int(n or 0))
        return True

    def _n_ReInitEnemySkillCoolDown(self, owner, node, ctx):
        """Reset the enemy skill _skillName's cooldown
        (ReInitEnemySkillCoolDown; _onlyResetCD zeroes it, otherwise the
        skill re-initialises from its cooldown sequence)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        name = node.get("_skillName") or ""
        sc = getattr(u, "skill_controller", None)
        if sc is None or not name:
            return False
        hit = False
        for run in getattr(sc, "skills", []) or []:
            prefab = getattr(getattr(run, "skill", None), "prefab_key", None) \
                or getattr(run, "prefab_key", None)
            if prefab != name:
                continue
            try:
                if node.get("_onlyResetCD"):
                    run.cooldown_remaining = 0.0
                else:
                    run.skill._apply_cooldown()
                hit = True
            except Exception:
                pass
        return hit

    def _n_EnemySkipWaitCheckPoint(self, owner, node, ctx):
        """Mark the enemy to skip WAIT checkpoints (EnemySkipWaitCheckPoint)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._skip_wait_checkpoint = True
        if battle:
            battle.emit(battle.tick, "enemy_skip_wait_cp",
                        {"unit": getattr(u, "inst_id", None)})
        return True

    def _n_DamageViaEs(self, owner, node, ctx):
        """Deal damage through the ES (energy) value
        (DamageViaEs; the ES system itself is a placeholder - the damage
        amount is read from the blackboard 'damage' or atk*atk_scale)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None:
            src = owner
        if tgt is None or getattr(tgt, "dead", False):
            return False
        bb = ctx.get("bb") or {}
        amount = _num(bb.get("damage"), 0.0)
        if amount <= 0:
            atk = _num(getattr(src.attributes, "get", lambda k: 0.0)("atk"), 0.0)
            amount = atk * _num(bb.get("atk_scale"), 1.0)
        if amount <= 0:
            return True
        battle.apply_damage(tgt, amount, self._dmg_type(node.get("_damageType")),
                            source=src, no_hit_recovery=bool(
                                node.get("_skipModifierEvent")))
        battle.emit(battle.tick, "es_damage",
                    {"unit": getattr(src, "inst_id", None),
                     "target": getattr(tgt, "inst_id", None),
                     "amount": round(amount, 3),
                     "esPlaceholder": True})
        return True

    def _n_CheckCharacterSkillType(self, owner, node, ctx):
        """Gate: the character's skill type matches _skillType
        (MANUAL=1 / AUTO=2)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        want = str(node.get("_skillType") or "").upper()
        want_i = {"MANUAL": 1, "AUTO": 2}.get(want, 1)
        sc = getattr(u, "skill_controller", None)
        if sc is None:
            return False
        act = getattr(sc, "active", None)
        if act is not None:
            st = getattr(getattr(act, "skill", None), "skill_type", None)
            if st is not None:
                return int(st) == want_i
        for run in getattr(sc, "skills", []) or []:
            st = getattr(getattr(run, "skill", None), "skill_type", None)
            if st is not None and int(st) == want_i:
                return True
        return False

    def _n_HideEntityInFogAndManageBuff(self, owner, node, ctx):
        """Hide the resolved unit's graphic in fog and apply the embedded
        buff (HideEntityInFogAndManageBuff)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._graphic_hidden = True
        bd = dict(node.get("_buff") or {})
        if bd.get("buffKey"):
            entry = materialise_buff(battle, u, bd, dict(ctx.get("bb") or {}),
                                     owner)
            if entry and entry.get("key"):
                battle.add_buff(u, entry)
        battle.emit(battle.tick, "entity_fog_hidden",
                    {"unit": getattr(u, "inst_id", None),
                     "buff": bd.get("buffKey")})
        return True

    def _n_EmitProjectileToTileUseSelector(self, owner, node, ctx):
        """Emit a projectile toward a tile / the resolved target unit
        (EmitProjectileToTileUseSelector; with a unit target the on-hit
        actions run on impact, otherwise the launch is recorded)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        tgt = _source_unit(battle, node.get("_targetType") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        key = node.get("_projectileKey") or ""
        if not key:
            key = (ctx.get("bb") or {}).get("projectile_key") or ""
        if tgt is None or getattr(tgt, "dead", False):
            battle.emit(battle.tick, "buff_emit_projectile",
                        {"unit": getattr(src, "inst_id", None),
                         "projectile": key or self._unit_projectile_key(src),
                         "ev": node.get("_ev"), "tileTarget": True,
                         "skipped": "no_unit_target"})
            return True
        ok = self._emit_projectile_with_hit(src, tgt, key, node, ctx)
        battle.emit(battle.tick, "buff_emit_projectile",
                    {"unit": getattr(src, "inst_id", None),
                     "target": getattr(tgt, "inst_id", None),
                     "projectile": key or self._unit_projectile_key(src),
                     "ev": node.get("_ev"), "tileTarget": True})
        return ok

    def _n_ApplyCacheAtkDamageFromBuff(self, owner, node, ctx):
        """Deal damage from the buff-cached atk (bb 'atk') scaled by
        bb[_damageScaleKey] (ApplyCacheAtkDamageFromBuff)."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        atk = _num(bb.get("atk"), 0.0)
        scale = _num(bb.get(node.get("_damageScaleKey") or "atk_scale"), 1.0)
        amount = atk * scale
        tgt = _source_unit(battle, node.get("_targetType") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None or getattr(tgt, "dead", False) or amount <= 0:
            return True
        battle.apply_damage(tgt, amount, self._dmg_type(node.get("_damageType")),
                            source=owner, no_hit_recovery=True)
        return True

    def _n_HalfIdleUpgradeTrap(self, owner, node, ctx):
        """Upgrade the trap at the source tile: replace the token matching
        bb[_upgradeTrapKey] with _upgradeTrapId (HalfIdleUpgradeTrap)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourcePosType") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        old_key = str(bb.get(node.get("_upgradeTrapKey") or "token_id") or "")
        new_id = node.get("_upgradeTrapId") or ""
        row = int(getattr(src, "row", 0) or 0)
        col = int(getattr(src, "col", 0) or 0)
        found = None
        for tk in list(battle.get_tokens()):
            if tk.dead or (tk.row, tk.col) != (row, col):
                continue
            if old_key and tk.token_id != old_key:
                continue
            found = tk
            break
        if found is None or not new_id:
            return False
        battle._retire_token(found, reason="upgrade")
        ok, _ = battle.spawn_token_forced(new_id, row, col, owner=owner)
        battle.emit(battle.tick, "trap_upgraded",
                    {"unit": getattr(src, "inst_id", None),
                     "from": old_key, "to": new_id,
                     "row": row, "col": col, "ok": bool(ok)})
        return bool(ok)

    def _n_Act27sideModifyTileCachedSideType(self, owner, node, ctx):
        """Cache the side type (ALLY/ENEMY) of the source's root tile (or
        its range when _useRangeId) - Act27sideModifyTileCachedSideType,
        exposed in the snapshot tileSideCache."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        side = str(node.get("_sideType") or "ALLY").upper()
        if node.get("_useRangeId"):
            try:
                from .battle import range_offsets_rotated
                offs = range_offsets_rotated(
                    node.get("_rangeId") or "",
                    int(getattr(src, "direction", 1) or 1))
            except Exception:
                offs = [(0, 0)]
            r0 = int(getattr(src, "row", 0) or 0)
            c0 = int(getattr(src, "col", 0) or 0)
            cells = [(r0 + dr, c0 + dc) for dr, dc in offs]
        else:
            cells = [(int(getattr(src, "row", 0) or 0),
                      int(getattr(src, "col", 0) or 0))]
        for r, c in cells:
            if battle.map.tile(r, c) is not None:
                battle._tile_side_cache[(r, c)] = side
        battle.emit(battle.tick, "tile_side_cached",
                    {"unit": getattr(src, "inst_id", None),
                     "sideType": side, "cells": len(cells)})
        return True

    def _n_SummonEnemiesFollowBranchRouteWithTileBlackboard(self, owner,
                                                            node, ctx):
        """Summon enemies along a branch route read from the source tile's
        blackboard (SummonEnemiesFollowBranchRouteWithTileBlackboard)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        key = self._summon_enemy_key(node, ctx.get("bb") or {})
        if not key:
            return False
        row = int(getattr(src, "row", 0) or 0)
        col = int(getattr(src, "col", 0) or 0)
        tbb = battle.tile_blackboard(row, col)
        route_index = 0
        try:
            route_index = int(tbb.get("branch_id", 0) or 0)
        except (TypeError, ValueError):
            pass
        e = battle.spawn_enemy_directive(key, row, col,
                                         route_index=route_index)
        if e is None:
            return False
        if node.get("_unharmful"):
            e.is_unharmful = True
        bd = node.get("_buffToEnemy")
        if isinstance(bd, dict) and bd.get("buffKey"):
            self._apply_summon_buffs(battle, e, [bd], ctx.get("bb") or {},
                                     owner)
        battle.emit(battle.tick, "enemy_summoned",
                    {"unit": getattr(src, "inst_id", None),
                     "enemyKey": key, "count": 1,
                     "instances": [e.inst_id],
                     "node": "SummonEnemiesFollowBranchRouteWithTileBlackboard"})
        return True

    # ---- batch62: football / legion / roguelike / small real -------------
    def _fever_value(self, node):
        battle = self.battle
        if battle is None:
            return 0.0
        key = node.get("_feverKey") or "env_033_fever"
        return float(battle._fever.get(key, 0.0) or 0.0)

    def _n_IsInFever(self, owner, node, ctx):
        return self._fever_value(node) > 0.0

    def _n_IsFeverFull(self, owner, node, ctx):
        return self._fever_value(node) >= 1.0

    def _n_AddFeverBySourceIfNotFull(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        key = node.get("_feverKey") or "env_033_fever"
        cur = self._fever_value(node)
        if cur >= 1.0:
            return False
        bb = ctx.get("bb") or {}
        delta = _num(bb.get("value"), 0.1)
        battle._fever[key] = min(1.0, cur + delta)
        battle.emit(battle.tick, "fever_added",
                    {"key": key, "value": round(battle._fever[key], 4)})
        return True

    def _n_TryActiveFeverIfFull(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        key = node.get("_feverKey") or "env_033_fever"
        if self._fever_value(node) < 1.0:
            return False
        battle._fever_active = True
        battle._fever[key] = 0.0
        battle.emit(battle.tick, "fever_activated", {"key": key})
        return True

    def _n_IsCloseToFootball(self, owner, node, ctx):
        battle = self.battle
        if not battle or battle._football_pos is None:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        fr, fc = battle._football_pos
        return abs(u.row - fr) + abs(u.col - fc) <= 1

    def _n_StopBall(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        battle._football_stopped = bool(node.get("_force", True))
        battle.emit(battle.tick, "football_stopped",
                    {"stopped": battle._football_stopped})
        return True

    def _n_LegionModeOnlyGainGold(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        if node.get("_loadFromBlackboard"):
            gold = int(_num(bb.get(node.get("_goldNumKey") or "gold_num"),
                            node.get("_goldNum") or 0))
        else:
            gold = int(_num(node.get("_goldNum"), 0))
        battle._legion_gold += max(0, gold)
        battle.emit(battle.tick, "legion_gold",
                    {"gold": battle._legion_gold, "delta": gold})
        return True

    def _n_LegionModeOnlyGainTrap(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        key = node.get("_tokenKey") or ""
        if key:
            battle._legion_traps.add(key)
        battle.emit(battle.tick, "legion_trap",
                    {"tokenKey": key, "cardType": node.get("_gainToCardType")})
        return True

    def _n_LegionModeOnlyDrawNextCard(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        if battle._legion_pending:
            battle._legion_hand.append(battle._legion_pending.pop(0))
        battle.emit(battle.tick, "legion_draw",
                    {"hand": list(battle._legion_hand)})
        return True

    def _n_LegionModeOnlySelectCard(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        n = max(0, int(_num(bb.get(node.get("_rangeNumKey") or "range_num"),
                            0.0)))
        card = bb.get("card_key")
        if card:
            battle._legion_hand.append(card)
        battle.emit(battle.tick, "legion_select",
                    {"count": n, "card": card})
        return True

    def _n_LegionModeOnlyCheckCardInHand(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        return bool(battle._legion_hand)

    def _n_LegionModeOnlyMarkCardReturnToHand(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        card = (ctx.get("bb") or {}).get("card_key")
        if card:
            battle._legion_hand.append(card)
        battle.emit(battle.tick, "legion_return_hand",
                    {"card": card, "keepStatus": bool(
                        node.get("_needKeepStatus"))})
        return True

    def _n_LegionModeOnlyAddProfessionLevel(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        prof = str(node.get("_professionCategory") or "NONE")
        battle._legion_profession_levels[prof] = \
            battle._legion_profession_levels.get(prof, 0) + int(
                _num(node.get("_levelCnt"), 1.0))
        battle.emit(battle.tick, "legion_profession_level",
                    {"profession": prof,
                     "level": battle._legion_profession_levels[prof]})
        return True

    def _n_LegionModeOnlyAssignDangerLevelToBB(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        ctx.setdefault("bb", {})[node.get("_dangerLevelKey") or
                                 "current_danger_level"] = \
            battle._legion_danger_level
        return True

    def _n_CompareRogueDiceNumber(self, owner, node, ctx):
        bb = ctx.get("bb") or {}
        v = _num(bb.get(node.get("_blackboardKey") or "dice_var"), 0.0)
        t = _num(node.get("_threshold"), 0.0)
        cond = str(node.get("_condType") or "EQ").upper()
        if cond in ("LE", "<="):
            return v <= t
        if cond in ("GE", ">="):
            return v >= t
        if cond in ("LT", "<"):
            return v < t
        if cond in ("GT", ">"):
            return v > t
        if cond in ("NE", "!="):
            return v != t
        return v == t

    def _n_RoguelikeLogExp(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        battle._rogue_exp += max(0, int(_num(bb.get(
            node.get("_expKey") or "exp"), 0.0)))
        battle.emit(battle.tick, "rogue_exp",
                    {"exp": battle._rogue_exp,
                     "expType": node.get("_expType")})
        return True

    def _n_SkipStage(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        battle.finished = True
        battle.result = "victory"
        battle.emit(battle.tick, "battle_end",
                    {"result": "victory", "node": "SkipStage"})
        return True

    def _n_AOEElementDamage(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        amount = _num(bb.get(node.get("_fixedEpDamageKey"),
                             node.get("_fixedEpDamage")), 0.0)
        if node.get("_isFixedEpDamage") is False and amount <= 0:
            atk = _num(getattr(src.attributes, "get",
                               lambda k: 0.0)("atk"), 0.0)
            amount = atk * _num(bb.get("ep_damage_ratio", 1.0), 1.0)
        et = {"FIRE": 2, "BURN": 2, "EROSION": 1, "DECAY": 3,
              "SANITY": 0, "NEURAL": 0}.get(
                  str(node.get("_elementDamageType") or "FIRE").upper(), 2)
        radius = 1.5
        if node.get("_useRadius"):
            radius = _num(node.get("_radius"), 1.5)
        hit = 0
        for u in list(battle.get_enemies()) + list(battle.get_operators()) + \
                list(battle.get_tokens()):
            if getattr(u, "dead", False):
                continue
            if abs(u.row - src.row) > radius or abs(u.col - src.col) > radius:
                continue
            battle.add_ep(u, et, amount, source=src)
            hit += 1
        return hit > 0

    def _n_HasCertainCharacterInFrontOfMe(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source") or "SOURCE",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        key = node.get("_characterKey") or ""
        if not key:
            return False
        d = int(getattr(src, "direction", 1) or 1)
        dmap = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        dr, dc = dmap.get(d % 4, (0, 1))
        cells = [(src.row + dr, src.col + dc),
                 (src.row + dr + dr, src.col + dc + dc)]
        for u in list(battle.get_tokens()) + list(battle.get_operators()) + \
                list(battle.get_enemies()):
            if getattr(u, "dead", False):
                continue
            if (u.row, u.col) not in cells:
                continue
            if str(getattr(u, "char_id", "") or
                   getattr(u, "token_id", "")) == key:
                return True
        return False

    def _n_FilterTargetWithPlayerSide(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if node.get("filterTargetPlayerSide") and u is not None:
            return int(getattr(u, "side", 0) or 0) == 1
        return True

    def _n_AssignEnemyLastMoveDirectionToBB(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_target") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        d = getattr(u, "_last_move_direction", None)
        if d is None:
            d = int(getattr(u, "direction", 1) or 1)
        ctx.setdefault("bb", {})[node.get("_blackboardKey") or
                                 "direction"] = d
        return True

    def _n_CheckDistanceToTileCenter(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        dx = float(u.pos_x) - float(u.col)
        dy = float(u.pos_y) - float(u.row)
        dist = (dx * dx + dy * dy) ** 0.5
        t = _num(node.get("_distance"), 1.0)
        cond = str(node.get("_condType") or "LE").upper()
        if cond in ("GE", ">="):
            return dist >= t
        if cond in ("GT", ">"):
            return dist > t
        return dist <= t

    def _n_CheckEnemyIsStayStill(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_target") or
                         "MODIFIER_TARGET", owner, ctx.get("source"),
                         ctx.get("target"))
        if u is None:
            return False
        from .consts import EnemyState
        return getattr(u, "state", None) != EnemyState.MOVE or \
            bool(getattr(u, "blocked_by", None))

    def _n_ExtendAbilityCooldown(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        name = node.get("_abilityName") or ""
        bb = ctx.get("bb") or {}
        ext = _num(bb.get(node.get("_extendTimeKey") or "duration"), 0.0)
        sc = getattr(u, "skill_controller", None)
        if sc is None or not name:
            return False
        hit = False
        for run in getattr(sc, "skills", []) or []:
            prefab = getattr(getattr(run, "skill", None), "prefab_key", None) \
                or getattr(run, "prefab_key", None)
            if prefab != name:
                continue
            try:
                run.cooldown_remaining = float(
                    getattr(run, "cooldown_remaining", 0.0) or 0.0) + ext
                hit = True
            except Exception:
                pass
        return hit

    def _n_SetCastSkillCost(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        bb = ctx.setdefault("bb", {})
        val = node.get("_value")
        vk = node.get("_valueBbKey")
        if vk and bb.get(vk) is not None:
            val = bb[vk]
        sc = getattr(u, "skill_controller", None)
        if sc is None:
            return False
        if node.get("_assignOldValueKey"):
            bb[node.get("_assignOldValueKey")] = int(
                getattr(getattr(getattr(sc, "active", None), "skill", None),
                        "sp_cost", 0) or 0)
        try:
            sk = getattr(getattr(sc, "active", None), "skill", None)
            if sk is not None:
                sk.sp_cost = int(_num(val, 0.0))
                return True
        except Exception:
            pass
        return False

    def _n_AssignEntityEsIntoBlackboard(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        # ES (energy) system is a placeholder: write 0 and note it
        ctx.setdefault("bb", {})[node.get("_blackboardKey") or
                                 "es_value"] = 0
        return True

    def _n_CheckCharacterIsMannuallySpawned(self, owner, node, ctx):
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        return bool(getattr(u, "_manually_spawned", False))

    def _n_Act46SideAddAreaSP(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        val = _num(bb.get(node.get("_valueKey") or "sp"),
                   node.get("_value") or 0.0)
        hit = 0
        for op in list(battle.get_operators()):
            if getattr(op, "dead", False):
                continue
            if abs(op.row - src.row) > 1.5 or abs(op.col - src.col) > 1.5:
                continue
            sc = getattr(op, "skill_controller", None)
            if sc is not None:
                sc.recover_sp(int(val))
            hit += 1
        return hit > 0

    def _n_SwitchToRebornState(self, owner, node, ctx):
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        u._reborn_state = True
        if battle:
            battle.emit(battle.tick, "reborn_state",
                        {"unit": getattr(u, "inst_id", None),
                         "force": bool(node.get("_isForce"))})
        return True

    def _n_RandomAction(self, owner, node, ctx):
        """Pick one action branch by the blackboard probability _probKey
        and run it (RandomAction)."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        prob = _num(bb.get(node.get("_probKey") or "prob1"), 0.5)
        branch = None
        if battle.rng is not None:
            try:
                if battle.rng.NextDouble() < prob:
                    branch = node.get("_actions") or []
            except Exception:
                branch = node.get("_actions") or []
        else:
            branch = node.get("_actions") or []
        if not branch:
            branch = node.get("_failActions") or []
        if branch:
            self.run_actions(owner, branch, ctx, 0)
        return True

    def _n_CreateBuffToCharacterInSpecifiedArea(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        bd = dict(node.get("_buffData") or {})
        if not bd.get("buffKey"):
            return False
        radius = 1.5
        hit = 0
        for op in list(battle.get_operators()):
            if getattr(op, "dead", False):
                continue
            if abs(op.row - src.row) > radius or abs(op.col - src.col) > radius:
                continue
            entry = materialise_buff(battle, op, bd, dict(ctx.get("bb") or {}),
                                     owner)
            if entry and entry.get("key"):
                battle.add_buff(op, entry)
                hit += 1
        return hit > 0

    def _n_ClearCharacterOnTileIfExists(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None or getattr(u, "dead", False):
            return False
        try:
            battle.apply_damage(u, float(u.hp) + 1.0, DamageType.PURE,
                                source=None, no_hit_recovery=True)
        except Exception:
            u.dead = True
            u.hp = 0.0
        return True

    def _n_KnockBackWithCharacterDirection(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source") or "SOURCE",
                           owner, ctx.get("source"))
        tgt = _source_unit(battle, node.get("_target") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None or src is tgt or \
                getattr(tgt, "dead", False):
            return False
        d = int(getattr(src, "direction", 1) or 1)
        dmap = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        dr, dc = dmap.get(d % 4, (0, 1))
        try:
            battle.displace(tgt, dr, dc, 1.0, source=src)
        except Exception:
            return False
        battle.emit(battle.tick, "knockback",
                    {"unit": getattr(tgt, "inst_id", None),
                     "source": getattr(src, "inst_id", None),
                     "direction": d})
        return True

    def _n_AddExcludeCharacterToDynamicBuffTile(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "SOURCE",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        battle._dynamic_tile_excludes.add(getattr(u, "inst_id", -1))
        return True

    def _n_FinishSpecifiedTileHoldingEffect(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        key = node.get("_effectKey") or ""
        cell = (getattr(u, "row", 0), getattr(u, "col", 0))
        held = battle._tile_holding_effects.get(cell)
        if held and key in held:
            held.discard(key)
        battle.emit(battle.tick, "tile_holding_effect_finished",
                    {"row": cell[0], "col": cell[1], "effect": key})
        return True

    def _n_ModifyAttributeDataRangeOverride(self, owner, node, ctx):
        """Clamp the resolved unit's attribute to a blackboard minimum
        (ModifyAttributeDataRangeOverride; the move_speed_range_override
        template keeps respawning enemies' moveSpeed >= the bb minimum).
        _doClear removes the clamp."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        attr = str(node.get("_attributeType") or "").upper()
        if attr not in ("MOVE_SPEED", "MOVESPEED"):
            return True
        if node.get("_doClear"):
            u._move_speed_min = 0.0
        else:
            bb = ctx.get("bb") or {}
            mv = bb.get(node.get("_minValueKey") or "minValue")
            if mv is not None:
                u._move_speed_min = float(mv)
        if battle:
            battle.emit(battle.tick, "attr_range_override",
                        {"unit": getattr(u, "inst_id", None),
                         "attribute": attr,
                         "min": u._move_speed_min,
                         "cleared": bool(node.get("_doClear"))})
        return True

    def _n_AssignStealAttributeAbilityTotalValueToBB(self, owner, node, ctx):
        """Write the accumulated steal-attribute value of the named
        ability to the blackboard (AssignStealAttributeAbilityTotal-
        ValueToBB). _assignStealMaxValue writes the cap instead. The
        accumulator is battle-side (keyed by unit+ability, starts at 0);
        the cap defaults to the unit's matching stat until a dedicated
        steal-ability executor feeds it."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_SOURCE",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        name = node.get("_abilityName") or "StealAtk"
        key = (getattr(u, "inst_id", None), name)
        cur = battle._steal_values.get(key) or 0.0
        cap = battle._steal_max.get(key)
        if cap is None:
            stat = {"StealAtk": "atk", "StealHp": "maxHp",
                    "StealDef": "def"}.get(name)
            try:
                cap = float(u.attributes.get(stat) or 0.0) if stat else 0.0
            except (TypeError, ValueError):
                cap = 0.0
            battle._steal_max[key] = cap
        bb = ctx.setdefault("bb", {})
        if node.get("_assignStealMaxValue"):
            bb["max_steal_value"] = float(cap)
        else:
            bb[f"steal_{name.lower().replace('steal', '')}"] = float(cur)
        battle.emit(battle.tick, "steal_value_assigned",
                    {"unit": getattr(u, "inst_id", None),
                     "ability": name,
                     "value": round(float(cur), 3),
                     "max": round(float(cap), 3),
                     "assignMax": bool(node.get("_assignStealMaxValue"))})
        return True

    def _n_IgnoreAllButMoveCp(self, owner, node, ctx):
        """Toggle the enemy's ignore-all-but-MOVE-checkpoints flag
        (IgnoreAllButMoveCp): while set, WAIT/PATROL/DISAPPEAR
        checkpoints are skipped and the enemy walks straight along the
        flow field."""
        battle = self.battle
        u = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"))
        if u is None:
            u = owner
        u._ignore_all_but_move_cp = bool(node.get("_ignore"))
        if battle:
            battle.emit(battle.tick, "enemy_ignore_nonmove_cp",
                        {"unit": getattr(u, "inst_id", None),
                         "ignore": bool(node.get("_ignore"))})
        return True

    def _n_FinishManagedProjectiles(self, owner, node, ctx):
        """Remove the projectiles managed by (sourced from) the resolved
        unit (e.g. enemy_mpprme_fly clears its lingering rays on buff end)."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        killed = 0
        for p in list(getattr(battle, "projectiles", []) or []):
            if getattr(p, "source", None) is not u:
                continue
            if getattr(p, "dead", False):
                continue
            p.dead = True
            killed += 1
        return killed > 0

    def _n_AOEHeal(self, owner, node, ctx):
        """Heal every unit of the target side within the range around the
        center (breeze S2 spreads a medical projectile's heal to the 8
        surrounding cells at attack@scale; enemy_ltnhap heals its group).
        _sourceSideType decides which literal side "ALLY" means (an enemy
        healer's ALLY is the enemy team)."""
        battle = self.battle
        if not battle:
            return True
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_SOURCE",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        center = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                              owner, ctx.get("source"), ctx.get("target"))
        if center is None:
            center = owner
        bb = ctx.get("bb") or {}
        scale = _num(bb.get(node.get("_healScale") or "heal_scale"), 0.0)
        if scale <= 0:
            return True
        opts = node.get("_targetOptions") or {}
        side = str(opts.get("targetSide") or "ALLY").upper()
        src_side = int(getattr(src, "side", 1) or 1)
        want = src_side if side == "ALLY" else (1 - src_side)
        ignore_heal_free = bool(node.get("_ignoreHealFree") or
                                opts.get("ignoreHealFree"))
        rid = node.get("_rangeId")
        if node.get("_useAttackRange"):
            cells = list(getattr(src, "range_shape", []) or [])
        elif rid:
            try:
                from .battle import range_offsets_rotated
                cells = range_offsets_rotated(
                    rid, getattr(center, "direction", 1))
            except Exception:
                cells = []
        else:
            cells = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                     if not (dr == 0 and dc == 0)]
        amount = _num(getattr(src, "attributes", None) and
                      src.attributes.get("atk"), 0.0) * scale
        units = (list(battle.get_operators()) + list(battle.get_tokens())
                 if want == 1 else list(battle.get_enemies()))
        exclude = center if node.get("_excludeTarget") else None
        healed = 0
        for u in units:
            if getattr(u, "dead", False) or u is exclude:
                continue
            if getattr(u, "side", 0) != want:
                continue
            pos = (getattr(u, "row", 0), getattr(u, "col", 0))
            if pos not in [(center.row + dr, center.col + dc)
                           for dr, dc in cells]:
                continue
            if not ignore_heal_free and                     getattr(u, "heal_free", lambda: False)():
                continue
            battle.apply_heal(u, amount, source=src)
            healed += 1
        return healed > 0

    def _n_CheckHasSp(self, owner, node, ctx):
        """Gate: the resolved unit has / lacks SP (_checkHasSp 1/0)."""
        u = _source_unit(self.battle, node.get("_ownerType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return False
        sp = _num(getattr(u, "sp", 0.0) or 0.0)
        want = node.get("_checkHasSp")
        if want is None:
            want = 1
        else:
            try:
                want = int(float(want))
            except (TypeError, ValueError):
                want = 1
        has = sp > 0
        return has if want == 1 else not has

    def _n_KillTokens(self, owner, node, ctx):
        """Kill the tokens owned by the resolved unit (owner reference),
        optionally filtered by an embedded buff key."""
        battle = self.battle
        if not battle:
            return False
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            u = owner
        need_buff = node.get("_buffKey") or ""
        killed = 0
        for t in list(getattr(battle, "tokens", []) or []):
            if getattr(t, "owner", None) is not u:
                continue
            if getattr(t, "dead", False):
                continue
            if need_buff:
                keys = [x.get("key") for x in getattr(t, "buffs", [])]
                if need_buff not in keys:
                    continue
            try:
                t.hp = 0.0
                t.dead = True
                killed += 1
            except Exception:
                pass
        return killed > 0

    def _n_HealViaDamage(self, owner, node, ctx):
        """Vampire lifesteal on damage output: heal the owner by the
        actual damage dealt x heal ratio (bb vampire.heal_scale /
        heal_scale / heal_ratio), e.g. S\u8428\u5361\u5179\u5bbf\u4e3b\u767e\u592b\u957f
        heals 150% of damage dealt."""
        battle = self.battle
        if not battle:
            return True
        dmg = ctx.get("damage") or {}
        amount = _num(dmg.get("amount"), 0.0)
        if amount <= 0:
            return True
        bb = ctx.get("bb") or {}
        ratio = None
        for k in ("vampire.heal_scale", "heal_scale", "heal_ratio",
                  "hp_recovery_ratio", "value"):
            v = bb.get(k)
            if v is not None:
                ratio = _num(v, None)
                break
        if ratio is None:
            return True
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if tgt is None:
            tgt = owner
        battle.apply_heal(tgt, amount * ratio, source=owner)
        return True

    def _n_InverseDamage(self, owner, node, ctx):
        """Reflect (inverse) damage back at the attacker on ON_TAKE_DAMAGE
        (e.g. Mlynar T2: Kazimierz operators reflect Mlynar atk x 15% TRUE
        damage when attacked; enemy_ltnclo[shield] reflects a fixed value
        while the shield is up). Filters: attacker side (_sideMask) and
        attacker presence (_hasSource). _damageType / _damageTypeKey is the
        REFLECTED damage type; the value comes from the blackboard
        (_damageValueKey), falling back to the incoming hit."""
        battle = self.battle
        if not battle:
            return True
        dmg = ctx.get("damage") or {}
        if not dmg:
            return True
        bb = ctx.get("bb") or {}
        attacker = ctx.get("source")
        if node.get("_hasSource") and attacker is None:
            return False
        if attacker is not None:
            side = str(node.get("_sideMask") or "BOTH_ALLY_AND_ENEMY").upper()
            # simulator sides: operator=1 (ALLY), enemy=0 (ENEMY)
            a_side = int(getattr(attacker, "side", 0) or 0)
            if side == "ENEMY" and a_side != 0:
                return False
            if side == "ALLY" and a_side != 1:
                return False
            if side not in ("ENEMY", "ALLY", "BOTH_ALLY_AND_ENEMY", "BOTH",
                            "ALL"):
                return False
        key = node.get("_damageValueKey") or "value"
        if node.get("_fixValue"):
            amount = _num(bb.get(key), 0.0)
        else:
            amount = _num(bb.get(key), float(dmg.get("amount") or 0.0))
        if amount <= 0:
            return False
        if attacker is None:
            attacker = owner
        dmg_type_name = node.get("_damageType") or ""
        tkey = node.get("_damageTypeKey") or ""
        if tkey:
            dmg_type_name = bb.get(tkey, dmg_type_name)
        dmg_type = self._dmg_type(dmg_type_name)
        try:
            battle.apply_damage(attacker, amount, dmg_type, source=owner,
                                no_hit_recovery=True)
        except Exception:
            return False
        return True

    def _n_AdvancedApplyDamage(self, owner, node, ctx):
        battle = self.battle
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        targets = _targets(battle, node.get("_targetType"), owner,
                           source=ctx.get("source"), target=ctx.get("target"))
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        key = node.get("_atkScaleVar") or "atk_scale"
        scale = _num(bb.get(key), _num(node.get("_defaultAtkScale"), 1.0))
        dmg_type = self._dmg_type(node.get("_damageType"))
        base = _num(getattr(src, "attributes", None) and
                    src.attributes.get("atk"), 0.0)
        if node.get("_baseOnHostAtk") and owner is not src:
            base = _num(owner.attributes.get("atk"), base)
        amount = base * scale
        for t in targets:
            if t is not None and not getattr(t, "dead", False):
                # template-driven damage (DoT / fixed) does not trigger ????
                if dmg_type == DamageType.ELEMENT and \
                        (ctx.get("bb") or {}).get("_ep_break_phase"):
                    # ON_EP_BREAK_START burst damage: accumulate toward the
                    # next burst, bypassing the current burst cooldown lock
                    _bt = int((ctx.get("bb") or {}).get(
                        "_ep_break_type") or 0)
                    battle.buffs.add_ep_force(t, _bt, amount)
                else:
                    battle.apply_damage(t, amount, dmg_type, source=src,
                                        no_hit_recovery=True)
        return True

    def _n_NoSourceDamage(self, owner, node, ctx):
        battle = self.battle
        bb = ctx.get("bb") or {}
        key = node.get("_damageKey") or "damage"
        amount = _num(bb.get(key), 0.0)
        dmg_type = self._dmg_type(node.get("_damageType"))
        target = ctx.get("target") or owner
        if amount > 0 and target is not None and not getattr(
                target, "dead", False):
            # no-source damage (buff/DoT) does not trigger ????
            battle.apply_damage(target, amount, dmg_type, source=owner,
                                no_hit_recovery=True)
        return True

    def _n_ApplyDamageByFixedValue(self, owner, node, ctx):
        battle = self.battle
        bb = ctx.get("bb") or {}
        key = node.get("_damageValueKey")
        amount = _num(bb.get(key, node.get("_damageValue")),
                      node.get("_damageValue") or 0.0) if key else \
            _num(node.get("_damageValue"), 0.0)
        dmg_type = self._dmg_type(node.get("_damageType"))
        target = ctx.get("target") or owner
        if amount > 0 and target is not None and not getattr(
                target, "dead", False):
            # fixed-value buff damage does not trigger ????
            battle.apply_damage(target, amount, dmg_type, source=owner,
                                no_hit_recovery=True)
        return True

    def _n_HealViaMaxHpRatio(self, owner, node, ctx):
        battle = self.battle
        target = _source_unit(battle, node.get("_healTarget"), owner,
                              ctx.get("source"))
        bb = ctx.get("bb") or {}
        key = node.get("_ratioKey") or (
            "hp_ratio" if bb.get("hp_ratio") is not None else "ratio")
        ratio = _num(bb.get(key, node.get("_ratio")), 0.0)
        base = owner.max_hp
        if node.get("_getMaxHpFromTarget") and target is not None:
            base = target.max_hp
        if target is not None and ratio > 0:
            battle.apply_heal(target, base * ratio, source=owner,
                              ignore_heal_free=bool(
                                  node.get("_ignoreHealFree")))
        return True

    def _n_HealToken(self, owner, node, ctx):
        """Heal the owner's tokens (e.g. 豆苗 S1 治疗磐蟹).
        Heal amount = token maxHp x buff hp_ratio when _healByRatio."""
        battle = self.battle
        if not battle:
            return True
        src = _source_unit(battle, node.get("_sourceTarget"), owner,
                           ctx.get("source"))
        if src is None:
            src = owner
        bb = ctx.get("bb") or {}
        ratio = _num(bb.get("hp_ratio",
                            bb.get("ratio",
                                   node.get("_ratio"))), 0.0)
        for tok in list(battle.get_tokens()):
            if tok.dead or getattr(tok, "owner", None) is not src:
                continue
            if node.get("_healByRatio"):
                amount = float(tok.max_hp or 0.0) * ratio
            else:
                amount = ratio
            if amount > 0:
                battle.apply_heal(tok, amount, source=src,
                                  ignore_heal_free=bool(
                                      node.get("_ignoreHealFree")))
        return True

    def _n_CopyHealth(self, owner, node, ctx):
        """Copy the source's HP to the target (acstmb_s_1[copy_health]).
        _copyByRatio scales the copied value to the target's maxHp."""
        battle = self.battle
        if not battle:
            return True
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None or getattr(src, "dead", False):
            return True
        if node.get("_copyByRatio") and float(src.max_hp or 1.0) > 0:
            tgt.hp = float(src.hp) * float(tgt.max_hp or 0.0) / \
                float(src.max_hp)
        else:
            tgt.hp = float(src.hp)
        tgt.hp = max(0.0, min(float(tgt.max_hp or 0.0), tgt.hp))
        if tgt.hp <= 0:
            tgt.dead = True
        return True

    def _n_UnlockHiddenArea(self, owner, node, ctx):
        """Reveal the hidden/fog area (trap_xbhydr_mesh)."""
        battle = self.battle
        if not battle:
            return True
        battle._fog_view = {}
        try:
            battle.emit(battle.tick, "unlock_hidden_area",
                        {"unit": getattr(owner, "inst_id", None)})
        except Exception:
            pass
        return True

    def _n_Main15ForceSetBattleSpeedLevel(self, owner, node, ctx):
        """Mainline 15: force battle speed level (SetForceBattleSpeed)."""
        battle = self.battle
        if not battle:
            return True
        prts = getattr(battle, "prts", None)
        if prts is not None:
            prts.SetForceBattleSpeed(bool(node.get("_enable")))
        else:
            battle._main15_force_speed = bool(node.get("_enable"))
        return True

    def _n_Main15InsertPrtsAction(self, owner, node, ctx):
        """Mainline 15: insert a PRTS action into the script queue."""
        battle = self.battle
        if battle:
            try:
                battle.emit(battle.tick, "main15_insert_prts",
                            {"actionType": node.get("_actionType"),
                             "priority": node.get("_priority"),
                             "unit": getattr(owner, "inst_id", None)})
            except Exception:
                pass
            prts = getattr(battle, "prts", None)
            if prts is not None:
                return prts.insert_from_node(owner, node, ctx)
        return True

    def _n_Main15SkipPrtsAction(self, owner, node, ctx):
        """Mainline 15: skip the current PRTS action."""
        battle = self.battle
        if battle:
            try:
                battle.emit(battle.tick, "main15_skip_prts",
                            {"actionType": node.get("_actionType"),
                             "unit": getattr(owner, "inst_id", None)})
            except Exception:
                pass
            prts = getattr(battle, "prts", None)
            if prts is not None:
                return prts.SkipPrtsAction(node.get("_actionType"))
        return True

    def _n_Main15FilterPrtsLastSubAction(self, owner, node, ctx):
        """Mainline 15 gate: whether the last executed PRTS sub-action
        matches the requested type (and the main action type when given).
        ``_filterActionInstead`` inverts the sub-action match."""
        battle = self.battle
        want = node.get("_actionType") or ""
        prts = getattr(battle, "prts", None) if battle else None
        got = prts.last_sub_action if prts is not None else None
        main = node.get("_mainActionType")
        if main and prts is not None and prts.last_main_action != main:
            return True if node.get("_filterActionInstead") else False
        if not want:
            return True
        if node.get("_filterActionInstead"):
            return got != want
        return got == want

    def _n_Main15TryNextPrtsAction(self, owner, node, ctx):
        """Mainline 15: advance the PRTS sub-action pipeline
        (TryNextSubAction)."""
        battle = self.battle
        if battle:
            try:
                battle.emit(battle.tick, "prts_try_next",
                            {"unit": getattr(owner, "inst_id", None),
                             "force": bool(node.get("_forceNext"))})
            except Exception:
                pass
            prts = getattr(battle, "prts", None)
            if prts is not None:
                return prts.TryNextSubAction(
                    bool(node.get("_doNextWhenSuccess", True)),
                    bool(node.get("_forceNext", False)))
        return True

    def _n_Main15CreateBuffToPrts(self, owner, node, ctx):
        """Mainline 15: apply a buff to the PRTS enemy."""
        battle = self.battle
        if not battle:
            return True
        prts = getattr(battle, "prts", None)
        if prts is None:
            return True
        return prts.CreateBuffToPrts(node.get("_buffToPrts"),
                                     ctx.get("bb") or {})

    # ---- act35side gems (env_017_act35side, reused by main 15-18) ----
    def _act35(self):
        return getattr(self.battle, "act35", None) if self.battle else None

    def _act35_target(self, node, owner, ctx):
        battle = self.battle
        spec = node.get("_targetType")
        if str(spec).upper() in ("PROJECTILE_TRACETARGET",
                                 "PROJECTILE_TRACE_TARGET"):
            # the projectile's trace target is the hit target in the
            # projectile-hit buff context
            return ctx.get("target") or owner
        return _source_unit(battle, spec, owner,
                            ctx.get("source"), ctx.get("target"))

    def _n_Act35SideSummonGems(self, owner, node, ctx):
        m = self._act35()
        tgt = self._act35_target(node, owner, ctx)
        if m is None or tgt is None:
            return False
        return m.summon_gem(tgt.row, tgt.col,
                            node.get("_gemsType") or "Polluted")

    def _n_Act35SideSummonGemsInFourDirections(self, owner, node, ctx):
        m = self._act35()
        tgt = self._act35_target(node, owner, ctx)
        if m is None or tgt is None:
            return False
        return m.summon_gems_in_four_directions(
            tgt.row, tgt.col, node.get("_gemsType") or "Polluted")

    def _n_Act35SideSummonGemsInRange(self, owner, node, ctx):
        m = self._act35()
        tgt = self._act35_target(node, owner, ctx)
        if m is None or tgt is None:
            return False
        if node.get("_useInProjectile"):
            return False          # projectile-trace targeting not modeled
        return m.summon_gems_in_range(
            tgt.row, tgt.col,
            node.get("_gemsType") or "Polluted",
            range_id=node.get("_rangeId") or "",
            is_circle=bool(node.get("_isCircleRange")),
            radius=float(node.get("_rangeRadius") or 0.0),
            direction=node.get("direction") or "UP")

    def _n_Act35SideSummonLinkGem(self, owner, node, ctx):
        m = self._act35()
        tgt = self._act35_target(node, owner, ctx)
        if m is None or tgt is None:
            return False
        return m.summon_link_gem(tgt.row, tgt.col)

    def _n_Act35SideCheckIfOnGemsTile(self, owner, node, ctx):
        m = self._act35()
        tgt = self._act35_target(node, owner, ctx)
        if m is None or tgt is None:
            return False
        on = m.check_on_gems_tile(
            tgt.row, tgt.col, bool(node.get("_excludeLinkGems")))
        return (not on) if node.get("_checkNotOn") else on

    def _n_Act35SideCheckNotOnExcludedTile(self, owner, node, ctx):
        m = self._act35()
        tgt = self._act35_target(node, owner, ctx)
        if m is None or tgt is None:
            return True
        return m.check_not_on_excluded_tile(tgt.row, tgt.col)

    def _n_Act35SideAssignGemsCountToBlackboard(self, owner, node, ctx):
        m = self._act35()
        if m is None:
            return False
        cnt = m.gems_count(bool(node.get("_excludeLinkGems")))
        cap = node.get("_maxCount")
        mkc = node.get("_maxCountKey")
        if mkc:
            try:
                cap = (ctx.get("bb") or {}).get(mkc, cap)
            except Exception:
                pass
        try:
            cap = int(cap) if cap else 0
        except (TypeError, ValueError):
            cap = 0
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        bb[node.get("_blackboardKey") or "cnt"] = \
            min(cnt, cap) if cap > 0 else cnt
        return True

    def _n_Act35SideEliminateGems(self, owner, node, ctx):
        m = self._act35()
        tgt = self._act35_target(node, owner, ctx)
        if m is None or tgt is None:
            return False
        # the node has no direction field; the game uses the manager's
        # EliminateGemsByPositionAndDirection with the default facing (UP)
        return m.eliminate_gems(tgt.row, tgt.col, "UP")

    # ---- act31side pollute areas (13-04 hard boss) --------------------
    def _act31(self):
        return getattr(self.battle, "act31", None) if self.battle else None

    def _act31_source(self, node, owner, ctx):
        battle = self.battle
        return _source_unit(battle, node.get("_sourceType"), owner,
                            ctx.get("source"), ctx.get("target"))

    def _n_Act31SideAddAreaPollute(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        value = m.pollute_value(src, node.get("_addPolluteV"))
        return m.add_area_pollute(
            int(src.row), int(src.col), value,
            radius=float(node.get("_rangeRadius") or 0.0),
            need_check_tile=bool(node.get("_needCheckTile")))

    def _n_Act31SidePurifyAreaPollute(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        value = m.pollute_value(src, node.get("_addPolluteV"))
        return m.purify_area_pollute(int(src.row), int(src.col), value)

    def _n_Act31SideDeathPolluteTile(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        value = m.pollute_value(src, None)
        return m.death_pollute_tile(
            int(src.row), int(src.col),
            radius=float(node.get("_rangeRadius") or 1.0), value=value)

    def _n_Act31SideCheckInPolluteArea(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        return m.check_in_pollute_area(int(src.row), int(src.col))

    def _n_Act31SideCheckTileInWaterArea(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        return m.check_tile_in_water_area(int(src.row), int(src.col))

    def _n_Act31SideCheckRootTilePolluteValue(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        return m.check_root_tile_pollute_value(
            int(src.row), int(src.col),
            node.get("_condType") or "GE",
            int(node.get("_checkValue") or 0),
            bool(node.get("_needAreaPV")))

    def _n_Act31SideAssignAreaPolluteValueToBB(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        v = m.pollute.get((int(src.row), int(src.col)), 0)
        if node.get("_assignTilePV") is False and \
                node.get("_assignPVRatio") is False:
            area = m._area_at(int(src.row), int(src.col))
            v = max((m.pollute.get(p, 0) for p in area), default=0)
        bb[node.get("_polluteVKey") or "dynamic"] = v
        return True

    def _n_Act31SideTriggerRebuildAreas(self, owner, node, ctx):
        m = self._act31()
        if m is None:
            return False
        return m.rebuild_areas()

    def _n_Act31SidePumpFlowIntoOtherArea(self, owner, node, ctx):
        m = self._act31()
        src = self._act31_source(node, owner, ctx)
        if m is None or src is None:
            return False
        return m.pump_flow(int(src.row), int(src.col),
                           node.get("_rangeId") or "")

    def _n_Act31SideCheckPumpBackTileValid(self, owner, node, ctx):
        return True

    def _n_ModifyEnemyGraphicScale(self, owner, node, ctx):
        """Graphic scale on the owner (reborn shrink etc.)."""
        tgt = _source_unit(self.battle, node.get("_ownerType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None:
            return False
        scale = float(node.get("_scaleValue") or 0.0)
        cur = float(getattr(tgt, "_graphic_scale", 1.0) or 1.0)
        if node.get("_isAdd"):
            cur = cur + scale
        else:
            cur = scale
        if node.get("_needMax"):
            cur = min(cur, float(node.get("_maxValue") or cur))
        tgt._graphic_scale = cur
        return True

    def _n_ApplyFixedElementDamage(self, owner, node, ctx):
        """Fixed element damage: bb[valueKey] * bb[scaleKey] (optional)
        applied as ELEMENT damage to the target."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        try:
            value = float(bb.get(node.get("_damageValueKey") or "value",
                                 0.0) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        scale = 1.0
        sk = node.get("_damageScaleKey")
        if sk:
            try:
                scale = float(bb.get(sk, 1.0) or 1.0)
            except (TypeError, ValueError):
                scale = 1.0
        amount = value * scale
        if amount <= 0:
            return False
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None or getattr(tgt, "dead", False):
            return False
        ep = {"SANITY": 0, "WATER": 1, "FIRE": 2, "DARK": 3}.get(
            str(node.get("_elementType") or "").upper(), 0)
        battle.add_ep(tgt, ep, amount)
        battle.emit(battle.tick, "element_damage_fixed",
                    {"unit": getattr(tgt, "inst_id", None),
                     "ep": ep, "amount": round(amount, 3)})
        return True

    def _n_CheckBuffAttributeModifierChanged(self, owner, node, ctx):
        """Converter gate: whether the source's attribute changed since the
        buff last mirrored it into its FINAL_ADDITION modifier."""
        battle = self.battle
        if not battle:
            return True
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if src is None:
            return True
        stat = {"ATK": "atk", "DEF": "def", "MAX_HP": "maxHp",
                "MOVE_SPEED": "moveSpeed",
                "ATTACK_SPEED": "attackSpeed"}.get(
                    str(node.get("_sourceAttributeType") or "").upper())
        if not stat:
            return True
        cur = getattr(src.attributes, "get", None)(stat) \
            if src.attributes is not None else None
        try:
            cur = float(cur or 0.0)
        except (TypeError, ValueError):
            cur = 0.0
        bb = ctx.get("bb") or {}
        entry = bb.get("_buff_entry") or {}
        cache_key = "_conv_last_" + stat
        last = bb.get(cache_key)
        if last is not None and abs(float(last) - cur) < 1e-9:
            return False
        bb[cache_key] = cur
        # mirror the source value into the buff's FINAL_ADDITION modifier
        bstat = {"ATK": "atk", "DEF": "def", "MAX_HP": "maxHp"}.get(
            str(node.get("_buffAttributeType") or "").upper(), stat)
        if isinstance(entry, dict) and entry.get("key"):
            entry["stat"] = bstat
            entry["final_add"] = cur
            entry["_converter_dirty"] = True
        return True

    def _n_LegionModeOnlyAssignCardCntToBB(self, owner, node, ctx):
        """Count cards matching _cardId (in hand when _onlyInHand) and
        assign to the blackboard _cardKey."""
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        pool = battle._legion_hand if node.get("_onlyInHand") else (
            list(battle._legion_hand) + list(battle._legion_pending))
        card = node.get("_cardId") or ""
        cnt = sum(1 for k in pool if str(k) == card)
        bb[node.get("_cardKey") or "cnt"] = cnt
        return True

    # ---- WDSLM stands (water-world spectators) ------------------------
    def _wdslm_stands(self, ability_name):
        battle = self.battle
        if battle is None:
            return []
        return battle._wdslm_stands.get(ability_name) or []

    def _n_RegisterAsStand(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        stand = _source_unit(battle, node.get("_source"), owner,
                             ctx.get("source"), ctx.get("target")) or owner
        host_name = node.get("_hostAbilityName") or "standRegisterList"
        if node.get("useIdToFindHost"):
            host_id = node.get("hostId") or ""
            host = None
            for e in battle.get_enemies():
                if not getattr(e, "dead", False) and \
                        (e.enemy_key or "") == host_id:
                    host = e
                    break
            if host is None:
                return False
        pool = battle._wdslm_stands.setdefault(host_name, [])
        if stand not in pool:
            pool.append(stand)
        battle.emit(battle.tick, "wdslm_stand_registered",
                    {"stand": getattr(stand, "inst_id", None),
                     "ability": host_name})
        return True

    def _n_CheckHasStands(self, owner, node, ctx):
        return bool(self._wdslm_stands(
            node.get("_abilityName") or "standRegisterList"))

    def _n_RunActionsToWdslmAbilityTarget(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        actions = node.get("_actionsToTarget") or []
        if not actions:
            return True
        ability = node.get("_abilityName") or "standRegisterList"
        at = str(node.get("_actionTargetType") or "").upper()
        if at in ("HOST", "SELF_WITH_HOST_AS_SOURCE"):
            targets = [owner]
        else:
            stands = self._wdslm_stands(ability)
            targets = list(stands)
            if at == "STANDS_EXCEPT_SELF":
                targets = [s for s in targets if s is not owner]
        if not targets:
            return False
        ran = 0
        for t in targets:
            if t is None or getattr(t, "dead", False):
                continue
            tctx = dict(ctx)
            tctx["target"] = t
            # keep the original buff owner as BUFF_OWNER; each stand is the
            # TARGET of the sub-actions
            self.run_actions(owner, actions, tctx, 0)
            ran += 1
        return ran > 0

    def _n_EqualizeTargetHpRatio(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_source"), owner,
                           ctx.get("source"), ctx.get("target"))
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None or getattr(tgt, "dead", False):
            return False
        if node.get("_useSourceHpRatio") and src is not None:
            mx = float(getattr(src, "max_hp", 0.0) or 0.0)
            ratio = float(getattr(src, "hp", 0.0) or 0.0) / mx \
                if mx > 0 else float(node.get("_hpRatio") or 0.5)
        else:
            ratio = float(node.get("_hpRatio") or 0.5)
        tgt.hp = float(getattr(tgt, "max_hp", 0.0) or 0.0) * ratio
        battle.emit(battle.tick, "wdslm_hp_equalized",
                    {"target": getattr(tgt, "inst_id", None),
                     "ratio": round(ratio, 4)})
        return True

    # ---- sandbox trace / toast / reward marks -------------------------
    def _n_SandboxMarkEntityNotReward(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        tgt._sandbox_not_reward = True
        return True

    def _n_SandboxShowToast(self, owner, node, ctx):
        if self.battle:
            self.battle.emit(self.battle.tick, "sandbox_toast",
                             {"toastKey": node.get("_toastKey"),
                              "lastTime": node.get("_lastTime")})
        return True

    def _n_SandboxEnableTraceTarget(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if node.get("_enabled"):
            tgt._sandbox_trace_enabled = True
            tgt._whole_trace = bool(node.get("_wholeTraceInstead"))
            tgt._trace_tile_instead = bool(node.get("_traceTileInstead"))
        else:
            tgt._sandbox_trace_enabled = False
            tgt._trace_target = None
            tgt._trace_pos = None
        return True

    def _n_SandboxCheckEnemyCanTraceTarget(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        has = (getattr(tgt, "_trace_target", None) is not None or
               getattr(tgt, "_trace_pos", None) is not None)
        if node.get("_checkHasTraceTarget"):
            return has
        if node.get("_checkHasTraceTargetNow"):
            return has
        return True

    def _n_SandboxSetEnemyTraceTarget(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None or src is None:
            return False
        if not node.get("_force") and \
                getattr(tgt, "_trace_target", None) is not None:
            return False
        tgt._trace_target = src
        return True

    def _n_SandboxMarkTraceReached(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        tgt._trace_reached = True
        return True

    def _n_SandboxIsRushEnemyMode(self, owner, node, ctx):
        return bool(getattr(self.battle, "_sandbox_rush_mode", False))

    def _n_SandboxIsRushEnemy(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        return bool(getattr(tgt, "_sandbox_rush", False))

    def _n_SandboxDisableClickCharacterInfo(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        tgt._sandbox_disable_click_info = bool(node.get("_enabled"))
        return True

    # ---- DurBus passengers -------------------------------------------
    def _n_DurBusAbilityCheckPassengers(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        pool = battle._durbus_passengers.setdefault(
            node.get("_abilityName") or "Bus", [])
        if node.get("_markCurrentPassengers"):
            for p in pool:
                p._durbus_marked = True
        return bool(pool)

    def _n_DurBusAbilityKillPassengers(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        pool = battle._durbus_passengers.setdefault(
            node.get("_abilityName") or "Bus", [])
        if not pool:
            return False
        if node.get("_killLastPassenger"):
            victims = [pool.pop()]
        else:
            victims, pool[:] = list(pool), []
        for p in victims:
            if p is not None and not getattr(p, "dead", False):
                try:
                    from .consts import DamageType
                    battle.apply_damage(p, 10 ** 9, DamageType.TRUE,
                                        source=None)
                except Exception:
                    pass
        battle.emit(battle.tick, "durbus_kill_passengers",
                    {"count": len(victims)})
        return True

    def _n_DurBusAbilityReleasePassenger(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        pool = battle._durbus_passengers.setdefault(
            node.get("_abilityName") or "Bus", [])
        if not pool:
            return False
        if node.get("_releaseLastOnly"):
            released = [pool.pop()]
        else:
            released, pool[:] = list(pool), []
        battle.emit(battle.tick, "durbus_release_passengers",
                    {"count": len(released),
                     "instIds": [getattr(p, "inst_id", None)
                                 for p in released]})
        return True

    # ---- sandbox v3 mode / weather / resources / stats ----------------
    def _n_SandboxV3ChangeWeather(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        key = node.get("_weatherKey") or "weatherId"
        weather = (ctx.get("bb") or {}).get(key)
        if node.get("_enable"):
            battle._sandbox_weather = str(weather) if weather else None
        battle.emit(battle.tick, "sandbox_weather",
                    {"weather": battle._sandbox_weather})
        return True

    def _n_SandboxCheckCurrentMode(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return True
        if node.get("_checkWeatherType"):
            want = node.get("_sandboxWeatherType")
            if want and battle._sandbox_weather != want:
                return False
        if node.get("_checkNodeType"):
            want = node.get("_sandboxNodeTypeV2")
            if want and battle._sandbox_node_type != want:
                return False
        if node.get("_checkSeasonType"):
            want = node.get("_sandboxSeasonTypeV2")
            if want and battle._sandbox_season != want:
                return False
        if node.get("_checkBuildMode"):
            if not battle._sandbox_build_mode:
                return False
        return True

    def _n_SandboxV3ModifyBuffStat(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        stat = str(node.get("_statType") or "PROSPERITY")
        try:
            value = float(node.get("_value") or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        vk = node.get("_valueBbKey")
        if vk:
            try:
                value = float((ctx.get("bb") or {}).get(vk, value) or 0.0)
            except (TypeError, ValueError):
                pass
        if str(node.get("_formula") or "ADDITION").upper() == "MULTIPLIER":
            battle._sandbox_stats[stat] = \
                float(battle._sandbox_stats.get(stat, 0.0)) * value
        else:
            battle._sandbox_stats[stat] = \
                float(battle._sandbox_stats.get(stat, 0.0)) + value
        return True

    def _n_SandboxV3RemoveBuffStat(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        battle._sandbox_stats = {}
        return True

    def _n_SandboxCollectPackedRes(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        packed = float(getattr(tgt, "_packed_res", 0.0) or 0.0)
        battle._sandbox_res = float(battle._sandbox_res or 0.0) + packed
        tgt._packed_res = 0.0
        return True

    def _n_SandboxCheckHasResource(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        res = float(getattr(tgt, "_packed_res", 0.0) or 0.0)
        if node.get("_checkFull"):
            return res >= float(getattr(tgt, "_packed_res_max", 1.0) or 1.0)
        return res > 0

    # ---- act49 side (character tile / word) ---------------------------
    def _n_Act49SideWriteCharacter(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._act49_tile_types[(int(tgt.row), int(tgt.col))] = \
            node.get("_tileType") or "Pure"
        return True

    def _n_Act49SideCheckCharacterTileType(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        got = battle._act49_tile_types.get((int(tgt.row), int(tgt.col)))
        if node.get("_checkAnyTile"):
            return got is not None
        return got == node.get("_tileType")

    def _n_Act49SideCheckWordTileBuildable(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        try:
            t = battle.map.tile(int(tgt.row), int(tgt.col))
            return t is not None and t.passable(0)
        except Exception:
            return False

    def _n_Act49SideSetEntityAnimatorColor(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        color = node.get("color") or {}
        tgt._animator_color = {
            "r": color.get("r", 0), "g": color.get("g", 0),
            "b": color.get("b", 0), "a": color.get("a", 0)}
        return True

    # ---- sandbox depth: items / animal / status records ----------------
    def _n_SandboxV3ManuallyAddItems(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        item_key = node.get("_itemIdsBbKey") or "item_id"
        cnt_key = node.get("_itemCntBbKey") or "item_count"
        item_id = bb.get(item_key)
        if not item_id and not node.get("_allowEmpty"):
            return False
        try:
            cnt = int(bb.get(cnt_key, 1) or 1)
        except (TypeError, ValueError):
            cnt = 1
        if item_id:
            battle._sandbox_items[item_id] = \
                battle._sandbox_items.get(item_id, 0) + max(0, cnt)
        battle.emit(battle.tick, "sandbox_items_add",
                    {"item": item_id, "count": cnt, "reason": node.get(
                        "_reason")})
        return True

    def _n_SandboxEntityDropItem(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        carried = dict(getattr(tgt, "_sandbox_items", {}) or {})
        for k, v in carried.items():
            battle._sandbox_items[k] = battle._sandbox_items.get(k, 0) + v
        tgt._sandbox_items = {}
        battle.emit(battle.tick, "sandbox_entity_drop",
                    {"unit": getattr(tgt, "inst_id", None),
                     "items": carried})
        return True

    def _n_SandboxRecordUnitState(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        key = node.get("_additionHpRatioKey") or "addition_hp_ratio"
        mx = float(getattr(tgt, "max_hp", 0.0) or 0.0)
        bb[key] = (float(getattr(tgt, "hp", 0.0) or 0.0) / mx) \
            if mx > 0 else 0.0
        battle._sandbox_unit_states[getattr(tgt, "inst_id", 0)] = {
            "hp": float(getattr(tgt, "hp", 0.0) or 0.0),
            "row": int(getattr(tgt, "row", 0) or 0),
            "col": int(getattr(tgt, "col", 0) or 0),
        }
        return True

    def _n_SandboxRecordUniEnemyStatus(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._sandbox_unit_states[getattr(tgt, "inst_id", 0)] = {
            "hp": float(getattr(tgt, "hp", 0.0) or 0.0),
            "row": int(getattr(tgt, "row", 0) or 0),
            "col": int(getattr(tgt, "col", 0) or 0),
        }
        return True

    def _n_SandboxSetUniEnemyStatus(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        st = battle._sandbox_unit_states.get(getattr(tgt, "inst_id", 0))
        if st:
            tgt.hp = st["hp"]
            tgt.row, tgt.col = st["row"], st["col"]
        return True

    def _n_SandboxV3IsCatchedAnimal(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        caught = bool(getattr(tgt, "_sandbox_caught", False))
        if node.get("_checkIsLegend"):
            legend = bool(getattr(tgt, "_sandbox_legend", False))
            return caught and (legend == bool(node.get("_isLegend")))
        return caught

    def _n_SandboxV3CheckIsAnimalEnemy(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        return bool(getattr(tgt, "_sandbox_animal", False))

    def _n_SandboxV3CatchAnimalEnemy(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._sandbox_caught = True
        return True

    def _n_SandboxV3SkipEnemyDropItems(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._sandbox_skip_drop = True
        return True

    def _n_SandboxV3CheckTrapType(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        want = node.get("_trapType")
        tk = node.get("_trapTypeKey")
        if tk:
            want = (ctx.get("bb") or {}).get(tk, want)
        return getattr(tgt, "_trap_type", None) == want

    def _n_SandboxV3ForceUnitDirty(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._sandbox_dirty = True
        return True

    def _n_SandboxV3TryMaintainService(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        battle.emit(battle.tick, "sandbox_maintain_service",
                    {"unit": getattr(owner, "inst_id", None)})
        return True

    def _n_SandboxV3AssignRecipeInfoToBb(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        key = node.get("_prosperityKey") or "prosperity_service"
        bb[key] = float(battle._sandbox_stats.get("PROSPERITY", 0.0) or 0.0)
        return True

    # ---- remaining playable-content nodes (full-bundle scan) ----------
    def _n_HasCharacterInCertainDirection(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        dr, dc = {"UP": (-1, 0), "DOWN": (1, 0),
                  "LEFT": (0, -1), "RIGHT": (0, 1)}.get(
                      str(node.get("_direction") or "").upper(), (0, 0))
        r, c = int(tgt.row) + dr, int(tgt.col) + dc
        if battle.map.idx(r, c) < 0:
            return False
        want_side = int(getattr(tgt, "side", 0) or 0) \
            if node.get("_checkSameSide") else None
        for u in (list(battle.get_operators()) + list(battle.get_enemies())
                  + list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if (int(u.row), int(u.col)) != (r, c):
                continue
            if node.get("_excludeTrapCategory") and \
                    getattr(u, "token_id", None) is not None:
                continue
            if want_side is not None and \
                    int(getattr(u, "side", 0) or 0) != want_side:
                continue
            return True
        return False

    def _n_Act49sideWriteCharacterBasedOnAnchorPos(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._act49_tile_types[(int(tgt.row), int(tgt.col))] = \
            node.get("_tileType") or "Anchor"
        return True

    def _n_Act49sideChargePrintingProgress(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        battle._act49_print_progress = float(
            battle._act49_print_progress or 0.0) + \
            float(node.get("_chargeValue") or 0.0)
        return True

    def _n_AssignManhattanDistanceToBB(self, owner, node, ctx):
        battle = self.battle
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"), ctx.get("target"))
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None:
            return False
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        bb[node.get("_blackboardKey") or "distance"] = \
            abs(int(src.row) - int(tgt.row)) + abs(int(src.col) - int(tgt.col))
        return True

    def _n_RacingEnemyRecover(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt.hp = float(getattr(tgt, "max_hp", 0.0) or 0.0)
        return True

    def _n_SwitchRacingMode(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._racing_mode = node.get("_racingMode") or "Racing"
        return True

    def _n_SwitchSubSpineConfig(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        idx = node.get("_index")
        k = node.get("_indexKey")
        if k:
            idx = (ctx.get("bb") or {}).get(k, idx)
        if node.get("_defaultToRandom") and idx in (None, -1):
            try:
                import random as _r
                idx = _r.randrange(3)
            except Exception:
                idx = 0
        tgt._sub_spine_index = int(idx if idx not in (None, -1) else 0)
        return True

    def _n_AssignSubSpineConfigIndexToBB(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        bb[node.get("_indexKey") or "spine"] = int(
            getattr(tgt, "_sub_spine_index", 0) or 0)
        return True

    def _n_SummonEnemyByAbilitySelector(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        keys = node.get("_enemyKeys") or []
        bb = ctx.get("bb") or {}
        bk = node.get("_getEnemyKeysFromBB")
        if bk and bb.get(bk):
            keys = [str(bb[bk])]
        if tgt is None or not keys:
            return False
        count = max(1, int(node.get("_summonCount") or 1))
        spawned = 0
        for i in range(count):
            key = keys[i % len(keys)]
            try:
                e = battle.spawn_enemy_directive(
                    key, int(tgt.row), int(tgt.col), route_index=0)
                if e is not None:
                    spawned += 1
            except Exception:
                pass
        return spawned > 0

    def _n_RO4DLC2TriggerBossSealTileSkill(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        bb = ctx.get("bb") or {}
        start = int(bb.get(node.get("_startColKey") or "startCol", 0) or 0)
        end = int(bb.get(node.get("_endColKey") or "endCol", start) or start)
        for r in range(battle.map.rows):
            for c in range(max(0, min(start, end)),
                           min(battle.map.cols, max(start, end) + 1)):
                battle._ro4dlc2_seal_tiles.add((r, c))
        battle.emit(battle.tick, "ro4dlc2_seal_tiles",
                    {"startCol": start, "endCol": end})
        return True

    def _n_SwitchDynamicBuffTileModeUseAbilitySelector(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        r, c = int(tgt.row), int(tgt.col)
        if str(node.get("_operation") or "INDEX").upper() == "INDEX":
            battle._tile_modes[(r, c)] = int(node.get("_modeIndex") or 0)
        else:
            battle._tile_modes.pop((r, c), None)
        return True

    def _n_Act49sideSsttzSacrificeEnemy(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None or getattr(tgt, "dead", False):
            return False
        from .consts import DamageType
        battle.apply_damage(tgt, 10 ** 9, DamageType.TRUE, source=None)
        return True

    # ---- next batch: balloon / magic circuit / friction / progress ----
    def _n_Act47SideAddForceToBalloon(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        try:
            force = float(node.get("_force") or 0.0)
        except (TypeError, ValueError):
            force = 0.0
        fk = node.get("_forceKey")
        if fk:
            try:
                force = float((ctx.get("bb") or {}).get(fk, force) or 0.0)
            except (TypeError, ValueError):
                pass
        if node.get("_isMinus"):
            force = -force
        cur = float(getattr(tgt, "_balloon_force", 0.0) or 0.0)
        if node.get("_isUpForce"):
            tgt._balloon_force_up = cur + force
        else:
            tgt._balloon_force = cur + force
        battle.emit(battle.tick, "balloon_force",
                    {"unit": getattr(tgt, "inst_id", None),
                     "force": round(force, 3), "up": bool(
                         node.get("_isUpForce"))})
        return True

    def _n_RoguelikeFilterCharacterInCandleHolder(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._candle_holder = True
        battle.emit(battle.tick, "roguelike_candle_holder",
                    {"unit": getattr(tgt, "inst_id", None)})
        return True

    def _n_RegistProgressBuff(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        battle._progress_buffs.append(getattr(owner, "inst_id", 0))
        return True

    def _n_ClearFirstBuffBlackboardByKey(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        key = node.get("_buffKey")
        for b in list(getattr(tgt, "buffs", None) or []):
            if key and b.get("key") != key:
                continue
            bb = b.get("blackboard")
            if isinstance(bb, dict):
                for k in [k for k in bb
                          if not str(k).startswith("_")]:
                    bb.pop(k, None)
            return True
        return False

    def _n_SetMagicCircuitLikeObstacleInRange(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        val = bool(node.get("_isLikeObstacle"))
        shape = []
        rid = node.get("_rangeId")
        if rid:
            try:
                from .battle import _load_range_table
                rt = _load_range_table()
                shape = [(int(g.get("row", 0)), int(g.get("col", 0)))
                         for g in (rt.get(rid) or {}).get("grids") or []]
            except Exception:
                shape = []
        if not shape:
            shape = getattr(tgt, "range_shape", None) or [(0, 0)]
        cells = {(int(tgt.row) + dr, int(tgt.col) + dc)
                 for dr, dc in shape}
        hit = 0
        for u in (list(battle.get_operators()) + list(battle.get_enemies())
                  + list(battle.get_tokens())):
            if (int(u.row), int(u.col)) in cells:
                u._magic_circuit_obstacle = val
                hit += 1
        return hit > 0

    def _n_UpdateFrictionFactor(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        if node.get("_restoreFrictionFactor"):
            tgt._friction_factor = float(
                getattr(tgt, "_base_friction_factor", 1.0) or 1.0)
        else:
            if not hasattr(tgt, "_base_friction_factor"):
                tgt._base_friction_factor = float(
                    getattr(tgt, "_friction_factor", 1.0) or 1.0)
            tgt._friction_factor = float(node.get("_frictionFactor") or 0.0)
        return True

    def _n_EnableEffectTransform(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._effect_transform = bool(node.get("_enabled"))
        return True

    def _n_EnemyDurcarCheckOverlapWithHighland(self, owner, node, ctx):
        tgt = _source_unit(self.battle, "BUFF_OWNER", owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        try:
            t = self.battle.map.tile(int(tgt.row), int(tgt.col))
            return t is not None and str(t.height_type or "").upper() in \
                ("1", "HIGHLAND", "HIGH")
        except Exception:
            return False

    def _n_FaceToLOrRViaMoreTargets(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_ownerType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        left = right = 0
        for u in (list(battle.get_operators()) + list(battle.get_enemies())
                  + list(battle.get_tokens())):
            if getattr(u, "dead", False) or u is tgt:
                continue
            dc = int(u.col) - int(tgt.col)
            if dc < 0:
                left += 1
            elif dc > 0:
                right += 1
        tgt._facing = "RIGHT" if right >= left else "LEFT"
        return True

    def _n_Act29SideSwitchCurretnAudioType(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        battle.emit(battle.tick, "act29_audio_switch",
                    {"mute": bool(node.get("_muteAudio")),
                     "typeKey": node.get("_typeKey")})
        return True

    def _n_ModifyEnemySpUIFlag(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._sp_ui_show = bool(node.get("_isShow"))
        return True

    def _n_AdjustEnemyHeightToRootTile(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        try:
            t = self.battle.map.tile(int(tgt.row), int(tgt.col))
            tgt._height = getattr(t, "height_type", None)
        except Exception:
            tgt._height = None
        return True

    def _n_AssignMcgrafTile(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        opts = node.get("_options") or {}
        want_build = str(opts.get("buildableType") or "").upper()
        for r in range(battle.map.rows):
            for c in range(battle.map.cols):
                t = battle.map.tile(r, c)
                if t is None:
                    continue
                if want_build == "MELEE" and t.buildable_type != 1:
                    continue
                if want_build == "RANGED" and t.buildable_type != 2:
                    continue
                if not t.passable(0):
                    continue
                bb = ctx.get("bb")
                if not isinstance(bb, dict):
                    bb = {}
                bb["mcgraf_tile_row"] = r
                bb["mcgraf_tile_col"] = c
                return True
        return False

    def _n_AssignElectricWorkCountToManager(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        work = str(node.get("_workType") or "WOOD")
        try:
            cnt = int(node.get("count") or 0)
        except (TypeError, ValueError):
            cnt = 0
        battle._electric_work[work] = battle._electric_work.get(work, 0) + cnt
        return True

    def _n_CoopBoatGainScore(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        try:
            score = float(node.get("_score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if node.get("_loadFromBlackboard"):
            try:
                score = float((ctx.get("bb") or {}).get(
                    node.get("_scoreKey") or "score", score) or 0.0)
            except (TypeError, ValueError):
                pass
        if node.get("isMin"):
            score = -abs(score)
        battle._coop_scores["boat"] = \
            float(battle._coop_scores.get("boat", 0.0) or 0.0) + score
        return True

    def _n_AssignUnionFindMemberCntToBB(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        # 4-connected same-type units around the target (union-find count)
        kind = (getattr(tgt, "enemy_key", None) or
                getattr(tgt, "token_id", None) or "unit")
        seen, stack = {(int(tgt.row), int(tgt.col))}, \
            [(int(tgt.row), int(tgt.col))]
        by_pos = {}
        for u in (list(battle.get_operators()) + list(battle.get_enemies())
                  + list(battle.get_tokens())):
            if not getattr(u, "dead", False):
                by_pos[(int(u.row), int(u.col))] = u
        while stack:
            r, c = stack.pop()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (r + dr, c + dc)
                u = by_pos.get(nb)
                if u is None or nb in seen:
                    continue
                ukind = (getattr(u, "enemy_key", None) or
                         getattr(u, "token_id", None) or "unit")
                if ukind == kind:
                    seen.add(nb)
                    stack.append(nb)
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        bb[node.get("_key") or "count"] = len(seen)
        return True

    # ---- legion / gather / roguelike batch ----------------------------
    def _n_RistarMove(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, "BUFF_OWNER", owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        keys = set(node.get("_tileKeyList") or [])
        best = None
        best_d = 1e9
        for r in range(battle.map.rows):
            for c in range(battle.map.cols):
                t = battle.map.tile(r, c)
                if t is None or t.tile_key not in keys:
                    continue
                d = abs(r - int(tgt.row)) + abs(c - int(tgt.col))
                if d < best_d:
                    best, best_d = (r, c), d
        if best is None:
            return False
        tgt.row, tgt.col = best
        tgt.pos_x, tgt.pos_y = float(best[1]), float(best[0])
        return True

    def _n_SpawnCharacterByUid(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        bb = ctx.get("bb") or {}
        uid = bb.get("uid") or bb.get("char_id")
        if not uid:
            return False
        row, col = int(tgt.row), int(tgt.col)
        if node.get("_getPosViaBB"):
            try:
                row = int(bb.get("row", row))
                col = int(bb.get("col", col))
            except (TypeError, ValueError):
                pass
        try:
            e = battle.spawn_enemy_directive(str(uid), row, col,
                                             route_index=0)
        except Exception:
            return False
        return e is not None

    def _n_HostKillSummonedApopsisEnemy(self, owner, node, ctx):
        battle = self.battle
        host = _source_unit(battle, node.get("_source"), owner,
                            ctx.get("source"), ctx.get("target")) or owner
        if host is None:
            return False
        killed = 0
        for e in list(battle.get_enemies()):
            if getattr(e, "dead", False):
                continue
            src = getattr(e, "summon_source", None)
            if src is host:
                battle.apply_damage(e, 10 ** 9, DamageType.TRUE,
                                    source=None)
                killed += 1
        return killed > 0

    def _n_LegionModeOnlyModifyMaxProfessionBuffCnt(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        if node.get("_resetToDefault"):
            battle._legion_profession_buff_cnt = 0
        else:
            battle._legion_profession_buff_cnt = int(getattr(
                battle, "_legion_profession_buff_cnt", 0) or 0) + \
                int(node.get("_addValue") or 0)
        return True

    def _n_LegionModeOnlyCheckHandCardNotFull(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return True
        return len(battle._legion_hand) < \
            int(getattr(battle, "_legion_hand_max", 8) or 8)

    def _n_LegionModeOnlyAssignSpecifiedProfessionStackCntToBB(
            self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        prof = str(node.get("_queryProfessionCategory") or "").upper()
        cnt = int(getattr(battle, "_legion_profession_counts", {}).get(
            prof, 0) or 0)
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        bb[node.get("_assignBlackboardKey") or "cnt"] = cnt
        return True

    def _n_InitForces(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        bb = ctx.get("bb") or {}
        tgt._forces = {
            "passing": float(bb.get(node.get("_passBallForceKey") or
                                    "passing_force", 0.0) or 0.0),
            "slapshot": float(bb.get(node.get("_slapShotForceKey") or
                                     "slapshot_force", 0.0) or 0.0),
            "clearance": float(bb.get(node.get("_clearanceForceKey") or
                                      "clearance_force", 0.0) or 0.0),
        }
        return True

    def _n_ManageSbell2AttachListenerAbility(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_ownerType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        battle.emit(battle.tick, "sbell2_listener",
                    {"unit": getattr(tgt, "inst_id", None),
                     "ability": node.get("_abilityName"),
                     "s1": bool(node.get("_isS1RelatedOperate")),
                     "s2": bool(node.get("_isS2RelatedOperate"))})
        return True

    def _n_GatherRegisterListener(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._gather_listeners.append(
            (tgt, str(node.get("_listenerType") or "ENEMY")))
        return True

    def _n_GatherRemoveListener(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._gather_listeners = [
            (u, t) for (u, t) in battle._gather_listeners if u is not tgt]
        return True

    def _n_RebuildCharacterOnTileInRange(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        shape = []
        rid = node.get("_rangeId")
        if rid:
            try:
                from .battle import _load_range_table
                rt = _load_range_table()
                shape = [(int(g.get("row", 0)), int(g.get("col", 0)))
                         for g in (rt.get(rid) or {}).get("grids") or []]
            except Exception:
                shape = []
        if not shape:
            shape = [(0, 0)]
        cells = {(int(tgt.row) + dr, int(tgt.col) + dc)
                 for dr, dc in shape}
        hit = 0
        for u in (list(battle.get_operators()) + list(battle.get_tokens())):
            if getattr(u, "dead", False):
                continue
            if (int(u.row), int(u.col)) not in cells:
                continue
            if node.get("_createBuff"):
                bd = node.get("_buff") or {}
                if bd.get("buffKey"):
                    try:
                        from .buff_templates import materialise_buff
                        entry = materialise_buff(battle, u, bd,
                                                 ctx.get("bb") or {}, owner)
                        if entry:
                            battle.add_buff(u, entry)
                    except Exception:
                        pass
            hit += 1
        return hit > 0

    def _n_HalfIdleCheckHasCertainTargetUseAbilitySelector(
            self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        exclude = None
        if node.get("_excludeTarget"):
            exclude = _source_unit(battle, node.get("_excludeTargetType"),
                                   owner, ctx.get("source"),
                                   ctx.get("target"))
        count = 0
        for u in (list(battle.get_operators()) + list(battle.get_enemies())
                  + list(battle.get_tokens())):
            if getattr(u, "dead", False) or u is exclude or u is tgt:
                continue
            count += 1
        floor = float(node.get("_floorTargetCnt") or 1.0)
        fk = node.get("_floorTargetCntKey")
        if fk:
            try:
                floor = float((ctx.get("bb") or {}).get(fk, floor) or 1.0)
            except (TypeError, ValueError):
                pass
        return count >= floor

    # ---- roguelike buff nodes (user scope: buffs count, levels don't) --
    def _n_RoguelikeLogExpUseSerializedTrapID(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        try:
            exp = float((ctx.get("bb") or {}).get(
                node.get("_expKey") or "toolgun_exp_1", 0.0) or 0.0)
        except (TypeError, ValueError):
            exp = 0.0
        trap = node.get("_trapID") or "trap"
        battle._rogue_exp_use[trap] = \
            float(battle._rogue_exp_use.get(trap, 0.0) or 0.0) + exp
        return True

    def _n_RoguelikeCheckZoneType(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return True
        return battle._rogue_zone_type == node.get("_zoneType")

    def _n_RoguelikeShowToastRL04(self, owner, node, ctx):
        return self._rogue_toast(node, "rl04")

    def _n_RoguelikeShowToastRL05(self, owner, node, ctx):
        return self._rogue_toast(node, "rl05")

    def _n_RoguelikeShowToastRL06(self, owner, node, ctx):
        return self._rogue_toast(node, "rl06")

    def _rogue_toast(self, node, kind):
        battle = self.battle
        if not battle:
            return True
        fkey = f"_toastTypeRL{kind[-2:]}"
        battle.emit(battle.tick, f"roguelike_toast_{kind}",
                    {"toastType": node.get(fkey, node.get("_toastType")),
                     "lastTime": node.get("_lastTime")})
        return True

    def _n_RollRogueDice(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        mx = max(1, int(node.get("_maxVal") or 12))
        value = battle.rng.next(mx) + 1
        battle._rogue_dice_log.append(value)
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        bb["dice"] = value
        battle.emit(battle.tick, "rogue_dice", {"value": value, "max": mx})
        return True

    def _n_RoguelikeDuelModeCheckStage(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return True
        return battle._rogue_duel_stage == node.get("gameStage")

    def _n_IsRogueLikeBoss(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        return bool(getattr(tgt, "_roguelike_boss", False))

    def _n_RoguelikeInheritEnemyHp(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        mx = float(getattr(tgt, "max_hp", 0.0) or 0.0)
        tgt._roguelike_hp_ratio = (
            float(getattr(tgt, "hp", 0.0) or 0.0) / mx) if mx > 0 else 0.0
        return True

    def _n_RoguelikeDeifyModeCheckStage(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return True
        return battle._rogue_deify_stage == node.get("gameStage")

    def _n_RoguelikeFilterFragmentCarryChar(self, owner, node, ctx):
        src = _source_unit(self.battle, node.get("_source"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        src._fragment_carry = True
        return True

    def _n_ApplyForceOnRogue4DLC2BounceEnemy(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        dk = node.get("_directionKey") or "direction"
        direction = (ctx.get("bb") or {}).get(dk, "UP")
        dr, dc = {"UP": (-1, 0), "DOWN": (1, 0),
                  "LEFT": (0, -1), "RIGHT": (0, 1)}.get(
                      str(direction).upper(), (0, 0))
        if node.get("_applyForceDirectly"):
            tgt.pos_x += dc * 0.5
            tgt.pos_y += dr * 0.5
        else:
            from .consts import DamageType
            battle.apply_damage(tgt, 1.0, DamageType.TRUE, source=None)
        return True

    def _n_HaveShieldRoguelike(self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        return float(battle._rogue_shield or 0.0) > 0

    def _n_RoguelikeRecordUnitStatus(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._sandbox_unit_states[getattr(tgt, "inst_id", 0)] = {
            "hp": float(getattr(tgt, "hp", 0.0) or 0.0),
            "row": int(getattr(tgt, "row", 0) or 0),
            "col": int(getattr(tgt, "col", 0) or 0),
        }
        return True

    def _n_RoguelikeDeifyModeRegisterChosenCharacter(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._rogue_deify_chosen = getattr(tgt, "inst_id", 0)
        return True

    def _n_RoguelikeDeifyModeRegisterDeifyTrap(self, owner, node, ctx):
        battle = self.battle
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        battle._rogue_deify_trap = getattr(tgt, "inst_id", 0)
        return True

    def _n_RoguelikeFilterHostrInCandleHolder(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        if tgt is None:
            return False
        tgt._candle_holder = True
        return True

    def _n_RoguelikeAssignCharacterInCandleHolderCntToBlackboard(
            self, owner, node, ctx):
        battle = self.battle
        if not battle:
            return False
        cnt = 0
        for u in (list(battle.get_operators()) + list(battle.get_tokens())):
            if not getattr(u, "dead", False) and \
                    getattr(u, "_candle_holder", False):
                cnt += 1
        bb = ctx.get("bb")
        if not isinstance(bb, dict):
            bb = {}
        bb[node.get("blackboardKey") or "cnt"] = cnt
        return True

    def _n_Rogue6StormDirectionCheck(self, owner, node, ctx):
        tgt = _source_unit(self.battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target")) or owner
        return bool(getattr(tgt, "_storm_direction", None))

    def _n_Main16ChangeTileShadowViaRange(self, owner, node, ctx):
        """Mainline 16: mark tiles in a rectangular range as shadowed
        (simplified: record the shadow area and emit)."""
        battle = self.battle
        if not battle:
            return True
        begin = node.get("_beginPosition") or {}
        end = node.get("_endPosition") or {}
        r0 = int(begin.get("row") or 0)
        c0 = int(begin.get("col") or 0)
        r1 = int(end.get("row") or 0)
        c1 = int(end.get("col") or 0)
        battle._main16_shadow = {(r, c)
                                 for r in range(min(r0, r1), max(r0, r1) + 1)
                                 for c in range(min(c0, c1), max(c0, c1) + 1)}
        try:
            battle.emit(battle.tick, "main16_shadow_range",
                        {"begin": [r0, c0], "end": [r1, c1]})
        except Exception:
            pass
        return True

    def _n_Main16CheckTargetInShadowStateTile(self, owner, node, ctx):
        """Mainline 16 gate: the owner/target stands on a shadowed tile."""
        battle = self.battle
        if not battle:
            return True
        tgt = _source_unit(battle, node.get("_target"), owner,
                           ctx.get("source"), ctx.get("target"))
        shadow = getattr(battle, "_main16_shadow", set()) or set()
        return tgt is not None and (tgt.row, tgt.col) in shadow

    def _n_Mainline14InformLrdeadDeath(self, owner, node, ctx):
        """Mainline 14: inform the lrdead phase-2 env system (emit only)."""
        battle = self.battle
        if battle:
            try:
                battle.emit(battle.tick, "mainline14_lrdead_death",
                            {"envSysKey": node.get("_evnSysKey"),
                             "unit": getattr(owner, "inst_id", None)})
            except Exception:
                pass
        return True

    def _n_Mainline14TriggerSkill(self, owner, node, ctx):
        """Mainline 14: trigger the lrdead env skill (emit + try to
        trigger a matching enemy skill)."""
        battle = self.battle
        if not battle:
            return True
        src = _source_unit(battle, "SOURCE", owner, ctx.get("source"))
        sc = getattr(src, "skill_controller", None)
        if sc is not None:
            for s in getattr(sc, "skills", None) or []:
                if getattr(s, "prefab_key", "") in (
                        "LrdeadTriggerSkill", "TriggerSkill"):
                    try:
                        sc._start_cast((s, None))
                    except Exception:
                        pass
                    break
        try:
            battle.emit(battle.tick, "mainline14_trigger_skill",
                        {"envSysKey": node.get("_evnSysKey")})
        except Exception:
            pass
        return True

    def _n_Mainline17CreateBossClickCounterButton(
            self, owner, node, ctx):
        """Mainline 17: boss click-counter (simplified: record required
        clicks; battle emits click events for the AI layer)."""
        battle = self.battle
        if not battle:
            return True
        battle._main17_click_required = int(
            node.get("_requiredClickCount") or 0)
        battle._main17_click_success_buff = node.get("_successBuffKey")
        try:
            battle.emit(battle.tick, "mainline17_click_counter",
                        {"required": battle._main17_click_required})
        except Exception:
            pass
        return True

    def _n_HpNoLessThanCertainPercentModifier(self, owner, node, ctx):
        """Clamp incoming damage so the owner's HP cannot drop below a
        percent of max HP (game HpNoLessThanCertainPercentModifier).
        Ground truth: 煌 T1 紧急除颤 — while huang_t_1[lock] is active
        HP stays >= huang_t_1[lock].min_hp_ratio (0.5) for the talent
        duration. The ratio is read from the buff blackboard (namespaced
        key first, then generic fallbacks), defaulting to 0.5."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        ratio = None
        for k in ("huang_t_1[lock].min_hp_ratio", "min_hp_ratio",
                  "hp_no_less_than_percent", "hp_percent", "ratio"):
            v = bb.get(k)
            if v is not None:
                ratio = _num(v, None)
                if ratio is not None:
                    break
        if ratio is None:
            ratio = 0.5
        dmg = ctx.get("damage") or {}
        amount = _num(dmg.get("amount"), 0.0)
        if amount <= 0:
            return True
        max_hp = float(getattr(owner, "max_hp", 0.0) or 0.0)
        hp = float(getattr(owner, "hp", 0.0) or 0.0)
        if max_hp <= 0:
            return True
        floor = max(0.0, ratio * max_hp)
        allowed = max(0.0, hp - floor)
        dmg["amount"] = min(amount, allowed)
        return True

    def _n_HealByFixedValue(self, owner, node, ctx):
        battle = self.battle
        target = _source_unit(battle, node.get("_healTarget"), owner,
                              ctx.get("source"))
        bb = ctx.get("bb") or {}
        key = node.get("_healValueKey")
        amount = _num(bb.get(key, node.get("_healValue")),
                      node.get("_healValue") or 0.0) if key else \
            _num(node.get("_healValue"), 0.0)
        if target is not None and amount > 0:
            battle.apply_heal(target, amount, source=owner)
        return True

    def _n_BleedingDamageIncreasingReset(self, owner, node, ctx):
        """dragon_fire ramp reset: the ramp restarts on refresh,
        which the model gets via fresh remaining_ticks."""
        return True

    def _n_BleedingDamagePerSec(self, owner, node, ctx):
        """dragon_fire DoT: PURE damage = baseDamage + addOnDamage
        ramping linearly to cap over addOnDuration seconds."""
        battle = self.battle
        bb = ctx.get("bb") or {}
        base = _num(bb.get(node.get("_baseDamageKey") or "baseDamage"), 0.0)
        add = _num(bb.get(node.get("_damageKey") or "addOnDamage"), 0.0)
        ramp = _num(bb.get(node.get("_durationToIncreaseKey") or "addOnDuration"), 0.0)
        entry = bb.get("_buff_entry") or {}
        total = _num(entry.get("_total_ticks") or bb.get("_total_ticks"), 0)
        remain = _num(entry.get("remaining_ticks") or bb.get("_remaining_ticks"), 0)
        elapsed = max(0.0, (float(total) - float(remain)) / 30.0)
        frac = min(1.0, elapsed / ramp) if ramp > 0 else 1.0
        amount = base + add * frac
        target = ctx.get("target") or owner
        if amount > 0 and target is not None and not getattr(
                target, "dead", False):
            battle.apply_damage(target, amount, DamageType.TRUE,
                                source=owner, no_hit_recovery=True)
        return True


    def _n_ApplyDamageByAtkScale(self, owner, node, ctx):
        return self._n_AdvancedApplyDamage(owner, node, ctx)

    # ---- prefab-driven economy / control nodes ----
    def _n_ModifyCost(self, owner, node, ctx):
        """ModifyCost (charge_cost): add deployment cost from blackboard."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_blackboardKey") or "cost"
        amount = _num(bb.get(key), 0.0)
        if amount:
            battle.battle_cost_add(amount)
        return True

    def _try_deploy_trap(self, owner, node, ctx):
        """Traper (\u9677\u9631\u5e08): deploy the operator's trap token
        (token_*_mine matched by codename) at the nearest free buildable
        tile inside its attack range; count from bb `_cntKey`."""
        battle = self.battle
        if not battle:
            return False
        op = ctx.get("source") or owner
        if op is None or getattr(op, "dead", False):
            return False
        code = (getattr(op, "char_id", "") or "").rsplit("_", 1)[-1]
        if not code:
            return False
        token_key = None
        try:
            data = getattr(battle, "char_data", None) or {}
            for k in data:
                # traper mines / craftsman devices: token_*_<code>_<suffix>
                if k.startswith("token_") and ("_" + code + "_") in k:
                    token_key = k
                    break
        except Exception:
            pass
        if not token_key:
            return False
        cnt_key = node.get("_cntKey") or "cnt"
        bb = ctx.get("bb") or {}
        try:
            cnt = max(1, int(float(bb.get(cnt_key, 1) or 1)))
        except (TypeError, ValueError):
            cnt = 1
        placed = 0
        cells = [(op.row + dr, op.col + dc)
                 for dr, dc in (getattr(op, "range_shape", None) or [])]
        occ = set()
        for u in list(battle.get_operators()) + list(battle.get_tokens()):
            occ.add((u.row, u.col))
        for e in battle.get_enemies():
            if not getattr(e, "dead", False):
                occ.add((e.row, e.col))
        cells.sort(key=lambda c: abs(c[0] - op.row) + abs(c[1] - op.col))
        cands = [c for c in cells if c not in occ]
        for r, c in cands:
            t = battle.map.tile(r, c) if battle.map else None
            if t is None or not t.buildable_type:
                continue
            try:
                ok = battle.deploy_token(token_key, r, c, owner=op)
                if isinstance(ok, tuple):
                    ok = bool(ok[0])
            except Exception:
                ok = False
            if ok:
                placed += 1
                if placed >= cnt:
                    break
        if placed == 0 and (op.row, op.col) not in occ:
            try:
                ok = battle.deploy_token(token_key, op.row, op.col,
                                         owner=op)
                if isinstance(ok, tuple):
                    ok = bool(ok[0])
            except Exception:
                ok = False
            placed += 1 if ok else 0
        return placed > 0

    def _n_ApplyElementHeal(self, owner, node, ctx):
        """ApplyElementHeal (ep_heal_all): heal element EP by ratio of max."""
        battle = self.battle
        if not battle:
            return True
        bb = ctx.get("bb") or {}
        target = ctx.get("target") or owner
        ratio = _num(bb.get("ep_heal_ratio"),
                     _num(node.get("_healRatio"), 0.0))
        if ratio <= 0:
            return True
        amount = ratio * battle.buffs.ep_max(target)
        # EP heal = reduce every element bar (clamped at 0)
        battle.buffs.recover_ep(target, amount)
        return True

    def _n_Withdraw(self, owner, node, ctx):
        """Withdraw (suicide): force the unit off the field."""
        battle = self.battle
        if not battle or owner is None:
            return True
        if getattr(owner, "side", 0) == 1:
            try:
                battle.withdraw(owner.inst_id)
            except Exception:
                owner.hp = 0.0
        else:
            owner.hp = 0.0
        return True

    def _n_RechargeToken(self, owner, node, ctx):
        """RechargeToken: traper (\u9677\u9631\u5e08) deploys its trap
        token; otherwise immediately grant cnt SP (charge recovery)."""
        battle = self.battle
        if battle is not None and self._try_deploy_trap(owner, node, ctx):
            return True
        bb = ctx.get("bb") or {}
        key = node.get("_cntKey") or "cnt"
        cnt = _num(bb.get(key), 1.0)
        sc = getattr(owner, "skill_controller", None)
        if sc is not None and cnt > 0:
            sc.recover_sp(1, float(cnt))
        return True

    def _n_DisableTrait(self, owner, node, ctx):
        return True

    def _n_EnableTrait(self, owner, node, ctx):
        return True

    def _n_RemainingRatioToAttributeModifier(self, owner, node, ctx):
        """Decaying stat modifier (e.g. Gravel S1 def +200% attenuating).

        The buff entry's layer is refreshed each ON_BUFF_TRIGGER with
        value = blackboard value x remaining-ratio, so Attributes rebuild
        picks up the decay."""
        battle = self.battle
        bb = ctx.get("bb") or {}
        entry = bb.get("_buff_entry")
        stat = _ATTR_TYPE_NAMES.get(_attr_type_int(node.get("_attributeType")))
        if not stat or entry is None:
            return True
        key = node.get("_valueKey") or stat
        value = _num(bb.get(key), _num(node.get("_value"), 0.0))
        rem = _num(bb.get("_remaining_ticks"), 0.0)
        total = _num(bb.get("_total_ticks"), 1.0) or 1.0
        ratio = max(0.0, min(1.0, rem / total))
        if node.get("_isInversed"):
            ratio = 1.0 - ratio
        formula = _formula_int(node.get("_formulaType"))
        layer = "mul" if formula in (1, 3) else \
            ("final_add" if formula == 2 else "add")
        if formula == 3:
            entry[layer] = 1.0 + value * ratio
        else:
            entry[layer] = value * ratio
        entry["stat"] = stat
        if battle is not None:
            battle.buffs._rebuild_modifiers(owner)
        return True

    def _dmg_type(self, name):
        from .consts import DamageType
        n = (name or "").upper()
        if n in ("PURE", "TRUE"):
            return DamageType.TRUE
        if n == "MAGIC" or "MAGIC" in n or "??" in n:
            return DamageType.MAGICAL
        if n == "ELEMENT":
            return DamageType.ELEMENT
        return DamageType.PHYSICAL

    # ---- buff creation / removal -----------------------------------------
    def _n_CreateBuff(self, owner, node, ctx):
        battle = self.battle
        targets = _targets(battle, node.get("_buffOwner"), owner,
                           source=ctx.get("source"), target=ctx.get("target"))
        bb = dict(ctx.get("bb") or {})
        for t in targets:
            if t is None or getattr(t, "dead", False):
                continue
            entry = _embedded_buff(battle, t, node, bb, owner)
            battle.add_buff(t, entry)
        return True

    def _n_SpawnTokenOnTargetTile(self, owner, node, ctx):
        """Force-spawn a token on the owner's tile (game SpawnTokenOn-
        TargetTile, e.g. ?? S3 ???? on the bursting enemy)."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source")) or ctx.get("source")
        key = node.get("_spawnTokenKey") or ""
        if tgt is None or not key:
            return False
        ok, _ = battle.spawn_token_forced(key, tgt.row, tgt.col, owner=src)
        return bool(ok)

    def _n_CreateBuffToCharacterOnTargetRootTile(self, owner, node, ctx):
        """Apply the embedded buffs to the character token standing on the
        owner's root tile (refresh of an existing cage)."""
        battle = self.battle
        if not battle:
            return False
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if tgt is None:
            return False
        buffs = node.get("_buffs") or []
        applied = 0
        for tk in battle.tokens:
            if tk.dead or (tk.row, tk.col) != (tgt.row, tgt.col):
                continue
            # a forced refresh resets the summon's HP to full (PRTS:
            # existing cage on the tile is refreshed: HP reset + re-block)
            tk.hp = tk.max_hp
            battle.emit(battle.tick, "token_refresh",
                        {"tokenId": tk.token_id, "instId": tk.inst_id,
                         "row": tk.row, "col": tk.col,
                         "owner": getattr(tk.owner, "inst_id", None)})
            for bd in buffs:
                entry = _embedded_buff(battle, tk, {"_buff": bd},
                                       ctx.get("bb") or {}, owner)
                battle.add_buff(tk, entry)
                applied += 1
        return applied > 0

    def _n_CreateBuffById(self, owner, node, ctx):
        battle = self.battle
        key = node.get("_buffKey") or ""
        targets = _targets(battle, node.get("_buffOwner"), owner,
                           source=ctx.get("source"), target=ctx.get("target"))
        for t in targets:
            if t is None or getattr(t, "dead", False):
                continue
            db = buff_definition(key)
            if db:
                entry = materialise_buff(battle, t, named_buff(db),
                                         dict(ctx.get("bb") or {}), owner)
                battle.add_buff(t, entry)
            else:
                battle.add_buff(t, {"key": key, "remaining_ticks": 30 * 3600,
                                    "layers": 1, "source": owner,
                                    "template_key": key})
        return True

    def _n_CreateBuffInRange(self, owner, node, ctx):
        battle = self.battle
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        if src is None:
            src = owner
        radius = _num(node.get("_range"), 1.0)
        r0, c0 = src.row, src.col
        opts = node.get("_targetOptions") or {}
        for t in battle.get_enemies() + battle.get_operators() + \
                battle.get_tokens():
            if getattr(t, "dead", False):
                continue
            if abs(t.row - r0) > radius or abs(t.col - c0) > radius:
                continue
            if not _passes_target_options(t, opts):
                continue
            entry = _embedded_buff(battle, t, node, ctx.get("bb") or {},
                                   owner)
            battle.add_buff(t, entry)
        return True

    def _n_RemoveBuff(self, owner, node, ctx):
        battle = self.battle
        key = node.get("_buffKey") or ""
        targets = _targets(battle, node.get("_buffOwner"), owner,
                           source=ctx.get("source"), target=ctx.get("target"))
        for t in targets:
            if t is not None:
                battle.buffs.remove(t, key)
        return True

    def _n_RemoveAllStatusResistableBuffs(self, owner, node, ctx):
        battle = self.battle
        targets = _targets(battle, node.get("_targetType"), owner,
                           source=ctx.get("source"), target=ctx.get("target"))
        for t in targets:
            if t is not None:
                for b in list(getattr(t, "buffs", []) or []):
                    battle.buffs.remove(t, b["key"])
        return True

    def _n_TriggerAbility(self, owner, node, ctx):
        """Trigger a named ability on the resolved owner (game
        TriggerAbility / TriggerSpecifiedAbility / TriggerAbilityMergeBB).
        The emulator's concrete ability implementations live in the battle
        Python drivers (blaze2 reborn, spawn-token skills, ...); this node
        resolves the owner + target, merges the requested blackboard keys,
        and emits an observable event so every named-ability trigger is
        externally visible even when the ability itself is driven
        elsewhere."""
        return self._trigger_named_ability(owner, node, ctx, merge_bb=False)

    def _n_TriggerSpecifiedAbility(self, owner, node, ctx):
        return self._trigger_named_ability(owner, node, ctx, merge_bb=False)

    def _n_TriggerAbilityMergeBB(self, owner, node, ctx):
        return self._trigger_named_ability(owner, node, ctx, merge_bb=True)

    def _n_TriggerAbilityUseSelectorMergeBB(self, owner, node, ctx):
        """TriggerAbilityMergeBB variant whose target comes from an
        ability selector (the resolved _targetType stands in for the
        selector approximation)."""
        return self._trigger_named_ability(owner, node, ctx, merge_bb=True)

    def _trigger_named_ability(self, owner, node, ctx, merge_bb):
        battle = self.battle
        src = _source_unit(battle, node.get("_ownerType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        name = node.get("_abilityName") or ""
        if not name:
            return False
        bb = ctx.setdefault("bb", {})
        if merge_bb:
            # best-effort merge: the ability's parameter keys are copied
            # from the unit when they are not already in the blackboard
            for k in node.get("_assignBBKeys") or []:
                bb.setdefault(k, getattr(src, k, None))
        if battle is not None:
            battle.emit(battle.tick, "buff_trigger_ability",
                        {"unit": getattr(src, "inst_id", None),
                         "ability": name,
                         "target": getattr(tgt, "inst_id", None),
                         "castDirectly": bool(node.get("_castDirectly")),
                         "mergeBB": merge_bb,
                         "checkCanUse": bool(
                             node.get("_checkCanUseAblityFlag"))})
        return True

    # ---- blackboard -------------------------------------------------------
    def _n_EnsureBlackboardDefaultValue(self, owner, node, ctx):
        for s in node.get("_defaultSettings") or []:
            key = s.get("key")
            if key and key not in ctx.get("bb", {}):
                ctx.setdefault("bb", {})[key] = s.get("val")
        return True

    def _n_AssignBlackboardValue(self, owner, node, ctx):
        key = node.get("_blackboardKey")
        if key:
            ctx.setdefault("bb", {})[key] = node.get("_value")
        return True

    def _n_ModifyBlackboardStr(self, owner, node, ctx):
        """Set a blackboard string key from a fixed _value or copied from
        _fromBlackboardKeys (ModifyBlackboardStr, e.g. act46side toast
        texts)."""
        bb = ctx.setdefault("bb", {})
        keys = node.get("_blackboardKeys") or ""
        if not keys:
            return True
        val = node.get("_value")
        fk = node.get("_fromBlackboardKeys")
        if fk:
            val = bb.get(fk, val)
        bb[keys] = val
        return True

    # ---- visual / structural (record only) --------------------------------
    def _n_CreateEffect(self, owner, node, ctx):
        if self.battle:
            self.battle.emit(self.battle.tick, "buff_effect",
                             {"unit": owner.inst_id,
                              "effect": node.get("_effectKey")})
        return True

    def _n_CreateTileEffect(self, owner, node, ctx):
        """Visual tile effect (CreateTileEffect): emitted as an observable
        tile_effect event; holds no battle-state effect."""
        if self.battle:
            self.battle.emit(self.battle.tick, "tile_effect",
                             {"unit": getattr(owner, "inst_id", None),
                              "effect": node.get("_effectKey"),
                              "holdIt": bool(node.get("_holdIt")),
                              "verifyBeforeCreate": bool(
                                  node.get("_verifyBeforeCreate"))})
        return True

    def _n_PlayAudio(self, owner, node, ctx):
        return True

    def _n_ModifyGraphicHolderHeight(self, owner, node, ctx):
        return True

    def _n_SwitchMode(self, owner, node, ctx):
        """Switch the resolved unit's mode index (mode_index) and fire
        ON_UNIT_SWITCH_MODE (SwitchMode is a core node, 1100+ uses)."""
        battle = self.battle
        u = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                         owner, ctx.get("source"), ctx.get("target"))
        if u is None:
            return True
        mi = node.get("_modeIndex")
        if node.get("_loadModeFromBlackboard"):
            bb = ctx.get("bb") or {}
            mi = bb.get("mode_index", mi)
        if node.get("_restoreDefault"):
            mi = 0
        if mi is None:
            return True
        try:
            u.mode_index = int(mi)
        except (TypeError, ValueError):
            return True
        if battle is not None:
            try:
                battle._dispatch_buff_events(u, "ON_UNIT_SWITCH_MODE",
                                             source=u, target=u)
            except Exception:
                pass
        return True

    def _n_EmitProjectile(self, owner, node, ctx):
        """Emit a projectile from the source to the target, applying the
        embedded _buffDataList on hit."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType"), owner,
                           ctx.get("source"))
        tgt = _source_unit(battle, node.get("_targetType"), owner,
                           ctx.get("source"), ctx.get("target"))
        if src is None or tgt is None or getattr(tgt, "dead", False):
            return False
        bb = ctx.get("bb") or {}
        key = node.get("_projectileKey") or bb.get("projectile_key") or ""
        if not key:
            return False
        buffs = node.get("_buffDataList") or []
        if buffs:
            def _cb(battle, proj, _buffs=buffs, _bb=bb, _owner=owner):
                for bd in _buffs:
                    try:
                        entry = materialise_buff(
                            battle, proj.target, dict(bd), dict(_bb),
                            _owner)
                        if entry and entry.get("key"):
                            battle.add_buff(proj.target, entry)
                    except Exception:
                        pass
            battle.spawn_projectile(src, tgt, key, DamageType.TRUE,
                                    hit_callback=_cb)
        else:
            battle.spawn_projectile(src, tgt, key, DamageType.TRUE)
        return True

    def _emit_projectile_with_hit(self, src, tgt, key, node, ctx):
        """Spawn a projectile; on hit run the node's _actions chain
        (e.g. AdvancedApplyDamage) and then apply _buffDataList. When the
        node carries no projectile key, fall back to the source unit's own
        attack projectile ('op_<charId>' for operators, the active skill's
        projectile for enemies)."""
        battle = self.battle
        if battle is None or tgt is None or getattr(tgt, "dead", False):
            return False
        bb = dict(ctx.get("bb") or {})
        if not key:
            key = self._unit_projectile_key(src)
        if not key:
            battle.emit(battle.tick, "buff_emit_projectile",
                        {"unit": getattr(src, "inst_id", None),
                         "target": getattr(tgt, "inst_id", None),
                         "projectile": "", "skipped": "no_projectile_key"})
            return True
        actions = node.get("_actions") or []
        buffs = node.get("_buffDataList") or []
        count = max(1, int(_num(node.get("_emitCount"), 1.0)))
        for _ in range(count):
            def _cb(battle, proj, _actions=actions, _buffs=buffs,
                    _bb=bb, _src=src, _engine=self):
                if _actions:
                    try:
                        _engine.run_actions(
                            _src, _actions,
                            {"owner": _src, "source": _src,
                             "target": proj.target, "damage": None,
                             "bb": _bb}, 0)
                    except Exception:
                        pass
                for bd in _buffs:
                    try:
                        entry = materialise_buff(
                            battle, proj.target, dict(bd), dict(_bb), _src)
                        if entry and entry.get("key"):
                            battle.add_buff(proj.target, entry)
                    except Exception:
                        pass
            battle.spawn_projectile(src, tgt, key, DamageType.TRUE,
                                    hit_callback=_cb)
        return True

    def _unit_projectile_key(self, src):
        """Best-effort basic-attack projectile key for a unit: operators
        use the synthetic 'op_<charId>' key, enemies the projectile of
        their first skill that carries one."""
        if src is None:
            return ""
        cid = getattr(src, "char_id", None) or getattr(src, "token_id", None)
        if cid:
            return "op_%s" % cid
        sc = getattr(src, "skill_controller", None)
        if sc is not None:
            for run in getattr(sc, "skills", []) or []:
                pk = getattr(run, "projectile_key", None) or ""
                if pk:
                    return pk
        return ""

    def _n_EmitProjectileUseAbilitySelector(self, owner, node, ctx):
        """Emit a projectile toward the resolved ability-selector target,
        running the node's _actions chain on hit (game
        EmitProjectileUseAbilitySelector: taraxa splash, enemy_tinker
        missile, logos/resonance projectiles). _excludeTarget drops the
        projectile when the resolved target is the excluded unit."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        tgt = _source_unit(battle, node.get("_targetType") or "BUFF_OWNER",
                           owner, ctx.get("source"), ctx.get("target"))
        if node.get("_excludeTarget"):
            ex = _source_unit(battle, node.get("_excludeTargetType")
                              or "BUFF_OWNER", owner, ctx.get("source"),
                              ctx.get("target"))
            if ex is not None and tgt is not None and ex is tgt:
                return True
        key = node.get("_projectileKey") or ""
        if not key:
            key = (ctx.get("bb") or {}).get("projectile_key") or ""
        ok = self._emit_projectile_with_hit(src, tgt, key, node, ctx)
        battle.emit(battle.tick, "buff_emit_projectile",
                    {"unit": getattr(src, "inst_id", None),
                     "target": getattr(tgt, "inst_id", None),
                     "projectile": key or self._unit_projectile_key(src),
                     "selector": node.get("_abilityName"),
                     "useAbilityFromOther": bool(
                         node.get("_useAbilityFromOther"))})
        return ok

    def _n_EmitProjectileOnSourceRootTile(self, owner, node, ctx):
        """Emit the source's projectile from its root tile (game
        EmitProjectileOnSourceRootTile; observed with ON_HIT_TILE /
        ON_HIT_OBJECT and empty action lists - mostly positional/visual,
        exposed as an observable event with the resolved key)."""
        battle = self.battle
        if not battle:
            return False
        src = _source_unit(battle, node.get("_sourceType") or "BUFF_OWNER",
                           owner, ctx.get("source"))
        if src is None:
            src = owner
        tgt = _source_unit(battle, node.get("_targetType") or "TARGET",
                           owner, ctx.get("source"), ctx.get("target"))
        if tgt is None or getattr(tgt, "dead", False):
            battle.emit(battle.tick, "buff_emit_projectile",
                        {"unit": getattr(src, "inst_id", None),
                         "projectile": self._unit_projectile_key(src),
                         "ev": node.get("_ev"),
                         "skipped": "no_target"})
            return True
        key = node.get("_projectileKey") or ""
        if not key:
            key = (ctx.get("bb") or {}).get("projectile_key") or ""
        ok = self._emit_projectile_with_hit(src, tgt, key, node, ctx)
        battle.emit(battle.tick, "buff_emit_projectile",
                    {"unit": getattr(src, "inst_id", None),
                     "target": getattr(tgt, "inst_id", None),
                     "projectile": key or self._unit_projectile_key(src),
                     "ev": node.get("_ev"), "fromRootTile": True})
        return ok
