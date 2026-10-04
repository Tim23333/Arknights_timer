"""Canonical source JSON wrappers; identifiers never enter the candidate kernel."""
from pathlib import Path
import sys
from copy import deepcopy
import json
import hashlib

PRIMARY = Path(__file__).resolve().parents[3]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m12_projection_candidate"
sys.path.insert(0, str(CANDIDATE)); sys.path.insert(1, str(PRIMARY))
import ark_sim
from ark_sim import Compiler, Engine
assert Path(ark_sim.__file__).resolve().is_relative_to(CANDIDATE.resolve())
from tools import witness_canonical_roster_trio as trio
from tools import canonical_summon_witness_support as support
sys.path.remove(str(CANDIDATE)); sys.path.insert(0, str(CANDIDATE))


def chen_scene(enabled=True):
    data = trio.scene([trio.actor("chen", sp=4)], enemy=None, target="chen")
    data["scenarioDraft"]["waves"] = [{"at": 119, "definition": "unit/witness_enemy", "position": {"row": 4, "col": 5}, "instanceAlias": "enemy"}]
    if enabled:
        unit = next(e for e in data["entities"] if e["id"] == "unit/char_010_chen")
        unit["components"]["resources"]["sp"]["recovery_freeze_abilities"] = ["ability/campaign_chen_s1"]
    return data


def kalts_scene(filtered=True, selected=False):
    data = support.scene([support.actor("char_003_kalts", "host", sp=15 if selected else 0),
        support.actor("char_003_kalts", "foreign_owner", row=1, col=1, sp=0)])
    data["scenarioDraft"]["initialEntities"].append({"definition": "unit/kalts_mon3tr_model", "instanceAlias": "foreign_mon",
        "position": {"row": 4, "col": 5}, "components": {"ownership": {"owner": "foreign_owner"}, "resources": {"hp": {"initial": 3000}}}})
    unit = next(e for e in data["entities"] if e["id"] == "unit/char_003_kalts")
    if filtered: unit["components"]["resources"]["sp"]["recovery"]["interrupt_abilities"] = ["ability/kalts_host_s3"]
    return data


def probe():
    result = {}
    for configured in (False, True):
        s = Engine.create(Compiler().compile(chen_scene(configured)), seed=11); s.advance(122)
        expected = 0 if configured else 1
        assert s.ctx.resources.current("chen", "sp") == expected
        result["chen_precise_freeze" if configured else "chen_legacy_gap"] = {"SP_t122": expected,
            "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint}
    for filtered in (False, True):
        s = Engine.create(Compiler().compile(kalts_scene(filtered)), seed=0); s.advance(40)
        packets = [e for e in s.session.events if e["type"] == "healing.accepted" and e["payload"]["source"] == s.session.world.resolve("host")]
        assert bool(packets) == filtered
        result["kalts_filtered_gate" if filtered else "kalts_legacy_gap"] = {"heal_packets": len(packets),
            "foreign_mon_HP": s.ctx.resources.current("foreign_mon", "hp"), "program_fingerprint": s.program.fingerprint,
            "runtime_fingerprint": s.runtime_fingerprint}
    sources = {}
    for name in ("skills.chen.json", "skills.kalts.json"):
        path = PRIMARY/"packages/campaign"/name; sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    result["source_SHA"] = sources
    result["canonical_package_SHA"] = hashlib.sha256(trio.PACKAGE.read_bytes()).hexdigest()
    result["client_body_verified"] = False
    return result


if __name__ == "__main__":
    from ark_sim.adapters.api import implementation_digest
    output = PRIMARY/"docs/campaign/candidates/M10_CANONICAL_PROBES.json"
    result = {"schema": "ark-sim/m10-canonical-probes/v1", "candidate_module_path": ark_sim.__file__,
        "implementation_digest": implementation_digest(), "probes": probe(), "formal_approved": False}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print("M10 canonical actual probes passed", output)
