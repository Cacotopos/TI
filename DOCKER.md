# TI — Docker Distribution Guide

This document describes how to run the project in Docker on another computer. Point an agent at this file.

## Files required to run in Docker

These files from the repository are required to build and run the Docker images:

- `Dockerfile` — lean editor + static site generator image
- `Dockerfile.ocr` — full OCR image for `card_diff.py`
- `docker-compose.yml` — editor service definition
- `requirements.editor.txt` — lean Python dependencies
- `requirements.txt` — full Python dependencies (used by `Dockerfile.ocr`)
- `expansions/` — editor, generator, templates, and saved expansion configs
- `card_diff/` — OCR card comparison tool (only needed for `Dockerfile.ocr`)
- `.env` (optional) — S3/AWS environment variables for deployment
- `~/.aws/` credentials (optional) — for S3 sync

You do **not** need to send:

- `.venv/` or `venv/`
- `expansions/sites/` (generated output)
- `exports/reports/`
- `.git/` (unless building from a clone)

## How the container points to local project files

`docker-compose.yml` bind-mounts the entire project directory into the container at `/app`:

```yaml
volumes:
  - .:/app
```

This means the container uses the **local files on the other dev's machine**, not just the code baked into the image. The other dev can:

- Edit code and have Flask reload it
- View and modify `expansions/editor/data/` configs directly on their host
- See generated sites in `expansions/sites/` on their host

Source image assets are also mounted separately. The paths in `expansions/editor/data/<expansion>/config.json` are absolute host paths, so the same absolute path is mounted inside the container.

## Source image assets

Expansion configs in `expansions/editor/data/<expansion>/config.json` store the absolute path to the source card images on the host. The Docker container must have that same path mounted, or generation will fail with a missing-source warning.

Either:

1. Send the source images to the other computer and place them at the same absolute path, or
2. Edit `config.json` to use a relative path inside the container and mount a folder to `/app/source-images`.

## Quick start for another computer

```bash
# 1. Get the project
git clone https://github.com/Cacotopos/TI.git
cd TI

# 2. (Optional) copy the source image assets to the same absolute host path
#    used in the expansion config.json. For example:
#    /Users/me/Documents/.../Monuments/Printable Cards/v3.1

# 3. Start the editor
docker compose up --build -d editor

# 4. Open the editor
open http://localhost:3030
```

## Generate a site in Docker

```bash
export SOURCE_IMAGES="/absolute/path/to/Printable Cards/v3.1"
docker compose up -d editor

docker compose exec editor python -m expansions.generator.site \
  expansions/editor/data/monuments/config.json \
  --output expansions/sites/monuments
```

The generated site is written to `expansions/sites/monuments/` on the host (because `docker-compose.yml` mounts `.:/app`).

## OCR / card_diff image

Build the heavier image only when you need OCR-based card comparison:

```bash
docker build -f Dockerfile.ocr -t ti-ocr .
docker run --rm -v "$PWD:/app" ti-ocr \
  card_diff/card_diff.py v3/Monuments v3.1/Monuments \
  --output exports/reports/monuments_v3_v3.1
```

## Common commands

```bash
# Rebuild after pulling code changes
docker compose up --build -d editor

# View logs
docker compose logs -f editor

# Stop everything
docker compose down

# Remove volumes (deletes saved editor data and generated sites)
docker compose down -v

# Inspect the generated site inside the container
docker compose exec editor ls -la expansions/sites/monuments
```

## Notes

- The lean editor image uses `requirements.editor.txt` and does **not** include PyTorch or EasyOCR. It is intended for the editor and site generator only.
- Generated sites and saved expansion configs are stored in Docker volumes, so they persist across restarts unless you run `docker compose down -v`.
- If you are sending the project without git, include at least the files listed in the "Files required" section above.
