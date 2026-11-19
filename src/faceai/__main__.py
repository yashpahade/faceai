"""`python -m faceai` se server start karo."""

import uvicorn

from faceai.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "faceai.api.app:create_app",
        factory=True,
        host=s.host,
        port=s.port,
        reload=s.env == "dev",
        log_config=None,  # logging hum khud setup karte hain
    )


if __name__ == "__main__":
    main()
