import json
from pathlib import Path


def _migrate_config(data: dict) -> dict:
    """Migrate legacy isCard boolean to component string."""
    for asset in data.get("assets", {}).values():
        if "component" not in asset:
            asset["component"] = "us-mini" if asset.get("isCard", True) else "other"
        if "isCard" in asset:
            del asset["isCard"]
    return data


def load_config(path: Path) -> dict:
    """Load and return an expansion config.json."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # TODO: validate against schema/expansion.json
    return _migrate_config(data)
