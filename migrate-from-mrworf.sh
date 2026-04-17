#!/bin/bash
#
# migrate-from-mrworf.sh - Switch an existing mrworf/photoframe install to dev-brewery/photoframe.
# https://github.com/dev-brewery/photoframe
#
# Idempotent: safe to re-run. Detects the current remote and branch and only
# acts when needed. See MIGRATION.md for the manual procedure this script
# automates (Scenario A).
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/photoframe}"
TARGET_REMOTE="https://github.com/dev-brewery/photoframe.git"
TARGET_BRANCH="${TARGET_BRANCH:-clean_3x}"

echo "=== dev-brewery/photoframe migration ==="
echo "Repo:    $REPO_DIR"
echo "Target:  $TARGET_REMOTE  ($TARGET_BRANCH)"
echo

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./migrate-from-mrworf.sh"
    exit 1
fi

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "ERROR: $REPO_DIR is not a git repository."
    echo "       Set REPO_DIR=... if photoframe lives elsewhere, or use install.sh for a fresh install."
    exit 1
fi

cd "$REPO_DIR"

CURRENT_REMOTE="$(git remote get-url origin 2>/dev/null || echo 'none')"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'none')"
echo "Current: $CURRENT_REMOTE  ($CURRENT_BRANCH)"
echo

# Stop the service before touching the working tree.
if systemctl list-unit-files | grep -q '^frame.service'; then
    SERVICE_WAS_RUNNING=0
    if systemctl is-active --quiet frame.service; then
        SERVICE_WAS_RUNNING=1
        echo "Stopping frame.service..."
        systemctl stop frame.service
    fi
else
    SERVICE_WAS_RUNNING=0
fi

# Back up live configuration.
if [ -d /root/photoframe_config ]; then
    BACKUP="/root/photoframe_config.backup.$(date +%Y%m%d-%H%M%S).tar.gz"
    echo "Backing up /root/photoframe_config -> $BACKUP"
    tar -czf "$BACKUP" -C /root photoframe_config
fi

# Swap remote if needed.
if [ "$CURRENT_REMOTE" != "$TARGET_REMOTE" ]; then
    echo "Switching remote: $CURRENT_REMOTE -> $TARGET_REMOTE"
    git remote set-url origin "$TARGET_REMOTE"
fi

echo "Fetching..."
git fetch origin

# Switch to target branch (create or reset local tracking branch).
echo "Checking out $TARGET_BRANCH..."
git checkout -B "$TARGET_BRANCH" "origin/$TARGET_BRANCH"
git pull --ff-only

# Install apt deps that the fork needs (idempotent — apt is fine to re-run).
echo "Installing apt dependencies..."
apt-get update
apt-get install -y \
    python3 python3-pip \
    python3-netifaces python3-flask python3-requests \
    imagemagick fbset git bc \
    libjpeg-turbo-progs libheif-examples \
    openssh-server

# Python pip deps.
if [ -f "$REPO_DIR/requirements.txt" ]; then
    echo "Installing pip dependencies..."
    pip3 install --break-system-packages -r "$REPO_DIR/requirements.txt" || \
        pip3 install -r "$REPO_DIR/requirements.txt"
fi

# Refresh systemd unit from the repo copy.
if [ -f "$REPO_DIR/frame.service" ]; then
    echo "Updating /etc/systemd/system/frame.service..."
    cp "$REPO_DIR/frame.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable frame.service
fi

# Restart only if the service was running before, or if it's now enabled.
if [ "$SERVICE_WAS_RUNNING" -eq 1 ] || systemctl is-enabled --quiet frame.service; then
    echo "Starting frame.service..."
    systemctl start frame.service
    sleep 2
    systemctl is-active --quiet frame.service && echo "frame.service is active." \
        || echo "WARNING: frame.service is not active after start."
fi

echo
echo "=== Migration complete ==="
echo "Now on: $(git remote get-url origin)  ($(git rev-parse --abbrev-ref HEAD))"
echo "HEAD:   $(git log -1 --oneline)"
echo "Web UI: http://$(hostname -I 2>/dev/null | awk '{print $1}'):7777"
