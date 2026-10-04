"""Campaign inventory and guarded V2 execution; a decoded level is not a pass."""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed_roster(reference):
    rows = reference.get("roster", [])
    ids = [row["character_id"] for row in rows]
    if len(ids) != 12 or len(set(ids)) != 12:
        raise ValueError("campaign requires exactly twelve unique fixed operators")
    for row in rows:
        config = row["config"]
        expected = {"elite_phase": 2, "level": 70, "potential": 1, "potential_rank": 0,
                    "trust_percent": 100, "mastery": 3, "skill_rank": 7,
                    "skill_level_index": 9, "equipment_id": None, "equipment_level": 0}
        if any(type(config.get(key)) is not type(value) or config.get(key) != value for key, value in expected.items()):
            raise ValueError("fixed campaign configuration changed; create an explicit goal/profile revision")
    raw = (json.dumps(reference["frozen"], ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != reference["frozen_sha256"]:
        raise ValueError("frozen roster dependency bytes do not match their identity")
    return ids


def audit_recovery(record, root=ROOT):
    if record is None:
        return "missing", ["native_data_not_recovered"]
    output = record.get("output_path")
    if not output:
        return "failed", [record.get("error", "native_data_decode_failed")]
    path = root / output
    if not path.exists() or sha(path) != record["output_sha256"]:
        return "stale", ["recovered_content_identity_mismatch"]
    provenance = [(record.get("source_path"), record.get("source_sha256")),
                  (ROOT.parent/"ark_parser/enemy/extract_level_data.py", record.get("helper_sha256")),
                  (ROOT.parent/"ark_parser/enemy/extract_enemy_data.py", record.get("fb_helper_sha256")),
                  (ROOT/"tools/extract_campaign_levels.py", record.get("extractor_sha256"))]
    for source, expected in provenance:
        source = root/source if isinstance(source, str) else source
        if source is None or not source.exists() or sha(source) != expected:
            return "stale", ["native_source_or_decoder_identity_mismatch"]
    if record.get("core_status") == "reference_verified":
        reference = root / record["reference_path"]
        if not reference.exists() or sha(reference) != record["reference_sha256"]:
            return "stale", ["native_reference_identity_mismatch"]
        if not record.get("core_exact_equal") or record.get("differences"):
            return "mismatched", ["core_reference_comparison_failed"]
        decoded, native = load(path), load(reference)
        from tools.extract_campaign_levels import canonical_core
        if canonical_core(decoded) != canonical_core(native):
            return "mismatched", ["actual_core_reference_comparison_failed"]
        return "core_reference_verified", list(record.get("unverified_root_fields", []))
    return record.get("core_status", "decoded_unverified"), list(record.get("issues", [])) + ["native_reference_comparison_pending"]


def execution_gate(program, case, reference):
    """Require a complete conversion contract before attempting a campaign run."""
    ids = fixed_roster(reference)
    metadata = program.scenario.get("metadata", {}).get("campaign", {})
    if metadata.get("native_level_id") != case["level_id"]:
        raise ValueError("compiled scenario belongs to a different native level")
    if metadata.get("roster_frozen_sha256") != reference["frozen_sha256"]:
        raise ValueError("compiled squad does not lock the selected twelve-person profile")
    actual = [program.definitions[ref].get("metadata", {}).get("native_id")
              for ref in program.scenario.get("roster", ())]
    if sorted(actual) != sorted(ids):
        raise ValueError("compiled scenario does not contain exactly the fixed twelve-person roster")
    pending = metadata.get("pending_mechanics")
    if pending is None or pending:
        raise ValueError("campaign conversion must explicitly resolve all pending native mechanics")
    if metadata.get("native_fields_verified") is not True:
        raise ValueError("only core geometry has been checked; required native fields remain unverified")
    declarations = metadata.get("selected_skill_definitions", {})
    for row in reference["roster"]:
        ref = declarations.get(row["character_id"])
        ability = program.definitions.get(ref, {})
        if (ability.get("kind") != "ability" or
                ability.get("metadata", {}).get("native_skill_id") != row["config"]["skill_id"]):
            raise ValueError(f"selected native skill is absent or substituted: {row['character_id']}")
        unit = next(program.definitions[ref] for ref in program.scenario["roster"]
                    if program.definitions[ref].get("metadata", {}).get("native_id") == row["character_id"])
        if declarations[row["character_id"]] not in unit.get("components", {}).get("abilities", ()):
            raise ValueError(f"selected skill is not owned by its operator: {row['character_id']}")
    witnesses = metadata.get("mechanic_tests", {})
    required = metadata.get("required_mechanics")
    if not required or any(not witnesses.get(key) for key in required):
        raise ValueError("required campaign mechanics lack explicit independent test references")
    return metadata


def object_identity(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def atomic_json(path, value):
    """Replace only after a complete fsynced write; preserve the old result on failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_case_result(native_id, result, root=ROOT):
    if not re.fullmatch(r"main_\d{2}-\d+", native_id):
        raise ValueError("invalid campaign native ID")
    path = root/"validation/campaign/results"/f"{native_id}.json"
    # Keep every previous receipt, rather than discarding a successful run on
    # refresh or source revision. The current pointer is committed atomically.
    if path.exists():
        previous = load(path)
        history = path.parent/"history"/native_id/f"{object_identity(previous)}.json"
        if not history.exists():
            atomic_json(history, previous)
    atomic_json(path, result)
    return path


def case_inputs(case, reference, root=ROOT):
    from ark_sim.adapters.api import implementation_digest
    return {"content_sha256": sha(root/case["planned_content"]),
            "commands_sha256": sha(root/case["planned_commands"]),
            "roster_full_sha256": object_identity(reference),
            "roster_profile_sha256": object_identity([{ "character_id": row["character_id"], "config": row["config"]}
                                                       for row in reference["roster"]]),
            "implementation_sha256": implementation_digest(),
            "native_source_sha256": case.get("native_source_sha256")}


def review_gate(case, reference, root=ROOT):
    """Trust an independent conversion review, never a package's self-description."""
    path = root/"validation/campaign/reviews"/f"{case['native_id']}.json"
    if not path.exists():
        raise ValueError("independent conversion review receipt is required before campaign execution")
    receipt = load(path)
    expected = case_inputs(case, reference, root)
    if (receipt.get("schema") != "ark-sim/campaign-conversion-review/v1" or
            receipt.get("status") != "approved_for_model_run" or
            receipt.get("native_id") != case["native_id"] or
            receipt.get("input_identity") != expected or not receipt.get("reviewer")):
        raise ValueError("conversion review receipt is absent, incomplete or stale")
    checks = ("unit_attributes_and_growth", "selected_skills_and_talents", "native_enemy_dependencies",
              "map_routes_controls_and_objectives", "no_substituted_or_ignored_mechanics")
    if any(receipt.get("checks", {}).get(key) != "passed" for key in checks):
        raise ValueError("conversion review receipt lacks required independent checks")
    evidence = receipt.get("test_evidence", [])
    if not evidence:
        raise ValueError("conversion review receipt must reference executed independent tests")
    for record in evidence:
        evidence_path = root/record["path"]
        if not evidence_path.exists() or sha(evidence_path) != record["sha256"]:
            raise ValueError("reviewed test evidence identity mismatch")
        results = load(evidence_path)
        if (results.get("passed") is not True or
                results.get("implementation_sha256") != expected["implementation_sha256"] or
                not results.get("tests")):
            raise ValueError("independent test evidence is missing, failed or from a different implementation")
        for test in results["tests"]:
            test_path = root/test["path"]
            if not test_path.exists() or sha(test_path) != test["source_sha256"] or test.get("result") != "passed":
                raise ValueError("independent test source or result is stale")
    return receipt, expected


def run_case(case, reference, root=ROOT, max_ticks=18000):
    receipt, input_identity = review_gate(case, reference, root)
    from ark_sim import Compiler, Engine
    from ark_sim.tools.replay import replay
    import importlib.util
    import gc
    spec = importlib.util.spec_from_file_location("campaign_verification", ROOT/"tools/verify_v2_baseline.py")
    verification = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verification)
    observations = verification.observations
    content, commands = root / case["planned_content"], root / case["planned_commands"]
    program = Compiler().compile(content)
    metadata = execution_gate(program, case, reference)
    sim = Engine.create(program, seed=123)
    for entry in load(commands):
        action = dict(entry)
        sim.submit(action, at=action.pop("at"))
    sim.session.advance(min(300, max_ticks))
    checkpoint = sim.checkpoint()
    while not sim.ctx.state()["finished"] and sim.session.time < max_ticks:
        sim.session.advance(min(150, max_ticks-sim.session.time))
    state = sim.ctx.state()
    rejected = [event for event in sim.session.events if event["type"] == "command.rejected"]
    if not state["finished"] or state["result"] != "victory" or state["pending_waves"] or rejected:
        raise ValueError("campaign run did not satisfy victory, wave completion and legal-command gates")
    # Summons and transformations require their declared independent cases;
    # the scripted native wave count must still be preserved by conversion.
    expected = metadata.get("native_spawn_count")
    if (type(expected) is not int or expected <= 0 or expected != case["expected_native_spawns"]
            or expected != len(program.scenario.get("waves", ()))):
        raise ValueError("native SPAWN population was not preserved by conversion")
    if state["kills"] + state["leaks"] < expected:
        raise ValueError("native enemy lifecycle totals do not account for the wave population")
    expected_observations = observations(sim)
    record = sim.export_replay()
    until, runtime_fingerprint = sim.session.time, sim.runtime_fingerprint
    del sim
    gc.collect()
    continued = Engine.restore(program, checkpoint)
    continued.session.advance(until-continued.session.time)
    if observations(continued) != expected_observations:
        raise ValueError("checkpoint continuation differs")
    del continued, checkpoint
    gc.collect()
    if observations(replay(program, record)) != expected_observations:
        raise ValueError("campaign replay differs")
    return {"native_id": case["native_id"], "status": "model_passed_pending_review", "model_result": state,
            "model_status": "passed_pending_review", "input_identity": input_identity,
            "conversion_review_sha256": object_identity(receipt),
            "program_fingerprint": program.fingerprint, "runtime_fingerprint": runtime_fingerprint,
            "observations": expected_observations, "checkpoint_equal": True, "replay_equal": True,
            "client_status": "pending", "independent_review_status": "pending",
            "mechanic_test_references": dict(metadata["mechanic_tests"]), "replay": record}


def build_progress(catalog, reference, recovery, root=ROOT, run_ready=False):
    ids = fixed_roster(reference)
    recovered = {row["level_id"]: row for row in recovery.get("levels", [])}
    selected = sorted((row for row in catalog["stages"] if row["selected"]),
                      key=lambda row: (row["chapter"], row["native_sequence"]))
    cases = []
    for row in selected:
        recovery_row = recovered.get(row["level_id"])
        source_status, source_gaps = audit_recovery(recovery_row, root)
        native_spawns = 0
        if recovery_row and recovery_row.get("output_path") and source_status != "stale":
            native = load(root/recovery_row["output_path"])
            for wave in native.get("waves", []):
                for fragment in wave.get("fragments", []):
                    for action in fragment.get("actions", []):
                        kind = action.get("actionType", 0)
                        kind = kind.get("value", kind.get("name")) if isinstance(kind, dict) else kind
                        if kind in (0, "SPAWN"):
                            native_spawns += action.get("count", 1)
        case = {"chapter": row["chapter"], "native_id": row["native_id"], "code": row["code"],
                "level_id": row["level_id"], "source_status": source_status, "source_gaps": source_gaps,
                "expected_native_spawns": native_spawns,
                "native_source_sha256": recovery_row.get("source_sha256") if recovery_row else None,
                "planned_content": f"packages/mainline/{row['native_id']}.json",
                "planned_commands": f"scenarios/mainline/{row['native_id']}/commands.json",
                "status": "awaiting_v2_content", "model_status": "not_run", "client_status": "pending",
                "blockers": ["twelve_person_content_and_native_dependencies_not_converted"]}
        content, commands = root / case["planned_content"], root / case["planned_commands"]
        saved = root/"validation/campaign/results"/f"{row['native_id']}.json"
        archived = root/"validation/campaign/results/history"/row["native_id"]
        case["evidence_history"] = [str(p.relative_to(root)).replace("\\", "/") for p in sorted(archived.glob("*.json"))]
        if saved.exists():
            case["evidence_history"].append(str(saved.relative_to(root)).replace("\\", "/"))
            previous = load(saved)
            if content.exists() and commands.exists() and source_status == "core_reference_verified":
                try:
                    receipt, current_inputs = review_gate(case, reference, root)
                    if (previous.get("input_identity") == current_inputs and
                            previous.get("conversion_review_sha256") == object_identity(receipt) and
                            previous.get("status") == "model_passed_pending_review" and
                            previous.get("checkpoint_equal") is True and previous.get("replay_equal") is True):
                        from ark_sim import Compiler, Engine
                        current_program = Compiler().compile(content)
                        execution_gate(current_program, case, reference)
                        current_runtime = Engine.create(current_program, seed=123).runtime_fingerprint
                        if (previous.get("program_fingerprint") != current_program.fingerprint or
                                previous.get("runtime_fingerprint") != current_runtime):
                            raise ValueError("saved model evidence belongs to a different program/runtime")
                        case.update({key: value for key, value in previous.items() if key != "replay"})
                        case["blockers"] = []
                except (ValueError, KeyError):
                    pass
        if content.exists() and commands.exists():
            if case["model_status"] != "passed_pending_review":
                case["status"] = "awaiting_execution_gate"
            if run_ready:
                try:
                    if source_status != "core_reference_verified":
                        raise ValueError("native core source is not reference verified")
                    result = run_case(case, reference, root)
                    save_case_result(row["native_id"], result, root)
                    case.update(result)
                    case["model_status"] = "passed_pending_review"
                    case["blockers"] = []
                except Exception as exc:
                    case["status"] = "blocked"
                    case["model_status"] = "failed"
                    case["blockers"] = [f"{type(exc).__name__}: {exc}"]
                    save_case_result(row["native_id"], {"native_id": row["native_id"], "status": "blocked",
                        "model_status": "not_run", "client_status": "pending", "blockers": case["blockers"]}, root)
        cases.append(case)
    counts = {"targets": len(cases), "decoded": sum(c["source_status"] not in ("missing", "failed", "stale") for c in cases),
              "core_reference_verified": sum(c["source_status"] == "core_reference_verified" for c in cases),
              "v2_content_present": sum((root/c["planned_content"]).exists() for c in cases),
              "partial_model_files_present": sum((root/"packages/campaign/mainline_models"/f"{c['level_id']}.json").exists() for c in cases),
              "model_passed_pending_review": sum(c["model_status"] == "passed_pending_review" for c in cases),
              "accepted": 0, "client_verified": 0}
    return {"schema": "ark-sim/mainline-campaign-progress/v1", "goal_status": "active",
            "scope": "fixed twelve-person, selected normal mainline penultimate/final stages",
            "roster_ids": ids, "roster_frozen_sha256": reference["frozen_sha256"],
            "input_identities": {"catalog": object_identity(catalog), "roster": object_identity(reference),
                                 "recovery": object_identity(recovery)},
            "counts": counts, "cases": cases,
            "acceptance_note": "Source decoding and model victory do not imply mechanic coverage, independent review or client accuracy."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT/"packages/campaign/mainline_catalog.json")
    parser.add_argument("--roster", type=Path, default=ROOT/"packages/campaign/roster.reference.json")
    parser.add_argument("--recovery", type=Path, default=ROOT/"validation/campaign/data_recovery.json")
    parser.add_argument("--output", type=Path, default=ROOT/"validation/campaign/progress.json")
    parser.add_argument("--run-ready", action="store_true", help="execute only complete V2 cases; unresolved cases remain blocked")
    args = parser.parse_args()
    result = build_progress(load(args.catalog), load(args.roster), load(args.recovery), run_ready=args.run_ready)
    atomic_json(args.output, result)
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
