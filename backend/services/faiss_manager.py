# ============================================
# FAISS HIGH-LEVEL MANAGER (FIXED - Flat Index)
# ============================================
"""
FAISS ke upar convenience layer
FLAT index use karta hai - 1 vector se kaam karta hai
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import logging

from .faiss_service import FAISSService

logger = logging.getLogger(__name__)

class FAISSManager:
    """
    High-level FAISS manager
    Face registration aur recognition ke liye easy interface
    """
    
    def __init__(self, index_path: Path):
        """
        FAISS Manager initialize karo
        FLAT index - no training required, works with 1+ vectors
        """
        self.faiss = FAISSService(
            index_path=index_path,
            vector_dimension=512,
            index_type="Flat"  # FLAT index - koi minimum vectors nahi chahiye
        )
        
        # Recognition settings
        self.default_threshold = 0.6
        self.max_results = 5
    
    def register_face(
        self,
        face_vector: np.ndarray,
        person_name: str,
        additional_info: Optional[dict] = None
    ) -> Dict:
        """
        Face register karo system mein
        
        Parameters:
        - face_vector: 512-dim face embedding
        - person_name: Person ka naam
        - additional_info: Extra info (email, phone, etc.)
        
        Returns:
        - Registration result
        """
        try:
            # Check karo ki vector sahi hai
            if face_vector is None or len(face_vector) != 512:
                return {
                    "success": False,
                    "message": f"Invalid face vector. Expected 512-dim, got {len(face_vector) if face_vector is not None else 'None'}",
                    "face_id": None
                }
            
            # Metadata prepare karo
            metadata = {
                "name": person_name,
            }
            
            if additional_info:
                metadata.update(additional_info)
            
            # FAISS mein add karo
            face_id = self.faiss.add_single_vector(
                vector=face_vector,
                metadata=metadata
            )
            
            if face_id:
                logger.info(f"Face registered: {face_id} → {person_name}")
                return {
                    "success": True,
                    "message": f"Face registered for {person_name}",
                    "face_id": face_id,
                    "name": person_name
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to register face in FAISS",
                    "face_id": None
                }
                
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return {
                "success": False,
                "message": str(e),
                "face_id": None
            }
    
    def recognize_face(
        self,
        face_vector: np.ndarray,
        threshold: Optional[float] = None,
        max_results: Optional[int] = None
    ) -> Dict:
        """
        Face recognize karo
        
        Parameters:
        - face_vector: Query face embedding
        - threshold: Matching threshold
        - max_results: Maximum results to return
        
        Returns:
        - Recognition results
        """
        try:
            # Default values
            threshold = threshold or self.default_threshold
            max_results = max_results or self.max_results
            
            # Check if index is empty
            if self.faiss.total_vectors == 0:
                return {
                    "success": True,
                    "is_recognized": False,
                    "message": "FAISS index is empty. Register faces first.",
                    "matches": []
                }
            
            # Search karo
            matches = self.faiss.search_similar(
                query_vector=face_vector,
                k=max_results,
                threshold=threshold
            )
            
            if len(matches) == 0:
                return {
                    "success": True,
                    "is_recognized": False,
                    "message": "No match found",
                    "matches": []
                }
            
            # Results format karo
            formatted_matches = []
            for match in matches:
                formatted_matches.append({
                    "face_id": match["face_id"],
                    "name": match["metadata"].get("name", "Unknown"),
                    "confidence": round(match["similarity_score"] * 100, 2),
                    "metadata": match["metadata"]
                })
            
            # Best match
            best_match = formatted_matches[0]
            
            return {
                "success": True,
                "is_recognized": True,
                "message": f"Recognized as {best_match['name']}",
                "best_match": best_match,
                "all_matches": formatted_matches,
                "total_matches": len(formatted_matches)
            }
            
        except Exception as e:
            logger.error(f"Recognition failed: {e}")
            return {
                "success": False,
                "is_recognized": False,
                "message": str(e),
                "matches": []
            }
    
    def delete_person(self, face_id: str) -> Dict:
        """
        Person ko system se delete karo
        """
        try:
            # Check if exists
            if face_id not in self.faiss.id_to_metadata:
                return {
                    "success": False,
                    "message": "Face ID not found"
                }
            
            # Delete karo
            success = self.faiss.delete_face(face_id)
            
            if success:
                logger.info(f"Face deleted: {face_id}")
                return {
                    "success": True,
                    "message": "Face deleted successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to delete face"
                }
            
        except Exception as e:
            logger.error(f"Deletion failed: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_person_info(self, face_id: str) -> Optional[Dict]:
        """
        Person ki information retrieve karo
        """
        if face_id in self.faiss.id_to_metadata:
            return self.faiss.id_to_metadata[face_id]
        return None
    
    def list_all_faces(self) -> List[Dict]:
        """
        System mein registered saare faces ki list
        """
        faces = []
        
        for face_id, metadata in self.faiss.id_to_metadata.items():
            faces.append({
                "face_id": face_id,
                "name": metadata.get("name", "Unknown"),
                "registered_at": metadata.get("added_at", "Unknown")
            })
        
        return faces
    
    def get_system_stats(self) -> Dict:
        """
        System statistics
        """
        faiss_stats = self.faiss.get_stats()
        
        return {
            **faiss_stats,
            "recognition_threshold": self.default_threshold,
            "max_results": self.max_results
        }
    
    def rebuild_database(self) -> Dict:
        """
        FAISS index rebuild karo
        """
        try:
            self.faiss.rebuild_index()
            return {
                "success": True,
                "message": "Database rebuilt successfully",
                "stats": self.get_system_stats()
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }