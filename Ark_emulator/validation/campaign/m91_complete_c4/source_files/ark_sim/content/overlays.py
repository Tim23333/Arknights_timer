"""Explicit recursive overlays. Arrays replace instead of implicitly append."""
from copy import deepcopy
from collections.abc import Mapping


def merge(base, patch):
    result = deepcopy(dict(base))
    for key, value in patch.items():
        if isinstance(value, Mapping) and value == {"$delete": True}:
            result.pop(key, None)
        elif isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
