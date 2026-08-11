"""Module (\\u6a21\\u7ec4) attribute bonus tests.

Squad entries may carry moduleId + moduleLevel; the X/Y module per-phase
attribute bonuses from module_stats.json are added on deploy and exposed
in the operator snapshot.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator


def _battle(squad):
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def test_module_stat_bonus_levels():
    from ark_emulator.loader import DataStore
    st = DataStore()
    b3 = st.module_stat_bonus("uniequip_002_phatm2", 3)
    assert b3 == {"max_hp": 200.0, "atk": 42.0}, b3
    b1 = st.module_stat_bonus("uniequip_002_phatm2", 1)
    assert b1 == {"max_hp": 125.0, "atk": 30.0}, b1
    assert st.module_stat_bonus("uniequip_002_phatm2", 9) == b3
    assert st.module_stat_bonus("no_such_module", 3) is None


def test_module_attributes_applied_on_deploy():
    base_squad = [{"charId": "char_1042_phatm2", "phase": 2, "level": 50,
                   "skillIndex": 2, "skillLevels": [1, 1, 1]}]
    mod_squad = [dict(base_squad[0], moduleId="uniequip_002_phatm2",
                      moduleLevel=3)]
    _, b0 = _battle(base_squad)
    _, b1 = _battle(mod_squad)
    b0.deploy("char_1042_phatm2", 2, 3)
    b1.deploy("char_1042_phatm2", 2, 3)
    op0 = b0.operators[0]
    op1 = b1.operators[0]
    assert op0.module is None
    assert op1.module == {"id": "uniequip_002_phatm2", "level": 3}
    assert abs(op1.attributes.get("atk") - op0.attributes.get("atk") - 42.0) \
        < 1e-6
    assert abs(op1.max_hp - op0.max_hp - 200.0) < 1e-6
    # snapshot carries the module info
    snap = b1.snapshot()
    assert snap["deployed"][0]["module"] == \
        {"id": "uniequip_002_phatm2", "level": 3}


def test_module_nested_config_and_blaze2_def():
    # nested module dict + a different module (blaze2 X: atk/def)
    squad = [{"charId": "char_1040_blaze2", "phase": 2, "level": 50,
              "skillIndex": 0, "skillLevels": [1, 1, 1],
              "module": {"id": "uniequip_002_blaze2", "level": 2}}]
    sim, b = _battle(squad)
    b.deploy("char_1040_blaze2", 2, 3)
    op = b.operators[0]
    assert op.module == {"id": "uniequip_002_blaze2", "level": 2}
    from ark_emulator.loader import DataStore
    st = DataStore()
    bb = st.module_stat_bonus("uniequip_002_blaze2", 2)
    assert bb == {"atk": 66.0, "def": 20.0}, bb
    base_atk = op.attributes.get("atk") - 66.0
    base_def = op.attributes.get("def") - 20.0
    assert base_atk > 0 and base_def > 0


def test_module_talent_blackboard_upgrade():
    from ark_emulator.loader import DataStore
    st = DataStore()
    ups = st.module_talent_upgrades("uniequip_002_phatm2", 3)
    assert ups, "battle_equip talent upgrades must parse"
    assert ups[0]["talent_index"] == 2 and ups[0]["name"] == "\u5815\u68a6"
    assert ups[0]["values"] == [-20.0, 90.0], ups[0]
    assert ups[1]["values"] == [-24.0, 90.0], ups[1]

    def deploy(pot):
        sq = [{"charId": "char_1042_phatm2", "phase": 2, "level": 50,
               "skillIndex": 2, "skillLevels": [1, 1, 1],
               "potential": pot, "moduleId": "uniequip_002_phatm2",
               "moduleLevel": 3}]
        sim, b = _battle(sq)
        b.deploy("char_1042_phatm2", 2, 3)
        return b.operators[0]

    op0 = deploy(0)
    bb0 = op0.talent_system.to_dict()[1]["blackboard"]
    assert abs(bb0["attack_speed"] - (-20.0)) < 1e-9, bb0
    assert abs(bb0["value"] - 90.0) < 1e-9, bb0
    # the enemy-side aura reads the module-upgraded values
    spec = [x for x in op0.talent_system.enemy_aura_specs()
            if x["kind"] == "phatm2_t2_speed"][0]
    assert abs(spec["attack_speed"] - (-20.0)) < 1e-9

    op4 = deploy(4)
    bb4 = op4.talent_system.to_dict()[1]["blackboard"]
    assert abs(bb4["attack_speed"] - (-24.0)) < 1e-9, bb4
    assert abs(bb4["value"] - 90.0) < 1e-9


def test_trust_bonus_scales_with_trust():
    def deploy(trust=0):
        sq = [{"charId": "char_1040_blaze2", "phase": 2, "level": 50,
               "skillIndex": 0, "skillLevels": [1, 1, 1]}]
        if trust:
            sq[0]["trust"] = trust
        sim, b = _battle(sq)
        b.deploy("char_1040_blaze2", 2, 3)
        return b.operators[0]

    b0 = deploy(0)
    b100 = deploy(100)
    b200 = deploy(200)
    assert b0.trust == 0 and b200.trust == 200
    # PRTS \u4fe1\u8d56\u52a0\u6210\u4e0a\u9650: \u70db\u714c atk +90 at 200%
    assert abs(b200.attributes.get("atk") - b0.attributes.get("atk")
               - 90.0) < 1e-6
    # linear at 100%
    assert abs(b100.attributes.get("atk") - b0.attributes.get("atk")
               - 45.0) < 1e-6
    # snapshot carries trust
    assert b200.to_dict().get("trust") == 200
    # \u9152\u795e: hp +300 / atk +40 at 200% trust
    def deploy2(trust=0):
        sq = [{"charId": "char_1042_phatm2", "phase": 2, "level": 50,
               "skillIndex": 2, "skillLevels": [1, 1, 1]}]
        if trust:
            sq[0]["trust"] = trust
        sim, b = _battle(sq)
        b.deploy("char_1042_phatm2", 2, 3)
        return b.operators[0]
    g0 = deploy2(0)
    g200 = deploy2(200)
    assert abs(g200.max_hp - g0.max_hp - 300.0) < 1e-6
    assert abs(g200.attributes.get("atk") - g0.attributes.get("atk")
               - 40.0) < 1e-6


def test_module_trait_upgrade_values():
    """battle_equip overrideTraitDataBundle: 哈洛德 WDM-X 腿部护理套装
    upgrades the trait blackboard ep_heal_ratio 0.5 -> 0.6 at module
    level 1+ (all phases carry the trait part)."""
    from ark_emulator.loader import DataStore
    st = DataStore()
    for lv in (1, 2, 3):
        ups = st.module_trait_upgrades("uniequip_002_harold", lv)
        assert ups, (lv, ups)
        assert ups[0]["values"] == [0.6], (lv, ups[0])
    assert st.module_trait_upgrades("no_such_module", 3) == []


def test_all_module_upgrade_parsing_is_robust():
    """Every battle_equip entry parses trait/talent upgrades without
    crashing (malformed phases / non-list blackboards are skipped)."""
    from ark_emulator.loader import DataStore
    st = DataStore()
    be = st.battle_equip
    assert len(be) > 400
    for mid in be:
        for lv in (1, 2, 3):
            tr = st.module_trait_upgrades(mid, lv)
            tl = st.module_talent_upgrades(mid, lv)
            assert isinstance(tr, list) and isinstance(tl, list), mid


def test_wandermedic_wdmx_modules_trait_upgrade():
    """纯艾/蜜莓/桑葚 WDM-X modules lift the wandermedic trait
    ep_heal_ratio to 0.6 at module level 1+ (same overrideTraitDataBundle
    channel as 哈洛德)."""
    for cid, mid in (("char_1016_agoat2", "uniequip_002_agoat2"),
                     ("char_449_glider", "uniequip_002_glider"),
                     ("char_473_mberry", "uniequip_002_mberry")):
        sq = [{"charId": cid, "phase": 2, "level": 50,
               "skillIndex": 0, "skillLevels": [1, 1, 1],
               "moduleId": mid, "moduleLevel": 1}]
        sim, b = _battle(sq)
        b.deploy(cid, 2, 3)
        op = b.operators[0]
        assert abs(op.trait_system.ep_heal_ratio() - 0.6) < 1e-9, \
            (cid, mid, op.trait_system.ep_heal_ratio())


def test_agoat2_wdmx_talent_upgrade_aura():
    """纯艾 WDM-X lv3: T2 火山灰疗愈 aura uses the module-upgraded values
    (maxHp 8%, epDamageResistance 14%) instead of the base 6%/12%."""
    from ark_emulator.loader import DataStore
    st = DataStore()
    ups = st.module_talent_upgrades("uniequip_002_agoat2", 3)
    assert ups[0]["values"] == [0.08, 0.14], ups
    sq = [{"charId": "char_1016_agoat2", "phase": 2, "level": 50,
           "skillIndex": 0, "skillLevels": [1, 1, 1],
           "moduleId": "uniequip_002_agoat2", "moduleLevel": 3}]
    sim, b = _battle(sq)
    b.deploy("char_1016_agoat2", 2, 3)
    b.deploy("char_149_scave", 3, 3)
    ally = b.operators[-1]
    raw_mhp = ally.max_hp
    sim.run_ticks(5)
    assert abs(ally.max_hp - raw_mhp * 1.08) < 1e-6, \
        (raw_mhp, ally.max_hp)
    assert abs(float(ally.attributes.get("epDamageResistance") or 0.0)
               - 14.0) < 1e-6


def test_harold_wdmx_module_trait_and_talent():
    """哈洛德 WDM-X 腿部护理套装: module level 1+ raises the wandermedic
    trait ep_heal_ratio to 0.6 and adds module stat bonuses; module level 3
    upgrades talent 1 我即军营 to 23% (26% at potential 5) on over-half
    allies in range."""
    def deploy(module_level=None, potential=0):
        sq = [{"charId": "char_4114_harold", "phase": 2, "level": 50,
               "skillIndex": 1, "skillLevels": [1, 1, 1],
               "potential": potential}]
        if module_level:
            sq[0]["moduleId"] = "uniequip_002_harold"
            sq[0]["moduleLevel"] = module_level
        sq.append({"charId": "char_149_scave", "phase": 2, "level": 50,
                   "skillIndex": 0, "skillLevels": [1, 1, 1]})
        sim, b = _battle(sq)
        b.deploy("char_4114_harold", 2, 3)
        op = b.operators[0]
        b.deploy("char_149_scave", 3, 3)
        ally = b.operators[-1]
        sim.run_ticks(5)
        return op, ally, b

    op0, ally0, b0 = deploy()
    assert abs(op0.trait_system.ep_heal_ratio() - 0.5) < 1e-9
    b0.add_ep(ally0, 0, 600)
    _tick_aura_pass(b0)
    # no-module baseline: E2 talent 15%
    assert abs(float(ally0.attributes.get("epDamageResistance") or 0.0)
               - 15.0) < 1e-6

    op1, ally1, b1 = deploy(module_level=1)
    assert abs(op1.trait_system.ep_heal_ratio() - 0.6) < 1e-9
    b1.add_ep(ally1, 0, 600)
    _tick_aura_pass(b1)
    # module lv1 has no talent upgrade: stays 15%
    assert abs(float(ally1.attributes.get("epDamageResistance") or 0.0)
               - 15.0) < 1e-6

    op3, ally3, b3 = deploy(module_level=3)
    assert abs(op3.trait_system.ep_heal_ratio() - 0.6) < 1e-9
    assert abs(op3.attributes.get("atk")
               - op0.attributes.get("atk") - 32.0) < 1e-6   # module stats
    b3.add_ep(ally3, 0, 600)
    _tick_aura_pass(b3)
    assert abs(float(ally3.attributes.get("epDamageResistance") or 0.0)
               - 23.0) < 1e-6

    op5, ally5, b5 = deploy(module_level=3, potential=5)
    b5.add_ep(ally5, 0, 600)
    _tick_aura_pass(b5)
    assert abs(float(ally5.attributes.get("epDamageResistance") or 0.0)
               - 26.0) < 1e-6


def _tick_aura_pass(b, n=5):
    """Advance the battle 5 ticks (aura sync pass)."""
    for _ in range(n):
        b.tick_once()


def test_module_trait_elite_ep_scale():
    """酒神 Y 模组: module talent upgrades lift the elite/leader elemental
    damage bonus (module_elite_ep_scale) on source-side EP application."""
    from ark_emulator.consts import EnemyState

    def setup(mod):
        sq = [{"charId": "char_1042_phatm2", "phase": 2, "level": 50,
               "skillIndex": 2, "skillLevels": [1, 1, 1]}]
        if mod:
            sq[0].update({"moduleId": "uniequip_002_phatm2",
                          "moduleLevel": 3})
        sim, b = _battle(sq)
        b.deploy("char_1042_phatm2", 2, 3)
        return sim, b

    def spawn(b, row, col, lv):
        b.spawn_enemy("enemy_1000_gopro", 0, overrides={
            "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
            "row": row, "col": col})
        e = b.enemies[-1]
        e.state = EnemyState.COMBAT
        e.level_type = lv
        return e

    def ep(b, e):
        rec = [x for x in e.buffs if x.get("key") == "ep_neural"]
        if not rec:
            return 0.0
        # full-bar model: damage = maxEp - remaining
        return max(0.0, b.buffs.ep_max(e) - rec[-1]["value"])

    sim, b = setup(False)
    op = b.operators[0]
    elite = spawn(b, 2, 4, 1)
    normal = spawn(b, 3, 4, 0)
    b.add_ep(elite, 0, 100.0, source=op)
    b.add_ep(normal, 0, 100.0, source=op)
    assert abs(ep(b, elite) - 100.0) < 1e-9
    assert abs(ep(b, normal) - 100.0) < 1e-9

    sim2, b2 = setup(True)
    op2 = b2.operators[0]
    e2 = spawn(b2, 2, 4, 1)
    n2 = spawn(b2, 3, 4, 0)
    b2.add_ep(e2, 0, 100.0, source=op2)
    b2.add_ep(n2, 0, 100.0, source=op2)
    assert abs(ep(b2, e2) - 118.0) < 1e-9, ep(b2, e2)
    assert abs(ep(b2, n2) - 100.0) < 1e-9


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")



def test_blaze2_x_module_melting_ignition_scaled():
    """blaze2 X module (uniequip_002_blaze2) upgrades the melting-ignition
    talent blackboard: on any enemy FIRE-burst the operator heals
    maxHp x hp_ratio and the bursting enemy gains atk x ep_damage_scale
    fire EP. The module lifts ep_damage_scale 3.5 -> 3.9 (pot <4)."""
    from ark_emulator.consts import EnemyState

    def run(mod):
        sq = [{"charId": "char_1040_blaze2", "phase": 2, "level": 50,
               "skillIndex": 0, "skillLevels": [1, 1, 1]}]
        if mod:
            sq[0].update({"moduleId": "uniequip_002_blaze2",
                          "moduleLevel": 2})
        sim = Simulator(level_id="level_main_01-01", squad=sq)
        sim.run_ticks(15)
        b = sim.battle
        b.max_cost = 100000.0
        b.cost = 0.0
        b.cost_increase_time = 1e7
        b.battle_cost_add(100.0)
        b.deploy("char_1040_blaze2", 2, 3)
        op = b.operators[0]
        op.hp = op.max_hp * 0.5
        b.spawn_enemy("enemy_1000_gopro", 0, overrides={
            "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
            "row": 2, "col": 4})
        e = b.enemies[-1]
        e.state = EnemyState.COMBAT

        def fire_ep():
            rec = [x for x in e.buffs if x.get("key") == "ep_fire"]
            if not rec:
                return 0.0
            # full-bar model: damage = maxEp - remaining (may exceed maxEp
            # with over-accumulated burst bonus)
            return max(0.0, b.buffs.ep_max(e) - rec[-1]["value"])
        t1 = next(x for x in op.buffs if x.get("key") == "blaze2_t_1")
        hp0, ep0 = float(op.hp), fire_ep()
        b.add_ep(e, 2, 2000.0)          # FIRE burst
        for _ in range(3):
            b.tick_once()
        return op, hp0, op.hp, ep0, fire_ep(), t1

    op0, hp0, hp1, ep0, ep1, t1_0 = run(False)
    op1, hp1a, hp1b, ep1a, ep1b, t1_1 = run(True)
    # module upgrades the blackboard
    assert abs(t1_0["blackboard"]["ep_damage_scale"] - 3.5) < 1e-9
    assert abs(t1_1["blackboard"]["ep_damage_scale"] - 3.9) < 1e-9
    assert abs(t1_0["blackboard"]["ratio"] - 0.12) < 1e-9
    # heal = maxHp x 0.12 on the fire burst
    assert abs((hp1 - hp0) - op0.max_hp * 0.12) < 0.5
    assert abs((hp1b - hp1a) - op1.max_hp * 0.12) < 0.5
    # bursting enemy gains atk x scale fire EP
    assert abs((ep1 - ep0) - op0.attributes.get("atk") * 3.5) < 1.0
    assert abs((ep1b - ep1a) - op1.attributes.get("atk") * 3.9) < 1.0



def test_blaze2_y_module_reborn_regen_enhanced():
    """blaze2 Y module (uniequip_003_blaze2) upgrades the T2 reborn
    blackboard: downed-state regen 3% -> 4% maxHp per second."""
    def deploy(mod):
        sq = [{"charId": "char_1040_blaze2", "phase": 2, "level": 50,
               "skillIndex": 0, "skillLevels": [1, 1, 1]}]
        if mod:
            sq[0].update({"moduleId": "uniequip_003_blaze2",
                          "moduleLevel": 3})
        sim = Simulator(level_id="level_main_01-01", squad=sq)
        sim.run_ticks(15)
        b = sim.battle
        b.max_cost = 100000.0
        b.cost = 0.0
        b.cost_increase_time = 1e7
        b.battle_cost_add(100.0)
        b.deploy("char_1040_blaze2", 2, 3)
        return b.operators[0]

    op0 = deploy(False)
    op1 = deploy(True)
    t0 = next(x for x in op0.buffs if x.get("key") == "blaze2_t_2")
    t1 = next(x for x in op1.buffs if x.get("key") == "blaze2_t_2")
    assert abs(t0["blackboard"]["hp_recovery_per_sec_by_max_hp_ratio"]
               - 0.03) < 1e-9
    assert abs(t1["blackboard"]["hp_recovery_per_sec_by_max_hp_ratio"]
               - 0.04) < 1e-9
    assert t0["blackboard"]["stun"] == t1["blackboard"]["stun"] == 5.0
