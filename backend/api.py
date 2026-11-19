import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import numpy as np
import cv2
import io
import base64

from .services.pipeline import FaceProcessingPipeline
from .config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="FaceAI - REST API")

# Allow local CORS for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    # Initialize pipeline once at startup (heavy models load here)
    try:
        app.state.pipeline = FaceProcessingPipeline()
    except Exception as e:
        logger.exception("Pipeline startup failed")
        app.state.pipeline = None


def _get_pipeline() -> FaceProcessingPipeline:
    pipeline = getattr(app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline is not initialized. Model load failed.")
    return pipeline


@app.get("/")
def root():
    """Redirect root to interactive docs for convenience."""
    return RedirectResponse(url="/docs")


def _read_image_from_upload(upload: UploadFile) -> np.ndarray:
    data = upload.file.read()
    # Try using OpenCV decode
    nparr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


@app.post("/register")
async def register(name: str = Form(...), file: UploadFile = File(...)):
    """Register a new person. Provide `name` and an image file."""
    try:
        img = _read_image_from_upload(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    pipeline = _get_pipeline()
    result = pipeline.register_person(img, name)

    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)

    return result


@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    """Recognize faces in an uploaded image."""
    try:
        img = _read_image_from_upload(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    pipeline = _get_pipeline()
    results = pipeline.process_image(img, return_visualization=False)

    # Simplify response: include bbox and recognition summary
    out = {
        "faces_found": results.get("faces_found", 0),
        "faces": []
    }

    for f in results.get("faces", []):
        rec = f.get("recognition") or {}
        face_obj = {
            "bbox": f.get("bbox"),
            "confidence": f.get("confidence"),
            "has_embedding": f.get("has_embedding", False),
            "quality": f.get("quality", {}),
            "recognition": {
                "is_recognized": rec.get("is_recognized", False),
                "best_match": rec.get("best_match") if rec.get("is_recognized") else None,
                "all_matches": rec.get("all_matches", [])
            }
        }
        out["faces"].append(face_obj)

    return out


@app.get("/faces")
def list_faces():
    pipeline = _get_pipeline()
    faces = pipeline.faiss_manager.list_all_faces()
    return {"total": len(faces), "faces": faces}


@app.delete("/faces/{face_id}")
def delete_face(face_id: str):
    pipeline = _get_pipeline()
    res = pipeline.faiss_manager.delete_person(face_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message"))
    return res


@app.post("/bulk_import")
def bulk_import():
    """Trigger bulk import of images from data/faces (same rules as CLI bulk import)."""
    faces_dir = settings.DATA_DIR / "faces"
    if not faces_dir.exists():
        raise HTTPException(status_code=400, detail=f"Faces folder not found: {faces_dir}")

    allowed = settings.ALLOWED_EXTENSIONS
    pipeline = _get_pipeline()
    added = 0
    skipped = 0

    for entry in faces_dir.iterdir():
        if entry.is_dir():
            person_name = entry.name
            for img_file in entry.iterdir():
                if not img_file.is_file():
                    continue
                if img_file.suffix.lower().lstrip('.') not in allowed:
                    skipped += 1
                    continue
                img = cv2.imread(str(img_file))
                if img is None:
                    skipped += 1
                    continue
                res = pipeline.register_person(img, person_name)
                if res.get('success'):
                    added += 1
        elif entry.is_file():
            if entry.suffix.lower().lstrip('.') not in allowed:
                skipped += 1
                continue
            stem = entry.stem
            person_name = stem.split('_')[0] if '_' in stem else stem
            img = cv2.imread(str(entry))
            if img is None:
                skipped += 1
                continue
            res = pipeline.register_person(img, person_name)
            if res.get('success'):
                added += 1

    return {"added": added, "skipped": skipped}
