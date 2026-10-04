"""Single executor for arbitrary components, callbacks, and JSON tasks."""
from threading import RLock
from contextlib import contextmanager

from ._data import clone, integer, name
from .clock import Clock
from .events import EventLog
from .random import RandomStreams
from .scheduler import Scheduler
from .transaction import commit
from .world import World


class ReactionBudgetExceeded(RuntimeError):
    """A same-time callback cycle exceeded the configured work budget."""


class Session:
    CHECKPOINT_SCHEMA = "ark-sim/kernel-checkpoint/v1"

    def __init__(self, quantum=1 / 30, seed=0, phase_order=None, reaction_budget=10000,
                 random_factory=None, random_algorithm=None, random_registry=None):
        self._lock = RLock()
        self.clock = Clock(quantum)
        self.reaction_budget = integer(reaction_budget, "reaction budget", 1)
        self.world = World(self._lock)
        self.scheduler = Scheduler(phase_order, self._lock)
        self._events = EventLog(self._lock)
        self.random = RandomStreams(seed, self._lock, lambda: self.time, factory=random_factory,
                                    algorithm=random_algorithm, registry=random_registry)
        self._handlers = {}
        self._systems = []
        self._active_key = None
        self._active_task = None
        self._advancing = False
        self._failure = None
        self._atomic_depth = 0
        self._cache_epoch = 0

    @property
    def time(self):
        with self._lock:
            return self.clock.time

    @property
    def quantum(self):
        return self.clock.quantum

    @property
    def current_task(self):
        """Detached dispatch identity; callback data cannot select this task."""
        with self._lock:
            return clone(self._active_task) if self._active_task is not None else None

    @property
    def events(self):
        return self._events.records

    @property
    def cache_epoch(self):
        """Local invalidation boundary for derived caches, never replay state."""
        with self._lock:
            return self._cache_epoch

    def register_handler(self, kind, callback):
        with self._lock:
            self._require_idle_registration()
            name(kind, "handler kind")
            if not callable(callback):
                raise TypeError("handler must be callable")
            if kind in self._handlers:
                raise ValueError(f"Handler already registered: {kind}")
            self._handlers[kind] = callback

    def add_system(self, callback, phase=0):
        with self._lock:
            self._require_idle_registration()
            if not callable(callback):
                raise TypeError("system must be callable")
            self.scheduler.rank(phase)
            sequence = self.scheduler.reserve_sequence()
            self._systems.append({"callback": callback, "phase": phase, "priority": 0, "seq": sequence})
            return sequence

    def add_boundary_system(self, callback):
        """Settle registered domain state at each new clock boundary.

        This is an explicit opt-in observer, not dispatch of the next frame's
        queued tasks. Registration is part of the checkpoint system signature.
        """
        with self._lock:
            self._require_idle_registration()
            if not callable(callback):raise TypeError('Boundary callback must be callable')
            seq=self.scheduler.reserve_sequence()
            self._systems.append({'callback':callback,'phase':0,'priority':0,'seq':seq,'boundary':True})
            return seq

    def _require_idle_registration(self):
        if self._advancing or self._atomic_depth:
            raise RuntimeError("Callbacks cannot be registered during advance or an atomic operation")

    def _validate_schedule(self, at, phase, priority, scheduler=None):
        scheduler = scheduler or self.scheduler
        integer(at, "task time", 0)
        integer(priority, "task priority")
        rank = scheduler.rank(phase)
        if at < self.time:
            raise ValueError(f"Cannot schedule in the past: {at} < {self.time}")
        if self._active_key is not None and at == self.time:
            if (rank, priority) < self._active_key[1:3]:
                raise ValueError("A same-time task cannot precede the currently executing phase/priority")

    def schedule(self, kind, payload, at, phase=0, priority=0):
        with self._lock:
            self._validate_schedule(at, phase, priority)
            return self.scheduler.schedule(kind, payload, at, phase, priority, now=self.time)

    def cancel(self, task_id):
        with self._lock:
            self.scheduler.cancel(task_id)

    def emit(self, event_type, payload, cause=None):
        with self._lock:
            return self._events.emit(event_type, payload, self.time, cause)

    def commit(self, intents):
        with self._lock:
            return commit(self, intents)

    @contextmanager
    def atomic(self):
        """Group domain commits and direct writes into a nested savepoint.

        Holds the executor lock throughout. On failure all stores and identity
        allocators roll back, including random consumption. Journal capture is
        constant in history length: append-only logs retain their original
        container and only their length/next ID is saved. Callbacks and clock
        advancement cannot change while the operation is open.
        """
        with self._lock:
            saved = self._capture_atomic()
            self._atomic_depth += 1
            try:
                yield self
            except BaseException:
                self._restore_atomic(saved)
                raise
            finally:
                self._atomic_depth -= 1

    def _capture_atomic(self):
        return {"world": self.world._fork_validated(), "scheduler": self.scheduler.fork(),
                "events": self._events._records, "event_length": len(self._events._records),
                "event_next_id": self._events._next_id,
                "random_streams": dict(self.random._streams),
                "random_states": {key: clone(backend.snapshot()) for key, backend in self.random._streams.items()},
                "random_counts": dict(self.random._counts), "random_seed": clone(self.random._seed),
                "random_algorithm": self.random._algorithm, "random_samples": self.random._samples,
                "random_length": len(self.random._samples), "time": self.time, "quantum": self.quantum,
                "reaction_budget": self.reaction_budget, "failure": clone(self._failure), "active_key": self._active_key}

    def _restore_atomic(self, saved):
        # Captured world/queue records were already validated; no boundary
        # checkpoint API is called, so this also works within an active handler.
        self.world._adopt_validated(saved["world"], preserve_views=False)
        queue = saved["scheduler"]
        self.scheduler.phase_order, self.scheduler._phase_ranks = queue.phase_order, queue._phase_ranks
        self.scheduler._tasks, self.scheduler._heap = queue._tasks, queue._heap
        self.scheduler._next_id, self.scheduler._next_seq = queue._next_id, queue._next_seq
        del saved["events"][saved["event_length"]:]
        self._events._records, self._events._next_id = saved["events"], saved["event_next_id"]
        payload_cache = getattr(self._events, "_payload_interner", None)
        if payload_cache is not None:
            payload_cache.clear()
        for key, backend in saved["random_streams"].items():
            backend.restore(saved["random_states"][key])
        del saved["random_samples"][saved["random_length"]:]
        self.random._streams, self.random._counts = saved["random_streams"], saved["random_counts"]
        self.random._samples = saved["random_samples"]
        self.random._seed, self.random._algorithm = saved["random_seed"], saved["random_algorithm"]
        self.clock.time, self.clock.quantum = saved["time"], saved["quantum"]
        self.reaction_budget, self._failure = saved["reaction_budget"], saved["failure"]
        self._active_key = saved["active_key"]
        self._cache_epoch += 1

    def advance(self, n):
        """Process [time, time+n), including newly scheduled same-time work."""
        with self._lock:
            integer(n, "advance units", 0)
            if self._atomic_depth:
                raise RuntimeError("advance cannot run while an atomic operation is open")
            if self._advancing:
                raise RuntimeError("advance cannot be called recursively from a callback")
            if self._failure is not None:
                raise RuntimeError("Session execution has failed; restore a valid checkpoint before advancing")
            end = self.time + n
            self._advancing = True
            try:
                while self.time < end:
                    systems = sorted((s for s in self._systems if not s.get("boundary", False)), key=lambda item: (
                        self.scheduler.rank(item["phase"]), item["priority"], item["seq"]))
                    system_index = 0
                    callbacks = 0
                    recent = []
                    while True:
                        task = self.scheduler.peek()
                        if task is not None and task["at"] < self.time:
                            raise ValueError("Task queue contains a task before current logical time")
                        task_key = self.scheduler.key(task) if task is not None and task["at"] == self.time else None
                        system = systems[system_index] if system_index < len(systems) else None
                        system_key = (self.time, self.scheduler.rank(system["phase"]), system["priority"], system["seq"]) if system else None
                        if task_key is None and system_key is None:
                            break
                        if callbacks >= self.reaction_budget:
                            causes = [(record["id"], record["cause"]) for record in self._events._records[-8:]]
                            raise ReactionBudgetExceeded(
                                f"Reaction budget {self.reaction_budget} exhausted at time {self.time}; "
                                f"recent callbacks={recent[-8:]}; event causes={causes}")
                        callbacks += 1
                        if task_key is not None and (system_key is None or task_key < system_key):
                            task = self.scheduler.pop()
                            self._active_key = task_key
                            recent.append(f"task {task['id']} ({task['kind']})")
                            handler = self._handlers.get(task["kind"])
                            if handler is None:
                                raise KeyError(f"No handler registered for task kind: {task['kind']}")
                            self._active_task = task
                            try:
                                handler(self, clone(task["payload"]))
                            finally:
                                self._active_task = None
                        else:
                            self._active_key = system_key
                            recent.append(f"system {system['seq']} (phase {system['phase']})")
                            system_index += 1
                            system["callback"](self)
                    self._active_key = None
                    self.clock.time += 1
                    # Run every step, so segmented and continuous advances
                    # settle the same boundaries and record the same history.
                    for observer in sorted((s for s in self._systems if s.get('boundary',False)),key=lambda s:s['seq']):
                        if callbacks>=self.reaction_budget:raise ReactionBudgetExceeded('Boundary callback exceeds reaction budget')
                        callbacks+=1
                        with self.atomic():observer['callback'](self)
                    # Boundary observers may compute at the next logical time.
                    # Derived memoization must not survive an idle boundary:
                    # restoration rebuilds views/cache, while continuous and
                    # segmented execution must emit the same calculation trace.
                    self._cache_epoch += 1
            except Exception as exc:
                self._failure = {"time": self.time, "exception": type(exc).__name__, "message": str(exc)}
                raise
            finally:
                self._active_key = None
                self._active_task = None
                self._advancing = False
            return self.time

    def snapshot(self):
        with self._lock:
            return self._state_data()

    def enable_event_journal(self, path):
        with self._lock:
            if self._advancing or self._atomic_depth:
                raise RuntimeError("Event storage can only change at an idle boundary")
            self._events.enable_disk(path)

    def export_events_jsonl(self, path):
        return self._events.export_jsonl(path)

    def checkpoint(self, event_reference=False):
        with self._lock:
            if self._advancing or self._atomic_depth:
                raise RuntimeError("Checkpoint is only available between advance calls and atomic operations")
            return self._state_data(event_reference)

    def _state_data(self, event_reference=False):
        return clone({"schema": self.CHECKPOINT_SCHEMA, "time": self.time,
                      "boundary": not self._advancing and not self._atomic_depth,
                      "quantum": self.quantum, "reaction_budget": self.reaction_budget,
                      "world": self.world.snapshot(), "scheduler": self.scheduler.snapshot(),
                      "events": self._events.snapshot(event_reference), "random": self.random.snapshot(),
                      "systems": [{**{key: item[key] for key in ("phase", "priority", "seq")},
                                   **({'boundary':True} if item.get('boundary',False) else {})}
                                  for item in self._systems], "failure": self._failure})

    def restore(self, data):
        """Validate all stores first; registered callback implementations are retained."""
        with self._lock:
            if self._advancing or self._atomic_depth:
                raise RuntimeError("Cannot restore during advance or an atomic operation")
            data = clone(data)
            if data["schema"] != self.CHECKPOINT_SCHEMA:
                raise ValueError("Unsupported kernel checkpoint schema")
            if data.get("boundary") is not True:
                raise ValueError("Restore requires a snapshot captured between advance calls")
            clock = Clock(data["quantum"], data["time"])
            budget = integer(data["reaction_budget"], "reaction budget", 1)
            world = World()
            world.restore(data["world"])
            scheduler = Scheduler()
            scheduler.restore(data["scheduler"])
            events = EventLog()
            events.restore(data["events"])
            random = self.random.empty_copy()
            random.restore(data["random"])
            failure = data["failure"]
            if failure is not None:
                if not isinstance(failure, dict) or not {"time", "exception", "message"}.issubset(failure):
                    raise ValueError("Invalid checkpoint execution failure")
                if integer(failure["time"], "failure time", 0) != clock.time:
                    raise ValueError("Failure time disagrees with checkpoint time")
                name(failure["exception"], "failure exception")
                if not isinstance(failure["message"], str):
                    raise ValueError("Failure message must be a string")
            if any(task["at"] < clock.time for task in scheduler.pending):
                raise ValueError("Checkpoint task is before checkpoint time")
            if any(event["time"] > clock.time for event in events._records):
                raise ValueError("Checkpoint event is after checkpoint time")
            if any(sample["time"] > clock.time for sample in random.samples):
                raise ValueError("Checkpoint random sample is after checkpoint time")
            if len(data["systems"]) != len(self._systems):
                raise ValueError("Restore requires the same registered system count")
            system_sequences = set()
            for recorded, live in zip(data["systems"], self._systems):
                boundary=recorded.get('boundary',False)
                if type(boundary) is not bool or boundary!=live.get('boundary',False):
                    raise ValueError('Restore requires identical boundary system registration')
                integer(recorded["priority"], "system priority")
                if recorded["phase"] != live["phase"] or recorded["priority"] != live["priority"]:
                    raise ValueError("Restore requires the same registered system phases")
                scheduler.rank(recorded["phase"])
                sequence = integer(recorded["seq"], "system sequence", 1)
                if sequence in system_sequences or sequence >= scheduler._next_seq:
                    raise ValueError("Invalid checkpoint system sequence")
                system_sequences.add(sequence)
            if system_sequences.intersection(task["seq"] for task in scheduler.pending):
                raise ValueError("Task and system sequences collide")
            self.clock.quantum, self.clock.time = clock.quantum, clock.time
            self.reaction_budget = budget
            self.world._entities, self.world._aliases, self.world._next_id = world._entities, world._aliases, world._next_id
            self.world._versions, self.world._views = world._versions, {}
            self.scheduler.phase_order, self.scheduler._phase_ranks = scheduler.phase_order, scheduler._phase_ranks
            self.scheduler._tasks, self.scheduler._heap = scheduler._tasks, scheduler._heap
            self.scheduler._next_id, self.scheduler._next_seq = scheduler._next_id, scheduler._next_seq
            self._events._records, self._events._next_id = events._records, events._next_id
            self._events._payload_interner.clear()
            self.random._seed, self.random._streams = random._seed, random._streams
            self.random._counts, self.random._samples = random._counts, random._samples
            self.random._algorithm = random._algorithm
            for recorded, live in zip(data["systems"], self._systems):
                live["seq"] = recorded["seq"]
            self._failure = failure
            self._cache_epoch += 1
