#!/bin/bash
# PiLot OS - HDMI hotplug handler
# Starts/stops pilot-kiosk.service based on HDMI connection state
# Installed to: /usr/lib/pilot/hdmi-detect.sh

set -euo pipefail

KIOSK_SERVICE="pilot-kiosk.service"

hdmi_connected() {
    for card in /sys/class/drm/card*-HDMI-A-*; do
        if [ -f "${card}/status" ]; then
            status=$(cat "${card}/status")
            if [ "${status}" = "connected" ]; then
                return 0
            fi
        fi
    done
    return 1
}

if hdmi_connected; then
    echo "HDMI connected - starting kiosk"
    systemctl start "${KIOSK_SERVICE}" || true
else
    echo "HDMI disconnected - stopping kiosk"
    systemctl stop "${KIOSK_SERVICE}" || true
fi
