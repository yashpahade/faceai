from faceai.eval.gate import check

GATE = {
    "min_kfold_accuracy": 0.99,
    "min_tar_at_far": {"1e-3": 0.97},
    "max_failure_to_detect_rate": 0.01,
}


def _metrics(acc=0.998, tar=0.99, ftd=0.001):
    return {
        "kfold_accuracy": acc,
        "tar_at_far": {"1e-3": {"tar": tar, "threshold": 0.3}},
        "failure_to_detect_rate": ftd,
    }


def test_gate_passes_good_model():
    assert check(_metrics(), GATE) == []


def test_gate_fails_on_each_regression():
    assert any("kfold_accuracy" in f for f in check(_metrics(acc=0.95), GATE))
    assert any("TAR@FAR=1e-3" in f for f in check(_metrics(tar=0.90), GATE))
    assert any("failure_to_detect" in f for f in check(_metrics(ftd=0.05), GATE))


def test_gate_fails_when_metric_missing():
    m = _metrics()
    m["tar_at_far"] = {}
    assert check(m, GATE) == ["TAR@FAR=1e-3 missing from metrics"]
