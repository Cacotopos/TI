#!/usr/bin/env python3
"""Local web editor for collecting expansion data."""

import json
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Expansion Editor</title></head>
    <body>
      <h1>Expansion Editor</h1>
      <p>POST /api/save with JSON body to save a configuration.</p>
      <p>GET /api/load?id=monuments to load a configuration.</p>
    </body>
    </html>
    """


@app.route("/api/save", methods=["POST"])
def save():
    data = request.get_json(force=True)
    expansion_id = data.get("id", "unknown")
    out_dir = DATA_DIR / expansion_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    overview = data.get("overview", "")
    (out_dir / "expansion-overview.md").write_text(overview, encoding="utf-8")
    return jsonify({"ok": True, "id": expansion_id, "path": str(out_dir)})


@app.route("/api/load")
def load():
    expansion_id = request.args.get("id", "unknown")
    config_path = DATA_DIR / expansion_id / "config.json"
    if not config_path.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(config_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
