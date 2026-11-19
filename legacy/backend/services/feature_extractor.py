# ============================================
# FEATURE EXTRACTION SERVICE
# ============================================
"""
Face se feature vector (embedding) extract karta hai
512-dimension ka vector har face ke liye unique hota hai
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """
    Face feature extraction using deep learning models
    """

    def __init__(self, model_type: str = "insightface"):
        """
        Feature extractor initialize karo
        """
        self.model_type = model_type
        self.model = None
        self.vector_dimension = 512
        self._initialize_model()

    def _initialize_model(self):
        """
        Selected model initialize karo
        """
        try:
            if self.model_type == "insightface":
                self._init_insightface_model()
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")

            logger.info(f"Feature extractor initialized: {self.model_type}")

        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            self.model = None
            self.vector_dimension = 0
            logger.warning("Continuing without InsightFace model. Feature extraction will be disabled.")

    def _init_insightface_model(self):
        """
        InsightFace ArcFace model initialize karo
        """
        try:
            import insightface
            from insightface.app import FaceAnalysis

            self.model = FaceAnalysis(
                name="buffalo_l",
                providers=['CPUExecutionProvider'],
                allowed_modules=['detection', 'recognition']
            )

            self.model.prepare(
                ctx_id=0,
                det_size=(640, 640)
            )

            self.vector_dimension = 512
            logger.info("InsightFace ArcFace model loaded")

        except Exception as e:
            logger.exception("Failed to load InsightFace model")
            self.model = None
            raise RuntimeError(
                "InsightFace model could not be initialized. "
                "Check onnxruntime compatibility and Python base image."
            ) from e

    def extract_features(
        self,
        face_image: np.ndarray,
        normalize: bool = True
    ) -> Optional[np.ndarray]:
        """
        Face image se feature vector extract karo
        """
        if self.model is None:
            logger.warning("No InsightFace model loaded; feature extraction disabled.")
            return None

        try:
            return self._extract_insightface(face_image, normalize)
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None

    def _extract_insightface(
        self,
        face_image: np.ndarray,
        normalize: bool
    ) -> Optional[np.ndarray]:
        """
        InsightFace se features extract karo
        """
        if self.model is None:
            raise RuntimeError("InsightFace model is not loaded")

        # BGR to RGB convert karo
        rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)

        # Check image size
        h, w = rgb_image.shape[:2]

        # Resize agar bahut chota ya bada ho
        if w < 50 or h < 50:
            rgb_image = cv2.resize(rgb_image, (112, 112))
        elif w > 500 or h > 500:
            rgb_image = cv2.resize(rgb_image, (320, 320))

        # Face analysis karo
        faces = self.model.get(rgb_image)

        if len(faces) == 0:
            # Try with different size
            resized = cv2.resize(rgb_image, (320, 320))
            faces = self.model.get(resized)

            if len(faces) == 0:
                logger.warning("No face found in image for extraction")
                return None

        # Sabse confident face ka embedding lo
        best_face = max(faces, key=lambda x: x.det_score if hasattr(x, 'det_score') else 0)

        # Embedding nikaalo
        embedding = None
        if hasattr(best_face, 'embedding'):
            embedding = best_face.embedding
        elif hasattr(best_face, 'normed_embedding'):
            embedding = best_face.normed_embedding

        if embedding is None:
            logger.warning("No embedding found")
            return None

        # Normalize karo agar required
        if normalize:
            embedding = self._l2_normalize(embedding)

        return embedding

    @staticmethod
    def _l2_normalize(vector: np.ndarray) -> np.ndarray:
        """
        Vector ko L2 normalize karo
        """
        norm = np.linalg.norm(vector)
        if norm > 0:
            return vector / norm
        return vector

    def compare_faces(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
        metric: str = "cosine"
    ) -> float:
        """
        Do face embeddings compare karo
        """
        if metric == "cosine":
            return self._cosine_similarity(embedding1, embedding2)
        elif metric == "euclidean":
            return self._euclidean_similarity(embedding1, embedding2)
        else:
            raise ValueError(f"Unknown metric: {metric}")

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Cosine similarity calculate karo
        """
        vec1 = FeatureExtractor._l2_normalize(vec1)
        vec2 = FeatureExtractor._l2_normalize(vec2)

        similarity = np.dot(vec1, vec2)
        similarity = np.clip(similarity, -1.0, 1.0)
        similarity = (similarity + 1.0) / 2.0

        return float(similarity)

    @staticmethod
    def _euclidean_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Euclidean distance se similarity calculate karo
        """
        distance = np.linalg.norm(vec1 - vec2)
        similarity = 1.0 / (1.0 + distance)
        return float(similarity)

    def get_model_info(self) -> dict:
        """
        Current model ki information
        """
        return {
            "model_type": self.model_type,
            "vector_dimension": self.vector_dimension,
            "is_loaded": self.model is not None,
            "normalization": "L2"
        }


class FaceQualityChecker:
    """
    Check karta hai ki face recognition ke liye suitable hai ya nahi
    """

    @staticmethod
    def check_quality(face_image: np.ndarray) -> dict:
        """
        Face image quality check karo
        """
        quality_report = {
            "is_usable": True,
            "issues": [],
            "metrics": {}
        }

        # Size check
        height, width = face_image.shape[:2]
        quality_report["metrics"]["size"] = f"{width}x{height}"

        if width < 80 or height < 80:
            quality_report["is_usable"] = False
            quality_report["issues"].append("Face too small")

        # Brightness check
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        quality_report["metrics"]["brightness"] = float(brightness)

        if brightness < 40:
            quality_report["issues"].append("Too dark")
            quality_report["is_usable"] = False
        elif brightness > 240:
            quality_report["issues"].append("Too bright")
            quality_report["is_usable"] = False

        # Blur detection
        blur_score = FaceQualityChecker._estimate_blur(gray)
        quality_report["metrics"]["blur_score"] = float(blur_score)

        if blur_score < 50:
            quality_report["issues"].append("Image is blurry")
            quality_report["is_usable"] = False

        # Contrast check
        contrast = np.std(gray)
        quality_report["metrics"]["contrast"] = float(contrast)

        if contrast < 20:
            quality_report["issues"].append("Low contrast")
            quality_report["is_usable"] = False

        return quality_report

    @staticmethod
    def _estimate_blur(gray_image: np.ndarray) -> float:
        """
        Laplacian variance se blur estimate karo
        """
        laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
        variance = laplacian.var()
        return variance

    @staticmethod
    def improve_quality(face_image: np.ndarray) -> np.ndarray:
        """
        Face image quality improve karo
        """
        # Denoise
        denoised = cv2.fastNlMeansDenoisingColored(
            face_image, None, 10, 10, 7, 21
        )

        # Sharpen
        kernel_sharpen = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ])
        sharpened = cv2.filter2D(denoised, -1, kernel_sharpen)

        # CLAHE for contrast
        lab = cv2.cvtColor(sharpened, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        return enhanced
