"""Shared desktop/WebUI presentation; never owns readers, sessions or policy."""
import threading
import time


class FrontendPresentation:
    def __init__(self, mode='desktop'):
        # A launch preference never grants exclusive ownership of telemetry.
        self.mode = 'shared'
        self._lock = threading.RLock()
        self._pages = {}

    @staticmethod
    def _validate_client(client_id):
        if not isinstance(client_id, str) or not 1 <= len(client_id) <= 128:
            raise ValueError('无效的网页身份')

    def page_status(self, client_id, now=None):
        self._validate_client(client_id)
        now = time.monotonic() if now is None else now
        with self._lock:
            self._pages = {key: seen for key, seen in self._pages.items() if now - seen < 120}
            if client_id not in self._pages and len(self._pages) >= 128:
                raise ValueError('网页数量已达上限')
            self._pages[client_id] = now
        return {**self.status(), 'active': True}

    def stream_allowed(self, client_id, now=None):
        # Per-channel connection limits and duplicate-client rejection remain
        # owned by WebUiServer; desktop visibility never revokes a web stream.
        if client_id:
            try:
                self._validate_client(client_id)
            except ValueError:
                return False
        return True

    @property
    def native_active(self):
        return True

    @property
    def web_active(self):
        return True

    def status(self):
        return {'mode': 'shared'}
