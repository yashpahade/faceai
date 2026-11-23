"""
Input rules (server = asli guard; frontend `lib/validate.js` same rules sirf UX ke liye dikhata hai,
API ko seedha call karke bypass nahi ho sakta).

Name:     letters (koi bhi language, e.g. "अमित"), space, . ' -   | digits/symbols nahi
Mobile:   Indian mobile: 10 digits, 6-9 se shuru; +91 / 91 / 0 prefix, spaces, dashes allowed
          -> hamesha "+91XXXXXXXXXX" mein store (ek format = search/duplicate check aasaan)
Password: 8-128 chars, kam se kam 1 letter + 1 digit
Roll no:  letters, digits, - /
"""

import re
import unicodedata

_PHONE = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")
_ROLL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/]*$")


def _is_letter(ch: str) -> bool:
    # L* = letters, M* = combining marks (Hindi/Marathi matras: ि ु ा ं). Dono naam ka hissa hain.
    return unicodedata.category(ch)[0] in ("L", "M")


def clean_name(v: str) -> str:
    v = " ".join(v.split())  # extra spaces hatao
    if any(ch.isdigit() for ch in v):
        raise ValueError("name cannot contain numbers")
    if any(not (_is_letter(ch) or ch in " .'-") for ch in v):
        raise ValueError("name can contain only letters, spaces and . ' -")
    if sum(_is_letter(ch) for ch in v) < 2 or not _is_letter(v[0]):
        raise ValueError("name must have at least 2 letters and start with a letter")
    return v


def clean_phone(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    digits = re.sub(r"[\s\-()]", "", v)
    if re.search(r"[^\d+]", digits):
        raise ValueError("mobile number can contain only digits")
    m = _PHONE.match(digits)
    if not m:
        raise ValueError("enter a valid 10-digit mobile number (starts with 6-9)")
    return f"+91{m.group(1)}"


def check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("password must be at least 8 characters")
    if not re.search(r"[^\W\d_]", v):
        raise ValueError("password must contain at least one letter")
    if not re.search(r"\d", v):
        raise ValueError("password must contain at least one number")
    return v


def clean_roll(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip().upper()
    if not _ROLL.match(v):
        raise ValueError("roll no can contain only letters, numbers, - and /")
    return v
