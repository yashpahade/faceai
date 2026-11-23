"""
Phase A: accuracy ideas ko LFW pe NAAPO, phir decide karo (andaaze se nahi).

    python scripts/accuracy_experiments.py --lfw data/lfw --out reports/experiments/phase_a.json

Teen detection passes (har LFW image pe), unse 7 variants derive hote hain:
  pass 640        -> baseline (thr 0.5), thr 0.4, flip-TTA
  pass 1280       -> det_size 1280, multi-scale (640 + 1280 merged with NMS)
  pass 640+CLAHE  -> CLAHE, CLAHE + flip-TTA
Har variant: same LFW 6000 pairs, same metrics (Phase 2) -> seedha comparison.

Flip-TTA = face aur uski mirror image dono embed karo, average lo. Front camera mirror wali
problem bhi isse handle hoti hai, kyunki embedding mirror-invariant ho jaati hai.
"""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from faceai.config import Settings
from faceai.eval.embed import pick_center_face
from faceai.eval.evaluate import FAILED_SCORE, far_key
from faceai.eval.lfw import load_pairs
from faceai.eval.metrics import auc, eer, kfold_accuracy, roc_curve, tar_at_far
from faceai.vision.align import align_face
from faceai.vision.detector import SCRFDDetector, _nms
from faceai.vision.engine import FaceEngine
from faceai.vision.preprocess import apply_clahe

LOW_THR = 0.3  # sab detect karo, variants baad mein score se filter karte hain


def embed_faces(engine, img, faces):
    """(plain, flip-TTA) embeddings har face ke liye."""
    if not faces:
        return np.empty((0, engine.dim)), np.empty((0, engine.dim))
    crops = [align_face(img, f.kps) for f in faces]
    flips = [c[:, ::-1].copy() for c in crops]
    e = engine.embedder.embed(crops + flips)
    plain, flipped = e[: len(faces)], e[len(faces) :]
    tta = plain + flipped
    tta /= np.linalg.norm(tta, axis=1, keepdims=True)
    return plain, tta


def merge(faces_a, faces_b, iou=0.4):
    allf = faces_a + faces_b
    if not allf:
        return []
    boxes = np.stack([f.bbox for f in allf]).astype(np.float32)
    scores = np.array([f.det_score for f in allf], np.float32)
    return [allf[i] for i in _nms(boxes, scores, iou)]


def select(faces, thr, shape):
    kept = [f for f in faces if f.det_score >= thr]
    j = pick_center_face(kept, shape)
    return None if j is None else kept[j]


def metrics_for(emb, ok, pairs_idx, labels, folds):
    i1, i2 = pairs_idx
    scores = np.einsum("ij,ij->i", emb[i1], emb[i2])
    pair_ok = ok[i1] & ok[i2]
    scores = np.where(pair_ok, scores, FAILED_SCORE)
    roc = roc_curve(scores, labels)
    acc, std, _ = kfold_accuracy(scores, labels, folds)
    e, _ = eer(roc)
    out = {
        "failure_to_detect_rate": round(float(1 - ok.mean()), 5),
        "kfold_accuracy": round(acc, 5),
        "auc": round(auc(roc), 6),
        "eer": round(e, 5),
    }
    for far in (1e-4, 1e-3):
        tar, thr = tar_at_far(roc, far)
        out[f"tar_at_far_{far_key(far)}"] = round(tar, 5)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lfw", type=Path, default=Path("data/lfw"))
    ap.add_argument("--out", type=Path, default=Path("reports/experiments/phase_a.json"))
    ap.add_argument("--limit", type=int, default=0, help="debug: sirf pehli N images")
    args = ap.parse_args()

    s = Settings(_env_file=None)
    engine = FaceEngine(s.models_dir, s.model_pack, 640, s.device)
    engine.warmup()
    det = {640: engine.detector, 1280: SCRFDDetector(engine.detector.session, input_size=1280)}

    pairs = load_pairs(args.lfw)
    paths = sorted(set(pairs.path1) | set(pairs.path2))
    if args.limit:
        paths = paths[: args.limit]
    index = {p: i for i, p in enumerate(paths)}
    keep = np.array(
        [a in index and b in index for a, b in zip(pairs.path1, pairs.path2, strict=False)]
    )
    i1 = np.array([index[a] for a, k in zip(pairs.path1, keep, strict=False) if k])
    i2 = np.array([index[b] for b, k in zip(pairs.path2, keep, strict=False) if k])
    labels, folds = pairs.label[keep], pairs.fold[keep]

    variants = [
        "baseline_640_thr0.5",
        "thr0.4",
        "flip_tta",
        "det1280",
        "multiscale_640+1280",
        "clahe",
        "clahe+flip_tta",
    ]
    emb = {v: np.zeros((len(paths), engine.dim), np.float32) for v in variants}
    ok = {v: np.zeros(len(paths), bool) for v in variants}
    ms = {"640": [], "1280": [], "clahe_640": []}

    def put(v, i, img, face, use_tta):
        if face is None:
            return
        plain, tta = embed_faces(engine, img, [face])
        emb[v][i] = (tta if use_tta else plain)[0]
        ok[v][i] = True

    t_start = time.perf_counter()
    for i, rel in enumerate(paths):
        img = cv2.imread(str(args.lfw / rel))
        t0 = time.perf_counter()
        f640 = det[640].detect(img, LOW_THR)
        t1 = time.perf_counter()
        f1280 = det[1280].detect(img, LOW_THR)
        t2 = time.perf_counter()
        img_c = apply_clahe(img)
        fc = det[640].detect(img_c, LOW_THR)
        t3 = time.perf_counter()
        ms["640"].append((t1 - t0) * 1000)
        ms["1280"].append((t2 - t1) * 1000)
        ms["clahe_640"].append((t3 - t2) * 1000)

        put("baseline_640_thr0.5", i, img, select(f640, 0.5, img.shape), False)
        put("thr0.4", i, img, select(f640, 0.4, img.shape), False)
        put("flip_tta", i, img, select(f640, 0.5, img.shape), True)
        put("det1280", i, img, select(f1280, 0.5, img.shape), False)
        put("multiscale_640+1280", i, img, select(merge(f640, f1280), 0.5, img.shape), False)
        put("clahe", i, img_c, select(fc, 0.5, img.shape), False)
        put("clahe+flip_tta", i, img_c, select(fc, 0.5, img.shape), True)
        if (i + 1) % 1000 == 0:
            el = time.perf_counter() - t_start
            print(
                f"  {i + 1}/{len(paths)}  {el / (i + 1) * 1000:.0f} ms/img (3 passes)", flush=True
            )

    result = {
        "device": engine.device,
        "n_images": len(paths),
        "n_pairs": int(len(labels)),
        "detector_ms_p50": {k: round(float(np.median(v)), 2) for k, v in ms.items()},
        "variants": {v: metrics_for(emb[v], ok[v], (i1, i2), labels, folds) for v in variants},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", newline="\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
