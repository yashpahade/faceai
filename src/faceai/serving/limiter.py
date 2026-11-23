"""
Admission control / backpressure: ek saath kitni inference chalengi, aur kitna intezaar allowed hai.

Bina limit ke: load badha -> saari requests queue mein -> HAR request slow -> clients timeout karke
retry karte hain -> load aur badhta hai -> server gir jaata hai ("retry storm").
Limit ke saath: capacity bhar gayi -> nayi request turant 503 + `Retry-After`. Jo andar hain wo
time pe complete hoti hain. "Kuch logon ko jaldi 'no'" > "sabko der se timeout".

    max_concurrent  = GPU/CPU pe ek saath kitni requests (zyada => contention, latency badhti)
    max_wait_ms     = slot ke liye kitna rukna; usse zyada => reject
"""

import threading
from contextlib import contextmanager


class OverloadedError(Exception):
    pass


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int, max_wait_ms: float):
        self.max_concurrent = max_concurrent
        self.max_wait = max_wait_ms / 1000
        self._sem = threading.BoundedSemaphore(max_concurrent)
        self._lock = threading.Lock()
        self.in_flight = 0
        self.rejected = 0

    @contextmanager
    def slot(self):
        if not self._sem.acquire(timeout=self.max_wait):
            with self._lock:
                self.rejected += 1
            raise OverloadedError("server busy, retry later")
        with self._lock:
            self.in_flight += 1
        try:
            yield
        finally:
            with self._lock:
                self.in_flight -= 1
            self._sem.release()
