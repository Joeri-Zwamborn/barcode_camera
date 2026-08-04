#!/bin/bash

set -e

APP_NAME="barcode_camera"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"

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

CONFIG_FILE="$APP_DIR/config.yaml"
CONFIG_EXAMPLE="$APP_DIR/config.example.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating config.yaml from the example configuration..."
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    echo "Edit $CONFIG_FILE with this Pi's camera, scanner, and storage settings."
fi

echo "Creating Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
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

sudo systemctl daemon-reload

echo
echo "======================================"
echo "Installation complete!"
echo "======================================"
