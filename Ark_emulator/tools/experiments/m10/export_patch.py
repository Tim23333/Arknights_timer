"""Export isolated M10 changes relative to the retained queue-bounds base."""
from pathlib import Path
import json
import base64
import hashlib
import difflib
PRIMARY = Path(__file__).resolve().parents[3]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m10_cast_freeze_candidate"
DOCS = PRIMARY/"docs/campaign/candidates"
base = json.loads((DOCS/"m10_cast_freeze_baseline.json").read_bytes())
patch = []; hashes = {}
for name, record in sorted(base["files"].items()):
    path = CANDIDATE/"ark_sim"/name
    old = base64.b64decode(record["base64"]).decode().replace("\r\n", "\n")
    new = path.read_text(encoding="utf8")
    hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    patch.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile="a/ark_sim/"+name, tofile="b/ark_sim/"+name))
(DOCS/"M10_CAST_RESOURCE.patch").write_text("".join(patch), encoding="utf8", newline="\n")
(DOCS/"M10_SOURCE_HASHES.json").write_text(json.dumps({"base_digest": base["base_digest"], "candidate_root": str(CANDIDATE),
    "files": hashes, "diff_normalizes_line_endings_hashes_cover_actual_bytes": True}, indent=2)+"\n", encoding="utf8", newline="\n")
print("M10 patch exported; source hashes locked")
