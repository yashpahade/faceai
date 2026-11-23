"""
Image preprocessing before detection (Phase A).

1. EXIF orientation: phone camera photo ko "sideways" pixels ke saath save karta hai aur EXIF
   tag mein likhta hai "90 degree ghuma ke dikhao". Tag ignore kiya to detector ko lete hue chehre
   milte hain -> face miss. `decode_image` tag apply karta hai.
2. CLAHE (Contrast Limited Adaptive Histogram Equalization): andhere/uneven lighting mein local
   contrast badhata hai. Sirf LUMINANCE (LAB ka L channel) pe, taaki colors na bigdein.
   Optional hai: embeddings pe asar padta hai, isliye pehle LFW pe naapo
   (scripts/accuracy_experiments.py), phir on karo.
"""

import cv2
import numpy as np


def decode_image(data: bytes) -> np.ndarray | None:
    """Bytes -> BGR image, EXIF orientation applied (OpenCV IMREAD_COLOR yahi karta hai)."""
    # IMREAD_COLOR (bina IMREAD_IGNORE_ORIENTATION) JPEG ka EXIF Orientation tag apply karta hai.
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def apply_clahe(img_bgr: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return cv2.cvtColor(cv2.merge((clahe.apply(l_ch), a_ch, b_ch)), cv2.COLOR_LAB2BGR)
