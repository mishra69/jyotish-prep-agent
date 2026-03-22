#!/usr/bin/env bash
# Rolling redeploy to Cloud Run — rebuild image, push, deploy new revision.
# DB lives in GCS independently of the container; no migration needed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

source "$ROOT_DIR/.env"

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID not set in .env}"
: "${GCP_REGION:?GCP_REGION not set in .env}"

export CLOUDSDK_PYTHON

GCLOUD="${GCLOUD:-gcloud}"
IMAGE_REPO="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/jyotish/jyotish-agent"
SERVICE_NAME="jyotish-agent"

echo "=== Redeploying $SERVICE_NAME to Cloud Run ==="

echo "--- Building and pushing image via Cloud Build..."
"$GCLOUD" builds submit "$ROOT_DIR" \
    --tag="$IMAGE_REPO:latest" \
    --project="$GCP_PROJECT_ID" \
    --region="$GCP_REGION"

echo "--- Deploying new revision..."
"$GCLOUD" run deploy "$SERVICE_NAME" \
    --image="$IMAGE_REPO:latest" \
    --region="$GCP_REGION" \
    --project="$GCP_PROJECT_ID" \
    --platform=managed

URL=$("$GCLOUD" run services describe "$SERVICE_NAME" \
    --region="$GCP_REGION" \
    --project="$GCP_PROJECT_ID" \
    --format="value(status.url)")

echo ""
echo "=== Redeploy complete ==="
echo "URL: $URL"
