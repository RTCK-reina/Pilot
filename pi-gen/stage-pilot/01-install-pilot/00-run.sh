#!/bin/bash -e
#
# Stage: 01-install-pilot
# Install PiLot application, Python venv, systemd units, and OS config files.
#

# --- Create pilot system user ---
on_chroot << 'CHEOF'
if ! id -u pilot >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/pilot --shell /usr/sbin/nologin pilot
fi
CHEOF

# --- Create directory structure ---
install -d "${ROOTFS_DIR}/opt/pilot"
install -d "${ROOTFS_DIR}/opt/pilot/src"
install -d "${ROOTFS_DIR}/var/lib/pilot"
install -d "${ROOTFS_DIR}/var/lib/pilot/db"
install -d "${ROOTFS_DIR}/var/lib/pilot/backups"
install -d -m 700 "${ROOTFS_DIR}/var/lib/pilot/secrets"

# --- Create Python venv and install dependencies ---
# Stage the requirements file into the chroot before running pip
install -m 644 "${STAGE_DIR}/../../requirements.txt" "${ROOTFS_DIR}/tmp/pilot-requirements.txt"

on_chroot << 'CHEOF'
python3 -m venv /opt/pilot/venv
/opt/pilot/venv/bin/pip install --upgrade pip
/opt/pilot/venv/bin/pip install -r /tmp/pilot-requirements.txt
rm -f /tmp/pilot-requirements.txt
CHEOF

# --- Copy application source code ---
cp -a "${STAGE_DIR}/../../src/." "${ROOTFS_DIR}/opt/pilot/src/"

# --- Copy static vendor files (chart.js, leaflet.js) if present ---
if [ -d "${STAGE_DIR}/../../src/pilot_dashboard/static/vendor" ]; then
    cp -a "${STAGE_DIR}/../../src/pilot_dashboard/static/vendor/." \
        "${ROOTFS_DIR}/opt/pilot/src/pilot_dashboard/static/vendor/"
fi

# --- Install systemd unit files ---
for unit_file in "${STAGE_DIR}/../../systemd/"*.service "${STAGE_DIR}/../../systemd/"*.timer; do
    if [ -f "${unit_file}" ]; then
        install -m 644 "${unit_file}" "${ROOTFS_DIR}/etc/systemd/system/"
    fi
done

# --- Install OS config files ---

# nftables firewall rules
if [ -f "${STAGE_DIR}/../../os/nftables.conf" ]; then
    install -m 644 "${STAGE_DIR}/../../os/nftables.conf" "${ROOTFS_DIR}/etc/nftables.conf"
fi

# journald configuration
if [ -f "${STAGE_DIR}/../../os/journald.conf" ]; then
    install -m 644 "${STAGE_DIR}/../../os/journald.conf" "${ROOTFS_DIR}/etc/systemd/journald.conf"
fi

# fstab overlay
if [ -f "${STAGE_DIR}/../../os/fstab" ]; then
    install -m 644 "${STAGE_DIR}/../../os/fstab" "${ROOTFS_DIR}/etc/fstab"
fi

# tmpfiles.d configuration
if [ -d "${STAGE_DIR}/../../os/tmpfiles.d" ]; then
    install -d "${ROOTFS_DIR}/etc/tmpfiles.d"
    for tmpfile in "${STAGE_DIR}/../../os/tmpfiles.d/"*; do
        if [ -f "${tmpfile}" ]; then
            install -m 644 "${tmpfile}" "${ROOTFS_DIR}/etc/tmpfiles.d/"
        fi
    done
fi

# --- Set ownership and permissions ---
on_chroot << 'CHEOF'
chown -R pilot:pilot /opt/pilot
chown -R pilot:pilot /var/lib/pilot
chmod 700 /var/lib/pilot/secrets
CHEOF
