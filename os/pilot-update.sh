#!/bin/bash
# PiLot OS - OTA update via GitHub Releases
# Installed to: /usr/lib/pilot/pilot-update.sh
# Checks for new release, downloads, backs up DB, stops services, extracts, migrates, restarts

set -euo pipefail

REPO="rtck/pilot"
INSTALL_DIR="/opt/pilot"
DATA_DIR="/var/lib/pilot"
BACKUP_DIR="${DATA_DIR}/backups"
CURRENT_VERSION_FILE="${INSTALL_DIR}/.version"
DOWNLOAD_DIR=$(mktemp -d)

cleanup() {
    rm -rf "${DOWNLOAD_DIR}"
}
trap cleanup EXIT

# --- Read current version ---
CURRENT_VERSION="0.0.0"
if [ -f "${CURRENT_VERSION_FILE}" ]; then
    CURRENT_VERSION=$(cat "${CURRENT_VERSION_FILE}")
fi
echo "Current version: ${CURRENT_VERSION}"

# --- Check for latest release ---
echo "Checking for updates..."
LATEST_RELEASE=$(gh release view --repo "${REPO}" --json tagName,assets -q '.')
LATEST_VERSION=$(echo "${LATEST_RELEASE}" | jq -r '.tagName' | sed 's/^v//')

if [ -z "${LATEST_VERSION}" ] || [ "${LATEST_VERSION}" = "null" ]; then
    echo "ERROR: Could not determine latest version"
    exit 1
fi

echo "Latest version: ${LATEST_VERSION}"

if [ "${CURRENT_VERSION}" = "${LATEST_VERSION}" ]; then
    echo "Already up to date."
    exit 0
fi

echo "Updating from ${CURRENT_VERSION} to ${LATEST_VERSION}..."

# --- Download release asset ---
echo "Downloading release..."
gh release download "v${LATEST_VERSION}" \
    --repo "${REPO}" \
    --pattern "pilot-*.tar.gz" \
    --dir "${DOWNLOAD_DIR}"

ARCHIVE=$(find "${DOWNLOAD_DIR}" -name "pilot-*.tar.gz" | head -1)
if [ -z "${ARCHIVE}" ]; then
    echo "ERROR: No release archive found"
    exit 1
fi

# --- Backup database ---
echo "Backing up database..."
mkdir -p "${BACKUP_DIR}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [ -f "${DATA_DIR}/db/pilot.db" ]; then
    cp "${DATA_DIR}/db/pilot.db" "${BACKUP_DIR}/pilot_${TIMESTAMP}.db"
    echo "Database backed up to ${BACKUP_DIR}/pilot_${TIMESTAMP}.db"
fi

# --- Stop services ---
echo "Stopping PiLot services..."
systemctl stop tesla-poller.service || true
systemctl stop pilot-dashboard.service || true
systemctl stop pilot-kiosk.service || true
systemctl stop pilot-watchdog.service || true

# --- Extract new release ---
echo "Extracting update..."
tar -xzf "${ARCHIVE}" -C "${INSTALL_DIR}" --strip-components=1

# --- Update version marker ---
echo "${LATEST_VERSION}" > "${CURRENT_VERSION_FILE}"

# --- Run database migrations if migration script exists ---
if [ -f "${INSTALL_DIR}/migrate.sh" ]; then
    echo "Running database migrations..."
    bash "${INSTALL_DIR}/migrate.sh"
fi

# --- Reinstall Python dependencies ---
if [ -f "${INSTALL_DIR}/requirements.txt" ]; then
    echo "Updating Python dependencies..."
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" --quiet
fi

# --- Set permissions ---
chown -R pilot:pilot "${INSTALL_DIR}"

# --- Restart services ---
echo "Restarting PiLot services..."
systemctl start tesla-poller.service
systemctl start pilot-dashboard.service
systemctl start pilot-watchdog.service

echo "=== PiLot OS: Updated to v${LATEST_VERSION} ==="
