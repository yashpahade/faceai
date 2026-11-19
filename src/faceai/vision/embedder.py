"""
ArcFace recognizer (InsightFace `w600k_r50.onnx`: ResNet-50 trained on WebFace600K).

Aligned 112x112 face -> 512 numbers ka vector (embedding).
Training ka goal (ArcFace loss): same person ke vectors paas-paas, alag log door,
*angle* ke hisaab se.
Isliye hum vectors ko L2-normalize karte hain (length = 1). Tab:
    cosine_similarity(a, b) = a . b   (dot product)   range -1..1
Same person typically ~0.5+, alag log ~0.0-0.2.
Exact cut-off (threshold) Phase 2 mein data se nikalenge.
"""

import cv2
import numpy as np
import onnxruntime as ort

from faceai.vision.align import ARCFACE_SIZE


class ArcFaceEmbedder:
    def __init__(self, session: ort.InferenceSession):
        self.session = session
        self.input_name = session.get_inputs()[0].name
        self.dim = int(session.get_outputs()[0].shape[-1])

    def embed(self, aligned_faces_bgr: list[np.ndarray]) -> np.ndarray:
        """Batch of aligned faces -> (N, dim) L2-normalized float32. Ek call = ek GPU pass."""
        if not aligned_faces_bgr:
            return np.empty((0, self.dim), dtype=np.float32)
        blob = cv2.dnn.blobFromImages(
            aligned_faces_bgr,
            1.0 / 127.5,
            (ARCFACE_SIZE, ARCFACE_SIZE),
            (127.5, 127.5, 127.5),
            swapRB=True,
        )
        emb = self.session.run(None, {self.input_name: blob})[0].astype(np.float32)
        return emb / np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-12)
