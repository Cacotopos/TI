#!/usr/bin/env python3
"""Local web editor for collecting expansion data.

Reads S3 credentials from the project .env file and can deploy a generated
expansion site to S3.
"""

import hashlib
import io
import json
import mimetypes
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, ProfileNotFound
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from PIL import Image

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
S3_CLEANUP_GRACE_SECONDS = int(os.getenv("S3_CLEANUP_GRACE_SECONDS", "300"))


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _aws_profile_configured(profile: str) -> bool:
    """Return True if the AWS CLI is installed and the named profile exists."""
    if not shutil.which("aws"):
        return False
    try:
        result = subprocess.run(
            ["aws", "configure", "list-profiles"],
            capture_output=True,
            text=True,
            check=True,
        )
        profiles = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        return profile in profiles
    except Exception:
        return False


GIT_COMMIT = _git_commit()


def _migrate_config(data: dict) -> dict:
    """Migrate legacy isCard boolean to component string."""
    for asset in data.get("assets", {}).values():
        if "component" not in asset:
            asset["component"] = "us-mini" if asset.get("isCard", True) else "other"
        if "isCard" in asset:
            del asset["isCard"]
    return data


# Landscape aspect ratios for known physical card components.
_COMPONENT_RATIOS = {
    "us-mini": 1.470,
    "tarot": 1.668,
    "poker": 1.381,
}
_COMPONENT_RATIO_TOLERANCE = 0.06


def _detect_component_from_dimensions(width: int, height: int) -> str:
    """Guess the physical component from image aspect ratio."""
    if width <= 0 or height <= 0:
        return "us-mini"
    ratio = max(width, height) / min(width, height)
    best = "other"
    best_diff = float("inf")
    for component, expected in _COMPONENT_RATIOS.items():
        diff = abs(ratio - expected)
        if diff < best_diff and diff < _COMPONENT_RATIO_TOLERANCE:
            best_diff = diff
            best = component
    return best


def _load_config(expansion_id: str) -> dict:
    config_path = DATA_DIR / expansion_id / "config.json"
    if not config_path.exists():
        return {}
    return _migrate_config(json.loads(config_path.read_text(encoding="utf-8")))


def _save_config(expansion_id: str, data: dict) -> Path:
    out_dir = DATA_DIR / expansion_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    overview = data.get("overview", "")
    (out_dir / "expansion-overview.md").write_text(overview, encoding="utf-8")
    return out_dir


@app.route("/")
def index():
    return render_template("editor.html", git_commit=GIT_COMMIT)


@app.route("/api/version")
def version():
    return jsonify({"commit": GIT_COMMIT})


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
        [sys.executable, "-m", "expansions.generator.site", str(config_path), "--output", str(output_dir)],
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


def _s3_client():
    """Return an S3 client using the configured profile, falling back to default."""
    try:
        session = boto3.Session(profile_name=AWS_PROFILE)
    except ProfileNotFound:
        session = boto3.Session()
    return session.client("s3", region_name=S3_REGION)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


