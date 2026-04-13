#!/bin/bash -e
#
# Stage: 02-configure
# Enable services, configure hostname, install zram, Log2Ram, and boot settings.
#

# --- Enable PiLot systemd services ---
on_chroot << 'CHEOF'
systemctl enable pilot-first-boot
systemctl enable pilot-setup
CHEOF

# --- Configure hostname to "pilot" ---
echo "pilot" > "${ROOTFS_DIR}/etc/hostname"
sed -i 's/127\.0\.1\.1.*/127.0.1.1\tpilot/' "${ROOTFS_DIR}/etc/hosts"

# --- Install zram swap ---
on_chroot << 'CHEOF'
# Create zram setup script
cat > /usr/local/sbin/zram-setup.sh << 'ZRAM'
#!/bin/bash
modprobe zram
echo lz4 > /sys/block/zram0/comp_algorithm
echo 256M > /sys/block/zram0/disksize
mkswap /dev/zram0
swapon -p 100 /dev/zram0
ZRAM
chmod 755 /usr/local/sbin/zram-setup.sh

# Create zram systemd service
cat > /etc/systemd/system/zram-swap.service << 'ZRAMSVC'
[Unit]
Description=Configure zram swap device
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/zram-setup.sh
ExecStop=/bin/bash -c 'swapoff /dev/zram0 && echo 1 > /sys/block/zram0/reset'

[Install]
WantedBy=multi-user.target
ZRAMSVC
systemctl enable zram-swap
CHEOF

# --- Configure Log2Ram ---
on_chroot << 'CHEOF'
# Create log2ram setup script
cat > /usr/local/sbin/log2ram-setup.sh << 'L2R'
#!/bin/bash
SIZE=64M
LOG_DIR=/var/log
mount -t tmpfs -o "size=${SIZE},nodev,nosuid,noexec" tmpfs /var/log.hdd
rsync -a --delete "${LOG_DIR}/" /var/log.hdd/
mount --bind /var/log.hdd "${LOG_DIR}"
L2R
chmod 755 /usr/local/sbin/log2ram-setup.sh

# Create log2ram systemd service
cat > /etc/systemd/system/log2ram.service << 'L2RSVC'
[Unit]
Description=Log2Ram - mount /var/log in RAM
DefaultDependencies=no
Before=sysinit.target syslog.service rsyslog.service systemd-journald.service
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/log2ram-setup.sh
ExecStop=/bin/bash -c 'rsync -a --delete /var/log/ /var/log.hdd/ && umount /var/log'

[Install]
WantedBy=sysinit.target
L2RSVC
systemctl enable log2ram
CHEOF

# --- Copy CLAUDE.md to pilot home directory ---
if [ -f "${STAGE_DIR}/../../CLAUDE.md" ]; then
    install -d "${ROOTFS_DIR}/home/pilot"
    install -m 644 "${STAGE_DIR}/../../CLAUDE.md" "${ROOTFS_DIR}/home/pilot/CLAUDE.md"
    on_chroot << 'CHEOF'
    chown pilot:pilot /home/pilot/CLAUDE.md
CHEOF
fi

# --- Set gpu_mem=16 in config.txt ---
if [ -f "${ROOTFS_DIR}/boot/firmware/config.txt" ]; then
    # Replace existing gpu_mem line or append
    if grep -q '^gpu_mem=' "${ROOTFS_DIR}/boot/firmware/config.txt"; then
        sed -i 's/^gpu_mem=.*/gpu_mem=16/' "${ROOTFS_DIR}/boot/firmware/config.txt"
    else
        echo "gpu_mem=16" >> "${ROOTFS_DIR}/boot/firmware/config.txt"
    fi
elif [ -f "${ROOTFS_DIR}/boot/config.txt" ]; then
    if grep -q '^gpu_mem=' "${ROOTFS_DIR}/boot/config.txt"; then
        sed -i 's/^gpu_mem=.*/gpu_mem=16/' "${ROOTFS_DIR}/boot/config.txt"
    else
        echo "gpu_mem=16" >> "${ROOTFS_DIR}/boot/config.txt"
    fi
fi
