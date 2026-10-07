"""Stable task ordering independent of game-domain semantics."""
import heapq
from collections.abc import Mapping
from threading import RLock

from ._data import clone, integer, name, readonly


class Scheduler:
    def __init__(self, phase_order=None, lock=None):
        self._lock = lock or RLock()
        self.phase_order = clone(phase_order)
        if phase_order is None:
            self._phase_ranks = None
        elif isinstance(phase_order, Mapping):
            self._phase_ranks = {}
            for phase, rank in phase_order.items():
                # JSON mapping keys are names; sequence syntax also allows integer phases.
                name(phase, "phase")
                self._phase_ranks[phase] = integer(rank, "phase rank")
            if len(set(self._phase_ranks.values())) != len(self._phase_ranks):
                raise ValueError("phase ranks must be unique")
        elif isinstance(phase_order, (list, tuple)):
            self._phase_ranks = {}
            for rank, phase in enumerate(phase_order):
                if isinstance(phase, bool) or not isinstance(phase, (str, int)):
                    raise ValueError("phase must be a string or integer")
                if isinstance(phase, str):
                    name(phase, "phase")
                if phase in self._phase_ranks:
                    raise ValueError(f"Duplicate phase: {phase}")
                self._phase_ranks[phase] = rank
        else:
            raise ValueError("phase_order must be an array or object")
        self._heap = []
        self._tasks = {}
        self._next_id = 1
        self._next_seq = 1

    def rank(self, phase):
        if isinstance(phase, bool) or not isinstance(phase, (str, int)):
            raise ValueError("phase must be a string or integer")
        if self._phase_ranks is None:
            return integer(phase, "phase")
        if phase not in self._phase_ranks:
            raise ValueError(f"Phase is absent from phase_order: {phase}")
        return self._phase_ranks[phase]

    def reserve_sequence(self):
        with self._lock:
            sequence = self._next_seq
            self._next_seq += 1
            return sequence

    @property
    def next_task_id(self):
        """Read the allocator without serializing every pending payload."""
        with self._lock:
            return self._next_id

    def fork(self):
        """Internal isolated queue for a transaction or nested savepoint.

        Stored task records are owned here and never edited after schedule or
        restore. Public peek/pop/pending/snapshot return detached read views.
        Copying the task index and heap therefore isolates all supported writes
        while retaining already-validated payloads. New schedule payloads still
        cross the complete JSON clone/validation boundary.
        """
        with self._lock:
            candidate = Scheduler(self.phase_order)
            candidate._tasks = dict(self._tasks)
            candidate._heap = list(self._heap)
            candidate._next_id = self._next_id
            candidate._next_seq = self._next_seq
            return candidate

    def key(self, task):
        return (task["at"], self.rank(task["phase"]), task["priority"], task["seq"])

    def schedule(self, kind, payload, at, phase=0, priority=0, now=0):
        with self._lock:
            name(kind, "task kind")
            integer(at, "task time", 0)
            integer(now, "current time", 0)
            if at < now:
                raise ValueError(f"Cannot schedule in the past: {at} < {now}")
            self.rank(phase)
            integer(priority, "task priority")
            payload = clone(payload)
            task_id = self._next_id
            self._next_id += 1
            task = {"id": task_id, "kind": kind, "payload": payload, "at": at,
                    "phase": phase, "priority": priority, "seq": self.reserve_sequence()}
            self._tasks[task_id] = task
            heapq.heappush(self._heap, (self.key(task), task_id))
            return task_id

    def cancel(self, task_id):
        with self._lock:
            integer(task_id, "task ID", 1)
            if task_id not in self._tasks:
                raise KeyError(f"Unknown or completed task ID: {task_id}")
            del self._tasks[task_id]
            if not self._tasks:
                self._heap.clear()
            elif len(self._heap) > max(64, 2*len(self._tasks)):
                # Forked transactions retain the heap instead of rebuilding it
                # on every commit. Bound cancelled records with amortized
                # compaction; ordering still uses the complete stable task key.
                self._heap = [(self.key(task), key) for key, task in self._tasks.items()]
                heapq.heapify(self._heap)

    def _discard_cancelled(self):
        while self._heap and self._heap[0][1] not in self._tasks:
            heapq.heappop(self._heap)

    def peek(self):
        with self._lock:
            self._discard_cancelled()
            return readonly(clone(self._tasks[self._heap[0][1]])) if self._heap else None

    def pop(self):
        with self._lock:
            self._discard_cancelled()
            if not self._heap:
                return None
            _, task_id = heapq.heappop(self._heap)
            return readonly(clone(self._tasks.pop(task_id)))

    @property
    def pending(self):
        with self._lock:
            return tuple(readonly(clone(task)) for task in sorted(self._tasks.values(), key=self.key))

    def snapshot(self):
        with self._lock:
            return clone({"phase_order": self.phase_order, "tasks": sorted(self._tasks.values(), key=self.key),
                          "next_id": self._next_id, "next_seq": self._next_seq})

    def restore(self, data):
        with self._lock:
            data = clone(data)
            candidate = Scheduler(data["phase_order"])
            for task in data["tasks"]:
                if not isinstance(task, dict) or not {"id", "kind", "payload", "at", "phase", "priority", "seq"}.issubset(task):
                    raise ValueError("Task checkpoint lacks required fields")
                task_id = integer(task["id"], "task ID", 1)
                name(task["kind"], "task kind")
                integer(task["at"], "task time", 0)
                integer(task["priority"], "task priority")
                integer(task["seq"], "task sequence", 1)
                candidate.rank(task["phase"])
                if task_id in candidate._tasks:
                    raise ValueError(f"Duplicate task ID: {task_id}")
                candidate._tasks[task_id] = task
            sequences = [task["seq"] for task in candidate._tasks.values()]
            if len(sequences) != len(set(sequences)):
                raise ValueError("Duplicate task sequence")
            candidate._next_id = integer(data["next_id"], "next task ID", 1)
            candidate._next_seq = integer(data["next_seq"], "next task sequence", 1)
            if candidate._tasks and candidate._next_id <= max(candidate._tasks):
                raise ValueError("next task ID would reuse an existing ID")
            if sequences and candidate._next_seq <= max(sequences):
                raise ValueError("next task sequence would reuse an existing sequence")
            candidate._heap = [(candidate.key(task), task_id) for task_id, task in candidate._tasks.items()]
            heapq.heapify(candidate._heap)
            self.phase_order, self._phase_ranks = candidate.phase_order, candidate._phase_ranks
            self._tasks, self._heap = candidate._tasks, candidate._heap
            self._next_id, self._next_seq = candidate._next_id, candidate._next_seq