@app.route("/api/deploy/<expansion_id>", methods=["POST"])
def deploy(expansion_id: str):
    """Deploy the generated site to S3.

    Only files whose content (MD5) has changed are uploaded. Assets receive
    long immutable cache headers because their URLs are content-hashed; HTML
    and data.json receive short no-cache headers so the latest pages are
    always fetched.

    Each deploy writes a manifest to S3 (monuments/deploys/<commit>-<ts>.json)
    and a mutable "latest" copy. After uploading, stale objects from older
    deploys are removed after a short grace period.
    """
    site_dir = ROOT / "expansions" / "sites" / expansion_id
    if not site_dir.exists():
        return jsonify({"error": "site not generated"}), 404

    config = _load_config(expansion_id)
    deploy_path = config.get("s3_path") or expansion_id
    prefix = f"{deploy_path}/"
    deploys_prefix = f"{prefix}deploys/"
    deploy_start = datetime.now(timezone.utc)
    grace_cutoff = deploy_start - timedelta(seconds=S3_CLEANUP_GRACE_SECONDS)

    try:
        s3 = _s3_client()
    except Exception as e:
        return jsonify({"ok": False, "stdout": "", "stderr": str(e)}), 500

    # List existing S3 objects and their ETags (content MD5s).
    existing: dict[str, str] = {}
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                existing[obj["Key"]] = obj["ETag"].strip('"')
    except ClientError as e:
        return jsonify({"ok": False, "stdout": "", "stderr": str(e)}), 500

    uploaded = 0
    uploaded_files: list[str] = []
    skipped = 0
    errors: list[str] = []
    manifest_assets: list[dict] = []
    current_keys: set[str] = set()

    for local_path in sorted(site_dir.rglob("*")):
        if not local_path.is_file():
            continue
        # Ignore macOS .DS_Store and other dot files.
        if any(part.startswith(".") for part in local_path.relative_to(site_dir).parts):
            continue
        rel = str(local_path.relative_to(site_dir)).replace("\\", "/")
        s3_key = f"{prefix}{rel}"
        md5 = _md5(local_path)
        size = local_path.stat().st_size
        content_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

        current_keys.add(s3_key)
        manifest_assets.append({
            "key": rel,
            "md5": md5,
            "size": size,
            "content_type": content_type,
        })

        if existing.get(s3_key) == md5:
            skipped += 1
            continue

        cache_control = (
            "public, max-age=31536000, immutable"
            if rel.startswith("assets/")
            else "public, max-age=0, must-revalidate"
        )
        extra = {"CacheControl": cache_control, "ContentType": content_type}
        try:
            s3.upload_file(str(local_path), S3_BUCKET, s3_key, ExtraArgs=extra)
            uploaded += 1
            uploaded_files.append(rel)
        except ClientError as e:
            errors.append(f"{rel}: {e}")

    if errors:
        return jsonify({
            "ok": False,
            "stdout": f"Uploaded {uploaded} files, skipped {skipped} unchanged files.",
            "stderr": "\n".join(errors),
            "url": f"http://{S3_BUCKET}.s3-website-{S3_REGION}.amazonaws.com/{deploy_path}/index.html",
        }), 500

    # Build and upload a per-deploy manifest and the mutable "latest" copy.
    git_commit = _git_commit()
    timestamp = deploy_start.isoformat().replace(":", "-")
    manifest_name = f"{git_commit}-{timestamp}.json"
    manifest = {
        "git_commit": git_commit,
        "timestamp": deploy_start.isoformat(),
        "expansion": expansion_id,
        "prefix": deploy_path,
        "count": len(manifest_assets),
        "total_bytes": sum(a["size"] for a in manifest_assets),
        "assets": sorted(manifest_assets, key=lambda a: a["key"]),
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")

    manifest_key_historical = f"{deploys_prefix}{manifest_name}"
    manifest_key_latest = f"{deploys_prefix}latest.json"

    # Compare with the previous manifest for a changeset report before we
    # overwrite the mutable "latest" copy.
    previous_manifest: dict | None = None
    try:
        prev_obj = s3.get_object(Bucket=S3_BUCKET, Key=manifest_key_latest)
        previous_manifest = json.loads(prev_obj["Body"].read().decode("utf-8"))
    except ClientError:
        pass

    try:
        for key in (manifest_key_historical, manifest_key_latest):
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=manifest_bytes,
                ContentType="application/json",
                CacheControl="public, max-age=0, must-revalidate",
            )
        current_keys.add(manifest_key_latest)
    except ClientError as e:
        return jsonify({
            "ok": False,
            "stdout": f"Uploaded {uploaded} files, skipped {skipped} unchanged files.",
            "stderr": f"Failed to upload manifest: {e}",
            "url": f"http://{S3_BUCKET}.s3-website-{S3_REGION}.amazonaws.com/{deploy_path}/index.html",
        }), 500

    current_by_key = {a["key"]: a for a in manifest_assets}
    previous_by_key: dict[str, dict] = {}
    if previous_manifest:
        previous_by_key = {a["key"]: a for a in previous_manifest.get("assets", [])}

    added: list[dict] = [current_by_key[k] for k in sorted(set(current_by_key) - set(previous_by_key))]
    removed: list[dict] = [previous_by_key[k] for k in sorted(set(previous_by_key) - set(current_by_key))]
    changed: list[dict] = []
    unchanged = 0
    for key in sorted(set(current_by_key) & set(previous_by_key)):
        left = previous_by_key[key]
        right = current_by_key[key]
        if left["md5"] != right["md5"]:
            changed.append({
                "key": key,
                "left_md5": left["md5"],
                "right_md5": right["md5"],
                "left_size": left["size"],
                "right_size": right["size"],
            })
        else:
            unchanged += 1

    # Clean up stale S3 objects that are not in the current manifest and are
    # older than the grace period. Manifests under deploys/ are never deleted.
    deleted = 0
    deleted_bytes = 0
    cleanup_errors: list[str] = []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key in current_keys or key.startswith(deploys_prefix):
                    continue
                last_modified = obj["LastModified"]
                if last_modified < grace_cutoff:
                    s3.delete_object(Bucket=S3_BUCKET, Key=key)
                    deleted += 1
                    deleted_bytes += obj["Size"]
    except ClientError as e:
        cleanup_errors.append(f"Cleanup failed: {e}")

    stdout_lines = [f"Uploaded {uploaded} files, skipped {skipped} unchanged files."]
    if uploaded_files:
        stdout_lines.append("Uploaded:")
        stdout_lines.extend(f"  {f}" for f in uploaded_files)
    stdout_lines.append(f"Manifest: {manifest_key_historical}")
    stdout_lines.append("Changeset:")
    stdout_lines.append(f"  added: {len(added)}")
    stdout_lines.append(f"  removed: {len(removed)}")
    stdout_lines.append(f"  changed: {len(changed)}")
    stdout_lines.append(f"  unchanged: {unchanged}")
    if deleted:
        stdout_lines.append(f"Cleanup: deleted {deleted} stale objects ({deleted_bytes / 1024 / 1024:.1f} MB)")
    if cleanup_errors:
        stdout_lines.extend(f"  {e}" for e in cleanup_errors)
    stdout = "\n".join(stdout_lines)

    return jsonify({
        "ok": True,
        "stdout": stdout,
        "stderr": "\n".join(cleanup_errors),
        "url": f"http://{S3_BUCKET}.s3-website-{S3_REGION}.amazonaws.com/{deploy_path}/index.html",
        "manifest_url": f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{manifest_key_historical}",
        "changeset": {
            "added": [a["key"] for a in added],
            "removed": [a["key"] for a in removed],
            "changed": changed,
            "unchanged": unchanged,
            "deleted": deleted,
            "deleted_bytes": deleted_bytes,
        },
    })


