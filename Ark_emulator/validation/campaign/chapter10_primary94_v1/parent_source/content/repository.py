"""Deterministic package loading and ID indexing."""
import json
from pathlib import Path
from copy import deepcopy
from collections.abc import Mapping
from ..contracts.models import thaw


COLLECTIONS = {"projectiles": "projectile", "entities": "entity", "abilities": "ability", "buffs": "buff", "controls": "control",
               "selectors": "selector", "behaviors": "behavior", "policies": "policy",
               "rules": "calculation_rule", "rulesets": "ruleset", "presets": "preset",
               "scenarios": "scenario", "definitions": None}
PACKAGE_FIELDS = set(COLLECTIONS) | {"schemaVersion", "status", "manifest",
                                    "scenarioDraft", "formulaPreviewCases", "metadata"}


class ContentError(ValueError):
    """A content error with the ID and field included in its message."""


def load_sources(sources):
    """Yield copied package dictionaries from paths, directories, or mappings."""
    if sources is None:
        return []
    if isinstance(sources, (str, Path, Mapping)):
        sources = [sources]
    result = []
    for source in sources:
        if isinstance(source, Mapping):
            value = thaw(source)
            if "kind" in value:
                value = {"definitions": [value]}
            result.append(("<mapping>", value))
            continue
        path = Path(source)
        if not path.exists():
            raise ContentError(f"Package path does not exist: {path}")
        paths = sorted(path.rglob("*.json")) if path.is_dir() else [path]
        for file in paths:
            try:
                value = json.loads(file.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                raise ContentError(f"Invalid package JSON at {file}: {exc}") from exc
            if not isinstance(value, dict):
                raise ContentError(f"Package root must be an object: {file}")
            if "kind" in value:
                value = {"definitions": [value]}
            result.append((str(file), value))
    return result


class Repository:
    def __init__(self, sources):
        self.raw = {}
        self.origins = {}
        self.manifests = []
        self.drafts = []
        for source_index, (origin, package) in enumerate(sources):
            origin = f"{origin}#{source_index}"
            unknown = set(package) - PACKAGE_FIELDS
            if unknown:
                raise ContentError(f"{origin}: unknown package fields {sorted(unknown)}")
            if package.get("schemaVersion", 2) != 2:
                raise ContentError(f"{origin}: unsupported schemaVersion")
            manifest = package.get("manifest", {})
            if not isinstance(manifest, dict):
                raise ContentError(f"{origin}.manifest must be an object")
            if set(manifest) - {"id", "version", "requires", "externals", "description", "metadata"}:
                raise ContentError(f"{origin}.manifest: unknown fields {sorted(set(manifest) - {'id', 'version', 'requires', 'externals', 'description', 'metadata'})}")
            for field in ("requires", "externals"):
                if not isinstance(manifest.get(field, []), list) or not all(isinstance(x, str) for x in manifest.get(field, [])):
                    raise ContentError(f"{origin}.manifest.{field}: expected an ID list")
            self.manifests.append((origin, deepcopy(manifest)))
            for collection, kind in COLLECTIONS.items():
                values = package.get(collection, [])
                if isinstance(values, dict):
                    values = [dict(v, id=k) for k, v in values.items()]
                if not isinstance(values, list):
                    raise ContentError(f"{origin}.{collection} must be a list or ID map")
                for definition in values:
                    if not isinstance(definition, dict):
                        raise ContentError(f"{origin}.{collection}: definition must be an object")
                    definition = deepcopy(definition)
                    if kind and "kind" not in definition:
                        definition["kind"] = kind
                    self.add(definition, origin)
            if "scenarioDraft" in package:
                draft = deepcopy(package["scenarioDraft"])
                draft.setdefault("kind", "scenario")
                self.add(draft, origin)
                self.drafts.append(draft["id"])

    def add(self, definition, origin="<scenario>"):
        identifier = definition.get("id")
        if not isinstance(identifier, str) or "/" not in identifier or any(c.isspace() for c in identifier):
            raise ContentError(f"{origin}: definition ID must be a namespaced string, got {identifier!r}")
        if identifier in self.raw:
            raise ContentError(f"Conflicting definition {identifier}: {self.origins[identifier]} and {origin}; use explicit extends or overlays")
        self.raw[identifier] = deepcopy(definition)
        self.origins[identifier] = origin
