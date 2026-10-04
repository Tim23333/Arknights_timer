"""Export the root's independent checks with their exact final source bindings."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    tests = ROOT/"tools/experiments/m16_root_peer/test_terrain_review.py"
    execution = ROOT/"validation/campaign/m16_terrain/root_peer_tests_20261002.json"
    run = json.loads(execution.read_bytes())
    core = "669982006a81507973d8f3c3abb1f694d7ee9831de67ad2de1c0b3ea441df571"
    assert run["passed"] and run["implementation_before"] == core == run["implementation_after"]
    assert run["selection"] == ["tools\\experiments\\m16_root_peer\\test_terrain_review.py", "-q"]
    report = {"schema": "ark-sim/root-terrain-independent-review/v1", "passed": True,
        "reviewer": "/root", "author": "/root/campaign_roster", "implementation": core,
        "source_identity_recording": "Final source binding after the actual run; no in-process start-source capture claimed",
        "formal_stage_approved": False, "client_verified": False,
        "execution": {"path": execution.relative_to(ROOT).as_posix(), "sha256": sha(execution)},
        "test_source": {"path": tests.relative_to(ROOT).as_posix(), "sha256": sha(tests)},
        "exporter_sha256": sha(Path(__file__)), "bindings": {},
        "checks": [
            {"case": "blocking_owner_retire_preserves_second_layer_and_restored_live_grid",
                "claims": ["same owner key across two owners preserves surviving owner", "retire retains HP", "mask removal resumes actual walker", "checkpoint and recorded commands replay states and events equal"]},
            {"case": "rule_only_in_overlay_loads_and_invalid_numeric_output_rolls_back",
                "claims": ["overlay-only calculation dependency resolves", "nonpositive path cost rejects", "API-only atomic failure restores whole checkpoint"]},
            {"case": "actual_emp_preserves_native_pass_and_advanced_then_restores_after_withdraw",
                "claims": ["real EMP wrapper preserves pass3 advanced0 HIGHLAND", "source physicalHeight numeric .4 is consumed", "repeated tile reads preserve whole checkpoint", "withdraw restores original tile and command replay equals"]}],
        "limitations": ["No chapter 1 whole-stage execution", "No native method-body or client comparator claim", "Catalog agent peer review still pending"]}
    for relative in ("packages/campaign/chapter01_devices/emp.terrain.json", "packages/campaign/chapter01_devices/emp.source.json",
        "validation/campaign/m16_terrain/changed_files.json", "validation/campaign/m16_terrain/candidate_final.json"):
        report["bindings"][relative] = sha(ROOT/relative)
    output = ROOT/"validation/campaign/m16_terrain/root_peer_review_20261002.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps({"passed": True, "checks": 3, "report_sha256": sha(output)}))


if __name__ == "__main__": main()
