"""Phase B API contracts (OpenAPI /docs inhi se banta hai; React frontend inhi pe chalega)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from faceai.attendance.validators import check_password, clean_name, clean_phone, clean_roll

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class _InputRules(BaseModel):
    """Name / mobile / password / roll no rules (attendance/validators.py). Jis model mein jo
    field ho, us par lagte hain; None = field nahi bheja (optional update)."""

    @field_validator("full_name", check_fields=False)
    @classmethod
    def _name(cls, v):
        return None if v is None else clean_name(v)

    @field_validator("phone", check_fields=False)
    @classmethod
    def _phone(cls, v):
        return clean_phone(v)

    @field_validator("password", check_fields=False)
    @classmethod
    def _password(cls, v):
        return None if v is None else check_password(v)

    @field_validator("roll_no", check_fields=False)
    @classmethod
    def _roll(cls, v):
        return clean_roll(v)


class SignupIn(_InputRules):
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    consent: Literal[True] = Field(description="biometric (face) data store karne ki permission")


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


class FaceLoginIn(BaseModel):
    liveness_token: str = Field(description="/v1/liveness/verify se mila single-use token")


class FaceResetIn(_InputRules):
    """Forgot password: email + liveness wala chehra + naya password (signup jaise rules)."""

    email: str = Field(max_length=255)
    liveness_token: str = Field(description="/v1/liveness/verify se mila single-use token")
    password: str = Field(min_length=8, max_length=128, description="naya password")


class ChangePasswordIn(_InputRules):
    current_password: str = Field(max_length=128)
    password: str = Field(min_length=8, max_length=128, description="naya password")


class TempPasswordOut(BaseModel):
    user_id: str
    temporary_password: str = Field(description="sirf ek baar dikhaya jaata hai; user ko do")


class BatchRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    role: str
    full_name: str
    phone: str | None
    roll_no: str | None
    status: str
    batch_id: str | None
    face_enrolled: bool = False
    enrollment_date: date
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def of(cls, u) -> UserOut:
        out = cls.model_validate(u)
        out.face_enrolled = u.person_id is not None
        return out


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    similarity: float | None = None


class ProfileUpdate(_InputRules):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class StudentCreate(_InputRules):
    email: str = Field(pattern=EMAIL, max_length=255)
    full_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    roll_no: str | None = Field(default=None, max_length=30)
    batch_id: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    consent: Literal[True] = Field(description="student ne biometric consent diya (signed form)")


class StudentCreated(BaseModel):
    student: UserOut
    temporary_password: str = Field(description="sirf ek baar dikhaya jaata hai; student ko do")


class StudentUpdate(_InputRules):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    roll_no: str | None = Field(default=None, max_length=30)
    batch_id: str | None = None
    status: Literal["active", "inactive"] | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class BatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_time: str = Field(pattern=HHMM, examples=["09:00"])
    end_time: str = Field(pattern=HHMM, examples=["10:00"])
    days: str = Field(default="0,1,2,3,4", pattern=r"^[0-6](,[0-6])*$", description="Mon=0..Sun=6")
    late_after_min: int = Field(default=10, ge=0, le=1440)
    open_before_min: int = Field(default=15, ge=0, le=1440)

    @field_validator("end_time")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class BatchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_time: str | None = Field(default=None, pattern=HHMM)
    end_time: str | None = Field(default=None, pattern=HHMM)
    days: str | None = Field(default=None, pattern=r"^[0-6](,[0-6])*$")
    late_after_min: int | None = Field(default=None, ge=0, le=1440)
    open_before_min: int | None = Field(default=None, ge=0, le=1440)


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    start_time: str
    end_time: str
    days: str
    late_after_min: int
    open_before_min: int
    student_count: int = 0


class MarkOut(BaseModel):
    user_id: str
    full_name: str
    status: str
    reason: str
    confidence: float | None = None


class ScanOut(BaseModel):
    faces: int = Field(description="faces detected in the frame")
    unknown: int = Field(description="faces not matching any enrolled student")
    results: list[MarkOut]


class SelfMarkIn(BaseModel):
    liveness_token: str


class ManualIn(BaseModel):
    user_id: str
    day: date | None = Field(default=None, description="default: aaj (local timezone)")
    status: Literal["present", "late", "absent"]


class RecordOut(BaseModel):
    user_id: str
    full_name: str
    email: str
    roll_no: str | None
    batch_id: str
    batch: str
    day: date
    status: str
    method: str | None
    confidence: float | None
    marked_at: str | None


# ---------- bulk import (#4) ----------
class ImportRow(_InputRules):
    """Ek CSV row. Same rules jaise signup/admin create (validators.py)."""

    full_name: str = Field(max_length=100)
    email: str = Field(pattern=EMAIL, max_length=255)
    phone: str | None = None
    roll_no: str | None = Field(default=None, max_length=30)
    batch: str | None = Field(default=None, max_length=100, description="batch NAME (not id)")

    @field_validator("batch")
    @classmethod
    def _blank_batch(cls, v):
        return v.strip() or None if v else None


class ImportResult(BaseModel):
    rows: int
    valid: int
    errors: list[dict]
    created: list[dict] = Field(description="temporary passwords: shown ONCE")


# ---------- teachers (#7) ----------
class TeacherCreate(_InputRules):
    email: str = Field(pattern=EMAIL, max_length=255)
    full_name: str = Field(max_length=100)
    phone: str | None = None
    password: str | None = Field(default=None, max_length=128)
    batch_ids: list[str] = Field(default_factory=list)


class TeacherOut(UserOut):
    batch_ids: list[str] = []


class BatchIdsIn(BaseModel):
    batch_ids: list[str]


# ---------- holidays + leave (#8) ----------
class HolidayIn(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=100)
    batch_id: str | None = Field(default=None, description="null = all batches")


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    day: date
    name: str
    batch_id: str | None


class LeaveIn(BaseModel):
    start: date
    end: date
    reason: str = Field(min_length=3, max_length=500)


class LeaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: str
    start: date
    end: date
    reason: str
    status: str
    full_name: str | None = None


class LeaveDecision(BaseModel):
    approve: bool
