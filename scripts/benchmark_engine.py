"""
Engine micro-benchmark (no server): detector latency vs det_size, embedder latency vs batch size.

    python scripts/benchmark_engine.py data/samples/t1.jpg --out reports/perf/engine.json

Ye do sawaalon ka DATA deta hai:
1. det_size chhota karne se kitna fast hoga? (accuracy ka asar: params.yaml det_size badal ke
   `dvc repro` chalao - speed/accuracy trade-off dono taraf se naapo)
2. Batching se kitna fayda? ms/face batch size ke saath kitna girta hai -> MicroBatcher worth it?
"""

import argparse
import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

from faceai.config import Settings
from faceai.vision.detector import SCRFDDetector
from faceai.vision.engine import FaceEngine


def timeit(fn, n: int, warmup: int = 3) -> dict:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return {
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(samples[int(0.95 * (len(samples) - 1))], 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    s = Settings(_env_file=None)
    engine = FaceEngine(s.models_dir, s.model_pack, 640, args.device)
    engine.warmup()
    img = cv2.imread(str(args.image))
    faces = engine.analyze(img)
    print(f"device={engine.device}  image={img.shape[1]}x{img.shape[0]}  faces={len(faces)}")

    result: dict = {"device": engine.device, "detector": {}, "embedder": {}}
    print("\nDetector (per image):")
    for size in (320, 480, 640):
        det = SCRFDDetector(engine.detector.session, input_size=size)
        r = timeit(lambda d=det: d.detect(img), args.n)
        r["faces_found"] = len(det.detect(img))
        result["detector"][size] = r
        print(f"  det_size={size:4d}  p50={r['p50_ms']:7.2f} ms  faces={r['faces_found']}")

    print("\nEmbedder (one call):")
    crop = faces[0].aligned if faces else np.zeros((112, 112, 3), np.uint8)
    for bs in (1, 2, 4, 8, 16, 32):
        batch = [crop] * bs
        r = timeit(lambda b=batch: engine.embedder.embed(b), args.n)
        r["ms_per_face"] = round(r["p50_ms"] / bs, 3)
        result["embedder"][bs] = r
        print(f"  batch={bs:3d}  p50={r['p50_ms']:7.2f} ms  per-face={r['ms_per_face']:6.3f} ms")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", newline="\n")
        print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
