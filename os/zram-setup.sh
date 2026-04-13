#!/bin/bash
# PiLot OS - ZRAM swap setup
# Provides 256MB compressed swap using lz4 for fast compression
# Installed to: /usr/lib/pilot/zram-setup.sh

set -euo pipefail

ZRAM_SIZE_MB=256
ZRAM_ALGO=lz4

# Load zram kernel module
modprobe zram num_devices=1

# Configure zram0
echo "${ZRAM_ALGO}" > /sys/block/zram0/comp_algorithm
echo "${ZRAM_SIZE_MB}M" > /sys/block/zram0/disksize

# Initialize and enable swap
mkswap /dev/zram0
swapon -p 100 /dev/zram0

echo "zram0: ${ZRAM_SIZE_MB}MB swap with ${ZRAM_ALGO} compression enabled"
