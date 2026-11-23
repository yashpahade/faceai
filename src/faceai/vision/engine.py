"""
FaceEngine: detect -> align -> embed, EK pass mein.

Legacy pipeline: detect -> crop -> crop pe DOBARA detect -> fail -> 4 fallbacks (aur galat face ki
embedding ka risk). Yahan har face ki embedding usi face ke apne landmarks se aati hai.
Koi fallback nahi.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np

from faceai.vision.align import align_face
from faceai.vision.detector import SCRFDDetector, merge_detections
from faceai.vision.embedder import ArcFaceEmbedder
from faceai.vision.preprocess import apply_clahe
from faceai.vision.runtime import create_session
from faceai.vision.types import DetectedFace

DETECTOR_FILE = "det_10g.onnx"
RECOGNIZER_FILE = "w600k_r50.onnx"

logger = logging.getLogger(__name__)


class FaceEngine:
    def __init__(
        self,
        models_dir: Path,
        pack: str,
        det_size: int = 640,
        device: str = "auto",
        intra_op_threads: int = 0,
        extra_det_sizes: tuple[int, ...] = (),
        clahe: bool = False,
        flip_tta: bool = False,
    ):
        pack_dir = models_dir / pack
        det_sess = create_session(pack_dir / DETECTOR_FILE, device, intra_op_threads)
        rec_sess = create_session(pack_dir / RECOGNIZER_FILE, device, intra_op_threads)
        self.detector = SCRFDDetector(det_sess, input_size=det_size)
        # Phase A options (default off; scripts/accuracy_experiments.py ke results se decide)
        self.extra_detectors = [SCRFDDetector(det_sess, input_size=s) for s in extra_det_sizes]
        self.clahe = clahe
        self.flip_tta = flip_tta
        self.embedder = ArcFaceEmbedder(rec_sess)
        # Serving mein ise MicroBatcher se replace kiya jaata hai (Phase 4); default = direct call
        self.embed_fn: Callable[[list[np.ndarray]], np.ndarray] = self.embedder.embed
        self.dim = self.embedder.dim
        # model_id har stored embedding ke saath save hota hai (embedding versioning)
        self.model_id = f"{pack}/{Path(RECOGNIZER_FILE).stem}"
        self.requested_device = device

    @property
    def device(self) -> str:
        """ASLI device. ORT GPU fail hone pe chupchaap CPU pe chala jaata hai (session recreate),
        isliye har baar session se poochho - kabhi cached value pe bharosa mat karo."""
        sessions = (self.detector.session, self.embedder.session)
        on_gpu = all(s.get_providers()[0] == "CUDAExecutionProvider" for s in sessions)
        return "cuda" if on_gpu else "cpu"

    def detect(self, image_bgr: np.ndarray, det_threshold: float) -> list[DetectedFace]:
        faces = self.detector.detect(image_bgr, threshold=det_threshold)
        if self.extra_detectors:
            # Multi-scale: chhote faces bade input pe, bade faces chhote pe -> merge + NMS
            for d in self.extra_detectors:
                faces += d.detect(image_bgr, threshold=det_threshold)
            faces = merge_detections(faces, self.detector.nms_threshold)
        return faces

    def embed_aligned(self, crops: list[np.ndarray]) -> np.ndarray:
        if not self.flip_tta:
            return self.embed_fn(crops)
        # Flip-TTA: face + mirror image dono embed, average. Mirror-invariant embedding.
        e = self.embed_fn(crops + [c[:, ::-1].copy() for c in crops])
        n = len(crops)
        avg = e[:n] + e[n:]
        return avg / np.linalg.norm(avg, axis=1, keepdims=True).clip(min=1e-12)

    def analyze(self, image_bgr: np.ndarray, det_threshold: float = 0.5) -> list[DetectedFace]:
        if self.clahe:
            image_bgr = apply_clahe(image_bgr)
        faces = self.detect(image_bgr, det_threshold)
        if not faces:
            return []
        for f in faces:
            f.aligned = align_face(image_bgr, f.kps)
        embeddings = self.embed_aligned([f.aligned for f in faces])  # saare faces ek batch mein
        for f, e in zip(faces, embeddings, strict=True):
            f.embedding = e
        return faces

    def warmup(self) -> None:
        """
        Pehli inference slow hoti hai (CUDA kernels init) - startup pe hi kar lo.
        DONO models chalao: black image pe koi face nahi milta, to sirf analyze() se
        embedder kabhi warm nahi hota (aur uski GPU problem startup pe pakdi nahi jaati).
        """
        size = self.detector.input_size
        self.detector.detect(np.zeros((size, size, 3), np.uint8))
        self.embedder.embed([np.zeros((112, 112, 3), np.uint8)])
        if self.requested_device == "cuda" and self.device != "cuda":
            raise RuntimeError("device=cuda requested but inference fell back to CPU")
        if self.requested_device == "auto" and self.device == "cpu":
            logger.warning("running on CPU (GPU unavailable or failed); inference will be slower")
