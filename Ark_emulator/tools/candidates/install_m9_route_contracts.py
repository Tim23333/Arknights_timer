"""Install explicit-route contracts in the isolated candidate only."""
from copy import deepcopy
import json
from pathlib import Path

PRIMARY = Path(__file__).resolve().parents[2]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m9_candidate"


def install():
    assert CANDIDATE.resolve() != PRIMARY.resolve()
    catalog_path = CANDIDATE/"ark_sim/rules/contracts.json"
    preset_path = CANDIDATE/"ark_sim/content/presets/ark_standard.json"
    catalog = json.loads(catalog_path.read_bytes())
    original = next(c for c in catalog["contracts"] if c["id"] == "movement.wait_deadline")
    for identifier, fields, output in (
        ("movement.transition", [("kind", "integer"), ("position", "position"), ("checkpoint", "value_map"), ("parameters", "value_map")], "value_map"),
        ("movement.checkpoint_position", [("position", "position"), ("offset", "value_map"), ("parameters", "value_map")], "position")):
        item = deepcopy(original)
        item.update(id=identifier, inputs=[{"name": name, "type": kind, "required": True} for name, kind in fields],
                    outputType=output, outputSchema={"type": output}, description="Explicit replaceable route model; no native-body accuracy claim.")
        catalog["contracts"] = [c for c in catalog["contracts"] if c["id"] != identifier]+[item]
    preset = json.loads(preset_path.read_bytes())
    for identifier, contract, provider in (("rule/m9_living_transition", "movement.transition", "ark.movement.living_transition"),
                                            ("rule/m9_checkpoint_cartesian", "movement.checkpoint_position", "ark.movement.checkpoint_cartesian")):
        item = {"id": identifier, "kind": "calculation_rule", "contract": contract,
            "implementation": {"type": "provider", "provider": provider},
            "metadata": {"scope": "explicit_model_profile", "client_verified": False}}
        preset["rules"] = [r for r in preset["rules"] if r["id"] != identifier]+[item]
    # No implicit binding: native portal/offset data must select a declared rule.
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    preset_path.write_text(json.dumps(preset, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print("candidate contracts installed:", CANDIDATE)


if __name__ == "__main__": install()
