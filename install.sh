#!/bin/bash

set -e

APP_NAME="barcode_camera"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"
SERVICE_FILE="$APP_DIR/barcode_camera.service"

echo "======================================"
echo "Installing Barcode Camera"
echo "======================================"

echo "Updating package lists..."
sudo apt update

echo "Installing system packages..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-opencv \
    python3-evdev \
    python3-requests \
    python3-msal \
    git

echo "Creating Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

echo "Installing Python packages..."

source "$VENV_DIR/bin/activate"

pip install --upgrade pip

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

deactivate

echo "Creating image directory..."

mkdir -p "$HOME/Production_Photos"

echo "Installing systemd service..."

sudo cp "$SERVICE_FILE" /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable barcode_camera.service

sudo systemctl restart barcode_camera.service

echo
echo "======================================"
echo "Installation complete!"
echo "======================================"

echo
echo "Service status:"
sudo systemctl --no-pager status barcode_camera.service