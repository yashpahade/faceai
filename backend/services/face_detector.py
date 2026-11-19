# ============================================
# FACE DETECTION SERVICE
# ============================================
"""
Ye service image mein se faces detect karti hai
Multiple detection methods support karta hai:
1. InsightFace (Primary - Best accuracy)
2. OpenCV Haar Cascade (Backup)
3. MediaPipe (Alternative)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
import logging

# Logger setup
logger = logging.getLogger(__name__)

class FaceDetector:
    """
    Face Detection Class
    Different methods se face detect karta hai
    """
    
    def __init__(self, method: str = "insightface"):
        """
        Face detector initialize karo
        
        Parameters:
        - method: "insightface", "opencv", ya "mediapipe"
        """
        self.method = method
        self.detector = None
        self._initialize_detector()
    
    def _initialize_detector(self):
        """
        Selected method ke hisaab se detector initialize karo
        Har method ka apna loading process hai
        """
        try:
            if self.method == "insightface":
                self._init_insightface()
            elif self.method == "opencv":
                self._init_opencv()
            elif self.method == "mediapipe":
                self._init_mediapipe()
            else:
                raise ValueError(f"Unknown method: {self.method}")
            
            logger.info(f"Face detector initialized with method: {self.method}")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.method} detector: {e}")
            # Fallback to OpenCV agar kuch bhi fail ho
            logger.warning("Falling back to OpenCV detector")
            self.method = "opencv"
            self._init_opencv()
    
    def _init_insightface(self):
        """
        InsightFace detector initialize karo
        Ye deep learning based hai, sabse accurate
        """
        try:
            import insightface
            from insightface.app import FaceAnalysis
            
            # Face analysis app create karo
            self.detector = FaceAnalysis(
                name="buffalo_l",  # Lightweight model
                providers=['CPUExecutionProvider']  # CPU pe run karega
            )
            
            # Model prepare karo
            self.detector.prepare(
                ctx_id=0,  # CPU device
                det_size=(640, 640),  # Detection size
                det_thresh=0.5  # Detection threshold
            )
            
            logger.info("InsightFace detector ready")
            
        except ImportError:
            raise ImportError("InsightFace not installed. Run: pip install insightface")
    
    def _init_opencv(self):
        """
        OpenCV Haar Cascade detector initialize karo
        Ye traditional method hai, lightweight
        """
        # OpenCV ka pre-trained face detector load karo
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        
        if not Path(cascade_path).exists():
            raise FileNotFoundError(f"Cascade file not found: {cascade_path}")
        
        self.detector = cv2.CascadeClassifier(cascade_path)
        logger.info("OpenCV Haar Cascade detector ready")
    
    def _init_mediapipe(self):
        """
        MediaPipe face detector initialize karo
        Google ka framework hai, accha balance hai speed vs accuracy
        """
        try:
            import mediapipe as mp
            
            self.mp_face_detection = mp.solutions.face_detection
            self.detector = self.mp_face_detection.FaceDetection(
                model_selection=1,  # 1 for full range, 0 for short range
                min_detection_confidence=0.5
            )
            logger.info("MediaPipe detector ready")
            
        except ImportError:
            raise ImportError("MediaPipe not installed. Run: pip install mediapipe")
    
    def detect_faces(
        self, 
        image: np.ndarray,
        confidence_threshold: float = 0.5
    ) -> List[dict]:
        """
        Image mein se faces detect karo
        
        Parameters:
        - image: numpy array (BGR format)
        - confidence_threshold: minimum confidence score
        
        Returns:
        - List of detected faces with bbox and confidence
        """
        if self.method == "insightface":
            return self._detect_insightface(image, confidence_threshold)
        elif self.method == "opencv":
            return self._detect_opencv(image, confidence_threshold)
        elif self.method == "mediapipe":
            return self._detect_mediapipe(image, confidence_threshold)
    
    def _detect_insightface(
        self, 
        image: np.ndarray, 
        threshold: float
    ) -> List[dict]:
        """
        InsightFace se faces detect karo
        Sabse detailed information milta hai
        """
        # BGR to RGB convert karo (InsightFace expects RGB)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Faces detect karo
        faces = self.detector.get(rgb_image)
        
        results = []
        for face in faces:
            # Detection confidence check karo
            if face.det_score < threshold:
                continue
            
            # Bounding box nikaalo
            bbox = face.bbox.astype(int).tolist()
            
            # Facial landmarks agar available ho
            landmarks = None
            if hasattr(face, 'kps'):
                landmarks = face.kps.tolist()
            
            results.append({
                "bbox": bbox,  # [x1, y1, x2, y2]
                "confidence": float(face.det_score),
                "landmarks": landmarks,
                "embedding": face.embedding if hasattr(face, 'embedding') else None
            })
        
        return results
    
    def _detect_opencv(
        self, 
        image: np.ndarray, 
        threshold: float
    ) -> List[dict]:
        """
        OpenCV Haar Cascade se faces detect karo
        Simple but fast method
        """
        # Gray scale mein convert karo
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Histogram equalization for better detection
        gray = cv2.equalizeHist(gray)
        
        # Faces detect karo
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,  # Image scaling factor
            minNeighbors=5,    # Minimum neighbors for detection
            minSize=(30, 30),  # Minimum face size
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        results = []
        for (x, y, w, h) in faces:
            # OpenCV mein confidence score nahi hota, to estimate karte hain
            # Face size ke hisaab se confidence calculate
            face_area = w * h
            image_area = image.shape[0] * image.shape[1]
            estimated_confidence = min(0.9, face_area / image_area * 10)
            
            results.append({
                "bbox": [int(x), int(y), int(x+w), int(y+h)],
                "confidence": estimated_confidence,
                "landmarks": None,
                "embedding": None
            })
        
        return results
    
    def _detect_mediapipe(
        self, 
        image: np.ndarray, 
        threshold: float
    ) -> List[dict]:
        """
        MediaPipe se faces detect karo
        Good balance of speed and accuracy
        """
        # BGR to RGB convert karo
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        results = self.detector.process(rgb_image)
        
        faces = []
        if results.detections:
            height, width = image.shape[:2]
            
            for detection in results.detections:
                # Confidence check
                if detection.score[0] < threshold:
                    continue
                
                # Bounding box nikaalo
                bbox = detection.location_data.relative_bounding_box
                
                # Relative coordinates ko absolute mein convert
                x = int(bbox.xmin * width)
                y = int(bbox.ymin * height)
                w = int(bbox.width * width)
                h = int(bbox.height * height)
                
                # Landmarks nikaalo
                landmarks = []
                for landmark in detection.location_data.relative_keypoints:
                    lx = int(landmark.x * width)
                    ly = int(landmark.y * height)
                    landmarks.append([lx, ly])
                
                faces.append({
                    "bbox": [x, y, x+w, y+h],
                    "confidence": float(detection.score[0]),
                    "landmarks": landmarks,
                    "embedding": None
                })
        
        return faces
    
    def preprocess_face(
        self, 
        image: np.ndarray, 
        bbox: List[int],
        target_size: Tuple[int, int] = (112, 112)
    ) -> np.ndarray:
        """
        Detected face ko crop aur preprocess karo
        
        Parameters:
        - image: Full image
        - bbox: Face bounding box [x1, y1, x2, y2]
        - target_size: Output face size
        
        Returns:
        - Preprocessed face image
        """
        x1, y1, x2, y2 = bbox
        
        # Bounding box expand karo (thoda margin add)
        margin = 20
        height, width = image.shape[:2]
        
        x1 = max(0, x1 - margin)
        y1 = max(0, y1 - margin)
        x2 = min(width, x2 + margin)
        y2 = min(height, y2 + margin)
        
        # Face crop karo
        face_crop = image[y1:y2, x1:x2]
        
        # Agar crop empty hai to original return karo
        if face_crop.size == 0:
            return cv2.resize(image, target_size)
        
        # Face resize karo target size pe
        face_resized = cv2.resize(face_crop, target_size)
        
        return face_resized
    
    def draw_faces(
        self, 
        image: np.ndarray, 
        faces: List[dict],
        color: Tuple[int, int, int] = (0, 255, 0)
    ) -> np.ndarray:
        """
        Image pe detected faces draw karo (visualization ke liye)
        
        Parameters:
        - image: Input image
        - faces: Detected faces list
        - color: Box color (BGR format)
        
        Returns:
        - Image with drawn faces
        """
        # Image copy banao taki original safe rahe
        img_copy = image.copy()
        
        for i, face in enumerate(faces):
            bbox = face["bbox"]
            confidence = face.get("confidence", 0)
            
            # Bounding box draw karo
            cv2.rectangle(
                img_copy, 
                (bbox[0], bbox[1]), 
                (bbox[2], bbox[3]), 
                color, 
                2
            )
            
            # Confidence score show karo
            label = f"Face {i+1}: {confidence:.2f}"
            cv2.putText(
                img_copy,
                label,
                (bbox[0], bbox[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )
            
            # Landmarks draw karo agar available ho
            if face.get("landmarks"):
                for (lx, ly) in face["landmarks"]:
                    cv2.circle(img_copy, (lx, ly), 2, (255, 0, 0), -1)
        
        return img_copy


# ============================================
# FACTORY FUNCTION
# ============================================
def create_face_detector(method: str = "insightface") -> FaceDetector:
    """
    Face detector object create karo
    Factory pattern use kiya hai for flexibility
    """
    return FaceDetector(method=method)