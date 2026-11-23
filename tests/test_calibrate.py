import numpy as np

from faceai.eval.calibrate import build_pairs, calibrate


def test_build_pairs_genuine_and_impostor():
    labels = ["a", "a", "a", "b", "b", "c"]
    i1, i2, same = build_pairs(labels)
    assert same.sum() == 3 + 1  # a: 3 pairs, b: 1 pair
    for x, y, s in zip(i1, i2, same, strict=True):
        assert (labels[x] == labels[y]) == bool(s)
    assert len({(x, y) for x, y in zip(i1, i2, strict=True)}) == len(i1)  # no duplicates


def test_calibrate_finds_threshold_between_classes():
    rng = np.random.default_rng(0)
    people = 40
    centers = rng.standard_normal((people, 64))
    labels, embs = [], []
    for p in range(people):
        for _ in range(4):
            v = centers[p] + 0.3 * rng.standard_normal(64)
            embs.append(v / np.linalg.norm(v))
            labels.append(f"p{p}")
    embs = np.array(embs, np.float32)
    out = calibrate(embs, np.ones(len(labels), bool), labels, target_far=0.001)
    thr = out["recommended_threshold"]["threshold"]
    assert out["impostor_score_p99"] < thr <= out["genuine_score_p05"] + 0.2
    assert out["recommended_threshold"]["tar"] > 0.9
    assert out["warnings"] == []


def test_calibrate_warns_on_too_little_data():
    rng = np.random.default_rng(1)
    embs = rng.standard_normal((6, 8)).astype(np.float32)
    embs /= np.linalg.norm(embs, axis=1, keepdims=True)
    out = calibrate(embs, np.ones(6, bool), ["a", "a", "b", "b", "c", "c"], 0.001)
    assert any("cannot be measured" in w for w in out["warnings"])
    assert any("fewer than 10 people" in w for w in out["warnings"])
