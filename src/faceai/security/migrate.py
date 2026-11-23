"""
Embeddings ko encrypt / nayi key pe rotate karo (ek transaction mein).

    $env:FACEAI_ENCRYPTION_KEYS = "2:<new>,1:<old>"
    python -m faceai.security.migrate

1. Plaintext rows (Phase 1-6 wali DB) -> active key se encrypt
2. Purani key wale rows -> active (pehli) key pe re-encrypt
Uske baad purani key config se hata sakte ho. Server band karke chalao (ya baad mein restart karo).
"""

from faceai.config import get_settings
from faceai.security.crypto import Cipher, parse_keys
from faceai.store.db import Database


def main() -> None:
    s = get_settings()
    if not s.encryption_keys:
        raise SystemExit("FACEAI_ENCRYPTION_KEYS is not set")
    cipher = Cipher(parse_keys(s.encryption_keys))
    db = Database(s.db_path, cipher=cipher)
    before = db.count_unencrypted()
    changed = db.reencrypt_all()
    db.add_audit("security.reencrypt", "system:migrate", detail={"rows": changed})
    db.close()
    print(
        f"{changed} embeddings (re)encrypted with key id {cipher.active_id} ({before} were plain)"
    )


if __name__ == "__main__":
    main()
