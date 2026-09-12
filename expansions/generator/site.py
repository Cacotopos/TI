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

# Maximum width (in pixels) for web-displayed card images. Source images are
# often 1764px+ wide but displayed at ~400px, so downsizing to 2x retina
# avoids shipping multi-megabyte files to S3 with no visible quality loss.
# The banner is exempt (it needs full width for the header cover).
_WEB_MAX_WIDTH = 800


def _resize_for_web(img: Image.Image) -> Image.Image:
    """Downscale an image so its longest side is at most _WEB_MAX_WIDTH pixels.
    Images already at or below the cap are returned unchanged.
    """
    w, h = img.size
    longest = max(w, h)
    if longest <= _WEB_MAX_WIDTH:
        return img
    scale = _WEB_MAX_WIDTH / longest
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
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
        img = _resize_for_web(img)
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
    banner_rel = (config.get("banner") or {}).get("path", "").replace("\\", "/")
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
            is_banner = rel_path == banner_rel

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
                    if not is_banner:
                        img = _resize_for_web(img)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=92)
                    dest.write_bytes(buffer.getvalue())
            else:
                if rotate:
                    with Image.open(p) as img:
                        img = img.convert("RGB")
                        img = img.rotate(-rotate, expand=True)
                        if not is_banner:
                            img = _resize_for_web(img)
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=92)
                        dest.write_bytes(buffer.getvalue())
                else:
                    with Image.open(p) as img:
                        fmt = img.format or "JPEG"
                        if fmt.upper() in ("JPEG", "JPG"):
                            img = img.convert("RGB")
                            if not is_banner:
                                img = _resize_for_web(img)
                            buffer = io.BytesIO()
                            img.save(buffer, format="JPEG", quality=92)
                            dest.write_bytes(buffer.getvalue())
                        else:
                            if "exif" in img.info:
                                img.info.pop("exif")
                            if not is_banner:
                                img = _resize_for_web(img)
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


# Version salt for the content hash. Bumping this prefix changes every hashed
# filename, which forces CloudFront/browsers to fetch fresh copies.
_HASH_VERSION = "v2"


# Pattern for a hashed filename segment, e.g. `.v2-3a808a5d1455`
_HASH_SEGMENT = re.compile(rf"\.{re.escape(_HASH_VERSION)}-[0-9a-f]{{12}}")


# Pattern to detect any old fingerprinted filename so we can clean them up.
_ANY_HASH_SEGMENT = re.compile(r"\.v\d+-[0-9a-f]{12}")


def _is_hashed_name(name: str) -> bool:
    return bool(_ANY_HASH_SEGMENT.search(name))


def _clean_hashed_name(name: str) -> str:
    """Return the clean filename for a fingerprinted file, e.g. styles.css."""
    # Remove the hash segment that appears before the final extension.
    return re.sub(rf"\.{re.escape(_HASH_VERSION)}-[0-9a-f]{{12}}(?=\.[^.]+$)", "", name)


def _hashed_path(path: Path, hash_value: str) -> Path:
    """Return a new Path with the hash segment inserted before the extension."""
    return path.parent / f"{path.stem}.{_HASH_VERSION}-{hash_value}{path.suffix}"


def _file_hash(path: Path) -> str:
    data = path.read_bytes()
    if data:
        return hashlib.md5(_HASH_VERSION.encode() + data).hexdigest()[:12]
    return "empty"


def _hash_asset_file(path: Path, output_dir: Path) -> dict[str, str]:
    """Hash a single file, rename it with the hash in its filename, and return
    a mapping from the clean relative path to the hashed relative path.
    """
    if not path.exists():
        return {}
    h = _file_hash(path)
    new_path = _hashed_path(path, h)
    if path != new_path:
        path.rename(new_path)
    clean_rel = str(new_path.parent.relative_to(output_dir) / _clean_hashed_name(new_path.name)).replace("\\", "/")
    new_rel = str(new_path.relative_to(output_dir)).replace("\\", "/")
    return {clean_rel: new_rel}


