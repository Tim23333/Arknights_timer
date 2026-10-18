"""Encode an already sanitized, owned public snapshot without another walk.

Not a general replacement for json.dumps: callers must have removed non-finite
floats and runtime objects at the publication boundary. Never use for raw data,
strict SSE validation, persistence or arbitrary command replies.
"""
import json

try:
    import orjson as _orjson
except ImportError:
    _orjson = None


def encode_sanitized(value):
    """Return JSON text, retaining stdlib support for large ints/surrogates.

    Bytes are decoded deliberately: changing WS text frames to binary would
    break the existing protocol. Finite float spelling can differ, not values.
    """
    if _orjson is not None:
        try:
            return _orjson.dumps(value).decode('utf-8')
        except (TypeError, ValueError):
            pass
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
