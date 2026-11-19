"""
Face alignment - recognition accuracy ka sabse underrated step.

ArcFace ko training ke time har face aise dikhaya gaya tha ki dono aankhein, naak, honth
112x112 image mein FIXED positions (ARCFACE_TEMPLATE) pe hon.
Inference pe bhi wahi karna zaroori hai,
warna embedding galat aati hai. Legacy code bbox crop + resize karta tha -> tilted/offset faces ->
kharab embeddings.

Hum 5 detected landmarks -> template pe ek "similarity transform" (rotation + uniform scale +
translation) fit karte hain (Umeyama algorithm, least squares), phir warpAffine.
"""

import cv2
import numpy as np

ARCFACE_SIZE = 112
ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],  # left eye
        [73.5318, 51.5014],  # right eye
        [56.0252, 71.7366],  # nose tip
        [41.5493, 92.3655],  # mouth left
        [70.7299, 92.2041],  # mouth right
    ],
    dtype=np.float32,
)


def umeyama_similarity(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """
    src points ko dst pe map karne wala best similarity transform (2x3 matrix).
    Umeyama (1991): dono point sets ko center karo, covariance ka SVD, usse rotation + scale.
    """
    src = src.astype(np.float64)
    dst = dst.astype(np.float64)
    n = src.shape[0]
    src_mean, dst_mean = src.mean(0), dst.mean(0)
    src_c, dst_c = src - src_mean, dst - dst_mean

    cov = dst_c.T @ src_c / n
    u, s, vt = np.linalg.svd(cov)
    d = np.ones(2)
    if np.linalg.det(cov) < 0:  # reflection se bachao (mirror image nahi chahiye)
        d[-1] = -1
    rot = u @ np.diag(d) @ vt
    var_src = (src_c**2).sum() / n
    scale = (s * d).sum() / var_src
    trans = dst_mean - scale * rot @ src_mean

    m = np.zeros((2, 3), dtype=np.float32)
    m[:, :2] = scale * rot
    m[:, 2] = trans
    return m


def align_face(image_bgr: np.ndarray, kps: np.ndarray) -> np.ndarray:
    """5 landmarks -> 112x112 aligned face crop (BGR)."""
    m = umeyama_similarity(kps, ARCFACE_TEMPLATE)
    return cv2.warpAffine(image_bgr, m, (ARCFACE_SIZE, ARCFACE_SIZE), borderValue=0.0)