def _compute_asset_hashes(output_dir: Path) -> dict[str, str]:
    """Hash and rename all files under output_dir/assets/.

    Returns a mapping from clean relative paths to hashed relative paths.
    Old hashed files from previous runs are removed first to avoid duplicates.
    """
    hashes: dict[str, str] = {}
    if not output_dir.exists():
        return hashes
    assets_dir = output_dir / "assets"
    if not assets_dir.exists():
        return hashes

    # Remove any stale hashed files from a previous build.
    for p in assets_dir.rglob("*"):
        if p.is_file() and _is_hashed_name(p.name):
            try:
                p.unlink()
            except Exception:
                pass

    for p in assets_dir.rglob("*"):
        if not p.is_file():
            continue
        try:
            hashes.update(_hash_asset_file(p, output_dir))
        except Exception:
            continue
    return hashes


def _hash_data_json(path: Path) -> dict[str, str]:
    """Return a query-string busted URL for data.json without renaming it."""
    if not path.exists():
        return {}
    h = _file_hash(path)
    rel = str(path.relative_to(path.parent.parent)).replace("\\", "/")
    return {rel: f"{rel}?v={_HASH_VERSION}-{h}"}


def _bust_url(path: str, hashes: dict[str, str]) -> str:
    """Resolve a clean site-relative path to its content-hashed public URL."""
    if not path or path.startswith(("http://", "https://", "//")):
        return path
    # Strip a leading slash so relative paths always match.
    lookup = path.lstrip("/")
    if lookup in hashes:
        return hashes[lookup]
    return path


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

    # Prepare the banner image so it gets content-hashed with the rest.
    banner_path = _prepare_banner(config, output_dir)

    images = _collect_assets(config)
    git_commit = _git_commit()

    # Hash and rename static assets. This gives each asset a content-hashed
    # filename, which is the only cache-busting mechanism that works when a
    # CDN (e.g. CloudFront) ignores query strings.
    asset_hashes = _compute_asset_hashes(output_dir)

    # Add content-hashed display URLs to each image while keeping the clean
    # source-relative paths intact for data.json and external consumers.
    for img in images:
        img["url"] = _bust_url(img.get("path", ""), asset_hashes)
        back = img.get("back", "")
        if back:
            back_path = back if back.startswith("assets/images/") else f"assets/images/{back}"
            img["back_url"] = _bust_url(back_path, asset_hashes)

    site = {
        **config,
        "images": images,
        "sections": config.get("sections", []),
        "banner_path": banner_path,
        "banner_url": _bust_url(banner_path or "", asset_hashes),
        "git_commit": git_commit,
    }

    # Write search-data.js before rendering HTML, then hash/rename it so the
    # <script src> in the HTML can point to a fingerprinted file.
    js_dir = output_dir / "assets" / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    search_data_path = js_dir / "search-data.js"
    search_data_path.write_text(
        f"window.SITE_DATA = {json.dumps(site)};", encoding="utf-8"
    )
    asset_hashes.update(_hash_asset_file(search_data_path, output_dir))

    # Write the clean public export data.json. It keeps its clean filename but
    # gets a query-string hash for the download link.
    export_data = _build_export(config, images, site["sections"], git_commit)
    data_json_path = output_dir / "data.json"
    data_json_path.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
    asset_hashes.update(_hash_data_json(data_json_path))

    def bust_filter(path: str) -> str:
        return _bust_url(path, asset_hashes)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))
    env.filters["markdown"] = _markdown_filter
    env.filters["bust"] = bust_filter

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


def main():
    parser = argparse.ArgumentParser(description="Build a static expansion site")
    parser.add_argument("config", type=Path, help="Path to config.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    args = parser.parse_args()
    build_site(args.config, args.output)


if __name__ == "__main__":
    main()
