#!/bin/bash
# Run this locally to deploy a new version to the VM.
# Usage: bash deploy/update.sh

set -e

GCLOUD="$HOME/Downloads/google-cloud-sdk/bin/gcloud"
VM_NAME="jyotish-agent"
ZONE="us-central1-a"

export CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.11

echo "Pulling latest code on VM..."
$GCLOUD compute ssh "$VM_NAME" --zone="$ZONE" -- \
  "sudo git -C /opt/jyotish pull && sudo /opt/jyotish/venv/bin/pip install -q -r /opt/jyotish/requirements.txt && sudo chown -R www-data:www-data /opt/jyotish && sudo systemctl restart jyotish"

echo ""
echo "Done. Checking service status..."
$GCLOUD compute ssh "$VM_NAME" --zone="$ZONE" -- \
  "sudo systemctl status jyotish --no-pager"
