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
    """Render a small subset of Markdown to HTML, matching the client renderer."""
    if not text:
        return ""
    html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def inline(s: str) -> str:
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.*?)\*", r"<em>\1</em>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" class="text-accent hover:underline">\1</a>', s)
        return s

    lines = html.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        header_match = re.match(r"^(#{1,6})\s*(.*)$", line)
        if header_match:
            level = len(header_match.group(1))
            out.append(f"<h{level}>{inline(header_match.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r"^-\s+(.*)$", line):
            items: list[str] = []
            while i < len(lines) and re.match(r"^-\s+(.*)$", lines[i].strip()):
                item_text = re.sub(r"^-\s+", "", lines[i].strip())
                items.append(f"<li>{inline(item_text)}</li>")
                i += 1
            out.append(f"<ul>{''.join(items)}</ul>")
            continue

        para_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            stripped = lines[i].strip()
            if re.match(r"^(#{1,6})\s*(.*)$", stripped) or re.match(r"^-\s+(.*)$", stripped):
                break
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            para = inline("\n".join(para_lines))
            para = para.replace("\n", "<br>")
            out.append(f"<p>{para}</p>")

    return "\n".join(out)



def _copy_assets(output_dir: Path) -> None:
    assets_dir = output_dir / "assets"
    for sub in ("css", "js", "images"):
        src = TEMPLATE_DIR / sub
        if src.exists():
            shutil.copytree(src, assets_dir / sub, dirs_exist_ok=True)


_CROP_COMPONENTS = {"us-mini", "tarot", "poker"}
_COMPONENT_CROP_BOXES: dict[str, tuple[float, float, float, float]] = {}


def _load_mask_crop_box(mask_path: Path) -> tuple[float, float, float, float]:
    """Load a card mask and return the relative bounding box (left, top, right, bottom)."""
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


def _default_crop_box(component: str) -> tuple[float, float, float, float]:
    """Default relative crop box for components that do not have a mask file."""
    if component == "tarot":
        return (0.0251, 0.0407, 0.9749, 0.9593)
    if component == "poker":
        return (0.0356, 0.0486, 0.9644, 0.9514)
    return (0.0, 0.0, 1.0, 1.0)


def _component_crop_box(component: str) -> tuple[float, float, float, float]:
    """Return the cached crop box for a physical component."""
    if component in _COMPONENT_CROP_BOXES:
        return _COMPONENT_CROP_BOXES[component]
    if component == "us-mini":
        mask_path = ROOT / "Icons" / "Card Mask.png"
        if mask_path.exists():
            box = _load_mask_crop_box(mask_path)
        else:
            box = _default_crop_box(component)
    else:
        mask_path = ROOT / "Icons" / f"{component.replace('-', ' ').title()} Mask.png"
        if mask_path.exists():
            box = _load_mask_crop_box(mask_path)
        else:
            box = _default_crop_box(component)
    _COMPONENT_CROP_BOXES[component] = box
    return box


def _crop_image(path: Path, crop_box: tuple[float, float, float, float], rotate: int = 0) -> bytes:
    """Crop a source image to a relative bounding box and return JPEG bytes.

    Portrait images are rotated to landscape before cropping, then rotated back
    so they are displayed in their natural orientation while keeping the same
    crop area. User rotation is applied first.
    """
    with Image.open(path) as img:
        img = img.convert("RGB")
        if rotate:
            img = img.rotate(-rotate, expand=True)
        w, h = img.size
        portrait = h > w
        if portrait:
            img = img.rotate(-90, expand=True)
            w, h = img.size
        left, top, right, bottom = crop_box
        crop = (int(left * w), int(top * h), int(right * w), int(bottom * h))
        img = img.crop(crop)
        if portrait:
            img = img.rotate(90, expand=True)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=92)
        return buffer.getvalue()


