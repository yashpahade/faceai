"""create_all race condition.

Do backend ek saath start hon to 'table already exists' se crash nahi hona chahiye.
"""

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import OperationalError

from faceai.attendance import models
from faceai.attendance.models import Base, create_all, make_engine


@pytest.fixture
def engine(tmp_path):
    eng = make_engine(f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    yield eng
    eng.dispose()


def test_real_race_is_survived(engine, monkeypatch):
    """Asli race reproduce: 'check' ke BAAD aur CREATE se PEHLE table kisi aur ne bana di."""
    monkeypatch.setattr(models.time, "sleep", lambda s: None)
    table = Base.metadata.tables["batch_teachers"]
    state = {"raced": False}

    def other_process_creates_it_first(target, connection, **kw):
        if not state["raced"]:
            state["raced"] = True
            target.create(connection, checkfirst=False)  # "doosra process" jeet gaya

    event.listen(table, "before_create", other_process_creates_it_first)
    try:
        create_all(engine)
    finally:
        event.remove(table, "before_create", other_process_creates_it_first)

    assert state["raced"], "race was not triggered; test is not testing anything"
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())


def _op_error(msg: str) -> OperationalError:
    return OperationalError("CREATE TABLE ...", {}, Exception(msg))


def test_non_race_errors_are_not_retried(engine, monkeypatch):
    calls = []

    def boom(eng):
        calls.append(1)
        raise _op_error("disk I/O error")

    monkeypatch.setattr(Base.metadata, "create_all", boom)
    with pytest.raises(OperationalError, match="disk I/O"):
        create_all(engine)
    assert len(calls) == 1  # asli problem chhupi nahi, turant fail


def test_gives_up_after_attempts(engine, monkeypatch):
    monkeypatch.setattr(models.time, "sleep", lambda s: None)
    calls = []

    def always_races(eng):
        calls.append(1)
        raise _op_error("table batch_teachers already exists")

    monkeypatch.setattr(Base.metadata, "create_all", always_races)
    with pytest.raises(OperationalError):
        create_all(engine, attempts=3)
    assert len(calls) == 3


def test_create_all_is_idempotent(engine):
    create_all(engine)
    create_all(engine)  # doosri baar: sab tables maujood -> kuch nahi karna, koi error nahi
    assert "batch_teachers" in inspect(engine).get_table_names()
