"""Portable writable data roots, separate from bundled read-only resources."""
from pathlib import Path
import sys


def data_root() -> Path:
    """Resolve program-relative data storage regardless of the launch directory.

    Source runs use the repository root. Frozen releases use the EXE directory,
    never PyInstaller's temporary resource extraction directory. No drive letter
    or machine-specific user directory is built into the release defaults.
    """
    root = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parents[2])
    return root / 'data'
