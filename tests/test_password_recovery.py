"""Forgot password (face), change password, admin temporary password."""

from faceai.serving.ratelimit import DEFAULT_RULES, RateLimiter
from tests.test_attendance import _admin, _live_token, _png

GENERIC = "could not verify it's you"


def _student(c, email: str, face: int | None) -> dict:
    body = {"email": email, "password": "oldpass123", "full_name": "Stu Dent", "consent": True}
    t = c.post("/v1/auth/signup", json=body).json()
    h = {"Authorization": f"Bearer {t['access_token']}"}
    if face is not None:
        assert c.post("/v1/me/face", files={"file": _png(face)}, headers=h).status_code == 201
    return {"id": t["user"]["id"], "email": email, "h": h}


def _login(c, email, password) -> int:
    return c.post("/v1/auth/login", json={"email": email, "password": password}).status_code


def _reset(c, email, face, password="newpass456"):
    tok = _live_token(c, face)
    body = {"email": email, "liveness_token": tok, "password": password}
    return c.post("/v1/auth/reset-password/face", json=body)


# ---------- forgot password via face ----------
def test_face_reset_sets_password_logs_in_and_kills_old_sessions(app_client):
    c = app_client
    a = _student(c, "a@x.in", 42)
    r = _reset(c, "A@X.in ", 42)  # email case/space tolerant
    assert r.status_code == 200, r.text
    new_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert c.get("/v1/me", headers=new_h).status_code == 200  # reset = logged in
    assert c.get("/v1/me", headers=a["h"]).status_code == 401  # purana session band
    assert _login(c, "a@x.in", "oldpass123") == 401
    assert _login(c, "a@x.in", "newpass456") == 200


def test_face_reset_rejects_someone_elses_face(app_client):
    c = app_client
    _student(c, "a@x.in", 42)
    _student(c, "b@x.in", 7)
    r = _reset(c, "a@x.in", 7)  # B ka chehra, A ka email
    assert r.status_code == 401 and r.json()["detail"] == GENERIC
    assert _login(c, "a@x.in", "oldpass123") == 200  # A ka password nahi badla


def test_face_reset_same_error_for_unknown_email_and_unenrolled(app_client):
    c = app_client
    _student(c, "a@x.in", 42)
    _student(c, "noface@x.in", None)
    for email, face in [("nobody@x.in", 42), ("noface@x.in", 42)]:
        r = _reset(c, email, face)
        assert r.status_code == 401 and r.json()["detail"] == GENERIC  # enumeration leak nahi
    assert _login(c, "noface@x.in", "oldpass123") == 200


def test_face_reset_validates_password_and_token(app_client):
    c = app_client
    _student(c, "a@x.in", 42)
    assert _reset(c, "a@x.in", 42, password="short").status_code == 422
    assert _reset(c, "a@x.in", 42, password="onlyletters").status_code == 422
    tok = _live_token(c, 42)
    body = {"email": "a@x.in", "liveness_token": tok, "password": "newpass456"}
    assert c.post("/v1/auth/reset-password/face", json=body).status_code == 200
    assert c.post("/v1/auth/reset-password/face", json=body).status_code == 401  # single-use


def test_reset_endpoint_is_rate_limited():
    rule = RateLimiter(DEFAULT_RULES).rule_for("/v1/auth/reset-password/face")
    assert rule is not None and rule.per_minute <= 5


# ---------- change password (logged in) ----------
def test_change_password(app_client):
    c = app_client
    a = _student(c, "a@x.in", None)
    bad = c.post(
        "/v1/me/password",
        json={"current_password": "wrong", "password": "newpass456"},
        headers=a["h"],
    )
    assert bad.status_code == 400  # 401 nahi: frontend 401 pe logout kar deta
    assert c.get("/v1/me", headers=a["h"]).status_code == 200  # galat input se session nahi gaya
    r = c.post(
        "/v1/me/password",
        json={"current_password": "oldpass123", "password": "newpass456"},
        headers=a["h"],
    )
    assert r.status_code == 200
    assert c.get("/v1/me", headers=a["h"]).status_code == 401  # purana token band
    new_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert c.get("/v1/me", headers=new_h).status_code == 200  # is device pe logged-in
    assert _login(c, "a@x.in", "newpass456") == 200
    weak = c.post(
        "/v1/me/password", json={"current_password": "newpass456", "password": "x"}, headers=new_h
    )
    assert weak.status_code == 422


# ---------- admin temporary password ----------
def test_admin_reset_gives_working_temp_password(app_client):
    c = app_client
    h = _admin(c)
    a = _student(c, "a@x.in", None)
    r = c.post(f"/v1/admin/students/{a['id']}/reset-password", headers=h)
    assert r.status_code == 200
    temp = r.json()["temporary_password"]
    assert _login(c, "a@x.in", temp) == 200
    assert _login(c, "a@x.in", "oldpass123") == 401
    assert c.get("/v1/me", headers=a["h"]).status_code == 401


def test_admin_reset_permissions(app_client):
    c = app_client
    h = _admin(c)
    a = _student(c, "a@x.in", None)
    b = _student(c, "b@x.in", None)
    # student kisi aur ka reset nahi kar sakta
    assert c.post(f"/v1/admin/students/{b['id']}/reset-password", headers=a["h"]).status_code == 403
    assert c.post("/v1/admin/students/nope/reset-password", headers=h).status_code == 404
    admin_id = c.get("/v1/me", headers=h).json()["id"]
    assert c.post(f"/v1/admin/students/{admin_id}/reset-password", headers=h).status_code == 403
