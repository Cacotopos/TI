import json
from pathlib import Path


def load_config(path: Path) -> dict:
    """Load and return an expansion config.json."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # TODO: validate against schema/expansion.json
    return data
