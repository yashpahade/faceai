"""
Model card reader (serving side).

`python -m faceai.registry pull` ise models/<pack>/ mein likhta hai.

Serving ko pata hona chahiye ki wo KAUN sa registered version chala raha hai, warna incident ke
time "production mein kaunsa model tha?" ka jawab nahi milta. Card na ho to bhi app chalti hai
(local dev), bas /version mein `model_version: null` aata hai.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

CARD_FILE = "model_card.json"
logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_card(pack_dir: Path, verify: bool = True) -> dict[str, Any] | None:
    """Card padho; `verify` => disk ki files card ke sha256 se match honi chahiye."""
    path = pack_dir / CARD_FILE
    if not path.exists():
        return None
    card = json.loads(path.read_text(encoding="utf-8"))
    if verify:
        for name, expected in card.get("files", {}).items():
            f = pack_dir / name
            if not f.exists() or _sha256(f) != expected:
                # Card kuch aur kehta hai, disk pe kuch aur hai => version info pe bharosa nahi
                raise RuntimeError(f"model file {name} does not match {CARD_FILE}")
    return card
