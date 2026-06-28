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
from flask import Flask, jsonify, render_template, request

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

    generator = ROOT / "expansions" / "generator" / "site.py"
    result = subprocess.run(
        ["python3", str(generator), str(config_path), "--output", str(output_dir)],
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


@app.route("/api/settings")
def settings():
    return jsonify({
        "bucket": S3_BUCKET,
        "region": S3_REGION,
        "profile": AWS_PROFILE,
    })


if __name__ == "__main__":
    app.run(debug=True, port=3030)
