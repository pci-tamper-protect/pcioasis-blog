# AWS Bedrock — Luma Ray 2 (video arena)

Arena provider: `bedrock_luma` · Model: `luma.ray-v2:0` · Region: **us-west-2**

**Hub:** [`deploy/VIDEO_GENERATORS.md`](../VIDEO_GENERATORS.md)

## Prerequisites

1. **Model access:** AWS Console → Bedrock → Model access → enable Luma Ray 2 in `us-west-2`.
2. **S3 output prefix:** e.g. `s3://your-bucket/video-arena/` (bucket must exist).
3. **IAM:** permissions for async invoke + S3 read/write on that prefix.

## AWS CLI setup

```bash
aws configure
# or: export AWS_PROFILE=your-profile

aws sts get-caller-identity
aws bedrock list-foundation-models --region us-west-2 \
  --query "modelSummaries[?contains(modelId,'luma')].modelId" --output table
```

## Config file

```bash
cp deploy/aws/bedrock-luma-config.json.example /tmp/bedrock-luma.json
# edit s3_output_uri and region
```

## Load env

```bash
chmod +x deploy/aws/export-bedrock-luma.sh
eval "$(./deploy/aws/export-bedrock-luma.sh)"
```

## After generation (S3 → local MP4)

Bedrock writes async output to S3. The arena creates `DOWNLOAD.md` unless you enable download:

```bash
export VIDEO_ARENA_S3_DOWNLOAD=1
export VIDEO_ARENA_S3_OUTPUT_KEY=path/from/job/output.mp4
```

Inspect the Bedrock job response / S3 console for the object key.

## Optional: GCP Secret Manager (config only — not AWS keys)

Store the JSON **without** long-lived AWS keys if you use `aws configure` / IAM roles locally:

```bash
gcloud secrets versions add bedrock-luma-config --project=pcioasis-blog --data-file=/tmp/bedrock-luma.json
export BEDROCK_LUMA_CONFIG_GCP_SECRET=bedrock-luma-config
eval "$(./deploy/aws/export-bedrock-luma.sh)"
```

## Test

```bash
./deploy/scripts/verify-video-credentials.sh bedrock_luma
```

**Docs:** [Luma on Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-luma.html)
