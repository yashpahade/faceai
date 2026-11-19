"""
SQLite repository = SOURCE OF TRUTH.

Legacy: FAISS index + pickle metadata alag-alag files -> ek save ho, doosra crash ho jaye => desync.
Yahan: embeddings bhi SQLite mein (BLOB). FAISS sirf ek fast search CACHE hai jo startup pe yahin se
rebuild hota hai. SQLite transactions atomic hain -> data kabhi aadha-adhura nahi.

Production mein ye Postgres (+ pgvector) ho sakta hai; interface same rahega.
"""

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS persons (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS embeddings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    model_id    TEXT NOT NULL,          -- kis model ne banayi (embedding versioning)
    vector      BLOB NOT NULL,          -- float32 bytes
    det_score   REAL NOT NULL,
    sharpness   REAL NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emb_person ON embeddings(person_id);
CREATE INDEX IF NOT EXISTS idx_emb_model  ON embeddings(model_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Person:
    id: str
    name: str
    created_at: str
    num_faces: int = 0


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # FastAPI sync endpoints alag threads mein chalte hain -> ek connection + lock
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode = WAL")  # readers writers ko block nahi karte
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # ---------- persons ----------
    def create_person(self, name: str) -> Person:
        p = Person(id=uuid.uuid4().hex, name=name, created_at=_now())
        with self._lock:
            self._conn.execute(
                "INSERT INTO persons (id, name, created_at) VALUES (?, ?, ?)",
                (p.id, p.name, p.created_at),
            )
        return p

    def get_person(self, person_id: str) -> Person | None:
        with self._lock:
            row = self._conn.execute(
                """SELECT p.*, COUNT(e.id) AS num_faces FROM persons p
                   LEFT JOIN embeddings e ON e.person_id = p.id
                   WHERE p.id = ? GROUP BY p.id""",
                (person_id,),
            ).fetchone()
        return Person(**dict(row)) if row else None

    def list_persons(self) -> list[Person]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT p.*, COUNT(e.id) AS num_faces FROM persons p
                   LEFT JOIN embeddings e ON e.person_id = p.id
                   GROUP BY p.id ORDER BY p.created_at"""
            ).fetchall()
        return [Person(**dict(r)) for r in rows]

    def get_names(self, person_ids: list[str]) -> dict[str, str]:
        if not person_ids:
            return {}
        q = ",".join("?" * len(person_ids))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT id, name FROM persons WHERE id IN ({q})", person_ids
            ).fetchall()
        return {r["id"]: r["name"] for r in rows}

    def delete_person(self, person_id: str) -> list[int]:
        """Person + uski saari embeddings delete (privacy: 'right to be forgotten').
        Return: deleted embedding ids (taaki index se bhi hata sakein)."""
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                ids = [
                    r[0]
                    for r in self._conn.execute(
                        "SELECT id FROM embeddings WHERE person_id = ?", (person_id,)
                    )
                ]
                self._conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return ids

    # ---------- embeddings ----------
    def add_embedding(
        self, person_id: str, model_id: str, vector: np.ndarray, det_score: float, sharpness: float
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO embeddings (person_id, model_id, vector, det_score, sharpness,
                   created_at) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    person_id,
                    model_id,
                    vector.astype(np.float32).tobytes(),
                    det_score,
                    sharpness,
                    _now(),
                ),
            )
            return int(cur.lastrowid)

    def load_embeddings(self, model_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Ek model ki saari embeddings: (ids, person_ids, vectors). Index rebuild ke liye."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, person_id, vector FROM embeddings WHERE model_id = ? ORDER BY id",
                (model_id,),
            ).fetchall()
        if not rows:
            return np.empty(0, np.int64), np.empty(0, object), np.empty((0, 0), np.float32)
        ids = np.array([r["id"] for r in rows], dtype=np.int64)
        pids = np.array([r["person_id"] for r in rows], dtype=object)
        vecs = np.stack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
        return ids, pids, vecs

    def count_other_models(self, model_id: str) -> int:
        """Purane model ki embeddings - model upgrade ke baad re-enrollment/re-embedding chahiye."""
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE model_id != ?", (model_id,)
            ).fetchone()[0]
