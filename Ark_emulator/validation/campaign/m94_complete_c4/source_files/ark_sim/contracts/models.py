"""Immutable compilation and calculation records shared across modules."""
import hashlib
import json
from dataclasses import dataclass, field
from collections.abc import Mapping
from types import MappingProxyType


class FrozenMapping(Mapping):
    """A recursively frozen mapping that can safely be reused by ``freeze``."""
    __slots__ = ("_data",)

    def __init__(self, value):
        object.__setattr__(self, "_data", MappingProxyType({k: freeze(v) for k, v in value.items()}))

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __setattr__(self, key, value):
        raise TypeError("frozen mappings cannot be modified")

    def __deepcopy__(self, memo):
        return self


class FrozenTuple(tuple):
    """An immutable sequence with recursively frozen children."""
    def __new__(cls, value):
        return tuple.__new__(cls, (freeze(v) for v in value))

    def __deepcopy__(self, memo):
        return self


def freeze(value):
    value_type = type(value)
    if value_type in (str, int, float, bool, type(None), FrozenMapping, FrozenTuple):
        return value
    if value_type is dict:
        return FrozenMapping(value)
    if value_type in (list, tuple):
        return FrozenTuple(value)
    if isinstance(value, Mapping):
        return FrozenMapping(value)
    if isinstance(value, (list, tuple)):
        return FrozenTuple(value)
    return value


def thaw(value):
    value_type = type(value)
    if value_type in (str, int, float, bool, type(None)):
        return value
    if value_type is dict:
        return {k: thaw(v) for k, v in value.items()}
    if value_type in (list, tuple, FrozenTuple):
        return [thaw(v) for v in value]
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw(v) for v in value]
    return value


def digest(value):
    raw = json.dumps(thaw(value), ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SimulationProgram:
    scenario: Mapping
    definitions: Mapping
    ruleset: Mapping
    rules: Mapping
    dependency_ids: tuple
    fingerprint: str
    metadata: Mapping = field(default_factory=dict)

    def __post_init__(self):
        for key in ("scenario", "definitions", "ruleset", "rules", "metadata"):
            object.__setattr__(self, key, freeze(getattr(self, key)))
        object.__setattr__(self, "dependency_ids", tuple(self.dependency_ids))

    def __deepcopy__(self, memo):
        return self

    def to_dict(self):
        return {"scenario": thaw(self.scenario), "definitions": thaw(self.definitions),
                "ruleset": thaw(self.ruleset), "rules": thaw(self.rules),
                "dependency_ids": list(self.dependency_ids), "fingerprint": self.fingerprint,
                "metadata": thaw(self.metadata)}


@dataclass(frozen=True)
class EvaluationResult:
    value: object
    trace: Mapping
    rule_id: str

    def __post_init__(self):
        object.__setattr__(self, "value", freeze(self.value))
        object.__setattr__(self, "trace", freeze(self.trace))


@dataclass(frozen=True)
class Intent:
    op: str
    entity_id: object = None
    path: tuple = ()
    value: object = None
    data: Mapping = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "path", tuple(self.path))
        object.__setattr__(self, "value", freeze(self.value))
        object.__setattr__(self, "data", freeze(self.data))
