"""Phase 7: encryption at rest, API keys, audit log, consent, deletion, retention, liveness."""

import base64
import os
import sqlite3
from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from faceai.api.app import create_app
from faceai.security.auth import hash_key, verify
from faceai.security.crypto import Cipher, DecryptionError, parse_keys
from faceai.security.liveness import LivenessResult
from faceai.store.db import Database
from tests.fakes import FakeEngine, make_image

KEY1 = base64.b64encode(os.urandom(32)).decode()
KEY2 = base64.b64encode(os.urandom(32)).decode()


def _png(value: int) -> dict:
    ok, buf = cv2.imencode(".png", make_image(value))
    return {"file": ("f.png", buf.tobytes(), "image/png")}


# ---------- crypto ----------
def test_cipher_roundtrip_and_aad_binding():
    c = Cipher(parse_keys(KEY1))
    blob = c.encrypt(b"vector-bytes", b"person-a|model")
    assert b"vector-bytes" not in blob
    assert c.decrypt(blob, b"person-a|model") == b"vector-bytes"
    # A ki embedding B ki row mein chipkao -> fail
    with pytest.raises(DecryptionError):
        c.decrypt(blob, b"person-b|model")
    # ek bit badlo -> fail (GCM integrity)
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(DecryptionError):
        c.decrypt(tampered, b"person-a|model")


def test_key_rotation_old_key_still_decrypts():
    old = Cipher(parse_keys(f"1:{KEY1}"))
    blob = old.encrypt(b"x", b"aad")
    rotated = Cipher(parse_keys(f"2:{KEY2},1:{KEY1}"))
    assert rotated.active_id == 2
    assert rotated.decrypt(blob, b"aad") == b"x"
    assert rotated.key_id(rotated.encrypt(b"x", b"aad")) == 2


def test_bad_key_length_rejected():
    with pytest.raises(ValueError, match="32 bytes"):
        parse_keys(base64.b64encode(b"short").decode())


# ---------- DB: encryption at rest ----------
def test_db_stores_ciphertext_not_vectors(tmp_path):
    db = Database(tmp_path / "f.db", cipher=Cipher(parse_keys(KEY1)))
    p = db.create_person("A", consent=True)
    vec = np.arange(8, dtype=np.float32)
    db.add_embedding(p.id, "m", vec, 0.9, 50.0)
    raw = sqlite3.connect(tmp_path / "f.db").execute("SELECT vector FROM embeddings").fetchone()[0]
    assert raw[:2] == b"E1" and vec.tobytes() not in raw
    _, _, vecs = db.load_embeddings("m")
    np.testing.assert_array_equal(vecs[0], vec)


def test_migrate_encrypts_legacy_plaintext_rows(tmp_path):
    plain = Database(tmp_path / "f.db")
    p = plain.create_person("A", consent=True)
    vec = np.ones(8, np.float32)
    plain.add_embedding(p.id, "m", vec, 0.9, 50.0)
    plain.close()
    db = Database(tmp_path / "f.db", cipher=Cipher(parse_keys(KEY1)))
    assert db.count_unencrypted() == 1
    assert db.reencrypt_all() == 1
    assert db.count_unencrypted() == 0
    np.testing.assert_array_equal(db.load_embeddings("m")[2][0], vec)


# ---------- auth ----------
def test_verify_key():
    assert verify("secret", [hash_key("secret")]) == f"key:{hash_key('secret')[:8]}"
    assert verify("wrong", [hash_key("secret")]) is None
    assert verify(None, [hash_key("secret")]) is None


@pytest.fixture
def secure_client(settings):
    s = settings.model_copy(
        update={"api_key_hashes": hash_key("k1"), "auth": "required", "encryption_keys": KEY1}
    )
    with TestClient(create_app(s, engine=FakeEngine())) as c:
        yield c


def test_api_requires_key(secure_client):
    assert secure_client.get("/v1/persons").status_code == 401
    assert secure_client.get("/v1/persons", headers={"X-API-Key": "bad"}).status_code == 401
    assert secure_client.get("/v1/persons", headers={"X-API-Key": "k1"}).status_code == 200
    # health/metrics probes ko key nahi chahiye (load balancer, Prometheus)
    assert secure_client.get("/health/live").status_code == 200


