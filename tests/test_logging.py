import json
import logging

from faceai.logging import JsonFormatter, request_id_ctx


def _record(msg: str, **extra) -> logging.LogRecord:
    rec = logging.LogRecord("faceai.test", logging.INFO, __file__, 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_json_formatter_emits_valid_json_with_extras():
    out = JsonFormatter().format(_record("hello", request_id="r1", face_count=2))
    data = json.loads(out)
    assert data["msg"] == "hello"
    assert data["level"] == "INFO"
    assert data["request_id"] == "r1"
    assert data["face_count"] == 2


def test_request_id_appears_in_logs(client, caplog):
    with caplog.at_level(logging.INFO, logger="faceai.api"):
        client.get("/health/live", headers={"X-Request-ID": "trace-me"})
    assert any(getattr(r, "request_id", None) == "trace-me" for r in caplog.records)
    assert request_id_ctx.get() == "-"  # request ke baad context reset ho gaya
