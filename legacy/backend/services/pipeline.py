# ============================================
# COMPLETE FACE PROCESSING PIPELINE
# ============================================
"""
End-to-end face processing pipeline
Image → Detection → Preprocessing → Feature Extraction
FIXED: Feature extraction from cropped faces
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging
import time

from .face_detector import FaceDetector
from .face_processor import FaceProcessor
from .feature_extractor import FeatureExtractor, FaceQualityChecker
from .faiss_manager import FAISSManager
from ..config import settings

logger = logging.getLogger(__name__)

class FaceProcessingPipeline:
    """
    Complete face processing pipeline
    Image → Detection → Preprocessing → Feature Extraction → Recognition
    """

    def __init__(
        self,
        detector_method: str = "insightface",
        extractor_model: str = "insightface"
    ):
        """
        Pipeline initialize karo with all components
        """
        logger.info("Initializing Face Processing Pipeline...")

        # Core components
        self.detector = FaceDetector(method=detector_method)
        self.extractor = FeatureExtractor(model_type=extractor_model)
        self.processor = FaceProcessor()
        self.quality_checker = FaceQualityChecker()

        # FAISS Manager initialize karo
        self.faiss_manager = FAISSManager(index_path=settings.FAISS_INDEX_PATH)

        # Configuration
        self.confidence_threshold = settings.FACE_DETECTION_THRESHOLD
        self.recognition_threshold = settings.FACE_RECOGNITION_THRESHOLD
        self.enhance_faces = True
        self.check_quality = True

        logger.info("Pipeline ready with FAISS integration!")

    def process_image(
        self,
        image: np.ndarray,
        return_visualization: bool = False,
        run_recognition: bool = True
    ) -> Dict:
        """
        Complete pipeline through a single image

        Parameters:
        - image: Input image (numpy array)
        - return_visualization: Draw results on image
        - run_recognition: Search database for matches

        Returns:
        - Dictionary with all processing results
        """
        results = {
            "status": "success",
            "faces_found": 0,
            "faces": [],
            "processing_time": {}
        }

        # Step 1: Validate image
        t1 = time.time()
        if not self.processor.validate_face_image(image):
            results["status"] = "invalid_image"
            return results

        # Step 2: Detect faces
        t2 = time.time()
        faces = self.detector.detect_faces(
            image,
            confidence_threshold=self.confidence_threshold
        )
        results["faces_found"] = len(faces)
        results["processing_time"]["detection"] = time.time() - t2

        if len(faces) == 0:
            results["status"] = "no_faces_found"
            return results

        # Step 3: Process each face
        t3 = time.time()

        for i, face in enumerate(faces):
            face_result = self._process_single_face(image, face, i)

            # Step 4: Recognition (agar enabled hai aur embedding mili hai)
            if run_recognition and face_result.get("has_embedding"):
                recognition_result = self.faiss_manager.recognize_face(
                    face_vector=face_result["embedding"],
                    threshold=self.recognition_threshold
                )
                face_result["recognition"] = recognition_result

            results["faces"].append(face_result)

        results["processing_time"]["extraction_and_recognition"] = time.time() - t3

        # Step 5: Visualization (optional)
        if return_visualization:
            vis_image = self.draw_pipeline_results(image, results["faces"])
            results["visualization"] = vis_image

        results["total_time"] = time.time() - t1

        return results

    def register_person(
        self,
        image: np.ndarray,
        person_name: str,
        additional_info: Optional[dict] = None
    ) -> Dict:
        """
        Image se face extract karke register karo
        """
        # Detection
        faces = self.detector.detect_faces(image, confidence_threshold=self.confidence_threshold)

        if len(faces) == 0:
            return {"success": False, "message": "No face detected in image"}

        if len(faces) > 1:
            return {"success": False, "message": f"Multiple faces ({len(faces)}) detected. Registration requires exactly one face."}

        # Process the single face
        face_result = self._process_single_face(image, faces[0], 0)

        if not face_result.get("has_embedding"):
            return {"success": False, "message": "Failed to extract features from face"}

        # Quality check check
        if self.check_quality and not face_result["quality"]["is_usable"]:
            return {
                "success": False,
                "message": f"Poor image quality: {', '.join(face_result['quality']['issues'])}",
                "quality": face_result["quality"]
            }

        # Register in FAISS
        reg_result = self.faiss_manager.register_face(
            face_vector=face_result["embedding"],
            person_name=person_name,
            additional_info=additional_info
        )

        return reg_result

    def draw_pipeline_results(
        self,
        image: np.ndarray,
        face_results: List[Dict]
    ) -> np.ndarray:
        """Draw bounding boxes and names on image"""
        img_copy = image.copy()

        for res in face_results:
            bbox = res["bbox"]
            name = "Unknown"
            confidence = 0

            if res.get("recognition") and res["recognition"].get("is_recognized"):
                best_match = res["recognition"]["best_match"]
                name = best_match["name"]
                confidence = best_match["confidence"]

            # Draw box
            cv2.rectangle(img_copy, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)

            # Label
            label = f"{name} ({confidence}%)" if name != "Unknown" else "Unknown"
            cv2.putText(
                img_copy,
                label,
                (bbox[0], bbox[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

        return img_copy


    def _process_single_face(
        self,
        image: np.ndarray,
        face_detection: Dict,
        face_index: int
    ) -> Dict:
        """
        Ek face ko completely process karo - FIXED VERSION

        Returns:
        - Face data with embedding and metadata
        """
        face_data = {
            "face_index": face_index,
            "bbox": face_detection["bbox"],
            "confidence": face_detection["confidence"],
            "has_embedding": False
        }

        # ===== STEP A: Crop face =====
        face_crop = self.detector.preprocess_face(
            image,
            face_detection["bbox"],
            target_size=(112, 112)
        )

        print(f"  Face {face_index}: crop shape={face_crop.shape}")

        # ===== STEP B: Quality check =====
        if self.check_quality:
            quality = self.quality_checker.check_quality(face_crop)
            face_data["quality"] = quality

            # Improve if needed
            if not quality["is_usable"] and self.enhance_faces:
                print(f"  Face {face_index}: enhancing quality...")
                face_crop = self.quality_checker.improve_quality(face_crop)
        else:
            face_data["quality"] = {"is_usable": True}

        # ===== STEP C: Extract features (MULTIPLE METHODS) =====
        embedding = None

        if self.extractor.model is not None:
            # Method 1: Direct from InsightFace model using face crop
            try:
                face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)

                # Ensure minimum size
                h, w = face_rgb.shape[:2]
                if h < 80 or w < 80:
                    face_rgb = cv2.resize(face_rgb, (112, 112))

                # Get faces with embeddings from crop
                faces_from_crop = self.extractor.model.get(face_rgb)

                if len(faces_from_crop) > 0:
                    best = max(
                        faces_from_crop,
                        key=lambda x: x.det_score if hasattr(x, 'det_score') else 0
                    )

                    if hasattr(best, 'embedding') and best.embedding is not None:
                        embedding = best.embedding
                        print(f"  Face {face_index}: ✓ Embedding from crop")
                    elif hasattr(best, 'normed_embedding') and best.normed_embedding is not None:
                        embedding = best.normed_embedding
                        print(f"  Face {face_index}: ✓ Normed embedding from crop")
                else:
                    print(f"  Face {face_index}: No face in crop, trying full image...")

            except Exception as e:
                print(f"  Face {face_index}: Method 1 error: {e}")

        else:
            print(f"  Face {face_index}: InsightFace model unavailable; skipping direct embedding methods")

        # Method 2: From full image (fallback)
        if embedding is None and self.extractor.model is not None:
            try:
                full_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                faces_full = self.extractor.model.get(full_rgb)

                if len(faces_full) > face_index:
                    face_from_full = faces_full[face_index]

                    if hasattr(face_from_full, 'embedding') and face_from_full.embedding is not None:
                        embedding = face_from_full.embedding
                        print(f"  Face {face_index}: ✓ Embedding from full image")
                    elif hasattr(face_from_full, 'normed_embedding') and face_from_full.normed_embedding is not None:
                        embedding = face_from_full.normed_embedding
                        print(f"  Face {face_index}: ✓ Normed embedding from full image")
                else:
                    if len(faces_full) > 0:
                        best = max(
                            faces_full,
                            key=lambda x: x.det_score if hasattr(x, 'det_score') else 0
                        )
                        if hasattr(best, 'embedding') and best.embedding is not None:
                            embedding = best.embedding
                            print(f"  Face {face_index}: ✓ Embedding from full image (best)")

            except Exception as e:
                print(f"  Face {face_index}: Method 2 error: {e}")

        # Method 3: Feature extractor class
        if embedding is None:
            try:
                embedding = self.extractor.extract_features(face_crop, normalize=True)
                if embedding is not None:
                    print(f"  Face {face_index}: ✓ Embedding from extractor class")
            except Exception as e:
                print(f"  Face {face_index}: Method 3 error: {e}")

        # Method 4: Resize and retry
        if embedding is None and self.extractor.model is not None:
            try:
                face_resized = cv2.resize(face_crop, (112, 112))
                face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
                faces_retry = self.extractor.model.get(face_rgb)

                if len(faces_retry) > 0:
                    best = max(
                        faces_retry,
                        key=lambda x: x.det_score if hasattr(x, 'det_score') else 0
                    )
                    if hasattr(best, 'embedding') and best.embedding is not None:
                        embedding = best.embedding
                        print(f"  Face {face_index}: ✓ Embedding from resize retry")
            except Exception as e:
                print(f"  Face {face_index}: Method 4 error: {e}")

        # ===== STEP D: Store embedding =====
        if embedding is not None:
            # Normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            face_data["embedding"] = embedding
            face_data["has_embedding"] = True
            face_data["vector_dimension"] = embedding.shape[0]
            print(f"  Face {face_index}: ✓ Final embedding shape={embedding.shape}")
        else:
            print(f"  Face {face_index}: ✗ ALL METHODS FAILED - No embedding extracted")

        return face_data

    def process_image_file(
        self,
        image_path: Path,
        return_visualization: bool = False
    ) -> Dict:
        """
        File se image load karo aur process karo
        """
        # Read image
        image = cv2.imread(str(image_path))

        if image is None:
            return {"status": "error", "message": "Failed to read image"}

        # Process
        return self.process_image(image, return_visualization)

    def get_pipeline_info(self) -> Dict:
        """Pipeline configuration info"""
        return {
            "detector": self.detector.method,
            "extractor": self.extractor.model_type,
            "vector_dimension": self.extractor.vector_dimension,
            "confidence_threshold": self.confidence_threshold,
            "quality_check": self.check_quality,
            "face_enhancement": self.enhance_faces
        }
