"""W normal attack + HP/C4 composition using explicit replaceable model profiles.

This is content authoring, not a native Boss/FSM or full-stage implementation.
All Engine probes import a pinned independent runtime root, never primary.
"""
from __future__ import annotations
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "packages/campaign/chapter01_sources/native.reference.json"
SOURCE_SHA = "a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd"
OUT = ROOT / "packages/campaign/chapter01_models/w_combat"
RUNTIME = ROOT.parent / "unpack_work/campaign_m10_cast_freeze_candidate"
EXPECTED = "f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e"
NORMAL = "ability/chapter01_w_normal_"
UNIT = "unit/chapter01_w"
C4 = "ability/chapter01_w_c4_"
PROFILES = {"two_full_packets_model": [9, 23], "first_signal_only_model": [9]}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def encoded(v): return (json.dumps(v, ensure_ascii=False, indent=2)+"\n").encode("utf8")


def build(profile="two_full_packets_model"):
    if profile not in PROFILES: raise ValueError("explicit normal packet profile unknown")
    from tools.build_chapter01_w_model import build as build_hp_c4
    from tools.extract_campaign_animation_bindings import parse_spine, library_identity
    if sha(SOURCE) != SOURCE_SHA: raise ValueError("frozen chapter01 source audit checksum changed")
    package = build_hp_c4()
    source = read(SOURCE); w = source["enemies"]["enemy_1504_cqbw"]
    reader_before = library_identity()
    payload = base64.b64decode(w["animation"]["payload_base64"], validate=True)
    if hashlib.sha256(payload).hexdigest() != w["animation"]["payload_sha256"]:
        raise ValueError("native animation raw payload checksum changed")
    if parse_spine(payload) != w["animation"]["parsed"] or library_identity() != reader_before:
        raise ValueError("fresh controlled reader and frozen animation disagree")
    if reader_before != source["spine_library_identity"]: raise ValueError("native Spine reader identity drift")
    native_projectile = source["projectiles"]["projectile_enemy_cqbw"]
    attrs = w["native_enemy"]["resolved"]["attributes"]
    if (attrs["atk"], attrs["baseAttackTime"], w["native_enemy"]["resolved"]["rangeRadius"]) != (470, 4, 2.5):
        raise ValueError("W DB normal attack inputs changed")
    normals = []
    components = w["prefab"]["components"]
    if len(w["modes"]) != 2: raise ValueError("native mode count changed")
    for mode in w["modes"]:
        normal = components[str(mode["combat_path_id"])]
        f = normal["raw"]
        if normal["native_class"] != "RangedAttack" or (f["_waitForAttackEvent"], f["_timeMode"], f["_damageType"], f["_atkScale"],
            f["_projectileKey"], f["_waitForProjectileInvalid"], f["_useCachedAtkOnly"]) != (1, 0, 1, 1, "projectile_enemy_cqbw", 0, 0):
            raise ValueError("native normal RangedAttack inputs changed")
        anim = mode["attack_animation"]
        if [(e["name"], e["frame"], e["exact_authored_frame"]) for e in anim["events"]] != [("OnAttack", 9, True), ("OnAttack", 23, True)]:
            raise ValueError("normal authored animation event binding changed")
        mode_go = mode["raw_mode"]["m_GameObject"]["m_PathID"]
        descendants = {mode_go}
        while True:
            next_ids = descendants | {r["path_id"] for r in w["prefab"]["hierarchy"] if r["parent_path_id"] in descendants}
            if next_ids == descendants: break
            descendants = next_ids
        selectors = [c for c in components.values() if c["native_class"] == "AdvancedSelector" and c["gameobject_path_id"] in descendants]
        if len(selectors) != 1: raise ValueError("mode subtree normal selector missing/ambiguous")
        sf = selectors[0]["raw"]
        if (sf["_targetSide"], sf["_targetMotion"], sf["_postFilter"], sf["_maxNum"]) != (2, 1, 4, 1):
            raise ValueError("native normal selector side/motion/priority/count changed")
        trigger = components[str(mode["raw_mode"]["_attackTrigger"]["m_PathID"])]
        if trigger["native_class"] != "SelectorTrigger": raise ValueError("normal trigger pointer class mismatch")
        # Exact descendant membership proves serialized containment; it cannot
        # prove the missing implicit-selector inheritance method body.
        normals.append({"mode_index": mode["index"], "mode_source": mode, "combat_source": normal,
            "selector_source": selectors[0], "attack_trigger_source": trigger,
            "selector_binding_evidence": "exact mode subtree containment; null combat selector inheritance body pending"})
    movers = [c for c in native_projectile["components"].values() if c["native_class"] == "ParacurveMovement"]
    simples = [c for c in native_projectile["components"].values() if c["native_class"] == "SimpleProjectile"]
    if len(movers) != 1 or len(simples) != 1: raise ValueError("normal projectile closure ambiguous")
    mover, projectile = movers[0]["raw"], simples[0]["raw"]
    if (mover["_speed"], projectile["_lifeTime"], projectile["_maxHitNum"], projectile["_stopAfterMaxHit"],
            projectile["_stopWhenSourceInvalid"], projectile["_alwaysHitTraceTargetInTheEnd"]) != (5, 10, 1, 1, 0, 1):
        raise ValueError("normal projectile speed/lifetime/hit flags changed")
    identities = {"chapter01_source_audit": sha(SOURCE), "prior_HP_C4_builder": sha(ROOT / "tools/build_chapter01_w_model.py"),
        "new_builder": sha(Path(__file__)), "offline_source_helper": sha(ROOT / "tools/build_chapter01_enemy_sources.py"),
        "animation_reader_helper": sha(ROOT / "tools/extract_campaign_animation_bindings.py")}
    native_ids = {}
    for r in [*source["sources"].values(), w["prefab"]["source"], w["animation"]["source"], native_projectile["source"]]:
        path = ROOT.parent / r["path"]
        if not path.is_file() or sha(path) != r["sha256"]: raise ValueError("native source changed: " + r["path"])
        native_ids[r["path"]] = r["sha256"]
    package["rules"] = [{"id": "rule/chapter01_w_flight", "kind": "calculation_rule", "contract": "projectile.flight_time",
        "implementation": {"type": "expression", "expression": "min(inputs.distance / inputs.speed, params.lifetime_seconds)"},
        "parameters": {"lifetime_seconds": 10}, "metadata": {"profile": "launch_distance_speed_cap_v1", "client_verified": False}}]
    for index in (0, 1):
        sid = "selector/chapter01_w_normal_"+str(index)
        package["selectors"].append({"id": sid, "kind": "selector", "region": {"type": "radius", "radius": 2.5},
            "filters": [{"tag": "player"}, {"tag": "ground"}, {"state": "alive"}], "ordering": "stable", "limit": 1})
        ability = {"id": NORMAL+str(index), "kind": "ability", "activation": {"mode": "automatic_attack",
            "condition": f"inputs.resources.mode.current == {index}"}, "selector": sid, "target_capture": "at_cast",
            "parameters": {"projectile_speed": 5}, "rules": {"projectile.flight_time": "rule/chapter01_w_flight"},
            "metadata": {"native_mode": index, "packet_profile": profile, "native_two_events_not_packet_count_proof": True},
            "timeline": [{"at_seconds": frame/30, "effect": {"op": "damage", "damage_type": "physical", "scale": 1,
                "condition": "inputs.targets[0].components.runtime.alive",
                "read_mode": {"source_attributes": "at_hit", "target_attributes": "at_hit"}}} for frame in PROFILES[profile]]}
        package["abilities"].append(ability); package["entities"][0]["components"]["abilities"].append(ability["id"])
    for ability in package["abilities"]:
        if ability["id"].startswith(C4):
            ability["activation"]["parameters"].update(cancel_pending_attacks=True, reset_attack_clock=True)
    meta = package["manifest"]["metadata"]
    meta["model_gaps"] = [g for g in meta["model_gaps"] if g != "normal_attack_not_authored"]
    meta["model_gaps"] += ["native_Paracurve_collision_tracking_and_projectile_expiry_not_converted", "native_C4_AttachToTarget_invalid_callback_not_converted"]
    meta["profiles"].update(normal_packet={"selected": profile, "available": PROFILES,
        "interpretation": "explicit model selection: one full physical packet per selected authored signal; animation events alone do not prove native packet count",
        "target": "one ground player captured at cast; stable runtime ID ordering replaces native postFilter4 priority",
        "clock": "DB4s/ASPD100; unscaled frame9/23; mode restart cancels unlaunched normal tasks; native FSM pending",
        "flight": "launch planar distance /speed5 capped10s, captured ID; source retirement preserves launched packet, target retirement discards packet",
        "C4_interlock": "cancel pending normal tasks + reset attack clock at C4 start; already launched projectiles remain; block new normal casts until C4 finishes"})
    meta.update(builder_sha256=sha(Path(__file__)), source_identities=identities, status="partial_W_normal_HP_C4_composed_model",
        full_enemy_implemented=False, formal_stage_approved=False)
    package["manifest"]["id"] = "package/campaign/chapter01_w_combat_model"
    source_out = {"schema": "ark-sim/chapter01-w-combat-source/v1", "identities": identities, "native_source_sha256": native_ids,
        "native_enemy": w["native_enemy"], "normal_modes": normals, "prefab": w["prefab"], "animation": w["animation"],
        "normal_projectile": native_projectile, "BSON": source["bson"], "native_monoscripts": source["native_monoscripts"],
        "native_class_declarations": source["native_class_declarations"], "spine_reader_identity": source["spine_library_identity"],
        "method_bodies_recovered": False, "profile": profile, "client_pending": meta["client_pending"],
        "gap_matrix": {"normal_source_fields_and_authored_frames": "resolved", "normal_model_damage_flight_capture_clock": "executable_declared_profile",
            "native_signal_to_packet_and_GetTimeScale": "client_pending", "native_selector_priority_filters": "client_pending",
            "HP_boundary_and_C4_timer": "inherited_explicit_model", "C4_attach_expiry_invalid_callbacks": "model_gap",
            "native_Paracurve_body_collision_tracking": "model_gap", "full_stage_and_full_Boss": "not_executed_not_complete"}}
    return source_out, package


