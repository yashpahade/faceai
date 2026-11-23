"""
Drift detection: kya production mein aa raha data waisa hi hai jaisa pehle tha?

Model ki accuracy production mein seedha nahi naap sakte, kyunki labels nahi hote (kaun sach mein
kaun tha?). Par INPUTS aur OUTPUTS ki distribution naap sakte hain. Achanak badli => kuch hua hai:
- `brightness` / `face_px` girne lage: naya camera, kam roshni, door se photos (input drift)
- `det_score` gira: blurry/occluded faces
- `top1_similarity` gira, unknown rate badha: model ab users ko pehchaan nahi pa raha (output drift)

PSI (Population Stability Index) dono distributions ki tulna ek number mein karta hai:
    PSI = sum_bins (cur% - ref%) * ln(cur% / ref%)
    < 0.1 stable   |   0.1 - 0.25 thoda shift, nazar rakho   |   > 0.25 badi drift, investigate karo

Reference = deploy ke baad ke pehle `reference_size` observations (jab sab theek tha), disk pe save,
taaki restart pe reset na ho. Current = sabse naye `window_size` observations (rolling).
Reference reset karna (e.g. jaan-boojh ke naya camera lagaya) = reference file delete karo.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Har feature ke fixed bins (reference aur current SAME bins pe compare hone chahiye)
FEATURES: dict[str, np.ndarray] = {
    "top1_similarity": np.linspace(-0.2, 1.0, 13),
    "det_score": np.linspace(0.5, 1.0, 11),
    "face_px": np.array([0, 40, 60, 80, 120, 160, 240, 320, 480, 10_000], float),
    "brightness": np.linspace(0, 255, 11),
}
EPS = 1e-4  # khaali bin pe ln(0) se bachne ke liye


def psi(reference: np.ndarray, current: np.ndarray, bins: np.ndarray) -> float:
    ref = np.histogram(np.clip(reference, bins[0], bins[-1]), bins)[0].astype(float)
    cur = np.histogram(np.clip(current, bins[0], bins[-1]), bins)[0].astype(float)
    ref = np.maximum(ref / max(ref.sum(), 1), EPS)
    cur = np.maximum(cur / max(cur.sum(), 1), EPS)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


class DriftMonitor:
    def __init__(
        self,
        reference_path: Path | None = None,
        reference_size: int = 500,
        window_size: int = 500,
        min_samples: int = 100,
    ):
        self.reference_path = reference_path
        self.reference_size = reference_size
        self.min_samples = min_samples
        self._lock = threading.Lock()
        self.reference: dict[str, list[float]] = {f: [] for f in FEATURES}
        self.window: dict[str, deque[float]] = {f: deque(maxlen=window_size) for f in FEATURES}
        self.frozen = False
        self._load()

    def _load(self) -> None:
        if self.reference_path and self.reference_path.exists():
            data = json.loads(self.reference_path.read_text(encoding="utf-8"))
            self.reference = {f: list(map(float, data.get(f, []))) for f in FEATURES}
            self.frozen = True
            logger.info("drift reference loaded from %s", self.reference_path)

    def _freeze(self) -> None:
        self.frozen = True
        if self.reference_path:
            self.reference_path.parent.mkdir(parents=True, exist_ok=True)
            self.reference_path.write_text(json.dumps(self.reference), encoding="utf-8")
        logger.info("drift reference frozen (%d samples)", self.reference_size)

    def observe(self, feature: str, value: float) -> None:
        with self._lock:
            if not self.frozen:
                ref = self.reference[feature]
                if len(ref) < self.reference_size:
                    ref.append(float(value))
                if all(len(v) >= self.reference_size for v in self.reference.values()):
                    self._freeze()
                return
            self.window[feature].append(float(value))

    def scores(self) -> dict[str, float | None]:
        """feature -> PSI (None = abhi data kam hai)."""
        with self._lock:
            out: dict[str, float | None] = {}
            for f, bins in FEATURES.items():
                cur, ref = self.window[f], self.reference[f]
                if not self.frozen or len(cur) < self.min_samples or len(ref) < self.min_samples:
                    out[f] = None
                else:
                    out[f] = round(psi(np.array(ref), np.array(cur), bins), 4)
            return out
