"""
API key authentication (`X-API-Key` header).

Bina auth ke koi bhi /v1/persons se saare naam list kar sakta hai, ya kisi ki photo bhej ke pata
laga sakta hai ki wo database mein hai ya nahi. Biometric API ko kabhi khula mat chhodo.

- Server pe keys ka sirf SHA-256 HASH rakha jaata hai (FACEAI_API_KEY_HASHES), plain key nahi:
  config/env leak ho to bhi keys kaam ki nahi. (API keys random 32+ bytes hoti hain, isliye
  password jaisa slow hash (bcrypt) zaroori nahi; plain SHA-256 kaafi hai.)
- `hmac.compare_digest`: constant-time compare. Normal `==` pehle galat character pe ruk jaata hai,
  aur response time se attacker character-by-character key guess kar sakta hai (timing attack).
- Audit log mein key nahi, sirf `actor` = hash ke pehle 8 characters jaata hai.

Naya key:  python -m faceai.security.auth   (key + uska hash print karta hai)
"""

import hashlib
import hmac
import secrets


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def actor_id(key_hash: str) -> str:
    return f"key:{key_hash[:8]}"


def verify(key: str | None, allowed_hashes: list[str]) -> str | None:
    """Valid key => actor id; warna None."""
    if not key:
        return None
    h = hash_key(key)
    for allowed in allowed_hashes:
        if hmac.compare_digest(h, allowed.strip().lower()):
            return actor_id(allowed)
    return None


if __name__ == "__main__":
    k = secrets.token_urlsafe(32)
    print(f"API key (client ko do, kahin save mat karo): {k}")
    print(f"FACEAI_API_KEY_HASHES={hash_key(k)}")
