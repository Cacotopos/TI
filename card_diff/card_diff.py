#!/usr/bin/env python3
"""
card_diff.py - Compare text extracted from game card images across two folders.

Usage:
    python card_diff.py <folder_a> <folder_b> [--output exports/reports/<name>]

Matches images by filename, extracts text via EasyOCR, diffs the results,
and writes a self-contained static report directory (index.html + results.json)
ready for S3 or any static host.
"""

import argparse
import difflib
import hashlib
import io
import json
import re
import sys
import warnings
from collections import OrderedDict
from pathlib import Path

warnings.filterwarnings("ignore", message=".*pin_memory.*", category=UserWarning)

import easyocr
import numpy as np
import torch
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# Unit abilities detected in the ability text block (new version only)
UNIT_ABILITIES = [
    "PRODUCTION",
    "BOMBARDMENT",
    "ANTI-FIGHTER BARRAGE",
    "PLANETARY SHIELD",
    "SUSTAIN DAMAGE",
    "DEPLOY",
    "SPACE CANNON",
]
UNIT_ABILITY_LABELS = {
    "PRODUCTION": "PROD",
    "BOMBARDMENT": "BOMB",
    "ANTI-FIGHTER BARRAGE": "AFB",
    "PLANETARY SHIELD": "SHIELD",
    "SUSTAIN DAMAGE": "SUSTAIN",
    "DEPLOY": "DEPLOY",
    "SPACE CANNON": "CANNON",
}
ACTION_LABEL = "ACTION"


def find_images(folder: Path) -> dict[str, Path]:
    return {
        str(p.relative_to(folder)): p
        for p in sorted(folder.rglob("*"))
        if p.suffix.lower() in IMAGE_EXTENSIONS
    }


MIN_CONFIDENCE = 0.5
ROW_BUCKET_PX = 15
FUZZY_EQUAL_RATIO = 0.85
CACHE_VERSION = 6  # bump to invalidate all caches

# Card text regions (x, y, w, h) — top-left origin
REGION_TITLE   = (300, 120, 1250, 100)
REGION_ABILITY = (725, 340,  900, 740)  # split at divider if found
REGION_ART     = ( 20, 335,  670, 560)
REGION_TITLE_PIX = REGION_TITLE  # alias for pixel diff

