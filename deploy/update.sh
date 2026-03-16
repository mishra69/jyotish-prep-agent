#!/bin/bash
# Run this locally to deploy a new version to the VM.
# Usage: bash deploy/update.sh

set -e

# Load config from .env
ENV_FILE="$(dirname "$0")/../.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env not found at $ENV_FILE"
    exit 1
fi
set -a; source "$ENV_FILE"; set +a

VM_NAME="${GCP_VM_NAME}"
ZONE="${GCP_ZONE}"
export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON}"

echo "Pulling latest code on VM..."
$GCLOUD compute ssh "$VM_NAME" --zone="$ZONE" -- \
  "sudo git -C /opt/jyotish pull && sudo /opt/jyotish/venv/bin/pip install -q -r /opt/jyotish/requirements.txt && sudo chown -R www-data:www-data /opt/jyotish && sudo systemctl restart jyotish"

echo ""
echo "Done. Checking service status..."
$GCLOUD compute ssh "$VM_NAME" --zone="$ZONE" -- \
  "sudo systemctl status jyotish --no-pager"
