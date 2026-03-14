#!/bin/bash
# Run this locally (on your Mac) to provision the GCP VM.
# Prerequisites: gcloud CLI installed and authenticated.
#
# Usage:
#   chmod +x deploy/setup_gcp.sh
#   ./deploy/setup_gcp.sh

set -e

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID=""          # Fill in: your GCP project ID (gcloud projects list)
REGION="us-central1"
ZONE="us-central1-a"
VM_NAME="jyotish-agent"
MACHINE_TYPE="e2-micro"
DISK_SIZE="20GB"
IMAGE_FAMILY="ubuntu-2404-lts-amd64"
IMAGE_PROJECT="ubuntu-os-cloud"

# ── Validate ──────────────────────────────────────────────────────────────────
if [ -z "$PROJECT_ID" ]; then
  echo "Error: Set PROJECT_ID at the top of this script."
  echo "Run 'gcloud projects list' to find your project ID."
  exit 1
fi

echo "Using project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# ── Reserve static IP ─────────────────────────────────────────────────────────
echo ""
echo "Reserving static external IP..."
gcloud compute addresses create jyotish-ip \
  --region="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || echo "(IP already exists, skipping)"

STATIC_IP=$(gcloud compute addresses describe jyotish-ip \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format="get(address)")
echo "Static IP: $STATIC_IP"

# ── Create VM ─────────────────────────────────────────────────────────────────
echo ""
echo "Creating VM..."
gcloud compute instances create "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --image-family="$IMAGE_FAMILY" \
  --image-project="$IMAGE_PROJECT" \
  --boot-disk-size="$DISK_SIZE" \
  --address="$STATIC_IP" \
  --tags="jyotish-http" \
  --metadata="startup-script=#! /bin/bash
apt-get update -q" 2>/dev/null || echo "(VM already exists, skipping)"

# ── Firewall rule ─────────────────────────────────────────────────────────────
echo ""
echo "Creating firewall rule for port 80..."
gcloud compute firewall-rules create jyotish-allow-http \
  --project="$PROJECT_ID" \
  --allow=tcp:80 \
  --target-tags="jyotish-http" \
  --description="Allow HTTP for Jyotish agent (HTTPS handled by Cloudflare)" \
  2>/dev/null || echo "(Firewall rule already exists, skipping)"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "VM created successfully!"
echo "Static IP: $STATIC_IP"
echo ""
echo "Next steps:"
echo "  1. Add a DNS A record in Cloudflare:"
echo "     Name: jyotish-agent"
echo "     Value: $STATIC_IP"
echo "     Proxy: ON (orange cloud)"
echo ""
echo "  2. Copy your .env to the VM:"
echo "     gcloud compute scp .env $VM_NAME:/tmp/.env --zone=$ZONE"
echo ""
echo "  3. SSH into the VM and run setup_server.sh:"
echo "     gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "     bash /tmp/setup_server.sh"
echo "============================================================"
