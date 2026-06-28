#!/usr/bin/env python3
"""Create the S3 bucket configured in .env.

Usage:
    python3 exports/s3-upload/create_bucket.py
"""

import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

REQUIRED_VARS = ["S3_AWS_REGION", "S3_AWS_BUCKET_NAME", "S3_AWS_ACCESS_KEY_ID", "S3_AWS_SECRET_ACCESS_KEY"]

missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
if missing:
    print(f"Error: missing environment variables: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

region = os.environ["S3_AWS_REGION"]
bucket = os.environ["S3_AWS_BUCKET_NAME"]

s3 = boto3.client(
    "s3",
    region_name=region,
    aws_access_key_id=os.environ["S3_AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["S3_AWS_SECRET_ACCESS_KEY"],
)

try:
    # LocationConstraint is required when the region is not us-east-1
    if region == "us-east-1":
        s3.create_bucket(Bucket=bucket)
    else:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": region},
        )
    print(f"Created bucket: s3://{bucket} in {region}")
except s3.exceptions.BucketAlreadyExists as e:
    print(f"Bucket already exists (owned by someone else): {bucket}")
    sys.exit(1)
except s3.exceptions.BucketAlreadyOwnedByYou:
    print(f"Bucket already exists and is owned by you: s3://{bucket}")
except Exception as e:
    print(f"Error creating bucket: {e}", file=sys.stderr)
    sys.exit(1)
