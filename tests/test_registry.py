"""Model registry flow on a throwaway MLflow DB: log -> candidate -> promote -> pull."""

import json

import pytest
import yaml

pytest.importorskip("mlflow")

from faceai import registry  # noqa: E402
from faceai.models.card import load_card  # noqa: E402

PARAMS = {
    "eval": {"det_size": 640, "det_threshold": 0.5, "target_fars": [0.001], "operating_far": 0.001},
    "gate": {
        "min_kfold_accuracy": 0.99,
        "min_tar_at_far": {"1e-3": 0.97},
        "max_failure_to_detect_rate": 0.01,
    },
}


def _metrics(tar=0.99, acc=0.996):
    return {
        "model_id": "pack/rec",
        "dataset": "lfw-6000-pairs",
        "n_pairs": 6000,
        "kfold_accuracy": acc,
        "failure_to_detect_rate": 0.001,
        "tar_at_far": {"1e-3": {"tar": tar, "threshold": 0.25}},
        "recommended_threshold": {"far": 0.001, "threshold": 0.25, "tar": tar},
        "device": "cpu",
    }


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """Workspace: chdir (mlruns/ yahin bane), fake model pack, params, metrics."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    pack = tmp_path / "models" / "pack"
    pack.mkdir(parents=True)
    (pack / "det.onnx").write_bytes(b"detector-weights")
    (pack / "rec.onnx").write_bytes(b"recognizer-weights-v1")
    (tmp_path / "params.yaml").write_text(yaml.safe_dump(PARAMS))
    (tmp_path / "reports").mkdir()
    return tmp_path, pack


def _log(ws, **metric_kw):
    root, pack = ws
    m = root / "reports" / "metrics.json"
    m.write_text(json.dumps(_metrics(**metric_kw)))
    return registry.log_evaluation(m, root / "params.yaml", pack, lock_path=root / "dvc.lock")


def test_flatten_metrics():
    flat = registry.flatten_metrics(_metrics())
    assert flat["tar_at_far_1e-3"] == 0.99
    assert flat["threshold_at_far_1e-3"] == 0.25
    assert flat["recommended_threshold"] == 0.25
    assert "model_id" not in flat


def test_log_creates_candidate_and_dedupes_same_weights(ws):
    r1 = _log(ws)
    assert r1["created"] and r1["version"] == "1" and r1["gate_failures"] == []
    # same weights, re-evaluated -> no new version (180 MB copy nahi hota)
    r2 = _log(ws)
    assert not r2["created"] and r2["version"] == "1"
    rows = registry.list_versions()
    assert [r["aliases"] for r in rows] == [["candidate"]]


def test_promote_then_pull_roundtrip(ws):
    root, pack = ws
    _log(ws)
    assert registry.promote() == "1"
    dest = root / "serving"
    card = registry.pull("champion", dest)
    assert card["version"] == "1"
    assert (dest / "rec.onnx").read_bytes() == b"recognizer-weights-v1"
    served = load_card(dest)  # serving side verifies sha256
    assert served["version"] == "1" and served["alias"] == "champion"


def test_promote_refuses_gate_failure(ws):
    _log(ws, tar=0.5)
    with pytest.raises(ValueError, match="quality gate"):
        registry.promote()


def test_promote_refuses_regression_vs_champion(ws):
    root, pack = ws
    _log(ws, tar=0.995)
    registry.promote()
    (pack / "rec.onnx").write_bytes(b"recognizer-weights-v2")  # naya model, thoda kharab
    r = _log(ws, tar=0.98)
    assert r["created"] and r["version"] == "2"
    with pytest.raises(ValueError, match="worse than champion"):
        registry.promote()
    assert registry.promote(force=True) == "2"  # human override, explicitly


def test_load_card_detects_tampered_file(ws):
    root, pack = ws
    _log(ws)
    registry.promote()
    dest = root / "serving"
    registry.pull("champion", dest)
    (dest / "rec.onnx").write_bytes(b"something else")
    with pytest.raises(RuntimeError, match="does not match"):
        load_card(dest)
