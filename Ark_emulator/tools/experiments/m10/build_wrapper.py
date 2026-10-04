"""Apply exactly two resource-policy declarations to frozen canonical content."""
from pathlib import Path
from copy import deepcopy
import json
import hashlib
import argparse

PRIMARY = Path(__file__).resolve().parents[3]
SOURCE = PRIMARY/"packages/campaign/mainline_models/level_main_00-10.m8_roster.json"
OUTPUT = PRIMARY/"packages/campaign/mainline_models/level_main_00-10.m10_resource_precision.json"
EVIDENCE = PRIMARY/"docs/campaign/candidates/M10_WRAPPER_SOURCE.json"


def build():
    original = json.loads(SOURCE.read_bytes()); data = deepcopy(original)
    def unit(cid): return next(e for e in data["entities"] if e["id"] == "unit/"+cid)
    unit("char_010_chen")["components"]["resources"]["sp"]["recovery_freeze_abilities"] = ["ability/campaign_chen_s1"]
    unit("char_003_kalts")["components"]["resources"]["sp"]["recovery"]["interrupt_abilities"] = ["ability/kalts_host_s3"]
    # Remove only these newly added declarations and independently prove equality.
    restored = deepcopy(data)
    for cid, section, key in [("char_010_chen", "freeze", "recovery_freeze_abilities"), ("char_003_kalts", "interrupt", "interrupt_abilities")]:
        target = next(e for e in restored["entities"] if e["id"] == "unit/"+cid)["components"]["resources"]["sp"]
        (target if section == "freeze" else target["recovery"]).pop(key)
    assert restored == original
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    data = build(); text = json.dumps(data, ensure_ascii=False, indent=2)+"\n"
    if args.check:
        if not OUTPUT.exists() or json.loads(OUTPUT.read_bytes()) != data: raise SystemExit("M10 resource wrapper drift")
    else: OUTPUT.write_text(text, encoding="utf8", newline="\n")
    record = {"schema": "ark-sim/m10-resource-wrapper-source/v1", "source": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "output": str(OUTPUT), "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), "exactly_two_resource_declarations_changed": True,
        "scope": {"unit/char_010_chen": {"recovery_freeze_abilities": ["ability/campaign_chen_s1"]},
                  "unit/char_003_kalts": {"recovery.interrupt_abilities": ["ability/kalts_host_s3"]}},
        "all_other_definitions_equal": True, "client_body_verified": False}
    flags = {}
    for filename in ("skills.chen.json", "skills.kalts.json"):
        path = PRIMARY/"packages/campaign"/filename; rows = []
        def walk(value, label):
            if isinstance(value, dict):
                if "_allowSpRecoveryWhenAffecting" in value: rows.append({"path": label, "value": value["_allowSpRecoveryWhenAffecting"]})
                for key, child in value.items(): walk(child, label+"."+key)
            elif isinstance(value, list):
                for i, child in enumerate(value): walk(child, label+f"[{i}]")
        walk(json.loads(path.read_bytes()), filename)
        flags[filename] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "raw_allow_sp_flags": rows}
    record["source_recipe_flags"] = flags
    EVIDENCE.write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print("M10 wrapper generated/checked", OUTPUT)
