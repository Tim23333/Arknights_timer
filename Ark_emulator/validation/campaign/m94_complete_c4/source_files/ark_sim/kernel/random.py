"""Named streams with explicit, version-locked algorithm factories.

Factories receive a deterministic integer derived from (root seed, stream).
Each backend declares algorithm/version and implements sample, snapshot and
restore. The kernel owns stream identity, JSON validation and consumption logs.
"""
import hashlib
import inspect
import json
import math
import random as _random
import types
from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock

from ._data import clone, integer, name, readonly


DEFAULT_ALGORITHM = "python-mt19937/sha256-stream-seed-v1"
_SEED_UNSPECIFIED = object()


def _tuple_tree(value):
    return tuple(_tuple_tree(item) for item in value) if isinstance(value, list) else value


class MT19937Backend:
    algorithm = DEFAULT_ALGORITHM
    version = "1"

    def __init__(self, seed):
        self._generator = _random.Random(seed)

    def sample(self):
        return self._generator.random()

    def snapshot(self):
        return self._generator.getstate()

    def restore(self, data):
        self._generator.setstate(_tuple_tree(data))


def _code_record(code):
    constants = []
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            constants.append(_code_record(value))
        elif isinstance(value, bytes):
            constants.append({"bytes": value.hex()})
        elif value is None or isinstance(value, (str, bool, int, float)):
            constants.append(value)
        elif isinstance(value, tuple):
            constants.append([item for item in value if item is None or isinstance(item, (str, bool, int, float))])
        else:
            constants.append({"type": type(value).__name__})
    return {"bytecode": code.co_code.hex(), "constants": constants, "names": list(code.co_names),
            "freevars": list(code.co_freevars), "arguments": code.co_argcount,
            "keyword_arguments": code.co_kwonlyargcount}


def _factory_record(factory):
    try:
        source = inspect.getsource(factory)
    except (OSError, TypeError):
        source = None
    result = {"module": getattr(factory, "__module__", type(factory).__module__),
              "name": getattr(factory, "__qualname__", type(factory).__qualname__), "source": source}
    target = factory if inspect.isfunction(factory) else getattr(factory, "__call__", None)
    if target is not None and hasattr(target, "__code__"):
        result["code"] = _code_record(target.__code__)
        result["defaults"] = clone(getattr(target, "__defaults__", None))
        result["keyword_defaults"] = clone(getattr(target, "__kwdefaults__", None))
        closure = getattr(target, "__closure__", None)
        if closure:
            captured = []
            for cell in closure:
                value = cell.cell_contents
                if inspect.isclass(value) or inspect.isfunction(value):
                    captured.append({"callable": getattr(value, "__qualname__", ""),
                                     "module": getattr(value, "__module__", "")})
                else:
                    captured.append(clone(value))
            result["closure"] = captured
    if inspect.isclass(factory):
        result["methods"] = {key: _code_record(value.__code__) for key, value in vars(factory).items()
                             if hasattr(value, "__code__")}
    result["configuration"] = clone(getattr(factory, "configuration", {}))
    explicit = getattr(factory, "fingerprint", None)
    if explicit is not None:
        result["declared_fingerprint"] = name(explicit, "factory fingerprint")
    return result


@dataclass(frozen=True)
class AlgorithmSpec:
    algorithm: str
    version: str
    factory: object
    fingerprint: str

    @classmethod
    def create(cls, definition, registry_name=None):
        if isinstance(definition, Mapping):
            factory = definition.get("factory")
            algorithm = definition.get("algorithm", registry_name)
            version = definition.get("version")
            configuration = clone(definition.get("configuration", {}))
        else:
            factory = definition
            algorithm = getattr(factory, "algorithm", registry_name)
            version = getattr(factory, "version", None)
            configuration = {}
        name(algorithm, "random algorithm")
        name(version, "random algorithm version")
        if registry_name is not None and algorithm != registry_name:
            raise ValueError("Random registry key disagrees with algorithm declaration")
        if not callable(factory):
            raise ValueError("Random algorithm factory must be callable")
        metadata = {"algorithm": algorithm, "version": version, "factory": _factory_record(factory),
                    "configuration": configuration, "seed_derivation": "sha256-json-root-and-stream/v1"}
        raw = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return cls(algorithm, version, factory, hashlib.sha256(raw.encode("utf-8")).hexdigest())

    def create_backend(self, seed):
        backend = self.factory(seed)
        if getattr(backend, "algorithm", None) != self.algorithm or getattr(backend, "version", None) != self.version:
            raise ValueError("Random backend algorithm/version disagrees with its factory declaration")
        for method in ("sample", "snapshot", "restore"):
            if not callable(getattr(backend, method, None)):
                raise ValueError(f"Random backend lacks required method: {method}")
        clone(backend.snapshot())
        return backend


