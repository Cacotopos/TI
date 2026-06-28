#!/usr/bin/env python3
"""Upload a static report site to an S3 bucket.

Usage:
    python3 exports/s3-upload/upload.py <report_dir>

The report directory name is used as the S3 key prefix. For example:

    exports/reports/report_v3_v31/

is uploaded to:

    s3://<bucket>/report_v3_v31/index.html

Credentials are read from exports/s3-upload/.env or from environment variables.
"""

import argparse
import mimetypes
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load .env from the same directory as this script if it exists
_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.is_file():
    load_dotenv(_ENV_PATH)

REQUIRED_VARS = ["S3_AWS_REGION", "S3_AWS_BUCKET_NAME"]


def upload_report(report_dir: Path, bucket: str, region: str, profile: str | None) -> None:
    if not report_dir.is_dir():
        print(f"Error: {report_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    if profile:
        session = boto3.Session(profile_name=profile)
        s3 = session.client("s3", region_name=region)
    else:
        s3 = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=os.environ.get("S3_AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("S3_AWS_SECRET_ACCESS_KEY"),
        )

    prefix = report_dir.name
    uploaded = 0

    for path in sorted(report_dir.rglob("*")):
        if not path.is_file():
            continue

        key = f"{prefix}/{path.relative_to(report_dir)}"
        content_type = mimetypes.guess_type(str(path))[0] or "binary/octet-stream"

        try:
            s3.upload_file(
                str(path),
                bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            print(f"  s3://{bucket}/{key} ({content_type})")
            uploaded += 1
        except ClientError as e:
            print(f"Error uploading {key}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"\nUploaded {uploaded} files to s3://{bucket}/{prefix}/")
    print(f"Public URL: https://{bucket}.s3.{region}.amazonaws.com/{prefix}/index.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a static report site to S3")
    parser.add_argument("report_dir", type=Path, help="Path to the report directory (e.g. exports/reports/report_v3_v31)")
    parser.add_argument("--profile", type=str, help="Use a named AWS CLI profile instead of .env credentials")
    parser.add_argument("--bucket", type=str, help="Override S3 bucket name (default: S3_AWS_BUCKET_NAME env var)")
    args = parser.parse_args()

    bucket = args.bucket or os.environ.get("S3_AWS_BUCKET_NAME")
    region = os.environ.get("S3_AWS_REGION")

    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print(f"Error: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    if not args.profile and (not os.environ.get("S3_AWS_ACCESS_KEY_ID") or not os.environ.get("S3_AWS_SECRET_ACCESS_KEY")):
        print("Error: missing S3_AWS_ACCESS_KEY_ID or S3_AWS_SECRET_ACCESS_KEY", file=sys.stderr)
        print("Either provide them via .env/env vars, or use --profile <aws-profile-name>.", file=sys.stderr)
        sys.exit(1)

    upload_report(
        args.report_dir,
        bucket,
        region,
        args.profile,
    )


if __name__ == "__main__":
    main()
