"""New wrapper records the standard cell profile; no selector angle edits."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "packages/campaign/mainline_models/level_main_00-10.m11_block_sync.json"
OUTPUT = ROOT / "packages/campaign/mainline_models/level_main_00-10.m12_projection.json"
PIN = "af46aea8d1ffde0261ca777268ee69a3e8aa1adfecadb8e79adcc2246c5771c0"


def build():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN: raise ValueError("frozen M11 input drift")
    p = json.loads(raw)
    p["manifest"]["metadata"]["M12_projection"] = {"source_sha256": PIN,
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "profile": "standard_grid_cells_floor_coordinate_plus_half_v1",
        "source_target_offsets_and_on_path": "half ties toward positive infinity; finite continuous coordinates",
        "continuous_regions": "circle/radius/manhattan use original continuous metric",
        "selector_override": "caller may replace entire selector provider",
        "native_continuous_comparator": "client_pending", "formal_approval": False}
    return p


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--check", action="store_true"); args = p.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2)+"\n").encode("utf8")
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != raw: raise ValueError("M12 content drift")
    else: OUTPUT.write_bytes(raw)
    print(json.dumps({"output": OUTPUT.as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "formal_approval": False}))
