"""
Liveness / presentation-attack detection (PAD): kya camera ke saamne ASLI insaan hai, ya photo,
phone screen, ya mask?

Bina iske face recognition ek "photo dikhao, andar aao" system hai. Kisi ki Instagram photo
print karke attendance lag jaati hai.

Do approaches:
- Passive: ek hi frame dekh ke model decide karta hai (texture, moire patterns, screen reflections).
  e.g. MiniFASNet (Silent-Face-Anti-Spoofing), ONNX mein ~2 MB.
- Active: user se kuch karwao (palak jhapkao, sir ghumao) aur video frames check karo. Zyada
  strong, par UX kharab aur client-side kaam chahiye.

Is repo mein KOI liveness model ship nahi hota: PAD model ko apne camera/attack types pe evaluate
kiye bina (APCER/BPCER metrics, ISO/IEC 30107-3) production mein lagana "security theatre" hai.
Isliye yahan sirf interface + wiring hai:
- `FACEAI_LIVENESS=off`      (default): check nahi hota, response mein `liveness: null`
- `FACEAI_LIVENESS=required`: checker configured nahi => app READY NAHI hogi (fail closed).
  Spoof mila => enroll 422, recognize mein us face ka match nahi diya jaata.
Apna model lagane ke liye `LivenessChecker` protocol implement karo aur `create_app(...,
liveness=...)` mein do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class LivenessResult:
    live: bool
    score: float  # 0..1, real hone ka confidence
    method: str


class LivenessChecker(Protocol):
    name: str

    def check(self, image_bgr: np.ndarray, bbox: np.ndarray) -> LivenessResult: ...
