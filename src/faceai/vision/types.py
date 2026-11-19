from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class DetectedFace:
    bbox: np.ndarray  # (4,) x1, y1, x2, y2 in original image pixels
    kps: np.ndarray  # (5, 2) landmarks: left eye, right eye, nose, mouth left, mouth right
    det_score: float
    embedding: np.ndarray | None = field(default=None, repr=False)  # (512,) L2-normalized
    aligned: np.ndarray | None = field(default=None, repr=False)  # (112, 112, 3) BGR crop

    @property
    def width(self) -> float:
        return float(self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return float(self.bbox[3] - self.bbox[1])


class FaceEngineProtocol(Protocol):
    """Service layer sirf is interface pe depend karti hai.

    Isliye tests mein fake engine de sakte hain.
    """

    model_id: str
    dim: int
    device: str

    def analyze(self, image_bgr: np.ndarray, det_threshold: float) -> list[DetectedFace]: ...
