"""Pure-math tests for the vision building blocks (no model files needed)."""

import numpy as np
import pytest

from faceai.vision.align import ARCFACE_TEMPLATE, align_face, umeyama_similarity
from faceai.vision.detector import _nms
from faceai.vision.quality import sharpness, yaw_ratio


def _apply(m: np.ndarray, pts: np.ndarray) -> np.ndarray:
    return pts @ m[:, :2].T + m[:, 2]


def test_umeyama_recovers_known_similarity_transform():
    # template ko rotate(20deg) + scale(2.5) + shift karke "detected landmarks" banao
    a = np.deg2rad(20)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    src = (ARCFACE_TEMPLATE @ rot.T) * 2.5 + np.array([300, 150])
    m = umeyama_similarity(src, ARCFACE_TEMPLATE)
    np.testing.assert_allclose(_apply(m, src), ARCFACE_TEMPLATE, atol=1e-3)


def test_umeyama_never_mirrors_face():
    src = ARCFACE_TEMPLATE * 2 + 10
    m = umeyama_similarity(src, ARCFACE_TEMPLATE)
    assert np.linalg.det(m[:, :2]) > 0  # positive determinant = no reflection


def test_align_face_output_shape():
    img = np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8)
    out = align_face(img, ARCFACE_TEMPLATE * 3 + 50)
    assert out.shape == (112, 112, 3)


def test_nms_removes_overlapping_duplicates():
    boxes = np.array([[0, 0, 100, 100], [5, 5, 105, 105], [300, 300, 400, 400]], np.float32)
    scores = np.array([0.9, 0.8, 0.7], np.float32)
    assert _nms(boxes, scores, 0.4) == [0, 2]


@pytest.mark.parametrize("nose_x,expected_frontal", [(50, True), (68, False)])
def test_yaw_ratio(nose_x, expected_frontal):
    kps = np.array([[30, 50], [70, 50], [nose_x, 70], [35, 90], [65, 90]], np.float32)
    assert (yaw_ratio(kps) < 0.6) == expected_frontal


def test_sharpness_blurry_vs_sharp():
    flat = np.full((112, 112, 3), 128, np.uint8)
    noisy = np.random.default_rng(0).integers(0, 255, (112, 112, 3), dtype=np.uint8)
    assert sharpness(flat) < 1 < sharpness(noisy)