@app.route("/api/image/<expansion_id>/<path:filename>")
def serve_image(expansion_id: str, filename: str):
    """Serve a source image file for preview, stripping EXIF orientation so the
    preview matches the generated site output.
    """
    config = _load_config(expansion_id)
    images_path = config.get("source", {}).get("images", "")
    if not images_path:
        return "", 404
    images_src = ROOT / images_path
    if not images_src.exists():
        return "", 404
    src = images_src / filename
    if not src.exists():
        return "", 404
    try:
        with Image.open(src) as img:
            fmt = img.format or "JPEG"
            if fmt.upper() in ("JPEG", "JPG"):
                img = img.convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=92)
                buffer.seek(0)
                return send_file(buffer, mimetype="image/jpeg")
            if "exif" in img.info:
                img.info.pop("exif")
            buffer = io.BytesIO()
            img.save(buffer, format=fmt)
            buffer.seek(0)
            mimetype = Image.MIME.get(fmt, "image/png")
            return send_file(buffer, mimetype=mimetype)
    except Exception:
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

            width, height = 0, 0
            try:
                with Image.open(p) as img:
                    width, height = img.size
            except Exception:
                pass
            if height == width:
                orientation = "square"
            elif height > width:
                orientation = "portrait"
            else:
                orientation = "landscape"

            if path in existing_assets:
                assets[path] = existing_assets[path]
                if "type" not in assets[path]:
                    assets[path]["type"] = "Other Component"
                if "faction" not in assets[path]:
                    assets[path]["faction"] = ""
                if "orientation" not in assets[path]:
                    assets[path]["orientation"] = orientation
                if "component" not in assets[path]:
                    assets[path]["component"] = _detect_component_from_dimensions(width, height)
            else:
                assets[path] = {
                    "id": p.stem,
                    "path": path,
                    "filename": p.name,
                    "folder": folder,
                    "configured": False,
                    "hidden": False,
                    "component": _detect_component_from_dimensions(width, height),
                    "title": p.stem,
                    "description": "",
                    "faq": [],
                    "section": "cards",
                    "group": folder,
                    "back": "",
                    "type": "Other Component",
                    "faction": "",
                    "orientation": orientation,
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
    """Return expansion IDs from saved config files."""
    ids = set()
    if DATA_DIR.exists():
        for p in DATA_DIR.iterdir():
            if p.is_dir() and not p.name.startswith(".") and (p / "config.json").exists():
                ids.add(p.name)
    return jsonify(sorted(ids))


@app.route("/api/source-folders")
def list_source_folders():
    """Return relative paths of folders that contain image files, anywhere under the project root."""
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    folders = set()
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in image_exts:
            rel = p.relative_to(ROOT).parent
            path = str(rel).replace("\\", "/")
            if path and not path.startswith("."):
                folders.add(path)
    return jsonify(sorted(folders))


@app.route("/api/pick-folder", methods=["POST"])
def pick_folder():
    """Open a native OS folder picker and return the selected absolute path."""
    system = platform.system()
    if system == "Darwin":
        script = 'POSIX path of (choose folder with prompt "Select source image folder")'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"error": "No folder selected"}), 400
        path = result.stdout.strip().rstrip("/")
        return jsonify({"path": path})
    if system == "Linux":
        try:
            result = subprocess.run(
                ["zenity", "--file-selection", "--directory"],
                capture_output=True, text=True, check=True
            )
            return jsonify({"path": result.stdout.strip().rstrip("/")})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    if system == "Windows":
        try:
            script = 'Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = "Select source image folder"; $f.ShowDialog() | Out-Null; $f.SelectedPath'
            result = subprocess.run(["powershell", "-Command", script], capture_output=True, text=True, check=True)
            return jsonify({"path": result.stdout.strip().rstrip("/")})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    return jsonify({"error": f"Folder picker not supported on {system}"}), 400


@app.route("/api/settings")
def settings():
    return jsonify({
        "bucket": S3_BUCKET,
        "region": S3_REGION,
        "profile": AWS_PROFILE,
    })


@app.route("/api/deploy-status")
def deploy_status():
    """Return whether the configured AWS profile is available for S3 deploy."""
    return jsonify({
        "can_deploy": _aws_profile_configured(AWS_PROFILE),
        "profile": AWS_PROFILE,
        "bucket": S3_BUCKET,
        "region": S3_REGION,
    })


if __name__ == "__main__":
    port = int(os.getenv("EDITOR_PORT", "3030"))
    host = os.getenv("EDITOR_HOST", "127.0.0.1")
    debug = os.getenv("EDITOR_DEBUG", "true").lower() in ("1", "true", "yes")
    app.run(debug=debug, host=host, port=port)
