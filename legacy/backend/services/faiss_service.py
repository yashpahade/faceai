# ============================================
# FAISS VECTOR DATABASE SERVICE
# ============================================
"""
FAISS (Facebook AI Similarity Search) integration
Face vectors ko store, search aur manage karta hai
Ye system ka core hai - similarity matching engine
"""

import numpy as np
import pickle
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FAISSService:
    """
    FAISS Vector Database Manager
    Face embeddings ka complete lifecycle manage karta hai
    """

    def __init__(
        self,
        index_path: Path,
        vector_dimension: int = 512,
        index_type: str = "IVF"  # IVF, HNSW, Flat
    ):
        """
        FAISS service initialize karo

        Parameters:
        - index_path: FAISS index file ka path
        - vector_dimension: Face embedding ka size (512)
        - index_type: Index type (IVF=fast, HNSW=accurate, Flat=exhaustive)
        """
        self.index_path = Path(index_path)
        self.vector_dimension = vector_dimension
        self.index_type = index_type

        # Main components
        self.index = None  # FAISS index object
        self.id_to_metadata = {}  # Face ID → Metadata mapping
        self.id_to_index = {}  # Face ID → Index mapping

        # Configuration
        self.is_trained = False
        self.total_vectors = 0

        # Index parameters
        if index_type == "IVF":
            self.nlist = 100  # Number of clusters
            self.nprobe = 10  # Search clusters
        elif index_type == "HNSW":
            self.M = 32  # Connections per layer
            self.efConstruction = 200  # Build time accuracy

        # Index load ya create karo
        self._initialize_index()

    def _initialize_index(self):
        """
        FAISS index initialize karo
        Agar pehle se saved hai to load karo, nahi to new banao
        """
        try:
            import faiss

            if self.index_path.exists():
                # Saved index load karo
                logger.info("Loading existing FAISS index...")
                self.load_index()
                if self.index is None or not self._is_index_compatible():
                    logger.warning(
                        "Existing FAISS index is incompatible with the requested index type. "
                        "Deleting stale files and recreating a fresh index."
                    )
                    try:
                        self.index_path.unlink()
                        metadata_path = self.index_path.parent / f"{self.index_path.stem}_metadata.pkl"
                        if metadata_path.exists():
                            metadata_path.unlink()
                    except Exception as exc:
                        logger.warning(f"Failed to delete stale index files: {exc}")
                    self._create_new_index()
            else:
                # New index create karo
                logger.info("Creating new FAISS index...")
                self._create_new_index()

        except ImportError:
            raise ImportError(
                "FAISS install karo: pip install faiss-cpu (ya faiss-gpu for GPU)"
            )

    def _create_new_index(self):
        """
        Naya FAISS index create karo
        Index type ke hisaab se different configuration
        """
        import faiss
        if self.index_type == "IVF":
            # IVF index - Clustering based, fast search
            quantizer = faiss.IndexFlatL2(self.vector_dimension)
            self.index = faiss.IndexIVFFlat(
                quantizer,
                self.vector_dimension,
                self.nlist,
                faiss.METRIC_L2
            )
            logger.info(f"Created IVF index with {self.nlist} clusters")

        elif self.index_type == "HNSW":
            # HNSW index - Graph based, very accurate
            self.index = faiss.IndexHNSWFlat(
                self.vector_dimension,
                self.M
            )
            self.index.hnsw.efConstruction = self.efConstruction
            logger.info(f"Created HNSW index with M={self.M}")

        elif self.index_type == "Flat":
            # Flat index - Brute force, exact search
            self.index = faiss.IndexFlatL2(self.vector_dimension)
            logger.info("Created Flat index (exact search)")

        else:
            raise ValueError(f"Unknown index type: {self.index_type}")

        self.is_trained = self.index_type == "Flat"
        self.total_vectors = 0

    def add_vectors(
        self,
        vectors: List[np.ndarray],
        metadata_list: List[dict],
        face_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        FAISS index mein naye face vectors add karo

        Parameters:
        - vectors: List of face embeddings
        - metadata_list: Har face ka metadata (name, etc.)
        - face_ids: Optional custom IDs, nahi to auto-generate

        Returns:
        - List of added face IDs
        """
        import faiss

        if len(vectors) == 0:
            logger.warning("No vectors to add")
            return []

        # Generate IDs agar provide nahi kiye
        if face_ids is None:
            from backend.utils.helpers import generate_unique_id
            face_ids = [generate_unique_id() for _ in range(len(vectors))]

        # Vectors ko numpy array mein convert karo
        vectors_array = np.array(vectors, dtype=np.float32)

        # Validation
        if vectors_array.shape[1] != self.vector_dimension:
            raise ValueError(
                f"Vector dimension mismatch. Expected {self.vector_dimension}, "
                f"got {vectors_array.shape[1]}"
            )

        # IVF index ko train karo agar pehli baar hai
        if self.index_type == "IVF" and not self.is_trained:
            if self.total_vectors + len(vectors) >= self.nlist:
                logger.info("Training IVF index...")
                self.index.train(vectors_array)
                self.is_trained = True
            else:
                logger.warning(f"Need at least {self.nlist} vectors to train IVF index")
                return []

        # Index mein add karo
        start_idx = self.total_vectors
        self.index.add(vectors_array)

        # Metadata store karo
        for i, (face_id, metadata) in enumerate(zip(face_ids, metadata_list)):
            idx = start_idx + i

            self.id_to_metadata[face_id] = {
                **metadata,
                "index_id": idx,
                "added_at": datetime.now().isoformat()
            }

            self.id_to_index[face_id] = idx

        self.total_vectors += len(vectors)

        # Index save karo
        self.save_index()

        logger.info(f"Added {len(vectors)} vectors. Total: {self.total_vectors}")
        return face_ids

    def add_single_vector(
        self,
        vector: np.ndarray,
        metadata: dict,
        face_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Ek single face vector add karo
        Convenience function
        """
        from backend.utils.helpers import generate_unique_id

        if face_id is None:
            face_id = generate_unique_id()

        return self.add_vectors(
            [vector],
            [metadata],
            [face_id]
        )[0]

    def search_similar(
        self,
        query_vector: np.ndarray,
        k: int = 5,
        threshold: float = 0.6
    ) -> List[dict]:
        """
        Query vector ke similar faces search karo

        Parameters:
        - query_vector: Search karne wala face vector
        - k: Top-k results
        - threshold: Minimum similarity threshold

        Returns:
        - List of matched faces with scores
        """
        import faiss

        if self.total_vectors == 0:
            logger.warning("FAISS index is empty")
            return []

        # Query vector prepare karo
        query = np.array([query_vector], dtype=np.float32)

        # IVF index ke liye nprobe set karo
        if self.index_type == "IVF":
            self.index.nprobe = self.nprobe

        # Search karo
        distances, indices = self.index.search(query, min(k, self.total_vectors))

        # Results format karo
        results = []

        for distance, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for no match
                continue

            # Distance ko similarity mein convert karo
            similarity = self._distance_to_similarity(float(distance))

            # Threshold check
            if similarity < threshold:
                continue

            # Face ID dhundho
            face_id = self._get_face_id_by_index(int(idx))

            if face_id:
                metadata = self.id_to_metadata.get(face_id, {})

                results.append({
                    "face_id": face_id,
                    "similarity_score": similarity,
                    "distance": float(distance),
                    "metadata": metadata,
                    "index_position": int(idx)
                })

        # Score ke hisaab se sort karo (highest first)
        results.sort(key=lambda x: x["similarity_score"], reverse=True)

        return results[:k]

    def search_by_id(
        self,
        face_id: str,
        k: int = 5
    ) -> List[dict]:
        """
        Existing face ID se similar faces search karo
        "Find similar faces" feature ke liye
        """
        if face_id not in self.id_to_index:
            logger.warning(f"Face ID not found: {face_id}")
            return []

        # Existing face ka vector nikaalo
        idx = self.id_to_index[face_id]
        vector = self._get_vector_by_index(idx)

        if vector is None:
            return []

        # Search karo (k+1 kyunki pehla result wahi face hoga)
        results = self.search_similar(vector, k=k+1)

        # Same face ko results se hatao
        results = [r for r in results if r["face_id"] != face_id]

        return results[:k]

    def delete_face(self, face_id: str) -> bool:
        """
        Face index se delete karo
        FAISS mein direct delete nahi hota, soft delete karte hain
        """
        if face_id not in self.id_to_metadata:
            logger.warning(f"Face ID not found: {face_id}")
            return False

        # Metadata se delete karo
        del self.id_to_metadata[face_id]

        if face_id in self.id_to_index:
            del self.id_to_index[face_id]

        # Note: FAISS index se remove nahi kar sakte directly
        # Isliye rebuild karna padega agar permanent delete chahiye

        logger.info(f"Face marked as deleted: {face_id}")
        return True

    def rebuild_index(self):
        """
        FAISS index rebuild karo from scratch
        Useful after many deletions
        """
        import faiss

        logger.info("Rebuilding FAISS index...")

        # Saare active vectors collect karo
        active_vectors = []
        active_metadata = []
        active_ids = []

        for face_id, metadata in self.id_to_metadata.items():
            idx = metadata["index_id"]
            vector = self._get_vector_by_index(idx)

            if vector is not None:
                active_vectors.append(vector)
                active_metadata.append(metadata)
                active_ids.append(face_id)

        # New index create karo
        self._create_new_index()

        # Saare vectors add karo
        if active_vectors:
            vectors_array = np.array(active_vectors, dtype=np.float32)

            if self.index_type == "IVF":
                self.index.train(vectors_array)
                self.is_trained = True

            self.index.add(vectors_array)

            # Remapping karo
            for i, (face_id, metadata) in enumerate(zip(active_ids, active_metadata)):
                metadata["index_id"] = i
                self.id_to_metadata[face_id] = metadata
                self.id_to_index[face_id] = i

            self.total_vectors = len(active_vectors)

        # Save karo
        self.save_index()

        logger.info(f"Index rebuilt. Total vectors: {self.total_vectors}")

    def save_index(self):
        """
        FAISS index ko disk pe save karo
        Binary format mein store hota hai
        """
        import faiss

        try:
            # FAISS index save karo
            faiss.write_index(self.index, str(self.index_path))

            # Metadata save karo
            metadata_path = self.index_path.parent / f"{self.index_path.stem}_metadata.pkl"
            with open(metadata_path, 'wb') as f:
                pickle.dump({
                    "id_to_metadata": self.id_to_metadata,
                    "id_to_index": self.id_to_index,
                    "total_vectors": self.total_vectors,
                    "is_trained": self.is_trained,
                    "index_type": self.index_type,
                    "vector_dimension": self.vector_dimension,
                    "last_saved": datetime.now().isoformat()
                }, f)

            logger.info(f"Index saved to {self.index_path}")

        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    def load_index(self):
        """
        Saved FAISS index load karo
        """
        import faiss

        try:
            # FAISS index load karo
            if self.index_path.exists():
                self.index = faiss.read_index(str(self.index_path))
                logger.info(f"Loaded FAISS index from {self.index_path}")
            else:
                logger.warning("Index file not found, creating new")
                self._create_new_index()
                return

            # Metadata load karo
            metadata_path = self.index_path.parent / f"{self.index_path.stem}_metadata.pkl"
            if metadata_path.exists():
                with open(metadata_path, 'rb') as f:
                    data = pickle.load(f)

                    self.id_to_metadata = data.get("id_to_metadata", {})
                    self.id_to_index = data.get("id_to_index", {})
                    self.total_vectors = data.get("total_vectors", 0)
                    self.is_trained = data.get("is_trained", self.index_type == "Flat")
                    self.vector_dimension = data.get("vector_dimension", self.vector_dimension)

                logger.info(f"Loaded metadata. Total vectors: {self.total_vectors}")
            else:
                logger.warning("Metadata file not found")

        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            self._create_new_index()

    def _distance_to_similarity(self, distance: float) -> float:
        """
        L2 distance ko similarity score (0-1) mein convert karo
        Lower distance = Higher similarity
        """
        # Sigmoid-like transformation
        similarity = 1.0 / (1.0 + distance)

        # Scale to 0-100
        return float(similarity)

    def _is_index_compatible(self) -> bool:
        """
        Loaded index type compatibility check karo.
        """
        import faiss

        if self.index is None:
            return False

        index_class = self.index.__class__.__name__
        logger.debug(f"Loaded FAISS index class: {index_class}")

        if self.index_type == "Flat":
            return index_class == "IndexFlatL2" or index_class == "IndexFlat" or index_class == "IndexFlatIP"
        if self.index_type == "IVF":
            return index_class.startswith("IndexIVF")
        if self.index_type == "HNSW":
            return index_class == "IndexHNSWFlat"

        return False

    def _get_vector_by_index(self, idx: int) -> Optional[np.ndarray]:
        """
        Index position se vector retrieve karo
        """
        import faiss

        try:
            # FAISS se vector reconstruct karo
            vector = self.index.reconstruct(int(idx))
            return vector
        except Exception as e:
            logger.error(f"Failed to get vector at index {idx}: {e}")
            return None

    def _get_face_id_by_index(self, idx: int) -> Optional[str]:
        """
        Index position se face ID dhundho
        Reverse lookup
        """
        for face_id, index_id in self.id_to_index.items():
            if index_id == idx:
                return face_id
        return None

    def get_stats(self) -> dict:
        """
        FAISS index ki statistics
        Monitoring ke liye
        """
        return {
            "total_vectors": self.total_vectors,
            "index_type": self.index_type,
            "vector_dimension": self.vector_dimension,
            "is_trained": self.is_trained,
            "index_path": str(self.index_path),
            "memory_usage": self._estimate_memory_usage(),
            "registered_faces": len(self.id_to_metadata)
        }

    def _estimate_memory_usage(self) -> str:
        """
        Estimate karo kitni memory use ho rahi hai
        """
        vector_memory = self.total_vectors * self.vector_dimension * 4  # 4 bytes per float32

        if vector_memory < 1024:
            return f"{vector_memory} B"
        elif vector_memory < 1024**2:
            return f"{vector_memory/1024:.2f} KB"
        elif vector_memory < 1024**3:
            return f"{vector_memory/(1024**2):.2f} MB"
        else:
            return f"{vector_memory/(1024**3):.2f} GB"

    def clear_all(self):
        """
        Saara data clear karo (CAREFUL!)
        """
        self._create_new_index()
        self.id_to_metadata = {}
        self.id_to_index = {}
        self.total_vectors = 0
        self.is_trained = False

        # Delete files
        if self.index_path.exists():
            self.index_path.unlink()

        metadata_path = self.index_path.parent / f"{self.index_path.stem}_metadata.pkl"
        if metadata_path.exists():
            metadata_path.unlink()

        logger.warning("All FAISS data cleared!")
