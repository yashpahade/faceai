"""
Enrollment quality gates.

"Garbage in, garbage out": database mein ek dhundhli/side-face photo enroll ho gayi to us insaan ki
har future recognition kharab hogi.
Isliye register karte waqt strict checks, recognize karte waqt nahi.
Thresholds abhi rough hain - Phase 2 mein data dekh ke tune karenge.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from faceai.vision.types import DetectedFace


@dataclass
class QualityReport:
    det_score: float
    face_px: float
    sharpness: float
    yaw_ratio: float  # 0 = frontal, ~1 = full profile
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def sharpness(aligned_bgr: np.ndarray) -> float:
    """Laplacian variance: edges kitne tez hain. Blurry image => kam value."""
    gray = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def yaw_ratio(kps: np.ndarray) -> float:
    """Naak dono aankhon ke beech kahan hai? Beech mein => frontal (0). Ek side => profile (~1)."""
    left_eye, right_eye, nose = kps[0], kps[1], kps[2]
    eye_dx = right_eye[0] - left_eye[0]
    if abs(eye_dx) < 1e-6:
        return 1.0
    pos = (nose[0] - left_eye[0]) / eye_dx  # 0.5 = centered
    return float(min(1.0, abs(pos - 0.5) * 2))


def assess(
    face: DetectedFace,
    aligned_bgr: np.ndarray,
    min_det_score: float,
    min_face_px: int,
    min_sharpness: float,
    max_yaw: float = 0.6,
) -> QualityReport:
    rep = QualityReport(
        det_score=face.det_score,
        face_px=min(face.width, face.height),
        sharpness=sharpness(aligned_bgr),
        yaw_ratio=yaw_ratio(face.kps),
    )
    if rep.det_score < min_det_score:
        rep.issues.append(f"low detection score ({rep.det_score:.2f} < {min_det_score})")
    if rep.face_px < min_face_px:
        rep.issues.append(f"face too small ({rep.face_px:.0f}px < {min_face_px}px)")
    if rep.sharpness < min_sharpness:
        rep.issues.append(f"image too blurry (sharpness {rep.sharpness:.0f} < {min_sharpness})")
    if rep.yaw_ratio > max_yaw:
        rep.issues.append("face not frontal enough (look at the camera)")
    return rep
