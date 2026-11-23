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
    enroll_min_face_px: int = Field(
        default=80, ge=16, description="bbox ki chhoti side (pixels); Phase A: 60 -> 80"
    )
    enroll_min_sharpness: float = Field(default=40.0, ge=0.0, description="Laplacian variance")

    # --- Serving performance (Phase 4) ---
    batching: Literal["auto", "on", "off"] = Field(
        default="off",
        description="cross-request embedding micro-batching; auto = sirf GPU pe. Default off: "
        "RTX 3050 laptop pe load test mein throughput nahi badha (docs/phase-4-serving.md)",
    )
    # GPU benchmark: per-face 10.6 ms (b=1) -> 4.4 ms (b=16) -> 4.9 ms (b=32). 16 sweet spot.
    batch_max_size: int = Field(default=16, ge=1, le=256)
    batch_max_wait_ms: float = Field(default=3.0, ge=0.0, le=100.0)
    max_concurrent_inference: int = Field(
        default=4, ge=1, description="ek saath kitni requests inference karein; baaki wait/503"
    )
    max_queue_wait_ms: float = Field(default=2000.0, ge=0.0, description="slot ka max intezaar")
    ort_intra_op_threads: int = Field(
        default=0, ge=0, description="CPU threads per ONNX session; 0 = ORT default (all cores)"
    )

    # --- Accuracy options (Phase A) - reports/experiments/phase_a.json ke results se defaults ---
    det_extra_sizes: list[int] = Field(
        default=[], description="multi-scale: det_size ke saath ye sizes bhi (e.g. [1280])"
    )
    clahe: bool = Field(default=False, description="detection se pehle CLAHE contrast fix")
    flip_tta: bool = Field(default=False, description="face + mirror embed karke average")

    # --- Monitoring (Phase 6) ---
    drift_reference_size: int = Field(default=500, ge=50, description="reference window (faces)")
    drift_window_size: int = Field(default=500, ge=50, description="rolling current window (faces)")

    # --- Trust & safety (Phase 7) ---
    encryption_keys: str | None = Field(
        default=None,
        repr=False,  # logs/tracebacks mein key kabhi na chhape
        description="'<b64>' ya '2:<new>,1:<old>'; embeddings AES-GCM encrypted at rest",
    )
    api_key_hashes: str = Field(
        default="", repr=False, description="comma-separated SHA-256 hashes of API keys"
    )
    auth: Literal["auto", "required", "off"] = Field(
        default="auto", description="auto = prod mein required, warna off"
    )
    liveness: Literal["off", "required"] = "off"
    retention_days: int | None = Field(
        default=None, ge=1, description="isse purani embeddings startup pe purge"
    )

    # --- Product: attendance SaaS (Phase B) ---
    product_db_url: str = Field(
        default=f"sqlite:///{(PROJECT_ROOT / 'data' / 'faceai_app.db').as_posix()}",
        description="users/batches/attendance DB; prod: postgresql+psycopg://...",
    )
    jwt_secret: str | None = Field(
        default=None, repr=False, description="HS256 secret (32+ chars); prod mein zaroori"
    )
    jwt_ttl_minutes: int = Field(default=720, ge=5, le=43200)
    timezone: str = Field(default="Asia/Kolkata", description="attendance days/times isi zone mein")
    face_login_threshold: float = Field(
        default=0.5,
        ge=-1.0,
        le=1.0,
        description="face login ke liye min similarity (recognize threshold se STRICT rakho)",
    )
    face_login_margin: float = Field(
        default=0.05, ge=0.0, le=1.0, description="top-1 aur top-2 mein min farak (ambiguous => no)"
    )

    @property
    def auth_required(self) -> bool:
        return self.auth == "required" or (self.auth == "auto" and self.env == "prod")

    @property
    def api_key_hash_list(self) -> list[str]:
        return [h.strip() for h in self.api_key_hashes.split(",") if h.strip()]

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
