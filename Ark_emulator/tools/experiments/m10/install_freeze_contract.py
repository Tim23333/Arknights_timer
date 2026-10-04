"""M10 isolated contract installer; never writes any other runtime."""
from pathlib import Path
import json
from copy import deepcopy

PRIMARY = Path(__file__).resolve().parents[3]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m10_cast_freeze_candidate"
path = CANDIDATE/"ark_sim/rules/contracts.json"
catalog = json.loads(path.read_bytes())
template = deepcopy(next(c for c in catalog["contracts"] if c["id"] == "resource.recovery"))
template.update(id="resource.recovery_freeze", outputType="boolean", outputSchema={"type": "boolean"},
    inputs=[{"name": name, "type": kind, "required": True} for name, kind in (
        ("owner", "entity_snapshot"), ("resource", "string"), ("casts", "value_map"), ("time", "logic_time"),
        ("configured_frozen", "boolean"), ("parameters", "value_map"))],
    description="Explicit final Boolean override; metadata authority may解除 legacy/ability freeze. No implicit/default binding.")
catalog["contracts"] = [c for c in catalog["contracts"] if c["id"] != template["id"]]+[template]
path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
print("M10 explicit Boolean freeze contract installed")
