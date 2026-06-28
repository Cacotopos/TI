#!/usr/bin/env python3
"""Build a static expansion site from a config.json file."""

import argparse
import json
import shutil
from pathlib import Path

import jinja2

from .config import load_config


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _copy_assets(output_dir: Path) -> None:
    assets_dir = output_dir / "assets"
    for sub in ("css", "js", "images"):
        src = TEMPLATE_DIR / sub
        if src.exists():
            shutil.copytree(src, assets_dir / sub, dirs_exist_ok=True)


def _copy_source_images(config: dict, config_dir: Path, output_dir: Path) -> None:
    images_src = config_dir / config.get("source", {}).get("images", "")
    if not images_src.exists():
        return
    images_dest = output_dir / "assets" / "images"
    images_dest.mkdir(parents=True, exist_ok=True)
    for p in images_src.rglob("*"):
        if p.is_file():
            rel = p.relative_to(images_src)
            dest = images_dest / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)


def build_site(config_path: Path, output_dir: Path) -> None:
    """Generate a standalone static site at output_dir."""
    config = load_config(config_path)
    config_dir = config_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    _copy_assets(output_dir)
    _copy_source_images(config, config_dir, output_dir)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("index.html")
    html = template.render(config=config)
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
