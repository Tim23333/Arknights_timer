"""One replaceable game-data bundle shared by readers, parsers and packaging.

The external bundle beside a frozen executable takes precedence. A missing
bundle supports the old checkout layout; an incomplete selected bundle never
silently mixes data from another version. Restart readers after editing offsets.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_NAME = "ARKNIGHTS_GAME_DATA_DIR"


def bundle_root() -> Path | None:
    explicit = os.environ.get(ENV_NAME)
    if explicit:
        root = Path(explicit).resolve()
        if not (root / "manifest.json").is_file():
            raise ValueError(f"{ENV_NAME}: missing manifest.json in {root}")
        return root
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "game_data")
        candidates.append(Path(getattr(sys, "_MEIPASS", REPO_ROOT)) / "game_data")
    candidates.append(REPO_ROOT / "game_data")
    return next((p for p in candidates if (p / "manifest.json").is_file()), None)


def manifest(root: Path | None = None) -> dict:
    root = root or bundle_root()
    if root is None:
        return {}
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(f"Unsupported game_data manifest: {root}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def legacy_table(prefix: str, directory: Path | str) -> Path | None:
    directory = Path(directory)
    stable = directory / f"{prefix}.bin"
    if stable.is_file():
        return stable
    files = sorted(p for p in directory.glob(f"{prefix}*.bin")
                   if re.fullmatch(re.escape(prefix) + r"[a-fA-F0-9]+\.bin", p.name))
    if len(files) > 1:
        raise ValueError(f"Multiple versions of {prefix} in {directory}; rebuild game_data")
    return files[0] if files else None


def table_path(prefix: str, legacy_dir: Path | str | None = None) -> Path | None:
    root = bundle_root()
    if root is not None:
        path = root / "tables" / f"{prefix}.bin"
        if not path.is_file():
            raise FileNotFoundError(f"Missing {prefix} in selected game_data: {root}")
        return path
    return legacy_table(prefix, legacy_dir or REPO_ROOT / "data" / "tables")


def catalog_path(name: str) -> Path | None:
    root = bundle_root()
    if root is None:
        return None
    path = root / "catalogs" / f"{name}.json"
    return path if path.is_file() else None


def merge_overrides(base, patch):
    """ID/field dictionaries merge recursively; lists and scalar values replace."""
    if isinstance(base, dict) and isinstance(patch, dict):
        result = copy.deepcopy(base)
        for key, value in patch.items():
            result[key] = merge_overrides(result.get(key), value)
        return result
    return copy.deepcopy(patch)


def load_catalog(name: str) -> dict | None:
    path = catalog_path(name)
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    override = path.parent.parent / "overrides" / f"{name}.json"
    if override.is_file():
        data = merge_overrides(data, json.loads(override.read_text(encoding="utf-8")))
    return data


def offset_path(platform: str) -> Path | None:
    if platform not in {"android_arm64", "pc_x64"}:
        raise ValueError(f"Unsupported platform: {platform}")
    root = bundle_root()
    if root is None:
        return None
    path = root / "offsets" / f"{platform}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {platform} offsets in {root}")
    return path


def load_offsets(platform: str) -> dict | None:
    path = offset_path(platform)
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("platform") != platform:
        raise ValueError(f"Offset platform mismatch: expected {platform}, got {data.get('platform')}")
    override = path.parent.parent / "overrides" / f"{platform}.json"
    if override.is_file():
        data = merge_overrides(data, json.loads(override.read_text(encoding="utf-8")))
    if data.get("platform") != platform:
        raise ValueError("Offset overrides cannot change platform")
    return data


def runtime_offsets(group: str) -> dict:
    payload = load_offsets('android_arm64')
    return (payload or {}).get('runtime', {}).get(group, {})


def fingerprint(*paths: Path | str | None) -> tuple:
    root = bundle_root()
    candidates = [Path(p) for p in paths if p]
    if root:
        candidates.append(root / "manifest.json")
        candidates.append(root / 'offsets' / 'android_arm64.json')
        candidates.extend(sorted((root / "overrides").glob("*.json")))
    return tuple((str(p.resolve()), p.stat().st_mtime_ns, p.stat().st_size)
                 for p in candidates if p.is_file())


def validate_bundle(root: Path) -> list[str]:
    """Validate generated artifacts; hand edits belong in overrides/."""
    data = manifest(root)
    errors = []
    for relative, expected in data.get("files", {}).items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append(f"Path outside bundle: {relative}")
        elif not path.is_file():
            errors.append(f"Missing file: {relative}")
        elif sha256_file(path) != expected["sha256"]:
            errors.append(f"Hash mismatch: {relative}")
    for platform in ("android_arm64", "pc_x64"):
        path = root / "offsets" / f"{platform}.json"
        if path.is_file():
            if json.loads(path.read_text(encoding="utf-8")).get("platform") != platform:
                errors.append(f"Platform mismatch: {platform}")
    return errors
