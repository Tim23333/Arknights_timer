"""Export owned route changes; keep root's scheduler-fork edits separate."""
import base64
import difflib
import hashlib
import json
from pathlib import Path

PRIMARY = Path(__file__).resolve().parents[2]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m9_candidate"
DOCS = PRIMARY/"docs/campaign/candidates"


if __name__ == "__main__":
    baseline = json.loads((DOCS/"m9_route_baseline.json").read_bytes())
    patches = []; hashes = {}
    for name, record in sorted(baseline["files"].items()):
        original = base64.b64decode(record["base64"]).decode("utf8").replace("\r\n", "\n")
        path = CANDIDATE/"ark_sim"/name; current = path.read_text(encoding="utf8")
        hashes["ark_sim/"+name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if name in ("domains/abilities.py", "domains/buffs.py"):
            # The independent M9_SCHEDULER_FORK.patch owns these three reads.
            current = current.replace('.scheduler.next_task_id', '.scheduler.snapshot()["next_id"]')
        patches.extend(difflib.unified_diff(original.splitlines(True), current.splitlines(True),
            fromfile="a/ark_sim/"+name, tofile="b/ark_sim/"+name))
    (DOCS/"M9_ROUTE_VISIBILITY.patch").write_text("".join(patches), encoding="utf8", newline="\n")
    (DOCS/"m9_route_source_hashes.json").write_text(json.dumps({"candidate_baseline_digest": baseline["candidate_baseline_digest"],
        "files": hashes, "scheduler_fork_edits_excluded_from_route_patch": True,
        "patch_review_normalizes_line_endings_actual_hashes_do_not": True}, indent=2)+"\n", encoding="utf8", newline="\n")
    print("route patch and actual candidate source hashes exported")
