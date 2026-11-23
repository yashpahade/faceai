"""
Retention policy: `--days` se purani embeddings delete (cron/scheduled job se chalao).

    python -m faceai.security.retention --days 365

Data jitna kam rakhoge, leak utna chhota hoga ("data minimization"). Running server ka index
restart pe rebuild hota hai. Ya server ko `FACEAI_RETENTION_DAYS` do: startup pe khud purge.
"""

import argparse

from faceai.config import get_settings
from faceai.security.crypto import Cipher, parse_keys
from faceai.store.db import Database


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=s.retention_days, required=s.retention_days is None)
    args = ap.parse_args()
    cipher = Cipher(parse_keys(s.encryption_keys)) if s.encryption_keys else None
    db = Database(s.db_path, cipher=cipher)
    removed = db.purge_embeddings_older_than(args.days)
    db.add_audit(
        "retention.purge",
        "system:retention",
        detail={"days": args.days, "deleted_embeddings": len(removed)},
    )
    db.close()
    print(f"purged {len(removed)} embeddings older than {args.days} days")


if __name__ == "__main__":
    main()
