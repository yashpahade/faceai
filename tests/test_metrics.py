import numpy as np
import pytest

from faceai.eval.metrics import (
    auc,
    best_accuracy_threshold,
    eer,
    kfold_accuracy,
    roc_curve,
    tar_at_far,
)


def test_perfect_separation():
    scores = np.array([0.9, 0.8, 0.7, 0.2, 0.1, 0.0])
    labels = np.array([1, 1, 1, 0, 0, 0])
    roc = roc_curve(scores, labels)
    assert auc(roc) == pytest.approx(1.0)
    assert tar_at_far(roc, 0.0)[0] == 1.0
    assert eer(roc)[0] == 0.0
    acc, t = best_accuracy_threshold(scores, labels)
    assert acc == 1.0 and 0.2 < t <= 0.7


def test_random_scores_auc_near_half():
    rng = np.random.default_rng(0)
    scores = rng.random(20000)
    labels = rng.integers(0, 2, 20000)
    assert auc(roc_curve(scores, labels)) == pytest.approx(0.5, abs=0.02)


def test_tar_at_far_hand_computed():
    # 4 genuine, 4 impostor. Ek impostor (0.95) sabse upar.
    scores = np.array([0.9, 0.8, 0.6, 0.3, 0.95, 0.5, 0.2, 0.1])
    labels = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    roc = roc_curve(scores, labels)
    # FAR=0 -> threshold 0.95 se upar hona chahiye -> koi genuine accept nahi
    assert tar_at_far(roc, 0.0)[0] == 0.0
    # FAR<=0.25 (1 impostor allowed) -> 0.95 ke baad 0.9,0.8,0.6 accept, 0.5 (impostor) se pehle
    tar, thr = tar_at_far(roc, 0.25)
    assert tar == 0.75 and thr == pytest.approx(0.6)


def test_ties_handled():
    scores = np.array([0.5, 0.5, 0.5, 0.5])
    labels = np.array([1, 0, 1, 0])
    roc = roc_curve(scores, labels)
    np.testing.assert_allclose(roc.far, [0, 1])
    np.testing.assert_allclose(roc.tar, [0, 1])


def test_kfold_threshold_not_tuned_on_test_fold():
    rng = np.random.default_rng(1)
    labels = np.tile([1, 0], 500)
    scores = np.where(labels == 1, rng.normal(0.6, 0.1, 1000), rng.normal(0.1, 0.1, 1000))
    folds = np.repeat(np.arange(10), 100)
    mean, std, thrs = kfold_accuracy(scores, labels, folds)
    assert mean > 0.98 and len(thrs) == 10
    assert all(0.2 < t < 0.5 for t in thrs)


def test_requires_both_classes():
    with pytest.raises(ValueError):
        roc_curve(np.array([0.1, 0.2]), np.array([1, 1]))
