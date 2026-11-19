"""
Vector index (FAISS) - "is face se sabse milte-julte stored faces kaun se hain?"

IndexFlatIP = exact search by Inner Product.
Normalized vectors pe inner product = cosine similarity.
(Legacy IndexFlatL2 use karta tha aur L2 distance ko "similarity %" bana deta tha - confusing.)

Flat = brute force, har vector se compare. ~1 lakh faces tak milliseconds mein. Usse bade scale pe
approximate indexes (IVF, HNSW) aate hain - speed vs accuracy trade-off. Abhi zaroorat nahi.

IndexIDMap2: humare SQLite embedding IDs ko hi FAISS IDs bana deta hai -> delete aasaan.
"""

import threading

import faiss
import numpy as np


class VectorIndex:
    def __init__(self, dim: int):
        self.dim = dim
        self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(dim))
        self._owner: dict[int, str] = {}  # embedding_id -> person_id
        self._lock = threading.RLock()

    def __len__(self) -> int:
        return self._index.ntotal

    def add(self, ids: np.ndarray, person_ids: np.ndarray, vectors: np.ndarray) -> None:
        if len(ids) == 0:
            return
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if vectors.shape[1] != self.dim:
            raise ValueError(f"dim mismatch: index={self.dim}, got={vectors.shape[1]}")
        with self._lock:
            self._index.add_with_ids(vectors, np.asarray(ids, dtype=np.int64))
            self._owner.update(zip(ids.tolist(), person_ids.tolist(), strict=True))

    def remove(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock:
            self._index.remove_ids(np.asarray(ids, dtype=np.int64))
            for i in ids:
                self._owner.pop(i, None)

    def search_persons(self, query: np.ndarray, k: int = 20) -> list[tuple[str, float]]:
        """
        Top matches PERSON level pe: ek insaan ki kai photos ho sakti hain, uska best score lo.
        Return [(person_id, similarity)] sorted desc.
        """
        with self._lock:
            n = self._index.ntotal
            if n == 0:
                return []
            sims, ids = self._index.search(query.reshape(1, -1).astype(np.float32), min(k, n))
            best: dict[str, float] = {}
            for sim, eid in zip(sims[0], ids[0], strict=True):
                if eid == -1:
                    continue
                pid = self._owner[int(eid)]
                best[pid] = max(best.get(pid, -1.0), float(sim))
        return sorted(best.items(), key=lambda kv: -kv[1])
