"""
Fake face engine for tests: no ONNX, no GPU, deterministic.

Encoding convention for test images (np.full((H, W, 3), value)):
- value 0         -> no face
- width >= 400    -> two faces (both identity = value)
- value 255       -> one face but blurry (aligned crop is flat)
- otherwise       -> one face; identity (embedding) derived from `value`
"""

import numpy as np

from faceai.vision.types import DetectedFace

DIM = 64


def identity_vector(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).standard_normal(DIM).astype(np.float32)
    return v / np.linalg.norm(v)


def make_image(value: int, width: int = 200) -> np.ndarray:
    return np.full((200, width, 3), value, dtype=np.uint8)


def _face(value: int, x0: float) -> DetectedFace:
    rng = np.random.default_rng(value)
    sharp = rng.integers(0, 255, (112, 112, 3), dtype=np.uint8)
    flat = np.full((112, 112, 3), 128, np.uint8)
    kps = np.array(
        [[x0 + 30, 60], [x0 + 70, 60], [x0 + 50, 80], [x0 + 35, 100], [x0 + 65, 100]],
        dtype=np.float32,
    )
    return DetectedFace(
        bbox=np.array([x0, 20, x0 + 100, 140], np.float32),
        kps=kps,
        det_score=0.9,
        embedding=identity_vector(value),
        aligned=flat if value == 255 else sharp,
    )


class FakeEngine:
    model_id = "fake/v1"
    dim = DIM
    device = "cpu"

    def analyze(self, image_bgr: np.ndarray, det_threshold: float = 0.5) -> list[DetectedFace]:
        value = int(image_bgr[0, 0, 0])
        if value == 0:
            return []
        if image_bgr.shape[1] >= 400:
            return [_face(value, 0), _face(value, 200)]
        return [_face(value, 0)]
