"""
Phase B REST API: /v1/auth, /v1/me, /v1/admin.

Auth: `Authorization: Bearer <JWT>`. RBAC: `require_admin` dependency admin routes pe.
(Phase 7 wali X-API-Key machine clients ke liye /v1 biometric routes pe rehti hai.)
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from faceai.api.routes import inference_slot, read_image
from faceai.attendance import schemas as sc
from faceai.attendance.models import User
from faceai.attendance.security import decode_token
from faceai.attendance.service import (
    AttendanceService,
    AuthError,
    ConflictError,
    NotFound,
    RuleError,
)
from faceai.service import EnrollmentError

router = APIRouter(prefix="/v1")
bearer = HTTPBearer(auto_error=False)


def get_svc(request: Request) -> AttendanceService:
    svc = getattr(request.app.state, "attendance", None)
    if svc is None:
        raise HTTPException(503, "service not ready")
    return svc


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    svc: AttendanceService = Depends(get_svc),
) -> User:
    claims = decode_token(creds.credentials, svc.jwt_secret) if creds else None
    if claims is None:
        raise HTTPException(401, "not authenticated", headers={"WWW-Authenticate": "Bearer"})
    with svc.sessions() as db:
        u = db.get(User, claims["sub"])
    # token_version mismatch = password badla / account band -> purana token bekaar
    if u is None or u.status != "active" or u.token_version != claims.get("ver"):
        raise HTTPException(401, "session expired", headers={"WWW-Authenticate": "Bearer"})
    request.state.actor = f"user:{u.id[:8]}"
    return u


def require_admin(u: User = Depends(current_user)) -> User:
    if u.role != "admin":
        raise HTTPException(403, "admin only")
    return u


def _err(e: Exception):
    if isinstance(e, NotFound):
        return HTTPException(404, f"{e} not found")
    if isinstance(e, ConflictError):
        return HTTPException(409, str(e))
    if isinstance(e, AuthError):
        return HTTPException(401, str(e))
    if isinstance(e, RuleError):
        return HTTPException(422, str(e))
    if isinstance(e, EnrollmentError):
        detail = {"message": str(e)}
        if e.quality:
            from dataclasses import asdict

            detail["quality"] = asdict(e.quality)
        return HTTPException(422, detail)
    raise e


def _range(start: date | None, end: date | None, svc: AttendanceService) -> tuple[date, date]:
    end = end or svc.now_local().date()
    start = start or end - timedelta(days=29)
    if start > end or (end - start).days > 366:
        raise HTTPException(422, "invalid date range (max 1 year)")
    return start, end


# ================= auth (public) =================
@router.post("/auth/signup", response_model=sc.TokenOut, status_code=201, tags=["auth"])
def signup(body: sc.SignupIn, svc: AttendanceService = Depends(get_svc)):
    """Student account. Next: POST /v1/me/face (photo) -> face login possible."""
    try:
        u, token = svc.signup(body.email, body.password, body.full_name, body.phone)
    except ConflictError as e:
        raise _err(e) from None
    return {"access_token": token, "user": sc.UserOut.of(u)}


@router.post("/auth/login", response_model=sc.TokenOut, tags=["auth"])
def login(body: sc.LoginIn, svc: AttendanceService = Depends(get_svc)):
    try:
        u, token = svc.login(body.email, body.password)
    except AuthError as e:
        raise _err(e) from None
    return {"access_token": token, "user": sc.UserOut.of(u)}


@router.post("/auth/face-login", response_model=sc.TokenOut, tags=["auth"])
def face_login(body: sc.FaceLoginIn, request: Request, svc: AttendanceService = Depends(get_svc)):
    """Flow: /v1/liveness/challenge -> /v1/liveness/verify (frames) -> yahan token bhejo.
    Face wahi identify hota hai jisne liveness pass kiya (alag photo nahi bhej sakte)."""
    emb = request.app.state.challenges.consume_token(body.liveness_token)
    if emb is None:
        raise HTTPException(401, "invalid or expired liveness token")
    try:
        u, token, sim = svc.face_login(emb)
    except AuthError as e:
        raise _err(e) from None
    return {"access_token": token, "user": sc.UserOut.of(u), "similarity": round(sim, 4)}


# ================= me (student/admin) =================
@router.get("/me", response_model=sc.UserOut, tags=["me"])
def me(u: User = Depends(current_user)):
    return sc.UserOut.of(u)


@router.patch("/me", response_model=sc.UserOut, tags=["me"])
def update_me(body: sc.ProfileUpdate, u: User = Depends(current_user), svc=Depends(get_svc)):
    return sc.UserOut.of(svc.update_user(u.id, body.model_dump(exclude_none=True)))


@router.post("/me/face", tags=["me"], status_code=201)
def enroll_my_face(
    request: Request,
    file: UploadFile = File(...),
    replace: bool = Query(False, description="true = purana face data hata ke naya (re-enroll)"),
    u: User = Depends(current_user),
    svc: AttendanceService = Depends(get_svc),
):
    img = read_image(request, file)
    try:
        with inference_slot(request):
            emb_id, quality = svc.enroll_face(u.id, img, request.state.actor, replace)
    except (EnrollmentError, NotFound) as e:
        raise _err(e) from None
    return {"embedding_id": emb_id, "quality_issues": quality.issues}


@router.post("/me/attendance", response_model=sc.MarkOut, tags=["me"])
def mark_my_attendance(
    body: sc.SelfMarkIn,
    request: Request,
    u: User = Depends(current_user),
    svc: AttendanceService = Depends(get_svc),
):
    emb = request.app.state.challenges.consume_token(body.liveness_token)
    if emb is None:
        raise HTTPException(401, "invalid or expired liveness token")
    return svc.mark_self(u.id, emb).__dict__


@router.get("/me/attendance", response_model=list[sc.RecordOut], tags=["me"])
def my_attendance(
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    u: User = Depends(current_user),
    svc: AttendanceService = Depends(get_svc),
):
    a, b = _range(start, end, svc)
    return svc.records(a, b, user_id=u.id)


# ================= admin =================
@router.get("/admin/overview", tags=["admin"])
def overview(_: User = Depends(require_admin), svc: AttendanceService = Depends(get_svc)):
    return svc.overview()


@router.get("/admin/students", response_model=list[sc.UserOut], tags=["admin"])
def list_students(
    q: str | None = Query(None, max_length=100),
    batch_id: str | None = None,
    status: str | None = None,
    _: User = Depends(require_admin),
    svc: AttendanceService = Depends(get_svc),
):
    return [sc.UserOut.of(u) for u in svc.list_students(q, batch_id, status)]


@router.post("/admin/students", response_model=sc.StudentCreated, status_code=201, tags=["admin"])
def create_student(body: sc.StudentCreate, _: User = Depends(require_admin), svc=Depends(get_svc)):
    try:
        u, pw = svc.create_student(body.model_dump(exclude={"consent"}), "admin")
    except (ConflictError, NotFound) as e:
        raise _err(e) from None
    return {"student": sc.UserOut.of(u), "temporary_password": pw}


@router.get("/admin/students/{user_id}", response_model=sc.UserOut, tags=["admin"])
def get_student(user_id: str, _: User = Depends(require_admin), svc=Depends(get_svc)):
    with svc.sessions() as db:
        u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "student not found")
    return sc.UserOut.of(u)


@router.patch("/admin/students/{user_id}", response_model=sc.UserOut, tags=["admin"])
def update_student(
    user_id: str, body: sc.StudentUpdate, _: User = Depends(require_admin), svc=Depends(get_svc)
):
    try:
        return sc.UserOut.of(svc.update_user(user_id, body.model_dump(exclude_unset=True)))
    except NotFound as e:
        raise _err(e) from None


@router.delete("/admin/students/{user_id}", tags=["admin"])
def delete_student(
    user_id: str, request: Request, _: User = Depends(require_admin), svc=Depends(get_svc)
):
    try:
        n = svc.delete_user(user_id, request.state.actor)
    except NotFound as e:
        raise _err(e) from None
    return {"user_id": user_id, "deleted_embeddings": n}


@router.post("/admin/students/{user_id}/face", status_code=201, tags=["admin"])
def enroll_student_face(
    user_id: str,
    request: Request,
    file: UploadFile = File(...),
    replace: bool = False,
    _: User = Depends(require_admin),
    svc: AttendanceService = Depends(get_svc),
):
    img = read_image(request, file)
    try:
        with inference_slot(request):
            emb_id, quality = svc.enroll_face(user_id, img, request.state.actor, replace)
    except (EnrollmentError, NotFound) as e:
        raise _err(e) from None
    return {"embedding_id": emb_id, "quality_issues": quality.issues}


@router.get("/admin/batches", response_model=list[sc.BatchOut], tags=["admin"])
def list_batches(_: User = Depends(require_admin), svc=Depends(get_svc)):
    return [
        {**sc.BatchOut.model_validate(b).model_dump(), "student_count": n}
        for b, n in svc.list_batches()
    ]


@router.post("/admin/batches", response_model=sc.BatchOut, status_code=201, tags=["admin"])
def create_batch(body: sc.BatchIn, _: User = Depends(require_admin), svc=Depends(get_svc)):
    try:
        return svc.create_batch(body.model_dump())
    except ConflictError as e:
        raise _err(e) from None


@router.patch("/admin/batches/{batch_id}", response_model=sc.BatchOut, tags=["admin"])
def update_batch(
    batch_id: str, body: sc.BatchUpdate, _: User = Depends(require_admin), svc=Depends(get_svc)
):
    try:
        return svc.update_batch(batch_id, body.model_dump(exclude_unset=True))
    except NotFound as e:
        raise _err(e) from None


@router.delete("/admin/batches/{batch_id}", status_code=204, tags=["admin"])
def delete_batch(batch_id: str, _: User = Depends(require_admin), svc=Depends(get_svc)):
    try:
        svc.delete_batch(batch_id)
    except NotFound as e:
        raise _err(e) from None
    return Response(status_code=204)


@router.post("/admin/attendance/scan", response_model=sc.ScanOut, tags=["admin"])
def scan(
    request: Request,
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    svc: AttendanceService = Depends(get_svc),
):
    """Live camera frame: pehchaane gaye saare students mark (admin supervised kiosk)."""
    img = read_image(request, file)
    with inference_slot(request):
        out = svc.scan(img, f"admin:{admin.id[:8]}")
    return {**out, "results": [r.__dict__ for r in out["results"]]}


@router.post("/admin/attendance/manual", tags=["admin"])
def manual(body: sc.ManualIn, admin: User = Depends(require_admin), svc=Depends(get_svc)):
    day = body.day or svc.now_local().date()
    try:
        svc.manual(body.user_id, day, body.status, f"admin:{admin.id[:8]}")
    except (NotFound, RuleError) as e:
        raise _err(e) from None
    return {"user_id": body.user_id, "day": str(day), "status": body.status}


@router.get("/admin/attendance", response_model=list[sc.RecordOut], tags=["admin"])
def attendance(
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    batch_id: str | None = None,
    user_id: str | None = None,
    _: User = Depends(require_admin),
    svc: AttendanceService = Depends(get_svc),
):
    a, b = _range(start, end, svc)
    return svc.records(a, b, batch_id, user_id)


@router.get("/admin/reports/summary", tags=["admin"])
def report_summary(
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    batch_id: str | None = None,
    _: User = Depends(require_admin),
    svc: AttendanceService = Depends(get_svc),
):
    a, b = _range(start, end, svc)
    return svc.summary(a, b, batch_id)


@router.get("/admin/reports/export.csv", tags=["admin"])
def report_csv(
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    batch_id: str | None = None,
    _: User = Depends(require_admin),
    svc: AttendanceService = Depends(get_svc),
):
    a, b = _range(start, end, svc)
    return Response(
        svc.export_csv(a, b, batch_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="attendance_{a}_{b}.csv"'},
    )
