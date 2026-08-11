"""Enemy AI: combines skills, targeting and buffs for one enemy per tick."""

from .consts import DamageType, EnemyState, resolve_attack_range


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
    if enemy.state in (EnemyState.DEAD, EnemyState.REACH_EXIT,
                       EnemyState.DISAPPEAR):
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
        t = pa.get("target")
        if (t is None or getattr(t, "dead", False) or
                enemy.flag(11) or enemy.flag(31)):
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


def _resolve_pending_attack(enemy, battle, pa):
    """Hit frame reached: melee deals damage now, ranged launches the
    projectile (which then flies to the target)."""
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
