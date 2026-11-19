"""
Model artifacts download + integrity check.

    python -m faceai.models.download

MLOps concept - model ek ARTIFACT hai, code nahi:
- git mein nahi jaata (bada binary). Yahan URL + SHA-256 checksum pinned hai.
- Checksum match nahi => file corrupt / tampered / galat version => fail. Silent galat model se
  bura kuch nahi (accuracy chupke se gir jaati hai).
- Phase 3 mein ye kaam MLflow Model Registry karega (versions, stages, lineage).

LICENSE: InsightFace pretrained models sirf NON-COMMERCIAL research ke liye hain.
"""

import argparse
import hashlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from faceai.config import get_settings

MODEL_PACKS: dict[str, dict] = {
    "buffalo_l": {
        "url": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        "license": "non-commercial research only (InsightFace)",
        "files": {
            # filename: sha256 (pinned)
            "det_10g.onnx": "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
            "w600k_r50.onnx": "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
        },
    }
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(pack_dir: Path, files: dict[str, str]) -> list[str]:
    """Return list of problems (empty = sab theek)."""
    problems = []
    for name, expected in files.items():
        p = pack_dir / name
        if not p.exists():
            problems.append(f"missing: {name}")
        elif sha256(p) != expected:
            problems.append(f"checksum mismatch: {name}")
    return problems


def _progress(blocks: int, block_size: int, total: int) -> None:
    if total > 0:
        pct = min(100, blocks * block_size * 100 // total)
        sys.stdout.write(f"\r  downloading... {pct}%")
        sys.stdout.flush()


def download(pack: str, models_dir: Path, force: bool = False) -> Path:
    spec = MODEL_PACKS[pack]
    pack_dir = models_dir / pack
    if not force and not verify(pack_dir, spec["files"]):
        print(f"[ok] {pack} already present and verified at {pack_dir}")
        return pack_dir

    print(f"Model pack '{pack}' - license: {spec['license']}")
    pack_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / f"{pack}.zip"
        urllib.request.urlretrieve(spec["url"], zip_path, _progress)
        print()
        with zipfile.ZipFile(zip_path) as zf:
            members = {Path(m).name: m for m in zf.namelist()}
            for name in spec["files"]:
                if name not in members:
                    raise RuntimeError(f"{name} not found in archive")
                with zf.open(members[name]) as src, (pack_dir / name).open("wb") as dst:
                    shutil.copyfileobj(src, dst)

    problems = verify(pack_dir, spec["files"])
    if problems:
        for name in spec["files"]:
            print(f"  {name}: sha256={sha256(pack_dir / name)}")
        raise RuntimeError(f"verification failed: {problems}")
    print(f"[ok] {pack} downloaded and verified -> {pack_dir}")
    return pack_dir


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--pack", default=s.model_pack, choices=list(MODEL_PACKS))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    download(args.pack, s.models_dir, args.force)


if __name__ == "__main__":
    main()