def runtime(root, expected):
    root = root.resolve(); sys.path.insert(0, str(root))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    actual = Path(ark_sim.__file__).resolve()
    if actual.parent != root / "ark_sim": raise RuntimeError("wrong runtime import: " + str(actual))
    if implementation_digest() != expected: raise RuntimeError("runtime implementation does not match explicit pin")
    return {"runtime_root": root.as_posix(), "actual_import": actual.as_posix(), "implementation_digest": expected}


def fixture(package, positions=((3, 4),), automatic_c4=False, phase=0):
    from tools.build_chapter01_w_model import fixture as old_fixture
    p = old_fixture(package, positions=positions, automatic=automatic_c4)
    p["scenarioDraft"]["resources"] = {"dp": {"initial": 0, "capacity": 99}}
    # Content fixture choice: suppress C4 clock only when isolating normals.
    if not automatic_c4:
        for i in (0, 1):
            r = p["entities"][0]["components"]["resources"][f"c4_clock_{i}"]
            r.update(initial=0, recovery_rate=0)
    p["entities"][0]["components"]["resources"]["mode"]["initial"] = phase
    if phase == 1:
        p["entities"][0]["components"]["resources"]["hp"]["initial"] = 5000
    return p


def verify(package, identity):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    checks = []
    def make(p): return Engine.create(Compiler().compile(p), seed=811)
    def launches(s): return [e for e in s.session.events if e["type"] == "projectile.launched"]
    def normal_starts(s): return [e for e in s.session.events if e["type"] == "ability.started" and e["payload"]["ability"].startswith(NORMAL)]
    for phase in (0, 1):
        s = make(fixture(package, phase=phase)); s.advance(15)
        assert s.ctx.resources.current("target0", "hp") == 5000
        s.advance(1); assert s.ctx.resources.current("target0", "hp") == 4630
        s.advance(14); assert s.ctx.resources.current("target0", "hp") == 4260
        assert [e["time"] for e in launches(s)] == [9, 23]
        assert [e["payload"]["flight_seconds"] for e in launches(s)] == [.2, .2]
        cp = s.checkpoint(); r = Engine.restore(s.program, cp); s.advance(106); r.advance(106)
        assert s.ctx.resources.current("target0", "hp") == 3890
        assert [e["time"] for e in normal_starts(s)] == [0, 120]
        assert first_difference(s.snapshot(), r.snapshot()) is None
        assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
        checks.append({"case": "normal_phase_"+str(phase), "launch_ticks": [9, 23, 129], "impact_ticks": [15, 29, 135],
            "damage_per_packet": 470-100, "cast_ticks": [0, 120], "checkpoint_equal": True, "commands_replay_equal": True,
            "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint})
    # Capture one identity for both selected signals; no second target splash.
    s = make(fixture(package, positions=((3, 4), (3, 5)))); s.advance(30)
    assert [s.ctx.resources.current("target"+str(i), "hp") for i in (0, 1)] == [4260, 5000]
    checks.append({"case": "target_capture_isolation", "HP": [4260, 5000]})
    # Real recorded withdraw commands demonstrate source and target retirement.
    for ref, expected in (("w", 4630), ("target0", 5000)):
        s = make(fixture(package)); s.advance(10)
        s.submit({"action": "withdraw", "source": ref}); s.advance(25)
        assert s.ctx.resources.current("target0", "hp") == expected
        assert len(launches(s)) == 1
        assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
        checks.append({"case": "withdraw_"+ref, "target_HP": expected, "launch_count": 1, "commands_replay_equal": True})
    # Manual fixture C4 owns the same source; start at t10 after first normal
    # launch. Cancellation affects signal23; launched signal9 still impacts15.
    p = fixture(package)
    p["entities"][0]["components"]["resources"]["c4_clock_0"]["initial"] = 20
    s = make(p); s.advance(10)
    s.submit({"action": "skill", "source": "w", "ability": C4+"0"}); s.advance(114)
    assert [e["time"] for e in launches(s)] == [9]
    assert s.ctx.resources.current("target0", "hp") == 4630
    cp = s.checkpoint(); r = Engine.restore(s.program, cp); s.advance(17); r.advance(17)
    assert s.ctx.resources.current("target0", "hp") == 3514  # 5000 -370 -746 -370
    assert [e["time"] for e in launches(s)] == [9, 134]
    assert first_difference(s.snapshot(), r.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
    checks.append({"case": "C4_interlock", "C4_start": 10, "C4_impact": 124, "normal_launches": [9, 134],
        "target_HP": 3514, "checkpoint_equal": True, "commands_replay_equal": True})
    # HP event-driven phase entry/exit uses recorded commands, not ctx writes.
    p = fixture(package, automatic_c4=True)
    for name, hp in (("half", 5000), ("restore", 5001)):
        aid = "ability/w_combat_probe_"+name
        p["abilities"].append({"id": aid, "kind": "ability", "activation": {"mode": "manual",
            "on_start": [{"op": "modify_resource", "target": "source", "resource": "hp", "value": hp}]},
            "parameters": {"blocks_attacks": False}, "timeline": []})
        p["entities"][0]["components"]["abilities"].append(aid)
    s = make(p); s.advance(5); s.submit({"action": "skill", "source": "w", "ability": "ability/w_combat_probe_half"}); s.advance(3)
    assert s.ctx.resources.current("w", "mode") == 1
    # Phase enter seeds C4 ready: explicit inherited immediate T1 clock policy.
    s.advance(116); assert s.ctx.resources.current("target0", "hp") == 4254
    s.submit({"action": "skill", "source": "w", "ability": "ability/w_combat_probe_restore"}); s.advance(18)
    assert s.ctx.resources.current("w", "mode") == 0
    # Read stored base without adding an out-of-band calculation.trace event
    # that a command-only replay would correctly not reproduce.
    assert s.ctx.get("w", ("attributes", "base", "atk")) == 470
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
    checks.append({"case": "recorded_half_HP_restore", "half_mode": 1, "restore_mode": 0, "ATK_both": 470,
        "normal_modes_started": [e["payload"]["ability"] for e in normal_starts(s)], "commands_replay_equal": True})
    if implementation_digest() != identity["implementation_digest"]: raise RuntimeError("runtime changed during probes")
    return {"schema": "ark-sim/chapter01-w-combat-assertions/v1", "runtime": identity, "checks": checks,
        "passed": True, "client_verified": False, "full_enemy_implemented": False, "formal_stage_approved": False,
        "model_sha256": hashlib.sha256(encoded(package)).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--check", action="store_true")
    p.add_argument("--runtime-root", type=Path, default=RUNTIME); p.add_argument("--expected-digest", default=EXPECTED)
    args = p.parse_args()
    identity = runtime(args.runtime_root, args.expected_digest)
    source, model = build()
    # Offline author helpers add ROOT to sys.path. The imported runtime package
    # is already pinned, and actual __file__/digest is rechecked below.
    sys.path.insert(0, str(args.runtime_root.resolve()))
    evidence = verify(model, identity)
    _, alternative = build("first_signal_only_model")
    from ark_sim import Compiler
    Compiler().compile(fixture(alternative))
    evidence["alternative_first_signal_profile_compiles"] = True
    evidence["builder_sha256"] = sha(Path(__file__))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("native.reference.json", source), ("model.json", model),
            ("first_signal.model.json", alternative), ("probe.json", fixture(model)), ("assertions.json", evidence)):
        path = OUT/name
        if args.check:
            if not path.exists() or path.read_bytes() != encoded(value): raise ValueError("W combat artifact drift: "+name)
        else: path.write_bytes(encoded(value))
    print(json.dumps({"passed": True, "checks": len(evidence["checks"]), "runtime": identity, "full_boss": False}))


if __name__ == "__main__": main()
