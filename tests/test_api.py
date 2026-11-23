from faceai import __version__


def test_liveness(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_readiness(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_readiness_returns_503_when_not_ready(client):
    client.app.state.ready = False
    r = client.get("/health/ready")
    assert r.status_code == 503


def test_version(client):
    r = client.get("/version")
    assert r.json() == {
        "app_version": __version__,
        "env": "test",
        "model_id": "fake/v1",
        "device": "cpu",
        "model_version": None,  # no model_card.json -> unregistered model
        "model_alias": None,
        "match_threshold": 0.4,
        "recommended_threshold": None,
    }


def test_request_id_is_generated(client):
    r = client.get("/health/live")
    assert len(r.headers["X-Request-ID"]) == 12


def test_request_id_is_propagated(client):
    r = client.get("/health/live", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
