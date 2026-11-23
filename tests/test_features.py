"""#4 bulk import, #7 teacher role (scoping), #8 holidays + leave."""

from datetime import timedelta

import cv2
import pytest
from fastapi.testclient import TestClient

from faceai.api.app import create_app
from faceai.attendance.models import User
from faceai.attendance.security import hash_password
from tests.fakes import FakeEngine, make_image


def _png(value: int) -> tuple:
    ok, buf = cv2.imencode(".png", make_image(value))
    return ("f.png", buf.tobytes(), "image/png")


@pytest.fixture
def c(settings):
    s = settings.model_copy(
        update={"jwt_secret": "test-secret-0123456789abcdef", "rate_limit": False}
    )
    with TestClient(create_app(s, engine=FakeEngine())) as client:
        yield client


def _login(c, email, pw):
    r = c.post("/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(c):
    with c.app.state.attendance.sessions.begin() as db:
        db.add(
            User(
                email="admin@x.in",
                full_name="Admin",
                password_hash=hash_password("adminpass123"),
                role="admin",
            )
        )
    return _login(c, "admin@x.in", "adminpass123")


def _batch(c, h, name):
    r = c.post(
        "/v1/admin/batches",
        json={
            "name": name,
            "start_time": "00:00",
            "end_time": "23:59",
            "days": "0,1,2,3,4,5,6",
            "late_after_min": 1440,
            "open_before_min": 0,
        },
        headers=h,
    )
    return r.json()["id"]


def _csv(text):
    return {"file": ("students.csv", text.encode("utf-8-sig"), "text/csv")}


# ---------------- #4 bulk import ----------------
def test_import_preview_then_commit_with_credentials(c):
    h = _admin(c)
    _batch(c, h, "Morning Batch")
    csv_text = (
        "full_name,email,phone,roll_no,batch\n"
        "Asha Rao,asha@x.in,98765 43210,r-01,morning batch\n"
        "Ravi Kumar,ravi@x.in,,R-02,\n"
    )
    prev = c.post("/v1/admin/import/students?dry_run=true", files=_csv(csv_text), headers=h).json()
    assert prev == {"rows": 2, "valid": 2, "errors": [], "created": []}
    assert c.get("/v1/admin/students", headers=h).json() == []  # dry run: kuch save nahi
    # consent ke bina commit nahi
    assert (
        c.post(
            "/v1/admin/import/students?dry_run=false", files=_csv(csv_text), headers=h
        ).status_code
        == 422
    )
    done = c.post(
        "/v1/admin/import/students?dry_run=false&consent=true", files=_csv(csv_text), headers=h
    ).json()
    assert [x["email"] for x in done["created"]] == ["asha@x.in", "ravi@x.in"]
    assert all(len(x["temporary_password"]) >= 8 for x in done["created"])
    students = {s["email"]: s for s in c.get("/v1/admin/students", headers=h).json()}
    assert (
        students["asha@x.in"]["phone"] == "+919876543210"
        and students["asha@x.in"]["roll_no"] == "R-01"
    )
    assert students["asha@x.in"]["batch_id"] and students["ravi@x.in"]["batch_id"] is None


def test_import_is_all_or_nothing_with_row_errors(c):
    h = _admin(c)
    c.post(
        "/v1/admin/students",
        json={"email": "old@x.in", "full_name": "Old One", "consent": True},
        headers=h,
    )
    csv_text = (
        "full_name,email,phone,batch\n"
        "Good Person,good@x.in,9876543210,\n"
        "Bad7Name,bad@x.in,,\n"  # row 3: digits in name
        "Dup Email,old@x.in,,\n"  # row 4: already registered
        "No Batch,nb@x.in,12345,Ghost\n"  # row 5: bad phone + unknown batch
        "Twice,good@x.in,,\n"  # row 6: duplicate in file
    )
    r = c.post(
        "/v1/admin/import/students?dry_run=false&consent=true", files=_csv(csv_text), headers=h
    ).json()
    errs = {(e["row"], e["field"]) for e in r["errors"]}
    assert {(3, "full_name"), (4, "email"), (5, "phone"), (5, "batch"), (6, "email")} <= errs
    assert r["created"] == []
    assert [s["email"] for s in c.get("/v1/admin/students", headers=h).json()] == ["old@x.in"]


def test_import_rejects_missing_columns_and_template_works(c):
    h = _admin(c)
    bad = c.post("/v1/admin/import/students", files=_csv("name,mail\nA,b\n"), headers=h)
    assert bad.status_code == 422 and "missing columns" in bad.json()["detail"]
    tpl = c.get("/v1/admin/import/students-template.csv", headers=h)
    assert tpl.text.splitlines()[0] == "full_name,email,phone,roll_no,batch"


# ---------------- #7 teacher role ----------------
def _teacher_setup(c):
    h = _admin(c)
    b1, b2 = _batch(c, h, "B1"), _batch(c, h, "B2")
    s1 = c.post(
        "/v1/admin/students",
        json={"email": "s1@x.in", "full_name": "Sita", "batch_id": b1, "consent": True},
        headers=h,
    ).json()["student"]["id"]
    s2 = c.post(
        "/v1/admin/students",
        json={"email": "s2@x.in", "full_name": "Gita", "batch_id": b2, "consent": True},
        headers=h,
    ).json()["student"]["id"]
    t = c.post(
        "/v1/admin/teachers",
        json={
            "email": "t@x.in",
            "full_name": "Teacher One",
            "password": "teach1234",
            "batch_ids": [b1],
        },
        headers=h,
    )
    assert t.status_code == 201, t.text
    return h, _login(c, "t@x.in", "teach1234"), b1, b2, s1, s2


def test_teacher_sees_only_own_batches(c):
    h, th, b1, b2, s1, s2 = _teacher_setup(c)
    assert [s["email"] for s in c.get("/v1/admin/students", headers=th).json()] == ["s1@x.in"]
    assert [b["name"] for b in c.get("/v1/admin/batches", headers=th).json()] == ["B1"]
    assert c.get(f"/v1/admin/students/{s1}", headers=th).status_code == 200
    assert c.get(f"/v1/admin/students/{s2}", headers=th).status_code == 403
    assert c.get("/v1/admin/overview", headers=th).json()["students"] == 1
    # attendance + reports scoped
    c.post("/v1/admin/attendance/manual", json={"user_id": s1, "status": "present"}, headers=th)
    assert (
        c.post(
            "/v1/admin/attendance/manual", json={"user_id": s2, "status": "present"}, headers=th
        ).status_code
        == 403
    )
    names = {r["full_name"] for r in c.get("/v1/admin/attendance", headers=th).json()}
    assert names == {"Sita"}
    assert {
        s["full_name"] for s in c.get("/v1/admin/reports/summary", headers=th).json()["students"]
    } == {"Sita"}


def test_teacher_cannot_do_admin_only_things(c):
    h, th, b1, b2, s1, s2 = _teacher_setup(c)
    assert (
        c.post(
            "/v1/admin/students",
            json={"email": "z@x.in", "full_name": "Zed", "consent": True},
            headers=th,
        ).status_code
        == 403
    )
    assert c.delete(f"/v1/admin/students/{s1}", headers=th).status_code == 403
    assert (
        c.post(
            "/v1/admin/batches",
            json={"name": "X", "start_time": "09:00", "end_time": "10:00"},
            headers=th,
        ).status_code
        == 403
    )
    assert c.get("/v1/admin/teachers", headers=th).status_code == 403
    assert (
        c.post("/v1/admin/import/students", files=_csv("full_name,email\n"), headers=th).status_code
        == 403
    )


def test_teacher_kiosk_marks_only_own_students(c):
    h, th, b1, b2, s1, s2 = _teacher_setup(c)
    c.post(f"/v1/admin/students/{s1}/face", files={"file": _png(42)}, headers=h)
    c.post(f"/v1/admin/students/{s2}/face", files={"file": _png(43)}, headers=h)
    own = c.post("/v1/admin/attendance/scan", files={"file": _png(42)}, headers=th).json()
    assert [(r["full_name"], r["status"]) for r in own["results"]] == [("Sita", "present")]
    other = c.post("/v1/admin/attendance/scan", files={"file": _png(43)}, headers=th).json()
    assert [(r["full_name"], r["status"], r["reason"]) for r in other["results"]] == [
        ("Gita", "rejected", "not in your batches")
    ]


def test_reassigning_teacher_batches(c):
    h, th, b1, b2, s1, s2 = _teacher_setup(c)
    tid = c.get("/v1/admin/teachers", headers=h).json()[0]["id"]
    r = c.put(f"/v1/admin/teachers/{tid}/batches", json={"batch_ids": [b2]}, headers=h)
    assert r.json()["batch_ids"] == [b2]
    assert [s["email"] for s in c.get("/v1/admin/students", headers=th).json()] == ["s2@x.in"]


# ---------------- #8 holidays + leave ----------------
def test_holiday_blocks_marking_and_is_not_absent(c):
    h = _admin(c)
    b = _batch(c, h, "B1")
    sid = c.post(
        "/v1/admin/students",
        json={"email": "h@x.in", "full_name": "Hari", "batch_id": b, "consent": True},
        headers=h,
    ).json()["student"]["id"]
    c.post(f"/v1/admin/students/{sid}/face", files={"file": _png(42)}, headers=h)
    svc = c.app.state.attendance
    today = svc.now_local().date()
    with svc.sessions.begin() as db:
        db.get(User, sid).enrollment_date = today - timedelta(days=2)
    yesterday = today - timedelta(days=1)
    assert (
        c.post(
            "/v1/admin/holidays", json={"day": str(yesterday), "name": "Diwali"}, headers=h
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/v1/admin/holidays",
            json={"day": str(today), "name": "Local fest", "batch_id": b},
            headers=h,
        ).status_code
        == 201
    )
    # today holiday -> scan rejects
    r = c.post("/v1/admin/attendance/scan", files={"file": _png(42)}, headers=h).json()
    assert (
        r["results"][0]["status"] == "rejected"
        and "holiday: Local fest" in r["results"][0]["reason"]
    )
    rows = {
        x["day"]: x["status"]
        for x in c.get(f"/v1/admin/attendance?user_id={sid}", headers=h).json()
    }
    assert rows[str(yesterday)] == "holiday" and rows[str(today - timedelta(days=2))] == "absent"
    s = c.get("/v1/admin/reports/summary", headers=h).json()["students"][0]
    assert (
        s["holiday"] == 2 and s["absent"] == 1 and s["attendance_pct"] == 0.0
    )  # holidays % mein nahi


def test_leave_request_approve_excludes_from_absent(c):
    h = _admin(c)
    b = _batch(c, h, "B1")
    st = c.post(
        "/v1/auth/signup",
        json={"email": "l@x.in", "password": "leave1234", "full_name": "Lata", "consent": True},
    ).json()
    sid = st["user"]["id"]
    c.patch(f"/v1/admin/students/{sid}", json={"batch_id": b}, headers=h)
    svc = c.app.state.attendance
    today = svc.now_local().date()
    with svc.sessions.begin() as db:
        db.get(User, sid).enrollment_date = today - timedelta(days=3)
    sh = {"Authorization": f"Bearer {st['access_token']}"}
    d1, d2 = today - timedelta(days=3), today - timedelta(days=2)
    lv = c.post(
        "/v1/me/leaves", json={"start": str(d1), "end": str(d2), "reason": "fever"}, headers=sh
    ).json()
    assert lv["status"] == "pending"
    # pending leave abhi absent hi hai
    assert {
        r["status"] for r in c.get(f"/v1/admin/attendance?user_id={sid}", headers=h).json()
    } == {"absent"}
    pend = c.get("/v1/admin/leaves", headers=h).json()
    assert [(p["full_name"], p["status"]) for p in pend] == [("Lata", "pending")]
    assert (
        c.patch(f"/v1/admin/leaves/{lv['id']}", json={"approve": True}, headers=h).json()["status"]
        == "approved"
    )
    rows = {
        x["day"]: x["status"]
        for x in c.get(f"/v1/admin/attendance?user_id={sid}", headers=h).json()
    }
    assert (
        rows[str(d1)] == rows[str(d2)] == "leave"
        and rows[str(today - timedelta(days=1))] == "absent"
    )
    assert c.get("/v1/me/leaves", headers=sh).json()[0]["status"] == "approved"
    bad = c.post(
        "/v1/me/leaves", json={"start": str(d2), "end": str(d1), "reason": "oops"}, headers=sh
    )
    assert bad.status_code == 422


def test_teacher_cannot_decide_leave_outside_batches(c):
    h, th, b1, b2, s1, s2 = _teacher_setup(c)
    svc = c.app.state.attendance
    lv = svc.request_leave(s2, svc.now_local().date(), svc.now_local().date(), "trip")
    assert (
        c.patch(f"/v1/admin/leaves/{lv.id}", json={"approve": True}, headers=th).status_code == 403
    )
    assert c.get("/v1/admin/leaves", headers=th).json() == []
