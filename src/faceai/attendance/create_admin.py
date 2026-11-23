"""
Pehla admin account banao (signup sirf students ke liye hai; admin API se nahi ban sakta).

    python -m faceai.attendance.create_admin --email admin@school.in --name "Admin"

Password prompt pe maanga jaata hai (shell history / process list mein na dikhe).
"""

import argparse
import getpass

from sqlalchemy import select

from faceai.attendance.models import User, create_all, make_engine, make_sessionmaker
from faceai.attendance.security import hash_password
from faceai.config import get_settings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", default="Admin")
    args = ap.parse_args()
    pw = getpass.getpass("Admin password (min 12 chars): ")
    if len(pw) < 12 or pw != getpass.getpass("Repeat: "):
        raise SystemExit("passwords must match and be at least 12 characters")
    s = get_settings()
    engine = make_engine(s.product_db_url)
    create_all(engine)
    sessions = make_sessionmaker(engine)
    with sessions.begin() as db:
        email = args.email.strip().lower()
        u = db.scalar(select(User).where(User.email == email))
        if u is None:
            db.add(
                User(
                    email=email, full_name=args.name, password_hash=hash_password(pw), role="admin"
                )
            )
            print(f"admin created: {email}")
        else:
            u.role, u.password_hash, u.status = "admin", hash_password(pw), "active"
            u.token_version += 1
            print(f"existing user promoted to admin (password reset): {email}")


if __name__ == "__main__":
    main()
