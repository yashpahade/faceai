"""params.yaml loader.

DVC isi file ko track karta hai: koi param badla => dependent stages rerun.
"""

from pathlib import Path
from typing import Any

import yaml


def load_params(path: Path = Path("params.yaml")) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