class RandomStreams:
    ALGORITHM = DEFAULT_ALGORITHM

    def __init__(self, seed=0, lock=None, clock=None, factory=None, algorithm=None, registry=None):
        self._lock = lock or RLock()
        if algorithm is not None:
            name(algorithm, "random algorithm")
        self._seed = clone(seed)
        self._clock = clock or (lambda: 0)
        self._registry = {DEFAULT_ALGORITHM: AlgorithmSpec.create(MT19937Backend)}
        if registry is not None:
            if not isinstance(registry, Mapping):
                raise ValueError("random registry must map algorithm names to factories")
            for identifier, definition in registry.items():
                self._register(AlgorithmSpec.create(definition, identifier))
        if factory is not None:
            spec = AlgorithmSpec.create(factory)
            self._register(spec)
            if algorithm is None:
                algorithm = spec.algorithm
        self._algorithm = algorithm or DEFAULT_ALGORITHM
        if self._algorithm not in self._registry:
            raise ValueError(f"Unknown random algorithm: {self._algorithm}")
        self._streams = {}
        self._counts = {}
        self._samples = []

    def _register(self, spec):
        if spec.algorithm in self._registry:
            raise ValueError(f"Random algorithm already registered: {spec.algorithm}")
        self._registry[spec.algorithm] = spec

    @property
    def algorithm(self):
        return self._algorithm

    @property
    def version(self):
        return self._registry[self._algorithm].version

    @property
    def fingerprint(self):
        return self._registry[self._algorithm].fingerprint

    def _derived_seed(self, stream, seed=_SEED_UNSPECIFIED):
        raw = json.dumps([self._seed if seed is _SEED_UNSPECIFIED else seed, stream], ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
        return int.from_bytes(hashlib.sha256(raw).digest(), "big")

    def _generator(self, stream):
        if stream not in self._streams:
            generator = self._registry[self._algorithm].create_backend(self._derived_seed(stream))
            self._streams[stream] = generator
            self._counts[stream] = 0
        return self._streams[stream]

    def sample(self, stream):
        with self._lock:
            name(stream, "random stream")
            generator = self._generator(stream)
            rollback = clone(generator.snapshot()) if self._algorithm != DEFAULT_ALGORITHM else None
            try:
                value = generator.sample()
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value < 1:
                    raise ValueError("Random sample must be finite and in [0, 1)")
            except Exception:
                if rollback is not None:
                    generator.restore(rollback)
                raise
            self._counts[stream] += 1
            self._samples.append({"sequence": len(self._samples) + 1, "stream": stream,
                                  "index": self._counts[stream], "value": value,
                                  "time": self._clock()})
            return value

    @property
    def samples(self):
        with self._lock:
            return tuple(readonly(clone(sample)) for sample in self._samples)

    def snapshot(self):
        with self._lock:
            return clone({"algorithm": self.algorithm, "version": self.version, "fingerprint": self.fingerprint,
                          "seed": self._seed,
                          "streams": {key: {"state": self._streams[key].snapshot(), "count": self._counts[key]}
                                      for key in sorted(self._streams)}, "samples": self._samples})

    def empty_copy(self):
        """Keep registered trusted factories while staging a restore."""
        candidate = object.__new__(RandomStreams)
        candidate._lock = RLock()
        candidate._seed, candidate._clock = clone(self._seed), self._clock
        candidate._registry = dict(self._registry)
        candidate._algorithm = self._algorithm
        candidate._streams, candidate._counts, candidate._samples = {}, {}, []
        return candidate

    def restore(self, data):
        with self._lock:
            data = clone(data)
            algorithm = data["algorithm"]
            name(algorithm, "checkpoint random algorithm")
            if algorithm not in self._registry:
                raise ValueError(f"Unknown random algorithm in checkpoint: {algorithm}")
            spec = self._registry[algorithm]
            if data.get("version") != spec.version:
                raise ValueError("Checkpoint random algorithm version does not match its registered factory")
            if data.get("fingerprint") != spec.fingerprint:
                raise ValueError("Checkpoint random algorithm fingerprint does not match its registered factory")
            streams, counts = {}, {}
            for stream, item in data["streams"].items():
                name(stream, "random stream")
                backend = spec.create_backend(self._derived_seed(stream, data["seed"]))
                backend.restore(clone(item["state"]))
                clone(backend.snapshot())
                streams[stream] = backend
                counts[stream] = integer(item["count"], "sample count", 0)
            logged_counts = {key: 0 for key in streams}
            previous_time = 0
            for sequence, sample in enumerate(data["samples"], 1):
                stream = sample["stream"]
                integer(sample["sequence"], "sample sequence", 1)
                integer(sample["index"], "stream sample index", 1)
                if stream not in streams or sample["sequence"] != sequence:
                    raise ValueError("Invalid random consumption sequence")
                logged_counts[stream] += 1
                if sample["index"] != logged_counts[stream]:
                    raise ValueError("Invalid per-stream consumption index")
                integer(sample["time"], "sample time", 0)
                if sample["time"] < previous_time:
                    raise ValueError("Random sample times must be nondecreasing")
                if not isinstance(sample["value"], (int, float)) or isinstance(sample["value"], bool) or not 0 <= sample["value"] < 1:
                    raise ValueError("Invalid random sample")
                previous_time = sample["time"]
            if logged_counts != counts:
                raise ValueError("Random state counts disagree with sample log")
            self._seed, self._algorithm, self._streams, self._counts = data["seed"], algorithm, streams, counts
            self._samples = data["samples"]
