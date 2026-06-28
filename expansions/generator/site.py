#!/usr/bin/env python3
"""Build a static expansion site from a config.json file."""

import argparse
import json
import shutil
from pathlib import Path

from .config import load_config


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def build_site(config_path: Path, output_dir: Path) -> None:
    """Generate a standalone static site at output_dir."""
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy shared assets
    assets_dir = output_dir / "assets"
    if (TEMPLATE_DIR / "css").exists():
        shutil.copytree(TEMPLATE_DIR / "css", assets_dir / "css", dirs_exist_ok=True)
    if (TEMPLATE_DIR / "js").exists():
        shutil.copytree(TEMPLATE_DIR / "js", assets_dir / "js", dirs_exist_ok=True)

    # Build index.html
    css_links = ["assets/css/styles.css"]
    js_links = ["assets/js/search.js", "assets/js/filters.js", "assets/js/ui.js"]
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{config['name']} v{config['version']}</title>
{''.join(f'<link rel="stylesheet" href="{c}"/>' for c in css_links)}
</head>
<body>
<header>
  <h1>{config['name']} <span>v{config['version']}</span></h1>
  <p>{config.get('description', '')}</p>
</header>
<main>
  <p>Generated site for {config['name']}.</p>
</main>
{''.join(f'<script src="{j}"></script>' for j in js_links)}
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")

    # Write data.json for JS search
    (output_dir / "data.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"Site generated: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Build a static expansion site")
    parser.add_argument("config", type=Path, help="Path to config.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    args = parser.parse_args()
    build_site(args.config, args.output)


if __name__ == "__main__":
    main()
