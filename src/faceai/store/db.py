"""
SQLite repository = SOURCE OF TRUTH.

Legacy: FAISS index + pickle metadata alag-alag files -> ek save ho, doosra crash ho jaye => desync.
Yahan: embeddings bhi SQLite mein (BLOB). FAISS sirf ek fast search CACHE hai jo startup pe yahin se
rebuild hota hai. SQLite transactions atomic hain -> data kabhi aadha-adhura nahi.

Phase 7 (trust & safety):
- embeddings AES-GCM se encrypted (agar `cipher` diya), AAD = person_id|model_id
- `PRAGMA secure_delete`: deleted data zero se overwrite (warna free pages mein pada rehta)
- `consent_at` har person ke saath, `audit_log` har write ke liye (bina biometric/naam ke)

Production mein ye Postgres (+ pgvector) ho sakta hai; interface same rahega.
"""

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from faceai.security.crypto import Cipher

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS persons (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    consent_at  TEXT                    -- kab consent mila (Phase 7)
);
CREATE TABLE IF NOT EXISTS embeddings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    model_id    TEXT NOT NULL,          -- kis model ne banayi (embedding versioning)
    vector      BLOB NOT NULL,          -- float32 bytes, ya encrypted blob (b"E1"...)
    det_score   REAL NOT NULL,
    sharpness   REAL NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emb_person ON embeddings(person_id);
CREATE INDEX IF NOT EXISTS idx_emb_model  ON embeddings(model_id);
-- Append-only. person_id pe foreign key NAHI: person delete hone ke baad bhi audit rehna chahiye
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    action      TEXT NOT NULL,
    actor       TEXT NOT NULL,
    person_id   TEXT,
    request_id  TEXT,
    detail      TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_person ON audit_log(person_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Person:
    id: str
    name: str
    created_at: str
    num_faces: int = 0
    consent_at: str | None = None


class Database:
    def __init__(self, path: Path, cipher: Cipher | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.cipher = cipher
        # FastAPI sync endpoints alag threads mein chalte hain -> ek connection + lock
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode = WAL")  # readers writers ko block nahi karte
            self._conn.execute("PRAGMA secure_delete = ON")  # deleted data overwrite ho
            self._conn.executescript(SCHEMA)
            self._migrate()

    def _migrate(self) -> None:
        """Purani (Phase 1) DB files: naye columns add karo. Schema migration ka simplest roop."""
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(persons)")}
        if "consent_at" not in cols:
            self._conn.execute("ALTER TABLE persons ADD COLUMN consent_at TEXT")

    def close(self) -> None:
        self._conn.close()

    # ---------- crypto helpers ----------
    @staticmethod
    def _aad(person_id: str, model_id: str) -> bytes:
        return f"{person_id}|{model_id}".encode()

    def _seal(self, person_id: str, model_id: str, raw: bytes) -> bytes:
        return self.cipher.encrypt(raw, self._aad(person_id, model_id)) if self.cipher else raw

    def _open(self, person_id: str, model_id: str, blob: bytes) -> bytes:
        if Cipher.is_encrypted(blob):
            if self.cipher is None:
                raise RuntimeError("embeddings are encrypted but FACEAI_ENCRYPTION_KEYS is not set")
            return self.cipher.decrypt(blob, self._aad(person_id, model_id))
        return blob  # legacy plaintext row (migrate se encrypt karo)

    # ---------- persons ----------
    def create_person(self, name: str, consent: bool) -> Person:
        if not consent:
            raise ValueError("consent is required to store biometric data")
        now = _now()
        p = Person(id=uuid.uuid4().hex, name=name, created_at=now, consent_at=now)
        with self._lock:
            self._conn.execute(
                "INSERT INTO persons (id, name, created_at, consent_at) VALUES (?, ?, ?, ?)",
                (p.id, p.name, p.created_at, p.consent_at),
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

    def count_persons(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]

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
        blob = self._seal(person_id, model_id, vector.astype(np.float32).tobytes())
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO embeddings (person_id, model_id, vector, det_score, sharpness,
                   created_at) VALUES (?, ?, ?, ?, ?, ?)""",
                (person_id, model_id, blob, det_score, sharpness, _now()),
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
        vecs = np.stack(
            [
                np.frombuffer(self._open(r["person_id"], model_id, r["vector"]), dtype=np.float32)
                for r in rows
            ]
        )
        return ids, pids, vecs

    def count_other_models(self, model_id: str) -> int:
        """Purane model ki embeddings - model upgrade ke baad re-enrollment/re-embedding chahiye."""
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE model_id != ?", (model_id,)
            ).fetchone()[0]

    def count_unencrypted(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE substr(vector, 1, 2) != ?", (b"E1",)
            ).fetchone()[0]

    def reencrypt_all(self) -> int:
        """Plaintext rows encrypt karo, purani key wale rows active key pe lao (key rotation).
        Ek transaction: beech mein crash => kuch nahi badla."""
        if self.cipher is None:
            raise RuntimeError("no encryption key configured")
        changed = 0
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, person_id, model_id, vector FROM embeddings"
            ).fetchall()
            self._conn.execute("BEGIN")
            try:
                for r in rows:
                    blob = r["vector"]
                    if (
                        Cipher.is_encrypted(blob)
                        and self.cipher.key_id(blob) == self.cipher.active_id
                    ):
                        continue
                    raw = self._open(r["person_id"], r["model_id"], blob)
                    new = self.cipher.encrypt(raw, self._aad(r["person_id"], r["model_id"]))
                    self._conn.execute(
                        "UPDATE embeddings SET vector = ? WHERE id = ?", (new, r["id"])
                    )
                    changed += 1
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return changed

    def purge_embeddings_older_than(self, days: int) -> list[int]:
        """Retention policy: `days` se purani embeddings delete. Return: deleted ids."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
        with self._lock:
            ids = [
                r[0]
                for r in self._conn.execute(
                    "SELECT id FROM embeddings WHERE created_at < ?", (cutoff,)
                )
            ]
            if ids:
                q = ",".join("?" * len(ids))
                self._conn.execute(f"DELETE FROM embeddings WHERE id IN ({q})", ids)
        return ids

    # ---------- audit ----------
    def add_audit(
        self,
        action: str,
        actor: str,
        person_id: str | None = None,
        request_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO audit_log (ts, action, actor, person_id, request_id, detail)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (_now(), action, actor, person_id, request_id, json.dumps(detail or {})),
            )

    def list_audit(self, person_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM audit_log", []
        if person_id:
            sql, args = sql + " WHERE person_id = ?", [person_id]
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY id LIMIT ?", [*args, limit]).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]
