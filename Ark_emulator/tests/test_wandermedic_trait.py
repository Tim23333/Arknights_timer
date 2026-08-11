"""Wandermedic (\u884c\u533b) trait tests.

Branch trait: every heal action restores HP and simultaneously recovers
ALL element bars of the target by source ATK x ep_heal_ratio (0.5). Full-HP
allies with element buildup are valid heal targets (and normally the only
targets when nobody is wounded); heal-free blocks the whole heal action
including the EP recovery.

Targeting (PRTS branch note, shared by \u871c\u8393/\u6851\u8393/
\u7eaf\u715c\u827e\u96c5\u6cd5\u62c9):
  normal attack  : lowest HP ratio > lowest damaged-element value >
                   earlier deploy
  skill with "\u4f18\u5148\u6cbb\u7597\u5143\u7d20\u635f\u4f24\u6700\u4e25\u91cd
  \u7684\u76ee\u6807": lowest damaged-element value > lowest HP ratio
  (the game implements "\u6700\u4e25\u91cd" as "\u5143\u7d20\u503c\u6700\u4f4e",
  a documented PRTS quirk).  Full-HP + full-element units are not targets.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import AbnormalFlag, DamageType
from ark_emulator.targeting import HateSystem


def _battle(char_id="char_449_glider", skill_index=0):
    squad = [{"charId": char_id, "phase": 2, "level": 50,
              "skillIndex": skill_index, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy(b, char_id, row=2, col=3):
    ok, pid = b.deploy(char_id, row, col)
    assert ok, pid
    return b.operators[-1]


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    op._pending_attack = None
    op.attack_timer = 1e6


def _ep(unit, key):
    rec = [x for x in unit.buffs if x.get("key") == key]
    if not rec:
        return 0.0
    # full-bar model: damage = maxEp(1000) - remaining
    return max(0.0, 1000.0 - rec[-1]["value"])


def test_wandermedic_trait_flags():
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")          # \u871c\u8393, wandermedic
    ts = op.trait_system
    assert ts.is_wandermedic()
    assert ts.is_healer()                        # medic profession
    assert abs(ts.ep_heal_ratio() - 0.5) < 1e-9
    atk = float(op.attributes.get("atk") or 0)
    assert abs(ts.ep_heal_amount() - atk * 0.5) < 1e-6


def test_heal_recovers_all_ep_types():
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    ally = _deploy(b, "char_149_scave", 3, 3)
    b.apply_damage(ally, 100.0, DamageType.TRUE, source=None)
    hp_before = ally.hp
    b.add_ep(ally, 0, 300)                           # neural bar
    b.add_ep(ally, 2, 120)                           # burning bar
    _land_attack(b, op, ally)
    sim.run_ticks(20)
    atk = float(op.attributes.get("atk") or 0)
    expect = atk * 0.5
    assert ally.hp > hp_before, (hp_before, ally.hp)
    assert abs(_ep(ally, "ep_neural") - max(0.0, 300.0 - expect)) < 1e-3
    assert _ep(ally, "ep_fire") == 0.0               # clamped at zero
    assert _ep(ally, "ep_dark") == 0.0


def test_full_hp_ally_with_ep_is_targetable():
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    ally = _deploy(b, "char_149_scave", 3, 3)
    assert ally.hp == ally.max_hp                    # untouched
    b.add_ep(ally, 1, 250)                           # water bar buildup
    tgt = HateSystem(b).operator_target(op)
    assert tgt is ally, tgt.inst_id if tgt else None
    _land_attack(b, op, ally)
    sim.run_ticks(20)
    atk = float(op.attributes.get("atk") or 0)
    assert ally.hp == ally.max_hp                    # no HP wasted
    assert abs(_ep(ally, "ep_water") - max(0.0, 250.0 - atk * 0.5)) < 1e-3


def test_full_hp_clean_ally_not_targeted():
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    _deploy(b, "char_149_scave", 3, 3)
    assert HateSystem(b).operator_target(op) is None


def test_priority_wounded_first_then_ep_lowest():
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_149_scave", 3, 4)
    # identical characters -> exactly equal hp ratio (80%); PRTS tie-break
    # is "\u5143\u7d20\u503c\u6700\u4f4e":
    # a1's damaged-element value (80) is lower than a2's (260), so a1 wins.
    b.apply_damage(a1, a1.max_hp * 0.2, DamageType.TRUE, source=None)
    b.apply_damage(a2, a2.max_hp * 0.2, DamageType.TRUE, source=None)
    b.add_ep(a1, 0, 80)
    b.add_ep(a2, 0, 260)
    b.add_ep(a2, 3, 260)
    assert HateSystem(b).operator_target(op) is a1
    # a wounded ally always outranks a full-HP one with EP
    b.apply_damage(a2, 50.0, DamageType.TRUE, source=None)
    assert HateSystem(b).operator_target(op) is a2


def test_ep_priority_skill_flips_order():
    """\u831b\u8393 S2 \u632f\u594b (skchr_glider_2) is marked
    "\u4f18\u5148\u6cbb\u7597\u5143\u7d20\u635f\u4f24\u6700\u4e25\u91cd\u7684\u76ee\u6807";
    while active the sort flips to element value first (still lowest first)."""
    sim, b = _battle(skill_index=1)
    op = _deploy(b, "char_449_glider")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_185_frncat", 3, 4)
    # a2 has lower HP ratio (80% vs 90%), a1 has lower element value
    b.apply_damage(a1, a1.max_hp * 0.1, DamageType.TRUE, source=None)
    b.apply_damage(a2, a2.max_hp * 0.2, DamageType.TRUE, source=None)
    b.add_ep(a1, 0, 80)
    b.add_ep(a2, 0, 260)
    assert HateSystem(b).operator_target(op) is a2   # idle: hp ratio first
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    assert sc.active is not None
    assert HateSystem(b).operator_target(op) is a1   # S2 active: ep first


def test_deploy_time_tie_break():
    """Equal HP ratio and equal element value -> earlier deploy wins
    (PRTS: "\u66f4\u65e9\u90e8\u7f72")."""
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_149_scave", 3, 4)
    b.apply_damage(a1, a1.max_hp * 0.2, DamageType.TRUE, source=None)
    b.apply_damage(a2, a2.max_hp * 0.2, DamageType.TRUE, source=None)
    b.add_ep(a1, 0, 100)
    b.add_ep(a2, 0, 100)
    assert HateSystem(b).operator_target(op) is a1


def test_full_hp_full_ep_target_excluded():
    """\u5143\u7d20\u503c\u5df2\u6ee1 + \u751f\u547d\u5df2\u6ee1\u7684\u5355\u4f4d
    \u4e0d\u4f5c\u4e3a\u6cbb\u7597\u76ee\u6807 (PRTS)."""
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    _deploy(b, "char_185_frncat", 3, 4)
    b.buffs.add_ep_force(a1, 0, 1e9)     # full HP + element value full
    assert HateSystem(b).operator_target(op) is None
    a2 = b.operators[-1]
    b.apply_damage(a2, a2.max_hp * 0.2, DamageType.TRUE, source=None)
    assert HateSystem(b).operator_target(op) is a2


def test_operator_targets_top_n_ordering():
    """operator_targets returns the top-N heal candidates in the same
    priority order as operator_target."""
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_149_scave", 3, 4)
    a3 = _deploy(b, "char_149_scave", 3, 5)
    for u in (a1, a2, a3):
        b.apply_damage(u, u.max_hp * 0.2, DamageType.TRUE, source=None)
    b.add_ep(a1, 0, 80)
    b.add_ep(a2, 0, 260)
    b.add_ep(a3, 0, 500)
    top = HateSystem(b).operator_targets(op, 2)
    assert [u.inst_id for u in top] == [a1.inst_id, a2.inst_id], \
        [u.inst_id for u in top]
    assert HateSystem(b).operator_targets(op, 1) == [a1]


def test_s2_multi_target_heal():
    """\u871c\u8393 S2 \u632f\u5948 (attack@max_target=2): while active every
    heal action heals the top-2 in-range allies (HP + EP recovery each)."""
    sim, b = _battle(skill_index=1)
    op = _deploy(b, "char_449_glider")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_149_scave", 3, 4)
    b.apply_damage(a1, a1.max_hp * 0.2, DamageType.TRUE, source=None)
    b.apply_damage(a2, a2.max_hp * 0.2, DamageType.TRUE, source=None)
    b.add_ep(a1, 0, 300)
    b.add_ep(a2, 0, 300)
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    assert sc.active.heal_max_target() == 2
    hp0 = (a1.hp, a2.hp)
    _land_attack(b, op, a1)
    atk = float(op.attributes.get("atk") or 0)
    expect = atk * 0.5
    assert a1.hp > hp0[0] and a2.hp > hp0[1], (a1.hp, a2.hp)
    assert abs(_ep(a1, "ep_neural") - max(0.0, 300.0 - expect)) < 1e-3
    assert abs(_ep(a2, "ep_neural") - max(0.0, 300.0 - expect)) < 1e-3


def test_s1_multi_target_heal():
    """\u871c\u8393 S1 \u7cbe\u795e\u62a4\u7406 (curated 2 targets): the
    next heal action targets the 2 in-range allies with the LOWEST element
    value (PRTS: "\u6700\u4e25\u91cd" is implemented as "\u5143\u7d20\u503c
    \u6700\u4f4e")."""
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_149_scave", 3, 4)
    a3 = _deploy(b, "char_149_scave", 3, 5)
    for u in (a1, a2, a3):
        b.apply_damage(u, u.max_hp * 0.3, DamageType.TRUE, source=None)
    b.add_ep(a1, 0, 800)
    b.add_ep(a2, 0, 400)
    b.add_ep(a3, 0, 100)
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    assert sc.active.heal_max_target() == 2
    hp0 = (a1.hp, a2.hp, a3.hp)
    _land_attack(b, op, a1)
    assert a1.hp == hp0[0]                    # highest EP -> not targeted
    assert a2.hp > hp0[1] and a3.hp > hp0[2]
    atk = float(op.attributes.get("atk") or 0)
    expect = atk * 0.5
    # ep-first order while S1 is active: a3 (100) < a2 (400) < a1 (800),
    # so the top-2 targets are a3 and a2; a1 keeps its EP
    assert abs(_ep(a1, "ep_neural") - 800.0) < 1e-3
    assert abs(_ep(a2, "ep_neural") - max(0.0, 400.0 - expect)) < 1e-3
    assert abs(_ep(a3, "ep_neural") - max(0.0, 100.0 - expect)) < 1e-3


def test_agoat2_s3_five_shot_cycle_heal():
    """\u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S3 \u706b\u5c71\u56de\u97ff: 5 \u8fde\u53d1,
    each shot heals 25% ATK (HP + EP), re-picking the top not-yet-selected
    ally and cycling through the priority order with fewer candidates."""
    sim, b = _battle("char_1016_agoat2", skill_index=2)
    op = _deploy(b, "char_1016_agoat2")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_149_scave", 3, 4)
    a3 = _deploy(b, "char_149_scave", 3, 5)
    for u in (a1, a2, a3):
        b.apply_damage(u, u.max_hp * 0.3, DamageType.TRUE, source=None)
        b.add_ep(u, 0, 500)
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    assert sc.active.heal_shot_count() == 5
    assert abs(sc.active.heal_attack_scale() - 0.25) < 1e-9
    assert len(op.range_shape) == b.map.rows * b.map.cols  # full-map range
    hp0 = [u.hp for u in (a1, a2, a3)]
    _land_attack(b, op, a1)
    atk = float(op.attributes.get("atk") or 0)
    per = atk * 0.25
    # 5 shots over 3 equal-priority candidates -> a1,a2,a3,a1,a2
    assert abs(a1.hp - hp0[0] - 2 * per) < 1e-3, a1.hp - hp0[0]
    assert abs(a2.hp - hp0[1] - 2 * per) < 1e-3, a2.hp - hp0[1]
    assert abs(a3.hp - hp0[2] - 1 * per) < 1e-3, a3.hp - hp0[2]
    ep = atk * 0.5 * 0.25
    assert abs(_ep(a1, "ep_neural") - max(0.0, 500.0 - 2 * ep)) < 1e-3
    assert abs(_ep(a2, "ep_neural") - max(0.0, 500.0 - 2 * ep)) < 1e-3
    assert abs(_ep(a3, "ep_neural") - max(0.0, 500.0 - 1 * ep)) < 1e-3


def test_agoat2_s3_range_restores_on_expire():
    """S3 \u706b\u5c71\u56de\u97ff full-map range restores to the base shape
    when the skill ends (via _base_range_shape)."""
    sim, b = _battle("char_1016_agoat2", skill_index=2)
    op = _deploy(b, "char_1016_agoat2")
    base = list(op.range_shape)
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    assert len(op.range_shape) == b.map.rows * b.map.cols
    sc.interrupt_active()
    assert sc.active is None
    assert op.range_shape == base


def test_agoat2_s1_extra_target():
    """\u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 S1 \u65e0\u58f0\u6da6\u7269:
    "\u6bcf\u6b21\u53ef\u989d\u5916\u6cbb\u7597\u4e00\u540d\u5355\u4f4d" -> each heal
    action hits 2 in-range allies at full ATK."""
    sim, b = _battle("char_1016_agoat2", skill_index=0)
    op = _deploy(b, "char_1016_agoat2")
    a1 = _deploy(b, "char_149_scave", 3, 3)
    a2 = _deploy(b, "char_149_scave", 3, 4)
    b.apply_damage(a1, a1.max_hp * 0.2, DamageType.TRUE, source=None)
    b.apply_damage(a2, a2.max_hp * 0.2, DamageType.TRUE, source=None)
    b.add_ep(a1, 0, 300)
    b.add_ep(a2, 0, 300)
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    assert sc.active.heal_max_target() == 2
    hp0 = (a1.hp, a2.hp)
    _land_attack(b, op, a1)
    atk = float(op.attributes.get("atk") or 0)
    assert a1.hp > hp0[0] and a2.hp > hp0[1]
    assert abs(_ep(a1, "ep_neural") - max(0.0, 300.0 - atk * 0.5)) < 1e-3
    assert abs(_ep(a2, "ep_neural") - max(0.0, 300.0 - atk * 0.5)) < 1e-3


def test_agoat2_t2_aura_base_and_s3_double():
    """\u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 T2 \u706b\u5c71\u7070\u7597\u6108:
    allies in her attack range get maxHp +6% (mul) and elemental damage
    taken -12%; S3 \u706b\u5c71\u56de\u97ff doubles both (+12% / -24%)."""
    sim, b = _battle("char_1016_agoat2", skill_index=2)
    op = _deploy(b, "char_1016_agoat2")
    ally = _deploy(b, "char_149_scave", 3, 3)
    raw_mhp = ally.max_hp                    # aura has not ticked yet
    sim.run_ticks(5)
    assert abs(ally.max_hp - raw_mhp * 1.06) < 1e-6, (raw_mhp, ally.max_hp)
    base_res = float(ally.attributes.get("epDamageResistance") or 0)
    assert abs(base_res - 12.0) < 1e-6, base_res
    sc = op.skill_controller
    op.sp = sc.skills[2].sp_cost
    ok, _ = sc.activate(2)
    assert ok
    sim.run_ticks(5)
    assert abs(ally.max_hp - raw_mhp * 1.12) < 1e-6, ally.max_hp
    assert abs(float(ally.attributes.get("epDamageResistance") or 0)
               - 24.0) < 1e-6
    assert op.to_dict().get("visionLost") is True
    sc.interrupt_active()
    sim.run_ticks(5)
    assert abs(ally.max_hp - raw_mhp * 1.06) < 1e-6, ally.max_hp
    assert abs(float(ally.attributes.get("epDamageResistance") or 0)
               - 12.0) < 1e-6
    assert op.to_dict().get("visionLost") is False


def test_agoat2_t1_hot_ticks():
    """\u7eaf\u70c1\u827e\u96c5\u6cd5\u62c9 T1 \u6c29\u6c33: a normal heal gives
    the target a 1s-interval HoT (ATK x 10% HP + element recovery each tick
    at E2, cached ATK), expiring after the 6s duration."""
    sim, b = _battle("char_1016_agoat2")
    op = _deploy(b, "char_1016_agoat2")
    ally = _deploy(b, "char_149_scave", 3, 3)
    # big pool so the HoT is not clamped (attributes drive max_hp rebuilds)
    ally.attributes.base["maxHp"] = 100000.0
    ally.max_hp = 100000.0
    ally.hp = 100000.0
    sim.run_ticks(5)                     # let the T2 maxHp aura stabilise
    ally.set_flag(AbnormalFlag.INVINCIBLE, 3600 * 30)  # no spawn damage
    ally.hp = 30000.0
    b.add_ep(ally, 0, 900)                   # below the 1000 burst threshold
    _land_attack(b, op, ally)
    rec = [x for x in ally.buffs if x.get("key") == "agoat2_t_1"]
    assert rec, [x.get("key") for x in ally.buffs]
    atk = float(op.attributes.get("atk") or 0)
    per = atk * 0.10
    bb = rec[-1]["blackboard"]
    assert abs(bb["dynamic"] - atk) < 1e-3, bb
    assert abs(bb["heal_scale"] - 0.10) < 1e-6
    assert bb["stack_cnt"] == 1.0
    hp0 = ally.hp
    ep0 = _ep(ally, "ep_neural")
    sim.run_ticks(30)                      # first HoT tick
    assert abs(ally.hp - hp0 - per) < 1e-3, (ally.hp - hp0, per)
    assert abs(_ep(ally, "ep_neural")
               - max(0.0, ep0 - per * 0.5)) < 1e-3
    hp1 = ally.hp
    sim.run_ticks(150)                     # +5 ticks, then buff expires
    assert abs(ally.hp - hp1 - 5 * per) < 1e-3, (ally.hp - hp1, 5 * per)
    assert not [x for x in ally.buffs if x.get("key") == "agoat2_t_1"], \
        "HoT must expire after its 6s duration"


def test_agoat2_t1_stack_and_cached_atk_update():
    """\u6c29\u6c33 stacks up to 3 layers; each layer heals per tick; a 4th
    heal refreshes duration/ATK but keeps the cap."""
    sim, b = _battle("char_1016_agoat2")
    op = _deploy(b, "char_1016_agoat2")
    ally = _deploy(b, "char_149_scave", 3, 3)
    ally.attributes.base["maxHp"] = 100000.0
    ally.max_hp = 100000.0
    ally.hp = 100000.0
    sim.run_ticks(5)                     # T2 aura stable before measuring
    ally.set_flag(AbnormalFlag.INVINCIBLE, 3600 * 30)
    ally.hp = 30000.0
    b.add_ep(ally, 0, 900)
    for _ in range(3):
        _land_attack(b, op, ally)
    rec = [x for x in ally.buffs if x.get("key") == "agoat2_t_1"]
    assert rec and rec[-1]["blackboard"]["stack_cnt"] == 3.0
    atk = float(op.attributes.get("atk") or 0)
    per = atk * 0.10
    hp0 = ally.hp
    ep0 = _ep(ally, "ep_neural")
    sim.run_ticks(30)
    assert abs(ally.hp - hp0 - 3 * per) < 1e-3, (ally.hp - hp0, 3 * per)
    assert abs(_ep(ally, "ep_neural")
               - max(0.0, ep0 - 3 * per * 0.5)) < 1e-3
    _land_attack(b, op, ally)              # 4th heal: capped at 3
    rec = [x for x in ally.buffs if x.get("key") == "agoat2_t_1"]
    assert rec[-1]["blackboard"]["stack_cnt"] == 3.0


def test_heal_free_blocks_heal_and_ep():
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    ally = _deploy(b, "char_149_scave", 3, 3)
    ally.set_flag(AbnormalFlag.HEAL_FREE, 30 * 60)
    b.add_ep(ally, 0, 300)
    assert HateSystem(b).operator_target(op) is None
    healed = b.apply_heal(ally, 999.0, source=op)
    assert healed == 0.0
    assert _ep(ally, "ep_neural") == 300.0           # EP recovery blocked too


def test_trait_immune_heal_skips_ep_recovery():
    sim, b = _battle()
    op = _deploy(b, "char_449_glider")
    ally = _deploy(b, "char_149_scave", 3, 3)
    b.apply_damage(ally, 150.0, DamageType.TRUE, source=None)
    b.add_ep(ally, 0, 300)
    healed = b.apply_heal(ally, 100.0, source=op, trait_immune=True)
    assert healed == 100.0
    assert _ep(ally, "ep_neural") == 300.0


def test_physician_heal_does_not_recover_ep():
    sim, b = _battle("char_003_kalts")
    op = _deploy(b, "char_003_kalts")               # \u51ef\u5c14\u5e0c physician
    ally = _deploy(b, "char_149_scave", 3, 3)
    b.apply_damage(ally, 100.0, DamageType.TRUE, source=None)
    b.add_ep(ally, 0, 300)
    _land_attack(b, op, ally)
    sim.run_ticks(20)
    assert _ep(ally, "ep_neural") == 300.0


def test_recover_ep_clamps_at_zero():
    sim, b = _battle()
    ally = _deploy(b, "char_149_scave", 3, 3)
    b.add_ep(ally, 0, 100)
    b.add_ep(ally, 1, 40)
    recovered = b.buffs.recover_ep(ally, 300)
    assert recovered == 140.0
    assert _ep(ally, "ep_neural") == 0.0
    assert _ep(ally, "ep_water") == 0.0
    assert any(x.get("type") == "ep_recovered"
               for x in b.events.snapshot_events())


def test_harold_t1_over_half_element_resistance():
    """哈洛德 T1 我即军营: allies inside the attack range whose element
    damage exceeds half the burst threshold take epDamageResistance less
    element damage (E2 15%); under-half / clean units get nothing."""
    sim, b = _battle("char_4114_harold")
    op = _deploy(b, "char_4114_harold")
    ally = _deploy(b, "char_149_scave", 3, 3)
    sim.run_ticks(5)
    assert abs(float(ally.attributes.get("epDamageResistance") or 0.0)) < 1e-6
    b.add_ep(ally, 0, 600)                    # > half of 1000
    sim.run_ticks(5)
    assert abs(float(ally.attributes.get("epDamageResistance") or 0.0)
               - 15.0) < 1e-6
    b.add_ep(ally, 0, 200)                    # damage taken is reduced: 170
    assert abs(_ep(ally, "ep_neural") - 770.0) < 1e-3
    b.buffs.recover_ep(ally, 700)             # back under half
    sim.run_ticks(5)
    assert abs(float(ally.attributes.get("epDamageResistance") or 0.0)) < 1e-6
    b.add_ep(ally, 0, 200)                    # full damage again
    assert abs(_ep(ally, "ep_neural") - 270.0) < 1e-3


def test_harold_s2_trait_scale_ep_recovery():
    """哈洛德 S2 重症优先: while active, EP recovery is multiplied by
    trait_scale (lv1 1.2) only for targets whose element damage exceeds half;
    HP heal stays full and under-half targets keep the base recovery."""
    sim, b = _battle("char_4114_harold", skill_index=1)
    op = _deploy(b, "char_4114_harold")
    severe = _deploy(b, "char_149_scave", 3, 3)
    mild = _deploy(b, "char_149_scave", 3, 4)
    b.apply_damage(severe, severe.max_hp * 0.2, DamageType.TRUE, source=None)
    b.apply_damage(mild, mild.max_hp * 0.2, DamageType.TRUE, source=None)
    b.add_ep(severe, 0, 800)                  # > half
    b.add_ep(mild, 0, 300)                    # < half
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    assert sc.active is not None
    hp_severe, hp_mild = severe.hp, mild.hp
    _land_attack(b, op, severe)
    atk = float(op.attributes.get("atk") or 0)
    base = atk * 0.5
    assert severe.hp > hp_severe              # HP heal unchanged
    assert abs(_ep(severe, "ep_neural")
               - max(0.0, 800.0 - base * 1.2)) < 1e-3
    _land_attack(b, op, mild)
    atk = float(op.attributes.get("atk") or 0)
    assert mild.hp > hp_mild
    assert abs(_ep(mild, "ep_neural")
               - max(0.0, 300.0 - atk * 0.5)) < 1e-3


def test_mberry_s2_resistance_aura():
    """桑葚 S2 安全区域: while active, allies in the attack range get
    epDamageResistance (lv1 15%) so element damage taken is reduced; the
    aura drops when the skill is interrupted/expires."""
    sim, b = _battle("char_473_mberry", skill_index=1)
    op = _deploy(b, "char_473_mberry")
    ally = _deploy(b, "char_149_scave", 3, 3)
    sim.run_ticks(5)
    assert abs(float(ally.attributes.get("epDamageResistance") or 0.0)) < 1e-6
    sc = op.skill_controller
    op.sp = sc.skills[1].sp_cost
    ok, _ = sc.activate(1)
    assert ok
    sim.run_ticks(5)
    assert abs(float(ally.attributes.get("epDamageResistance") or 0.0)
               - 15.0) < 1e-6
    b.add_ep(ally, 0, 200)
    assert abs(_ep(ally, "ep_neural") - 170.0) < 1e-3
    sc.interrupt_active()
    sim.run_ticks(5)
    assert abs(float(ally.attributes.get("epDamageResistance") or 0.0)) < 1e-6
    b.add_ep(ally, 0, 200)
    assert abs(_ep(ally, "ep_neural") - 370.0) < 1e-3


def test_agoat2_s1_ep_regen_aura():
    """纯艾 S1 无声润物: while active (infinite window), every second all
    friendly units in the attack range recover ATK x ep_heal_ratio (lv1 2%)
    element damage; HP is untouched and out-of-range units get nothing."""
    sim, b = _battle("char_1016_agoat2", skill_index=0)
    op = _deploy(b, "char_1016_agoat2")
    a_in = _deploy(b, "char_149_scave", 3, 3)
    a_out = _deploy(b, "char_149_scave", 4, 4)   # row 4: outside 3-row range
    sim.run_ticks(5)      # let the T2 maxHp aura stabilise (hp scales up)
    b.add_ep(a_in, 0, 500)
    b.add_ep(a_out, 0, 500)
    b.add_ep(op, 0, 500)                          # own tile is in her range
    hp0 = (a_in.hp, a_out.hp, op.hp)
    ep0 = (_ep(a_in, "ep_neural"), _ep(a_out, "ep_neural"),
           _ep(op, "ep_neural"))   # T2 aura may reduce the incoming 500
    sc = op.skill_controller
    op.sp = sc.skills[0].sp_cost
    ok, _ = sc.activate(0)
    assert ok
    op.attack_timer = 1e6          # no normal heal attacks during measure
    sim.run_ticks(70)                             # ~2 full seconds
    atk = float(op.attributes.get("atk") or 0)
    per = atk * 0.02
    assert abs(_ep(a_in, "ep_neural")
               - max(0.0, ep0[0] - 2.0 * per)) < 1e-3, _ep(a_in, "ep_neural")
    assert abs(_ep(a_out, "ep_neural") - ep0[1]) < 1e-3
    assert abs(_ep(op, "ep_neural")
               - max(0.0, ep0[2] - 2.0 * per)) < 1e-3
    assert a_in.hp == hp0[0] and a_out.hp == hp0[1] and op.hp == hp0[2]
