"""
Threshold calibration on YOUR data (domain shift ka ilaaj).

    python -m faceai.eval.calibrate --data data/calibration --far 0.001

Folder layout (consent ke saath collect karo, apne asli cameras se):
    data/calibration/
        asha/   img1.jpg img2.jpg ...     (har insaan ki 3+ photos, alag din/lighting)
        ravi/   ...

LFW ka threshold (0.253) news photos se nikla hai. Classroom webcam, phone selfie, kam roshni pe
genuine/impostor scores ki distribution alag hoti hai, isliye threshold bhi alag hoga.

Pairs: har person ke andar saare genuine pairs + utne hi random impostor pairs (alag log).
FAR=0.001 naapne ke liye ~1000+ impostor pairs chahiye; kam data pe tool warning deta hai.
Output: reports/calibration/metrics.json -> `recommended_threshold` -> FACEAI_MATCH_THRESHOLD
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from faceai.eval.metrics import auc, eer, roc_curve, tar_at_far

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def build_pairs(labels: list[str], seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(idx1, idx2, is_same). Saare genuine pairs + utne hi (ya kam se kam 1000) impostor pairs."""
    by_person: dict[str, list[int]] = {}
    for i, lab in enumerate(labels):
        by_person.setdefault(lab, []).append(i)
    genuine = [p for idx in by_person.values() for p in itertools.combinations(idx, 2)]
    people = list(by_person)
    rng = np.random.default_rng(seed)
    n_imp = max(len(genuine), 1000)
    impostor: set[tuple[int, int]] = set()
    max_possible = sum(
        len(by_person[a]) * len(by_person[b]) for a, b in itertools.combinations(people, 2)
    )
    n_imp = min(n_imp, max_possible)
    while len(impostor) < n_imp:
        a, b = rng.choice(len(people), 2, replace=False)
        i = int(rng.choice(by_person[people[a]]))
        j = int(rng.choice(by_person[people[b]]))
        impostor.add((min(i, j), max(i, j)))
    pairs = genuine + sorted(impostor)
    same = np.array([1] * len(genuine) + [0] * len(impostor))
    arr = np.array(pairs, dtype=np.int64).reshape(-1, 2)
    return arr[:, 0], arr[:, 1], same


def calibrate(embeddings: np.ndarray, ok: np.ndarray, labels: list[str], target_far: float) -> dict:
    i1, i2, same = build_pairs(labels)
    scores = np.einsum("ij,ij->i", embeddings[i1], embeddings[i2])
    scores = np.where(ok[i1] & ok[i2], scores, -1.0)  # face nahi mila => worst case
    roc = roc_curve(scores, same)
    tar, thr = tar_at_far(roc, target_far)
    e, e_thr = eer(roc)
    n_imp = int((same == 0).sum())
    out = {
        "n_images": len(labels),
        "n_people": len(set(labels)),
        "n_genuine_pairs": int(same.sum()),
        "n_impostor_pairs": n_imp,
        "failure_to_detect_rate": round(float(1 - ok.mean()), 4),
        "auc": round(auc(roc), 5),
        "eer": round(e, 5),
        "eer_threshold": round(e_thr, 4),
        "recommended_threshold": {
            "far": target_far,
            "threshold": round(thr, 4),
            "tar": round(tar, 5),
        },
        "genuine_score_p05": round(float(np.percentile(scores[same == 1], 5)), 4),
        "impostor_score_p99": round(float(np.percentile(scores[same == 0], 99)), 4),
        "warnings": [],
    }
    if n_imp * target_far < 1:
        out["warnings"].append(
            f"only {n_imp} impostor pairs: FAR={target_far} cannot be measured reliably "
            f"(need >= {int(1 / target_far)}); collect more people"
        )
    if out["n_people"] < 10:
        out["warnings"].append("fewer than 10 people: threshold is a rough estimate")
    return out


def load_folder(root: Path) -> tuple[list[Path], list[str]]:
    paths, labels = [], []
    for person in sorted(p for p in root.iterdir() if p.is_dir()):
        for img in sorted(person.iterdir()):
            if img.suffix.lower() in IMAGE_EXT:
                paths.append(img)
                labels.append(person.name)
    return paths, labels


def main() -> None:
    from faceai.config import Settings
    from faceai.eval.embed import pick_center_face
    from faceai.vision.engine import FaceEngine
    from faceai.vision.preprocess import decode_image

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/calibration"))
    ap.add_argument("--far", type=float, default=0.001)
    ap.add_argument("--out", type=Path, default=Path("reports/calibration/metrics.json"))
    args = ap.parse_args()

    s = Settings()  # serving jaisi settings (.env) -> same preprocessing jo production mein hai
    engine = FaceEngine(
        s.models_dir,
        s.model_pack,
        s.det_size,
        s.device,
        extra_det_sizes=tuple(s.det_extra_sizes),
        clahe=s.clahe,
        flip_tta=s.flip_tta,
    )
    engine.warmup()
    paths, labels = load_folder(args.data)
    if len(set(labels)) < 2:
        raise SystemExit(f"need at least 2 people with photos under {args.data}")
    emb = np.zeros((len(paths), engine.dim), np.float32)
    ok = np.zeros(len(paths), bool)
    for i, p in enumerate(paths):
        img = decode_image(p.read_bytes())
        if img is None:
            continue
        faces = engine.analyze(img, s.det_threshold)
        j = pick_center_face(faces, img.shape)
        if j is not None:
            emb[i], ok[i] = faces[j].embedding, True
    result = calibrate(emb, ok, labels, args.far)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", newline="\n")
    print(json.dumps(result, indent=2))
    print(f"\nSet FACEAI_MATCH_THRESHOLD={result['recommended_threshold']['threshold']}")


if __name__ == "__main__":
    main()
