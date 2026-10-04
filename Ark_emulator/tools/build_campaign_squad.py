"""Join real roster stats with selected-skill models, preserving all gaps.

Fixture stats/targets/commands never enter the squad module. This is executable
integration, not an approval of native attack clocks, talents or full operators.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ark_sim.content.dependencies import references
from tools.build_campaign_units import build as base_units

OUTPUT = ROOT / "packages/campaign/squad.integrated.json"
# Translation bindings are content authoring data; the kernel sees no IDs.
BINDINGS = {
    "char_151_myrtle": ("myrtle", "unit/campaign_myrtle_fixture", "ability/campaign_myrtle_s2", False),
    "char_222_bpipe": ("bpipe", "unit/char_222_bpipe_fixture", "ability/campaign_bpipe_s3", True),
    "char_010_chen": ("chen", "unit/char_010_chen_fixture", "ability/campaign_chen_s1", True),
    "char_107_liskam": ("liskam", "unit/liskam_support_fixture", "ability/liskam_s1", False),
    "char_202_demkni": ("demkni", "unit/demkni_aura_fixture", "ability/demkni_s3", False),
    "char_128_plosis": ("plosis", "unit/plosis_support_fixture", "ability/plosis_s2_first_packet", False),
    "char_103_angel": ("angel", "unit/char_103_angel_fixture", "ability/campaign_angel_s3", True),
    "char_180_amgoat": ("amgoat", "unit/char_180_amgoat_fixture", "ability/campaign_amgoat_s3", True),
    "char_003_kalts": ("kalts", "unit/kalts_host_model", "ability/kalts_host_s3", False),
    "char_358_lisa": ("lisa", "unit/lisa_aura_fixture", "ability/lisa_s3", False),
    "char_400_weedy": ("weedy", "unit/campaign_weedy_selected", "ability/campaign_weedy_s3", False),
    "char_179_cgbird": ("cgbird", "unit/cgbird_aura_fixture", "ability/cgbird_s3", False),
}
SECTIONS = ("entities", "abilities", "buffs", "selectors", "rules", "behaviors", "policies")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def definition_map(package):
    return {row["id"]: deepcopy(row) for section in SECTIONS for row in package.get(section, [])}


def gather(roots, available):
    found, pending = {}, list(roots)
    while pending:
        key = pending.pop()
        if key in found or key not in available:
            continue  # Preset contracts remain references resolved by Compiler.
        row = available[key]
        found[key] = deepcopy(row)
        pending.extend(references(row))
    return found


def build():
    base = base_units()
    available_base = definition_map(base)
    talents, talent_defs, overrides = [], {}, {}
    for name in ("attack", "support"):
        path = ROOT / f"packages/campaign/talents.{name}.json"
        package = json.loads(path.read_text(encoding="utf-8"))
        talents.append((name, path, package["manifest"]["metadata"]))
        for key, row in definition_map(package).items():
            if key in talent_defs and talent_defs[key] != row:
                raise ValueError(f"Conflicting talent definition: {key}")
            talent_defs[key] = row
        for field in ("skill_definition_overrides", "token_definition_overrides"):
            values = package["manifest"]["metadata"].get(field, [])
            for row in values.values() if isinstance(values, dict) else values:
                if row["id"] in overrides and overrides[row["id"]] != row:
                    raise ValueError(f"Conflicting talent override: {row['id']}")
                overrides[row["id"]] = deepcopy(row)
    definitions, records, sources = {}, [], {}
    normalized = {row["character_id"]: row for row in json.loads(
        (ROOT/"packages/campaign/operators.normalized.json").read_text(encoding="utf8"))["operators"]}
    preset = json.loads((ROOT/"ark_sim/content/presets/ark_standard.json").read_text(encoding="utf8"))
    default_layers = next(r["attribute_layers"] for r in preset["rulesets"] if r["id"] == "ruleset/ark_standard")
    def insert(rows):
        for key, row in rows.items():
            if key in definitions and definitions[key] != row:
                raise ValueError(f"Conflicting integrated content definition: {key}")
            definitions[key] = row
    for entity in base["entities"]:
        native = entity["metadata"]["native_id"]
        name, fixture_id, skill_id, replace_normal = BINDINGS[native]
        path = ROOT / f"packages/campaign/skills.{name}.json"
        package = json.loads(path.read_text(encoding="utf-8"))
        source_defs = definition_map(package)
        fixture = source_defs[fixture_id]
        actor = deepcopy(entity)
        components = actor["components"]
        source = fixture["components"]
        # Existing base values are authoritative actual fixed growth/trust.
        for key, value in source.get("attributes", {}).get("base", {}).items():
            components["attributes"]["base"].setdefault(key, value)
        for key, spec in source.get("resources", {}).items():
            if key != "hp":
                components["resources"][key] = deepcopy(spec)
        components["abilities"] = [a for a in source.get("abilities", []) if "fixture_attack" not in a]
        if skill_id not in components["abilities"]:
            raise ValueError("Selected skill is not owned by source actor")
        if not replace_normal:
            components["abilities"].append(f"ability/{native}/normal_attack")
        for key in ("buffs", "buff_container", "ownership"):
            if key in source:
                components[key] = deepcopy(source[key])
        actor["rules"] = deepcopy(fixture.get("rules", {}))
        actor["metadata"].update(selected_skill_ability=skill_id, integrated_selected_skill=True,
            all_talents_complete=False, native_attack_clock_verified=False)
        actor["tags"].extend(["campaign_roster", "profession:" + next(r["raw_character"]["profession"]
            for r in json.loads((ROOT/"packages/campaign/operators.normalized.json").read_text(encoding="utf-8"))["operators"]
            if r["character_id"] == native)])
        talent_sources = []
        for talent_name, talent_path, talent_meta in talents:
            patch = talent_meta.get("unit_patches", {}).get(actor["id"])
            if patch is None:
                continue
            talent_sources.append(talent_name)
            attribute_patch = patch.get("attributes", {})
            for key, value in attribute_patch.get("base", attribute_patch).items():
                components["attributes"]["base"].setdefault(key, deepcopy(value))
            if patch.get("attribute_layers_append"):
                layers = components["attributes"].get("layers", default_layers)
                components["attributes"]["layers"] = list(dict.fromkeys([*layers, *patch["attribute_layers_append"]]))
            for key, value in patch.get("resources", {}).items():
                if key in components["resources"]:
                    if components["resources"][key] != value:
                        raise ValueError(f"Talent patch attempts to replace an existing resource: {actor['id']}/{key}")
                else:
                    components["resources"][key] = deepcopy(value)
            recovery_patch = patch.get("time_resource_patch")
            if recovery_patch:
                components["resources"][recovery_patch["resource"]]["recovery_rule"] = recovery_patch["recovery_rule"]
            for field, values in (("abilities", patch.get("talent_abilities", [])),):
                components[field] = list(dict.fromkeys([*components.get(field, []), *values]))
            actor["tags"] = list(dict.fromkeys([*actor["tags"], *patch.get("tags", [])]))
            initial = components.setdefault("buffs", {}).setdefault("initial", [])
            components["buffs"]["initial"] = list(dict.fromkeys([*initial, *patch.get("buffs", {}).get("initial", [])]))
            for field in ("deck", "deployable"):
                if patch.get(field):
                    merge_patch(components.setdefault(field, {}), patch[field])
            actor["rules"].update(deepcopy(patch.get("rules", {})))
        actor["metadata"]["talent_model_sources"] = talent_sources
        actor["metadata"]["talent_models_integrated"] = bool(talent_sources)
        if normalized[native]["selected_skill"]["level"]["spData"]["spType"] == "INCREASE_WITH_TIME":
            components["attributes"]["base"].setdefault("sp_recovery_rate", normalized[native]["stats"]["model_stats"]["spRecoveryPerSec"])
            layers = components["attributes"].get("layers", default_layers)
            components["attributes"]["layers"] = list(dict.fromkeys([*layers, "sp_recovery"]))
            actor["rules"]["attributes.effective"] = "rule/support_temporal"
            components["resources"]["sp"]["recovery_rule"] = "rule/support_time_sp"
            actor["tags"] = list(dict.fromkeys([*actor["tags"], "time_sp"]))
        local = {**available_base, **source_defs, **talent_defs, **overrides}
        diagnostic_moves = {"ability/token_leave", "ability/token_enter", "ability/aura_leave", "ability/aura_enter"}
        for row in local.values():
            if row.get("kind") == "entity":
                row["components"]["abilities"] = [a for a in row["components"].get("abilities", []) if a not in diagnostic_moves]
        local[actor["id"]] = actor
        roots = [actor["id"]]
        picked = gather(roots, local)
        for definition in picked.values():
            if definition.get("kind") == "ability":
                activation = definition.get("activation", {})
                initial = activation.get("on_start", [])
                if any(e.get("op") == "spawn" and e.get("owner") == "source" for e in initial):
                    promoted = []
                    for effect in initial:
                        if effect.get("op") == "modify_resource" and effect.get("target") == "battle" and effect.get("resource") == "dp" and effect.get("delta", 0) < 0:
                            if set(effect)-{"op", "target", "resource", "delta"}:
                                raise ValueError("Conditional owned deployment payment needs explicit author conversion")
                            activation.setdefault("costs", []).append({"owner": "battle", "resource": "dp", "amount": -effect["delta"]})
                            promoted.append(deepcopy(effect))
                        else:
                            continue
                    if promoted:
                        activation["on_start"] = [e for e in initial if e not in promoted]
                        definition.setdefault("metadata", {})["integrated_legacy_payment_promotions"] = promoted
                for effect in activation.get("on_start", []):
                    if effect.get("op") == "spawn" and effect.get("owner") == "source":
                        effect.pop("position", None)
                        effect.pop("facing", None)
                        effect.setdefault("parameters", {})["position_from_payload"] = True
                        paid = sum(c["amount"] for c in definition.get("activation", {}).get("costs", [])
                                   if c.get("owner") == "battle" and c.get("resource") == "dp")
                        effect["parameters"]["deployment_payment_amount"] = paid
        # No synthetic target/unit fixture is a valid squad dependency.
        if any(d.get("kind") == "entity" and key != actor["id"] and "fixture" in key for key, d in picked.items()):
            raise ValueError("Fixture entity escaped the selected-skill closure")
        insert(picked)
        meta = package["manifest"]["metadata"]
        gaps = list(meta.get("pending_mechanics", meta.get("source_gaps", meta.get("timing_limits", []))))
        gaps += ["full_native_operator_validation"]
        for talent_name, talent_path, talent_meta in talents:
            if talent_name in talent_sources:
                gaps.extend(talent_meta.get("pending", []))
                gaps.extend(talent_meta.get("pending_mechanics", []))
        records.append({"native_id": native, "selected_skill_native_id": entity["metadata"]["selected_skill_native_id"],
            "selected_skill_ability": skill_id, "source_package": path.relative_to(ROOT).as_posix(),
            "dependencies": sorted(picked), "talent_model_sources": talent_sources,
            "pending": gaps, "complete_operator": False})
        sources[name] = sha(path)
    output = {"schemaVersion": 2, "status": "integrated_partial_roster", "manifest": {
        "id": "package/campaign/integrated_roster", "version": "0.1.0", "requires": ["preset/ark_standard"],
        "metadata": {"official_roster_count": 12, "complete_operator_count": 0, "formal_mainline_approved": False,
            "source_packages": sources, "base_model_sha256": sha(ROOT/"packages/campaign/units.base.json"),
            "talent_source_packages": {name: sha(path) for name, path, meta in talents},
            "integration": records}}}
    section_for_kind = {"entity": "entities", "ability": "abilities", "buff": "buffs", "selector": "selectors",
        "rule": "rules", "calculation_rule": "rules", "behavior": "behaviors", "policy": "policies"}
    for key in sorted(definitions):
        row = definitions[key]
        output.setdefault(section_for_kind[row["kind"]], []).append(row)
    return output


def merge_patch(target, patch):
    """Merge explicitly authored talent extensions, appending list members."""
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_patch(target[key], value)
        elif isinstance(value, list) and isinstance(target.get(key), list):
            for item in value:
                if item not in target[key]:
                    target[key].append(deepcopy(item))
        else:
            target[key] = deepcopy(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2)+"\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Integrated squad source/output mismatch")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
    print("Twelve actual roster units joined with selected-skill models; remaining dependencies are explicit.")
