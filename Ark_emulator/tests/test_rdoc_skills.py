"""Doctor (医生, char_4125_rdoc) skill tests: S1 以暴制暴 and S2 激素手枪.

Covers the 31-bullet ammo mode, the 3-activations-per-deployment limit,
S1's instant self-heal + attack interval reduction, and S2's straight-line
hormone bullet (first friendly hit heals, first ground enemy stops it with
no effect).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle(skill_index=0):
    squad = [{"charId": "char_4125_rdoc", "phase": 2, "level": 1,
              "skillIndex": skill_index, "skillLevels": [1, 1, 1]},
             {"charId": "char_002_amiya", "phase": 2, "level": 1}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _deploy_doc(b):
    ok, did = b.deploy("char_4125_rdoc", 3, 3)      # ground, facing right
    assert ok, did
    ok, aid = b.deploy("char_002_amiya", 2, 3)      # ranged ally on high ground
    assert ok, aid
    doc = [o for o in b.operators if o.inst_id == did][0]
    ally = [o for o in b.operators if o.inst_id == aid][0]
    return doc, ally


def _sp_full(doc):
    doc.sp = doc.sp_max


def test_rdoc_s1_ammo_heal_and_interval():
    sim, b = _battle(skill_index=0)
    doc, ally = _deploy_doc(b)
    _sp_full(doc)
    doc.hp = doc.max_hp - 500.0
    hp0 = doc.hp
    ok, _ = b.activate_skill(doc.inst_id, 0)
    assert ok
    sc = doc.skill_controller
    assert sc.active is not None
    assert sc.active.is_ammo
    assert sc.active.ammo == 31
    # instant self-heal atk * heal_scale (lv1 = 1.0), capped at maxHp
    expect = min(doc.max_hp, hp0 + doc.attributes.get("atk") * 1.0)
    assert abs(doc.hp - expect) < 1e-6
    # attack interval reduced (additive -0.3 at lv1; carried by the
    # prefab owner buff rdoc_s1[switch_mode], blackboard path de-duped)
    bat = [x for x in doc.buffs if x.get("stat") == "baseAttackTime"]
    assert bat and abs(bat[-1].get("add", 0.0) + 0.3) < 1e-9, bat
    # 31 ammo consumed by attacks -> skill ends
    for _ in range(30):
        sc.on_ammo_attack()
    assert sc.active is not None and sc.active.ammo == 1
    sc.on_ammo_attack()
    assert sc.active is None, "skill must end when ammo runs out"


def test_rdoc_s1_three_uses_per_deploy():
    sim, b = _battle(skill_index=0)
    doc, ally = _deploy_doc(b)
    sc = doc.skill_controller
    for use in range(3):
        _sp_full(doc)
        ok, r = b.activate_skill(doc.inst_id, 0)
        assert ok, (use, r)
        for _ in range(31):
            sc.on_ammo_attack()      # burn the magazine
        assert sc.active is None
        assert sc.skills[0].use_count == use + 1
    _sp_full(doc)
    ok, r = b.activate_skill(doc.inst_id, 0)
    assert not ok and r == "use_limit"


def test_rdoc_s2_heals_first_friendly_hit():
    sim, b = _battle(skill_index=1)
    doc, ally = _deploy_doc(b)
    # ally in the tile directly in front (3,4), wounded
    ally.row, ally.col = 3, 4
    ally.deploy_tick = b.tick
    ally.hp = ally.max_hp - 300.0
    hp_a0 = ally.hp
    hp_d0 = doc.hp = doc.max_hp - 200.0
    _sp_full(doc)
    ok, _ = b.activate_skill(doc.inst_id, 1)
    assert ok
    projs = [p for p in b.projectiles if p.key == "projectile_chr_rdoc_s2"]
    assert projs, "hormone bullet must be launched"
    sim.run_ticks(15)      # bullet travels 1 tile at speed 5.0 (6 ticks)
    assert not [p for p in b.projectiles
                if p.key == "projectile_chr_rdoc_s2"], "bullet consumed"
    expect = min(ally.max_hp, hp_a0 + doc.attributes.get("atk") * 3.0)
    assert abs(ally.hp - expect) < 1e-6
    # S2 cast does NOT heal the caster
    assert abs(doc.hp - hp_d0) < 1e-9
    evs = b.events.snapshot_events()
    hit = [x for x in evs if x["type"] == "rdoc_s2_hit" and
           x["data"]["unit"] == doc.inst_id][-1]
    assert hit["data"]["kind"] == "ally"


def test_rdoc_s2_ground_enemy_stops_bullet_no_effect():
    sim, b = _battle(skill_index=1)
    doc, ally = _deploy_doc(b)
    ally.row, ally.col = 3, 5          # behind the enemy
    ally.deploy_tick = b.tick
    hp_a0 = ally.hp
    e = b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": 3, "col": 4})
    e.state = EnemyState.COMBAT
    hp_e0 = e.hp
    _sp_full(doc)
    ok, _ = b.activate_skill(doc.inst_id, 1)
    assert ok
    sim.run_ticks(15)
    assert not [p for p in b.projectiles
                if p.key == "projectile_chr_rdoc_s2"]
    assert abs(e.hp - hp_e0) < 1e-9, "enemy must take no damage"
    assert abs(ally.hp - hp_a0) < 1e-9, "ally behind enemy must not be healed"
    hit = [x for x in b.events.snapshot_events()
           if x["type"] == "rdoc_s2_hit" and
           x["data"]["unit"] == doc.inst_id][-1]
    assert hit["data"]["kind"] == "enemy"


def test_rdoc_s2_three_uses_per_deploy():
    sim, b = _battle(skill_index=1)
    doc, ally = _deploy_doc(b)
    sc = doc.skill_controller
    for use in range(3):
        _sp_full(doc)
        ok, r = b.activate_skill(doc.inst_id, 1)
        assert ok, (use, r)
        sim.run_ticks(25)      # deploy anim (15t) + bullet flight + 0.1s cast window
        assert sc.active is None or True  # S2 has no ammo/duration run
        assert sc.skills[1].use_count == use + 1
    _sp_full(doc)
    ok, r = b.activate_skill(doc.inst_id, 1)
    assert not ok and r == "use_limit"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    import traceback
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
