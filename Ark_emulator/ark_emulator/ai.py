"""Enemy AI: combines skills, targeting and buffs for one enemy per tick."""

from .consts import DamageType, EnemyState, resolve_attack_range


# These enemies use their normal attack cycle to heal hostiles instead of
# attacking operators.  Their database rangeRadius is consequently a healing
# target radius; treating it as an offensive radius makes it look like a
# full-map attack (Mephisto has rangeRadius=20).
_NORMAL_HEAL_TARGET_LIMITS = {
    "enemy_1507_mephi": 3,
}


def update_enemy_ai(enemy, battle, dt=1.0 / 30.0):
    """Per-tick enemy behaviour driver (called by BattleController).

    Order:
      1. skill controller tick (CD + active ability timeline)
      2. attack timer + normal attack
      3. target selection for abilities
    """
    if enemy.dead:
        return
    # defected enemies (SwitchSide -> ALLY) stop moving / attacking
    if getattr(enemy, "side", 0) == 1:
        if enemy._pending_attack is not None:
            enemy._pending_attack = None
        return
    if enemy.state == EnemyState.BORN:
        enemy.update_born(dt)
        return
    if enemy.state in (EnemyState.DEAD, EnemyState.REACH_EXIT):
        return
    if enemy.state == EnemyState.DISAPPEAR:
        enemy.update_movement(dt)
        return
    # controlled states (stun/frozen/...): no movement/attack/skill
    if not enemy.controllable_state() or enemy.flag(43):   # DOZE sleeps
        enemy._pending_attack = None
        if enemy.skill_controller is not None:
            enemy.skill_controller.update(dt)
        return
    # pending attack windup: damage lands at the animation hit frame
    if enemy._pending_attack is not None:
        pa = enemy._pending_attack
        if pa.get("heal"):
            targets = [t for t in pa.get("targets", [])
                       if t is not None and not getattr(t, "dead", False)]
            pa["targets"] = targets
            invalid = not targets
        else:
            t = pa.get("target")
            invalid = t is None or getattr(t, "dead", False)
        if invalid or enemy.flag(11) or enemy.flag(31):
            enemy._pending_attack = None
        else:
            pa["remaining"] -= 1
            if pa["remaining"] <= 0:
                _resolve_pending_attack(enemy, battle, pa)
                enemy._pending_attack = None
    # skill controller
    if enemy.skill_controller is not None:
        enemy.skill_controller.update(dt)
    # displacement (push/pull) takes priority over movement and attacks
    if enemy.displacement is not None:
        done = enemy.update_displacement(dt)
        if done:
            battle.on_displacement_end(enemy)
        return
    # movement (only when unblocked and moving)
    if enemy.state in (EnemyState.MOVE,) and enemy.blocked_by is None:
        # skill conveyor tiles (e.g. Thumpy S3 belt) override route
        # movement: the pull is applied in battle._tick_skill_tiles
        conv = battle.skill_tile_conveyor_at(enemy.row, enemy.col) \
            if hasattr(battle, "skill_tile_conveyor_at") else None
        if conv is not None:
            mass = float(enemy.attributes.get("massLevel") or 0.0)
            mass_max = float((conv.get("bb") or {}).get("mass_level") or 4.0)
            if mass <= mass_max:
                return
        reached = enemy.update_movement(dt)
        if reached:
            battle.on_enemy_reach_exit(enemy)
            return
    # attack timer with precise hit frame (damage lands at
    # hit_frame_ratio * interval, i.e. OnAttack event time within animation)
    interval = enemy.attributes.attack_interval()
    enemy.attack_timer -= dt
    if enemy.attack_timer <= 0:
        took_over = False
        if enemy.skill_controller is not None:
            took_over = enemy.skill_controller.on_attack_timer_zero()
        if not took_over and not enemy.flag(11) and not enemy.flag(31):
            # DISARMED / DISARMED_COMBAT: normal attack disabled
            _start_normal_attack(enemy, battle, interval)
        enemy.attack_timer += interval


