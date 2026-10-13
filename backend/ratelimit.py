"""Small in-memory sliding-window rate limiter for login/registration.

It lives in process memory, so it resets on restart and is per-instance. That
is acceptable for a single free-tier Render instance; it is basic abuse
protection, not a distributed rate limiter.

Why several keys per action?  Behind Vercel + Render the client IP is taken
from a forwarded header that a determined attacker can spoof, and all
visitors can share one proxy address. So accounts are protected by an
*email-based* key (cannot be bypassed by changing IP), and registration also
has a *global* cap as a backstop.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_MAX_KEYS = 5000


class RateLimiter:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def clear(self):
        with self._lock:
            self._hits.clear()

    def _prune(self, key, now, window):
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        return q

    def check(self, key, limit, window):
        """Raise HTTP 429 if `key` already used up `limit` hits in `window` seconds."""
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, now, window)
            if len(q) >= limit:
                raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")
            if not q:
                self._hits.pop(key, None)

    def hit(self, key, window):
        """Record one event for `key`."""
        now = time.monotonic()
        with self._lock:
            self._prune(key, now, window).append(now)
            if len(self._hits) > _MAX_KEYS:  # bound memory under many distinct keys
                for old_key in list(self._hits):
                    if not self._prune(old_key, now, window):
                        self._hits.pop(old_key, None)
                    if len(self._hits) <= _MAX_KEYS * 0.8:
                        break
                while len(self._hits) > _MAX_KEYS:
                    self._hits.pop(next(iter(self._hits)))

    def reset(self, key):
        with self._lock:
            self._hits.pop(key, None)


limiter = RateLimiter()
