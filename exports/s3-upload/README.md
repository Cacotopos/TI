# S3 Upload

Scripts and scaffolding for uploading the generated static report sites to an S3 bucket for public hosting.

## Setup

1. Create `exports/s3-upload/.env` from `.env.example`:

   ```bash
   cp exports/s3-upload/.env.example exports/s3-upload/.env
   ```

2. Fill in your AWS credentials and bucket name.

## Upload a report

```bash
# Upload a single report directory
python3 exports/s3-upload/upload.py exports/reports/report_v3_v31
```

The report directory name is used as the S3 key prefix. For example, `exports/reports/report_v3_v31` is uploaded to:

```
s3://<bucket>/report_v3_v31/index.html
```

## Future additions

- `cloudformation.yaml` or `terraform/` for bucket + CloudFront distribution
- Batch upload script for all reports
- CloudFront invalidation after upload
