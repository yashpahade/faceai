"""
Face verification metrics - pure numpy, no model needed.

Setup: N pairs, har pair ka similarity `score` aur `label` (1 = same person, 0 = alag log).
Ek threshold t chuno: score >= t => "same" bolo.

  TAR (True Accept Rate)  = same-person pairs mein se kitne sahi accept hue   (zyada = achha)
  FAR (False Accept Rate) = alag-logon pairs mein se kitne GALTI se accept hue (kam = achha)
  FRR = 1 - TAR           = genuine user ko reject kiya (user pareshaan)

Trade-off: threshold badhao -> FAR girta hai (secure) par FRR badhta hai (annoying). Dono saath
kam nahi kar sakte. ROC curve yahi poora trade-off dikhata hai.

Industry "accuracy" nahi bolti, bolti hai "TAR @ FAR=1e-3": "har 1000 mein se sirf 1 impostor
accept ho, us setting pe kitne genuine users pass hote hain?"
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class RocCurve:
    far: np.ndarray  # ascending
    tar: np.ndarray
    thresholds: np.ndarray  # far[i], tar[i] at score >= thresholds[i]


def roc_curve(scores: np.ndarray, labels: np.ndarray) -> RocCurve:
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(bool)
    n_pos, n_neg = labels.sum(), (~labels).sum()
    if n_pos == 0 or n_neg == 0:
        raise ValueError("need both genuine (1) and impostor (0) pairs")

    order = np.argsort(-scores, kind="stable")
    s, y = scores[order], labels[order]
    # ties: sirf har distinct score ke last index pe point rakho
    distinct = np.r_[np.where(np.diff(s))[0], len(s) - 1]
    tp = np.cumsum(y)[distinct]
    fp = np.cumsum(~y)[distinct]
    tar = np.r_[0.0, tp / n_pos]
    far = np.r_[0.0, fp / n_neg]
    thr = np.r_[np.inf, s[distinct]]
    return RocCurve(far=far, tar=tar, thresholds=thr)


def auc(roc: RocCurve) -> float:
    """Area under ROC. 1.0 = perfect, 0.5 = random coin toss."""
    return float(np.trapezoid(roc.tar, roc.far))


def tar_at_far(roc: RocCurve, target_far: float) -> tuple[float, float]:
    """Sabse zyada TAR jahan FAR <= target. Return (tar, threshold)."""
    ok = np.where(roc.far <= target_far)[0]
    i = ok[np.argmax(roc.tar[ok])]
    return float(roc.tar[i]), float(roc.thresholds[i])


def eer(roc: RocCurve) -> tuple[float, float]:
    """Equal Error Rate: wo point jahan FAR == FRR. Ek number mein model compare karne ke liye."""
    frr = 1 - roc.tar
    i = int(np.argmin(np.abs(roc.far - frr)))
    return float((roc.far[i] + frr[i]) / 2), float(roc.thresholds[i])


def best_accuracy_threshold(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Threshold jo (TP + TN) / N maximize kare. Return (accuracy, threshold)."""
    labels = np.asarray(labels).astype(bool)
    cands = np.unique(scores)
    # midpoints between consecutive unique scores = sabse stable thresholds
    cands = np.r_[cands[0] - 1e-6, (cands[:-1] + cands[1:]) / 2, cands[-1] + 1e-6]
    best_acc, best_t = -1.0, 0.0
    for t in cands:
        acc = float(((scores >= t) == labels).mean())
        if acc > best_acc:
            best_acc, best_t = acc, float(t)
    return best_acc, best_t


def kfold_accuracy(
    scores: np.ndarray, labels: np.ndarray, folds: np.ndarray
) -> tuple[float, float, list[float]]:
    """
    LFW standard protocol: 10 folds. Har baar 9 folds pe threshold chuno, bache 1 pe test karo.
    Kyun? Jis data pe threshold tune kiya usi pe accuracy naapna = cheating (overfitting).
    Return (mean_acc, std_acc, per-fold thresholds).
    """
    accs, thrs = [], []
    for k in np.unique(folds):
        train, test = folds != k, folds == k
        _, t = best_accuracy_threshold(scores[train], labels[train])
        accs.append(float(((scores[test] >= t) == labels[test].astype(bool)).mean()))
        thrs.append(t)
    return float(np.mean(accs)), float(np.std(accs)), thrs
