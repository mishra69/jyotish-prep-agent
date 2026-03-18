#!/usr/bin/env bash
# Rolling redeploy to Cloud Run — rebuild image, push, deploy new revision.
# DB lives in GCS independently of the container; no migration needed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

source "$ROOT_DIR/.env"

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID not set in .env}"
: "${GCP_REGION:?GCP_REGION not set in .env}"

GCLOUD="${GCLOUD:-gcloud}"
IMAGE_REPO="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/jyotish/jyotish-agent"
SERVICE_NAME="jyotish-agent"

echo "=== Redeploying $SERVICE_NAME to Cloud Run ==="

"$GCLOUD" auth configure-docker "$GCP_REGION-docker.pkg.dev" --quiet

echo "--- Building image..."
docker build -t "$IMAGE_REPO:latest" "$ROOT_DIR"

echo "--- Pushing image..."
docker push "$IMAGE_REPO:latest"

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