def test_prod_refuses_to_start_without_key_or_encryption(settings):
    s = settings.model_copy(update={"env": "prod"})
    with TestClient(create_app(s, engine=FakeEngine())) as c:
        assert c.get("/health/ready").status_code == 503


# ---------- consent, audit, deletion ----------
def test_consent_is_required(client):
    assert client.post("/v1/persons", json={"name": "A"}).status_code == 422
    assert client.post("/v1/persons", json={"name": "A", "consent": False}).status_code == 422
    r = client.post("/v1/persons", json={"name": "A", "consent": True})
    assert r.status_code == 201 and r.json()["consent_at"]


def test_audit_trail_survives_deletion_without_biometrics(secure_client):
    h = {"X-API-Key": "k1"}
    pid = secure_client.post("/v1/persons", json={"name": "A", "consent": True}, headers=h).json()[
        "id"
    ]
    secure_client.post(f"/v1/persons/{pid}/faces", files=_png(42), headers=h)
    r = secure_client.delete(f"/v1/persons/{pid}", headers=h)
    assert r.status_code == 200
    assert r.json() == {"person_id": pid, "deleted_embeddings": 1}

    events = secure_client.get(f"/v1/audit?person_id={pid}", headers=h).json()
    assert [e["action"] for e in events] == ["person.create", "face.enroll", "person.delete"]
    assert all(e["actor"] == f"key:{hash_key('k1')[:8]}" for e in events)
    # naam/vector audit mein nahi (audit log khud PII ka store na bane)
    assert "A" not in str([e["detail"] for e in events])
    # aur recognize ab match nahi karta
    r = secure_client.post("/v1/recognize", files=_png(42), headers=h).json()
    assert r["faces"][0]["match"] is None


def test_secure_delete_pragma_on(tmp_path):
    db = Database(tmp_path / "f.db")
    assert db._conn.execute("PRAGMA secure_delete").fetchone()[0] == 1


def test_retention_purges_old_embeddings(tmp_path):
    db = Database(tmp_path / "f.db")
    p = db.create_person("A", consent=True)
    old = db.add_embedding(p.id, "m", np.ones(4, np.float32), 0.9, 50.0)
    new = db.add_embedding(p.id, "m", np.ones(4, np.float32), 0.9, 50.0)
    past = (datetime.now(UTC) - timedelta(days=400)).isoformat(timespec="seconds")
    db._conn.execute("UPDATE embeddings SET created_at = ? WHERE id = ?", (past, old))
    assert db.purge_embeddings_older_than(365) == [old]
    assert db.load_embeddings("m")[0].tolist() == [new]


# ---------- liveness ----------
class FakeLiveness:
    name = "fake"

    def check(self, image_bgr, bbox):
        live = int(image_bgr[0, 0, 0]) != 99  # value 99 = "printed photo"
        return LivenessResult(live=live, score=0.9 if live else 0.1, method=self.name)


def test_liveness_required_without_checker_is_not_ready(settings):
    s = settings.model_copy(update={"liveness": "required"})
    with TestClient(create_app(s, engine=FakeEngine())) as c:
        assert c.get("/health/ready").status_code == 503


def test_liveness_blocks_spoof(settings):
    s = settings.model_copy(update={"liveness": "required"})
    with TestClient(create_app(s, engine=FakeEngine(), liveness=FakeLiveness())) as c:
        pid = c.post("/v1/persons", json={"name": "A", "consent": True}).json()["id"]
        r = c.post(f"/v1/persons/{pid}/faces", files=_png(99))
        assert r.status_code == 422 and "liveness" in r.json()["detail"]["message"]
        assert c.post(f"/v1/persons/{pid}/faces", files=_png(42)).status_code == 201
        face = c.post("/v1/recognize", files=_png(42)).json()["faces"][0]
        assert face["liveness"]["live"] is True and face["match"]["person_id"] == pid
