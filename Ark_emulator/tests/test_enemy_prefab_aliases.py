"""Enemy skill prefab-key alias + synthesis tests.

Covers the two verified naming variants between enemy_database skill
prefabKeys and the extracted enm_pfb GameObject names:
  - cut_tree / cuttree  -> CutTree  (enemy_1512_mcmstr)
  - BoomAll             -> DeathBoomAll (enemy_1543_cstlrs)
and the on-the-fly synthesis of behavior-catalog-style entries for skills
absent from skill_behavior_catalog.json but present in the full prefab
catalog (so EnemySkillController gets abilities / enemySkill params).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.loader import DataStore


def test_cut_tree_aliases_resolve_to_same_prefab():
    st = DataStore()
    # both spellings used across level entries resolve to the current
    # GameObject name CutTree (older builds named it cuttree)
    for key in ("cut_tree", "cuttree"):
        comps = st.prefab_components(key)
        assert comps, key
        cls = {c.get("class") for c in comps}
        assert "EnemySkill" in cls and "Ability" in cls, (key, cls)
    f = st.prefab_ability_fields("cuttree")
    assert "_preDelayFactor" in f and "_selectTargetTiming" in f
    # behavior catalog already has the (old-build) cuttree entry; the
    # level-1 variant cut_tree gets a synthesized one
    hits = [e for e in st.enemy_skills("enemy_1512_mcmstr")
            if e.get("prefabKey") in ("cuttree", "cut_tree")]
    pks = {e["prefabKey"] for e in hits}
    assert "cuttree" in pks and "cut_tree" in pks, pks
    syn = [e for e in hits if e.get("_synthesized")]
    assert syn and len(syn[0].get("abilities") or []) >= 1


def test_boomall_aliases_to_deathboomall():
    st = DataStore()
    comps = st.prefab_components("BoomAll")
    assert comps, "BoomAll must resolve to DeathBoomAll"
    f = st.prefab_ability_fields("BoomAll")
    assert "_projectileActions" in f or "_attackBlackboardModeIndex" in f
    hits = [e for e in st.enemy_skills("enemy_1543_cstlrs")
            if e.get("prefabKey") == "BoomAll"]
    assert hits, "synthesized BoomAll entry missing"
    syn = hits[0]
    assert syn.get("_synthesized") and syn.get("abilities")
    assert syn.get("enemyId") == "enemy_1543_cstlrs"


def test_spawn_wires_aliased_skills():
    sim = Simulator(level_id="level_main_01-01")
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True

    b.spawn_enemy("enemy_1512_mcmstr", 0)
    e = b.enemies[-1]
    sc = e.skill_controller
    run = next(s for s in sc.skills if s.prefab_key == "cuttree")
    assert run.prefab, "cuttree must carry the CutTree prefab fields"
    assert run.abilities, "cuttree must carry ability summaries"

    b.spawn_enemy("enemy_1543_cstlrs", 0)
    e2 = b.enemies[-1]
    sc2 = e2.skill_controller
    run2 = next(s for s in sc2.skills if s.prefab_key == "BoomAll")
    assert run2.prefab, "BoomAll must carry the DeathBoomAll prefab fields"
    assert run2.abilities


def test_shining_and_countdown_local_overrides():
    st = DataStore()
    # Shining (enemy_2138/2139 \u6c49\u79d1 flare): no GameObject named
    # Shining exists in the base catalog; the local override supplies the
    # flare prefab (projectile_enemy_shdbjg_shining + smoke-disable buff)
    comps = st.prefab_components("Shining")
    assert comps and len(comps) == 3, comps
    f = st.prefab_ability_fields("Shining")
    assert f.get("_projectileKey") == "projectile_enemy_shdbjg_shining"
    assert f.get("_animKey") == "Skill"
    bks = [c for c in comps]
    buffs = []
    for c in bks:
        for k in ("_buffs", "_activeBuffs", "_passiveBuffs"):
            for b in (c.get("fields") or {}).get(k) or []:
                if isinstance(b, dict) and b.get("buffKey"):
                    buffs.append(b["buffKey"])
    assert "enemy_shsmok_disable" in buffs, buffs
    # Countdown (enemy_4064 \u51b3\u80dc\u65f6\u523b\u7403)
    comps2 = st.prefab_components("Countdown")
    assert comps2 and len(comps2) == 2, comps2
    f2 = st.prefab_ability_fields("Countdown")
    assert any("mupenb" in str(c.get("fields") or {})
               for c in comps2)


def test_new_enemies_spawn_with_resolved_skills():
    sim = Simulator(level_id="level_main_01-01")
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True

    b.spawn_enemy("enemy_2138_shdbjg", 0)     # \u6c49\u79d1
    e = b.enemies[-1]
    run = next(s for s in e.skill_controller.skills
               if s.prefab_key == "Shining")
    assert run.prefab.get("_projectileKey") == \
        "projectile_enemy_shdbjg_shining"
    assert [x.get("buffKey") for x in run.prefab_buffs] == \
        ["enemy_shsmok_disable"]
    # projectile speed already in the local table
    from ark_emulator.projectiles import projectile_speed
    assert projectile_speed("projectile_enemy_shdbjg_shining") == 10.0

    b.spawn_enemy("enemy_4064_mupenb", 0)     # \u51b3\u80dc\u65f6\u523b\u7403
    e2 = b.enemies[-1]
    run2 = next(s for s in e2.skill_controller.skills
                if s.prefab_key == "Countdown")
    # the countdown marker is a SELF buff (template triggers the owner's
    # own Countdown skill via BUFF_OWNER), not a target debuff
    assert [x.get("buffKey") for x in run2.prefab_buffs] == []
    assert "enemy_mupenb_start_count_down" in [
        x["data"].get("buffKey") for x in run2.self_buffs]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
