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
from faceai.logging import request_id_ctx
from faceai.security.liveness import LivenessChecker
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
    match: Match | None  # None => unknown (threshold se neeche) ya liveness fail
    candidates: list[Match] = field(default_factory=list)
    liveness: dict | None = None  # None => liveness check nahi hua (off)


@dataclass
class RecognitionResult:
    faces: list[FaceResult]
    timings_ms: dict[str, float]


class RecognitionService:
    def __init__(
        self,
        engine: FaceEngineProtocol,
        db: Database,
        settings: Settings,
        liveness: LivenessChecker | None = None,
    ):
        self.engine = engine
        self.db = db
        self.s = settings
        self.liveness = liveness
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

    def _audit(self, action: str, actor: str, person_id: str | None, **detail) -> None:
        # Sirf IDs aur counts. Naam, image ya vector audit mein KABHI nahi.
        self.db.add_audit(action, actor, person_id, request_id_ctx.get(), detail)

    # ---------- persons ----------
    def create_person(self, name: str, consent: bool, actor: str = "anonymous") -> Person:
        p = self.db.create_person(name, consent=consent)
        self._audit("person.create", actor, p.id, consent=True)
        return p

    def get_person(self, person_id: str) -> Person:
        p = self.db.get_person(person_id)
        if p is None:
            raise NotFoundError(person_id)
        return p

    def list_persons(self) -> list[Person]:
        return self.db.list_persons()

    def delete_person(self, person_id: str, actor: str = "anonymous") -> int:
        self.get_person(person_id)
        removed = self.db.delete_person(person_id)
        self.index.remove(removed)  # DB ke saath index se bhi, warna delete ke baad bhi match hota
        self._audit("person.delete", actor, person_id, deleted_embeddings=len(removed))
        logger.info("deleted person %s (%d embeddings)", person_id, len(removed))
        return len(removed)

    def purge_expired(self, days: int, actor: str = "system:retention") -> int:
        removed = self.db.purge_embeddings_older_than(days)
        self.index.remove(removed)
        if removed:
            self._audit("retention.purge", actor, None, days=days, deleted_embeddings=len(removed))
            logger.info("retention: purged %d embeddings older than %d days", len(removed), days)
        return len(removed)

    def _check_liveness(self, image_bgr: np.ndarray, face) -> dict | None:
        if self.liveness is None:
            return None
        r = self.liveness.check(image_bgr, face.bbox)
        return {"live": r.live, "score": round(r.score, 4), "method": r.method}

    # ---------- enrollment ----------
    def enroll_face(
        self, person_id: str, image_bgr: np.ndarray, actor: str = "anonymous"
    ) -> tuple[int, QualityReport]:
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
        live = self._check_liveness(image_bgr, face)
        if live is not None and not live["live"]:
            # Spoof attempt khud audit-worthy hai
            self._audit("face.enroll_spoof_rejected", actor, person_id, score=live["score"])
            raise EnrollmentError("liveness check failed (possible photo/screen spoof)")

        emb_id = self.db.add_embedding(
            person_id, self.engine.model_id, face.embedding, face.det_score, quality.sharpness
        )
        self.index.add(
            np.array([emb_id]), np.array([person_id], dtype=object), face.embedding[None, :]
        )
        self._audit("face.enroll", actor, person_id, embedding_id=emb_id)
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
            live = self._check_liveness(image_bgr, f)
            if live is not None and not live["live"]:
                best, cands = None, []  # spoof pe identity mat batao
            results.append(
                FaceResult(
                    bbox=[round(float(v), 1) for v in f.bbox],
                    det_score=round(f.det_score, 4),
                    match=best,
                    candidates=cands,
                    liveness=live,
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
