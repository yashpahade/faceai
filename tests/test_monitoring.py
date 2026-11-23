"""Phase 6: /metrics + drift detection."""

import cv2
import numpy as np
import pytest

from faceai.monitoring.drift import FEATURES, DriftMonitor, psi
from tests.fakes import make_image


def _png(value: int) -> dict:
    ok, buf = cv2.imencode(".png", make_image(value))
    return {"file": ("f.png", buf.tobytes(), "image/png")}


def _metric(text: str, name: str) -> float:
    total = 0.0
    for line in text.splitlines():
        if line.startswith(name):
            total += float(line.rsplit(" ", 1)[1])
    return total


# ---------- PSI ----------
def test_psi_zero_for_same_distribution():
    rng = np.random.default_rng(0)
    a, b = rng.normal(0.5, 0.1, 5000), rng.normal(0.5, 0.1, 5000)
    assert psi(a, b, FEATURES["top1_similarity"]) < 0.02


def test_psi_large_for_shifted_distribution():
    rng = np.random.default_rng(0)
    ref, cur = rng.normal(0.6, 0.1, 5000), rng.normal(0.3, 0.1, 5000)
    assert psi(ref, cur, FEATURES["top1_similarity"]) > 0.25


# ---------- DriftMonitor ----------
def _feed(mon, n, sim, rng):
    for _ in range(n):
        mon.observe("top1_similarity", rng.normal(sim, 0.05))
        mon.observe("det_score", rng.uniform(0.8, 0.9))
        mon.observe("face_px", rng.uniform(100, 140))
        mon.observe("brightness", rng.uniform(100, 140))


def test_drift_monitor_reference_then_detects_shift(tmp_path):
    rng = np.random.default_rng(1)
    ref_path = tmp_path / "drift_reference.json"
    mon = DriftMonitor(ref_path, reference_size=200, window_size=200, min_samples=50)
    _feed(mon, 200, 0.6, rng)  # reference phase
    assert mon.frozen and ref_path.exists()
    assert mon.scores()["top1_similarity"] is None  # window abhi khaali

    _feed(mon, 200, 0.6, rng)  # same world
    assert mon.scores()["top1_similarity"] < 0.1

    _feed(mon, 200, 0.25, rng)  # users ab match nahi ho rahe
    assert mon.scores()["top1_similarity"] > 0.25
    assert mon.scores()["det_score"] < 0.1  # input wahi hai, output badla

    # restart: reference disk se aata hai, dobara seekhna nahi padta
    assert DriftMonitor(ref_path, reference_size=200).frozen


# ---------- /metrics ----------
def test_metrics_endpoint_exposes_red_and_model_metrics(client):
    pid = client.post("/v1/persons", json={"name": "A", "consent": True}).json()["id"]
    client.post(f"/v1/persons/{pid}/faces", files=_png(42))
    before = client.get("/metrics").text
    client.post("/v1/recognize", files=_png(42))  # match
    client.post("/v1/recognize", files=_png(7))  # unknown
    text = client.get("/metrics").text

    assert "faceai_ready 1.0" in text
    assert "faceai_persons 1.0" in text
    assert 'faceai_model_info{device="cpu",model_id="fake/v1",version="none"} 1.0' in text
    for result in ("match", "unknown"):
        name = f'faceai_recognitions_total{{result="{result}"}}'
        assert _metric(text, name) - _metric(before, name) == 1
    # route label = TEMPLATE, asli ID nahi (cardinality)
    assert 'route="/v1/persons/{person_id}/faces"' in text
    assert pid not in text


@pytest.mark.parametrize("path", ["/nope/123", "/nope/456"])
def test_unmatched_routes_share_one_label(client, path):
    client.get(path)
    text = client.get("/metrics").text
    assert "/nope/" not in text
    assert 'route="unmatched"' in text
