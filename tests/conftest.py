import pytest
from fastapi.testclient import TestClient

from faceai.api.app import create_app
from faceai.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    # tmp_path: har test ka apna temporary folder -> asli data/ kabhi touch nahi hota
    return Settings(env="test", data_dir=tmp_path, _env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:  # `with` => lifespan (startup) chalega
        yield c
