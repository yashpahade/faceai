"""
Dynamic micro-batching: alag-alag requests ke chehron ko EK GPU call mein embed karo.

Kyun? GPU par 1 face aur 16 faces embed karne mein lagbhag same time lagta hai (kernel launch +
memory transfer overhead dominate karta hai). 16 concurrent requests, har ek apna 1-face GPU call
karega to GPU 16 baar "almost khaali" chalega. Batcher unhe jod ke ek call karta hai.

    request A ──┐
    request B ──┼─► queue ─► worker thread: max_batch items YA max_wait_ms, jo pehle ho ─► fn(batch)
    request C ──┘                                                                         │
           ◄──────────────────── har request ko uske apne rows wapas ◄────────────────────┘

Trade-off: `max_wait_ms` = latency jo hum throughput ke liye dete hain. Akeli request ko bhi itna
intezaar karna pad sakta hai. Isliye chhota rakho (2-5 ms) aur load test se tune karo.

Model sirf dynamic batch dimension pe kaam karta hai: ArcFace `['None', 3, 112, 112]` -> haan.
SCRFD detector `[1, 3, ?, ?]` -> nahi (fixed batch 1), isliye detection per-request hi rehta hai.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    items: list[np.ndarray]
    future: Future


class MicroBatcher:
    def __init__(
        self,
        fn: Callable[[list[np.ndarray]], np.ndarray],
        max_batch: int = 32,
        max_wait_ms: float = 3.0,
        name: str = "batcher",
    ):
        self.fn = fn
        self.max_batch = max_batch
        self.max_wait = max_wait_ms / 1000
        self._q: queue.Queue[_Job | None] = queue.Queue()
        self._closed = False
        self.batches = 0  # stats: kitne model calls hue
        self.items = 0  # kitne items process hue  -> items/batches = avg batch size
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def __call__(self, items: list[np.ndarray]) -> np.ndarray:
        """Blocking: items submit karo, apne results ka intezaar karo."""
        if self._closed:
            raise RuntimeError("batcher closed")
        if not items:
            return self.fn([])
        fut: Future = Future()
        self._q.put(_Job(items, fut))
        return fut.result()

    def close(self) -> None:
        self._closed = True
        self._q.put(None)
        self._thread.join(timeout=5)

    @property
    def avg_batch_size(self) -> float:
        return self.items / self.batches if self.batches else 0.0

    def _collect(self, first: _Job) -> list[_Job]:
        jobs, n = [first], len(first.items)
        deadline = time.perf_counter() + self.max_wait
        while n < self.max_batch:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            try:
                job = self._q.get(timeout=remaining)
            except queue.Empty:
                break
            if job is None:  # close() signal: abhi wale jobs khatam karke ruk jao
                self._q.put(None)
                break
            jobs.append(job)
            n += len(job.items)
        return jobs

    def _run(self) -> None:
        while True:
            first = self._q.get()
            if first is None:
                return
            jobs = self._collect(first)
            flat = [x for j in jobs for x in j.items]
            try:
                out = self.fn(flat)
            except Exception as e:  # ek batch fail -> us batch ke saare callers ko error
                for j in jobs:
                    j.future.set_exception(e)
                continue
            self.batches += 1
            self.items += len(flat)
            start = 0
            for j in jobs:
                j.future.set_result(out[start : start + len(j.items)])
                start += len(j.items)
