"""
RecognitionService - business logic. HTTP aur ONNX dono se independent.

Layers (har layer sirf apne neeche wali ko jaanti hai):
    api/  (HTTP, validation)  ->  service.py (rules)  ->  vision/ (ML) + store/ (DB, index)
Fayda: engine ko fake se replace karke service ko bina GPU/model ke test kar sakte hain.
"""

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from faceai.config import Settings
from faceai.store.db import Database, Person
from faceai.store.index import VectorIndex
from faceai.vision.quality import QualityReport, assess
from faceai.vision.types import FaceEngineProtocol

logger = logging.getLogger(__name__)


class EnrollmentError(Exception):
    """User ki photo enrollment ke layak nahi (no face, multiple faces, poor quality)."""

    def __init__(self, message: str, quality: QualityReport | None = None):
        super().__init__(message)
        self.quality = quality


class NotFoundError(Exception):
    pass


@dataclass
class Match:
    person_id: str
    name: str
    similarity: float


@dataclass
class FaceResult:
    bbox: list[float]
    det_score: float
    match: Match | None  # None => unknown (threshold se neeche)
    candidates: list[Match] = field(default_factory=list)


@dataclass
class RecognitionResult:
    faces: list[FaceResult]
    timings_ms: dict[str, float]


class RecognitionService:
    def __init__(self, engine: FaceEngineProtocol, db: Database, settings: Settings):
        self.engine = engine
        self.db = db
        self.s = settings
        self.index = VectorIndex(engine.dim)
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        ids, pids, vecs = self.db.load_embeddings(self.engine.model_id)
        self.index.add(ids, pids, vecs)
        stale = self.db.count_other_models(self.engine.model_id)
        logger.info("index built: %d embeddings for model %s", len(ids), self.engine.model_id)
        if stale:
            logger.warning(
                "%d embeddings belong to a different model and are NOT searchable. "
                "Re-enroll those persons (model upgrade).",
                stale,
            )

    # ---------- persons ----------
    def create_person(self, name: str) -> Person:
        return self.db.create_person(name)

    def get_person(self, person_id: str) -> Person:
        p = self.db.get_person(person_id)
        if p is None:
            raise NotFoundError(person_id)
        return p

    def list_persons(self) -> list[Person]:
        return self.db.list_persons()

    def delete_person(self, person_id: str) -> None:
        self.get_person(person_id)
        removed = self.db.delete_person(person_id)
        self.index.remove(removed)
        logger.info("deleted person %s (%d embeddings)", person_id, len(removed))

    # ---------- enrollment ----------
    def enroll_face(self, person_id: str, image_bgr: np.ndarray) -> tuple[int, QualityReport]:
        self.get_person(person_id)
        faces = self.engine.analyze(image_bgr, self.s.det_threshold)
        if not faces:
            raise EnrollmentError("no face detected")
        if len(faces) > 1:
            raise EnrollmentError(f"{len(faces)} faces detected; enrollment needs exactly one")
        face = faces[0]
        quality = assess(
            face,
            face.aligned,
            min_det_score=self.s.enroll_min_det_score,
            min_face_px=self.s.enroll_min_face_px,
            min_sharpness=self.s.enroll_min_sharpness,
        )
        if not quality.ok:
            raise EnrollmentError("poor image quality: " + "; ".join(quality.issues), quality)

        emb_id = self.db.add_embedding(
            person_id, self.engine.model_id, face.embedding, face.det_score, quality.sharpness
        )
        self.index.add(
            np.array([emb_id]), np.array([person_id], dtype=object), face.embedding[None, :]
        )
        logger.info(
            "enrolled face",
            extra={
                "person_id": person_id,
                "embedding_id": emb_id,
                "det_score": round(face.det_score, 3),
            },
        )
        return emb_id, quality

    # ---------- recognition ----------
    def recognize(self, image_bgr: np.ndarray, top_k: int = 3) -> RecognitionResult:
        t0 = time.perf_counter()
        faces = self.engine.analyze(image_bgr, self.s.det_threshold)
        t1 = time.perf_counter()

        results: list[FaceResult] = []
        for f in faces:
            ranked = self.index.search_persons(f.embedding)[:top_k]
            names = self.db.get_names([pid for pid, _ in ranked])
            cands = [Match(pid, names[pid], round(sim, 4)) for pid, sim in ranked if pid in names]
            best = cands[0] if cands and cands[0].similarity >= self.s.match_threshold else None
            results.append(
                FaceResult(
                    bbox=[round(float(v), 1) for v in f.bbox],
                    det_score=round(f.det_score, 4),
                    match=best,
                    candidates=cands,
                )
            )
        t2 = time.perf_counter()
        timings = {"inference": round((t1 - t0) * 1000, 2), "search": round((t2 - t1) * 1000, 2)}
        logger.info(
            "recognized %d faces",
            len(results),
            extra={
                "faces": len(results),
                "identified": sum(r.match is not None for r in results),
                **timings,
            },
        )
        return RecognitionResult(results, timings)
