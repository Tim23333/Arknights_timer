"""Enemy skill ActionNode executor (prefab ``_actions`` SerializedState).

Enemy abilities carry a serialized action graph (xLua Nodes). We support the
most impactful node types observed in the prefab catalog:
  - MoveNextLevelBranch   : advance a level branch (e.g. Faust SummonBallis)
  - InstantKill           : kill target outright
  - BlinkNode             : teleport along the route
  - SummonEnemies*        : spawn enemies near the owner
  - TriggerEnemySkill     : trigger another skill
  - SwitchMode            : switch enemy mode / form
  - FinishBuffsById       : remove buffs by key
"""

import json


def battle_buff_exists(battle, unit, key):
    """Check whether a unit currently has a buff by key."""
    try:
        return battle.buffs.get(unit, key) is not None
    except Exception:
        return False


class ActionNodeExecutor:
    """Executes parsed action nodes against the battle."""

    def __init__(self, battle):
        self.battle = battle
        # prefab action graphs share node semantics with the buff template
        # engine (AdvancedApplyDamage / NoSourceDamage / CreateBuff ...);
        # unknown nodes fall back to the buff engine handlers so the
        # enemy skill prefab graphs get full behaviour instead of no-ops.
        try:
            from .buff_templates import BuffTemplateEngine
            self._buff_engine = BuffTemplateEngine(battle)
        except Exception:
            self._buff_engine = None

    def parse(self, serialized_state):
        if not serialized_state or serialized_state in ("null", "[]"):
            return []
        try:
            return json.loads(serialized_state)
        except Exception:
            return []

    def execute(self, nodes, source=None, target=None, owner=None):
        """Run a node list in order; returns first blocking result."""
        for n in nodes or []:
            if not isinstance(n, dict):
                continue
            ntype = n.get("$type") or ""
            self._dispatch(ntype, n, source, target, owner)

    def _check_condition(self, cond, source, target, owner):
        """Evaluate a condition node (e.g. CheckBlocked)."""
        if not isinstance(cond, dict):
            return True
        ctype = (cond.get("$type") or "").rsplit("+", 1)[-1].split(",", 1)[0]
        if ctype == "CheckBlocked":
            u = source if cond.get("_sourceType") == "SOURCE" else target
            return bool(u is not None and getattr(u, "blocked_by", None))
        if ctype == "CheckUnitAlive":
            u = target
            return bool(u is not None and not getattr(u, "dead", False))
        if ctype == "CheckContainsBuff":
            key = cond.get("_buffKey") or cond.get("buffKey")
            u = target
            if u is None or not key:
                return False
            return battle_buff_exists(self.battle, u, key)
        if ctype == "CheckUnitCurrentMode":
            u = target if cond.get("_targetType") == "TARGET" else source
            want = cond.get("_checkCurModeIndex")
            if u is None or want is None:
                return False
            return int(getattr(u, "mode_index", 0) or 0) == int(want)
        if ctype == "FilterByAbilityFinishReason":
            want = cond.get("_finishReason")
            got = getattr(owner, "_finish_reason", "") or \
                getattr(getattr(owner, "skill", None),
                        "_finish_reason", "") or ""
            return not want or str(got) == str(want)
        if ctype == "IfNot":
            inner = cond.get("_conditionNode") or cond.get("_conditionsNode")
            return not self._check_condition(inner, source, target, owner)
        if ctype == "IfConditions":
            conds = cond.get("_conditionsNode") or []
            return all(self._check_condition(c, source, target, owner)
                       for c in conds if isinstance(c, dict))
        if ctype == "CheckAbnormalFlag":
            u = target if cond.get("_targetType") == "TARGET" else source
            fname = cond.get("_abnormalFlag") or ""
            fval = {"STUNNED": 0, "SILENCED": 12, "FROZEN": 16,
                    "LEVITATE": 25, "FEARED": 33, "PALSY": 39,
                    "DOZE": 43, "UNMOVABLE": 13}.get(fname)
            if u is None or fval is None:
                return False
            has = u.flag(int(fval))
            return (not has) if cond.get("_isUnset") else has
        if ctype == "FilterId":
            u = target if cond.get("_targetType") == "TARGET" else source
            fid = cond.get("_filterId") or ""
            uid = (getattr(u, "token_id", None) or
                   getattr(u, "enemy_key", None) or
                   getattr(u, "char_id", ""))
            has = bool(uid == fid)
            return (not has) if cond.get("_isUnset") else has
        if ctype == "IsCharacter":
            u = target if cond.get("_targetType") == "TARGET" else source
            return bool(u is not None and getattr(u, "char_id", None))
        if ctype == "CheckHeightTypeOfCharacterRootTile":
            u = target if cond.get("_targetType") == "TARGET" else source
            if u is None:
                return False
            is_high = False
            try:
                t = self.battle.map.tile(u.row, u.col)
                is_high = bool(getattr(t, "buildable_type", 1) == 2)
            except Exception:
                pass
            want_low = str(cond.get("_heightType") or "").upper() == "LOWLAND"
            has = (not is_high) if want_low else is_high
            return (not has) if cond.get("_isUnset") else has
        return True

    def _dispatch(self, ntype, node, source, target, owner):
        battle = self.battle
        short = ntype.rsplit("+", 1)[-1].split(",", 1)[0] if ntype else ""
        if short == "IfElse":
            cond = node.get("_conditionNode") or {}
            ok = self._check_condition(cond, source, target, owner)
            branch = node.get("_succeedNodes") if ok else \
                node.get("_failNodes")
            self.execute(branch, source, target, owner)
            return
        if short.startswith("Check"):
            # pure condition nodes are handled by IfElse; ignore standalone
            return
        if short == "MoveNextLevelBranch":
            branch = node.get("_branchId") or (
                owner.skill.blackboard.get("branch_id")
                if owner and getattr(owner, "skill", None) else "")
            # move the branch cursor to the next phase and schedule it
            try:
                battle.execute_branch(
                    branch, is_loop=bool(node.get("_isLoop")))
            except Exception:
                pass
            battle.emit(battle.tick, "level_branch",
                        {"branch": branch, "unit":
                         getattr(source, "inst_id", None)})
        elif short == "PickRandomBranchPhase":
            branch = (owner.skill.blackboard.get("branch_id")
                      if owner and getattr(owner, "skill", None) else "")
            try:
                battle.execute_branch_random(
                    branch,
                    not_repeat=bool(node.get("_notRepeatInOneLoop")),
                    block_game_finish=bool(node.get("_blockGameFinish")))
            except Exception:
                pass
        elif short == "InstantKill":
            if target is not None and not target.dead:
                target.take_damage(target.hp + 1.0)
                battle.emit(battle.tick, "instant_kill",
                            {"unit": target.inst_id,
                             "source": getattr(source, "inst_id", None)})
        elif short == "BlinkNode":
            if source is not None and hasattr(source, "pos_x"):
                dist = float(node.get("_distance") or node.get("distance") or 0)
                if dist:
                    # move along route direction (simplified: forward col)
                    source.pos_x = min(battle.map.cols - 1,
                                       source.pos_x + dist)
                    if hasattr(source, "_sync_tile"):
                        source._sync_tile()
        elif short.startswith("SummonEnemies"):
            key = node.get("_enemyKey") or node.get("enemyKey")
            cnt = int(node.get("_summonCount") or node.get("_count") or
                      node.get("count") or 1)
            if key:
                ri = int(getattr(source, "route_index", 0) or 0)
                spawned = []
                for _ in range(cnt):
                    en = battle.spawn_enemy_directive(
                        key, getattr(source, "row", 0),
                        getattr(source, "col", 0), route_index=ri)
                    if en is not None:
                        spawned.append(en)
                for bd in (node.get("_buffs") or []):
                    bkey = bd.get("buffKey") or bd.get("key")
                    if bkey:
                        for en in spawned:
                            battle.add_buff(en, {"key": bkey,
                                                 "template_key": bkey,
                                                 "remaining_ticks": 30 * 60,
                                                 "layers": 1,
                                                 "source": source,
                                                 "blackboard": {}})
        elif short == "TriggerEnemySkill":
            skill_key = node.get("_skillKey") or node.get("skillKey")
            if skill_key and owner is not None and hasattr(owner, "skills"):
                battle.emit(battle.tick, "skill_trigger",
                            {"unit": getattr(source, "inst_id", None),
                             "skill": skill_key})
        elif short == "SwitchMode":
            mode = node.get("_modeIndex") or node.get("_mode")
            if source is not None:
                source.mode_index = mode
                battle.emit(battle.tick, "enemy_switch_mode",
                            {"unit": source.inst_id, "mode": mode})
        elif short == "FinishBuffsById":
            key = node.get("_buffId") or node.get("buffId")
            if key and target is not None:
                battle.buffs.remove(target, key)
        elif short == "CreateEffect":
            # visual only - exposed to observers, no battle-state effect
            battle.emit(battle.tick, "skill_effect",
                        {"unit": getattr(source, "inst_id", None),
                         "effect": node.get("_effectKey") or
                                   node.get("effectKey"),
                         "target": getattr(target, "inst_id", None)})
        elif short == "PlayAudio":
            battle.emit(battle.tick, "skill_audio",
                        {"unit": getattr(source, "inst_id", None),
                         "audio": node.get("_audioSignal") or
                                  node.get("audioSignal") or
                                  node.get("_audioKey")})
        elif short == "ReleaseFromBlocker":
            tgt = target if node.get("_target") == "TARGET" else source
            if tgt is not None and getattr(tgt, "blocked_by", None):
                blk = tgt.blocked_by
                if hasattr(blk, "remove_blockee"):
                    blk.remove_blockee(tgt)
                tgt.blocked_by = None
                if getattr(tgt, "state", None) == 3:   # COMBAT -> resume
                    tgt.state = 1                       # MOVE
                battle.emit(battle.tick, "enemy_released",
                            {"unit": tgt.inst_id})
        elif short == "ChangeMotionMode":
            tgt = target if node.get("_target") == "TARGET" else source
            if tgt is not None:
                mode = {"WALK": 0, "FLY": 1, "E_NUM": 0}.get(
                    str(node.get("_motionMode")), 0)
                if node.get("_resetToDefault"):
                    mode = 0
                tgt._motion_mode = mode
                battle.emit(battle.tick, "enemy_motion_mode",
                            {"unit": tgt.inst_id, "mode": mode})
        elif short == "FinishManagedProjectiles":
            tgt = target
            if tgt is not None:
                battle.projectiles = [
                    p for p in battle.projectiles
                    if getattr(p, "target", None) is not tgt]
        elif short == "SetBodyDirection":
            # cosmetic facing - observer event only
            battle.emit(battle.tick, "enemy_facing",
                        {"unit": getattr(source, "inst_id", None),
                         "direction": node.get("_direction")})
        elif short == "IgniteAllReedTile":
            # real state change: all reed tiles switch to mode 1
            # (flaming); per-tile tile_mode_switch events are emitted
            # by battle.switch_tiles_mode
            try:
                battle.switch_tiles_mode(
                    operation="INDEX", mode_index=1,
                    tile_type="REED_TILE", specify=True,
                    source=source)
            except Exception:
                pass
            battle.emit(battle.tick, "tiles_ignite",
                        {"unit": getattr(source, "inst_id", None),
                         "tileType": "reed"})
        elif short == "SwitchDynamicBuffTileMode":
            # real battle-state change: switch dynamic buff tile modes
            # (e.g. reed -> flaming INDEX 1 / FLIP_BOOL toggle); the
            # per-tile events are emitted by battle.switch_tiles_mode
            try:
                battle.switch_tiles_mode(
                    operation=node.get("_operation"),
                    mode_index=node.get("_modeIndex"),
                    tile_type=node.get("_tileType"),
                    specify=bool(node.get("_specifyTileType")),
                    source=source)
            except Exception:
                pass
            battle.emit(battle.tick, "tile_mode_switch",
                        {"unit": getattr(source, "inst_id", None),
                         "modeIndex": node.get("_modeIndex"),
                         "operation": node.get("_operation"),
                         "tileType": node.get("_tileType")})
        elif short == "CreateTileEffect":
            battle.emit(battle.tick, "tile_effect",
                        {"unit": getattr(source, "inst_id", None),
                         "effect": node.get("_effectKey")})
        elif short == "FinishCurrentWave":
            try:
                battle.waves.finish_current_wave()
            except Exception:
                pass
            battle.emit(battle.tick, "wave_finished_early",
                        {"unit": getattr(source, "inst_id", None)})
        elif short == "ForceSetToTilePosition":
            tgt = source if node.get("_targetType") == "SOURCE" else target
            if tgt is None:
                return
            if getattr(tgt, "blocked_by", None):
                blk = tgt.blocked_by
                if hasattr(blk, "remove_blockee"):
                    blk.remove_blockee(tgt)
                tgt.blocked_by = None
            rows, cols = battle.map.rows, battle.map.cols
            best, bd = None, 1e9
            for r in range(rows):
                for c in range(cols):
                    t = battle.map.tile(r, c)
                    if t is None or not t.passable(
                            getattr(tgt, "_motion_mode", 0)):
                        continue
                    d = abs(r - tgt.row) + abs(c - tgt.col)
                    if d < bd:
                        bd, best = d, (r, c)
            if best:
                tgt.row, tgt.col = best
                tgt.pos_x, tgt.pos_y = float(best[1]), float(best[0])
                if hasattr(tgt, "_sync_tile"):
                    tgt._sync_tile()
                battle.emit(battle.tick, "enemy_teleport",
                            {"unit": tgt.inst_id, "row": best[0],
                             "col": best[1]})
        elif short == "Transport":
            a = source if node.get("_sourceType") == "SOURCE" else target
            b = target if node.get("_targetType") == "TARGET" else source
            if a is None or b is None or a is b:
                return
            ar, ac = a.row, a.col
            a.row, a.col = b.row, b.col
            b.row, b.col = ar, ac
            a.pos_x, a.pos_y = float(a.col), float(a.row)
            b.pos_x, b.pos_y = float(b.col), float(b.row)
            if hasattr(a, "_sync_tile"):
                a._sync_tile()
            if hasattr(b, "_sync_tile"):
                b._sync_tile()
            battle.emit(battle.tick, "transport",
                        {"a": getattr(a, "inst_id", None),
                         "b": getattr(b, "inst_id", None)})
        elif short == "SummonEnemiesOnTargetTile":
            key = node.get("_enemyKey") or node.get("enemyKey")
            cnt = int(node.get("_summonCount") or 1)
            tgt = target
            if key and tgt is not None:
                for _ in range(cnt):
                    battle.spawn_enemy_directive(
                        key, tgt.row, tgt.col)
        elif short == "AlwaysNext":
            # unconditional continue - the executor iterates sequentially
            pass
        elif short == "TriggerAbility":
            name = node.get("_abilityName") or node.get("abilityName")
            if name and source is not None:
                sc = getattr(source, "skill_controller", None)
                if sc is not None:
                    t = target
                    if t is None or getattr(t, "dead", False):
                        t = None
                    for s in getattr(sc, "skills", None) or []:
                        if str(getattr(s, "prefab_key", "") or "") == name:
                            try:
                                sc._start_cast((s, t))
                            except Exception:
                                pass
                            break
                battle.emit(battle.tick, "enemy_trigger_ability",
                            {"unit": getattr(source, "inst_id", None),
                             "ability": name})
        elif short == "CreateBuffToBlockee":
            bd = node.get("_buff") or {}
            bkey = bd.get("buffKey") or bd.get("key")
            blocker = getattr(source, "blocked_by", None)
            if bkey and blocker is not None and not blocker.dead:
                battle.add_buff(blocker, {
                    "key": bkey, "template_key": bkey,
                    "remaining_ticks": 30 * 60, "layers": 1,
                    "source": source, "blackboard": {}})
        elif short == "TriggerBuffsByKeys":
            keys = node.get("_buffKeys") or []
            tgt = target if node.get("_targetType") == "TARGET" else source
            for b in list(getattr(tgt, "buffs", None) or []):
                if b.get("key") in keys:
                    try:
                        battle.buffs._fire(tgt, b, "ON_BUFF_TRIGGER",
                                           source=b.get("source"))
                    except Exception:
                        pass
        elif short == "EmitProjectile":
            pkey = node.get("_projectileKey") or node.get("projectileKey")
            if pkey and target is not None:
                try:
                    from .consts import DamageType
                    battle.spawn_projectile(source, target, pkey,
                                            DamageType.PHYSICAL,
                                            atk_scale=1.0)
                except Exception:
                    pass
        elif short == "InterruptAbility":
            name = node.get("_abilityName")
            sc = getattr(source, "skill_controller", None)
            if sc is not None and getattr(sc, "casting", None) is not None:
                if node.get("_useCurrentAbility") or not name or \
                        str(getattr(getattr(sc.casting, "skill", None),
                                    "prefab_key", "") or "") == name:
                    try:
                        sc.casting.finished = True
                    except Exception:
                        pass
        elif short == "DamageViaMaxHpRatio":
            tgt = target if node.get("_targetType") == "TARGET" else source
            if tgt is not None and not tgt.dead:
                ratio = 1.0
                for rk in ("_ratio", "_hpRatio", "_maxHpRatio"):
                    if node.get(rk) is not None:
                        try:
                            ratio = float(node.get(rk))
                        except (TypeError, ValueError):
                            pass
                        break
                from .consts import DamageType
                dt = {"PURE": DamageType.TRUE,
                      "PHYSICAL": DamageType.PHYSICAL,
                      "MAGICAL": DamageType.MAGICAL}.get(
                          str(node.get("_damageType") or ""),
                          DamageType.TRUE)
                battle.apply_damage(tgt, float(tgt.max_hp) * ratio, dt,
                                    source=source)
        elif short == "Withdraw":
            tgt = source
            if tgt is not None and not tgt.dead:
                if getattr(tgt, "side", 0) == 0:
                    # enemy-class unit: withdraw = mark finished
                    tgt.dead = True
                    try:
                        battle.buffs.on_owner_finish(tgt)
                    except Exception:
                        pass
                else:
                    try:
                        battle.withdraw(tgt.inst_id)
                    except Exception:
                        pass
        elif short == "ModifyCost":
            bb = {}
            sk = getattr(owner, "skill", None)
            if sk is not None:
                bb = getattr(sk, "blackboard", {}) or {}
            cost = bb.get(node.get("_blackboardKey") or "cost")
            try:
                battle.battle_cost_add(float(cost or 0.0))
            except (TypeError, ValueError):
                pass
        elif short == "AssignValueToBB":
            bbkey = node.get("_blackboardKey") or node.get("blackboardKey")
            if bbkey and owner is not None and hasattr(owner, "skill"):
                try:
                    owner.skill.blackboard[bbkey] = node.get("_value")
                except Exception:
                    pass
        elif short in ("SummonEnemiesWithRuntimeNearestEndPointRoute",
                       "SummonEnemyWithRuntimeRoute",
                       "SummonTrackingEnemyWithFixedDirection",
                       "SummonEnemiesFollowBranchRoute"):
            key = node.get("_enemyKey") or node.get("enemyKey")
            if not key:
                bb = {}
                sk = getattr(owner, "skill", None)
                if sk is not None:
                    bb = getattr(sk, "blackboard", {}) or {}
                key = bb.get("enemy_key") or bb.get("summon_enemy_key")
            cnt = int(node.get("_summonCount") or node.get("_count") or 1)
            if key:
                ri = int(getattr(source, "route_index", 0) or 0)
                for _ in range(cnt):
                    battle.spawn_enemy_directive(
                        key, getattr(source, "row", 0),
                        getattr(source, "col", 0), route_index=ri)
        elif short == "RebuildCharacterOnRandomTile":
            tgt = target if node.get("_target") == "TARGET" else source
            if tgt is not None:
                # revive the target on the nearest passable tile
                rows, cols = battle.map.rows, battle.map.cols
                best = None
                for r in range(rows):
                    for c in range(cols):
                        t = battle.map.tile(r, c)
                        if t is None or not t.passable(
                                getattr(tgt, "_motion_mode", 0)):
                            continue
                        best = (r, c)
                        break
                    if best:
                        break
                if best:
                    tgt.row, tgt.col = best
                    tgt.pos_x, tgt.pos_y = float(best[1]), float(best[0])
                    tgt.dead = False
                    tgt.hp = tgt.max_hp
                    if hasattr(tgt, "_sync_tile"):
                        tgt._sync_tile()
                bd = node.get("_buff") or {}
                bkey = bd.get("buffKey") or bd.get("key")
                if bkey:
                    battle.add_buff(tgt, {"key": bkey,
                                          "template_key": bkey,
                                          "remaining_ticks": 30 * 60,
                                          "layers": 1,
                                          "source": source,
                                          "blackboard": {}})
        elif short == "FinishSeveralBuffsById":
            keys = node.get("_buffKeys") or []
            tgt = target if node.get("_targetType") == "TARGET" else source
            for k in keys:
                try:
                    battle.buffs.remove(tgt, k)
                except Exception:
                    pass
        elif short == "TriggerAbilityUseSelector":
            name = node.get("_abilityName") or node.get("abilityName")
            if name and source is not None:
                sc = getattr(source, "skill_controller", None)
                if sc is not None:
                    t = target
                    if t is None or getattr(t, "dead", False):
                        t = None
                    for s in getattr(sc, "skills", None) or []:
                        if str(getattr(s, "prefab_key", "") or "") == name:
                            try:
                                sc._start_cast((s, t))
                            except Exception:
                                pass
                            break
        elif short == "AssignBuffBlackboard":
            bbkey = node.get("_blackboardKey") or node.get("blackboardKey")
            bkey = node.get("_buffKey") or node.get("buffKey")
            tgt = target if node.get("_targetType") == "TARGET" else source
            val = node.get("_defaultValue")
            if bkey and tgt is not None:
                rec = battle.buffs.get(tgt, bkey)
                if rec is not None and bbkey:
                    rec.setdefault("blackboard", {})[bbkey] = \
                        rec.get("value", val) if val is None else val
        elif short == "CreateNoSourceBuff":
            bd = node.get("_buff") or {}
            bkey = bd.get("buffKey") or bd.get("key")
            tgt = target if node.get("_targetType") == "TARGET" else source
            if bkey and tgt is not None:
                battle.add_buff(tgt, {"key": bkey,
                                      "template_key": bkey,
                                      "remaining_ticks": 30 * 60,
                                      "layers": 1,
                                      "source": None,
                                      "blackboard": {}})
        elif short == "CreateBuffOnTileInRange":
            bd = node.get("_buff") or {}
            bkey = bd.get("buffKey") or bd.get("key")
            if bkey:
                for e in list(battle.get_enemies()):
                    if e.dead:
                        continue
                    if abs(e.row - source.row) <= 1 and \
                            abs(e.col - source.col) <= 1:
                        battle.add_buff(e, {"key": bkey,
                                            "template_key": bkey,
                                            "remaining_ticks": 30 * 60,
                                            "layers": 1,
                                            "source": source,
                                            "blackboard": {}})
        elif short == "ChangeEnemyRouteMotionMode":
            tgt = target if node.get("_target") == "TARGET" else source
            if tgt is not None:
                want = str(node.get("_motionMode") or "WALK").upper()
                new_mode = 0 if want == "WALK" else 1
                tgt._motion_mode = new_mode
                if hasattr(tgt, "init_route"):
                    try:
                        # 用新运动模式重建流场；init_route 会重置
                        # _motion_mode，重建后恢复目标模式
                        tgt.init_route(battle.map)
                    except Exception:
                        pass
                tgt._motion_mode = new_mode
        elif short == "UpdateEnemyCurrentTile":
            tgt = target if node.get("_targetType") == "TARGET" else source
            if tgt is not None and hasattr(tgt, "_sync_tile"):
                try:
                    tgt._sync_tile()
                except Exception:
                    pass
        elif short == "CreateBuffInCircleRange":
            bd = node.get("_buff") or {}
            bkey = bd.get("buffKey") or bd.get("key")
            radius = float(node.get("_radius") or 1.0)
            if bkey:
                for e in list(battle.get_enemies()):
                    if e.dead:
                        continue
                    if abs(e.row - source.row) <= radius and \
                            abs(e.col - source.col) <= radius:
                        battle.add_buff(e, {"key": bkey,
                                            "template_key": bkey,
                                            "remaining_ticks": 30 * 60,
                                            "layers": 1,
                                            "source": source,
                                            "blackboard": {}})
        elif short == "EmitProjectileAlongEnemyRoute":
            pkey = node.get("_projectileKey") or node.get("projectileKey")
            if pkey and target is not None:
                try:
                    from .consts import DamageType
                    battle.spawn_projectile(source, target, pkey,
                                            DamageType.PHYSICAL,
                                            atk_scale=1.0)
                except Exception:
                    pass
        elif short == "EnemyTracePointAwayFromTarget":
            tgt = target if node.get("_target") == "TARGET" else source
            other = source if tgt is target else target
            dist = float(node.get("_distance") or 1.0)
            if tgt is not None and other is not None:
                dr = 0 if tgt.row == other.row else \
                    (1 if tgt.row > other.row else -1)
                dc = 0 if tgt.col == other.col else \
                    (1 if tgt.col > other.col else -1)
                if dr or dc:
                    try:
                        battle.displace(tgt, dr, dc, dist, source=source,
                                        kind="effect")
                    except Exception:
                        pass
        elif short == "AssignAttributeToBB":
            bbkey = node.get("_blackboardKey")
            if bbkey and owner is not None and hasattr(owner, "skill"):
                u = source if node.get("_targetType") == "SOURCE" else target
                if u is not None:
                    at = str(node.get("_attributeType") or "ATK")
                    key = {"ATK": "atk", "DEF": "def",
                           "MAX_HP": "maxHp"}.get(at, "atk")
                    try:
                        owner.skill.blackboard[bbkey] = float(
                            u.attributes.get(key) or 0.0)
                    except Exception:
                        pass
        elif short == "AssignMirrorTileToBB":
            bbkey = node.get("_blackboardKey")
            if bbkey and owner is not None and hasattr(owner, "skill"):
                u = target if node.get("_targetType") == "TARGET" else source
                if u is not None:
                    try:
                        owner.skill.blackboard[bbkey + "_row"] = u.row
                        owner.skill.blackboard[bbkey + "_col"] = \
                            battle.map.cols - 1 - u.col
                    except Exception:
                        pass
        elif short == "AOEDamageFromProjectile":
            tgt = target
            if tgt is not None:
                from .consts import DamageType
                dt = {"MAGICAL": DamageType.MAGICAL,
                      "PHYSICAL": DamageType.PHYSICAL,
                      "PURE": DamageType.TRUE}.get(
                          str(node.get("_damageType") or ""),
                          DamageType.PHYSICAL)
                scale = 1.0
                bb = {}
                sk = getattr(owner, "skill", None)
                if sk is not None:
                    bb = getattr(sk, "blackboard", {}) or {}
                try:
                    scale = float(bb.get("atk_scale") or 1.0)
                except (TypeError, ValueError):
                    pass
                atk = 0.0
                if getattr(source, "attributes", None) is not None:
                    try:
                        atk = float(source.attributes.get("atk") or 0.0)
                    except (TypeError, ValueError):
                        pass
                for e in list(battle.get_enemies()):
                    if e.dead:
                        continue
                    if abs(e.row - tgt.row) <= 1 and \
                            abs(e.col - tgt.col) <= 1:
                        battle.apply_damage(e, atk * scale, dt,
                                            source=source)
        elif short == "Main15TryNextPrtsAction":
            # 主线 15 章 PRTS 动作调度：推进子动作管线；无完整队列时
            # 保持事件暴露（battle.execute_branch 由 MoveNextLevelBranch
            # 驱动）。
            prts = getattr(battle, "prts", None)
            if prts is not None:
                prts.TryNextSubAction(
                    bool(node.get("_doNextWhenSuccess", True)),
                    bool(node.get("_forceNext", False)))
            battle.emit(battle.tick, "prts_try_next",
                        {"unit": getattr(source, "inst_id", None),
                         "force": bool(node.get("_forceNext"))})
        elif short == "LogExtraBattleInfo":
            key = node.get("_key") or ""
            if key:
                battle.stats.setdefault("extraInfo", {})
                cur = battle.stats["extraInfo"].get(key, 0)
                try:
                    cur += int(node.get("_additionValue") or 1)
                except (TypeError, ValueError):
                    cur += 1
                battle.stats["extraInfo"][key] = cur
            battle.emit(battle.tick, "log_extra_info",
                        {"unit": getattr(source, "inst_id", None),
                         "key": key})
        else:
            # fallback: delegate to the buff template engine handlers
            # (source/target/blackboard adapted to the buff ctx)
            if self._buff_engine is not None:
                handler = getattr(self._buff_engine, "_n_" + short, None)
                if handler is not None:
                    try:
                        u = source if source is not None else target
                        bb = {}
                        sk = getattr(owner, "skill", None)
                        if sk is not None:
                            bb = dict(getattr(sk, "blackboard", {}) or {})
                        self._buff_engine.run_actions(
                            u, [node],
                            {"owner": u, "source": source,
                             "target": target, "damage": None, "bb": bb}, 0)
                    except Exception:
                        pass
