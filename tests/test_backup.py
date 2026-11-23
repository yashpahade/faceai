import sqlite3
from contextlib import closing

from faceai.ops.backup import prune, sqlite_backup, verify


def test_backup_is_consistent_copy_and_prunes(tmp_path):
    src = tmp_path / "live.db"
    with closing(sqlite3.connect(src)) as c, c:
        c.execute("CREATE TABLE t (x)")
        c.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(100)])
    out = tmp_path / "backups"
    for i in range(4):
        sqlite_backup(src, out / f"bio-2026010{i}.db")
    assert verify(out / "bio-20260103.db")
    with closing(sqlite3.connect(out / "bio-20260103.db")) as c:
        assert c.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 100
    removed = prune(out, "bio-*.db", keep=2)
    assert [p.name for p in removed] == ["bio-20260100.db", "bio-20260101.db"]
    assert sorted(p.name for p in out.glob("*.db")) == ["bio-20260102.db", "bio-20260103.db"]
