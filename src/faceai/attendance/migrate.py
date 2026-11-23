"""
Product DB schema migrations (Alembic) - Phase E.

    python -m faceai.attendance.migrate              # upgrade to latest
    python -m faceai.attendance.migrate --revision "add guardian phone"   # new migration (dev)

Dev/test mein `create_all` chalta hai (fresh DB). Production DB mein data hai: column add karne ke
liye table drop nahi kar sakte. Migration = version-controlled schema change, har environment
(staging, prod) pe same order mein chalta hai. `alembic_version` table yaad rakhta hai kya lag gaya.
"""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from faceai.config import get_settings

MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", help="autogenerate a new migration with this message")
    args = ap.parse_args()
    cfg = alembic_config(get_settings().product_db_url)
    if args.revision:
        command.revision(cfg, message=args.revision, autogenerate=True)
    else:
        command.upgrade(cfg, "head")
        print("product DB is at the latest schema")


if __name__ == "__main__":
    main()
