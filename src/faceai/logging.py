"""
Structured logging.

Legacy code `print()` use karta tha - production mein print ka koi level, timestamp,
ya searchability nahi hoti. Yahan:
- dev  -> readable text logs
- prod -> ek line = ek JSON object, jise Grafana Loki / ELK / CloudWatch seedha parse kar sake
- har log line mein `request_id` hota hai, taaki ek request ke saare logs ek saath dhoondh sako
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

# Har request ka ID yahan store hota hai (async-safe, har request ka apna copy)
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "color_message",  # uvicorn ka ANSI-colored duplicate, JSON mein bekaar
}


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        # logger.info("x", extra={"face_count": 2}) -> extra fields bhi JSON mein
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn ke apne handlers hata do, taaki sab logs ek hi format mein aayein
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    # access log hum khud middleware mein likhte hain (latency ke saath)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
