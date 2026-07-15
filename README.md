# TI Card Diff

Compares Twilight Imperium card images across two versions, extracts ability text via OCR (EasyOCR), detects placement icons and unit abilities, and produces self-contained static report sites ready for S3 or any static host.

## Structure

```
TI/
├── card_diff/           # Core comparison engine
│   ├── card_diff.py     # Main script
│   └── overrides.json   # Manual detection overrides
├── exports/
│   ├── reports/         # Generated static report sites
│   └── s3-upload/       # S3 deployment scripts (to be added)
├── Icons/               # Icon template images
├── requirements.txt
└── README.md
```

Source card images (e.g. `v3/`, `v3.1/`) are not included in the repository. Pass the appropriate folders to `card_diff.py` when running locally.

## Setup

### Local Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Docker

A lean `Dockerfile` and `docker-compose.yml` are included for the editor and
static site generator. A separate `Dockerfile.ocr` contains the full PyTorch/
EasyOCR stack for `card_diff.py`.

```bash
cd /Users/kangarootime/Source/RiderProjects/TI
docker compose up --build -d editor
open http://localhost:3030
```

See `expansions/README.md` for full Docker usage, including mounting source
images and generating sites inside the container.

## Usage

All commands below assume you are in the project root (`/Users/kangarootime/Source/RiderProjects/TI`) and the virtual environment is active.

```bash
cd /Users/kangarootime/Source/RiderProjects/TI
source .venv/bin/activate
```

### Generating a report

Run `card_diff.py` with the source and target folders for the expansion you want to compare. Name the output directory after the report.

Example — monuments (v3 vs v3.1):

```bash
python3 card_diff/card_diff.py v3/Monuments v3.1/Monuments --output exports/reports/monuments_v3_v3.1
```

This creates a fully self-contained static report site at:

```
exports/reports/monuments_v3_v3.1/
├── index.html
├── styles.css
├── results.json
└── images/
    ├── a/
    └── b/
```

Images are automatically cropped to the card shape using the mask at `Icons/Card Mask.png` before being exported. The report CSS then adds rounded corners via `border-radius`. Cropping happens **after OCR**, so text extraction is unaffected.

If your scanned card images are a different resolution than the mask, the crop is computed in relative coordinates, so the mask should still match as long as the aspect ratio is consistent.

For future expansions, use the same script with the appropriate source/target folders and a descriptive output directory name:

```bash
python3 card_diff/card_diff.py <source_folder> <target_folder> --output exports/reports/<expansion>_<version_a>_<version_b>
```

### Re-rendering a report without re-running OCR

If you edit `card_diff.py`, the CSS, or `overrides.json`, you can rebuild the HTML/CSS from the saved `results.json` without re-running the expensive OCR step:

```bash
python3 card_diff/card_diff.py v3/Monuments v3.1/Monuments \
  --output exports/reports/monuments_v3_v3.1 \
  --load-json exports/reports/monuments_v3_v3.1/results.json
```

## Reports

Each report folder is a fully self-contained static site. It can be opened directly in a browser or uploaded to an S3 bucket for public hosting.

Filters are grouped into three sections:

- **Status**: change state, severity, and visual diff filters
- **Icons**: placement icon filters
- **Abilities**: unit ability and action keyword filters

## Overrides

Use `card_diff/overrides.json` to suppress false positives or adjust placement icons:

```json
{
  "Argent.jpg": { "suppress_abilities": ["SUSTAIN DAMAGE"] },
  "Letnev.jpg": { "suppress_abilities": ["PRODUCTION"] }
}
```

Supported override fields:

- `suppress_abilities`: list of unit ability strings to remove
- `suppress_action`: set `true` to remove a detected ACTION keyword
- `add_icons`, `remove_icons`: add or remove placement icons
- `add_negated`, `remove_negated`: adjust negated placement icons

## S3 Deployment

The report folder is a standalone static site. Upload it to S3 with the **AWS CLI** (not the Python script, unless you have `boto3` installed):

```bash
aws s3 sync exports/reports/monuments_v3_v3.1 \
  s3://ti4-expansions/monuments_v3_v3.1 \
  --profile tom-local-s3
```

The report becomes available at:

```
https://ti4-expansions.s3.ap-southeast-2.amazonaws.com/monuments_v3_v3.1/index.html
```

Or, if static website hosting is enabled on the bucket:

```
http://ti4-expansions.s3-website-ap-southeast-2.amazonaws.com/monuments_v3_v3.1/
```

### Re-uploading after a re-render

Re-rendering only touches `index.html`, `styles.css`, and `results.json` when images are unchanged, so a normal sync is fast:

```bash
aws s3 sync exports/reports/monuments_v3_v3.1 \
  s3://ti4-expansions/monuments_v3_v3.1 \
  --profile tom-local-s3
```

If you ever replace image files and want to avoid re-uploading by timestamp, use `--size-only` as a fallback:

```bash
aws s3 sync exports/reports/monuments_v3_v3.1 \
  s3://ti4-expansions/monuments_v3_v3.1 \
  --profile tom-local-s3 \
  --size-only
```

### Required AWS permissions

The IAM user in your `tom-local-s3` profile needs:

- `s3:ListBucket` on `arn:aws:s3:::ti4-expansions`
- `s3:PutObject` on `arn:aws:s3:::ti4-expansions/*`

Add them via the IAM user policy or the bucket policy.

### Alternative: Python upload script

If you have `boto3` installed, you can also use:

```bash
python3 exports/s3-upload/upload.py exports/reports/monuments_v3_v3.1 --profile tom-local-s3
```

This reads `S3_AWS_REGION` and `S3_AWS_BUCKET_NAME` from `exports/s3-upload/.env`.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'boto3'`** — The Python upload script needs `boto3`. Use the AWS CLI command above instead, or install it: `pip install boto3`.
- **`AccessDenied` on `ListBucket` or `PutObject`** — The IAM user lacks permission. Add `s3:ListBucket` and `s3:PutObject` to the IAM user or bucket policy.
- **Uploaded report still shows old title or image labels** — Clear browser cache and hard-refresh. S3 may also cache objects for a short time.
- **Re-uploading every image after a re-render** — This should no longer happen. The script now skips images whose MD5 checksum already matches. Use `aws s3 sync ... --size-only` if it still does.
- **Title says `Monuments vs Monuments` instead of `Monuments v3 vs v3.1`** — The title uses the parent folder names (`v3`, `v3.1`) and the folder name (`Monuments`). Ensure you are comparing `v3/Monuments` and `v3.1/Monuments`.
