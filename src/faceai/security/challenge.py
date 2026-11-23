"""
Active liveness: random head-movement challenge (Phase A anti-spoofing).

    POST /v1/liveness/challenge        -> {"challenge_id", "steps": ["turn_left", "center"], ...}
    POST /v1/liveness/verify  (frames)   -> {"live": true, "token": "..."}  (token 2 min valid)

Client har step ke liye ek frame bhejta hai (order mein). Server check karta hai:
1. har frame mein EXACTLY ek face
2. head sahi direction mein ghuma (yaw, 5 landmarks se: naak aankhon ke beech kahan hai)
3. saare frames mein SAME insaan (embedding similarity) -> beech mein photo badal ke dhoka nahi
4. challenge fresh (60s) aur ek hi baar use (replay of an old successful answer nahi chalega)

Kya rokta hai: printed photo, phone pe static photo (photo sir nahi ghumati, steps random hain).
Kya NAHI rokta: us insaan ka video jismein wo sahi order mein sir ghumaye, 3D mask, deepfake
stream. Uske liye passive PAD model chahiye (docs/phase-a-accuracy.md). Ye "basic" liveness hai.

Direction IMAGE ke hisaab se: "turn_left" = naak image ke LEFT side jaaye. Front camera ka preview
CSS se mirror hota hai, par bheje gaye frames un-mirrored hone chahiye (frontend yahi karta hai).
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

import numpy as np

STEPS = ("turn_left", "turn_right", "center")
YAW_TURN = 0.25  # signed yaw is threshold se zyada => ghuma hua
YAW_CENTER = 0.12
SAME_PERSON_MIN_SIM = 0.5
CHALLENGE_TTL_S = 60
TOKEN_TTL_S = 120


def signed_yaw(kps: np.ndarray) -> float:
    """-1 (naak image ke left) .. 0 (frontal) .. +1 (right). quality.yaw_ratio ka signed version."""
    left_eye, right_eye, nose = kps[0], kps[1], kps[2]
    eye_dx = right_eye[0] - left_eye[0]
    if abs(eye_dx) < 1e-6:
        return 0.0
    pos = (nose[0] - left_eye[0]) / eye_dx  # 0.5 = centered
    return float(np.clip((pos - 0.5) * 2, -1.0, 1.0))


def step_satisfied(step: str, yaw: float) -> bool:
    if step == "turn_left":
        return yaw <= -YAW_TURN
    if step == "turn_right":
        return yaw >= YAW_TURN
    return abs(yaw) <= YAW_CENTER


@dataclass
class Challenge:
    id: str
    steps: list[str]
    expires_at: float
    used: bool = False


@dataclass
class VerifyResult:
    live: bool
    reason: str
    token: str | None = None
    embedding: np.ndarray | None = field(default=None, repr=False)


class ChallengeStore:
    """In-memory (single process). Multi-replica deploy mein Redis mein rakho (Phase E)."""

    def __init__(self, n_steps: int = 2, clock=time.monotonic):
        self.n_steps = n_steps
        self.clock = clock
        self._challenges: dict[str, Challenge] = {}
        # token -> (expiry, verified face embedding). Login/attendance isi face se hota hai,
        # taaki liveness ek insaan kare aur login doosra na kar sake.
        self._tokens: dict[str, tuple[float, np.ndarray]] = {}
        self._lock = threading.Lock()

    def _gc(self) -> None:
        now = self.clock()
        self._challenges = {k: c for k, c in self._challenges.items() if c.expires_at > now}
        self._tokens = {k: t for k, t in self._tokens.items() if t[0] > now}

    def create(self) -> Challenge:
        rng = secrets.SystemRandom()
        # Hamesha kam se kam ek turn; consecutive same step nahi
        steps = [rng.choice(STEPS[:2])]
        while len(steps) < self.n_steps:
            steps.append(rng.choice([s for s in STEPS if s != steps[-1]]))
        c = Challenge(secrets.token_urlsafe(16), steps, self.clock() + CHALLENGE_TTL_S)
        with self._lock:
            self._gc()
            self._challenges[c.id] = c
        return c

    def verify(self, challenge_id: str, frames_faces: list[list]) -> VerifyResult:
        """frames_faces: har frame ke detected faces (embedding ke saath), steps ke order mein."""
        with self._lock:
            self._gc()
            c = self._challenges.get(challenge_id)
            if c is None:
                return VerifyResult(False, "unknown or expired challenge")
            if c.used:
                return VerifyResult(False, "challenge already used")
            c.used = True  # pass ho ya fail, dobara use nahi (brute-force retries band)
        if len(frames_faces) != len(c.steps):
            return VerifyResult(False, f"expected {len(c.steps)} frames, got {len(frames_faces)}")
        embs = []
        for i, (step, faces) in enumerate(zip(c.steps, frames_faces, strict=True)):
            if len(faces) != 1:
                return VerifyResult(False, f"frame {i + 1}: expected exactly one face")
            if not step_satisfied(step, signed_yaw(faces[0].kps)):
                return VerifyResult(False, f"frame {i + 1}: '{step}' not performed")
            embs.append(faces[0].embedding)
        e = np.stack(embs)
        sims = e @ e.T
        if sims.min() < SAME_PERSON_MIN_SIM:
            return VerifyResult(False, "different faces across frames")
        token = secrets.token_urlsafe(24)
        mean = e.mean(0)
        mean = mean / np.linalg.norm(mean)
        with self._lock:
            self._tokens[token] = (self.clock() + TOKEN_TTL_S, mean)
        return VerifyResult(True, "ok", token, mean)

    def consume_token(self, token: str | None) -> np.ndarray | None:
        """Liveness token ek hi baar use. Return: us live face ki embedding (ya None)."""
        if not token:
            return None
        with self._lock:
            self._gc()
            entry = self._tokens.pop(token, None)
        return None if entry is None else entry[1]
