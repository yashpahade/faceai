"""API contracts (request/response shapes). /docs (OpenAPI) inhi se auto-generate hota hai."""

from pydantic import BaseModel, Field


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Omkar"])


class PersonOut(BaseModel):
    id: str
    name: str
    created_at: str
    num_faces: int = 0


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
    match: MatchOut | None = Field(description="null => unknown person")
    candidates: list[MatchOut]


class RecognizeOut(BaseModel):
    faces: list[FaceOut]
    threshold: float
    model_id: str
    timings_ms: dict[str, float]
