"""
Stage 2: LFW pairs ki har unique image ki embedding nikalo (GPU pe).

    python -m faceai.eval.embed --lfw data/lfw --out data/eval/lfw_embeddings.npz

Embeddings ko alag stage/file mein kyun? Embedding mehenga hai (minutes), metrics sasta (seconds).
Sirf target FAR badla -> DVC sirf evaluate rerun karega, embed nahi (cached). Pipeline caching
ka yahi fayda hai.
"""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from faceai.config import Settings
from faceai.eval.lfw import load_pairs
from faceai.eval.params import load_params
from faceai.vision.engine import FaceEngine


def pick_center_face(faces, shape) -> int | None:
    """LFW protocol: photo ke CENTER wala chehra hi subject hai.

    (Background mein aur log bhi ho sakte hain.)
    """
    if not faces:
        return None
    cy, cx = shape[0] / 2, shape[1] / 2

    def dist(f):
        x1, y1, x2, y2 = f.bbox
        return ((x1 + x2) / 2 - cx) ** 2 + ((y1 + y2) / 2 - cy) ** 2

    return int(np.argmin([dist(f) for f in faces]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lfw", type=Path, default=Path("data/lfw"))
    ap.add_argument("--out", type=Path, default=Path("data/eval/lfw_embeddings.npz"))
    args = ap.parse_args()
    p = load_params()["eval"]

    s = Settings(_env_file=None)
    engine = FaceEngine(
        s.models_dir,
        s.model_pack,
        p["det_size"],
        s.device,
        extra_det_sizes=tuple(p.get("det_extra_sizes", [])),
        clahe=p.get("clahe", False),
        flip_tta=p.get("flip_tta", False),
    )
    engine.warmup()

    pairs = load_pairs(args.lfw)
    paths = sorted(set(pairs.path1) | set(pairs.path2))
    print(f"{len(paths)} unique images, model={engine.model_id}, device={engine.device}")

    emb = np.zeros((len(paths), engine.dim), np.float32)
    ok = np.zeros(len(paths), bool)
    n_faces = np.zeros(len(paths), np.int16)
    t0 = time.perf_counter()
    for i, rel in enumerate(paths):
        img = cv2.imread(str(args.lfw / rel))
        if img is None:
            raise FileNotFoundError(args.lfw / rel)
        faces = engine.analyze(img, p["det_threshold"])
        n_faces[i] = len(faces)
        j = pick_center_face(faces, img.shape)
        if j is not None:
            emb[i], ok[i] = faces[j].embedding, True
        if (i + 1) % 1000 == 0:
            ms = (time.perf_counter() - t0) / (i + 1) * 1000
            print(f"  {i + 1}/{len(paths)}  ({ms:.0f} ms/img)")
    elapsed = time.perf_counter() - t0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    index = {pth: i for i, pth in enumerate(paths)}
    np.savez_compressed(
        args.out,
        embeddings=emb,
        ok=ok,
        n_faces=n_faces,
        paths=np.array(paths),
        idx1=np.array([index[x] for x in pairs.path1]),
        idx2=np.array([index[x] for x in pairs.path2]),
        label=pairs.label,
        fold=pairs.fold,
        meta=json.dumps(
            {
                "model_id": engine.model_id,
                "device": engine.device,
                "det_size": p["det_size"],
                "ms_per_image": round(elapsed / len(paths) * 1000, 2),
            }
        ),
    )
    print(f"[ok] {ok.sum()}/{len(paths)} images with a face, {elapsed:.0f}s -> {args.out}")


if __name__ == "__main__":
    main()
