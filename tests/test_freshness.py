from faceai.eval.freshness import stale_deps


def test_code_change_is_stale():
    status = {"evaluate_lfw": [{"changed deps": {"src\\faceai\\eval\\metrics.py": "modified"}}]}
    assert stale_deps(status) == ["evaluate_lfw: src/faceai/eval/metrics.py (modified)"]


def test_params_change_is_stale():
    status = {"embed_lfw": [{"changed deps": {"params.yaml": "modified"}}]}
    assert stale_deps(status) == ["embed_lfw: params.yaml (modified)"]


def test_missing_data_and_models_in_ci_are_ignored():
    status = {
        "embed_lfw": [
            {"changed deps": {"data/lfw": "deleted", "models/buffalo_l": "deleted"}},
            {"changed outs": {"data/eval/lfw_embeddings.npz": "deleted"}},
        ]
    }
    assert stale_deps(status) == []


def test_clean_status():
    assert stale_deps({}) == []
