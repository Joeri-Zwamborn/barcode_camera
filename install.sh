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
    echo "Edit $CONFIG_FILE with this Pi's camera, scanner, and storage settings."
fi

echo "Creating Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

echo "Installing Azure Python packages..."

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

echo "Creating image directory..."

mkdir -p "$HOME/Production_Photos"

echo
echo "======================================"
echo "Installation complete!"
echo "======================================"
