import pytest
from fastapi.testclient import TestClient

from faceai.api.app import create_app
from faceai.config import Settings
from tests.fakes import FakeEngine


@pytest.fixture
def settings(tmp_path) -> Settings:
    # tmp_path: har test ka apna temporary folder -> asli data/ kabhi touch nahi hota
    return Settings(
        env="test",
        data_dir=tmp_path,
        product_db_url=f"sqlite:///{(tmp_path / 'app.db').as_posix()}",
        _env_file=None,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, engine=FakeEngine())) as c:  # `with` => lifespan chalega
        yield c


@pytest.fixture
def app_client_rl(settings):
    """Rate limiting ON (default) wala app (fresh limiter per test)."""
    with TestClient(
        create_app(settings.model_copy(update={"rate_limit": True}), engine=FakeEngine())
    ) as c:
        yield c
