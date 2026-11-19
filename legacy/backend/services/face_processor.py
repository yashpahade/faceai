# ============================================
# FACE PROCESSING SERVICE
# ============================================
"""
Face image preprocessing and enhancement
Recognition ke liye faces ko prepare karta hai
"""

import cv2
import numpy as np
from typing import Tuple, Optional
from PIL import Image
import io

class FaceProcessor:
    """
    Face image processing and enhancement
    """

    @staticmethod
    def read_image(image_path_or_bytes) -> np.ndarray:
        """
        Image ko read karo from file path ya bytes

        Parameters:
        - image_path_or_bytes: File path (str) ya bytes data

        Returns:
        - numpy array in BGR format
        """
        # Agar bytes hai to decode karo
        if isinstance(image_path_or_bytes, bytes):
            nparr = np.frombuffer(image_path_or_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            # File path se read karo
            image = cv2.imread(str(image_path_or_bytes))

        if image is None:
            raise ValueError("Failed to read image")

        return image

    @staticmethod
    def validate_face_image(
        image: np.ndarray,
        min_size: Tuple[int, int] = (50, 50),
        max_size: Tuple[int, int] = (4096, 4096)
    ) -> bool:
        """
        Check karo ki image valid hai ya nahi

        Parameters:
        - image: Input image
        - min_size: Minimum allowed image size
        - max_size: Maximum allowed image size

        Returns:
        - True if valid, False otherwise
        """
        height, width = image.shape[:2]

        # Size check
        if width < min_size[0] or height < min_size[1]:
            return False

        if width > max_size[0] or height > max_size[1]:
            return False

        # Check if image is completely black or white
        if np.mean(image) < 10 or np.mean(image) > 245:
            return False

        return True

    @staticmethod
    def enhance_image(image: np.ndarray) -> np.ndarray:
        """
        Image quality enhance karo for better detection

        Steps:
        1. Brightness/Contrast adjust
        2. Sharpening
        3. Noise removal
        """
        # Convert to float for processing
        img_float = image.astype(np.float32)

        # Auto contrast adjustment
        min_val = np.percentile(img_float, 2)
        max_val = np.percentile(img_float, 98)
        img_enhanced = np.clip((img_float - min_val) * 255.0 / (max_val - min_val), 0, 255)

        # Sharpening kernel apply karo
        kernel_sharpen = np.array([
            [-1, -1, -1],
            [-1,  9, -1],
            [-1, -1, -1]
        ])
        img_sharp = cv2.filter2D(img_enhanced.astype(np.uint8), -1, kernel_sharpen)

        # Slight blur for noise removal
        img_final = cv2.GaussianBlur(img_sharp, (3, 3), 0.5)

        return img_final

    @staticmethod
    def align_face(
        image: np.ndarray,
        left_eye: Tuple[int, int],
        right_eye: Tuple[int, int]
    ) -> np.ndarray:
        """
        Face ko align karo based on eye positions
        Isse recognition accuracy improve hoti hai

        Parameters:
        - image: Face image
        - left_eye: (x, y) of left eye
        - right_eye: (x, y) of right eye
        """
        # Angle calculate karo
        dx = right_eye[0] - left_eye[0]
        dy = right_eye[1] - left_eye[1]
        angle = np.degrees(np.arctan2(dy, dx))

        # Center point
        center = (image.shape[1] // 2, image.shape[0] // 2)

        # Rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Rotate image
        aligned = cv2.warpAffine(
            image,
            rotation_matrix,
            (image.shape[1], image.shape[0]),
            flags=cv2.INTER_CUBIC
        )

        return aligned

    @staticmethod
    def normalize_image(
        image: np.ndarray,
        target_size: Tuple[int, int] = (112, 112)
    ) -> np.ndarray:
        """
        Image ko normalize karo for model input
        Standard preprocessing pipeline
        """
        # Resize
        image = cv2.resize(image, target_size)

        # Convert to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Normalize pixel values (0-1 range)
        image = image.astype(np.float32) / 255.0

        # Standardize (mean=0.5, std=0.5)
        image = (image - 0.5) / 0.5

        return image

    @staticmethod
    def image_to_bytes(image: np.ndarray, format: str = "jpg") -> bytes:
        """
        Numpy image ko bytes mein convert karo
        API response ke liye
        """
        # Encode image
        success, buffer = cv2.imencode(f".{format}", image)

        if not success:
            raise ValueError("Failed to encode image")

        return buffer.tobytes()
