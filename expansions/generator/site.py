#!/usr/bin/env python3
"""Build a static expansion site from a config.json file."""

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import jinja2
import numpy as np
from PIL import Image

from expansions.generator.config import load_config


ROOT = Path(__file__).parent.parent.parent
TEMPLATE_DIR = ROOT / "expansions" / "templates"
MIN_BANNER_WIDTH = 1152 + 400


def _markdown_filter(text: str) -> str:
    """Render a small subset of Markdown to HTML."""
    if not text:
        return ""
    html = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    # Bold
    html = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html)
    # Italic
    html = re.sub(r"\*(.*?)\*", r"<em>\1</em>", html)
    # Headers
    for i in range(6, 0, -1):
        html = re.sub(rf"^#{i} (.*$)", rf"<h{i}>\1</h{i}>", html, flags=re.MULTILINE)
    # Inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', html)
    # Lists
    html = re.sub(r"^\s*-\s+(.*$)", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", html, flags=re.DOTALL)
    # Paragraphs
    paragraphs = html.split("\n\n")
    html = "\n\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" if p.strip() else p for p in paragraphs)
    return html



def _copy_assets(output_dir: Path) -> None:
    assets_dir = output_dir / "assets"
    for sub in ("css", "js", "images"):
        src = TEMPLATE_DIR / sub
        if src.exists():
            shutil.copytree(src, assets_dir / sub, dirs_exist_ok=True)


_MASK_CROP_BOX: tuple[float, float, float, float] | None = None


def _load_mask_crop_box(mask_path: Path) -> tuple[float, float, float, float]:
    """Load the card mask and return the relative bounding box (left, top, right, bottom)."""
    mask_img = Image.open(mask_path).convert("RGBA")
    r, g, b, a = mask_img.split()
    alpha = np.array(a)
    if alpha.max() > 0:
        card_pixels = alpha < 128
    else:
        gray = np.array(mask_img.convert("L"))
        card_pixels = gray < 128
    rows = card_pixels.any(axis=1)
    cols = card_pixels.any(axis=0)
    if not rows.any() or not cols.any():
        return (0.0, 0.0, 1.0, 1.0)
    top = np.argmax(rows)
    bottom = len(rows) - np.argmax(rows[::-1])
    left = np.argmax(cols)
    right = len(cols) - np.argmax(cols[::-1])
    h, w = card_pixels.shape
    return (left / w, top / h, right / w, bottom / h)


def _crop_card_image(path: Path, mask_path: Path) -> bytes:
    """Crop a source image to the card mask bounding box and return JPEG bytes.

    Portrait images are rotated to landscape before cropping, then rotated back
    so they are displayed in their natural orientation while keeping the same
    crop area.
    """
    global _MASK_CROP_BOX
    if _MASK_CROP_BOX is None:
        _MASK_CROP_BOX = _load_mask_crop_box(mask_path)

    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        portrait = h > w
        if portrait:
            img = img.rotate(-90, expand=True)
            w, h = img.size
        left, top, right, bottom = _MASK_CROP_BOX
        crop = (int(left * w), int(top * h), int(right * w), int(bottom * h))
        img = img.crop(crop)
        if portrait:
            img = img.rotate(90, expand=True)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=92)
        return buffer.getvalue()


def _collect_assets(config: dict) -> list[dict]:
    """Return visible, card assets as a list of image descriptors for the site."""
    assets = config.get("assets", {})
    images_path = config.get("source", {}).get("images", "")
    if not images_path:
        return []
    images_src = ROOT / images_path
    if not images_src.exists():
        return []

    images = []
    for path, asset in sorted(assets.items()):
        if asset.get("hidden"):
            continue
        if not asset.get("isCard", True):
            continue
        rel = Path(path)
        src_path = images_src / rel
        orientation = asset.get("orientation", "")
        if orientation not in ("landscape", "portrait"):
            orientation = "landscape"
            if src_path.exists():
                try:
                    with Image.open(src_path) as img:
                        w, h = img.size
                        if h > w:
                            orientation = "portrait"
                except Exception:
                    pass
        images.append({
            "id": asset.get("id", rel.stem),
            "path": str(Path("assets/images") / rel).replace("\\", "/"),
            "folder": str(rel.parent) if rel.parent != Path(".") else "",
            "name": asset.get("title") or rel.stem,
            "subtitle": asset.get("subtitle", ""),
            "backTitle": assets.get(asset.get("back", ""), {}).get("title", ""),
            "backSubtitle": assets.get(asset.get("back", ""), {}).get("subtitle", ""),
            "section": asset.get("section", "cards"),
            "group": asset.get("group") or (str(rel.parent) if rel.parent != Path(".") else ""),
            "back": asset.get("back", ""),
            "description": asset.get("description", ""),
            "faq": asset.get("faq", []),
            "type": asset.get("type", ""),
            "faction": asset.get("faction", ""),
            "configured": asset.get("configured", False),
            "stats": asset.get("stats", {}),
            "abilities": asset.get("abilities", {}),
            "prereq": asset.get("prereq", {}),
            "color": asset.get("color", ""),
            "synergy": asset.get("synergy", {}),
            "source": asset.get("source", {}),
            "orientation": orientation,
            "flavour": asset.get("flavour", ""),
        })
    return images