def _start_normal_attack(enemy, battle, interval):
    """Begin a normal attack: lock a target and start the windup. Damage
    (or the projectile launch) lands at the spine OnAttack hit frame,
    i.e. ``hit_frame_ratio * interval`` after the attack starts."""
    healer_target_limit = _normal_heal_target_limit(enemy)
    if healer_target_limit:
        _start_normal_heal(enemy, battle, interval, healer_target_limit)
        return

    radius = resolve_attack_range(enemy.attributes.get("rangeRadius"))
    try:
        battle._dispatch_buff_events(enemy, "ON_BEFORE_ATTACK",
                                     source=enemy)
    except Exception:
        pass
    # a blocked enemy always attacks the unit blocking it
    if enemy.blocked_by is not None and getattr(
            enemy.blocked_by, "side", 0) == 1 and not enemy.blocked_by.dead:
        target = enemy.blocked_by
    else:
        ops = [o for o in battle.get_operators()
               if not o.dead and not o.in_deploy_anim(battle.tick)]
        if not ops:
            return
        from .targeting import SEARCH_TARGET_TICK, search_gate
        target = search_gate(
            enemy, battle,
            lambda: min(ops, key=lambda o: _dist2(enemy, o)))
        if target not in ops:
            # cached target became invalid (died / deploy animation):
            # force a fresh search now (Search(force))
            target = search_gate(
                enemy, battle,
                lambda: min(ops, key=lambda o: _dist2(enemy, o)),
                force=True)
        if _dist2(enemy, target) > radius:
            return
    dist = _dist2(enemy, target)
    ranged = radius > 1.5 and dist > 1.0
    ratio = float(enemy.hit_frame_ratio or 0.5)
    frames = max(1, int(round(interval * ratio * 30.0)))
    # spell-on: normal attack started; buff listeners react now
    # (e.g. \u9152\u795e T2: 70 sanity EP to the attacker in her range)
    battle.on_enemy_ability_spell_on(enemy)
    enemy._pending_attack = {
        "target": target,
        "remaining": frames,
        "ranged": ranged,
    }


def _normal_heal_target_limit(enemy):
    key = str(getattr(enemy, "enemy_key", "") or "").split("#", 1)[0]
    return _NORMAL_HEAL_TARGET_LIMITS.get(key, 0)


def _start_normal_heal(enemy, battle, interval, target_limit):
    """Begin an enemy healer's normal action.

    Targets are locked at animation start, matching normal attack targeting.
    Only wounded allied enemies are valid; Mephisto cannot turn his global
    healing radius into an operator attack radius.
    """
    radius = resolve_attack_range(enemy.attributes.get("rangeRadius"))
    candidates = [
        target for target in battle.get_enemies()
        if target is not enemy
        and not getattr(target, "dead", False)
        and float(getattr(target, "hp", 0.0))
        < float(getattr(target, "max_hp", 0.0)) - 1e-9
        and _dist2(enemy, target) <= radius
    ]
    if not candidates:
        return
    # Native healers prioritise the lowest HP ratio.  Stable distance/instance
    # keys keep selection deterministic when ratios are equal.
    candidates.sort(key=lambda target: (
        float(target.hp) / max(1.0, float(target.max_hp)),
        _dist2(enemy, target),
        int(getattr(target, "inst_id", 0)),
    ))
    targets = candidates[:max(1, int(target_limit))]
    try:
        battle._dispatch_buff_events(enemy, "ON_BEFORE_ATTACK", source=enemy)
    except Exception:
        pass
    battle.on_enemy_ability_spell_on(enemy)
    ratio = float(enemy.hit_frame_ratio or 0.5)
    frames = max(1, int(round(interval * ratio * 30.0)))
    enemy._pending_attack = {
        "targets": targets,
        "remaining": frames,
        "heal": True,
    }


def _resolve_pending_attack(enemy, battle, pa):
    """Hit frame reached: melee deals damage now, ranged launches the
    projectile (which then flies to the target)."""
    if pa.get("heal"):
        amount = max(0.0, float(enemy.attributes.get("atk") or 0.0))
        targets = [target for target in pa.get("targets", [])
                   if target is not None and not getattr(target, "dead", False)]
        for target in targets:
            battle.apply_heal(target, amount, source=enemy)
        battle.emit(battle.tick, "attack", {
            "unit": enemy.inst_id,
            "targets": [target.inst_id for target in targets],
            "type": "enemy_heal_hit",
            "amount": round(amount, 3),
        })
        return

    target = pa.get("target")
    if target is None or getattr(target, "dead", False):
        return
    if pa.get("ranged"):
        battle.spawn_projectile(enemy, target,
                                f"enemy_{enemy.enemy_key}_atk",
                                DamageType.PHYSICAL)
    else:
        battle.enemy_normal_attack(enemy, target)


def _dist2(a, b):
    return ((a.pos_x - b.pos_x) ** 2 + (a.pos_y - b.pos_y) ** 2) ** 0.5
