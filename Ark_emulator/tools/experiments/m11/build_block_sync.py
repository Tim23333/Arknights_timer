"""New content wrapper for synchronous selected skill NoBlock; source unchanged."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
CANDIDATE = ROOT.parent / "unpack_work/campaign_m11_block_sync_candidate"
OUTPUT = ROOT / "packages/campaign/mainline_models/level_main_00-10.m11_block_sync.json"
SOURCE = ROOT / "packages/campaign/mainline_models/level_main_00-10.m10.json"


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    original = json.loads(SOURCE.read_bytes()); p = deepcopy(original)
    skill = next(a for a in p["abilities"] if a["id"] == "ability/campaign_myrtle_s2")
    first = skill["timeline"].pop(0)
    if first.get("at") != 0 or first["effect"].get("buff") != "buff/campaign_myrtle_no_block":
        raise ValueError("frozen NoBlock source timeline changed")
    skill["activation"]["on_start"] = [first["effect"], *skill["activation"].get("on_start", [])]
    skill.setdefault("parameters", {})["cancel_pending_attacks"] = True
    buff = next(b for b in p["buffs"] if b["id"] == "buff/campaign_myrtle_no_block")
    buff.setdefault("control", {})["block"] = False
    meta = p["manifest"].setdefault("metadata", {})
    meta["M11_block_sync"] = {"source": SOURCE.relative_to(ROOT).as_posix(), "source_sha256": sha(SOURCE),
        "builder_sha256": sha(Path(__file__)), "source_skill_sha256": sha(ROOT / "packages/campaign/skills.myrtle.json"),
        "base_core": "c0b92545a714e763f3e43d4e13d25f0be99ecda912cb8479536982ac38f8216e",
        "scope": "on_start NoBlock + explicit control.block=False + own unlaunched normal cancellation",
        "enemy_existing_cast_policy": "relation change preserves already started/launched attacks; only new stale-block casts prevented",
        "native_FSM_and_existing_attack_cancel_policy": "client_pending", "formal_approval": False}
    return p


def scene(held=False):
    p = build()
    p["scenarioDraft"].update(id="scenario/m11_block_boundary", map={"rows": 9, "cols": 12}, waves=[], scheduledEffects=[], objectives={},
        initialEntities=[{"definition": "unit/char_151_myrtle", "instanceAlias": "myrtle", "position": {"row": 4, "col": 4},
            "components": {"resources": {"sp": {"initial": 24}}}},
            {"definition": "unit/enemy_1000_gopro", "instanceAlias": "enemy", "position": {"row": 4, "col": 4},
                "route": {"motionMode": "WALK", "endPosition": {"row": 4, "col": 8}}}])
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); args = ap.parse_args()
    value = (json.dumps(build(), ensure_ascii=False, indent=2)+"\n").encode("utf8")
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != value: raise ValueError("M11 content wrapper drift")
    else: OUTPUT.write_bytes(value)
    print(json.dumps({"output": OUTPUT.as_posix(), "sha256": hashlib.sha256(value).hexdigest(), "core_modified": False}))
