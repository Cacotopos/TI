#!/usr/bin/env python3
"""Convert an expansion data.json into a print-order CSV.

One line per asset that has both a front and a back image.
Quantity defaults to 1 and is overridden by an `xN` token in either filename
(e.g. "Token Back x2.png" -> quantity 2).

File paths are written relative to the v3.1 source root, not the generated
site or the user's filesystem.
"""
import argparse
import csv
import json
import re
from pathlib import Path


def _find_quantity(path: str) -> int | None:
    """Return the first xN multiplier found in a filename, or None."""
    base = Path(path).stem
    # Match xN where x is not preceded/followed by another alphanum
    m = re.search(r"(?:^|[^a-zA-Z0-9])x(\d+)(?:[^a-zA-Z0-9]|$)", base, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _quantity(front: str, back: str) -> int:
    """Determine quantity from front/back filenames; default 1."""
    values = [v for v in (_find_quantity(front), _find_quantity(back)) if v is not None]
    return max(values) if values else 1


def _card_type(component: str) -> str:
    """Normalize component to a print card type."""
    if component == "us-mini":
        return "us mini"
    return component or ""


def _guess_config_path(data_path: Path) -> Path | None:
    """Infer the editor config path from the site data.json path."""
    # expansions/sites/<expansion>/data.json -> expansions/editor/data/<expansion>/config.json
    parts = data_path.parts
    try:
        sites_idx = parts.index("sites")
        if sites_idx + 1 < len(parts):
            expansion_id = parts[sites_idx + 1]
            root = data_path
            for _ in parts[sites_idx:]:
                root = root.parent
            return root / "expansions" / "editor" / "data" / expansion_id / "config.json"
    except ValueError:
        pass
    return None


def _load_config(config_path: Path | None) -> dict:
    if config_path and config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _original_path(data_path: str, asset: dict | None, fallback: str) -> str:
    """Return a path relative to the v3.1 source root.

    Prefer the original asset path from the editor config (preserves the
    original filename/extension). Fall back to stripping the generated
    `assets/images/` prefix from the data.json path.
    """
    if asset and asset.get("path"):
        return asset["path"]
    stripped = re.sub(r"^assets/images/", "", data_path)
    return stripped or fallback


def _ensure_relative(path: str) -> str:
    """Strip any leading /assets/images/ or leading slash to keep paths relative."""
    if not path:
        return path
    # Strip generated site prefix if present
    path = re.sub(r"^assets/images/", "", path)
    # Convert any absolute path to relative by taking the last components
    # that look like a source path. This is a defensive fallback.
    if path.startswith("/") and "/" in path:
        # Try to find a known root like 'v3.1/' or 'Printable Cards/v3.1/' or just keep as is
        for marker in ("/v3.1/", "/Printable Cards/v3.1/", "/Printable Cards/"):
            idx = path.find(marker)
            if idx != -1:
                return path[idx + len(marker):]
        return path.lstrip("/")
    return path


def build_print_order(data_path: Path, output_path: Path, config_path: Path | None) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    config = _load_config(config_path)

    # Build id -> asset lookup. Editor config assets are keyed by relative source path.
    assets_by_id: dict[str, dict] = {}
    for key, asset in config.get("assets", {}).items():
        asset_id = asset.get("id", "")
        if asset_id:
            assets_by_id[asset_id] = asset

    # Build path -> back asset key lookup for back images.
    back_keys: dict[str, str] = {}
    for key, asset in config.get("assets", {}).items():
        if asset.get("back"):
            back_keys[asset.get("back", "")] = key

    rows = []
    for card in data.get("cards", []):
        data_front = card.get("front", "")
        data_back = card.get("back", "")
        if not data_front or not data_back:
            continue

        asset = assets_by_id.get(card.get("id", ""), {})
        front = _original_path(data_front, asset, data_front)
        back = _original_path(data_back, None, data_back)

        # If the config asset has a back, use its original relative path.
        if asset and asset.get("back"):
            back = asset["back"]

        # Defensive: make sure neither path is an absolute / generated path.
        front = _ensure_relative(front)
        back = _ensure_relative(back)

        rows.append({
            "id": card.get("id", ""),
            "title": card.get("name", ""),
            "front_image": front,
            "back_image": back,
            "type": _card_type(card.get("component", "")),
            "quantity": _quantity(front, back),
            "group": card.get("group", ""),
            "faction": card.get("faction", ""),
            "section": card.get("section", ""),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "title", "front_image", "back_image",
            "type", "quantity", "group", "faction", "section",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a print-order CSV from expansion data.json")
    parser.add_argument("data_json", type=Path, help="Path to data.json")
    parser.add_argument("-c", "--config", type=Path, default=None,
                        help="Editor config.json (default: auto-locate from data.json)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output CSV path (default: <data_json_dir>/print_order.csv)")
    args = parser.parse_args()

    config_path = args.config or _guess_config_path(args.data_json)
    output = args.output or (args.data_json.parent / "print_order.csv")
    build_print_order(args.data_json, output, config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
