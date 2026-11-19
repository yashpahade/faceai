"""
v1 REST endpoints.

`/v1/` prefix = API versioning. Kal response format badalna ho to /v2 banao; purane clients
(mobile apps jo update nahi hue) /v1 pe chalte rahenge.

Endpoints `def` hain (`async def` nahi): ML inference CPU/GPU-bound blocking kaam hai. FastAPI
`def` endpoints ko threadpool mein chalata hai, isliye event loop block nahi hota.
"""

from dataclasses import asdict

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from faceai.api.schemas import EnrollOut, PersonCreate, PersonOut, RecognizeOut
from faceai.service import EnrollmentError, NotFoundError, RecognitionService

router = APIRouter(prefix="/v1")


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
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "could not decode image (jpg/png?)")
    return img


@router.post("/persons", response_model=PersonOut, status_code=201, tags=["persons"])
def create_person(body: PersonCreate, svc: RecognitionService = Depends(get_service)):
    return asdict(svc.create_person(body.name.strip()))


@router.get("/persons", response_model=list[PersonOut], tags=["persons"])
def list_persons(svc: RecognitionService = Depends(get_service)):
    return [asdict(p) for p in svc.list_persons()]


@router.get("/persons/{person_id}", response_model=PersonOut, tags=["persons"])
def get_person(person_id: str, svc: RecognitionService = Depends(get_service)):
    try:
        return asdict(svc.get_person(person_id))
    except NotFoundError:
        raise HTTPException(404, "person not found") from None


@router.delete("/persons/{person_id}", status_code=204, tags=["persons"])
def delete_person(person_id: str, svc: RecognitionService = Depends(get_service)):
    try:
        svc.delete_person(person_id)
    except NotFoundError:
        raise HTTPException(404, "person not found") from None
    return Response(status_code=204)


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
        emb_id, quality = svc.enroll_face(person_id, img)
    except NotFoundError:
        raise HTTPException(404, "person not found") from None
    except EnrollmentError as e:
        detail = {"message": str(e)}
        if e.quality:
            detail["quality"] = asdict(e.quality)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail) from None
    return {"embedding_id": emb_id, "person_id": person_id, "quality": asdict(quality)}


@router.post("/recognize", response_model=RecognizeOut, tags=["recognition"])
def recognize(
    request: Request,
    file: UploadFile = File(...),
    svc: RecognitionService = Depends(get_service),
):
    img = read_image(request, file)
    res = svc.recognize(img)
    return {
        "faces": [asdict(f) for f in res.faces],
        "threshold": svc.s.match_threshold,
        "model_id": svc.engine.model_id,
        "timings_ms": res.timings_ms,
    }
