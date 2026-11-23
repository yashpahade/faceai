"""
Passwords + JWT (Phase B).

Password hashing: scrypt (Python stdlib). "Memory-hard" hai: GPU se lakhon guesses/second karna
mehenga padta hai. Kabhi plain SHA-256 mat use karo passwords ke liye (bahut fast = brute-force
aasaan). Format: scrypt$n$r$p$salt_b64$hash_b64 -> parameters baad mein badal sakte ho.

JWT (JSON Web Token): login ke baad server ek signed token deta hai {sub: user_id, role, exp}.
Har request pe `Authorization: Bearer <token>`. Server signature verify karta hai, DB lookup bina
pata chal jaata hai ki kaun hai. `ver` (token_version) badha do -> saare purane tokens invalid
(password change, "logout from all devices").
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

import jwt

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    b64 = base64.b64encode
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt).decode()}${b64(h).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_b64, hash_b64 = stored.split("$")
        expected = base64.b64decode(hash_b64)
        got = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


def create_token(
    user_id: str, role: str, token_version: int, secret: str, ttl_minutes: int, method: str
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "ver": token_version,
        "amr": [method],  # authentication method: pwd | face (audit + policy ke liye)
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> dict | None:
    try:
        # algorithms explicitly fix: "alg: none" attack se bachav
        return jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["exp"]})
    except jwt.PyJWTError:
        return None
