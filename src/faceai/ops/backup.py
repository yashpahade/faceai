"""
Backups (Phase E). Cron / scheduled container se roz chalao.

    python -m faceai.ops.backup --out /backups --keep 7

1. Biometric SQLite (`data/faceai.db`): SQLite online backup API -> consistent copy, server chalte
   hue bhi (file copy karne se aadha-likha DB aa sakta hai). Embeddings already AES-GCM encrypted,
   isliye backup bhi encrypted hai. KEY backup ke saath KABHI mat rakho.
2. Product DB: Postgres ho to `pg_dump` (compose ka `backup` service ye karta hai); SQLite ho to
   wahi online backup.
3. Retention: sirf aakhri `--keep` backups. Purane backups bhi personal data hain: right to be
   forgotten ka matlab hai deleted users backups se bhi `keep` din mein gayab ho jaate hain.

Backup ka asli test = RESTORE. `--verify` har backup kholke integrity check karta hai.
"""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


def sqlite_backup(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # closing(): `with sqlite3.connect()` sirf commit karta hai, close NAHI. Windows pe khula
    # handle file delete (prune) rok deta hai.
    with closing(sqlite3.connect(src)) as s, closing(sqlite3.connect(dest)) as d:
        s.backup(d)
    return dest


def verify(path: Path) -> bool:
    with closing(sqlite3.connect(path)) as c:
        return c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def prune(folder: Path, pattern: str, keep: int) -> list[Path]:
    files = sorted(folder.glob(pattern))
    old = files[:-keep] if keep > 0 else files
    for f in old:
        f.unlink()
    return old


def main() -> None:
    from faceai.config import get_settings

    s = get_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=s.data_dir / "backups")
    ap.add_argument("--keep", type=int, default=7)
    ap.add_argument("--verify", action="store_true", default=True)
    args = ap.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    targets = [("biometric", s.db_path)]
    if s.product_db_url.startswith("sqlite:///"):
        targets.append(("product", Path(s.product_db_url.removeprefix("sqlite:///"))))
    for name, src in targets:
        if not src.exists():
            print(f"skip {name}: {src} missing")
            continue
        dest = sqlite_backup(src, args.out / f"{name}-{stamp}.db")
        ok = verify(dest) if args.verify else True
        removed = prune(args.out, f"{name}-*.db", args.keep)
        print(f"{name}: {dest} ({'verified' if ok else 'INTEGRITY FAILED'}), pruned {len(removed)}")
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
