# ============================================
# CONFIGURATION SETTINGS
# ============================================
"""
Ye file saare configuration settings ko manage karti hai
Environment variables se settings load karta hai
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Environment variables load karo
load_dotenv()

class Settings:
    """Main configuration class"""

    # Server settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

    # Application paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    UPLOAD_DIR = BASE_DIR / "uploads"

    # FAISS index path
    FAISS_INDEX_PATH = DATA_DIR / "face_index.faiss"
    METADATA_PATH = DATA_DIR / "metadata.json"

    # Face detection settings
    FACE_DETECTION_THRESHOLD = float(os.getenv("FACE_DETECTION_THRESHOLD", 0.5))
    FACE_RECOGNITION_THRESHOLD = float(os.getenv("FACE_RECOGNITION_THRESHOLD", 0.6))
    MAX_FACES_PER_IMAGE = int(os.getenv("MAX_FACES_PER_IMAGE", 10))

    # Vector settings
    VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", 512))

    # Upload settings
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 10485760))
    ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png").split(","))

    # Create necessary directories
    def __init__(self):
        """Ensure all directories exist"""
        self.DATA_DIR.mkdir(exist_ok=True, parents=True)
        self.UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
        (self.DATA_DIR / "faces").mkdir(exist_ok=True, parents=True)

# Global settings instance
settings = Settings()
