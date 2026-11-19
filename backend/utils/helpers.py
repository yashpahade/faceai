# ============================================
# HELPER FUNCTIONS
# ============================================
"""
Common utility functions jo baar baar use hongi
"""

import os
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

def generate_unique_id() -> str:
    """
    Unique ID generate karo har face/user ke liye
    Format: face_timestamp_uuid
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"face_{timestamp}_{unique_id}"

def get_timestamp() -> str:
    """Current timestamp in readable format"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def validate_image_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Check karo ki uploaded file image hai ya nahi
    Extension check karta hai
    """
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in allowed_extensions

def format_file_size(size_in_bytes: int) -> str:
    """File size ko readable format mein convert karo"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} TB"

def save_json(filepath: Path, data: dict) -> bool:
    """
    JSON file mein data save karo
    Returns True if successful
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False

def load_json(filepath: Path) -> Optional[dict]:
    """
    JSON file se data load karo
    Returns None if file doesn't exist or error
    """
    try:
        if not filepath.exists():
            return {}
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return None

def calculate_similarity_percentage(distance: float) -> float:
    """
    FAISS distance ko similarity percentage mein convert karo
    Lower distance = Higher similarity
    """
    # L2 distance ko similarity mein convert
    similarity = max(0, min(100, (1 - distance/2) * 100))
    return round(similarity, 2)