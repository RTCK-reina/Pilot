#!/bin/bash
# PiLot OS - First boot initialization
# Installed to: /usr/lib/pilot/first-boot.sh
# Runs once via pilot-first-boot.service, then marks completion

set -euo pipefail

echo "=== PiLot OS: First boot initialization ==="

# --- Resize root filesystem to fill SD card ---
echo "Resizing root filesystem..."
ROOT_PART=$(findmnt -n -o SOURCE /)
ROOT_DEV=$(lsblk -no PKNAME "${ROOT_PART}")
PART_NUM=$(echo "${ROOT_PART}" | grep -oE '[0-9]+$')

if command -v raspi-config >/dev/null 2>&1; then
    raspi-config --expand-rootfs || true
else
    growpart "/dev/${ROOT_DEV}" "${PART_NUM}" || true
    resize2fs "${ROOT_PART}" || true
fi

# --- Create pilot user if it does not exist ---
if ! id -u pilot >/dev/null 2>&1; then
    echo "Creating pilot user..."
    useradd --system --home-dir /var/lib/pilot --shell /usr/sbin/nologin pilot
fi

# --- Create required directories ---
echo "Creating PiLot directories..."
mkdir -p /var/lib/pilot
mkdir -p /var/lib/pilot/db
mkdir -p /var/lib/pilot/backups
mkdir -p /run/pilot

# --- Set ownership and permissions ---
echo "Setting permissions..."
chown -R pilot:pilot /var/lib/pilot
chmod 0750 /var/lib/pilot
chown pilot:pilot /run/pilot
chmod 0755 /run/pilot

# Ensure the venv and src directories are accessible
if [ -d /opt/pilot ]; then
    chown -R pilot:pilot /opt/pilot
fi

# --- Mark first boot as complete ---
touch /var/lib/pilot/.first-boot-done
echo "=== PiLot OS: First boot complete ==="
