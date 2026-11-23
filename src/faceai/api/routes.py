"""
v1 REST endpoints.

`/v1/` prefix = API versioning. Kal response format badalna ho to /v2 banao; purane clients
(mobile apps jo update nahi hue) /v1 pe chalte rahenge.

Endpoints `def` hain (`async def` nahi): ML inference CPU/GPU-bound blocking kaam hai. FastAPI
`def` endpoints ko threadpool mein chalata hai, isliye event loop block nahi hota.
"""

from contextlib import contextmanager
from dataclasses import asdict

import cv2
import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from faceai.api.schemas import (
    AuditOut,
    ChallengeOut,
    DeleteOut,
    EnrollOut,
    LivenessVerifyOut,
    PersonCreate,
    PersonOut,
    RecognizeOut,
)
from faceai.monitoring import metrics as m
from faceai.security import auth
from faceai.security.challenge import CHALLENGE_TTL_S, TOKEN_TTL_S
from faceai.service import EnrollmentError, NotFoundError, RecognitionService
from faceai.serving.limiter import OverloadedError
from faceai.vision.preprocess import decode_image


def require_api_key(request: Request) -> str:
    """Har /v1 call pe check. Valid key => `request.state.actor` (audit ke liye)."""
    s = request.app.state.settings
    if not s.auth_required:
        request.state.actor = "anonymous"
        return request.state.actor
    actor = auth.verify(request.headers.get("X-API-Key"), s.api_key_hash_list)
    if actor is None:
        raise HTTPException(
            401, "invalid or missing API key", headers={"WWW-Authenticate": "ApiKey"}
        )
    request.state.actor = actor
    return actor


router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])
# Bina login ke chahiye (face login se PEHLE liveness hota hai). Abuse se rate limit bachata hai.
public_router = APIRouter(prefix="/v1")


def get_service(request: Request) -> RecognitionService:
    svc = getattr(request.app.state, "service", None)
    if svc is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "model not loaded")
    return svc


def read_image(request: Request, file: UploadFile) -> np.ndarray:
    limit = request.app.state.settings.max_upload_bytes
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "image too large")
    img = decode_image(data)  # EXIF orientation applied (phone photos)
    if img is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "could not decode image (jpg/png?)")
    return img


def observe_recognition(request: Request, img: np.ndarray, res) -> None:
    """Model behaviour metrics + drift features (Phase 6). Sirf numbers, koi image/ID nahi."""
    m.INFERENCE_LATENCY.labels("inference").observe(res.timings_ms["inference"] / 1000)
    m.INFERENCE_LATENCY.labels("search").observe(res.timings_ms["search"] / 1000)
    m.FACES_PER_IMAGE.observe(len(res.faces))
    drift = request.app.state.drift
    if res.faces:
        drift.observe("brightness", float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean()))
    for f in res.faces:
        m.RECOGNITIONS.labels("match" if f.match else "unknown").inc()
        m.DET_SCORE.observe(f.det_score)
        drift.observe("det_score", f.det_score)
        x1, y1, x2, y2 = f.bbox
        drift.observe("face_px", min(x2 - x1, y2 - y1))
        if f.candidates:  # gallery khaali ho to similarity ka matlab nahi
            m.TOP1_SIMILARITY.observe(f.candidates[0].similarity)
            drift.observe("top1_similarity", f.candidates[0].similarity)


@contextmanager
def inference_slot(request: Request):
    """Admission control: slot nahi mila => 503 + Retry-After (client ko pata ho kab retry kare)."""
    try:
        with request.app.state.limiter.slot():
            yield
    except OverloadedError:
        m.REJECTED.inc()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "server busy", headers={"Retry-After": "1"}
        ) from None


@router.post("/persons", response_model=PersonOut, status_code=201, tags=["persons"])
def create_person(
    body: PersonCreate, request: Request, svc: RecognitionService = Depends(get_service)
):
    return asdict(svc.create_person(body.name.strip(), body.consent, request.state.actor))


