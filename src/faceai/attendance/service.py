"""
Attendance product logic (Phase B): signup/login, face enroll + face login, students, batches,
attendance marking (rules + duplicates), reports.

Biometric kaam `RecognitionService` (Phase 1-7) karta hai: consent, encryption, audit, index.
Ye layer sirf product rules jaanti hai, aur users ko biometric `person_id` se jodti hai.
"""

from __future__ import annotations

import csv
import io
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from faceai.attendance.models import Attendance, Batch, Holiday, Leave, User
from faceai.attendance.rules import decide
from faceai.attendance.security import create_token, hash_password, verify_password
from faceai.config import Settings
from faceai.service import RecognitionService

logger = logging.getLogger(__name__)


class AuthError(Exception):
    pass


class ConflictError(Exception):
    pass


class NotFound(Exception):
    pass


class ForbiddenError(Exception):
    """Teacher ne apne batches ke bahar ka data chhua (403)."""


class RuleError(Exception):
    """Attendance rule ne mana kiya (window ke bahar, already marked, no batch...)."""


@dataclass
class MarkResult:
    user_id: str
    full_name: str
    status: str  # present | late | already_marked | rejected
    reason: str
    confidence: float | None = None


class AttendanceService:
    def __init__(
        self,
        sessions: sessionmaker,
        bio: RecognitionService,
        settings: Settings,
        jwt_secret: str,
    ):
        self.sessions = sessions
        self.bio = bio
        self.s = settings
        self.jwt_secret = jwt_secret
        self.tz = ZoneInfo(settings.timezone)

    # ---------- helpers ----------
    def now_local(self) -> datetime:
        return datetime.now(UTC).astimezone(self.tz)

    def _token(self, u: User, method: str) -> str:
        return create_token(
            u.id, u.role, u.token_version, self.jwt_secret, self.s.jwt_ttl_minutes, method
        )

    def get_user(self, db: Session, user_id: str) -> User:
        u = db.get(User, user_id)
        if u is None:
            raise NotFound("user")
        return u

    # ---------- auth ----------
    def signup(self, email: str, password: str, full_name: str, phone: str | None) -> tuple:
        email = email.strip().lower()
        with self.sessions.begin() as db:
            if db.scalar(select(User).where(User.email == email)):
                raise ConflictError("email already registered")
            u = User(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name.strip(),
                phone=phone,
                role="student",
                # LOCAL date (FACEAI_TIMEZONE). UTC date 00:00-05:30 IST ke beech "kal" hota hai
                # -> naye student ka kal ka false "absent" ban jaata.
                enrollment_date=self.now_local().date(),
            )
            db.add(u)
            db.flush()
            return u, self._token(u, "pwd")

    def login(self, email: str, password: str) -> tuple:
        with self.sessions.begin() as db:
            u = db.scalar(select(User).where(User.email == email.strip().lower()))
            # Same error dono cases mein: "email exists?" leak nahi (user enumeration)
            if u is None or not verify_password(password, u.password_hash):
                raise AuthError("invalid email or password")
            if u.status != "active":
                raise AuthError("account inactive")
            u.last_login_at = datetime.now(UTC)
            return u, self._token(u, "pwd")

    def identify(self, embedding: np.ndarray) -> tuple[str, float] | None:
        """Embedding -> (person_id, similarity) agar threshold se upar, warna None."""
        ranked = self.bio.index.search_persons(embedding)
        if not ranked or ranked[0][1] < self.s.face_login_threshold:
            return None
        # Do log bahut paas (ambiguous)? Login mat do, password se karwao.
        if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < self.s.face_login_margin:
            return None
        return ranked[0]

    def face_login(self, live_embedding: np.ndarray) -> tuple:
        hit = self.identify(live_embedding)
        if hit is None:
            raise AuthError("face not recognized")
        person_id, sim = hit
        with self.sessions.begin() as db:
            u = db.scalar(select(User).where(User.person_id == person_id))
            if u is None or u.status != "active":
                raise AuthError("face not recognized")
            u.last_login_at = datetime.now(UTC)
            logger.info("face login", extra={"user_id": u.id, "similarity": round(sim, 3)})
            return u, self._token(u, "face"), sim

    # ---------- face enrollment ----------
    def enroll_face(self, user_id: str, image_bgr, actor: str, replace: bool = False):
        with self.sessions.begin() as db:
            u = self.get_user(db, user_id)
            if replace and u.person_id:
                self.bio.delete_person(u.person_id, actor)  # purani embeddings + index se bhi
                u.person_id = None
            if u.person_id is None:
                # Consent signup/admin create pe liya gaya (API contract: consent: true)
                p = self.bio.create_person(u.id, consent=True, actor=actor)
                u.person_id = p.id
            person_id = u.person_id
        return self.bio.enroll_face(person_id, image_bgr, actor)

    # ---------- students (admin) ----------
    def create_student(self, data: dict, actor: str, role: str = "student") -> tuple[User, str]:
        temp_password = data.pop("password", None) or secrets.token_urlsafe(9)
        data["email"] = data["email"].strip().lower()
        with self.sessions.begin() as db:
            if data.get("batch_id") and db.get(Batch, data["batch_id"]) is None:
                raise NotFound("batch")
            u = User(
                **data,
                password_hash=hash_password(temp_password),
                role=role,
                enrollment_date=self.now_local().date(),  # local date, not UTC (see signup)
            )
            db.add(u)
            try:
                db.flush()
            except IntegrityError:
                raise ConflictError("email already registered") from None
        return u, temp_password

    def list_students(
        self,
        q: str | None,
        batch_id: str | None,
        status: str | None,
        scope: set[str] | None = None,
    ):
        with self.sessions() as db:
            stmt = select(User).where(User.role == "student").order_by(User.full_name)
            if scope is not None:  # teacher: sirf apne batches
                stmt = stmt.where(User.batch_id.in_(scope))
            if q:
                like = f"%{q.lower()}%"
                stmt = stmt.where(
                    func.lower(User.full_name).like(like)
                    | func.lower(User.email).like(like)
                    | func.lower(func.coalesce(User.roll_no, "")).like(like)
                )
            if batch_id:
                stmt = stmt.where(User.batch_id == batch_id)
            if status:
                stmt = stmt.where(User.status == status)
            return list(db.scalars(stmt))

    def update_user(self, user_id: str, changes: dict) -> User:
        with self.sessions.begin() as db:
            u = self.get_user(db, user_id)
            if changes.get("batch_id") and db.get(Batch, changes["batch_id"]) is None:
                raise NotFound("batch")
            if "password" in changes:
                u.password_hash = hash_password(changes.pop("password"))
                u.token_version += 1  # purane sessions/tokens invalid
            if changes.get("status") == "inactive":
                u.token_version += 1
            for k, v in changes.items():
                setattr(u, k, v)
            return u

    def delete_user(self, user_id: str, actor: str) -> int:
        """Student + biometric data hatao (right to be forgotten). Return: embeddings deleted."""
        with self.sessions.begin() as db:
            u = self.get_user(db, user_id)
            n = 0
            if u.person_id:
                try:
                    n = self.bio.delete_person(u.person_id, actor)
                except Exception:  # biometric person pehle hi hata ho
                    logger.warning("biometric person %s missing during delete", u.person_id)
            db.delete(u)
            return n

    # ---------- batches ----------
    def create_batch(self, data: dict) -> Batch:
        with self.sessions.begin() as db:
            b = Batch(**data)
            db.add(b)
            try:
                db.flush()
            except IntegrityError:
                raise ConflictError("batch name already exists") from None
            return b

    def list_batches(self) -> list[tuple[Batch, int]]:
        with self.sessions() as db:
            counts = dict(
                db.execute(
                    select(User.batch_id, func.count())
                    .where(User.role == "student")
                    .group_by(User.batch_id)
                ).all()
            )
            return [
                (b, counts.get(b.id, 0)) for b in db.scalars(select(Batch).order_by(Batch.name))
            ]

    def update_batch(self, batch_id: str, changes: dict) -> Batch:
        with self.sessions.begin() as db:
            b = db.get(Batch, batch_id)
            if b is None:
                raise NotFound("batch")
            for k, v in changes.items():
                setattr(b, k, v)
            return b

    def delete_batch(self, batch_id: str) -> None:
        with self.sessions.begin() as db:
            b = db.get(Batch, batch_id)
            if b is None:
                raise NotFound("batch")
            db.delete(b)

    # ---------- attendance ----------
    def mark(
        self,
        user_id: str,
        method: str,
        marked_by: str,
        confidence: float | None = None,
        now_local: datetime | None = None,
    ) -> MarkResult:
        now_local = now_local or self.now_local()
        with self.sessions.begin() as db:
            u = self.get_user(db, user_id)
            if u.status != "active":
                return MarkResult(u.id, u.full_name, "rejected", "student inactive", confidence)
            if u.batch is None:
                return MarkResult(
                    u.id, u.full_name, "rejected", "not in any batch (assign one)", confidence
                )
            b = u.batch
            hol = self._holiday(db, b.id, now_local.date())
            if hol is not None:
                return MarkResult(u.id, u.full_name, "rejected", f"holiday: {hol.name}", confidence)
            d = decide(
                now_local, b.start_time, b.end_time, b.days, b.late_after_min, b.open_before_min
            )
            if not d.allowed:
                return MarkResult(
                    u.id, u.full_name, "rejected", f"{b.name}: {d.reason}", confidence
                )
            existing = db.scalar(
                select(Attendance).where(
                    Attendance.user_id == u.id,
                    Attendance.batch_id == b.id,
                    Attendance.day == now_local.date(),
                )
            )
            if existing:
                return MarkResult(
                    u.id, u.full_name, "already_marked", f"already {existing.status}", confidence
                )
            db.add(
                Attendance(
                    user_id=u.id,
                    batch_id=b.id,
                    day=now_local.date(),
                    status=d.status,
                    method=method,
                    confidence=confidence,
                    marked_by=marked_by,
                )
            )
            try:
                db.flush()
            except IntegrityError:  # do kiosks ne ek saath mark kiya
                return MarkResult(u.id, u.full_name, "already_marked", "already marked", confidence)
            return MarkResult(u.id, u.full_name, d.status, "ok", confidence)

    def mark_self(self, user_id: str, live_embedding: np.ndarray) -> MarkResult:
        """Student khud: liveness wala face uska APNA hona chahiye."""
        with self.sessions() as db:
            u = self.get_user(db, user_id)
            person_id, name = u.person_id, u.full_name
        if person_id is None:
            return MarkResult(user_id, name, "rejected", "face not enrolled")
        hit = self.identify(live_embedding)
        if hit is None or hit[0] != person_id:
            return MarkResult(user_id, name, "rejected", "face does not match your account")
        return self.mark(user_id, "face", "self", round(hit[1], 4))

    def scan(self, image_bgr, marked_by: str, scope: set[str] | None = None) -> dict:
        """Admin live camera / kiosk: photo ke saare pehchaane gaye students mark.
        UI ko HAR frame ka hisaab chahiye (kitne chehre, kitne anjaan), warna "kuch nahi hua"
        aur "chehra pehchana nahi" mein farak nahi dikhta."""
        res = self.bio.recognize(image_bgr, top_k=1)
        out: list[MarkResult] = []
        unknown = 0
        for f in res.faces:
            u = None
            if f.match is not None:
                with self.sessions() as db:
                    u = db.scalar(select(User).where(User.person_id == f.match.person_id))
            if u is None:
                unknown += 1
                continue
            if scope is not None and u.batch_id not in scope:
                out.append(MarkResult(u.id, u.full_name, "rejected", "not in your batches", None))
                continue
            out.append(self.mark(u.id, "face", marked_by, f.match.similarity))
        return {"faces": len(res.faces), "unknown": unknown, "results": out}

    def manual(
        self, user_id: str, day: date, status: str, admin_id: str, scope: set[str] | None = None
    ) -> Attendance | None:
        """Admin/teacher override: upsert. status='absent' => record hatao."""
        with self.sessions.begin() as db:
            u = self.get_user(db, user_id)
            if scope is not None and u.batch_id not in scope:
                raise ForbiddenError("student is not in your batches")
            if u.batch_id is None:
                raise RuleError("no batch assigned")
            rec = db.scalar(
                select(Attendance).where(
                    Attendance.user_id == u.id,
                    Attendance.batch_id == u.batch_id,
                    Attendance.day == day,
                )
            )
            if status == "absent":
                if rec:
                    db.delete(rec)
                return None
            if rec is None:
                rec = Attendance(user_id=u.id, batch_id=u.batch_id, day=day)
                db.add(rec)
            rec.status, rec.method, rec.marked_by, rec.confidence = status, "manual", admin_id, None
            rec.marked_at = datetime.now(UTC)
            return rec

    def records(
        self,
        start: date,
        end: date,
        batch_id: str | None = None,
        user_id: str | None = None,
        scope: set[str] | None = None,
    ) -> list[dict]:
        """Records + computed rows for class days without a record:
        holiday (us batch/sab ke liye) -> "holiday", approved leave -> "leave", warna -> "absent".
        Holiday/leave din attendance % ke denominator mein nahi gine jaate."""
        with self.sessions() as db:
            students = select(User).where(User.role == "student", User.batch_id.is_not(None))
            if scope is not None:
                students = students.where(User.batch_id.in_(scope))
            if batch_id:
                students = students.where(User.batch_id == batch_id)
            if user_id:
                students = students.where(User.id == user_id)
            users = list(db.scalars(students))
            recs = {
                (a.user_id, a.day): a
                for a in db.scalars(
                    select(Attendance).where(Attendance.day >= start, Attendance.day <= end)
                )
            }
            holidays: dict[tuple[str | None, date], str] = {
                (h.batch_id, h.day): h.name
                for h in db.scalars(select(Holiday).where(Holiday.day >= start, Holiday.day <= end))
            }
            leaves: dict[str, list[tuple[date, date]]] = {}
            for lv in db.scalars(
                select(Leave).where(
                    Leave.status == "approved", Leave.start <= end, Leave.end >= start
                )
            ):
                leaves.setdefault(lv.user_id, []).append((lv.start, lv.end))
            today = self.now_local().date()
            rows = []
            for u in users:
                b = u.batch
                class_days = set(b.days.split(","))
                d = max(start, u.enrollment_date)
                while d <= min(end, today):
                    a = recs.get((u.id, d))
                    if a is not None:
                        rows.append(_row(u, b, d, a.status, a.method, a.confidence, a.marked_at))
                    elif str(d.weekday()) in class_days:
                        if (b.id, d) in holidays or (None, d) in holidays:
                            rows.append(_row(u, b, d, "holiday", None, None, None))
                        elif any(s0 <= d <= e0 for s0, e0 in leaves.get(u.id, [])):
                            rows.append(_row(u, b, d, "leave", None, None, None))
                        elif d < today:
                            rows.append(_row(u, b, d, "absent", None, None, None))
                    d += timedelta(days=1)
            return sorted(rows, key=lambda r: (r["day"], r["full_name"]))

    def summary(
        self, start: date, end: date, batch_id: str | None = None, scope: set[str] | None = None
    ) -> dict:
        rows = self.records(start, end, batch_id, scope=scope)
        per_student: dict[str, dict] = {}
        per_day: dict[str, dict] = {}
        for r in rows:
            s = per_student.setdefault(
                r["user_id"],
                {
                    "user_id": r["user_id"],
                    "full_name": r["full_name"],
                    "batch": r["batch"],
                    "present": 0,
                    "late": 0,
                    "absent": 0,
                    "leave": 0,
                    "holiday": 0,
                },
            )
            s[r["status"]] += 1
            dd = per_day.setdefault(
                str(r["day"]),
                {
                    "day": str(r["day"]),
                    "present": 0,
                    "late": 0,
                    "absent": 0,
                    "leave": 0,
                    "holiday": 0,
                },
            )
            dd[r["status"]] += 1
        for s in per_student.values():
            total = s["present"] + s["late"] + s["absent"]
            s["attendance_pct"] = (
                round(100 * (s["present"] + s["late"]) / total, 1) if total else None
            )
        return {
            "from": str(start),
            "to": str(end),
            "students": sorted(per_student.values(), key=lambda s: s["full_name"]),
            "days": sorted(per_day.values(), key=lambda d: d["day"]),
        }

    def export_csv(
        self, start: date, end: date, batch_id: str | None = None, scope: set[str] | None = None
    ) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(
            [
                "day",
                "student",
                "email",
                "roll_no",
                "batch",
                "status",
                "method",
                "confidence",
                "marked_at",
            ]
        )
        for r in self.records(start, end, batch_id, scope=scope):
            w.writerow(
                [
                    r["day"],
                    _csv_safe(r["full_name"]),
                    _csv_safe(r["email"]),
                    _csv_safe(r["roll_no"] or ""),
                    _csv_safe(r["batch"]),
                    r["status"],
                    r["method"] or "",
                    r["confidence"] or "",
                    r["marked_at"] or "",
                ]
            )
        return buf.getvalue()

    def overview(self, scope: set[str] | None = None) -> dict:
        today = self.now_local().date()
        with self.sessions() as db:
            students = select(User).where(User.role == "student")
            if scope is not None:
                students = students.where(User.batch_id.in_(scope))
            users = list(db.scalars(students))
            ids = [u.id for u in users]
            today_counts = dict(
                db.execute(
                    select(Attendance.status, func.count())
                    .where(Attendance.day == today, Attendance.user_id.in_(ids))
                    .group_by(Attendance.status)
                ).all()
            )
            recent = db.execute(
                select(Attendance, User.full_name)
                .join(User, User.id == Attendance.user_id)
                .where(Attendance.user_id.in_(ids))
                .order_by(Attendance.marked_at.desc())
                .limit(10)
            ).all()
            n_batches = (
                len(scope)
                if scope is not None
                else db.scalar(select(func.count()).select_from(Batch))
            )
            pending_leaves = db.scalar(
                select(func.count())
                .select_from(Leave)
                .where(Leave.status == "pending", Leave.user_id.in_(ids))
            )
            holiday = self._holiday_any(db, today, scope)
        return {
            "students": len(users),
            "face_enrolled": sum(u.person_id is not None for u in users),
            "batches": n_batches,
            "pending_leaves": pending_leaves,
            "today": {
                "day": str(today),
                "present": today_counts.get("present", 0),
                "late": today_counts.get("late", 0),
                "holiday": holiday,
            },
            "recent": [
                {
                    "full_name": name,
                    "status": a.status,
                    "method": a.method,
                    "marked_at": a.marked_at.isoformat(),
                }
                for a, name in recent
            ],
        }

    # ---------- holidays ----------
    @staticmethod
    def _holiday(db: Session, batch_id: str, day: date) -> Holiday | None:
        return db.scalar(
            select(Holiday).where(
                Holiday.day == day, (Holiday.batch_id == batch_id) | Holiday.batch_id.is_(None)
            )
        )

    @staticmethod
    def _holiday_any(db: Session, day: date, scope: set[str] | None) -> str | None:
        hs = list(db.scalars(select(Holiday).where(Holiday.day == day)))
        for h in hs:
            if h.batch_id is None or scope is None or h.batch_id in scope:
                return h.name
        return None

    def list_holidays(self, start: date, end: date) -> list[Holiday]:
        with self.sessions() as db:
            return list(
                db.scalars(
                    select(Holiday)
                    .where(Holiday.day >= start, Holiday.day <= end)
                    .order_by(Holiday.day)
                )
            )

    def add_holiday(self, day: date, name: str, batch_id: str | None, actor: str) -> Holiday:
        with self.sessions.begin() as db:
            if batch_id and db.get(Batch, batch_id) is None:
                raise NotFound("batch")
            h = Holiday(day=day, name=name.strip(), batch_id=batch_id, created_by=actor)
            db.add(h)
            try:
                db.flush()
            except IntegrityError:
                raise ConflictError("holiday already exists for that day") from None
            return h

    def delete_holiday(self, holiday_id: int) -> None:
        with self.sessions.begin() as db:
            h = db.get(Holiday, holiday_id)
            if h is None:
                raise NotFound("holiday")
            db.delete(h)

    # ---------- leaves ----------
    def request_leave(self, user_id: str, start: date, end: date, reason: str) -> Leave:
        if end < start:
            raise RuleError("end date is before start date")
        if (end - start).days > 60:
            raise RuleError("leave can be at most 60 days")
        with self.sessions.begin() as db:
            lv = Leave(user_id=user_id, start=start, end=end, reason=reason.strip())
            db.add(lv)
            db.flush()
            return lv

    def my_leaves(self, user_id: str) -> list[Leave]:
        with self.sessions() as db:
            return list(
                db.scalars(
                    select(Leave).where(Leave.user_id == user_id).order_by(Leave.start.desc())
                )
            )

    def list_leaves(self, status: str | None, scope: set[str] | None) -> list[tuple[Leave, User]]:
        with self.sessions() as db:
            stmt = select(Leave, User).join(User, User.id == Leave.user_id).order_by(Leave.start)
            if status:
                stmt = stmt.where(Leave.status == status)
            if scope is not None:
                stmt = stmt.where(User.batch_id.in_(scope))
            return list(db.execute(stmt).all())

    def decide_leave(
        self, leave_id: int, approve: bool, actor: str, scope: set[str] | None
    ) -> Leave:
        with self.sessions.begin() as db:
            lv = db.get(Leave, leave_id)
            if lv is None:
                raise NotFound("leave")
            if scope is not None and lv.user.batch_id not in scope:
                raise ForbiddenError("student is not in your batches")
            lv.status = "approved" if approve else "rejected"
            lv.decided_by = actor
            return lv

    # ---------- teachers ----------
    def scope_for(self, user: User) -> set[str] | None:
        """Admin: None (sab). Teacher: assigned batch ids (khaali set = kuch nahi)."""
        if user.role == "admin":
            return None
        with self.sessions() as db:
            u = db.get(User, user.id)
            return {b.id for b in u.teaching}

    def list_teachers(self) -> list[User]:
        with self.sessions() as db:
            teachers = list(
                db.scalars(select(User).where(User.role == "teacher").order_by(User.full_name))
            )
            for t in teachers:
                t.batch_ids = [b.id for b in t.teaching]
            return teachers

    def set_teacher_batches(self, teacher_id: str, batch_ids: list[str]) -> list[str]:
        with self.sessions.begin() as db:
            t = self.get_user(db, teacher_id)
            if t.role != "teacher":
                raise RuleError("user is not a teacher")
            batches = list(db.scalars(select(Batch).where(Batch.id.in_(batch_ids))))
            if len(batches) != len(set(batch_ids)):
                raise NotFound("batch")
            t.teaching = batches
            return [b.id for b in batches]

    # ---------- bulk import ----------
    def import_students(self, rows: list[dict], dry_run: bool, actor: str) -> dict:
        """Saari rows validate; koi bhi error => KUCH import nahi (all-or-nothing)."""
        from pydantic import ValidationError

        from faceai.attendance.schemas import ImportRow

        errors: list[dict] = []
        clean: list[dict] = []
        with self.sessions() as db:
            batches = {b.name.strip().lower(): b.id for b in db.scalars(select(Batch))}
            existing = {e for (e,) in db.execute(select(User.email))}
        seen: set[str] = set()
        for i, raw in enumerate(rows, start=2):  # row 1 = header (Excel numbering)
            bname = (raw.get("batch") or "").strip()
            if bname and bname.lower() not in batches:  # har row ki SAARI galtiyan ek saath
                errors.append({"row": i, "field": "batch", "error": f"no batch named '{bname}'"})
            try:
                r = ImportRow(**raw)
            except ValidationError as e:
                for err in e.errors():
                    field = str(err["loc"][0]) if err["loc"] else "row"
                    msg = err["msg"].removeprefix("Value error, ")
                    errors.append({"row": i, "field": field, "error": msg})
                continue
            email = r.email.lower()
            if email in seen:
                errors.append({"row": i, "field": "email", "error": "duplicate in file"})
            elif email in existing:
                errors.append({"row": i, "field": "email", "error": "already registered"})
            seen.add(email)
            batch_id = batches.get(r.batch.strip().lower()) if r.batch else None
            clean.append({**r.model_dump(exclude={"batch"}), "email": email, "batch_id": batch_id})
        result = {
            "rows": len(rows),
            "valid": len(rows) - len({e["row"] for e in errors}),
            "errors": errors,
            "created": [],
        }
        if errors or dry_run:
            return result
        created = []
        with self.sessions.begin() as db:
            for data in clean:
                pw = secrets.token_urlsafe(9)
                u = User(
                    **data,
                    password_hash=hash_password(pw),
                    role="student",
                    enrollment_date=self.now_local().date(),
                )
                db.add(u)
                db.flush()
                created.append(
                    {
                        "id": u.id,
                        "email": u.email,
                        "full_name": u.full_name,
                        "temporary_password": pw,
                    }
                )
        logger.info("bulk import", extra={"students_created": len(created), "actor": actor})
        result["created"] = created
        return result


def _row(u: User, b: Batch, d: date, status, method, confidence, marked_at) -> dict:
    return {
        "user_id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "roll_no": u.roll_no,
        "batch_id": b.id,
        "batch": b.name,
        "day": d,
        "status": status,
        "method": method,
        "confidence": confidence,
        "marked_at": marked_at.isoformat() if marked_at else None,
    }


def _csv_safe(value: str) -> str:
    """CSV formula injection se bachao: "=HYPERLINK(...)" naam Excel mein code na chala de."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
