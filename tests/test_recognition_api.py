"""End-to-end API flow with the fake engine: create -> enroll -> recognize -> delete."""

import cv2
import pytest
from fastapi.testclient import TestClient

from faceai.api.app import create_app
from tests.fakes import FakeEngine, make_image


def _png(value: int, width: int = 200) -> dict:
    ok, buf = cv2.imencode(".png", make_image(value, width))
    assert ok
    return {"file": ("face.png", buf.tobytes(), "image/png")}


@pytest.fixture
def person(client) -> dict:
    r = client.post("/v1/persons", json={"name": "Omkar", "consent": True})
    assert r.status_code == 201
    return r.json()


def test_full_flow(client, person):
    pid = person["id"]
    r = client.post(f"/v1/persons/{pid}/faces", files=_png(42))
    assert r.status_code == 201, r.text
    assert r.json()["quality"]["issues"] == []

    # same identity -> match
    r = client.post("/v1/recognize", files=_png(42)).json()
    assert r["faces"][0]["match"]["person_id"] == pid
    assert r["faces"][0]["match"]["similarity"] > 0.99
    assert r["model_id"] == "fake/v1"

    # different identity -> unknown
    r = client.post("/v1/recognize", files=_png(7)).json()
    assert r["faces"][0]["match"] is None

    assert client.get(f"/v1/persons/{pid}").json()["num_faces"] == 1

    # delete -> ab recognize nahi hona chahiye (right to be forgotten)
    assert client.delete(f"/v1/persons/{pid}").json() == {"person_id": pid, "deleted_embeddings": 1}
    r = client.post("/v1/recognize", files=_png(42)).json()
    assert r["faces"][0]["match"] is None
    assert client.get(f"/v1/persons/{pid}").status_code == 404


def test_index_rebuilt_from_db_after_restart(settings, client, person):
    client.post(f"/v1/persons/{person['id']}/faces", files=_png(42))
    # naya app, same data_dir -> "server restart"
    with TestClient(create_app(settings, engine=FakeEngine())) as c2:
        r = c2.post("/v1/recognize", files=_png(42)).json()
        assert r["faces"][0]["match"]["person_id"] == person["id"]


@pytest.mark.parametrize(
    "value,width,msg",
    [(0, 200, "no face"), (42, 400, "2 faces"), (255, 200, "blurry")],
)
def test_enroll_rejects_bad_images(client, person, value, width, msg):
    r = client.post(f"/v1/persons/{person['id']}/faces", files=_png(value, width))
    assert r.status_code == 422
    assert msg in r.json()["detail"]["message"]


def test_enroll_unknown_person_404(client):
    assert client.post("/v1/persons/nope/faces", files=_png(42)).status_code == 404


def test_recognize_rejects_non_image(client):
    r = client.post("/v1/recognize", files={"file": ("x.txt", b"not an image", "text/plain")})
    assert r.status_code == 400


def test_recognize_rejects_oversized(client):
    client.app.state.settings = client.app.state.settings.model_copy(update={"max_upload_mb": 1})
    big = {"file": ("big.png", b"0" * (1024 * 1024 + 10), "image/png")}
    assert client.post("/v1/recognize", files=big).status_code == 413


def test_create_person_validates_name(client):
    assert client.post("/v1/persons", json={"name": "", "consent": True}).status_code == 422


def test_not_ready_when_model_missing(settings, tmp_path):
    # asli engine, par models folder khaali -> app chalu, ready nahi
    s = settings.model_copy(update={"models_dir": tmp_path / "no-models"})
    with TestClient(create_app(s)) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/ready").status_code == 503
        assert c.post("/v1/recognize", files=_png(42)).status_code == 503
