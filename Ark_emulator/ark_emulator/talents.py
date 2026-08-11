"""Operator talent system.

Talents come from characters.json (charId -> talents[{candidates:[
{unlockCondition, prefabKey, name, description, blackboard}]}]).
Candidates are picked by phase/level/potential; the highest unlocked
candidate's blackboard drives the effect. Common hooks:
  - attack SP bonus (e.g. amiya_t_1[atk].sp)
  - kill SP bonus (e.g. amiya_t_1[kill].sp)
  - stat modifiers (atk/def/...)
"""


class TalentSystem:
    """Per-operator talent selection and hooks."""

    def __init__(self, op, talent_data, phase=2, level=50, potential_rank=0):
        self.op = op
        self.talents = []
        self.token_key = None
        for t in (talent_data or []):
            best = None
            for cand in (t.get("candidates") or []):
                uc = cand.get("unlockCondition") or {}
                req_phase = uc.get("phase") or 0
                req_level = uc.get("level") or 0
                req_pot = cand.get("requiredPotentialRank") or 0
                if phase >= req_phase and level >= req_level and \
                        potential_rank >= req_pot:
                    best = cand
            if best is not None:
                bb = {b["key"]: b.get("value")
                      for b in (best.get("blackboard") or [])}
                self.talents.append({
                    "name": best.get("name"),
                    "description": best.get("description"),
                    "blackboard": bb,
                })
                # talent-bound summons (e.g. Kal'tsit -> Mon3tr)
                if best.get("tokenKey"):
                    self.token_key = best.get("tokenKey")

    def apply_module_upgrades(self, upgrades, potential_rank=0):
        """Override talent blackboard values from an equipped module
        (battle_equip phase candidates). battle_equip lists two candidates
        per talent: the base module value and the potential-upgraded
        variant (the base talent's upgraded candidate sits at potential
        rank 4 for the module pairs observed, e.g. \u9152\u795e \u5760\u68a6
        pot4). With potential < 4 the base candidate wins; otherwise the
        last candidate wins. The module value list follows the base talent
        candidate's blackboard key order (e.g. Y\u6a21\u7ec4 lv3:
        attack_speed -20, value 90 at potential 0; -24, 90 at potential 4)."""
        if not upgrades:
            return
        by_idx = {}
        for up in upgrades:
            idx = int(up.get("talent_index") or 0) - 1
            by_idx.setdefault(idx, []).append(up)
        for idx, ups in by_idx.items():
            if not (0 <= idx < len(self.talents)):
                continue
            pick = ups[-1] if (potential_rank >= 4 and len(ups) > 1) \
                else ups[0]
            base_keys = list(self.talents[idx]["blackboard"].keys())
            vals = pick.get("values") or []
            for i, k in enumerate(base_keys):
                if i < len(vals) and vals[i] is not None:
                    self.talents[idx]["blackboard"][k] = vals[i]

    def bb(self, key_part):
        """Value for the first talent blackboard key containing key_part."""
        for t in self.talents:
            for k, v in t["blackboard"].items():
                if key_part in k:
                    return v
        return None

    def bb_exact(self, key):
        """Exact blackboard key lookup (avoids substring collisions like
        ep_damage_ratio vs attack@ep_damage_ratio)."""
        for t in self.talents:
            if key in t["blackboard"]:
                return t["blackboard"][key]
        return None

    def attack_sp_bonus(self):
        return float(self.bb("[atk].sp") or 0.0)

    def kill_sp_bonus(self):
        return float(self.bb("[kill].sp") or 0.0)

    def ep_damage_scale(self):
        """Element damage taken multiplier from talent blackboards
        (e.g. Thumpy talent 1 \u63a2\u9669\u7406\u8bba: 0.95/0.90/0.85/0.80)."""
        v = self.bb("ep_damage_scale")
        return float(v) if v else 1.0

    def rdoc_overheal_params(self):
        """Doctor (char_4125_rdoc) talent 2 \u4ea4\u611f\u795e\u7ecf\u6fc0\u6d3b:
        overheal converts into a decaying shield. Returns
        (rate_per_0_1s, scale) or None when the talent is unlocked.
        Game buff rdoc_t2[shield]: dynamic_dec_per_sec = dynamic*dec_rate
        (dec_rate -0.2 E1 / -0.1 E2 per second), then *0.1s trigger
        interval, floored on the negative = magnitude ceil; cap = ATK*scale
        (scale 50 = 5000%)."""
        if getattr(self.op, "char_id", "") != "char_4125_rdoc":
            return None
        dec = self.bb("dec_rate")
        scale = self.bb("scale")
        if dec is None or scale is None:
            return None
        rate = abs(float(dec)) * 0.1
        return (rate, float(scale))

    # ---- Thumpy (\u73c0\u6bd4) talent wiring ----
    def _has_thumpy_ep(self):
        return self.bb("ep_damage_ratio[trigger]") is not None

    def _ep_type_from_desc(self):
        """Element type from the talent description (??=0 ??=1
        ??=2 ??=3) for attack-EP attach talents."""
        _ep_keys = ("attack@ep_damage_ratio", "ep_damage_ratio",
                    "attack@dark_damage_value",
                    "attack@ep_damage_ratio_talent")
        for t in self.talents:
            if not any(k in t["blackboard"] for k in _ep_keys):
                continue
            desc = t.get("description") or ""
            if "神经损伤" in desc:
                return 0
            if "侵蚀损伤" in desc:
                return 1
            if "灼燃损伤" in desc:
                return 2
            if "凋亡损伤" in desc:
                return 3
        return None

    def _attack_ep_attach(self, target, dmg_type, amount, battle):
        """Generic attack-element attach (attack@ep_damage_ratio, e.g.
        ?? T1 ????): every attack deals atk*ratio element damage to
        the target, plus a one-time splash (ep_damage_ratio) to the other
        enemies around it (range_radius)."""
        # PhonoR-0 (char_4136_phonor) talent 1: fixed decay EP per attack
        # within the deploy-window duration (blackboard duration = 40s).
        fixed = self.bb_exact("attack@dark_damage_value")
        if fixed is not None and float(fixed) > 0 and amount > 0 and \
                target is not None and not getattr(target, "dead", False):
            dur = float(self.bb("duration") or 0.0)
            win = int(dur * 30)
            op = self.op
            elapsed = battle.tick - getattr(op, "deploy_tick", 0)
            if win <= 0 or elapsed <= win:
                battle.add_ep(target, 3, float(fixed), source=op)
            return
        ratio = self.bb_exact("attack@ep_damage_ratio")
        if not ratio or amount <= 0 or target is None or \
                getattr(target, "dead", False):
            return
        ep_type = self._ep_type_from_desc()
        if ep_type is None:
            return
        op = self.op
        atk = float(op.attributes.get("atk") or 0)
        if atk <= 0:
            return
        battle.add_ep(target, ep_type, atk * float(ratio), source=op)
        splash = self.bb_exact("ep_damage_ratio")
        if splash and float(splash) > 0:
            for e in list(battle.get_enemies()):
                if e is target or e.dead:
                    continue
                if abs(e.row - target.row) <= 1 and \
                        abs(e.col - target.col) <= 1:
                    battle.add_ep(e, ep_type, atk * float(splash), source=op)

    def _phonor_fragile_tick(self, battle):
        """Apply/refresh magic + element fragility on every enemy inside the
        operator attack range while the deploy window is active. The buffs
        carry a short 1s life refreshed each tick so they fall off as soon
        as the enemy leaves the range (or the window expires / operator is
        withdrawn)."""
        op = self.op
        scale = self.bb("damage_scale")
        if scale is None or float(scale) <= 0.0:
            return
        dur = float(self.bb("duration") or 0.0)
        win = int(dur * 30)
        elapsed = battle.tick - getattr(op, "deploy_tick", 0)
        if win > 0 and elapsed > win:
            return
        cells = {(op.row + dr, op.col + dc)
                 for dr, dc in (op.range_shape or [])}
        if not cells:
            return
        payload = {"damage_scale": float(scale),
                   "_phonor_source": op.inst_id}
        for e in list(battle.get_enemies()):
            if e.dead or (e.row, e.col) not in cells:
                continue
            for key in ("weak[magic]", "weak[ep]"):
                battle.add_buff(e, {
                    "key": key,
                    "remaining_ticks": 30,     # 1s, refreshed every tick
                    "layers": 1,
                    "source": op,
                    "blackboard": payload})

    def tick(self, dt, battle):
        """Per-tick talent effects for deployed operators:
        - PhonoR-0 (char_4136_phonor) talent 1: while inside the deploy
          window (duration bb, 40s), enemies in her attack range carry
          magic + element fragility (game phonor_t_1[aura] ->
          weak[magic][inf] / weak[ep][inf], value = damage_scale).
        - Cello (char_245_cello) talent 1: enemies in range take
          atk*ep_damage_ratio decay EP every second, plus a 0.2s sluggish
          at E1+ (game cello_t_1 -> cello_t_1[core]).
        - 煌 (char_017_huang) talent 1 紧急除颤: when HP first drops below
          hp_ratio (0.25), once, heal 50% max HP and lock HP >= 50% for
          huang_t_1[lock].duration seconds.
        """
        cid = getattr(self.op, "char_id", "")
        if cid == "char_4136_phonor":
            self._phonor_fragile_tick(battle)
            return
        if cid == "char_017_huang":
            self._huang_t1_check(battle)
            return
        if cid != "char_245_cello":
            return
        ratio = self.bb("ep_damage_ratio")
        if not ratio or float(ratio) <= 0:
            return
        op = self.op
        acc = getattr(self, "_cello_acc", 0.0) + dt
        if acc < 1.0:
            self._cello_acc = acc
            return
        self._cello_acc = 0.0
        if not op.range_shape:
            return
        cells = {(op.row + dr, op.col + dc) for dr, dc in op.range_shape}
        atk = float(op.attributes.get("atk") or 0)
        slow = self.bb("sluggish")
        for e in list(battle.get_enemies()):
            if e.dead or (e.row, e.col) not in cells:
                continue
            if atk > 0:
                battle.add_ep(e, 3, atk * float(ratio), source=op)
            if slow and float(slow) > 0:
                battle.add_buff(e, {
                    "key": "op_sluggish",
                    "remaining_ticks": int(float(slow) * 30),
                    "layers": 1, "mul": -0.5, "stat": "moveSpeed",
                    "source": op})

    def _huang_t1_check(self, battle):
        """煌 T1 紧急除颤: when HP first drops below 25%, heal 50% max HP
        and keep HP >= 50% for the talent duration. The heal fires through
        the huang_t_1[heal] buff (HealViaMaxHpRatio), the HP floor through
        huang_t_1[lock] (HpNoLessThanCertainPercentModifier on
        ON_TAKE_DAMAGE). Only once per deployment."""
        op = self.op
        if getattr(self, "_huang_t1_done", False) or op.dead:
            return
        max_hp = float(op.max_hp or 0.0)
        if max_hp <= 0:
            return
        trigger = self.bb("hp_ratio")
        if trigger is None:
            return
        if float(op.hp or 0.0) / max_hp >= float(trigger):
            return
        self._huang_t1_done = True
        heal_ratio = self.bb("huang_t_1[heal].hp_ratio")
        lock_ratio = self.bb("huang_t_1[lock].min_hp_ratio")
        duration = self.bb("huang_t_1[lock].duration")
        heal_ratio = float(heal_ratio if heal_ratio is not None else 0.5)
        lock_ratio = float(lock_ratio if lock_ratio is not None else 0.5)
        dur = float(duration if duration is not None else 3.0)
        battle.add_buff(op, {
            "key": "huang_t_1[heal]",
            "template_key": "huang_t_1[heal]",
            "remaining_ticks": 30,
            "layers": 1, "source": op,
            "blackboard": {"hp_ratio": heal_ratio}})
        battle.add_buff(op, {
            "key": "huang_t_1[lock]",
            "template_key": "huang_t_1[lock]",
            "remaining_ticks": max(1, int(dur * 30)),
            "layers": 1, "source": op,
            "blackboard": {"huang_t_1[lock].min_hp_ratio": lock_ratio,
                           "huang_t_1[lock].duration": dur}})
        battle.emit(battle.tick, "huang_t1_trigger",
                    {"unit": op.inst_id, "hp": round(float(op.hp), 3),
                     "healRatio": heal_ratio, "lockRatio": lock_ratio,
                     "duration": dur})

    def deploy_buffs(self, battle):
        """Deploy-time talent buffs. Currently wires ?? T1 ????:
        a global fire-burst listener buff (blaze2_t_1) carrying her talent
        blackboard (ep_damage_scale / hp_ratio)."""
        out = []
        cid = getattr(self.op, "char_id", "")
        # threye (char_4102_threye): every damage output attaches decay EP
        # = atk * ep_damage_ratio (game template threye_t_2).
        if cid == "char_4102_threye":
            ratio = self.bb("ep_damage_ratio")
            if ratio is not None and float(ratio) > 0:
                out.append({
                    "key": "threye_t_2", "template_key": "threye_t_2",
                    "remaining_ticks": 30 * 3600, "layers": 1,
                    "source": self.op,
                    "blackboard": {"ep_damage_ratio": float(ratio)}})
        # pithst (char_616_pithst): attack attaches neural + burning +
        # decay EP, each atk * ep_damage_ratio (game template pithst_t_1).
        if cid == "char_616_pithst":
            ratio = self.bb("ep_damage_ratio")
            if ratio is not None and float(ratio) > 0:
                out.append({
                    "key": "pithst_t_1", "template_key": "pithst_t_1",
                    "remaining_ticks": 30 * 3600, "layers": 1,
                    "source": self.op,
                    "blackboard": {"ep_damage_ratio": float(ratio)}})
        # botany (char_4223_botany): any WATER (erosion) burst on the field
        # stacks attack speed (game botany_t_1 template; no range gate).
        if cid == "char_4223_botany":
            aspd = self.bb("attack_speed")
            maxst = int(float(self.bb("max_stack_cnt") or 3.0))
            if aspd is not None and float(aspd) > 0 and maxst > 0:
                op = self.op

                def _on_ep_burst(ev):
                    if getattr(op, "dead", False) or \
                            op not in list(battle.operators):
                        return
                    data = ev.data or {}
                    if int(data.get("type", -1)) != 1:
                        return
                    existing = battle.buffs.get(
                        op, "botany_t_1[attack_speed]")
                    layers = min(maxst, (existing.get("layers", 1)
                                         if existing else 0) + 1)
                    battle.add_buff(op, {
                        "key": "botany_t_1[attack_speed]",
                        "stat": "attackSpeed", "add": float(aspd),
                        "layers": layers,
                        "remaining_ticks": 1 << 30, "source": op})

                battle.events.subscribe("ep_burst", _on_ep_burst)
        if cid == "char_1040_blaze2":
            scale = self.bb("ep_damage_scale")
            if scale is not None:
                hp = float(self.bb("hp_ratio") or 0.0)
                out.append({
                    "key": "blaze2_t_1",
                    "template_key": "blaze2_t_1",
                    "remaining_ticks": 30 * 3600,
                    "layers": 1, "source": self.op,
                    "blackboard": {"ep_damage_scale": float(scale),
                                   "ratio": hp}})
            # T2 \u7edd\u5904\u91cd\u71c3: lethal hit -> downed state
            # (6000 barrier, %maxHp regen per sec, revive + stun nearby)
            ratio = self.bb("hp_recovery_per_sec_by_max_hp_ratio")
            if ratio is not None:
                out.append({
                    "key": "blaze2_t_2",
                    "template_key": "blaze2_t_2",
                    "remaining_ticks": 30 * 3600,
                    "layers": 1, "source": self.op,
                    "blackboard": {
                        "hp_recovery_per_sec_by_max_hp_ratio": float(ratio),
                        "stun": float(self.bb("stun") or 5.0),
                        "dynamic": float(self.bb("dynamic") or 6000.0)}})
        return out

    def on_damage_output(self, target, dmg_type, amount, battle):
        """Thumpy talent 1: physical damage output attaches water erosion
        (atk * ep_damage_ratio[trigger]) and marks the enemy; during the
        target's erosion burst cooldown it instead shortens the cooldown by
        duration_dec (mutually exclusive, PRTS note)."""
        # generic attack-element attach first (any damage type)
        self._attack_ep_attach(target, dmg_type, amount, battle)
        # Bobb (char_487_bobb) talent 1: the FIRST attack vs each enemy
        # applies a burning-EP DoT (atk*ep_damage_ratio_talent per second
        # for attack@dmg_duration seconds; game bobb_t_1[damage] template).
        cid = getattr(self.op, "char_id", "")
        if cid == "char_487_bobb" and amount > 0 and target is not None \
                and not getattr(target, "dead", False):
            ratio = self.bb_exact("attack@ep_damage_ratio_talent")
            dur = self.bb_exact("attack@dmg_duration")
            if ratio and float(ratio) > 0 and dur and float(dur) > 0:
                marked = getattr(self, "_bobb_marked", None)
                if marked is None:
                    marked = set()
                    self._bobb_marked = marked
                if target.inst_id not in marked:
                    marked.add(target.inst_id)
                    battle.buffs.apply(target, {
                        "key": "bobb_t_1[damage]",
                        "template_key": "bobb_t_1[damage]",
                        "remaining_ticks": max(1, int(float(dur) * 30)),
                        "layers": 1, "source": self.op,
                        "blackboard": {
                            "ep_damage_ratio_talent": float(ratio)},
                        "_trigger_interval": 30, "_trigger_acc": 0})
        if not self._has_thumpy_ep() or amount <= 0:
            return
        from .consts import DamageType
        if dmg_type != DamageType.PHYSICAL:
            return
        op = self.op
        atk = float(op.attributes.get("atk") or 0)
        if atk <= 0:
            return
        ratio = float(self.bb("ep_damage_ratio[trigger]") or 0.0)
        dec = float(self.bb("duration_dec") or 0.0)
        cd = battle.buffs.get(target, "ep_burst_cd_1")
        if cd is not None:
            if dec > 0 and cd.get("remaining_ticks"):
                cd["remaining_ticks"] = max(
                    0, int(cd["remaining_ticks"]) - int(round(dec * 30)))
                battle.emit(battle.tick, "thumpy_ep_cd_reduce", {
                    "unit": target.inst_id, "seconds": round(dec, 3),
                    "source": op.inst_id})
            return
        # mark BEFORE the EP so the burst sees it
        battle.add_buff(target, {
            "key": "thumpy_water_mark",
            "remaining_ticks": 1 << 30,
            "layers": 1,
            "source": op,
        })
        if ratio > 0:
            battle.add_ep(target, 1, atk * ratio)

    def thumpy_burst_reward(self, battle, enemy):
        """Thumpy talent 2 \u575a\u786c\u811a\u677f: marked enemy water burst
        gives the operator a DEF stack (max max_stack_cnt) and adds barrier
        (shield_value, capped at scale x max HP)."""
        shield = self.bb("shield_value")
        defv = self.bb("def")
        if shield is None and defv is None:
            return
        op = self.op
        if getattr(op, "dead", False):
            return
        max_stack = int(float(self.bb("max_stack_cnt") or 30.0))
        if defv:
            existing = None
            for x in (op.buffs or []):
                if x.get("key") == "thumpy_t2_def":
                    existing = x
                    break
            layers = min(max_stack, (existing.get("layers", 1)
                                     if existing else 0) + 1)
            battle.add_buff(op, {
                "key": "thumpy_t2_def", "stat": "def",
                "add": float(defv), "layers": layers,
                "remaining_ticks": 1 << 30, "source": op})
        if shield:
            scale = float(self.bb("scale") or 3.0)
            battle.add_barrier(op, float(shield),
                               max_value=float(op.max_hp) * scale,
                               source=op)

    # permanent talent stat whitelist (plain keys; attack@*/xxx.yyy keys are
    # attack-time / aura effects and are excluded here)
    _MULT_STATS = {"atk", "def", "max_hp", "move_speed", "magic_resistance"}
    _ADD_STATS = {"attack_speed", "block_cnt", "hp_recovery_per_sec",
                  "sp_recovery_per_sec", "taunt_level", "max_deploy_count",
                  "def_penetrate_fixed", "magic_resist_penetrate_fixed",
                  "def_penetrate", "magic_resist_penetrate", "range_radius"}
    _STAT_MAP = {
        "atk": "atk", "def": "def", "max_hp": "maxHp",
        "move_speed": "moveSpeed", "magic_resistance": "magicResistance",
        "attack_speed": "attackSpeed", "block_cnt": "blockCnt",
        "hp_recovery_per_sec": "hpRecoveryPerSec",
        "sp_recovery_per_sec": "spRecoveryPerSec",
        "taunt_level": "tauntLevel", "max_deploy_count": "maxDeployCount",
        "def_penetrate_fixed": "defPenetrateFixed",
        "magic_resist_penetrate_fixed": "magicResistPenetrateFixed",
        "def_penetrate": "defPenetrate",
        "magic_resist_penetrate": "magicResistPenetrate",
        "range_radius": "rangeRadius",
    }

    # talents whose blackboard carries timing/condition keys are periodic or
    # conditional effects, not permanent stats (e.g. ???? ?15? ??+60)
    _DYNAMIC_KEYS = {"interval", "duration", "prob", "hp_ratio",
                     "min_hp_ratio", "max_hp_ratio", "delay"}
    # operators whose plain stat keys are AURA (ally buffs), not self stats
    _AURA_CHARS = {"char_130_doberm", "char_308_swire"}

    def stat_modifiers(self):
        """Permanent self stat modifiers from talent blackboards.

        Returns [(attribute_stat, value, layer)] where layer is 'mul' for
        percent stats (atk/def/max_hp/move_speed/magic_resistance) and 'add'
        for flat stats (attack_speed, penetration, ...). Applied once at
        deploy so later buffs interact through the normal four-layer model.
        Talents with timing/condition keys and aura-type talents are
        excluded here (handled by their own hooks).
        """
        out = []
        cid = getattr(self.op, "char_id", "")
        for t in self.talents:
            bb = t["blackboard"]
            # ?? T1 ??/T2: range_radius is the splash radius and
            # attack_speed/value are enemy-side aura params, not self stats.
            if cid == "char_1042_phatm2" and (
                    "attack@ep_damage_ratio" in bb or
                    "attack_speed" in bb):
                continue
            if any(k in bb for k in self._DYNAMIC_KEYS):
                continue
            for k, v in bb.items():
                if v is None:
                    continue
                if cid in self._AURA_CHARS and k == "atk":
                    continue
                if k in self._MULT_STATS:
                    out.append((self._STAT_MAP[k], float(v), "mul"))
                elif k in self._ADD_STATS:
                    out.append((self._STAT_MAP[k], float(v), "add"))
        return out

    def aura_specs(self):
        """Instructor-family talent auras (ally buffs).

        Returns a list of spec dicts:
          {scope: 'field'|'cell8'|'self', target: 'melee'|'rarity3',
           cond: None|'block_ge3'|'block_lt3', stat, value, layer}
        The battle controller evaluates recipients and conditions each tick.
        """
        op = self.op
        cid = getattr(op, "char_id", "")
        out = []
        for t in self.talents:
            bb = t["blackboard"]
            # ?? ????: all 3-star operators atk
            if cid == "char_130_doberm" and "atk" in bb:
                out.append({"scope": "field", "target": "rarity3",
                            "stat": "atk", "value": float(bb["atk"]),
                            "layer": "mul"})
            # ??? ???????: melee allies in the 8 surrounding cells
            if cid == "char_308_swire" and "atk" in bb:
                out.append({"scope": "cell8", "target": "melee",
                            "stat": "atk", "value": float(bb["atk"]),
                            "layer": "mul"})
            # ?? ??: melee allies, block capacity >=3 full buff, <3 half
            if cid == "char_265_sophia":
                if "attack_speed" in bb and "def" in bb:
                    out.append({"scope": "field", "target": "melee",
                                "cond": "block_ge3", "stat": "attackSpeed",
                                "value": float(bb.get("attack_speed") or 0),
                                "layer": "add"})
                    out.append({"scope": "field", "target": "melee",
                                "cond": "block_ge3", "stat": "def",
                                "value": float(bb.get("def") or 0),
                                "layer": "mul"})
                if "sophia_t_1_less.attack_speed" in bb:
                    out.append({"scope": "field", "target": "melee",
                                "cond": "block_lt3",
                                "stat": "attackSpeed",
                                "value": float(
                                    bb.get("sophia_t_1_less.attack_speed")
                                    or 0), "layer": "add"})
                    out.append({"scope": "field", "target": "melee",
                                "cond": "block_lt3", "stat": "def",
                                "value": float(
                                    bb.get("sophia_t_1_less.def") or 0),
                                "layer": "mul"})
            # ?? ????: ally def in 8 cells when self not blocking;
            # self def while blocking
            # Pallas \u5e15\u62c9\u65af talent 1 \u82f1\u96c4\u7684\u8bde\u751f:
            # field aura for [\u7c73\u8bfa\u65af] operators above hp_ratio:
            # +atk% peak performance (same-name effects take the highest).
            if cid == "char_485_pallas" and \
                    "peak_performance.hp_ratio" in bb:
                out.append({
                    "scope": "field", "target": "minos",
                    "named": "peak_performance",
                    "cond": "hp_gt",
                    "hp_ratio": float(bb.get("peak_performance.hp_ratio")
                                        or 0.8),
                    "stat": "atk",
                    "value": float(bb.get("peak_performance.atk") or 0.0),
                    "layer": "mul"})
            if cid == "char_4106_bryota":
                blocking = bool(getattr(op, "blocked_enemies", None))
                ally_v = bb.get("bryota_t_ally.def")
                self_v = bb.get("bryota_t_self.def")
                if ally_v is not None and not blocking:
                    out.append({"scope": "cell8", "target": "melee",
                                "stat": "def", "value": float(ally_v),
                                "layer": "mul"})
                if self_v is not None and blocking:
                    out.append({"scope": "self", "stat": "def",
                                "value": float(self_v), "layer": "mul"})
            # \u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 T2 \u706b\u5c71\u7070\u7597\u6108:
            # allies in her attack range get maxHp +6% (mul) and elemental
            # damage taken -12% (epDamageResistance +12); S3 \u706b\u5c71
            # \u56de\u97ff doubles the effect (talent_scale = 2.0).
            if cid == "char_1016_agoat2" and "max_hp" in bb:
                _t2_scale = 1.0
                _sc = getattr(op, "skill_controller", None)
                _act = getattr(_sc, "active", None) if _sc else None
                if getattr(getattr(_act, "skill", None), "skill_id", "") == \
                        "skchr_agoat2_3":
                    _t2_scale = 2.0
                out.append({"scope": "range", "stat": "maxHp",
                            "value": float(bb["max_hp"]) * _t2_scale,
                            "layer": "mul"})
                if "ep_damage_resistance" in bb:
                    out.append({
                        "scope": "range", "stat": "epDamageResistance",
                        "value": float(bb["ep_damage_resistance"]) * 100.0
                        * _t2_scale, "layer": "add"})
            # \u54c8\u6d1b\u5fb7 T1 \u6211\u5373\u519b\u8425: allies inside the
            # attack range whose accumulated element damage exceeds half
            # their burst threshold take less element damage
            # (epDamageResistance 12/15/18% by phase/potential).
            if cid == "char_4114_harold" and \
                    "ep_damage_resistance" in bb:
                out.append({
                    "scope": "range", "stat": "epDamageResistance",
                    "value": float(bb["ep_damage_resistance"]) * 100.0,
                    "layer": "add", "cond": "ep_over_half"})
        return out

    def enemy_aura_specs(self):
        """Enemy-side talent auras evaluated per tick by the battle
        controller (allies never receive these). Currently \u9152\u795e
        T2 \u5760\u68a6:
          - pharm2_t2_speed: field-wide, enemies in SANITY burst recovery
            get attack_speed -12/-16 (blackboard attack_speed);
          - phatm2_t2_attack: enemies inside her attack range take 70
            SANITY EP whenever they start a normal attack (blackboard value).
        """
        cid = getattr(self.op, "char_id", "")
        if cid != "char_1042_phatm2":
            return []
        out = []
        for t in self.talents:
            bb = t["blackboard"]
            if "attack_speed" in bb and "value" in bb:
                out.append({"kind": "phatm2_t2_speed",
                            "attack_speed": float(bb["attack_speed"])})
                out.append({"kind": "phatm2_t2_attack",
                            "value": float(bb["value"])})
        return out

    def module_elite_ep_scale(self):
        """\u9152\u795e Y\u6a21\u7ec4 (uniequip_002_phatm2) \u7279\u6027:
        \u5bf9\u7cbe\u82f1\u548c\u9886\u8896\u654c\u4eba\u9020\u6210\u7684\u5143\u7d20\u635f\u4f24\u63d0\u5347
        18% (battle_equip phase-1 \u63cf\u8ff0\u5df2\u786e\u8ba4). Returns a
        damage multiplier (1.0 = no effect)."""
        mod = getattr(self.op, "module", None) or {}
        if getattr(self.op, "char_id", "") == "char_1042_phatm2" and \
                mod.get("id") == "uniequip_002_phatm2":
            return 1.18
        return 1.0

    def attack_heal_flat(self):
        """Flat HP restored per attack on an enemy (Pallas talent 2
        \u5973\u795e\u7684\u632f\u594b: 40/45). Returns None when not wired."""
        if getattr(self.op, "char_id", "") != "char_485_pallas":
            return None
        v = self.bb("value")
        return float(v) if v is not None else None

    def to_dict(self):
        return [{"name": t["name"], "description": t["description"],
                 "blackboard": t["blackboard"]} for t in self.talents]