@router.get("/persons", response_model=list[PersonOut], tags=["persons"])
def list_persons(svc: RecognitionService = Depends(get_service)):
    return [asdict(p) for p in svc.list_persons()]


@router.get("/persons/{person_id}", response_model=PersonOut, tags=["persons"])
def get_person(person_id: str, svc: RecognitionService = Depends(get_service)):
    try:
        return asdict(svc.get_person(person_id))
    except NotFoundError:
        raise HTTPException(404, "person not found") from None


@router.delete("/persons/{person_id}", response_model=DeleteOut, tags=["persons"])
def delete_person(person_id: str, request: Request, svc: RecognitionService = Depends(get_service)):
    """Right to be forgotten: DB + index se hatao, receipt lauto, audit mein proof."""
    try:
        n = svc.delete_person(person_id, request.state.actor)
    except NotFoundError:
        raise HTTPException(404, "person not found") from None
    return {"person_id": person_id, "deleted_embeddings": n}


@router.get("/audit", response_model=list[AuditOut], tags=["audit"])
def audit_log(
    person_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    svc: RecognitionService = Depends(get_service),
):
    return svc.db.list_audit(person_id, limit)


@router.post(
    "/persons/{person_id}/faces", response_model=EnrollOut, status_code=201, tags=["persons"]
)
def enroll_face(
    person_id: str,
    request: Request,
    file: UploadFile = File(...),
    svc: RecognitionService = Depends(get_service),
):
    img = read_image(request, file)
    try:
        with inference_slot(request):
            emb_id, quality = svc.enroll_face(person_id, img, request.state.actor)
    except NotFoundError:
        raise HTTPException(404, "person not found") from None
    except EnrollmentError as e:
        m.ENROLLMENTS.labels("rejected").inc()
        detail = {"message": str(e)}
        if e.quality:
            detail["quality"] = asdict(e.quality)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail) from None
    m.ENROLLMENTS.labels("ok").inc()
    return {"embedding_id": emb_id, "person_id": person_id, "quality": asdict(quality)}


@router.post("/recognize", response_model=RecognizeOut, tags=["recognition"])
def recognize(
    request: Request,
    file: UploadFile = File(...),
    svc: RecognitionService = Depends(get_service),
):
    img = read_image(request, file)
    with inference_slot(request):
        res = svc.recognize(img)
    observe_recognition(request, img, res)
    return {
        "faces": [asdict(f) for f in res.faces],
        "threshold": svc.s.match_threshold,
        "model_id": svc.engine.model_id,
        "timings_ms": res.timings_ms,
    }


# ---------- Active liveness (Phase A) ----------
@public_router.post("/liveness/challenge", response_model=ChallengeOut, tags=["liveness"])
def liveness_challenge(request: Request):
    """Random head-movement steps. Har step ke liye ek frame bhejo /liveness/verify pe."""
    c = request.app.state.challenges.create()
    return {"challenge_id": c.id, "steps": c.steps, "expires_in_s": CHALLENGE_TTL_S}


@public_router.post("/liveness/verify", response_model=LivenessVerifyOut, tags=["liveness"])
def liveness_verify(
    request: Request,
    challenge_id: str = Form(...),
    frames: list[UploadFile] = File(..., description="steps ke order mein, ek frame per step"),
    svc: RecognitionService = Depends(get_service),
):
    if len(frames) > 5:
        raise HTTPException(422, "too many frames")
    with inference_slot(request):
        faces = [svc.engine.analyze(read_image(request, f), svc.s.det_threshold) for f in frames]
    r = request.app.state.challenges.verify(challenge_id, faces)
    m.LIVENESS_CHECKS.labels("pass" if r.live else "fail").inc()
    return {"live": r.live, "reason": r.reason, "token": r.token, "token_ttl_s": TOKEN_TTL_S}
