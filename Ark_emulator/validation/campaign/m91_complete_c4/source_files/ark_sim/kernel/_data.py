"""Small data boundary helpers; the kernel stores JSON values only."""
import json
from collections.abc import Mapping
from ark_sim.contracts.models import freeze


def _plain(value):
    value_type = type(value)
    if value_type in (str, bool, int, float, type(None)):
        return value
    if value_type is dict:
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _plain(item) for key, item in value.items()}
    if value_type in (list, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError(f"Kernel state must be JSON data, got {type(value).__name__}")


def clone(value):
    """Validate finite JSON data and detach all caller-owned containers."""
    return json.loads(json.dumps(_plain(value), ensure_ascii=False, allow_nan=False))


def readonly(value):
    # This trusted deep-frozen tree can be reused by rule evaluation without
    # freezing the same read view on every input/context boundary again.
    return freeze(value)


def integer(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return value


def name(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value