def _copy_source_images(config: dict, output_dir: Path) -> None:
    images_path = config.get("source", {}).get("images", "")
    if not images_path:
        return
    images_src = ROOT / images_path
    if not images_src.exists():
        print(f"Warning: source image path not found: {images_src}")
        return

    assets = config.get("assets", {})
    section_types = {s.get("id"): s.get("type", "cards") for s in config.get("sections", [])}
    mask_path = ROOT / "Icons" / "Card Mask.png"
    crop = mask_path.exists()

    # Map card back images to their front asset orientation.
    back_to_front = {}
    front_portrait = set()
    for path, asset in assets.items():
        if asset.get("hidden") or not asset.get("isCard", True):
            continue
        section_id = asset.get("section", "cards")
        if section_types.get(section_id, "cards") != "cards":
            continue
        back = asset.get("back", "")
        if back:
            back_to_front[back] = path
        src_path = images_src / path
        if src_path.exists():
            try:
                with Image.open(src_path) as img:
                    w, h = img.size
                    if h > w:
                        front_portrait.add(path)
            except Exception:
                pass

    images_dest = output_dir / "assets" / "images"
    images_dest.mkdir(parents=True, exist_ok=True)
    for p in images_src.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
            rel = p.relative_to(images_src)
            dest = images_dest / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            rel_path = str(rel).replace("\\", "/")
            asset = assets.get(rel_path, {})
            section_id = asset.get("section", "cards")
            section_type = section_types.get(section_id, "cards")
            is_card = asset.get("isCard", True) and section_type == "cards"
            is_back = rel_path in back_to_front
            if crop and (is_card or is_back):
                data = _crop_card_image(p, mask_path)
                dest.write_bytes(data)
            elif is_back and back_to_front[rel_path] in front_portrait:
                with Image.open(p) as img:
                    img = img.convert("RGB")
                    w, h = img.size
                    if h <= w:
                        img = img.rotate(90, expand=True)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=92)
                    dest.write_bytes(buffer.getvalue())
            else:
                shutil.copy2(p, dest)


def _prepare_banner(config: dict, output_dir: Path) -> str | None:
    """Validate and return the output-relative path for the banner image.

    The banner is copied alongside other source images; this just confirms it
    meets the minimum width requirement and resolves its output URL.
    """
    banner_config = config.get("banner") or {}
    banner_path = banner_config.get("path", "")
    if not banner_path:
        return None
    images_path = config.get("source", {}).get("images", "")
    if images_path:
        banner_file = ROOT / images_path / banner_path
        if not banner_file.exists():
            banner_file = ROOT / banner_path
    else:
        banner_file = ROOT / banner_path
    if not banner_file.exists():
        print(f"Warning: banner not found: {banner_file}")
        return None

    try:
        with Image.open(banner_file) as img:
            width = img.width
    except Exception as e:
        print(f"Warning: could not read banner: {e}")
        return None

    if width < MIN_BANNER_WIDTH:
        print(f"Warning: banner is {width}px wide, minimum is {MIN_BANNER_WIDTH}px")
        return None

    images_path = config.get("source", {}).get("images", "")
    images_src = ROOT / images_path if images_path else None
    if images_src and images_src.exists():
        try:
            rel = banner_file.relative_to(images_src)
            return str(Path("assets/images") / rel).replace("\\", "/")
        except ValueError:
            pass
    # Banner is outside the source image folder; copy it to the root.
    ext = Path(banner_path).suffix or ".jpg"
    dest = output_dir / "assets" / "images" / f"banner{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(banner_file, dest)
    return str(Path("assets/images") / dest.name).replace("\\", "/")


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def build_site(config_path: Path, output_dir: Path) -> None:
    """Generate a standalone static site at output_dir."""
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    _copy_assets(output_dir)
    _copy_source_images(config, output_dir)

    images = _collect_assets(config)
    git_commit = _git_commit()
    site = {
        **config,
        "images": images,
        "sections": config.get("sections", []),
        "banner_path": _prepare_banner(config, output_dir),
        "git_commit": git_commit,
    }

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))
    env.filters["markdown"] = _markdown_filter

    # Index page
    index = env.get_template("index.html")
    (output_dir / "index.html").write_text(
        index.render(config=config, site=site), encoding="utf-8"
    )

    # Section pages
    for section in site["sections"]:
        template_name = f"section_{section['type']}.html"
        if not (TEMPLATE_DIR / template_name).exists():
            template_name = "section.html"
        template = env.get_template(template_name)
        page = output_dir / f"{section['id']}.html"
        page.write_text(template.render(config=config, site=site, section=section), encoding="utf-8")

    # Search page
    search = env.get_template("search.html")
    (output_dir / "search.html").write_text(
        search.render(config=config, site=site), encoding="utf-8"
    )

    # Write data.json for JS search
    (output_dir / "data.json").write_text(json.dumps(site, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build a static expansion site")
    parser.add_argument("config", type=Path, help="Path to config.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    args = parser.parse_args()
    build_site(args.config, args.output)


if __name__ == "__main__":
    main()
