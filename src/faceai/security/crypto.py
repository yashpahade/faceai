"""
Embeddings ka encryption at rest (AES-256-GCM).

Face embedding = BIOMETRIC data. Password leak ho to badal lo; chehra badal nahi sakte.
DB file chori ho (backup, laptop, galat permissions), to bhi vectors padhne layak nahi hone chahiye.

AES-GCM kyun?
- Encryption + integrity ek saath: koi ciphertext ka ek bit bhi badle to decrypt FAIL hoga.
- AAD (associated data) = `person_id|model_id`. Ciphertext us row se bandh jaata hai: attacker
  DB mein A ki embedding uthake B ki row mein chipka de ("main B hoon"), to decrypt fail hoga.
- Har encryption ka naya random 12-byte nonce (same nonce + same key dobara = GCM toot jaata hai).

Format: b"E1" | key_id (1 byte) | nonce (12) | ciphertext+tag
key_id se key rotation: naya key add karo (FACEAI_ENCRYPTION_KEYS="2:<new>,1:<old>"), pehli key
se encrypt hota hai, purani se ab bhi decrypt ho jaata hai; `python -m faceai.security.migrate`
sab rows ko nayi key pe le aata hai, phir purani key hata do.

Key kahan rakhein? Env var / secret manager (Vault, AWS KMS, k8s Secret). DB ke saath KABHI nahi.
Naya key:  python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"E1"
NONCE_LEN = 12


class DecryptionError(Exception):
    pass


def parse_keys(spec: str) -> dict[int, bytes]:
    """'2:<b64>,1:<b64>' (ya sirf '<b64>' => id 1) -> {id: 32-byte key}. Pehli = active key."""
    keys: dict[int, bytes] = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        kid, _, b64 = part.rpartition(":")
        key = base64.b64decode(b64)
        if len(key) != 32:
            raise ValueError("encryption key must be 32 bytes (base64-encoded)")
        keys[int(kid) if kid else 1] = key
    return keys


class Cipher:
    def __init__(self, keys: dict[int, bytes]):
        if not keys:
            raise ValueError("at least one key required")
        self.active_id = next(iter(keys))
        self._aes = {kid: AESGCM(k) for kid, k in keys.items()}

    @staticmethod
    def is_encrypted(blob: bytes) -> bool:
        return blob[:2] == MAGIC

    def key_id(self, blob: bytes) -> int:
        return blob[2]

    def encrypt(self, plaintext: bytes, aad: bytes) -> bytes:
        nonce = os.urandom(NONCE_LEN)
        ct = self._aes[self.active_id].encrypt(nonce, plaintext, aad)
        return MAGIC + bytes([self.active_id]) + nonce + ct

    def decrypt(self, blob: bytes, aad: bytes) -> bytes:
        if not self.is_encrypted(blob):
            raise DecryptionError("not an encrypted blob")
        kid = blob[2]
        if kid not in self._aes:
            raise DecryptionError(f"unknown key id {kid} (key removed before migration?)")
        nonce, ct = blob[3 : 3 + NONCE_LEN], blob[3 + NONCE_LEN :]
        try:
            return self._aes[kid].decrypt(nonce, ct, aad)
        except Exception as e:  # InvalidTag: tampered data, wrong key, or wrong row (AAD)
            raise DecryptionError("integrity check failed") from e
