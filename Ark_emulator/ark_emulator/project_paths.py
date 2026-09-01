"""Repository-relative paths used by the emulator data loaders.

The emulator is developed and run from the source repository, while its
generated data lives in sibling top-level directories such as ``ark_parser``
and ``unpack_work``.  Keeping path derivation here prevents generated files or
developer drive letters from becoming runtime configuration.
"""

from pathlib import Path
from typing import Union


PACKAGE_DIR = Path(__file__).resolve().parent
ARK_EMULATOR_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = ARK_EMULATOR_DIR.parent

ENEMY_DATA_DIR = PROJECT_ROOT / "ark_parser" / "enemy" / "data"
CHARACTER_DATA_DIR = PROJECT_ROOT / "ark_parser" / "character" / "data"
EXTRACT_LEVEL_DATA = PROJECT_ROOT / "ark_parser" / "enemy" / "extract_level_data.py"
LEVEL_ASSETS_INDEX = PACKAGE_DIR / "data_level_assets_index.json"
SPINE_ASSET_LIB = PROJECT_ROOT / "unpack_work" / "spine_asset_lib"


def resolve_project_path(path: Union[str, Path]) -> Path:
    """Resolve an index/config path relative to the repository root.

    Absolute paths remain supported for callers that deliberately provide an
    external data location.  Repository-generated indexes should store
    portable forward-slash paths relative to ``PROJECT_ROOT``.
    """

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


__all__ = [
    "ARK_EMULATOR_DIR",
    "CHARACTER_DATA_DIR",
    "ENEMY_DATA_DIR",
    "EXTRACT_LEVEL_DATA",
    "LEVEL_ASSETS_INDEX",
    "PACKAGE_DIR",
    "PROJECT_ROOT",
    "SPINE_ASSET_LIB",
    "resolve_project_path",
]
