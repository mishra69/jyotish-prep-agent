#!/bin/bash
# Run this ON THE VM after SSH-ing in.
# Installs all dependencies, clones the repo, and starts the app.
#
# Usage (from your Mac):
#   gcloud compute scp deploy/setup_server.sh jyotish-agent:/tmp/ --zone=us-central1-a
#   gcloud compute scp .env jyotish-agent:/tmp/.env --zone=us-central1-a
#   gcloud compute ssh jyotish-agent --zone=us-central1-a -- "bash /tmp/setup_server.sh"

set -e

REPO_URL="https://github.com/mishra69/jyotish-prep-agent.git"
APP_DIR="/opt/jyotish"
ENV_FILE="/etc/jyotish/.env"
PYTHON="python3"

echo "============================================================"
echo "Jyotish Agent — Server Setup"
echo "============================================================"

# ── System packages ───────────────────────────────────────────────────────────
echo ""
echo "[1/6] Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y -q python3 python3-pip python3-venv git curl

# ── Caddy ─────────────────────────────────────────────────────────────────────
echo ""
echo "[2/6] Installing Caddy..."
if ! command -v caddy &> /dev/null; then
  sudo apt-get install -y -q debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update -q
  sudo apt-get install -y -q caddy
fi
echo "Caddy installed."

# ── App code ──────────────────────────────────────────────────────────────────
echo ""
echo "[3/6] Cloning repository..."
if [ -d "$APP_DIR/.git" ]; then
  sudo git -C "$APP_DIR" pull
else
  sudo git clone "$REPO_URL" "$APP_DIR"
fi

echo "Setting up Python venv..."
sudo $PYTHON -m venv "$APP_DIR/venv"
sudo "$APP_DIR/venv/bin/pip" install -q --upgrade pip
sudo "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# ── Env file ──────────────────────────────────────────────────────────────────
echo ""
echo "[4/6] Installing env file..."
sudo mkdir -p /etc/jyotish
sudo cp /tmp/.env "$ENV_FILE"
sudo chmod 600 "$ENV_FILE"
sudo chown root:root "$ENV_FILE"
echo "Env file installed at $ENV_FILE"

# ── Caddyfile ─────────────────────────────────────────────────────────────────
echo ""
echo "[5/6] Configuring Caddy..."
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
:80 {
    reverse_proxy localhost:8501
}
EOF
sudo systemctl restart caddy
sudo systemctl enable caddy
echo "Caddy configured and running."

# ── Systemd service ───────────────────────────────────────────────────────────
echo ""
echo "[6/6] Installing systemd service..."
sudo tee /etc/systemd/system/jyotish.service > /dev/null <<EOF
[Unit]
Description=Jyotish Prep Agent
After=network.target

[Service]
User=www-data
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
Environment=HOME=$APP_DIR
ExecStart=$APP_DIR/venv/bin/streamlit run ui/app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo chown -R www-data:www-data "$APP_DIR"
sudo systemctl daemon-reload
sudo systemctl enable jyotish
sudo systemctl restart jyotish

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "Setup complete!"
echo ""
echo "Service status:"
sudo systemctl status jyotish --no-pager
echo ""
echo "Caddy status:"
sudo systemctl status caddy --no-pager
echo ""
echo "App should be live at: http://jyotish-agent.poojamishra.com"
echo "(DNS may take a few minutes to propagate)"
echo "============================================================"
