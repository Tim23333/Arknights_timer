# -*- coding: utf-8 -*-
"""More subclass trait tests:
- geek (\u602a\u6770): HP drains 1% maxHp per second, never below 1.
- unyield (\u4e0d\u5c48\u8005): cannot be healed by allied heal actions.
- fortress (\u8981\u585e): ranged 3x3 splash while not blocking, melee
  swing at the blocked target while blocking.
- underminer (\u524a\u5f31\u8005): basic attacks deal MAGICAL damage.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _spawn(b, row, col, hp=99999.0, defense=0.0, mr=0.0):
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": defense,
                       "magicResistance": mr, "moveSpeed": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(b, op, target, **kw):
    b._operator_attack(op, target, op.attributes.attack_interval(), **kw)
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_geek_hp_drain_and_min_hp():
    sim, b = _battle()
    assert b.deploy("char_225_haak", 2, 3)[0]      # \u963f (geek)
    op = b.operators[0]
    assert op.trait_system.is_geek()
    assert abs(op.trait_system.geek_drain_ratio() - 0.01) < 1e-9
    hp0 = float(op.hp)
    b._trait_tick(op, 1.0)
    assert abs((hp0 - op.hp) - hp0 * 0.01) < 0.01
    op.hp = 5.0
    b._trait_tick(op, 1.0)
    assert op.hp == 1.0
    assert not op.dead
    evs = [x for x in b.events.snapshot_events()
           if x["type"] == "trait_hp_drain"
           and (x.get("data") or {}).get("unit") == op.inst_id]
    assert evs


def test_unyield_cannot_be_healed():
    sim, b = _battle()
    assert b.deploy("char_163_hpsts", 3, 3)[0]     # \u706b\u795e (unyield)
    op = b.operators[0]
    assert op.trait_system.is_unyield()
    assert op.heal_free()
    op.hp = op.max_hp * 0.5
    before = op.hp
    healed = b.apply_heal(op, 500.0, source=op)
    assert healed == 0.0
    assert op.hp == before
    # an explicit heal-free-ignoring heal still works (self-heal path)
    healed = b.apply_heal(op, 200.0, source=op, ignore_heal_free=True)
    assert abs(healed - 200.0) < 0.01


def test_fortress_ranged_splash_when_not_blocking():
    sim, b = _battle()
    assert b.deploy("char_431_ashlok", 3, 3)[0]    # \u7070\u6beb (fortress)
    op = b.operators[0]
    assert op.trait_system.is_fortress()
    atk = float(op.attributes.get("atk"))
    assert atk > 0
    main = _spawn(b, 3, 6)
    near = _spawn(b, 2, 6)
    far = _spawn(b, 6, 6)
    _land_attack(b, op, main, fortress_splash=True)
    assert abs((99999.0 - main.hp) - atk) < 0.01, main.hp
    assert abs((99999.0 - near.hp) - atk) < 0.01, near.hp
    assert far.hp == 99999.0
    assert any(x["type"] == "attack"
               and (x.get("data") or {}).get("type") == "fortress_splash"
               for x in b.events.snapshot_events())


def test_fortress_scheduling_splash_without_blocker():
    """Not blocking: the attack scheduler emits the ranged splash attack
    on an in-range target."""
    sim, b = _battle()
    assert b.deploy("char_431_ashlok", 3, 3)[0]
    op = b.operators[0]
    atk = float(op.attributes.get("atk"))
    main = _spawn(b, 3, 6)
    near = _spawn(b, 2, 6)
    far = _spawn(b, 6, 6)
    for _ in range(120):
        b.tick_once()
        if any(x["type"] == "attack"
               and (x.get("data") or {}).get("type") == "fortress_splash"
               for x in b.events.snapshot_events()):
            break
    assert abs((99999.0 - main.hp) - atk) < 0.01, main.hp
    assert abs((99999.0 - near.hp) - atk) < 0.01, near.hp
    assert far.hp == 99999.0


def test_fortress_melee_when_blocking():
    sim, b = _battle()
    assert b.deploy("char_431_ashlok", 3, 3)[0]
    op = b.operators[0]
    atk = float(op.attributes.get("atk"))
    blk = _spawn(b, 3, 4)
    other = _spawn(b, 2, 4)
    blk.blocked_by = op
    op.add_blockee(blk)
    _land_attack(b, op, blk)
    assert abs((99999.0 - blk.hp) - atk) < 0.01, blk.hp
    assert other.hp == 99999.0


def test_underminer_magical_damage():
    sim, b = _battle()
    assert b.deploy("char_174_slbell", 2, 3)[0]    # \u521d\u96ea (underminer)
    op = b.operators[0]
    assert b._char_damage_type(op) == DamageType.MAGICAL
    atk = float(op.attributes.get("atk"))
    assert atk > 0
    e = _spawn(b, 2, 4, defense=500.0)
    _land_attack(b, op, e)
    # underminer is ranged: damage lands when the projectile arrives
    for _ in range(90):
        b.tick_once()
        if not b.projectiles:
            break
    assert abs((99999.0 - e.hp) - atk) < 0.01, (e.hp, atk)
def test_hookmaster_prefers_blocked_target():
    """\u94a9\u7d22\u5e08 hookmaster: basic attack prefers an enemy it
    blocks (even out of attack range); the trait flag is exposed."""
    sim, b = _battle()
    assert b.deploy("char_236_rope", 3, 3)[0]      # \u6697\u7d22 (hookmaster)
    op = b.operators[0]
    assert op.trait_system._flags.get("preferBlocked")
    assert op.trait_system._flags.get("canAttackAir")
    blk = _spawn(b, 3, 4)
    free = _spawn(b, 2, 4)
    blk.blocked_by = op
    op.add_blockee(blk)
    from ark_emulator.targeting import HateSystem
    t = HateSystem(b).operator_target(op)
    assert t is blk
    _land_attack(b, op, t)
    assert abs((99999.0 - blk.hp) - float(op.attributes.get("atk"))) < 0.01
    assert free.hp == 99999.0


def test_mercenary_prefer_blocked_flag():
    sim, b = _battle()
    assert b.deploy("char_394_hadiya", 3, 3)[0]    # \u54c8\u8482\u5a25 (mercenary)
    op = b.operators[0]
    assert op.trait_system._flags.get("preferBlocked")
def test_dollkeeper_swap_and_restore():
    """\u5080\u56e1\u5e08 dollkeeper: a lethal hit swaps the operator into
    its <\u66ff\u8eab> (blockCnt 0, doll stats), and after the trait
    duration the body returns with full HP and 0 SP."""
    sim, b = _battle()
    assert b.deploy("char_4016_kazema", 3, 3)[0]   # \u98ce\u4e38 (dollkeeper)
    op = b.operators[0]
    assert op.trait_system.is_dollkeeper()
    assert abs(op.trait_system.doll_duration() - 20.0) < 1e-9
    base_hp = float(op.max_hp)
    base_block = float(op.attributes.get("blockCnt"))
    for _ in range(20):
        b.tick_once()                               # finish deploy animation
    b.apply_damage(op, 999999.0, DamageType.PHYSICAL, source=op)
    assert op._doll_state and not op.dead
    assert op.attributes.get("blockCnt") == 0.0
    assert abs(op.max_hp - 1109.0) < 0.01           # \u7eb8\u5076 stats
    assert op.hp == op.max_hp
    op._doll_remaining = 10
    for _ in range(12):
        b.tick_once()
    assert not op._doll_state
    assert abs(op.max_hp - base_hp) < 0.01
    assert op.hp == op.max_hp
    assert op.sp == 0.0
    assert abs(float(op.attributes.get("blockCnt")) - base_block) < 0.01
    evs = [x for x in b.events.snapshot_events()
           if x["type"] == "doll_state"
           and (x.get("data") or {}).get("unit") == op.inst_id]
    assert [e["data"].get("type") for e in evs] == ["swap", "restore"]


def test_dollkeeper_lethal_while_doll_defeats():
    sim, b = _battle()
    assert b.deploy("char_4016_kazema", 3, 3)[0]
    op = b.operators[0]
    for _ in range(20):
        b.tick_once()
    b.apply_damage(op, 999999.0, DamageType.PHYSICAL, source=op)
    assert op._doll_state and not op.dead
    b.apply_damage(op, 999999.0, DamageType.PHYSICAL, source=op)
    assert op.dead


def test_guardian_skill_heals_ally():
    """\u5b88\u62a4\u8005 guardian: the heal skill (nearl S1 \u6025\u6551)
    heals the wounded ally in range for atk x heal_scale."""
    sim, b = _battle()
    assert b.deploy("char_148_nearl", 3, 3)[0]      # \u4e34\u5149 (guardian)
    op = b.operators[0]
    assert op.sub_profession_id == "guardian"
    assert b.deploy("char_127_estell", 3, 4)[0]     # \u827e\u4e1d\u6cf0\u5c14
    ally = b.operators[1]
    ally.hp = ally.max_hp * 0.4
    sc = op.skill_controller
    s1 = next(s for s in sc.skills if s.skill_id == "skchr_nearl_1")
    op.sp = s1.sp_cost
    ok, _ = sc.activate(0)
    assert ok
    for _ in range(30):
        b.tick_once()
    assert ally.hp > ally.max_hp * 0.4
    assert any(x["type"] == "heal"
               and (x.get("data") or {}).get("target") == ally.inst_id
               and (x.get("data") or {}).get("amount", 0) > 0
               for x in b.events.snapshot_events())
def test_reaperrange_all_range_and_front_row_150():
    """\u6536\u5272\u8005\uff08\u8fdc\uff09: basic attack hits EVERY enemy in
    range; the front-row strip takes 150% ATK, others take 100%."""
    sim, b = _battle()
    assert b.deploy("char_440_pinecn", 2, 3)[0]    # \u677e\u679c (reaperrange)
    op = b.operators[0]
    assert op.trait_system.is_reaperrange()
    atk = float(op.attributes.get("atk"))
    assert atk > 0
    front = _spawn(b, 2, 5)
    side = _spawn(b, 1, 4)
    far = _spawn(b, 6, 6)
    _land_attack(b, op, front)
    # ranged: wait for the projectiles to land
    for _ in range(90):
        b.tick_once()
        if not b.projectiles:
            break
    assert abs((99999.0 - front.hp) - atk * 1.5) < 0.01, (front.hp, atk)
    assert abs((99999.0 - side.hp) - atk) < 0.01, (side.hp, atk)
    assert far.hp == 99999.0
def test_snapshot_serializable_with_buff_sources():
    """Live-server detail output: snapshots must be JSON-serializable even
    when buffs carry unit objects as sources (gravel deploy talent)."""
    import json
    sim, b = _battle()
    assert b.deploy("char_237_gravel", 3, 3)[0]    # \u783e deploy buffs
    for _ in range(20):
        b.tick_once()
    op = b.operators[0]
    assert op.buffs and any(b.get("source") is op for b in op.buffs)
    snap = sim.snapshot()
    body = json.dumps(snap)
    assert body
    d = [x for x in snap["deployed"] if x.get("instId") == op.inst_id][0]
    for buff in d["buffs"]:
        src = buff.get("source")
        assert src is None or isinstance(src, int), src
def test_skywalker_liftoff_blocks_flying():
    """\u4fa6\u5bdf\u8005 skywalker: while a skill is active (liftoff) the
    operator can block flying enemies; normal operators cannot."""
    sim, b = _battle()
    assert b.deploy("char_4165_ctrail", 3, 3)[0]    # \u4e91\u8ff9 (skywalker)
    op = b.operators[0]
    for _ in range(20):
        b.tick_once()
    assert b._op_liftoff(op)
    air = _spawn(b, 3, 3)
    air.is_flying = True
    air.set_flag(3, 10 ** 9)
    b._update_blocking()
    assert air.blocked_by is op
    assert air in op.blocked_enemies
    # without liftoff the flying enemy is released again
    sc = getattr(op, "skill_controller", None)
    if sc is not None and sc.active is not None:
        try:
            sc.interrupt_active()
        except Exception:
            pass
    assert not b._op_liftoff(op)
    b._update_blocking()
    assert air.blocked_by is None
def test_traper_deploys_and_triggers_trap():
    """\u9677\u9631\u5e08 traper (robin S1): the skill deploys a trap token
    in range; an enemy stepping on it takes atk x atk_scale physical damage,
    is bound (UNMOVABLE) for `constraint` seconds, and the trap is consumed."""
    sim, b = _battle()
    assert b.deploy("char_451_robin", 2, 3)[0]     # \u7f57\u5bbe (traper)
    op = b.operators[0]
    sc = op.skill_controller
    s1 = next(s for s in sc.skills if s.skill_id == "skchr_robin_1")
    op.sp = s1.sp_cost
    ok, _ = sc.activate(0)
    assert ok
    for _ in range(10):
        b.tick_once()
    traps = [t for t in b.tokens if t.token_id == "token_10013_robin_mine"]
    assert traps, "trap token must be deployed"
    trap = traps[0]
    atk = float(trap.attributes.get("atk"))
    e = _spawn(b, trap.row, trap.col, hp=5000.0)
    e.state = EnemyState.MOVE
    hp0 = e.hp
    for _ in range(3):
        b.tick_once()
    assert abs((hp0 - e.hp) - atk * 2.0) < 0.01, (e.hp, atk)
    assert e.flag(13)                              # UNMOVABLE bind
    assert all(t.token_id != "token_10013_robin_mine" for t in b.tokens)
    assert any(x["type"] == "trap_fired"
               and (x.get("data") or {}).get("target") == e.inst_id
               for x in b.events.snapshot_events())
def test_alchemist_s1_dot_and_debuff():
    """\u70bc\u91d1\u5e08 alchemist (tinman S1): the alchemy unit applies
    tinman_s_1[dot] + atk debuff and deals atk x atk_scale periodic damage
    to every enemy inside projectile_range of the landing tile."""
    sim, b = _battle()
    assert b.deploy("char_4151_tinman", 2, 3)[0]    # \u9521\u4eba (alchemist)
    op = b.operators[0]
    assert op.sub_profession_id == "alchemist"
    atk = float(op.attributes.get("atk"))
    e = _spawn(b, 2, 5, hp=50000.0)
    near = _spawn(b, 1, 4, hp=50000.0)
    far = _spawn(b, 6, 6, hp=50000.0)
    for u in (e, near, far):
        u.state = EnemyState.MOVE
    sc = op.skill_controller
    s1 = next(s for s in sc.skills if s.skill_id == "skchr_tinman_1")
    op.sp = s1.sp_cost
    ok, _ = sc.activate(0)
    assert ok
    hp0, nhp0 = e.hp, near.hp
    for _ in range(90):
        b.tick_once()
    assert any(x.get("key") == "tinman_s_1[dot]" for x in e.buffs)
    assert any(x.get("key") == "tinman_s_1[dot]" for x in near.buffs)
    assert not any(x.get("key") == "tinman_s_1[dot]" for x in far.buffs)
    assert hp0 - e.hp > atk * 0.3 * 1.0            # periodic atk_scale damage
    assert nhp0 - near.hp > 0.0                     # zone neighbour DoT
    assert far.hp == 50000.0


def test_alchemist_s2_zone_heal_vs_damage():
    """\u70bc\u91d1\u5e08 alchemist (tinman S2): the projectile zone applies
    tinman_s_2[buff] to every unit inside projectile_range; IfTargetSide
    gates split the effects - ON_BUFF_START heals ALLY (cached_atk x
    hp_recovery_per_sec_ratio per second) and ON_BUFF_TRIGGER damages
    ENEMY (cached_atk MAGICAL). Allies must never take zone magic damage
    and enemies must never gain the heal modifier."""
    sim, b = _battle()
    assert b.deploy("char_4151_tinman", 2, 3)[0]    # \u9521\u4eba (alchemist)
    op = b.operators[0]
    atk = float(op.attributes.get("atk"))
    sc = op.skill_controller
    s1 = next(s for s in sc.skills if s.skill_id == "skchr_tinman_1")
    s1.sp_cost = 9999.0                             # block S1 auto cast
    e = _spawn(b, 2, 5, hp=50000.0, mr=20.0)
    b.deploy("char_127_estell", 3, 4)[0]            # ally inside zone radius
    ally = b.operators[1]
    ally.hp = ally.max_hp * 0.3
    hp0 = float(ally.hp)
    ehp0 = float(e.hp)
    s2 = next(s for s in sc.skills if s.skill_id == "skchr_tinman_2")
    op.sp = s2.sp_cost
    ok, _ = sc.activate(1)
    assert ok
    b.events.log = []
    for _ in range(200):
        b.tick_once()
    assert any(x.get("key") == "tinman_s_2[buff]" for x in e.buffs)
    assert any(x.get("key") == "tinman_s_2[buff]" for x in ally.buffs)
    heal_mods = [x for x in ally.buffs
                 if x.get("stat") == "hpRecoveryPerSec"]
    assert heal_mods, "ally must receive HP_RECOVERY_PER_SEC modifier"
    assert abs(float(heal_mods[0].get("add", 0.0)) -
               atk * 0.5 * 0.1) < 0.5
    assert ally.hp > hp0, "ally must be healed by the zone"
    assert e.hp < ehp0, "enemy must take zone magic damage"
    assert not any(x.get("stat") == "hpRecoveryPerSec" for x in e.buffs)
    ally_magic = [x for x in b.events.snapshot_events()
                  if x["type"] == "damage" and
                  x.get("data", {}).get("target") == ally.inst_id and
                  x.get("data", {}).get("type") == DamageType.MAGICAL and
                  x.get("data", {}).get("source") == op.inst_id]
    assert not ally_magic, "ally must never be hit by the zone magic damage"


def test_craftsman_s2_deploys_device():
    """\u5de5\u5320 craftsman (robrta S2): the recharge token buff deploys
    the operator's device token (\u5168\u81ea\u52a8\u9020\u578b\u4eea)."""
    sim, b = _battle()
    assert b.deploy("char_484_robrta", 3, 3)[0]     # \u7f57\u6bd4\u8408\u5854
    op = b.operators[0]
    assert op.sub_profession_id == "craftsman"
    sc = op.skill_controller
    s2 = next(s for s in sc.skills if s.skill_id == "skchr_robrta_2")
    op.sp = s2.sp_cost
    ok, _ = sc.activate(1)
    assert ok
    for _ in range(10):
        b.tick_once()
    devs = [t for t in b.tokens if t.token_id == "token_10018_robrta_mach"]
    assert devs, "craftsman device token must be deployed"
