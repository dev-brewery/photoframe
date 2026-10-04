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
TARGET_BRANCH="${TARGET_BRANCH:-3.0.0}"

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

# The fork supports Raspberry Pi OS Bullseye (11) and later, the same releases as
# install.sh. Older releases lack packages it installs from apt or the Python
# version it needs (3.8 or later). Stop before touching anything on those.
OS_VERSION="$(. /etc/os-release 2>/dev/null; echo "${VERSION_ID:-}")"
if [ -n "$OS_VERSION" ] && [ "${OS_VERSION%%.*}" -lt 11 ] 2>/dev/null; then
    echo "ERROR: this system is release $OS_VERSION; the migration needs Raspberry Pi OS Bullseye (11) or later."
    echo "       Flash the current image from the releases page instead (see MIGRATION.md, Scenario B)."
    exit 1
fi

cd "$REPO_DIR"

CURRENT_REMOTE="$(git remote get-url origin 2>/dev/null || echo 'none')"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'none')"
echo "Current: $CURRENT_REMOTE  ($CURRENT_BRANCH)"
echo

# Stop the service before touching the working tree.
# (systemctl cat needs no pipe, which could fail at random under pipefail.)
if systemctl cat frame.service > /dev/null 2>&1; then
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

# Install the packages the fork needs (idempotent — apt is fine to re-run).
# The same list as install.sh: every package in requirements.txt comes from apt,
# so pip is not used (Bookworm and later refuse system-wide pip installs, PEP 668).
echo "Installing dependencies..."
apt-get update
apt-get install -y \
    python3 python3-smbus \
    python3-netifaces python3-flask python3-requests \
    python3-oauthlib python3-requests-oauthlib python3-flask-httpauth \
    imagemagick fbset git bc \
    libjpeg-turbo-progs libheif-examples \
    openssh-server

# Refresh systemd unit from the repo copy.
if [ -f "$REPO_DIR/frame.service" ]; then
    echo "Updating /etc/systemd/system/frame.service..."
    cp "$REPO_DIR/frame.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable frame.service
fi

# Start the service. The unit is enabled above whenever the repo has frame.service,
# so after a migration the frame always runs.
START_FAILED=0
if [ "$SERVICE_WAS_RUNNING" -eq 1 ] || systemctl is-enabled --quiet frame.service; then
    echo "Starting frame.service..."
    # Do not let a failed start end the script before it reports the state below.
    systemctl start frame.service || true
    sleep 5
    if systemctl is-active --quiet frame.service; then
        echo "frame.service is active."
    else
        echo "WARNING: frame.service is not active after start. Check: journalctl -u frame.service"
        START_FAILED=1
    fi
fi

echo
if [ "$START_FAILED" -eq 1 ]; then
    echo "=== Migration done, but frame.service did not start ==="
else
    echo "=== Migration complete ==="
fi
echo "Now on: $(git remote get-url origin)  ($(git rev-parse --abbrev-ref HEAD))"
echo "HEAD:   $(git log -1 --oneline)"
echo "Web UI: http://$(hostname -I 2>/dev/null | awk '{print $1}'):7777"
exit "$START_FAILED"
