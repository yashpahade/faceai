"""
Real-model smoke test (models + a group photo needed, no server).

    python scripts/smoke_real_model.py data/samples/t1.jpg [--device cpu|cuda|auto]

1. Detect faces in the group photo.
2. Enroll each face (cropped with margin) as its own "person".
3. Recognize perturbed versions of the photo (flip, downscale, darker) -> every face should
   still map to the right person.
4. Print the cross-person similarity matrix (different people -> low) and latency.

Ye ACCURACY ka proof nahi hai (same photo hai). Asli evaluation Phase 2 mein benchmark pe.
"""

import argparse
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from faceai.config import Settings
from faceai.service import RecognitionService
from faceai.store.db import Database
from faceai.vision.engine import FaceEngine


def crop_with_margin(img: np.ndarray, bbox: np.ndarray, margin: float = 0.6) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    x1, y1 = int(max(0, x1 - margin * w)), int(max(0, y1 - margin * h))
    x2, y2 = int(min(img.shape[1], x2 + margin * w)), int(min(img.shape[0], y2 + margin * h))
    return img[y1:y2, x1:x2].copy()


def center_x(bbox) -> float:
    return (bbox[0] + bbox[2]) / 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    img = cv2.imread(str(args.image))
    assert img is not None, f"cannot read {args.image}"
    s = Settings(_env_file=None, device=args.device)

    t = time.perf_counter()
    engine = FaceEngine(s.models_dir, s.model_pack, s.det_size, s.device)
    engine.warmup()
    load_s = time.perf_counter() - t
    print(f"engine: {engine.model_id} on {engine.device} (load+warmup {load_s:.1f}s)")

    faces = engine.analyze(img, s.det_threshold)
    print(f"detected {len(faces)} faces")

    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "smoke.db")
        svc = RecognitionService(engine, db, s.model_copy(update={"enroll_min_face_px": 20}))

        # enroll each face as its own person (ids sorted left -> right)
        people = []
        for i, f in enumerate(sorted(faces, key=lambda f: center_x(f.bbox))):
            p = svc.create_person(f"person_{i}", consent=True)
            try:
                svc.enroll_face(p.id, crop_with_margin(img, f.bbox))
                people.append((p, center_x(f.bbox)))
            except Exception as e:
                print(f"  skip person_{i}: {e}")
        print(f"enrolled {len(people)} persons")

        # similarity matrix between different people
        embs = np.stack([f.embedding for f in sorted(faces, key=lambda f: center_x(f.bbox))])
        sim = embs @ embs.T
        off = sim[~np.eye(len(sim), dtype=bool)]
        print(
            f"cross-person similarity: max={off.max():.3f} mean={off.mean():.3f} "
            f"(threshold={s.match_threshold})"
        )

        h, w = img.shape[:2]
        variants = {
            "original": (img, lambda x: x),
            "flipped": (cv2.flip(img, 1), lambda x: w - x),
            "half-size": (cv2.resize(img, (w // 2, h // 2)), lambda x: x * 2),
            "darker": (cv2.convertScaleAbs(img, alpha=0.5, beta=0), lambda x: x),
        }
        all_ok = True
        for name, (vimg, to_orig_x) in variants.items():
            res = svc.recognize(vimg)
            correct = 0
            sims = []
            for fr in res.faces:
                cx = to_orig_x(center_x(fr.bbox))
                expected = min(people, key=lambda pc: abs(pc[1] - cx))[0]
                if fr.match and fr.match.person_id == expected.id:
                    correct += 1
                    sims.append(fr.match.similarity)
            ok = correct == len(people)
            all_ok &= ok
            print(
                f"  {name:10s} {correct}/{len(people)} correct  "
                f"min_sim={min(sims) if sims else float('nan'):.3f}  {res.timings_ms}  "
                f"{'OK' if ok else 'FAIL'}"
            )

        n = 20
        t = time.perf_counter()
        for _ in range(n):
            engine.analyze(img, s.det_threshold)
        ms = (time.perf_counter() - t) * 1000 / n
        print(f"latency: {ms:.1f} ms / image ({len(faces)} faces) on {engine.device}")
        db.close()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
