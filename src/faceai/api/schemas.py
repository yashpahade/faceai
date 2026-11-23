"""API contracts (request/response shapes). /docs (OpenAPI) inhi se auto-generate hota hai."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Omkar"])
    consent: Literal[True] = Field(
        description="Person ne biometric data store karne ki explicit permission di hai (zaroori)"
    )


class PersonOut(BaseModel):
    id: str
    name: str
    created_at: str
    num_faces: int = 0
    consent_at: str | None = None


class DeleteOut(BaseModel):
    """Deletion receipt: kya delete hua (proof of deletion audit log mein bhi)."""

    person_id: str
    deleted_embeddings: int


class AuditOut(BaseModel):
    id: int
    ts: str
    action: str
    actor: str
    person_id: str | None
    request_id: str | None
    detail: dict[str, Any]


class LivenessOut(BaseModel):
    live: bool
    score: float
    method: str


class QualityOut(BaseModel):
    det_score: float
    face_px: float
    sharpness: float
    yaw_ratio: float
    issues: list[str]


class EnrollOut(BaseModel):
    embedding_id: int
    person_id: str
    quality: QualityOut


class MatchOut(BaseModel):
    person_id: str
    name: str
    similarity: float = Field(description="cosine similarity -1..1 (probability NAHI hai)")


class FaceOut(BaseModel):
    bbox: list[float] = Field(description="[x1, y1, x2, y2] pixels")
    det_score: float
    match: MatchOut | None = Field(description="null => unknown person (ya liveness fail)")
    candidates: list[MatchOut]
    liveness: LivenessOut | None = Field(
        default=None, description="null => liveness check NAHI hua (off), pass nahi"
    )


class RecognizeOut(BaseModel):
    faces: list[FaceOut]
    threshold: float
    model_id: str
    timings_ms: dict[str, float]
