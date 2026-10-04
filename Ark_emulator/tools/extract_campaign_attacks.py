"""Freeze the twelve native base attack chains; extraction is not conversion."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/"packages/campaign/attacks.reference.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer_id(pointer):
    if not isinstance(pointer, dict) or pointer.get("m_FileID") != 0 or not pointer.get("m_PathID"):
        raise ValueError("required base attack reference is null or external")
    return pointer["m_PathID"]


def read_chain(character_id, config):
    import UnityPy
    directory = ROOT.parent/"data/charpack"/(character_id+".ab_unpacked")
    candidates = sorted(directory.glob("CAB-*"))
    if len(candidates) != 1:
        raise ValueError(f"exactly one native character CAB is required: {character_id}")
    path = candidates[0]
    trees = {obj.path_id: obj.read_typetree() for obj in UnityPy.load(str(path)).objects
             if obj.type.name == "MonoBehaviour"}
    roots = [(key, value) for key, value in trees.items() if "_modes" in value]
    if len(roots) != 1 or not roots[0][1]["_modes"]:
        raise ValueError(f"base mode root is ambiguous or absent: {character_id}")
    root_id, root = roots[0]
    mode_id = pointer_id(root["_modes"][0])
    mode = trees[mode_id]
    attack_id = pointer_id(mode["_attack"])
    attack = trees[attack_id]
    selected = {root_id, mode_id, attack_id}
    for field in ("_combat", "_attackTrigger"):
        pointer = mode.get(field, {})
        if pointer.get("m_FileID") == 0 and pointer.get("m_PathID") in trees:
            selected.add(pointer["m_PathID"])
    # Root mode references beyond zero remain source evidence, not part of the
    # base-mode closure. Follow local Mono links within the selected components.
    pending = list(selected-{root_id})
    external = []
    def visit(value):
        if isinstance(value, dict):
            if "m_FileID" in value and "m_PathID" in value and value["m_PathID"]:
                if value["m_FileID"]:
                    external.append(value)
                elif value["m_PathID"] in trees and value["m_PathID"] not in selected:
                    selected.add(value["m_PathID"])
                    pending.append(value["m_PathID"])
            else:
                for key, child in value.items():
                    if not key.startswith("m_"):
                        visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    while pending:
        visit(trees[pending.pop()])
    frames_path = ROOT.parent/"data/tables/effect_frames.json"
    frame_data = json.loads(frames_path.read_text(encoding="utf-8"))["characters"].get(character_id)
    if frame_data is None:
        raise ValueError(f"native animation frame evidence is absent: {character_id}")
    return {"character_id": character_id, "config": config, "status": "source_frozen_not_converted",
            "runnable": False, "root_path_id": root_id, "base_mode_path_id": mode_id, "attack_path_id": attack_id,
            "source": {"path": path.relative_to(ROOT.parent).as_posix(), "sha256": sha(path)},
            "components": {str(key): {"script_path_id": trees[key].get("m_Script", {}).get("m_PathID"),
                                      "fields": {k: v for k, v in trees[key].items() if not k.startswith("m_")}}
                           for key in sorted(selected)},
            "base_attack_fields": {key: value for key, value in attack.items() if not key.startswith("m_")},
            "animation_evidence": frame_data, "external_references": external,
            "pending": ["animation_scaling_and_event_alignment", "target_filter_translation",
                        "talents_and_trait_application", "source_version_correspondence"]}


def build():
    normalized_path = ROOT/"packages/campaign/operators.normalized.json"
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    rows = [read_chain(row["character_id"], row["config"]) for row in normalized["operators"]]
    return {"schema": "ark-sim/campaign-base-attacks-reference/v1", "status": "source_frozen_not_converted",
            "runnable": False, "normalized_sha256": sha(normalized_path),
            "frame_source_sha256": sha(ROOT.parent/"data/tables/effect_frames.json"), "operators": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.check:
        if json.loads(args.output.read_text(encoding="utf-8")) != result:
            raise ValueError("base attack source identity or contents drifted")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"operators": len(result["operators"]), "runnable": False}))


if __name__ == "__main__":
    main()
