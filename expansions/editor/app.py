#!/usr/bin/env python3
"""Local web editor for collecting expansion data.

Reads S3 credentials from the project .env file and can run aws s3 sync to
deploy a generated expansion site.
"""

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

app = Flask(__name__)

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load .env from the existing s3-upload location or project root.
for env_path in (ROOT / "exports" / "s3-upload" / ".env", ROOT / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

S3_BUCKET = os.getenv("S3_AWS_BUCKET_NAME", "ti4-expansions")
S3_REGION = os.getenv("S3_AWS_REGION", "ap-southeast-2")
AWS_PROFILE = os.getenv("S3_AWS_PROFILE", "tom-local-s3")


def _load_config(expansion_id: str) -> dict:
    config_path = DATA_DIR / expansion_id / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _save_config(expansion_id: str, data: dict) -> Path:
    out_dir = DATA_DIR / expansion_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    overview = data.get("overview", "")
    (out_dir / "expansion-overview.md").write_text(overview, encoding="utf-8")
    return out_dir


@app.route("/")
def index():
    return render_template("editor.html")


@app.route("/api/config/<expansion_id>")
def get_config(expansion_id: str):
    return jsonify(_load_config(expansion_id))


@app.route("/api/config/<expansion_id>", methods=["POST"])
def post_config(expansion_id: str):
    data = request.get_json(force=True)
    data["id"] = expansion_id
    _save_config(expansion_id, data)
    return jsonify({"ok": True, "id": expansion_id})


@app.route("/api/generate/<expansion_id>", methods=["POST"])
def generate(expansion_id: str):
    """Run the static site generator for this expansion."""
    config_path = DATA_DIR / expansion_id / "config.json"
    if not config_path.exists():
        return jsonify({"error": "config not found"}), 404

    output_dir = ROOT / "expansions" / "sites" / expansion_id
    output_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["python3", "-m", "expansions.generator.site", str(config_path), "--output", str(output_dir)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return jsonify({
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output_dir": str(output_dir),
    })


@app.route("/api/deploy/<expansion_id>", methods=["POST"])
def deploy(expansion_id: str):
    """Deploy the generated site to S3 using the configured bucket and profile."""
    site_dir = ROOT / "expansions" / "sites" / expansion_id
    if not site_dir.exists():
        return jsonify({"error": "site not generated"}), 404

    s3_path = f"s3://{S3_BUCKET}/{expansion_id}"
    cmd = [
        "aws", "s3", "sync", str(site_dir), s3_path,
        "--profile", AWS_PROFILE,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return jsonify({
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "url": f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{expansion_id}/index.html",
    })


@app.route("/api/image/<expansion_id>/<path:filename>")
def serve_image(expansion_id: str, filename: str):
    """Serve a source image file for preview."""
    config = _load_config(expansion_id)
    images_path = config.get("source", {}).get("images", "")
    if not images_path:
        return "", 404
    images_src = ROOT / images_path
    if not images_src.exists():
        return "", 404
    return send_from_directory(images_src, filename)


@app.route("/api/images/<expansion_id>")
def list_images(expansion_id: str):
    config = _load_config(expansion_id)
    images_path = config.get("source", {}).get("images", "")
    if not images_path:
        return jsonify([])
    images_src = ROOT / images_path
    if not images_src.exists():
        return jsonify([])
    images = []
    for p in sorted(images_src.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
            rel = p.relative_to(images_src)
            try:
                with Image.open(p) as img:
                    width, height = img.size
            except Exception:
                width, height = 0, 0
            images.append({
                "id": p.stem,
                "filename": p.name,
                "path": str(rel).replace("\\", "/"),
                "folder": str(rel.parent) if rel.parent != Path(".") else "",
                "width": width,
                "height": height,
            })
    return jsonify(images)


@app.route("/api/inspect/<expansion_id>", methods=["POST"])
def inspect(expansion_id: str):
    """Scan the source image folder and build an assets map from detected images.

    Preserves existing asset config where present, and marks newly detected
    assets as not configured.
    """
    config = _load_config(expansion_id)
    images_path = config.get("source", {}).get("images", "")
    if not images_path:
        return jsonify({"error": "no image folder configured"}), 400
    images_src = ROOT / images_path
    if not images_src.exists():
        return jsonify({"error": f"image folder not found: {images_src}"}), 400

    existing_assets = config.get("assets", {})
    assets = {}
    folders = set()

    for p in sorted(images_src.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
            rel = p.relative_to(images_src)
            path = str(rel).replace("\\", "/")
            folder = str(rel.parent) if rel.parent != Path(".") else ""
            folders.add(folder.split("/")[0] if folder else "General")

            if path in existing_assets:
                assets[path] = existing_assets[path]
                if "type" not in assets[path]:
                    assets[path]["type"] = "other component"
                if "faction" not in assets[path]:
                    assets[path]["faction"] = ""
            else:
                assets[path] = {
                    "id": p.stem,
                    "path": path,
                    "filename": p.name,
                    "folder": folder,
                    "configured": False,
                    "hidden": False,
                    "isCard": True,
                    "title": p.stem,
                    "description": "",
                    "faq": [],
                    "section": "cards",
                    "group": folder,
                    "back": "",
                    "type": "other component",
                    "faction": "",
                }

    # Remove assets whose source files no longer exist (e.g. renamed files).
    detected_paths = set(assets.keys())
    for path in list(existing_assets.keys()):
        if path not in detected_paths:
            assets.pop(path, None)

    # Suggest sections from top-level folders.
    suggested = []
    for f in sorted(folders):
        section_id = f.lower().replace(" ", "-")
        suggested.append({"id": section_id, "title": f, "type": "cards"})

    return jsonify({"assets": assets, "suggested_sections": suggested})


@app.route("/api/expansions")
def list_expansions():
    """Return expansion IDs from source folder subdirectories."""
    ids = set()
    source_dir = ROOT / "expansions" / "source"
    if source_dir.exists():
        for p in source_dir.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                ids.add(p.name)
    return jsonify(sorted(ids))


@app.route("/api/settings")
def settings():
    return jsonify({
        "bucket": S3_BUCKET,
        "region": S3_REGION,
        "profile": AWS_PROFILE,
    })


if __name__ == "__main__":
    app.run(debug=True, port=3030)
