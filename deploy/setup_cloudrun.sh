#!/usr/bin/env bash
# First-time Cloud Run provisioning for jyotish-prep-agent.
# Run once from your local machine (or the VM) after setting .env values.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Load config ───────────────────────────────────────────────────────────────
source "$ROOT_DIR/.env"

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID not set in .env}"
: "${GCP_REGION:?GCP_REGION not set in .env}"
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY not set in .env}"

GCLOUD="${GCLOUD:-gcloud}"
IMAGE_REPO="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/jyotish/jyotish-agent"
SERVICE_NAME="jyotish-agent"
GCS_BUCKET="${GCS_BUCKET:-$GCP_PROJECT_ID-jyotish-db}"
SA_NAME="jyotish-cloudrun"
SA_EMAIL="$SA_NAME@$GCP_PROJECT_ID.iam.gserviceaccount.com"

echo "=== Cloud Run setup for project: $GCP_PROJECT_ID ==="

# ── 1. Enable APIs ────────────────────────────────────────────────────────────
echo "--- Enabling required APIs..."
"$GCLOUD" services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    storage.googleapis.com \
    --project="$GCP_PROJECT_ID"

# ── 2. Create GCS bucket ──────────────────────────────────────────────────────
echo "--- Creating GCS bucket: $GCS_BUCKET..."
if ! "$GCLOUD" storage buckets describe "gs://$GCS_BUCKET" --project="$GCP_PROJECT_ID" &>/dev/null; then
    "$GCLOUD" storage buckets create "gs://$GCS_BUCKET" \
        --project="$GCP_PROJECT_ID" \
        --location="$GCP_REGION" \
        --uniform-bucket-level-access
    echo "    Bucket created."
else
    echo "    Bucket already exists."
fi

# ── 3. Seed GCS with existing DB (if present) ─────────────────────────────────
LOCAL_DB="$ROOT_DIR/jyotish.db"
if [[ -f "$LOCAL_DB" ]]; then
    echo "--- Uploading existing jyotish.db to GCS (seeds past consultations)..."
    "$GCLOUD" storage cp "$LOCAL_DB" "gs://$GCS_BUCKET/jyotish.db" --project="$GCP_PROJECT_ID"
    echo "    DB uploaded."
else
    echo "    No local jyotish.db found — bucket will start empty."
fi

# ── 4. Create Artifact Registry repo ─────────────────────────────────────────
echo "--- Creating Artifact Registry repo: jyotish..."
if ! "$GCLOUD" artifacts repositories describe jyotish \
        --location="$GCP_REGION" --project="$GCP_PROJECT_ID" &>/dev/null; then
    "$GCLOUD" artifacts repositories create jyotish \
        --repository-format=docker \
        --location="$GCP_REGION" \
        --project="$GCP_PROJECT_ID"
    echo "    Repo created."
else
    echo "    Repo already exists."
fi

# ── 5. Configure Docker auth ──────────────────────────────────────────────────
"$GCLOUD" auth configure-docker "$GCP_REGION-docker.pkg.dev" --quiet

# ── 6. Build and push Docker image ────────────────────────────────────────────
echo "--- Building Docker image..."
docker build -t "$IMAGE_REPO:latest" "$ROOT_DIR"

echo "--- Pushing Docker image..."
docker push "$IMAGE_REPO:latest"

# ── 7. Create service account ─────────────────────────────────────────────────
echo "--- Setting up service account: $SA_EMAIL..."
if ! "$GCLOUD" iam service-accounts describe "$SA_EMAIL" --project="$GCP_PROJECT_ID" &>/dev/null; then
    "$GCLOUD" iam service-accounts create "$SA_NAME" \
        --display-name="Jyotish Cloud Run SA" \
        --project="$GCP_PROJECT_ID"
    echo "    Service account created."
else
    echo "    Service account already exists."
fi

# Grant storage.objectAdmin on the bucket
"$GCLOUD" storage buckets add-iam-policy-binding "gs://$GCS_BUCKET" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectAdmin" \
    --project="$GCP_PROJECT_ID"

# ── 8. Deploy Cloud Run service ───────────────────────────────────────────────
echo "--- Deploying Cloud Run service: $SERVICE_NAME..."
"$GCLOUD" run deploy "$SERVICE_NAME" \
    --image="$IMAGE_REPO:latest" \
    --region="$GCP_REGION" \
    --project="$GCP_PROJECT_ID" \
    --platform=managed \
    --service-account="$SA_EMAIL" \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --cpu=1 \
    --timeout=300 \
    --allow-unauthenticated \
    --set-env-vars="OPENROUTER_API_KEY=$OPENROUTER_API_KEY,GCS_BUCKET=$GCS_BUCKET"

# ── 9. Print URL and next steps ───────────────────────────────────────────────
URL=$("$GCLOUD" run services describe "$SERVICE_NAME" \
    --region="$GCP_REGION" \
    --project="$GCP_PROJECT_ID" \
    --format="value(status.url)")

echo ""
echo "=== Deployment complete ==="
echo "Cloud Run URL: $URL"
echo ""
echo "Next steps:"
echo "  1. Verify at $URL"
echo "  2. Test session recovery: $URL?t=<old-thread-id>"
echo "  3. Map custom domain:"
echo "     $GCLOUD run domain-mappings create --service=$SERVICE_NAME --domain=YOUR_DOMAIN --region=$GCP_REGION --project=$GCP_PROJECT_ID"
echo "  4. Update DNS CNAME to: ghs.googlehosted.com"
echo "  5. Once verified, stop the VM:"
echo "     $GCLOUD compute instances stop \${GCP_VM_NAME:-jyotish-agent} --zone=\${GCP_ZONE:-us-central1-a} --project=$GCP_PROJECT_ID"
