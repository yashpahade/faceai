"""Active liveness challenge (head movement)."""

import numpy as np

from faceai.security.challenge import ChallengeStore, signed_yaw
from faceai.vision.types import DetectedFace


def _face(yaw: float, identity: int = 1) -> DetectedFace:
    # eyes at x=40, 80; nose x = 60 + yaw*20  -> signed_yaw == yaw
    kps = np.array([[40, 50], [80, 50], [60 + yaw * 20, 70], [45, 90], [75, 90]], np.float32)
    v = np.random.default_rng(identity).standard_normal(16).astype(np.float32)
    return DetectedFace(
        bbox=np.array([20, 20, 100, 120], np.float32),
        kps=kps,
        det_score=0.9,
        embedding=v / np.linalg.norm(v),
    )


POSE = {"turn_left": -0.6, "turn_right": 0.6, "center": 0.0}


def _answer(steps, identity=1):
    return [[_face(POSE[s], identity)] for s in steps]


def test_signed_yaw_direction():
    assert signed_yaw(_face(-0.6).kps) < -0.5
    assert signed_yaw(_face(0.6).kps) > 0.5
    assert abs(signed_yaw(_face(0.0).kps)) < 1e-6


def test_correct_answer_passes_and_token_is_single_use():
    store = ChallengeStore()
    c = store.create()
    assert len(c.steps) == 2 and c.steps[0] in ("turn_left", "turn_right")
    r = store.verify(c.id, _answer(c.steps))
    assert r.live and r.token
    emb = store.consume_token(r.token)
    assert emb is not None and abs(float(np.linalg.norm(emb)) - 1) < 1e-5
    assert store.consume_token(r.token) is None  # dobara nahi


def test_static_photo_fails():
    store = ChallengeStore()
    c = store.create()
    frozen = [[_face(0.0)] for _ in c.steps]  # photo sir nahi ghuma sakti
    r = store.verify(c.id, frozen)
    assert not r.live and "not performed" in r.reason


def test_face_swap_between_frames_fails():
    store = ChallengeStore()
    c = store.create()
    ans = _answer(c.steps)
    ans[-1] = [_face(POSE[c.steps[-1]], identity=99)]
    r = store.verify(c.id, ans)
    assert not r.live and "different faces" in r.reason


def test_challenge_is_single_use_and_expires():
    now = [0.0]
    store = ChallengeStore(clock=lambda: now[0])
    c = store.create()
    store.verify(c.id, [[_face(0.0)]])  # galat answer bhi challenge kha jaata hai
    assert store.verify(c.id, _answer(c.steps)).reason == "challenge already used"
    c2 = store.create()
    now[0] += 61
    assert store.verify(c2.id, _answer(c2.steps)).reason == "unknown or expired challenge"


def test_multiple_faces_rejected():
    store = ChallengeStore()
    c = store.create()
    ans = _answer(c.steps)
    ans[0] = ans[0] + [_face(0.0, identity=5)]
    assert "exactly one face" in store.verify(c.id, ans).reason


# ---------- API ----------
def _png(value: int) -> tuple:
    import cv2

    from tests.fakes import make_image

    ok, buf = cv2.imencode(".png", make_image(value))
    return ("f.png", buf.tobytes(), "image/png")


def test_liveness_api_flow(client):
    c = client.post("/v1/liveness/challenge").json()
    assert len(c["steps"]) == 2 and c["expires_in_s"] == 60
    # Fake engine ke faces hamesha frontal hain -> steps ko "center" set karke pass path test
    client.app.state.challenges._challenges[c["challenge_id"]].steps = ["center", "center"]
    files = [("frames", _png(42)), ("frames", _png(42))]
    r = client.post("/v1/liveness/verify", data={"challenge_id": c["challenge_id"]}, files=files)
    assert r.status_code == 200 and r.json()["live"] is True and r.json()["token"]
    # same challenge dobara -> reject
    r2 = client.post("/v1/liveness/verify", data={"challenge_id": c["challenge_id"]}, files=files)
    assert r2.json() == {**r2.json(), "live": False, "reason": "challenge already used"}


def test_liveness_api_rejects_frontal_photo_for_turn(client):
    c = client.post("/v1/liveness/challenge").json()
    client.app.state.challenges._challenges[c["challenge_id"]].steps = ["turn_left", "center"]
    files = [("frames", _png(42)), ("frames", _png(42))]
    r = client.post("/v1/liveness/verify", data={"challenge_id": c["challenge_id"]}, files=files)
    assert r.json()["live"] is False and "turn_left" in r.json()["reason"]
