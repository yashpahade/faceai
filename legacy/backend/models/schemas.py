# ============================================
# DATA MODELS & SCHEMAS
# ============================================
"""
Pydantic models for request/response validation
Ye ensure karta hai ki saara data sahi format mein ho
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class PersonInfo(BaseModel):
    """Person ka basic information"""
    name: str = Field(..., min_length=2, max_length=100, description="Person ka naam")
    email: Optional[str] = Field(None, description="Optional email")
    phone: Optional[str] = Field(None, description="Optional phone number")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Extra information")

class FaceRegistrationRequest(BaseModel):
    """Face register karne ka request format"""
    person_info: PersonInfo
    image_quality: Optional[str] = Field("high", description="Image quality preference")

class FaceRecognitionRequest(BaseModel):
    """Face recognize karne ka request format"""
    threshold: Optional[float] = Field(0.6, ge=0.1, le=1.0, description="Recognition threshold")
    max_results: Optional[int] = Field(5, ge=1, le=20, description="Maximum results to return")

class FaceDetectionResult(BaseModel):
    """Face detection ka result"""
    face_id: str
    bbox: List[int]  # [x, y, width, height]
    confidence: float
    landmarks: Optional[List[List[float]]] = None  # Facial landmarks

class FaceRecognitionResult(BaseModel):
    """Face recognition ka result"""
    face_id: str
    matched_person: Optional[PersonInfo] = None
    confidence_score: float
    is_match: bool
    bbox: List[int]
    processing_time: float

class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    message: str
    data: Optional[Dict] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    request_id: Optional[str] = None

class SystemStatus(BaseModel):
    """System health status"""
    status: str  # "healthy", "degraded", "unhealthy"
    total_faces_registered: int
    faiss_index_size: int
    uptime: float
    memory_usage: float
    last_rebuild: Optional[str] = None
