import pytest
from pydantic import ValidationError

from faceai.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.port == 8000
    assert s.env == "dev"
    assert s.max_upload_bytes == 10 * 1024 * 1024


def test_env_vars_override(monkeypatch):
    monkeypatch.setenv("FACEAI_PORT", "9001")
    monkeypatch.setenv("FACEAI_LOG_LEVEL", "debug")
    s = Settings(_env_file=None)
    assert s.port == 9001
    assert s.log_level == "DEBUG"


@pytest.mark.parametrize(
    "var,value",
    [
        ("FACEAI_PORT", "abc"),  # not an int
        ("FACEAI_PORT", "70000"),  # out of range
        ("FACEAI_ENV", "staging"),  # not an allowed env
        ("FACEAI_DET_THRESHOLD", "1.5"),  # threshold > 1
    ],
)
def test_invalid_config_fails_fast(monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
