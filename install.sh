#!/bin/bash
#
# install.sh - Fresh install of photoframe on Raspberry Pi OS
# https://github.com/dev-brewery/photoframe
#
set -e

echo "=== Photoframe Installer ==="

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./install.sh"
    exit 1
fi

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 python3-pip \
    python3-netifaces python3-flask python3-requests \
    imagemagick fbset git bc \
    libjpeg-turbo-progs libheif-examples \
    openssh-server

# Install Python pip dependencies
echo "Installing Python dependencies..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
    pip3 install -r "${SCRIPT_DIR}/requirements.txt"
fi

# Create config directory
mkdir -p /root/photoframe_config

# Install and enable systemd service
echo "Setting up systemd service..."
cp "${SCRIPT_DIR}/frame.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable frame.service

# Set up auto-update cron
if ! grep -q "photoframe/update.sh" /etc/crontab 2>/dev/null; then
    echo "15 3 * * * root /root/photoframe/update.sh" >> /etc/crontab
fi

# Enable i2c-dev for color sensor support
if [ -f /etc/modules-load.d/modules.conf ]; then
    if ! grep -q "i2c-dev" /etc/modules-load.d/modules.conf 2>/dev/null; then
        echo "i2c-dev" >> /etc/modules-load.d/modules.conf
    fi
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Start the service:  systemctl start frame.service"
echo "Web UI:             http://$(hostname -I 2>/dev/null | awk '{print $1}'):7777"
echo "Default login:      photoframe / password"
echo ""
echo "See README-Immich.md for Immich setup instructions."