# Horizontal white divider detection
DIVIDER_BRIGHT_THRESHOLD = 200   # min mean brightness for a white row
DIVIDER_MIN_COVERAGE     = 0.70  # fraction of row width that must be bright
DIVIDER_MIN_THICKNESS    = 3     # consecutive bright rows to confirm divider


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_version(text: str) -> str:
    # Remove version watermark in various forms before punctuation is stripped:
    # "m+ 3.0.8", "mt v3.1", "mtv3.1", "m+3.0.8", standalone version numbers
    text = re.sub(r"m[+tv]*\s*v?\s*\d+[.\d]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bv\s*\d+[.\d]*\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _to_python(obj):
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if isinstance(obj, list):
        return [_to_python(x) for x in obj]
    return obj


def load_ocr_cache(image_path: Path) -> dict | None:
    cache_path = image_path.with_suffix(image_path.suffix + ".ocr.json")
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if data.get("mtime") == image_path.stat().st_mtime and data.get("v") == CACHE_VERSION:
            return data["regions"]
    except Exception:
        pass
    return None


def save_ocr_cache(image_path: Path, regions: dict) -> None:
    cache_path = image_path.with_suffix(image_path.suffix + ".ocr.json")
    serializable = {
        k: [[_to_python(bbox), text, float(conf)] for bbox, text, conf in v]
        for k, v in regions.items()
    }
    data = {"v": CACHE_VERSION, "mtime": image_path.stat().st_mtime, "regions": serializable}
    cache_path.write_text(json.dumps(data), encoding="utf-8")


def _ocr_region(reader: easyocr.Reader, img: "Image.Image", box: tuple) -> list:
    """Crop img to (x,y,w,h) box and run OCR, returning raw results."""
    x, y, w, h = box
    crop = img.crop((x, y, x + w, y + h))
    raw = reader.readtext(np.array(crop), detail=1, paragraph=False)
    # Offset bounding boxes back to full-image coordinates
    return [[[[ px + x, py + y] for px, py in bbox], text, conf] for bbox, text, conf in raw]


def _find_divider_y(img: "Image.Image", box: tuple) -> int | None:
    """Return the y coordinate (in full-image space) of the first white horizontal
    divider line within box, or None. Searches middle 20%-80% of the region."""
    x, y, w, h = box
    crop = np.array(img.crop((x, y, x + w, y + h)).convert("L"), dtype=np.float32)
    min_bright_px = int(w * DIVIDER_MIN_COVERAGE)
    search_start = int(h * 0.20)
    search_end   = int(h * 0.80)
    consecutive = 0
    first_row = None
    for row_idx in range(search_start, search_end):
        bright_px = int((crop[row_idx] >= DIVIDER_BRIGHT_THRESHOLD).sum())
        if bright_px >= min_bright_px:
            if consecutive == 0:
                first_row = row_idx
            consecutive += 1
            if consecutive >= DIVIDER_MIN_THICKNESS:
                return y + first_row
        else:
            consecutive = 0
            first_row = None
    return None


def _region_text(results: list) -> str:
    """Filter, sort, normalise a list of raw OCR results into a text string."""
    filtered = [(r[0], r[1], r[2]) for r in results if r[2] >= MIN_CONFIDENCE]
    filtered.sort(key=lambda r: (round(r[0][0][1] / ROW_BUCKET_PX), r[0][0][0]))
    return "\n".join(normalize(strip_version(text)) for _, text, _ in filtered)


def _fuzzy_ability_match(flat: str, ability: str, threshold: float = 0.85) -> bool:
    """Return True if ability is a fuzzy match inside the flat text."""
    ability_words = ability.split()
    n = len(ability_words)
    words = flat.split()
    for i in range(len(words) - n + 1):
        phrase = " ".join(words[i:i + n])
        if difflib.SequenceMatcher(None, ability, phrase).ratio() >= threshold:
            return True
    return False


def detect_unit_abilities(results: list) -> tuple[set[str], bool]:
    """Return (unit_abilities, has_action) found in raw OCR ability-region results.
    Matches ALL CAPS unit-ability phrases and the ACTION: keyword.
    """
    if not results:
        return set(), False
    filtered = [(r[0], r[1], r[2]) for r in results if r[2] >= MIN_CONFIDENCE]
    filtered.sort(key=lambda r: (round(r[0][0][1] / ROW_BUCKET_PX), r[0][0][0]))
    flat = " ".join(text for _, text, _ in filtered)
    flat_upper = flat.upper()
    abilities = {ab for ab in UNIT_ABILITIES if ab in flat_upper or _fuzzy_ability_match(flat_upper, ab)}
    # Match "ACTION:" as a standalone keyword at the start of the ability text.
    # Case-insensitive uses of "action:" (e.g., "tactical action:") are false positives.
    has_action = flat_upper.strip().startswith("ACTION:")
    return abilities, has_action


def _apply_ability_suppression(name: str, abilities: set[str], has_action: bool) -> tuple[set[str], bool]:
    """Apply per-card suppress_abilities / suppress_action overrides."""
    overrides = _placement_overrides_for(name)
    for ab in overrides.get("suppress_abilities", []):
        abilities.discard(ab)
    if overrides.get("suppress_action", False):
        has_action = False
    return abilities, has_action


def flavour_text(image_path: Path) -> str:
    """Return the cached flavour text for an image, or empty string."""
    cached = load_ocr_cache(image_path)
    if cached is None:
        return ""
    return _region_text(cached.get("flavour", []))


def extract_text(reader: easyocr.Reader, image_path: Path) -> str:
    cached = load_ocr_cache(image_path)
    if cached is not None:
        regions = cached
    else:
        img = Image.open(image_path).convert("RGB")
        ax, ay, aw, ah = REGION_ABILITY

        # Detect divider line within ability region
        divider_y = _find_divider_y(img, REGION_ABILITY)

        # OCR title
        title_results = _ocr_region(reader, img, REGION_TITLE)

        if divider_y is not None:
            # Split ability region at the divider line
            ability_results = _ocr_region(reader, img, (ax, ay, aw, max(1, divider_y - ay)))
            flavour_results = _ocr_region(reader, img, (ax, divider_y, aw, max(1, ay + ah - divider_y)))
        else:
            ability_results = _ocr_region(reader, img, REGION_ABILITY)
            flavour_results = []

        regions = {"title": title_results, "ability": ability_results, "flavour": flavour_results}
        save_ocr_cache(image_path, regions)

    # Combine: title + ability only (flavour text is cosmetic, skip it)
    all_results = regions["title"] + regions["ability"]
    return _region_text(all_results)


def get_ability_results(reader: easyocr.Reader, image_path: Path) -> list:
    """Return raw OCR results for the ability region, running OCR if not cached."""
    cached = load_ocr_cache(image_path)
    if cached is not None and "ability" in cached:
        return cached["ability"]
    # Cache missing or incomplete: run full text extraction to populate it
    extract_text(reader, image_path)
    cached = load_ocr_cache(image_path)
    return cached.get("ability", []) if cached else []


def words_fuzzy_equal(a: list[str], b: list[str]) -> bool:
    """True if two word sequences are near-identical after joining (OCR noise)."""
    sa, sb = " ".join(a), " ".join(b)
    return difflib.SequenceMatcher(None, sa, sb).ratio() >= FUZZY_EQUAL_RATIO


def char_bag(text: str) -> str:
    """Sorted character bag of all non-space chars — immune to token splits and reordering."""
    return "".join(sorted(text.replace(" ", "").replace("\n", "")))


def bags_equal(text_a: str, text_b: str) -> bool:
    """True if the character bags are identical or near-identical (handles OCR noise)."""
    ba, bb = char_bag(text_a), char_bag(text_b)
    if ba == bb:
        return True
    # Allow up to ~3% character-level noise relative to total length
    ratio = difflib.SequenceMatcher(None, ba, bb).ratio()
    return ratio >= 0.97


def diff_texts(name: str, text_a: str, text_b: str) -> dict:
    def prepare(text: str) -> list[str]:
        return [w for l in text.splitlines() for w in l.split() if w]

    words_a = prepare(text_a)
    words_b = prepare(text_b)

    # Fast path: near-identical character bags = no real change
    if bags_equal(text_a, text_b):
        return {"name": name, "changed": False, "text_a": " ".join(words_a), "text_b": " ".join(words_b)}

    # Check if all differing blocks are fuzzy-equal (OCR noise)
    sm = difflib.SequenceMatcher(None, words_a, words_b, autojunk=False)
    real_change = False
    prev = None
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            prev = None
            continue
        elif tag == "replace":
            if not words_fuzzy_equal(words_a[i1:i2], words_b[j1:j2]):
                real_change = True
                break
            prev = None
        elif tag in ("delete", "insert"):
            # Paired delete+insert of fuzzy-equal content = shuffle noise
            opposite = "insert" if tag == "delete" else "delete"
            if prev and prev[0] == opposite and words_fuzzy_equal(
                words_a[prev[1]:prev[2]], words_b[prev[3]:prev[4]]
            ):
                prev = None
            else:
                prev = (tag, i1, i2, j1, j2)
                real_change = True
                break

    ability_ratio = difflib.SequenceMatcher(None, words_a, words_b, autojunk=False).ratio() if real_change else 1.0
    return {
        "name": name,
        "changed": real_change,
        "ability_ratio": round(ability_ratio, 3),
        "text_a": " ".join(words_a),
        "text_b": " ".join(words_b),
    }


PIXEL_DIFF_THRESHOLD = 15   # per-channel delta to ignore JPEG noise
PIXEL_SHIFT = 3             # max pixel offset to try when aligning images
VISUAL_CHANGE_PCT = 2.0     # % of icon-region pixels that must differ to flag visual change
ICON_REGION = (0, -280, 700, 0)  # (left, top_from_bottom, right, bottom_from_bottom)
TEXT_CHANGE_PCT  = 4.0      # % of ability-region pixels that must differ before OCR is run
ART_CHANGE_PCT   = 4.0      # % of art-region pixels that must differ to flag art change
TITLE_CHANGE_PCT = 4.0      # % of title-region pixels that must differ to flag title change

# Placement strip — x offset and strip width; Y start set to capture all icons
_PLACE_X   = 100
_PLACE_Y   = 925   # absolute card Y (frontier is highest at 925)
_PLACE_W   = 560
ICON_DIR   = Path(__file__).parent.parent / "Icons"

# Absolute Y coordinate of each base icon's top edge on the card
_ICON_ABS_Y = {
    "frontier":   925,
    "industrial": 940,
    "mecatol":    941,
    "legendary":  944,
    "relic":      945,
    "cultural":   943,
    "hazardous":  950,
    "invalid":    967,
    # not_X composites use the same Y as their base icon
    "not_legendary":  944,
    "not_mecatol":    941,
    "not_relic":      945,
    "tech":           947,
}

# Calibrated mean-abs-diff thresholds (score < threshold => icon present)
_ICON_THRESHOLDS = {
    # Base icons (no cross)
    "hazardous":      35.0,
    "cultural":       56.0,
    "industrial":     53.0,
    "relic":          59.3,
    "legendary":      73.2,
    "mecatol":        30.6,
    "frontier":       62.1,
    # Not-X composites
    "not_legendary":  62.0,
    "not_mecatol":    31.3,
    "not_relic":      33.0,
    "tech":           55.7,
}

_PLACEMENT_TEMPLATES: dict | None = None


# Icons that use the full opaque mask (no white-bg exclusion)
_FULL_MASK_ICONS = {"legendary", "mecatol", "frontier",
                    "not_legendary", "not_mecatol"}


def _load_placement_templates() -> dict:
    global _PLACEMENT_TEMPLATES
    if _PLACEMENT_TEMPLATES is not None:
        return _PLACEMENT_TEMPLATES
    _PLACEMENT_TEMPLATES = {}
    for name in _ICON_ABS_Y:
        p = ICON_DIR / f"{name}.png"
        if not p.exists():
            continue
        arr = np.array(Image.open(p).convert("RGBA"), dtype=np.float32)
        alpha  = arr[:, :, 3] / 255.0
        rgb    = arr[:, :, :3]
        opaque = alpha > 0.3
        if name in _FULL_MASK_ICONS:
            mask = opaque
        else:
            mask = opaque & (rgb.min(axis=2) < 180)
        _PLACEMENT_TEMPLATES[name] = (arr[:, :, :3], mask)
    return _PLACEMENT_TEMPLATES


def _icon_scan_score(card_rgb: "Image.Image", icon: str) -> float:
    """Slide icon template horizontally at its fixed Y; return best mean abs diff."""
    templates = _load_placement_templates()
    if icon not in templates:
        return 9999.0
    t_rgb, mask = templates[icon]
    th, tw = t_rgb.shape[:2]
    if mask.sum() < 10:
        return 9999.0
    y_abs = _ICON_ABS_Y[icon]
    strip = np.array(card_rgb.crop((_PLACE_X, y_abs, _PLACE_X + _PLACE_W, y_abs + th)),
                     dtype=np.float32)
    sw = strip.shape[1]
    if sw < tw:
        return 9999.0
    n_pos = sw - tw + 1
    # Vectorised: shape (n_pos, th, tw, 3)
    windows = np.lib.stride_tricks.sliding_window_view(strip[:th], (th, tw, 3)).reshape(n_pos, th, tw, 3)
    diffs = np.abs(windows - t_rgb)          # (n_pos, th, tw, 3)
    masked = diffs[:, mask, :]               # (n_pos, n_opaque, 3)
    scores = masked.mean(axis=(1, 2))        # (n_pos,)
    return float(scores.min())


def _load_placement_overrides() -> dict:
    """Load optional placement overrides from overrides.json next to the script."""
    p = Path(__file__).parent / "overrides.json"
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_PLACEMENT_OVERRIDES: dict | None = None


def _placement_overrides_for(name: str) -> dict:
    global _PLACEMENT_OVERRIDES
    if _PLACEMENT_OVERRIDES is None:
        _PLACEMENT_OVERRIDES = _load_placement_overrides()
    # Match by full path or by filename only
    if name in _PLACEMENT_OVERRIDES:
        return _PLACEMENT_OVERRIDES[name]
    if Path(name).name in _PLACEMENT_OVERRIDES:
        return _PLACEMENT_OVERRIDES[Path(name).name]
    return {}


def _detect_placement_icons_core(card_rgb: "Image.Image", override_path: Path | None = None) -> tuple[frozenset, frozenset]:
    """Core detection logic on an already-opened image."""
    raw = set()
    for icon, threshold in _ICON_THRESHOLDS.items():
        score = _icon_scan_score(card_rgb, icon)
        if score < threshold:
            raw.add(icon)
    # Resolve not_X composites
    icons = set()
    negated = set()
    for icon in raw:
        if icon.startswith("not_"):
            base = icon[4:]
            icons.add(base)
            negated.add(base)
        else:
            icons.add(icon)
    # Apply optional manual overrides
    overrides = _placement_overrides_for(str(override_path)) if override_path else {}
    for ic in overrides.get("add_icons", []):
        icons.add(ic)
    for ic in overrides.get("remove_icons", []):
        icons.discard(ic)
    for ic in overrides.get("add_negated", []):
        if ic in icons:
            negated.add(ic)
    for ic in overrides.get("remove_negated", []):
        negated.discard(ic)
    return frozenset(icons), frozenset(negated)


def detect_placement_icons(img_path: Path) -> tuple[frozenset, frozenset]:
    """Return (icons, negated) where icons is the full set of detected icon names
    and negated is the subset that have the invalid cross over them.
    """
    card_rgb = Image.open(img_path).convert("RGB")
    return _detect_placement_icons_core(card_rgb, override_path=img_path)


ICON_LABELS = {
    "invalid": "Not", "relic": "Relic", "hazardous": "Haz",
    "industrial": "Ind", "cultural": "Cul", "legendary": "Leg",
    "mecatol": "MR", "frontier": "Frontier", "tech": "Tech",
}


def format_placement(icons: frozenset, negated: frozenset = frozenset()) -> str:
    if not icons:
        return ""
    parts = []
    icon_order = ["mecatol", "legendary", "relic", "hazardous", "industrial", "cultural", "frontier", "tech"]
    for ic in icon_order:
        if ic not in icons:
            continue
        label = ICON_LABELS.get(ic, ic)
        if ic in negated:
            parts.append(f"Not {label}")
        else:
            parts.append(label)
    return "  ".join(parts)


def _region_pixel_diff(img_a: "Image.Image", img_b: "Image.Image", box: tuple) -> float:
    """Pixel diff % for a (x, y, w, h) region with shift compensation."""
    x, y, w, h = box
    crop_a = np.array(img_a.crop((x, y, x + w, y + h)), dtype=np.int16)
    best = 100.0
    for dy in range(-PIXEL_SHIFT, PIXEL_SHIFT + 1):
        for dx in range(-PIXEL_SHIFT, PIXEL_SHIFT + 1):
            crop_b = np.array(img_b.crop((x + dx, y + dy, x + w + dx, y + h + dy)), dtype=np.int16)
            pct = np.any(np.abs(crop_a - crop_b) > PIXEL_DIFF_THRESHOLD, axis=2).sum() / (crop_a.shape[0] * crop_a.shape[1]) * 100
            if pct < best:
                best = pct
    return round(best, 2)


def _open_pair(path_a: Path, path_b: Path):
    img_a = Image.open(path_a).convert("RGB")
    img_b = Image.open(path_b).convert("RGB")
    if img_a.size != img_b.size:
        img_b = img_b.resize(img_a.size, Image.LANCZOS)
    return img_a, img_b


def ability_pixel_diff(img_a: "Image.Image", img_b: "Image.Image") -> float:
    """Pixel diff % for the ability text region — used as pre-flight before OCR."""
    ax, ay, aw, ah = REGION_ABILITY
    return _region_pixel_diff(img_a, img_b, (ax, ay, aw, ah))


def title_pixel_diff(img_a: "Image.Image", img_b: "Image.Image") -> float:
    return _region_pixel_diff(img_a, img_b, REGION_TITLE_PIX)


def art_pixel_diff(img_a: "Image.Image", img_b: "Image.Image") -> float:
    return _region_pixel_diff(img_a, img_b, REGION_ART)


def placement_changed(path_a: Path, path_b: Path) -> tuple[bool, str, str, frozenset, frozenset, frozenset, frozenset]:
    """Detect placement icons; return (changed, label_a, label_b, icons_a, icons_b, negated_a, negated_b)."""
    img_a, img_b = _open_pair(path_a, path_b)
    return placement_changed_on(img_a, img_b, path_a, path_b)


def placement_changed_on(img_a: "Image.Image", img_b: "Image.Image", path_a: Path | None = None, path_b: Path | None = None) -> tuple[bool, str, str, frozenset, frozenset, frozenset, frozenset]:
    """Detect placement icons on already-opened images."""
    icons_a, neg_a = _detect_placement_icons_core(img_a, override_path=path_a)
    icons_b, neg_b = _detect_placement_icons_core(img_b, override_path=path_b)
    changed = (icons_a != icons_b) or (neg_a != neg_b)
    return changed, format_placement(icons_a, neg_a), format_placement(icons_b, neg_b), icons_a, icons_b, neg_a, neg_b


def _file_hash(path: Path) -> str:
    """Return the MD5 hex digest of a file, read in chunks."""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_mask_crop_box(mask_path: Path) -> tuple[float, float, float, float]:
    """Load the card mask and return the relative bounding box (left, top, right, bottom).

    The mask uses the alpha channel to indicate the card region: the transparent part
    is the card. If no alpha channel exists, the dark foreground is treated as the card.
    """
    mask_img = Image.open(mask_path).convert("RGBA")
    r, g, b, a = mask_img.split()
    alpha = np.array(a)
    if alpha.max() > 0:
        # Transparent pixels are the card.
        card_pixels = alpha < 128
    else:
        # No alpha: treat dark foreground as the card.
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


# Relative crop box from the card mask. Initialized lazily in copy_image_to_report.
_MASK_CROP_BOX: tuple[float, float, float, float] | None = None


def copy_image_to_report(path: Path, output_dir: Path, side: str,
                         mask_path: Path | None = None) -> str:
    """Copy an image into the report's images/{side}/ tree and return its relative path.

    If a card mask is available, the image is cropped to the card's bounding box.
    The output is saved as JPEG (or PNG if the source has transparency).
    Skips the copy if the destination already exists with the same MD5 checksum, so
    re-rendering a report does not touch unchanged images and S3 sync stays fast.
    """
    if not path or not path.exists():
        return ""

    global _MASK_CROP_BOX
    if mask_path is None:
        mask_path = Path(__file__).parent.parent / "Icons" / "Card Mask.png"
    if _MASK_CROP_BOX is None and mask_path.exists():
        _MASK_CROP_BOX = _load_mask_crop_box(mask_path)

    rel = Path(side) / path.name
    dest = output_dir / "images" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        if _MASK_CROP_BOX:
            left, top, right, bottom = _MASK_CROP_BOX
            w, h = img.size
            crop = (int(left * w), int(top * h), int(right * w), int(bottom * h))
            img = img.crop(crop)

        # If the source had transparency, keep PNG; otherwise use JPEG for size.
        if img.mode == "RGBA":
            ext = ".png"
        else:
            ext = ".jpg"
        dest = dest.with_suffix(ext)
        buffer = io.BytesIO()
        if ext == ".png":
            img.save(buffer, format="PNG")
        else:
            img.save(buffer, format="JPEG", quality=92)
        data = buffer.getvalue()

    if not dest.exists() or _file_hash(dest) != hashlib.md5(data).hexdigest():
        dest.write_bytes(data)
    return str(dest.relative_to(output_dir)).replace("\\", "/")


REPORT_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
  header { background: #1a1d27; border-bottom: 1px solid #2d3148; padding: 1.5rem 2rem; display: flex; align-items: center; justify-content: space-between; }
  h1 { font-size: 1.4rem; font-weight: 700; }
  .subtitle { color: #64748b; font-size: 0.9rem; margin-top: 0.2rem; }
  .stats { display: flex; gap: 1.5rem; align-items: center; }
  .stat { text-align: center; }
  .stat-num { font-size: 1.8rem; font-weight: 700; }
  .stat-num.red { color: #f87171; }
  .stat-num.green { color: #4ade80; }
  .stat-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .export-btn { background: #3b82f6; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 1rem; cursor: pointer; font-size: 0.9rem; font-weight: 600; transition: background 0.15s; }
  .export-btn:hover { background: #2563eb; }
  main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
  .folder-section { margin-bottom: 1.25rem; }
  .folder-header { display: flex; align-items: center; gap: 0.75rem; padding: 0.85rem 1.25rem; background: #12151f; border: 1px solid #2d3148; border-radius: 1.5rem; cursor: pointer; user-select: none; }
  .folder-header:hover { background: #1a1d2e; }
  .folder-chevron { font-size: 0.7rem; color: #64748b; transition: transform 0.2s; }
  .folder-chevron.open { transform: rotate(90deg); }
  .folder-name { font-weight: 700; font-size: 1rem; flex: 1; }
  .folder-count { font-size: 0.8rem; color: #64748b; }
  .folder-body { padding: 0.75rem 0 0 1.5rem; }
  .card { background: #1a1d27; border: 1px solid #2d3148; border-radius: 1.5rem; margin-bottom: 0.6rem; overflow: hidden; }
  .changed-card { border-color: #f87171; }
  .card-header { display: flex; align-items: center; gap: 0.75rem; padding: 0.85rem 1.25rem; cursor: pointer; user-select: none; }
  .card-header:hover { background: #1e2235; }
  .card-name { font-weight: 600; flex: 1; }
  .badge { font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 600; }
  .badge.ability-minor { background: #78350f; color: #fcd34d; }
  .badge.ability-moderate { background: #9a3412; color: #fdba74; }
  .badge.ability-major { background: #7f1d1d; color: #fca5a5; }
  .badge.flavour { background: #4c1d95; color: #c4b5fd; }
  .badge.title { background: #1e3a5f; color: #93c5fd; }
  .badge.art { background: #064e3b; color: #6ee7b7; }
  .badge.placement { background: #312e81; color: #a5b4fc; }
  .icon-pill { font-size: 0.7rem; padding: 0.15rem 0.5rem; opacity: 0.85; }
  .spacer { margin-left: 8px; }
  .icon-invalid    { background: #7f1d1d; color: #fca5a5; }
  .icon-legendary  { background: #78350f; color: #fde68a; }
  .icon-mecatol    { background: #1e3a5f; color: #93c5fd; }
  .icon-relic      { background: #713f12; color: #fcd34d; }
  .icon-hazardous  { background: #7f1d1d; color: #fca5a5; }
  .icon-industrial { background: #14532d; color: #86efac; }
  .icon-cultural   { background: #1e3a5f; color: #bfdbfe; }
  .icon-frontier   { background: #4a1d96; color: #ddd6fe; }
  .icon-tech       { background: #334155; color: #cbd5e1; }
  .unit-abilities { font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.75rem; }
  .ability-pill { background: #581c87; color: #e9d5ff; font-size: 0.7rem; padding: 0.15rem 0.5rem; opacity: 0.9; }
  .action-pill { background: #be185d; color: #fce7f3; font-size: 0.7rem; padding: 0.15rem 0.5rem; opacity: 0.9; }
  .badge.same { background: #14532d; color: #86efac; }
  .badge.new-badge { background: #14532d; color: #86efac; }
  .badge.deleted-badge { background: #713f12; color: #fde68a; }
  .chevron { font-size: 0.7rem; color: #64748b; transition: transform 0.2s; }
  .chevron.open { transform: rotate(90deg); }
  .card-body { padding: 1.25rem; border-top: 1px solid #2d3148; }
  .placement-diff { font-size: 0.85rem; color: #a5b4fc; margin-bottom: 0.75rem; }
  .images { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  .img-col { display: flex; flex-direction: column; gap: 0.5rem; }
  .img-label { font-size: 0.8rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
  .img-col img { width: 100%; border-radius: 1rem; border: 1px solid #2d3148; }
  .missing { opacity: 0.5; }
  .filters { display: flex; flex-direction: column; gap: 0.75rem; padding: 1rem 1.5rem; background: #12151f; border-bottom: 1px solid #2d3148; }
  .filter-section { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
  .filter-section-label { font-size: 0.7rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; min-width: 5rem; }
  .filter-btn { background: #1a1d27; color: #94a3b8; border: 1px solid #2d3148; padding: 0.35rem 0.9rem; border-radius: 9999px; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: all 0.15s; }
  .filter-btn:hover { background: #1e2235; color: #e2e8f0; }
  .filter-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
  .hidden { display: none !important; }
"""


def build_html(results: list[dict], folder_a: Path, folder_b: Path,
               images_a: dict, images_b: dict, output_dir: Path) -> str:
    side_a = folder_a.parent.name
    side_b = folder_b.parent.name
    expansion = folder_a.name

    new_count = sum(1 for r in results if r.get("missing") == "a")
    deleted_count = sum(1 for r in results if r.get("missing") == "b")
    changed_count = sum(1 for r in results if not r.get("missing") and (r["changed"] or r.get("visual_changed")))
    same_count = sum(1 for r in results if not r.get("missing") and not r["changed"] and not r.get("visual_changed"))
    total_count = len(results)

    # Discover which unit abilities / action actually appear in the B version
    discovered_abilities = set()
    has_any_action = False
    for r in results:
        discovered_abilities.update(r.get("unit_abilities_b", []))
        if r.get("has_action_b"):
            has_any_action = True

    # Group results by subfolder (parent of the relative name)
    folders: dict[str, list] = OrderedDict()
    for r in results:
        parts = Path(r["name"]).parts
        folder_key = str(Path(*parts[:-1])) if len(parts) > 1 else "."
        folders.setdefault(folder_key, []).append(r)

    cards_html = ""
    for folder_key, folder_results in folders.items():
        def _any_changed(r):
            return r.get("missing") or r.get("changed") or r.get("flavour_changed") or r.get("title_changed") or r.get("art_changed") or r.get("placement_changed")
        f_changed = sum(1 for r in folder_results if _any_changed(r))
        f_total = len(folder_results)
        folder_label = folder_key if folder_key != "." else "(root)"
        card_word = "card" if f_total == 1 else "cards"
        if f_changed:
            ch_word = "change" if f_changed == 1 else "changes"
            f_badge = f'<span class="badge ability-moderate">{f_changed} {ch_word}</span>'
        else:
            f_badge = f'<span class="badge same">all same</span>'

        inner = ""
        for r in folder_results:
            name = Path(r["name"]).name
            any_changed = r.get("changed") or r.get("flavour_changed") or r.get("title_changed") or r.get("art_changed") or r.get("placement_changed")
            sev = r.get("ability_severity")
            sev_label = sev.capitalize() if sev else ""
            # Icon pills for all detected icons (union of both versions)
            icons_a_set = r.get("icons_a", frozenset())
            icons_b_set = r.get("icons_b", frozenset())
            neg_a_set   = r.get("negated_a", frozenset())
            neg_b_set   = r.get("negated_b", frozenset())
            all_icons   = icons_a_set | icons_b_set
            all_negated = neg_a_set | neg_b_set
            icon_order  = ["legendary","mecatol","relic","hazardous","industrial","cultural","frontier","tech"]
            icon_pills  = ''.join(
                f'<span class="badge icon-pill icon-invalid" title="Not {ICON_LABELS.get(ic,ic)}">Not {ICON_LABELS.get(ic,ic)}</span>'
                if ic in all_negated else
                f'<span class="badge icon-pill icon-{ic}" title="{ICON_LABELS.get(ic,ic)}">{ICON_LABELS.get(ic,ic)}</span>'
                for ic in icon_order if ic in all_icons
            )
            ability_pills = ''.join(
                f'<span class="badge ability-pill ability-{ab.lower().replace(" ", "-")}">{UNIT_ABILITY_LABELS.get(ab, ab)}</span>'
                for ab in UNIT_ABILITIES if ab in r.get("unit_abilities_b", set())
            )
            action_pill = '<span class="badge action-pill">ACTION</span>' if r.get("has_action_b") else ''
            ability_block = ''
            if ability_pills or action_pill:
                ability_block = f'<div class="unit-abilities">Abilities: {action_pill}{ability_pills}</div>'

            badge = (
                (f'<span class="badge ability-{sev}">{sev_label}</span>' if sev else '') +
                ('<span class="badge flavour">Flavour</span>' if r.get("flavour_changed") else '') +
                ('<span class="badge title">Title</span>' if r.get("title_changed") else '') +
                ('<span class="badge art">Art</span>' if r.get("art_changed") else '') +
                ('<span class="badge placement">Placement &#x21C4;</span>' if r.get("placement_changed") else '') +
                ('<span class="badge same">Same</span>' if not any_changed else '') +
                ('<span class="spacer"></span>' if icon_pills else '') +
                icon_pills
            )
            data_abilities = '|'.join(sorted(r.get('unit_abilities_b', set())))
            data_action = 'true' if r.get('has_action_b') else 'false'
            if r.get("missing"):
                if r["missing"] == "a":
                    status_badge = '<span class="badge new-badge">New</span>'
                    img_src = copy_image_to_report(images_b[r["name"]], output_dir, "b") if r["name"] in images_b else ""
                    img_label = side_b
                    placement_line = f'<div class="placement-diff" style="opacity:0.5">Placement: <b>{r.get("placement_b") or "none"}</b></div>' if r.get("placement_b") else ""
                else:
                    status_badge = '<span class="badge deleted-badge">Deleted</span>'
                    img_src = copy_image_to_report(images_a[r["name"]], output_dir, "a") if r["name"] in images_a else ""
                    img_label = side_a
                    placement_line = f'<div class="placement-diff" style="opacity:0.5">Placement: <b>{r.get("placement_a") or "none"}</b></div>' if r.get("placement_a") else ""
                inner += f"""
              <div class="card changed-card" data-icons="{' '.join(sorted(all_icons))}" data-abilities="{data_abilities}" data-action="{data_action}">
                <div class="card-header" onclick="toggleCard(this)">
                  <span class="card-name">{name}</span>
                  {status_badge}{icon_pills}
                  <span class="chevron">▶</span>
                </div>
                <div class="card-body" style="display:none">
                  {placement_line}
                  {ability_block}
                  <div class="images">
                    <div class="img-col">
                      <div class="img-label">{img_label}</div>
                      <img src="{img_src}" alt="{name}" />
                    </div>
                  </div>
                </div>
              </div>"""
                continue

            img_a_src = copy_image_to_report(images_a[r["name"]], output_dir, "a") if r["name"] in images_a else ""
            img_b_src = copy_image_to_report(images_b[r["name"]], output_dir, "b") if r["name"] in images_b else ""

            inner += f"""
              <div class="card {'changed-card' if any_changed else 'same-card'}" data-icons="{' '.join(sorted(all_icons))}" data-abilities="{data_abilities}" data-action="{data_action}">
                <div class="card-header" onclick="toggleCard(this)">
                  <span class="card-name">{name}</span>
                  {badge}
                  <span class="chevron">▶</span>
                </div>
                <div class="card-body" style="display:none">
                  {('<div class="placement-diff">Placement &#x21C4;: <b>' + (r.get("placement_a") or "none") + '</b> → <b>' + (r.get("placement_b") or "none") + '</b></div>') if r.get("placement_changed") else ('<div class="placement-diff" style="opacity:0.5">Placement: <b>' + (r.get("placement_a") or "none") + '</b></div>') if r.get("placement_a") or r.get("placement_b") else ''}
                  {ability_block}
                  <div class="images">
                    <div class="img-col">
                      <div class="img-label">{side_a}</div>
                      <img src="{img_a_src}" alt="{name}" />
                    </div>
                    <div class="img-col">
                      <div class="img-label">{side_b}</div>
                      <img src="{img_b_src}" alt="{name}" />
                    </div>
                  </div>
                </div>
              </div>"""

        # Folder section — auto-open if it has changes
        open_attr = "" if f_changed else ' style="display:none"'
        cards_html += f"""
        <div class="folder-section">
          <div class="folder-header" onclick="toggleFolder(this)">
            <span class="folder-chevron {'open' if f_changed else ''}">▶</span>
            <span class="folder-name">{folder_label}</span>
            <span class="folder-count">{f_total} {card_word}</span>
            {f_badge}
          </div>
          <div class="folder-body"{open_attr}>
            {inner}
          </div>
        </div>"""

    export_rows = [
        {"name": r["name"],
         "ability_changed": r.get("changed", False),
         "flavour_changed": r.get("flavour_changed", False),
         "title_changed": r.get("title_changed", False),
         "art_changed": r.get("art_changed", False),
         "placement_changed": r.get("placement_changed", False),
         "placement_a": r.get("placement_a", ""),
         "placement_b": r.get("placement_b", ""),
         "icons_a": " ".join(sorted(r.get("icons_a", []))),
         "icons_b": " ".join(sorted(r.get("icons_b", []))),
         "negated_a": " ".join(sorted(r.get("negated_a", []))),
         "negated_b": " ".join(sorted(r.get("negated_b", []))),
         "unit_abilities_b": " ".join(sorted(r.get("unit_abilities_b", []))),
         "has_action_b": r.get("has_action_b", False),
         "text_a": r.get("text_a", ""), "text_b": r.get("text_b", "")}
        for r in results
    ]
    # Compact single-line JSON safe for embedding in a <script> tag
    json_payload = json.dumps(export_rows, separators=(",", ":")).replace("</script>", "<\\/script>")

    ability_filter_buttons = ''.join(
        f'<button class="filter-btn" data-filter="ability-{ab}">{UNIT_ABILITY_LABELS.get(ab, ab)}</button>'
        for ab in UNIT_ABILITIES if ab in discovered_abilities
    )
    action_filter_button = '<button class="filter-btn" data-filter="action">ACTION</button>' if has_any_action else ''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Card Diff &mdash; {expansion} {side_a} vs {side_b}</title>
<link rel="stylesheet" href="styles.css"/>
</head>
<body>
<header>
  <div>
    <h1>Card Diff &mdash; {expansion} <em>{side_a}</em> vs <em>{side_b}</em></h1>
    <div class="subtitle">{total_count} cards compared &bull; {deleted_count} deleted &bull; {new_count} new &bull; {changed_count} changed &bull; {same_count} same</div>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-num red">{deleted_count}</div><div class="stat-label">Deleted</div></div>
    <div class="stat"><div class="stat-num red">{new_count}</div><div class="stat-label">New</div></div>
    <div class="stat"><div class="stat-num red">{changed_count}</div><div class="stat-label">Changed</div></div>
    <div class="stat"><div class="stat-num green">{same_count}</div><div class="stat-label">Same</div></div>
  </div>
  <div style="display:flex;gap:0.5rem">
    <button class="export-btn" onclick="exportJson()">Export JSON</button>
    <button class="export-btn" onclick="exportCsv()">Export CSV</button>
  </div>
</header>
<div class="filters">
  <div class="filter-section">
    <span class="filter-section-label">Status</span>
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="changed">Changed</button>
    <button class="filter-btn" data-filter="ability-minor">Minor</button>
    <button class="filter-btn" data-filter="ability-moderate">Moderate</button>
    <button class="filter-btn" data-filter="ability-major">Major</button>
    <button class="filter-btn" data-filter="flavour">Flavour</button>
    <button class="filter-btn" data-filter="title">Title</button>
    <button class="filter-btn" data-filter="art">Art</button>
    <button class="filter-btn" data-filter="placement">Placement &#x21C4;</button>
    <button class="filter-btn" data-filter="new">New</button>
    <button class="filter-btn" data-filter="deleted">Deleted</button>
    <button class="filter-btn" data-filter="same">Same</button>
  </div>
  <div class="filter-section">
    <span class="filter-section-label">Icons</span>
    <button class="filter-btn" data-filter="icon-legendary">Leg</button>
    <button class="filter-btn" data-filter="icon-mecatol">MR</button>
    <button class="filter-btn" data-filter="icon-relic">Relic</button>
    <button class="filter-btn" data-filter="icon-hazardous">Haz</button>
    <button class="filter-btn" data-filter="icon-industrial">Ind</button>
    <button class="filter-btn" data-filter="icon-cultural">Cul</button>
    <button class="filter-btn" data-filter="icon-frontier">Frontier</button>
    <button class="filter-btn" data-filter="icon-tech">Tech</button>
  </div>
  <div class="filter-section">
    <span class="filter-section-label">Abilities</span>
    {action_filter_button}
    {ability_filter_buttons}
  </div>
</div>
<main>
{cards_html}
</main>
<script>
  const data = {json_payload};

  function toggleCard(header) {{
    const body = header.nextElementSibling;
    const chevron = header.querySelector('.chevron');
    if (!body) return;
    const hidden = getComputedStyle(body).display === 'none';
    body.style.display = hidden ? 'block' : 'none';
    chevron.classList.toggle('open', hidden);
  }}

  function toggleFolder(header) {{
    const body = header.nextElementSibling;
    const chevron = header.querySelector('.folder-chevron');
    if (!body) return;
    const hidden = getComputedStyle(body).display === 'none';
    body.style.display = hidden ? 'block' : 'none';
    chevron.classList.toggle('open', hidden);
  }}

  let activeFilter = 'all';

  function cardMatchesFilter(card, filter) {{
    if (filter === 'all') return true;
    if (filter === 'same') return card.classList.contains('same-card');
    if (filter === 'changed') return card.classList.contains('changed-card');
    if (filter === 'new') return !!card.querySelector('.new-badge');
    if (filter === 'deleted') return !!card.querySelector('.deleted-badge');
    if (filter === 'ability-minor' || filter === 'ability-moderate' || filter === 'ability-major')
      return !!card.querySelector(`.badge.${{filter}}`);
    if (filter === 'action') return card.dataset.action === 'true';
    if (filter.startsWith('ability-')) {{
      const abilities = (card.dataset.abilities || '').split('|').filter(Boolean);
      const abilityName = filter.replace('ability-', '');
      return abilities.includes(abilityName);
    }}
    if (filter.startsWith('icon-')) {{
      const icons = (card.dataset.icons || '').split(' ');
      const iconName = filter.replace('icon-', '');
      return icons.includes(iconName);
    }}
    return !!card.querySelector(`.badge.${{filter}}`);
  }}

  function applyFilter(filter) {{
    activeFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
    document.querySelectorAll('.folder-section').forEach(section => {{
      const body = section.querySelector('.folder-body');
      const header = section.querySelector('.folder-header');
      const chevron = header.querySelector('.folder-chevron');
      const cards = body.querySelectorAll('.card');
      let visible = 0;
      cards.forEach(card => {{
        const show = cardMatchesFilter(card, filter);
        card.classList.toggle('hidden', !show);
        if (show) visible++;
      }});
      section.classList.toggle('hidden', visible === 0);
      if (visible > 0) {{
        body.style.display = 'block';
        chevron.classList.add('open');
      }}
    }});
  }}

  document.querySelectorAll('.filter-btn').forEach(btn => {{
    btn.addEventListener('click', () => applyFilter(btn.dataset.filter));
  }});

  function exportJson() {{
    const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'card_diff.json';
    a.click();
    URL.revokeObjectURL(url);
  }}

  function exportCsv() {{
    const header = ['name', 'ability_changed', 'flavour_changed', 'title_changed', 'art_changed', 'placement_changed', 'placement_a', 'placement_b', 'icons_a', 'icons_b', 'negated_a', 'negated_b', 'unit_abilities_b', 'has_action_b', 'text_a', 'text_b'];
    const escape = v => '"' + String(v).replace(/"/g, '""') + '"';
    const rows = [header.join(','), ...data.map(r => header.map(k => escape(r[k])).join(','))];
    const blob = new Blob([rows.join('\\n')], {{type: 'text/csv'}});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'card_diff.csv';
    a.click();
    URL.revokeObjectURL(url);
  }}
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Diff text extracted from game card images.")
    parser.add_argument("folder_a", type=Path, help="First image folder")
    parser.add_argument("folder_b", type=Path, help="Second image folder")
    parser.add_argument("--output", type=Path, default=None, help="Output report directory (default: exports/reports/<folder_a>_vs_<folder_b>)")
    parser.add_argument("--load-json", type=Path, default=None, help="Skip OCR; load prior results JSON and re-render report")
    parser.add_argument("--no-gpu", dest="gpu", action="store_false", help="Disable GPU/MPS acceleration")
    parser.set_defaults(gpu=True)
    parser.add_argument("--lang", nargs="+", default=["en"], help="EasyOCR language codes (default: en)")
    args = parser.parse_args()

    if not args.folder_a.is_dir():
        print(f"Error: {args.folder_a} is not a directory", file=sys.stderr)
        sys.exit(1)
    if not args.folder_b.is_dir():
        print(f"Error: {args.folder_b} is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        args.output = Path(__file__).parent.parent / "exports" / "reports" / f"{args.folder_a.name}_vs_{args.folder_b.name}"
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.output.is_dir():
        print(f"Error: {args.output} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning folders...")
    images_a = find_images(args.folder_a)
    images_b = find_images(args.folder_b)

    if args.load_json:
        if not args.load_json.exists():
            print(f"Error: {args.load_json} not found", file=sys.stderr)
            sys.exit(1)
        print(f"Loading prior results from {args.load_json}...")
        loaded = json.loads(args.load_json.read_text(encoding="utf-8"))
        results = []
        for r in loaded:
            sr = dict(r)
            for k in ("icons_a", "icons_b", "negated_a", "negated_b"):
                sr[k] = frozenset(sr.get(k, []))
            sr["unit_abilities_b"] = set(sr.get("unit_abilities_b", []))
            sr["has_action_b"] = bool(sr.get("has_action_b", False))
            # Re-apply current overrides so JSON re-renders pick up edits to overrides.json
            sr["unit_abilities_b"], sr["has_action_b"] = _apply_ability_suppression(
                sr["name"], sr["unit_abilities_b"], sr["has_action_b"]
            )
            results.append(sr)
        print(f"  {len(results)} cards loaded")
        print(f"\nBuilding report...")
        (args.output / "images").mkdir(parents=True, exist_ok=True)
        css_path = args.output / "styles.css"
        css_path.write_text(REPORT_CSS.strip(), encoding="utf-8")
        print(f"  styles.css written")
        html = build_html(results, args.folder_a, args.folder_b, images_a, images_b, args.output)
        html_path = args.output / "index.html"
        html_path.write_text(html, encoding="utf-8")
        changed = sum(1 for r in results if r["changed"])
        print(f"Done. {changed}/{len(results)} cards changed.")
        print(f"Report: {html_path.resolve()}")
        return

    all_names = sorted(set(images_a) | set(images_b))
    print(f"  {args.folder_a.name}: {len(images_a)} images")
    print(f"  {args.folder_b.name}: {len(images_b)} images")
    print(f"  {len(all_names)} unique filenames total")

    if args.gpu and torch.backends.mps.is_available():
        device_label = "MPS (Apple Silicon)"
    elif args.gpu and torch.cuda.is_available():
        device_label = "CUDA"
    else:
        device_label = "CPU"
    print(f"\nLoading EasyOCR (lang={args.lang}, device={device_label})...")
    reader = easyocr.Reader(args.lang, gpu=args.gpu)

    results = []
    for i, name in enumerate(all_names, 1):
        print(f"[{i}/{len(all_names)}] {name}", end="", flush=True)

        if name not in images_a:
            print(" — missing in A")
            icons_b, neg_b = detect_placement_icons(images_b[name])
            ab_results_b = get_ability_results(reader, images_b[name])
            abilities_b, action_b = detect_unit_abilities(ab_results_b)
            abilities_b, action_b = _apply_ability_suppression(name, abilities_b, action_b)
            results.append({"name": name, "changed": True, "missing": "a", "text_a": "", "text_b": "",
                            "icons_a": frozenset(), "icons_b": icons_b,
                            "negated_a": frozenset(), "negated_b": neg_b,
                            "placement_a": "", "placement_b": format_placement(icons_b, neg_b),
                            "unit_abilities_b": abilities_b, "has_action_b": action_b})
            continue
        if name not in images_b:
            print(" — missing in B")
            icons_a, neg_a = detect_placement_icons(images_a[name])
            results.append({"name": name, "changed": True, "missing": "b", "text_a": "", "text_b": "",
                            "icons_a": icons_a, "icons_b": frozenset(),
                            "negated_a": neg_a, "negated_b": frozenset(),
                            "placement_a": format_placement(icons_a, neg_a), "placement_b": "",
                            "unit_abilities_b": set(), "has_action_b": False})
            continue

        # Open both images once; all checks below reuse these handles
        img_a, img_b = _open_pair(images_a[name], images_b[name])

        # Per-region pixel diffs
        apct   = ability_pixel_diff(img_a, img_b)
        tpct   = title_pixel_diff(img_a, img_b)
        artpct = art_pixel_diff(img_a, img_b)
        p_changed, p_label_a, p_label_b, p_icons_a, p_icons_b, p_neg_a, p_neg_b = placement_changed_on(img_a, img_b, images_a[name], images_b[name])

        # Unit abilities / action detection on the new (B) version — always run
        ab_results_b = get_ability_results(reader, images_b[name])
        abilities_b, action_b = detect_unit_abilities(ab_results_b)
        abilities_b, action_b = _apply_ability_suppression(name, abilities_b, action_b)

        # Ability OCR — only if pixel diff is significant
        if apct >= TEXT_CHANGE_PCT:
            text_a = extract_text(reader, images_a[name])
            text_b = extract_text(reader, images_b[name])
            diff = diff_texts(name, text_a, text_b)
        else:
            diff = {"name": name, "changed": False, "text_a": "", "text_b": ""}

        # Flavour OCR — read from cache (populated during extract_text if run, else empty)
        fa = flavour_text(images_a[name])
        fb = flavour_text(images_b[name])
        flavour_changed = bool(apct >= TEXT_CHANGE_PCT and not bags_equal(fa, fb) and (fa or fb))

        diff["title_changed"]   = bool(tpct >= TITLE_CHANGE_PCT)
        diff["flavour_changed"] = flavour_changed
        diff["art_changed"]     = bool(artpct >= ART_CHANGE_PCT)
        diff["placement_changed"] = p_changed
        diff["placement_a"]     = p_label_a
        diff["placement_b"]     = p_label_b
        diff["icons_a"]         = p_icons_a
        diff["icons_b"]         = p_icons_b
        diff["negated_a"]       = p_neg_a
        diff["negated_b"]       = p_neg_b
        diff["unit_abilities_b"] = abilities_b
        diff["has_action_b"]    = action_b
        # Ability severity based on word-level similarity ratio
        ratio = diff.get("ability_ratio", 1.0)
        if diff["changed"]:
            if ratio >= 0.75:   diff["ability_severity"] = "minor"
            elif ratio >= 0.50: diff["ability_severity"] = "moderate"
            else:               diff["ability_severity"] = "major"
        else:
            diff["ability_severity"] = None
        # legacy field — any change
        diff["visual_changed"]  = diff["art_changed"] or diff["placement_changed"]
        results.append(diff)
        parts = []
        if diff["changed"]:
            parts.append(diff["ability_severity"])
        if flavour_changed:           parts.append("flavour")
        if diff["title_changed"]:     parts.append("title")
        if diff["art_changed"]:       parts.append("art")
        if diff["placement_changed"]: parts.append("placement")
        status = "CHANGED (" + ", ".join(parts) + ")" if parts else "same"
        print(f" — {status}")

    print(f"\nBuilding report...")
    (args.output / "images").mkdir(parents=True, exist_ok=True)
    css_path = args.output / "styles.css"
    css_path.write_text(REPORT_CSS.strip(), encoding="utf-8")
    print(f"  styles.css written")
    html = build_html(results, args.folder_a, args.folder_b, images_a, images_b, args.output)
    html_path = args.output / "index.html"
    html_path.write_text(html, encoding="utf-8")

    # Save full results JSON next to the HTML report for fast re-render
    results_json_path = args.output / "results.json"
    serializable_results = []
    for r in results:
        sr = dict(r)
        for k in ("icons_a", "icons_b", "negated_a", "negated_b"):
            sr[k] = sorted(sr.get(k, []))
        sr["unit_abilities_b"] = sorted(sr.get("unit_abilities_b", []))
        serializable_results.append(sr)
    results_json_path.write_text(json.dumps(serializable_results, indent=2), encoding="utf-8")
    print(f"Saved results JSON: {results_json_path}")

    changed = sum(1 for r in results if r["changed"])
    print(f"Done. {changed}/{len(results)} cards changed.")
    print(f"Report: {html_path.resolve()}")


if __name__ == "__main__":
    main()
