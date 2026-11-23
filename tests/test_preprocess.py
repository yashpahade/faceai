"""Phase A: EXIF orientation, CLAHE, flip-TTA, multi-scale merge."""

import io

import numpy as np
import pytest

from faceai.vision.detector import merge_detections
from faceai.vision.preprocess import apply_clahe, decode_image
from faceai.vision.types import DetectedFace

PIL = pytest.importorskip("PIL.Image")


def _jpeg_with_orientation(w: int, h: int, orientation: int) -> bytes:
    img = PIL.new("RGB", (w, h), (200, 50, 50))
    exif = img.getexif()
    exif[0x0112] = orientation  # Orientation tag
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_decode_applies_exif_rotation():
    # Phone ne 400x200 pixels save kiye, tag 6 = "90 deg ghumao" -> dikhe 200 wide, 400 tall
    img = decode_image(_jpeg_with_orientation(400, 200, 6))
    assert img.shape[:2] == (400, 200)


def test_decode_rejects_garbage():
    assert decode_image(b"not an image") is None


def test_clahe_raises_contrast_keeps_shape():
    rng = np.random.default_rng(0)
    dark = (rng.random((120, 160, 3)) * 40).astype(np.uint8)  # low contrast, andhera
    out = apply_clahe(dark)
    assert out.shape == dark.shape and out.dtype == np.uint8
    assert out.std() > dark.std()


def _face(x0, score):
    return DetectedFace(
        bbox=np.array([x0, 0, x0 + 100, 100], np.float32),
        kps=np.zeros((5, 2), np.float32),
        det_score=score,
    )


def test_multiscale_merge_dedupes_same_face_keeps_best():
    merged = merge_detections([_face(0, 0.7), _face(2, 0.9), _face(300, 0.8)])
    assert [f.det_score for f in merged] == [0.9, 0.8]


class _Emb:
    def __init__(self):
        self.calls = []

    def __call__(self, crops):
        self.calls.append(len(crops))
        # "embedding" = mean pixel per channel; mirror ka mean same hota hai, isliye test
        # deterministic left/right asymmetric pattern use karta hai
        return np.stack(
            [c[:, :56].mean(axis=(0, 1)) - c[:, 56:].mean(axis=(0, 1)) + 1 for c in crops]
        )


def test_flip_tta_embeds_mirror_and_is_mirror_invariant():
    from faceai.vision.engine import FaceEngine

    eng = FaceEngine.__new__(FaceEngine)  # bina model files ke sirf embed logic test
    eng.flip_tta = True
    eng.embed_fn = _Emb()
    crop = np.zeros((112, 112, 3), np.uint8)
    crop[:, :56] = 200  # left half bright
    a = eng.embed_aligned([crop])
    b = eng.embed_aligned([crop[:, ::-1].copy()])
    assert eng.embed_fn.calls == [2, 2]  # har crop + uska mirror, ek hi batch
    np.testing.assert_allclose(a, b, atol=1e-6)
    np.testing.assert_allclose(np.linalg.norm(a, axis=1), 1.0, atol=1e-6)