def _detect_orientation(src_path: Path, asset: dict) -> str:
    """Return 'square', 'portrait' or 'landscape' for an image file, honouring rotation."""
    orientation = asset.get("orientation", "")
    if orientation in ("landscape", "portrait", "square"):
        return orientation
    if src_path.exists():
        try:
            with Image.open(src_path) as img:
                w, h = img.size
                rotate = int(asset.get("rotate", 0) or 0)
                if rotate in (90, 270):
                    w, h = h, w
                if h == w:
                    return "square"
                return "portrait" if h > w else "landscape"
        except Exception:
            pass
    return "landscape"


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
        if asset.get("component", "us-mini") == "other":
            continue
        rel = Path(path)
        src_path = images_src / rel
        orientation = _detect_orientation(src_path, asset)
        component = asset.get("component", "us-mini")
        images.append({
            "id": asset.get("id", rel.stem),
            "path": str(Path("assets/images") / rel).replace("\\", "/"),
            "folder": str(rel.parent) if rel.parent != Path(".") else "",
            "name": asset.get("title") or rel.stem,
            "subtitle": asset.get("subtitle", ""),
            "backTitle": assets.get(asset.get("back", ""), {}).get("title", ""),
            "backSubtitle": assets.get(asset.get("back", ""), {}).get("subtitle", ""),
            "backOrientation": _detect_orientation(images_src / asset["back"], assets.get(asset.get("back", ""), {})) if asset.get("back") else "",
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
            "placement": asset.get("placement", {}),
            "orientation": orientation,
            "component": component,
            "tileType": asset.get("tileType", ""),
            "anomalies": asset.get("anomalies", []),
            "wormholes": asset.get("wormholes", []),
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

    # Map back images to their front asset for portrait orientation matching.
    back_to_front = {}
    front_portrait = set()
    for path, asset in assets.items():
        back = asset.get("back", "")
        if back:
            back_to_front[back] = path
        src_path = images_src / path
        if _detect_orientation(src_path, asset) == "portrait":
            front_portrait.add(path)

    images_dest = output_dir / "assets" / "images"
    images_dest.mkdir(parents=True, exist_ok=True)
    for p in images_src.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
            rel = p.relative_to(images_src)
            dest = images_dest / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            rel_path = str(rel).replace("\\", "/")
            asset = assets.get(rel_path, {})
            rotate = int(asset.get("rotate", 0) or 0)
            component = asset.get("component", "us-mini")
            is_back = rel_path in back_to_front

            if component in _CROP_COMPONENTS:
                crop_box = _component_crop_box(component)
                data = _crop_image(p, crop_box, rotate)
                dest.write_bytes(data)
            elif is_back and back_to_front[rel_path] in front_portrait:
                with Image.open(p) as img:
                    img = img.convert("RGB")
                    if rotate:
                        img = img.rotate(-rotate, expand=True)
                    w, h = img.size
                    if h <= w:
                        img = img.rotate(90, expand=True)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=92)
                    dest.write_bytes(buffer.getvalue())
            else:
                if rotate:
                    with Image.open(p) as img:
                        img = img.convert("RGB")
                        img = img.rotate(-rotate, expand=True)
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=92)
                        dest.write_bytes(buffer.getvalue())
                else:
                    with Image.open(p) as img:
                        fmt = img.format or "JPEG"
                        if fmt.upper() in ("JPEG", "JPG"):
                            img = img.convert("RGB")
                            buffer = io.BytesIO()
                            img.save(buffer, format="JPEG", quality=92)
                            dest.write_bytes(buffer.getvalue())
                        else:
                            if "exif" in img.info:
                                img.info.pop("exif")
                            buffer = io.BytesIO()
                            img.save(buffer, format=fmt)
                            dest.write_bytes(buffer.getvalue())


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
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def _build_export(config: dict, images: list[dict], sections: list[dict], git_commit: str) -> dict:
    """Build a clean public JSON export from the generated image data."""

    def _truthy(value):
        if value is None:
            return False
        if isinstance(value, (list, dict, str)):
            return bool(value)
        return value not in (False, 0)

    def clean_card(img: dict) -> dict:
        card: dict = {
            "id": img["id"],
            "name": img.get("name", ""),
            "type": img.get("type", ""),
            "faction": img.get("faction", ""),
            "group": img.get("group", ""),
            "section": img.get("section", ""),
            "component": img.get("component", ""),
            "front": img.get("path", ""),
        }

        for field in ("subtitle", "flavour", "color", "tileType", "backTitle", "backSubtitle"):
            value = img.get(field)
            if _truthy(value):
                card[field] = value

        description = img.get("description", "")
        if _truthy(description):
            card["description"] = _markdown_filter(description)

        for field in ("anomalies", "wormholes"):
            value = img.get(field)
            if value:
                card[field] = value

        faq = img.get("faq", [])
        if faq:
            card["faq"] = [
                {"q": _markdown_filter(item.get("q", "")), "a": _markdown_filter(item.get("a", ""))}
                for item in faq
            ]

        for obj_field in ("stats", "abilities"):
            value = img.get(obj_field)
            if value and any(_truthy(v) for v in value.values()):
                card[obj_field] = value

        source = img.get("source")
        if source and source.get("enabled"):
            card["source"] = {
                k: v for k, v in source.items()
                if k != "enabled" and _truthy(v)
            }

        placement = img.get("placement")
        if placement and placement.get("enabled"):
            rules = placement.get("rules")
            if rules:
                card["placement"] = rules

        prereq = img.get("prereq")
        if prereq and prereq.get("enabled") and _truthy(prereq.get("value")):
            card["prereq"] = prereq["value"]

        synergy = img.get("synergy")
        if synergy and synergy.get("enabled") and _truthy(synergy.get("value")):
            card["synergy"] = synergy["value"]

        back = img.get("back", "")
        if back:
            card["back"] = back if back.startswith("assets/images/") else f"assets/images/{back}"

        return card

    overview = config.get("overview", "")
    return {
        "id": config.get("id", ""),
        "name": config.get("name", ""),
        "version": config.get("version", ""),
        "description": config.get("description", ""),
        "overview": _markdown_filter(overview) if overview else "",
        "git_commit": git_commit,
        "sections": [
            {"id": s.get("id", ""), "title": s.get("title", ""), "type": s.get("type", "")}
            for s in sections
        ],
        "groups": sorted({img.get("group", "") for img in images if img.get("group")}),
        "cards": [clean_card(img) for img in images if not img.get("hidden")],
    }


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

    # Write clean public export data.json
    export_data = _build_export(config, images, site["sections"], git_commit)
    (output_dir / "data.json").write_text(json.dumps(export_data, indent=2), encoding="utf-8")

    # Write search-data.js — inline full site data so search works with file:// (no fetch needed)
    js_dir = output_dir / "assets" / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (js_dir / "search-data.js").write_text(
        f"window.SITE_DATA = {json.dumps(site)};", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description="Build a static expansion site")
    parser.add_argument("config", type=Path, help="Path to config.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    args = parser.parse_args()
    build_site(args.config, args.output)


if __name__ == "__main__":
    main()
