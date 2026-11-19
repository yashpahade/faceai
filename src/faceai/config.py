"""
Centralized, typed configuration.

Kyun pydantic-settings?
- Legacy code mein `os.getenv(...)` har jagah bikhra tha, aur galat value (e.g. PORT="abc")
  runtime pe kahin beech mein crash karti thi.
- Yahan har setting ka TYPE aur VALIDATION ek jagah hai. Galat config => app start hi nahi hoga
  ("fail fast"), jo production mein bahut zaroori hai.

Priority order (high -> low): environment variables > .env file > defaults below.
Saare env vars ka prefix `FACEAI_` hai, e.g. FACEAI_PORT=9000
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FACEAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    env: Literal["dev", "test", "prod"] = "dev"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = Field(
        default=False,
        description="prod mein True: JSON logs machine-readable hote hain (Loki/ELK ke liye)",
    )

    # --- Paths ---
    data_dir: Path = PROJECT_ROOT / "data"
    models_dir: Path = PROJECT_ROOT / "models"

    # --- Model runtime ---
    model_pack: str = "buffalo_l"
    device: Literal["auto", "cuda", "cpu"] = Field(
        default="auto", description="auto = GPU mile to GPU, warna CPU"
    )
    det_size: int = Field(default=640, ge=160, le=1280, description="detector input (square)")

    # --- Recognition (Phase 2 mein evaluation se tune hoga, abhi placeholder) ---
    det_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    match_threshold: float = Field(
        default=0.4, ge=-1.0, le=1.0, description="cosine similarity; >= isse => same person"
    )
    max_upload_mb: int = Field(default=10, gt=0)

    # --- Enrollment quality gates ---
    enroll_min_det_score: float = Field(default=0.6, ge=0.0, le=1.0)
    enroll_min_face_px: int = Field(default=60, ge=16, description="bbox ki chhoti side (pixels)")
    enroll_min_sharpness: float = Field(default=40.0, ge=0.0, description="Laplacian variance")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "faceai.db"

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Ek hi Settings object poori app mein (cached). Tests mein `get_settings.cache_clear()`."""
    return Settings()
