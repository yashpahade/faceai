"""Phase B: auth, RBAC, students, batches, attendance rules, face login, reports."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import cv2
import pytest

from faceai.attendance.models import User
from faceai.attendance.rules import class_over, decide
from faceai.attendance.security import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from tests.fakes import make_image

IST = ZoneInfo("Asia/Kolkata")


def _png(value: int) -> tuple:
    ok, buf = cv2.imencode(".png", make_image(value))
    return ("f.png", buf.tobytes(), "image/png")


# ---------- pure units ----------
def test_password_hash_roundtrip_and_salted():
    h1, h2 = hash_password("correct horse"), hash_password("correct horse")
    assert h1 != h2  # har hash ka apna salt
    assert verify_password("correct horse", h1)
    assert not verify_password("wrong", h1)
    assert not verify_password("x", "garbage")


def test_jwt_roundtrip_and_tamper():
    t = create_token("u1", "student", 0, "secret", 5, "pwd")
    assert decode_token(t, "secret")["sub"] == "u1"
    assert decode_token(t, "other-secret") is None
    expired = create_token("u1", "student", 0, "secret", -1, "pwd")
    assert decode_token(expired, "secret") is None


@pytest.mark.parametrize(
    "hhmm,expect",
    [
        ("08:40", (False, None)),  # window abhi khuli nahi (09:00 - 15 min)
        ("08:50", (True, "present")),
        ("09:10", (True, "present")),  # exactly late_after -> abhi present
        ("09:11", (True, "late")),
        ("10:01", (False, None)),  # class khatam
    ],
)
def test_rules_window_and_late(hhmm, expect):
    h, m = map(int, hhmm.split(":"))
    now = datetime(2026, 11, 23, h, m, tzinfo=IST)  # Monday
    d = decide(now, "09:00", "10:00", "0,1,2,3,4", 10, 15)
    assert (d.allowed, d.status) == expect


def test_rules_no_class_on_weekend():
    sunday = datetime(2026, 11, 29, 9, 5, tzinfo=IST)
    assert decide(sunday, "09:00", "10:00", "0,1,2,3,4", 10, 15).allowed is False


# ---------- API ----------
def _admin(c) -> dict:
    svc = c.app.state.attendance
    with svc.sessions.begin() as db:
        db.add(
            User(
                email="admin@x.in",
                full_name="Admin",
                password_hash=hash_password("adminpass123"),
                role="admin",
            )
        )
    t = c.post("/v1/auth/login", json={"email": "admin@x.in", "password": "adminpass123"}).json()
    return {"Authorization": f"Bearer {t['access_token']}"}


def _always_open_batch(c, h) -> str:
    # Har din, poore din khula -> test time pe depend nahi
    r = c.post(
        "/v1/admin/batches",
        json={
            "name": "B1",
            "start_time": "00:00",
            "end_time": "23:59",
            "days": "0,1,2,3,4,5,6",
            "late_after_min": 1440,
            "open_before_min": 0,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _live_token(c, value: int) -> str:
    ch = c.post("/v1/liveness/challenge").json()
    c.app.state.challenges._challenges[ch["challenge_id"]].steps = ["center", "center"]
    files = [("frames", _png(value)), ("frames", _png(value))]
    r = c.post("/v1/liveness/verify", data={"challenge_id": ch["challenge_id"]}, files=files).json()
    assert r["live"], r
    return r["token"]


def test_signup_login_and_me(app_client):
    c = app_client
    body = {"email": "Asha@X.in", "password": "password123", "full_name": "Asha", "consent": True}
    r = c.post("/v1/auth/signup", json=body)
    assert r.status_code == 201 and r.json()["user"]["email"] == "asha@x.in"
    assert c.post("/v1/auth/signup", json=body).status_code == 409
    assert c.post("/v1/auth/signup", json={**body, "consent": False}).status_code == 422
    bad = c.post("/v1/auth/login", json={"email": "asha@x.in", "password": "nope"})
    assert bad.status_code == 401 and bad.json()["detail"] == "invalid email or password"
    tok = c.post("/v1/auth/login", json={"email": "asha@x.in", "password": "password123"}).json()
    me = c.get("/v1/me", headers={"Authorization": f"Bearer {tok['access_token']}"}).json()
    assert me["role"] == "student" and me["face_enrolled"] is False
    assert c.get("/v1/me").status_code == 401


def test_student_cannot_use_admin_routes(app_client):
    c = app_client
    t = c.post(
        "/v1/auth/signup",
        json={"email": "s@x.in", "password": "password123", "full_name": "Sam", "consent": True},
    ).json()["access_token"]
    assert c.get("/v1/admin/students", headers={"Authorization": f"Bearer {t}"}).status_code == 403


def test_face_enroll_face_login_and_self_attendance(app_client):
    c = app_client
    h_admin = _admin(c)
    batch = _always_open_batch(c, h_admin)
    t = c.post(
        "/v1/auth/signup",
        json={
            "email": "ravi@x.in",
            "password": "password123",
            "full_name": "Ravi",
            "consent": True,
        },
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    me = c.get("/v1/me", headers=h).json()
    c.patch(f"/v1/admin/students/{me['id']}", json={"batch_id": batch}, headers=h_admin)

    assert c.post("/v1/me/face", files={"file": _png(42)}, headers=h).status_code == 201
    assert c.get("/v1/me", headers=h).json()["face_enrolled"] is True

    # face login: liveness token se (password nahi)
    r = c.post("/v1/auth/face-login", json={"liveness_token": _live_token(c, 42)})
    assert r.status_code == 200 and r.json()["user"]["email"] == "ravi@x.in"
    # token single use
    tok = _live_token(c, 42)
    c.post("/v1/auth/face-login", json={"liveness_token": tok})
    assert c.post("/v1/auth/face-login", json={"liveness_token": tok}).status_code == 401
    # unknown face
    assert (
        c.post("/v1/auth/face-login", json={"liveness_token": _live_token(c, 7)}).status_code == 401
    )

    # self attendance: present, phir duplicate
    m1 = c.post("/v1/me/attendance", json={"liveness_token": _live_token(c, 42)}, headers=h).json()
    assert m1["status"] == "present"
    m2 = c.post("/v1/me/attendance", json={"liveness_token": _live_token(c, 42)}, headers=h).json()
    assert m2["status"] == "already_marked"
    # kisi aur ka chehra apne account pe nahi chalega
    other = c.post(
        "/v1/me/attendance", json={"liveness_token": _live_token(c, 7)}, headers=h
    ).json()
    assert other["status"] == "rejected"

    rec = c.get("/v1/me/attendance", headers=h).json()
    assert [r["status"] for r in rec] == ["present"]


def test_admin_crm_scan_manual_reports(app_client):
    c = app_client
    h = _admin(c)
    batch = _always_open_batch(c, h)
    r = c.post(
        "/v1/admin/students",
        json={
            "email": "zoya@x.in",
            "full_name": "Zoya",
            "roll_no": "R-7",
            "batch_id": batch,
            "consent": True,
        },
        headers=h,
    )
    assert r.status_code == 201 and len(r.json()["temporary_password"]) >= 8
    sid = r.json()["student"]["id"]
    assert (
        c.post(f"/v1/admin/students/{sid}/face", files={"file": _png(42)}, headers=h).status_code
        == 201
    )

    assert [s["roll_no"] for s in c.get("/v1/admin/students?q=r-7", headers=h).json()] == ["R-7"]
    assert c.get("/v1/admin/batches", headers=h).json()[0]["student_count"] == 1

    scan = c.post("/v1/admin/attendance/scan", files={"file": _png(42)}, headers=h).json()
    assert scan["faces"] == 1 and scan["unknown"] == 0
    assert [(s["full_name"], s["status"]) for s in scan["results"]] == [("Zoya", "present")]
    # unknown face: reported, not silently dropped
    unk = c.post("/v1/admin/attendance/scan", files={"file": _png(7)}, headers=h).json()
    assert unk == {"faces": 1, "unknown": 1, "results": []}

    # manual override -> late, phir report
    c.post("/v1/admin/attendance/manual", json={"user_id": sid, "status": "late"}, headers=h)
    summary = c.get("/v1/admin/reports/summary", headers=h).json()
    assert summary["students"][0]["late"] == 1 and summary["students"][0]["attendance_pct"] == 100.0
    csv_text = c.get("/v1/admin/reports/export.csv", headers=h).text
    assert csv_text.splitlines()[0].startswith("day,student,email") and "Zoya" in csv_text
    assert c.get("/v1/admin/overview", headers=h).json()["today"]["late"] == 1

    # delete student -> biometric bhi gaya, face ab match nahi
    d = c.delete(f"/v1/admin/students/{sid}", headers=h).json()
    assert d["deleted_embeddings"] == 1
    after = c.post("/v1/admin/attendance/scan", files={"file": _png(42)}, headers=h).json()
    assert after["results"] == [] and after["unknown"] == 1


def test_absent_rows_for_past_class_days(app_client, monkeypatch):
    c = app_client
    h = _admin(c)
    batch = _always_open_batch(c, h)
    sid = c.post(
        "/v1/admin/students",
        json={"email": "a@x.in", "full_name": "Anu", "batch_id": batch, "consent": True},
        headers=h,
    ).json()["student"]["id"]
    svc = c.app.state.attendance
    noon = datetime.combine(svc.now_local().date(), datetime.min.time(), IST).replace(hour=12)
    monkeypatch.setattr(svc, "now_local", lambda: noon)  # class (00:00-23:59) abhi chal rahi
    with svc.sessions.begin() as db:
        db.get(User, sid).enrollment_date = noon.date() - timedelta(days=3)
    rows = c.get(f"/v1/admin/attendance?user_id={sid}", headers=h).json()
    assert [r["status"] for r in rows] == ["absent", "absent", "absent"]  # aaj abhi absent nahi


def test_password_change_invalidates_old_tokens(app_client):
    c = app_client
    h = _admin(c)
    t = c.post(
        "/v1/auth/signup",
        json={"email": "p@x.in", "password": "password123", "full_name": "Pia", "consent": True},
    ).json()
    old = {"Authorization": f"Bearer {t['access_token']}"}
    c.patch(f"/v1/admin/students/{t['user']['id']}", json={"password": "newpassword1"}, headers=h)
    assert c.get("/v1/me", headers=old).status_code == 401


def test_csv_formula_injection_neutralized():
    from faceai.attendance.service import _csv_safe

    assert _csv_safe("=HYPERLINK(evil)") == "'=HYPERLINK(evil)"
    assert _csv_safe("Asha") == "Asha"


# ---------- input rules (name / mobile / password / roll) ----------
@pytest.mark.parametrize(
    "fn,raw,expected",
    [
        ("name", "  Asha   Rao ", "Asha Rao"),
        ("name", "D'Souza-Pinto", "D'Souza-Pinto"),
        ("name", "अमित कुमार", "अमित कुमार"),
        ("phone", "98765 43210", "+919876543210"),
        ("phone", "+91-98765-43210", "+919876543210"),
        ("phone", "09876543210", "+919876543210"),
        ("phone", "", None),
        ("password", "asha2026", "asha2026"),
        ("roll", "r-01/a", "R-01/A"),
    ],
)
def test_input_rules_accept_and_normalize(fn, raw, expected):
    from faceai.attendance import validators as v

    f = {
        "name": v.clean_name,
        "phone": v.clean_phone,
        "password": v.check_password,
        "roll": v.clean_roll,
    }[fn]
    assert f(raw) == expected


@pytest.mark.parametrize(
    "fn,raw,msg",
    [
        ("name", "Asha123", "cannot contain numbers"),
        ("name", "A", "at least 2"),
        ("name", "-.", "at least 2"),
        ("name", "Asha@Rao", "only letters"),
        ("phone", "98abc43210", "only digits"),
        ("phone", "12345", "valid 10-digit"),
        ("phone", "5876543210", "valid 10-digit"),  # 5 se shuru: Indian mobile nahi
        ("password", "password", "one number"),
        ("password", "12345678", "one letter"),
        ("password", "ab1", "at least 8"),
        ("roll", "R@01", "only letters, numbers"),
    ],
)
def test_input_rules_reject(fn, raw, msg):
    from faceai.attendance import validators as v

    f = {
        "name": v.clean_name,
        "phone": v.clean_phone,
        "password": v.check_password,
        "roll": v.clean_roll,
    }[fn]
    with pytest.raises(ValueError, match=msg):
        f(raw)


def test_signup_api_enforces_rules(app_client):
    base = {"email": "r@x.in", "password": "password123", "full_name": "Ravi", "consent": True}
    for bad in ({"full_name": "Ravi2"}, {"phone": "12345"}, {"password": "onlyletters"}):
        r = app_client.post("/v1/auth/signup", json={**base, **bad})
        assert r.status_code == 422, bad
    ok = app_client.post("/v1/auth/signup", json={**base, "phone": "98765 43210"})
    assert ok.status_code == 201 and ok.json()["user"]["phone"] == "+919876543210"


def test_enrollment_date_uses_local_timezone_not_utc(app_client, monkeypatch):
    """Regression: 00:30 IST = pichhle din 19:00 UTC. Naya student kal ka absent na bane."""
    from datetime import datetime as dt

    svc = app_client.app.state.attendance
    just_after_midnight_ist = dt(2026, 11, 24, 0, 30, tzinfo=IST)  # UTC: 2026-11-23 19:00
    monkeypatch.setattr(svc, "now_local", lambda: just_after_midnight_ist)
    h = _admin(app_client)
    batch = _always_open_batch(app_client, h)
    r = app_client.post(
        "/v1/admin/students",
        json={"email": "tz@x.in", "full_name": "Tara", "batch_id": batch, "consent": True},
        headers=h,
    ).json()
    assert r["student"]["enrollment_date"] == "2026-11-24"
    t = app_client.post(
        "/v1/auth/signup",
        json={"email": "tz2@x.in", "password": "password123", "full_name": "Tanu", "consent": True},
    ).json()
    assert t["user"]["enrollment_date"] == "2026-11-24"
    rows = app_client.get(
        f"/v1/admin/attendance?user_id={r['student']['id']}&from=2026-11-23&to=2026-11-24",
        headers=h,
    ).json()
    assert rows == []  # 23 Nov ko student tha hi nahi -> koi absent nahi


def test_class_over_rule():
    end = "13:00"
    day = datetime(2026, 11, 24, tzinfo=IST).date()
    at = lambda h, m: datetime(2026, 11, 24, h, m, tzinfo=IST)  # noqa: E731
    assert class_over(at(12, 59), day, end) is False  # class chal rahi
    assert class_over(at(13, 0), day, end) is False  # end minute tak attendance lagti hai
    assert class_over(at(13, 1), day, end) is True
    assert class_over(at(9, 0), day - timedelta(days=1), end) is True  # kal: hamesha over
    assert class_over(at(23, 0), day + timedelta(days=1), end) is False  # kal ki class


def test_today_counts_absent_only_after_class_ends(app_client, monkeypatch):
    """Regression: aaj absent student report se GAYAB tha (sirf kal se dikhta)."""
    c = app_client
    h = _admin(c)
    svc = c.app.state.attendance
    day = svc.now_local().date()
    clock = {"now": datetime.combine(day, datetime.min.time(), IST).replace(hour=9, minute=30)}
    monkeypatch.setattr(svc, "now_local", lambda: clock["now"])
    b = c.post(
        "/v1/admin/batches",
        json={
            "name": "Morning",
            "start_time": "09:00",
            "end_time": "13:00",
            "days": "0,1,2,3,4,5,6",
        },
        headers=h,
    ).json()["id"]
    ids = [
        c.post(
            "/v1/admin/students",
            json={"email": f"s{i}@x.in", "full_name": n, "batch_id": b, "consent": True},
            headers=h,
        ).json()["student"]["id"]
        for i, n in enumerate(["Asha", "Bela"])
    ]
    c.post("/v1/admin/attendance/manual", json={"user_id": ids[0], "status": "present"}, headers=h)

    def summary():
        r = c.get(f"/v1/admin/reports/summary?start={day}&end={day}", headers=h).json()
        return {s["full_name"]: (s["present"], s["absent"]) for s in r["students"]}

    assert summary() == {"Asha": (1, 0)}  # 09:30: class chal rahi -> Bela abhi absent NAHI

    clock["now"] = clock["now"].replace(hour=18)  # class 13:00 pe khatam
    assert summary() == {"Asha": (1, 0), "Bela": (0, 1)}  # ab Bela absent dikhni chahiye
