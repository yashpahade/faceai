"""
Stage 3: embeddings -> verification metrics, ROC, recommended threshold, error analysis.

    python -m faceai.eval.evaluate --emb data/eval/lfw_embeddings.npz --out reports/eval

Outputs (DVC inhe metrics/plots ki tarah track karta hai):
  metrics.json  - headline numbers  (`dvc metrics show`, `dvc metrics diff`)
  roc.csv       - ROC curve         (`dvc plots show`)
  scores.csv    - genuine vs impostor score histogram
  errors.json   - sabse buri galtiyan (error analysis: model KAHAN fail hota hai)
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from faceai.eval.metrics import auc, eer, kfold_accuracy, roc_curve, tar_at_far
from faceai.eval.params import load_params

FAILED_SCORE = -1.0  # jahan face detect nahi hua: worst case maano (reject), chhupao mat


def far_key(far: float) -> str:
    return f"{far:.0e}".replace("-0", "-")  # 0.001 -> "1e-3"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", type=Path, default=Path("data/eval/lfw_embeddings.npz"))
    ap.add_argument("--out", type=Path, default=Path("reports/eval"))
    args = ap.parse_args()
    p = load_params()["eval"]

    d = np.load(args.emb)
    meta = json.loads(str(d["meta"]))
    emb, ok = d["embeddings"], d["ok"]
    i1, i2, labels, folds = d["idx1"], d["idx2"], d["label"], d["fold"]

    scores = np.einsum("ij,ij->i", emb[i1], emb[i2])  # cosine (vectors normalized)
    pair_ok = ok[i1] & ok[i2]
    scores = np.where(pair_ok, scores, FAILED_SCORE)

    roc = roc_curve(scores, labels)
    acc_mean, acc_std, fold_thrs = kfold_accuracy(scores, labels, folds)
    eer_val, eer_thr = eer(roc)

    metrics = {
        "model_id": meta["model_id"],
        "dataset": "lfw-6000-pairs",
        "n_pairs": int(len(labels)),
        "failure_to_detect_rate": round(float(1 - ok.mean()), 5),
        "pairs_with_failure": int((~pair_ok).sum()),
        "kfold_accuracy": round(acc_mean, 5),
        "kfold_accuracy_std": round(acc_std, 5),
        "auc": round(auc(roc), 6),
        "eer": round(eer_val, 5),
        "eer_threshold": round(eer_thr, 4),
        "kfold_threshold_mean": round(float(np.mean(fold_thrs)), 4),
        "tar_at_far": {},
        "ms_per_image": meta["ms_per_image"],
        "device": meta["device"],
    }
    for far in p["target_fars"]:
        tar, thr = tar_at_far(roc, far)
        metrics["tar_at_far"][far_key(far)] = {"tar": round(tar, 5), "threshold": round(thr, 4)}

    op = p["operating_far"]
    op_tar, op_thr = tar_at_far(roc, op)
    metrics["recommended_threshold"] = {
        "far": op,
        "threshold": round(op_thr, 4),
        "tar": round(op_tar, 5),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # ROC: ~400 points kaafi hain plot ke liye
    idx = np.unique(np.linspace(0, len(roc.far) - 1, 400).astype(int))
    with (args.out / "roc.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["far", "tar", "threshold"])
        for i in idx:
            w.writerow(
                [f"{roc.far[i]:.6f}", f"{roc.tar[i]:.6f}", f"{min(roc.thresholds[i], 1.0):.4f}"]
            )

    # score histogram: genuine vs impostor distributions kitni alag hain?
    bins = np.linspace(-0.3, 1.0, 66)
    g, _ = np.histogram(scores[(labels == 1) & pair_ok], bins)
    im, _ = np.histogram(scores[(labels == 0) & pair_ok], bins)
    with (args.out / "scores.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["similarity", "genuine", "impostor"])
        for b, a, c in zip(bins[:-1], g, im, strict=True):
            w.writerow([f"{b + (bins[1] - bins[0]) / 2:.3f}", int(a), int(c)])

    # error analysis at recommended threshold
    paths = d["paths"]
    fa = np.where((labels == 0) & (scores >= op_thr))[0]
    fr = np.where((labels == 1) & (scores < op_thr))[0]

    def rows(ix, key):
        ix = ix[np.argsort(key(scores[ix]))][:15]
        return [
            {
                "img1": str(paths[i1[k]]),
                "img2": str(paths[i2[k]]),
                "score": round(float(scores[k]), 4),
                "face_found": bool(pair_ok[k]),
            }
            for k in ix
        ]

    errors = {
        "threshold": op_thr,
        "false_accepts": rows(fa, lambda s: -s),  # sabse "confident" galat match pehle
        "false_rejects": rows(fr, lambda s: s),  # sabse kam score wale genuine pehle
        "n_false_accepts": int(len(fa)),
        "n_false_rejects": int(len(fr)),
    }
    (args.out / "errors.json").write_text(json.dumps(errors, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
