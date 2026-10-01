#!/bin/bash

set -euo pipefail

APP_NAME="barcode_camera"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"
SERVICE_USER="$(id -un)"
if [ "$SERVICE_USER" = "root" ]; then
    echo "Run ./install.sh as the account that should run the camera (for example admin), without sudo."
    exit 1
fi
CONFIG_CREATED=false

echo "======================================"
echo "Installing Barcode Camera"
echo "======================================"

echo "Updating package lists..."
sudo apt update

echo "Installing system packages..."
sudo apt install -y \
    python3 \
    python3-opencv \
    python3-evdev \
    python3-yaml \
    python3-venv \
    git

CONFIG_FILE="$APP_DIR/config.yaml"
CONFIG_EXAMPLE="$APP_DIR/config.example.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating config.yaml from the example configuration..."
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    CONFIG_CREATED=true
    echo "Edit $CONFIG_FILE with this Pi's camera, scanner, and storage settings."
fi

echo "Creating Python virtual environment..."

# Stop the existing process before changing its Python environment.
if sudo systemctl is-active --quiet "$APP_NAME.service"; then
    sudo systemctl stop "$APP_NAME.service"
fi

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

echo "Installing Azure Python packages..."

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

echo "Creating image directory..."

mkdir -p "$HOME/Production_Photos"

echo "Installing systemd service..."
SERVICE_FILE="$(mktemp)"
trap 'rm -f "$SERVICE_FILE"' EXIT
python3 "$APP_DIR/scripts/render_service.py" "$APP_DIR" "$SERVICE_USER" > "$SERVICE_FILE"
sudo install -m 0644 "$SERVICE_FILE" "/etc/systemd/system/$APP_NAME.service"
sudo systemd-analyze verify "/etc/systemd/system/$APP_NAME.service"
sudo systemctl daemon-reload
sudo systemctl enable "$APP_NAME.service"
if [ "$CONFIG_CREATED" = false ]; then
    sudo systemctl restart "$APP_NAME.service"
    sudo systemctl status "$APP_NAME.service" --no-pager
else
    echo "Service installed and enabled. Edit config.yaml before starting it:"
    echo "sudo systemctl start $APP_NAME.service"
fi

echo
echo "======================================"
echo "Installation complete!"
echo "======================================"
