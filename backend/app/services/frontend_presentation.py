"""Presentation ownership only; never owns game readers, sessions or WS policy."""
import secrets
import threading
import time


class FrontendPresentation:
    def __init__(self, mode='desktop'):
        self.mode = mode
        self.managed = False
        self._pending = None
        self._lock = threading.RLock()
        self._pages = {}
        self._owner = None
        self._fallback_used = False

    def request_web(self, now=None, client_id=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            self._pages = {key: seen for key, seen in self._pages.items() if now - seen < 15}
            target = client_id or (self._owner if self._owner in self._pages else
                                   max(self._pages, key=self._pages.get, default=None))
            token = secrets.token_urlsafe(24)
            self._pending = (token, now + 30, target)
            self._fallback_used = False
            return token

    def confirm_web(self, token, now=None, client_id=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            if (not self._pending or token != self._pending[0] or now > self._pending[1]
                    or client_id != self._pending[2]):
                return False
            self._pending = None
            self._owner = client_id
            self.mode, self.managed = 'web', True
            return True

    def claim_web(self, token, client_id, now=None):
        now = time.monotonic() if now is None else now
        self._validate_client(client_id)
        with self._lock:
            if (not self._pending or token != self._pending[0] or now > self._pending[1]
                    or self._pending[2] not in (None, client_id)):
                return False
            self._pending = (token, self._pending[1], client_id)
            self._pages[client_id] = now
            return True

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
                raise ValueError('待机页面数量已达上限')
            self._pages[client_id] = now
            # Initial direct navigation can reserve one page. Once managed,
            # unselected pages never elect themselves merely by polling.
            if not self.managed and self._pending is None:
                self.request_web(now=now, client_id=client_id)
            result = {**self.status(), 'active': self.mode == 'web' and self._owner == client_id}
            if self._pending and now <= self._pending[1] and self._pending[2] == client_id:
                result['handoff'] = self._pending[0]
            return result

    def has_target(self, token):
        with self._lock:
            return bool(self._pending and self._pending[0] == token and self._pending[2])

    def release_fallback(self, token, now=None):
        """Open at most one fallback tab; late old requests cannot fan out."""
        now = time.monotonic() if now is None else now
        with self._lock:
            if (not self._pending or self._pending[0] != token or now > self._pending[1]
                    or self._fallback_used):
                return False
            self._pending = (token, self._pending[1], None)
            self._fallback_used = True
            return True

    def stream_allowed(self, client_id, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            if not client_id:
                return not self.managed  # Legacy local tests / initial transport.
            if self.mode == 'web' and self._owner == client_id:
                return True
            return bool(self._pending and self._pending[2] == client_id and now <= self._pending[1])

    def desktop(self):
        with self._lock:
            self._pending = None
            self.mode, self.managed = 'desktop', True

    @property
    def native_active(self):
        return not self.managed or self.mode == 'desktop'

    @property
    def web_active(self):
        return not self.managed or self.mode == 'web'

    def status(self):
        return {'mode': self.mode if self.managed else 'shared'}
