"""
LFW (Labeled Faces in the Wild) download + pairs parsing.

    python -m faceai.eval.lfw --out data/lfw

LFW: 13,233 photos, 5,749 log (zyaadatar celebrities, news photos). Verification protocol:
6,000 pairs (3,000 same person + 3,000 different), 10 folds.

DHYAN RAHE: LFW aaj ke models ke liye "aasaan" benchmark hai (~99.8%). Ye sanity check hai,
proof nahi ki aapke camera/lighting/users pe bhi itna hi chalega (domain shift). Asli threshold
apne deployment jaisa data collect karke tune hota hai.
"""

import argparse
import hashlib
import shutil
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# figshare mirror (same files scikit-learn's fetch_lfw_pairs uses)
FILES = {
    "lfw.tgz": {
        "url": "https://ndownloader.figshare.com/files/5976018",
        # matches scikit-learn's published checksum for the same file
        "sha256": "055f7d9c632d7370e6fb4afc7468d40f970c34a80d4c6f50ffec63f5a8d536c0",
    },
    "pairs.txt": {
        "url": "https://ndownloader.figshare.com/files/5976006",
        "sha256": "ea42330c62c92989f9d7c03237ed5d591365e89b3e649747777b70e692dc1592",
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch(name: str, dest: Path) -> None:
    spec = FILES[name]
    req = urllib.request.Request(spec["url"], headers={"User-Agent": "faceai-eval"})
    with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    got = _sha256(dest)
    if spec["sha256"] and got != spec["sha256"]:
        raise RuntimeError(f"{name}: checksum mismatch (got {got})")
    print(f"  {name}: sha256={got}")


def download(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _fetch("pairs.txt", out / "pairs.txt")
    with tempfile.TemporaryDirectory() as tmp:
        tgz = Path(tmp) / "lfw.tgz"
        print("  downloading lfw.tgz (~173 MB)...")
        _fetch("lfw.tgz", tgz)
        with tarfile.open(tgz) as tf:
            # filter="data": path traversal (../../evil) jaise malicious archives se bachav
            tf.extractall(out, filter="data")
    n = sum(1 for _ in (out / "lfw").rglob("*.jpg"))
    print(f"[ok] LFW ready at {out} ({n} images)")


@dataclass
class Pairs:
    path1: list[str]
    path2: list[str]
    label: np.ndarray  # 1 same, 0 different
    fold: np.ndarray


def _img(name: str, idx: str) -> str:
    return f"lfw/{name}/{name}_{int(idx):04d}.jpg"


def load_pairs(root: Path) -> Pairs:
    lines = (root / "pairs.txt").read_text().strip().splitlines()
    n_folds, n_per = map(int, lines[0].split())
    p1, p2, lab, fold = [], [], [], []
    i = 1
    for k in range(n_folds):
        for is_same in (1, 0):
            for _ in range(n_per):
                parts = lines[i].split("\t")
                i += 1
                if is_same:
                    name, a, b = parts
                    p1.append(_img(name, a))
                    p2.append(_img(name, b))
                else:
                    n1, a, n2, b = parts
                    p1.append(_img(n1, a))
                    p2.append(_img(n2, b))
                lab.append(is_same)
                fold.append(k)
    return Pairs(p1, p2, np.array(lab), np.array(fold))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/lfw"))
    download(ap.parse_args().out)


if __name__ == "__main__":
    main()
