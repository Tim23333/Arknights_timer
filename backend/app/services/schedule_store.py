"""In-memory last loaded schedule (frontend JSON)."""

from __future__ import annotations

from threading import RLock
from typing import Any, Dict, Optional


class ScheduleStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._payload: Optional[Dict[str, Any]] = None

    def load(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._payload = payload

    def get(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._payload

    def clear(self) -> None:
        with self._lock:
            self._payload = None
