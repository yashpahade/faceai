"""Phase 4: micro-batching + admission control."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from faceai.serving.batcher import MicroBatcher
from faceai.serving.limiter import ConcurrencyLimiter, OverloadedError


class CountingModel:
    """Fake model: har item ka 'embedding' = item ka mean; calls + batch sizes record karta hai."""

    def __init__(self, delay: float = 0.01):
        self.delay = delay
        self.batch_sizes: list[int] = []

    def __call__(self, items):
        self.batch_sizes.append(len(items))
        time.sleep(self.delay)  # GPU call ka fixed overhead
        return np.array([[float(x.mean())] for x in items], np.float32)


def test_results_go_back_to_the_right_caller():
    model = CountingModel()
    b = MicroBatcher(model, max_batch=64, max_wait_ms=20)
    try:
        with ThreadPoolExecutor(16) as ex:
            futs = {
                v: ex.submit(b, [np.full((2, 2), v), np.full((2, 2), v + 1000)]) for v in range(16)
            }
        for v, f in futs.items():
            assert f.result().ravel().tolist() == [v, v + 1000]
    finally:
        b.close()


def test_concurrent_requests_are_batched_together():
    model = CountingModel(delay=0.02)
    b = MicroBatcher(model, max_batch=64, max_wait_ms=30)
    try:
        with ThreadPoolExecutor(16) as ex:
            list(ex.map(lambda v: b([np.full((2, 2), v)]), range(16)))
        # 16 requests, par bahut kam model calls
        assert len(model.batch_sizes) < 16
        assert b.avg_batch_size > 1
    finally:
        b.close()


def test_max_batch_is_respected():
    model = CountingModel(delay=0.02)
    b = MicroBatcher(model, max_batch=4, max_wait_ms=50)
    try:
        with ThreadPoolExecutor(12) as ex:
            list(ex.map(lambda v: b([np.full((2, 2), v)]), range(12)))
        assert max(model.batch_sizes) <= 4
    finally:
        b.close()


def test_model_error_propagates_to_callers():
    def boom(items):
        raise ValueError("cuda died")

    b = MicroBatcher(boom, max_wait_ms=1)
    try:
        with pytest.raises(ValueError, match="cuda died"):
            b([np.zeros((2, 2))])
    finally:
        b.close()


def test_limiter_rejects_when_full():
    lim = ConcurrencyLimiter(max_concurrent=1, max_wait_ms=50)
    entered, release = threading.Event(), threading.Event()

    def hold():
        with lim.slot():
            entered.set()
            release.wait(2)

    t = threading.Thread(target=hold)
    t.start()
    entered.wait(2)
    with pytest.raises(OverloadedError), lim.slot():
        pass
    assert lim.rejected == 1
    release.set()
    t.join()
    with lim.slot():  # slot free again
        assert lim.in_flight == 1


def test_api_returns_503_with_retry_after_when_overloaded(client):
    import cv2

    from tests.fakes import make_image

    client.app.state.limiter = ConcurrencyLimiter(max_concurrent=1, max_wait_ms=0)
    ok, buf = cv2.imencode(".png", make_image(42))
    with client.app.state.limiter.slot():  # koi aur request slot pakde hue hai
        r = client.post("/v1/recognize", files={"file": ("f.png", buf.tobytes(), "image/png")})
    assert r.status_code == 503
    assert r.headers["Retry-After"] == "1"
