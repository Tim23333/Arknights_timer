"""Find the first observable difference, with explicit JSON-pointer tolerances.

By default every field is compared exactly. Numeric settings apply only to the
exact pointer named by the caller; they never propagate to neighbouring fields.
"""
import math
from collections.abc import Mapping
from decimal import Decimal, localcontext, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP

from ..contracts.models import thaw


_ROUNDINGS = {"half_even": ROUND_HALF_EVEN, "half_up": ROUND_HALF_UP,
              "floor": ROUND_FLOOR, "ceil": ROUND_CEILING, "trunc": ROUND_DOWN}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite(value):
    return not isinstance(value, float) or math.isfinite(value)


def _settings(tolerances):
    if tolerances is None:
        return {}
    if not isinstance(tolerances, Mapping):
        raise ValueError("tolerances must map exact JSON pointers to numeric settings")
    result = {}
    for path, definition in tolerances.items():
        if not isinstance(path, str) or (path and not path.startswith("/")):
            raise ValueError("Tolerance paths must be JSON pointers, using '' for the root")
        if _number(definition):
            definition = {"abs": definition}
        if not isinstance(definition, Mapping):
            raise ValueError(f"Numeric settings at {path!r} must be a number or object")
        if set(definition) - {"abs", "rel", "quantum", "rounding"}:
            raise ValueError(f"Unknown numeric comparison settings at {path!r}")
        settings = {"abs": definition.get("abs", 0), "rel": definition.get("rel", 0)}
        for key, value in settings.items():
            if not _number(value) or not _finite(value) or value < 0:
                raise ValueError(f"{key} tolerance at {path!r} must be finite and nonnegative")
        if "quantum" in definition:
            quantum = definition["quantum"]
            if not _number(quantum) or not _finite(quantum) or quantum <= 0:
                raise ValueError(f"quantum at {path!r} must be finite and positive")
            settings["quantum"] = quantum
        rounding = definition.get("rounding", "half_even")
        if not isinstance(rounding, str) or rounding not in _ROUNDINGS:
            raise ValueError(f"Unknown comparison rounding: {rounding}")
        if "rounding" in definition and "quantum" not in definition:
            raise ValueError(f"rounding at {path!r} requires quantum")
        settings["rounding"] = rounding
        result[path] = settings
    return result


def _quantize(value, settings):
    if "quantum" not in settings:
        return value
    quantum = Decimal(str(settings["quantum"]))
    value = Decimal(str(value))
    with localcontext() as context:
        context.prec = max(28, len(value.as_tuple().digits), value.adjusted() - quantum.adjusted() + 2)
        return (value / quantum).to_integral_value(
            rounding=_ROUNDINGS[settings["rounding"]]) * quantum


def _pointer(parent, key):
    part = str(key).replace("~", "~0").replace("/", "~1")
    return parent + "/" + part


def first_difference(expected, actual, tolerances=None):
    """Return ``None`` or ``{path, expected, actual, reason}``.

    Object keys use deterministic lexical order; array items use index order.
    A numeric setting is either an absolute tolerance or an object containing
    ``abs``, ``rel``, ``quantum`` and ``rounding``. Quantization occurs before
    tolerances are checked. Boolean values remain a distinct type throughout.
    """
    settings = _settings(tolerances)

    def difference(path, left, right, reason):
        return {"path": path, "expected": thaw(left), "actual": thaw(right), "reason": reason}

    def walk(left, right, path):
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            if any(not isinstance(key, str) for key in set(left) | set(right)):
                raise ValueError("Snapshot objects must have string keys")
            for key in sorted(set(left) | set(right)):
                child = _pointer(path, key)
                if key not in left:
                    return difference(child, None, right[key], "missing_expected")
                if key not in right:
                    return difference(child, left[key], None, "missing_actual")
                found = walk(left[key], right[key], child)
                if found is not None:
                    return found
            return None
        if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
            for index in range(max(len(left), len(right))):
                child = _pointer(path, index)
                if index >= len(left):
                    return difference(child, None, right[index], "missing_expected")
                if index >= len(right):
                    return difference(child, left[index], None, "missing_actual")
                found = walk(left[index], right[index], child)
                if found is not None:
                    return found
            return None
        if _number(left) and _number(right):
            if not _finite(left) or not _finite(right):
                raise ValueError(f"Snapshot contains a non-finite number at {path!r}")
            numeric = settings.get(path, {"abs": 0, "rel": 0})
            left_value, right_value = _quantize(left, numeric), _quantize(right, numeric)
            if left_value == right_value:
                return None
            left_value, right_value = Decimal(str(left_value)), Decimal(str(right_value))
            with localcontext() as context:
                context.prec = max(28, len(left_value.as_tuple().digits), len(right_value.as_tuple().digits)) + 5
                delta = abs(left_value - right_value)
                absolute = Decimal(str(numeric["abs"]))
                relative = Decimal(str(numeric["rel"]))
                if delta <= max(absolute, relative * max(abs(left_value), abs(right_value))):
                    return None
            return difference(path, left, right, "number")
        if type(left) is not type(right):
            return difference(path, left, right, "type")
        if left != right:
            return difference(path, left, right, "value")
        return None

    return walk(expected, actual, "")
