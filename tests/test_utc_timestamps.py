"""SQLite se padhe timestamps UTC-aware hone chahiye (warna browser unhe local time maanta hai).

Bug tha: API `2026-11-24T16:20:52` (bina timezone) bhejti -> IST browser 5.5h galat dikhata.
"""

from datetime import UTC, datetime, timedelta, timezone

from faceai.attendance.models import User, create_all, make_engine, make_sessionmaker


def _roundtrip(tmp_path, written: datetime) -> datetime:
    eng = make_engine(f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    create_all(eng)
    sm = make_sessionmaker(eng)
    with sm() as s:
        u = User(email="t@example.test", full_name="T", password_hash="x", created_at=written)
        s.add(u)
        s.commit()
        uid = u.id
    with sm() as s:  # fresh session -> value DB se aata hai, cache se nahi
        got = s.get(User, uid).created_at
    eng.dispose()
    return got


def test_read_back_is_utc_aware(tmp_path):
    written = datetime(2026, 11, 24, 16, 20, 52, tzinfo=UTC)
    got = _roundtrip(tmp_path, written)
    assert got.tzinfo is not None, "naive datetime -> browser would treat it as local time"
    assert got == written
    assert got.isoformat().endswith("+00:00")


def test_non_utc_input_is_normalized_to_utc(tmp_path):
    ist = timezone(timedelta(hours=5, minutes=30))
    written = datetime(2026, 11, 24, 21, 50, 52, tzinfo=ist)  # = 16:20:52 UTC
    got = _roundtrip(tmp_path, written)
    assert got == written  # same instant
    assert got.utcoffset() == timedelta(0)
    assert (got.hour, got.minute) == (16, 20)
