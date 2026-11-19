# ============================================
# EMBEDDING MANAGEMENT SERVICE
# ============================================
"""
Face embeddings ko manage karta hai
Storage, retrieval, aur caching handle karta hai
"""

import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class EmbeddingManager:
    """
    Face embedding storage aur management
    FAISS mein store hone se pehle intermediate storage
    """

    def __init__(self, storage_path: Path):
        """
        Embedding manager initialize karo

        Parameters:
        - storage_path: Path to store embeddings metadata
        """
        self.storage_path = Path(storage_path)
        self.embeddings_cache = {}  # In-memory cache
        self.metadata_file = self.storage_path / "embeddings_metadata.json"

        # Load existing data agar available ho
        self._load_metadata()

    def _load_metadata(self):
        """
        Pehle se saved embeddings metadata load karo
        """
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)

                # Convert string keys back to proper format
                self.embeddings_cache = data.get("embeddings", {})
                logger.info(f"Loaded {len(self.embeddings_cache)} embeddings metadata")

            except Exception as e:
                logger.error(f"Failed to load metadata: {e}")
                self.embeddings_cache = {}
        else:
            self.embeddings_cache = {}

    def _save_metadata(self):
        """
        Current embeddings metadata save karo
        """
        try:
            data = {
                "embeddings": self.embeddings_cache,
                "last_updated": datetime.now().isoformat(),
                "total_embeddings": len(self.embeddings_cache)
            }

            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self.embeddings_cache)} embeddings metadata")

        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def add_embedding(
        self,
        face_id: str,
        embedding: np.ndarray,
        metadata: dict = {}
    ) -> bool:
        """
        Naya face embedding add karo

        Parameters:
        - face_id: Unique face identifier
        - embedding: Face feature vector
        - metadata: Additional info (name, timestamp, etc.)
        """
        try:
            # Cache mein store karo
            self.embeddings_cache[face_id] = {
                "embedding": embedding.tolist(),  # Convert to list for JSON
                "vector_dimension": embedding.shape[0],
                "metadata": {
                    **metadata,
                    "registered_at": datetime.now().isoformat()
                }
            }

            # Persist karo
            self._save_metadata()

            logger.info(f"Added embedding for face: {face_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add embedding: {e}")
            return False

    def get_embedding(self, face_id: str) -> Optional[np.ndarray]:
        """
        Specific face ka embedding retrieve karo
        """
        if face_id in self.embeddings_cache:
            emb_data = self.embeddings_cache[face_id]
            embedding = np.array(emb_data["embedding"])
            return embedding

        logger.warning(f"Embedding not found for face_id: {face_id}")
        return None

    def get_all_embeddings(self) -> Dict[str, np.ndarray]:
        """
        Saare embeddings ek saath retrieve karo
        FAISS index build karne ke liye
        """
        embeddings_dict = {}

        for face_id, data in self.embeddings_cache.items():
            embeddings_dict[face_id] = np.array(data["embedding"])

        return embeddings_dict

    def remove_embedding(self, face_id: str) -> bool:
        """
        Face embedding delete karo
        """
        if face_id in self.embeddings_cache:
            del self.embeddings_cache[face_id]
            self._save_metadata()
            logger.info(f"Removed embedding: {face_id}")
            return True

        logger.warning(f"Embedding not found: {face_id}")
        return False

    def update_metadata(self, face_id: str, metadata: dict) -> bool:
        """
        Face ka metadata update karo
        """
        if face_id in self.embeddings_cache:
            self.embeddings_cache[face_id]["metadata"].update(metadata)
            self.embeddings_cache[face_id]["metadata"]["updated_at"] = datetime.now().isoformat()
            self._save_metadata()
            return True
        return False

    def get_stats(self) -> dict:
        """
        Embedding storage ki statistics
        """
        return {
            "total_embeddings": len(self.embeddings_cache),
            "storage_path": str(self.storage_path),
            "metadata_file": str(self.metadata_file),
            "cache_size": len(self.embeddings_cache)
        }

    def clear_all(self):
        """
        Saare embeddings clear karo (USE CAREFULLY)
        """
        self.embeddings_cache = {}
        self._save_metadata()
        logger.warning("All embeddings cleared!")
